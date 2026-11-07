"""Preview-only Vercel adapter. Workspace authority is not a human client review."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from . import state, web
from .publication import write_json
from .transactions import run_lock


def validate_policy(policy):
    allowed={'version','authority','owner','project_id','org_id','target','credential_ref'}
    if (set(policy)!=allowed or policy.get('version')!=1
            or policy.get('authority')!='workspace_publication_policy'
            or policy.get('target')!='preview' or not policy.get('owner')):
        raise ValueError('An explicit preview-only workspace publication policy is required')
    for field in ('project_id','org_id'):
        if not isinstance(policy[field],str) or not re.fullmatch(r'[A-Za-z0-9_-]+',policy[field]):
            raise ValueError('Publication project and organization identifiers are required')
    reference=policy['credential_ref']
    if reference!='vercel_cli' and not re.fullmatch(r'env:[A-Z][A-Z0-9_]*',reference):
        raise ValueError('Credentials must be private references, not inline secrets')
    return dict(policy)


def _auth_directory():
    if sys.platform=='darwin':
        return Path.home()/'Library/Application Support/com.vercel.cli'
    if os.name=='nt':
        return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'com.vercel.cli'
    return Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'com.vercel.cli'


def _token(policy):
    reference=policy['credential_ref']
    if reference.startswith('env:'):
        token=os.environ.get(reference[4:])
    else:
        path=_auth_directory()/'auth.json'
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
            raise ValueError('Vercel CLI authentication is unavailable')
        token=json.loads(path.read_text()).get('token')
    if not isinstance(token,str) or not token:
        raise ValueError('The configured Vercel credential is unavailable')
    return token


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None


def _api_json(path,policy):
    if not path.startswith(('/v9/projects/','/v6/deployments','/v13/deployments/')):
        raise ValueError('Unsupported publication readback')
    request=Request('https://api.vercel.com'+path,headers={'Authorization':'Bearer '+_token(policy)})
    try:
        with build_opener(_NoRedirect).open(request,timeout=10) as response:
            data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:
            raise ValueError('Vercel readback exceeds its bounded response budget')
        return json.loads(data)
    except (HTTPError,URLError,TimeoutError) as error:
        raise ValueError('Authorized Vercel readback unavailable; no automatic write retry') from error


@contextmanager
def _cli_credentials(policy):
    if policy['credential_ref']=='vercel_cli':
        yield []
        return
    # Environment credentials are supplied through a private temporary CLI
    # config, never through process arguments or a public build directory.
    with tempfile.TemporaryDirectory(prefix='vertigo-vercel-auth-') as folder:
        path=Path(folder)/'auth.json'
        descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'w') as stream:
            json.dump({'token':_token(policy)},stream)
        yield ['--global-config',folder]


def _deployment_url(value):
    value=value if str(value).startswith('https://') else 'https://'+str(value)
    parsed=urlsplit(value)
    if (parsed.scheme!='https' or parsed.username or parsed.password or parsed.port
            or parsed.path not in ('','/') or parsed.query or parsed.fragment
            or not re.fullmatch(r'[a-zA-Z0-9-]+\.vercel\.app',parsed.hostname or '')):
        raise ValueError('A unique Vercel deployment URL is required')
    return value.rstrip('/')


def deployment_stdout(stdout):
    """Native CLI emits structured JSON in non-TTY execution."""
    if not isinstance(stdout,str) or len(stdout)>1024*1024:
        raise ValueError('Deployment output is missing or exceeds its budget')
    try:record=json.loads(stdout)
    except json.JSONDecodeError:return _deployment_url(stdout.strip())
    if (not isinstance(record,dict) or record.get('status')!='ok'
            or not isinstance(record.get('deployment'),dict) or not record['deployment'].get('url')):
        raise ValueError('CLI response does not confirm a deployment; reconcile before another write')
    return _deployment_url(record['deployment']['url'])


class VercelPreviewAdapter:
    def __init__(self,policy):
        self.policy=validate_policy(policy)

    def project(self):
        policy=self.policy
        project=_api_json('/v9/projects/'+policy['project_id']+'?'+urlencode({'teamId':policy['org_id']}),policy)
        if project.get('id')!=policy['project_id'] or project.get('accountId')!=policy['org_id']:
            raise ValueError('Vercel project or owner does not match the workspace policy')
        # Vercel makes a project's first deployment production even without
        # --prod. Initial provisioning must happen separately at installation.
        if not (project.get('targets') or {}).get('production',{}).get('id'):
            raise ValueError('Project bootstrap is not complete; refuse a first production deployment')
        if project.get('ssoProtection') or project.get('passwordProtection'):
            raise ValueError('The selected project protects preview URLs; do not change existing site settings')
        return project

    def _record(self,deployment,key,run_id,build_id):
        metadata=deployment.get('meta') or {}
        if (deployment.get('projectId')!=self.policy['project_id']
                or deployment.get('target') not in (None,'preview')
                or any(metadata.get(k)!=v for k,v in {'vertigo_operation':key,
                    'vertigo_run':run_id,'vertigo_build':build_id}.items())):
            raise ValueError('Deployment readback belongs to a different project, target or build')
        status=deployment.get('readyState',deployment.get('state'))
        return {'status':'DEPLOYED' if status=='READY' else 'FAILED' if status in ('ERROR','CANCELED') else 'DEPLOYING',
            'deployment_id':deployment.get('id',deployment.get('uid')),
            'url':_deployment_url(deployment['url']) if deployment.get('url') else None,
            'provider_state':status,'build_id':build_id,'project_id':self.policy['project_id'],
            'org_id':self.policy['org_id'],'target':'preview','operation_key':key}

    def lookup(self,key,run_id,build_id):
        # A bounded absence after an uncertain write never authorizes a retry.
        query={'projectId':self.policy['project_id'],'teamId':self.policy['org_id'],
               'limit':100,'meta-vertigo_operation':key}
        result=_api_json('/v6/deployments?'+urlencode(query),self.policy)
        matches=[d for d in result.get('deployments',[]) if (d.get('meta') or {}).get('vertigo_operation')==key]
        if len(matches)>1:
            raise ValueError('More than one deployment matches the operation; manual reconciliation required')
        return self._record(matches[0],key,run_id,build_id) if matches else None

    def deploy(self,directory,key,run_id,build_id):
        executable=_vercel_executable()
        web.verify_bundle(directory)
        with tempfile.TemporaryDirectory(prefix='vertigo-preview-payload-') as temporary, _cli_credentials(self.policy) as auth:
            payload=Path(temporary)
            shutil.copytree(Path(directory)/'.vercel/output',payload/'.vercel/output')
            (payload/'.vercel/project.json').write_bytes(web._canonical({
                'projectId':self.policy['project_id'],'orgId':self.policy['org_id']}))
            command=[executable,'deploy','--prebuilt','--environment','preview','--json','--yes','--no-color',
                '--scope',self.policy['org_id'],'--cwd',str(payload),*auth]
            for name,value in {'vertigo_operation':key,'vertigo_run':run_id,'vertigo_build':build_id}.items():
                command.extend(['--meta',name+'='+value])
            environment=dict(os.environ,VERCEL_ORG_ID=self.policy['org_id'],
                VERCEL_PROJECT_ID=self.policy['project_id'],VERCEL_TELEMETRY_DISABLED='1',CI='1')
            # The process receives only the isolated prebuilt payload. Neither
            # plan, receipt, private profile nor run metadata is copied there.
            completed=subprocess.run(command,env=environment,capture_output=True,text=True,timeout=120)
            if completed.returncode:
                raise OSError('Vercel command outcome is unconfirmed')
            url=deployment_stdout(completed.stdout)
            deployment=_api_json('/v13/deployments/'+quote(urlsplit(url).hostname,safe='')+'?'+urlencode({'teamId':self.policy['org_id']}),self.policy)
            return self._record(deployment,key,run_id,build_id)


def _vercel_executable():
    from .web_setup import locate_vercel_cli
    try:return locate_vercel_cli()
    except OSError as error:raise ValueError('Run initial publication setup once; no dependency download during a prospect run') from error


def _publish_once(run_dir,directory,policy):
    """Private operation ledger, called only after the run's acceptance gate."""
    run=state.load_run(run_dir);root=Path(run['root']);policy=validate_policy(policy)
    current,manifest,_=web.current_build(run)
    if current!=Path(directory) or policy['owner']!=run['profile']['responsible']:
        raise ValueError('Publication build or responsible owner differs from the current run')
    adapter=VercelPreviewAdapter(policy);adapter.project()
    key=hashlib.sha256(web._canonical([run['id'],policy['org_id'],policy['project_id'],manifest['build_id']])).hexdigest()
    path=state._safe_path(root,'web/publication/'+key+'.json',exists=False)
    existing=adapter.lookup(key,run['id'],manifest['build_id'])
    with run_lock(root):
        prior=json.loads(path.read_text()) if path.exists() else None
        if existing:
            receipt=existing
        elif prior:
            receipt=dict(prior,status='UNKNOWN_OUTCOME' if prior['status'] in ('STARTED','UNKNOWN_OUTCOME') else prior['status'])
        else:
            from .web_timing import require_time
            require_time(run)
            receipt={'status':'STARTED','operation_key':key,'run_id':run['id'],'build_id':manifest['build_id'],
                'project_id':policy['project_id'],'org_id':policy['org_id'],'target':'preview',
                'policy_sha256':hashlib.sha256(web._canonical(policy)).hexdigest(),
                'authority':'workspace_publication_policy','started_at':datetime.now(timezone.utc).isoformat()}
        write_json(path,receipt)
    if existing or prior:
        return receipt
    # Exactly one caller creates. A crash after STARTED can only reconcile.
    try:
        outcome=adapter.deploy(directory,key,run['id'],manifest['build_id'])
    except (OSError,subprocess.TimeoutExpired):
        outcome=adapter.lookup(key,run['id'],manifest['build_id']) or dict(receipt,status='UNKNOWN_OUTCOME')
    except BaseException:
        with run_lock(root):
            write_json(path,dict(receipt,status='UNKNOWN_OUTCOME'))
        raise
    with run_lock(root):
        write_json(path,outcome)
    return outcome


def preflight_run(run_dir,policy_path=None):
    """Read current hosting authority in the executing task; never provision it."""
    run=state.load_run(run_dir)
    if state.delivery_format(run)!='web':raise ValueError('Publication preflight requires a web run')
    configured=run['profile']['parameters'].get('publication_policy')
    if not policy_path and not configured:raise ValueError('Publication was not prepared at installation')
    path=Path(policy_path or configured)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('A bounded private workspace publication policy is required')
    policy=validate_policy(json.loads(path.read_text()))
    if policy['owner']!=run['profile'].get('responsible') or not run['profile'].get('responsible_confirmed'):
        raise ValueError('Publication policy does not belong to this workspace owner')
    _vercel_executable()
    _token(policy)
    VercelPreviewAdapter(policy).project()
    return {'status':'READY','scope':'current_publication_prerequisites_only',
            'checked_at':datetime.now(timezone.utc).isoformat(),'provider_writes':0,
            'project_id':policy['project_id'],'target':'preview','client_quality':'NOT_RUN'}


def _publication_ready(run_dir,policy):
    run=state.load_run(run_dir)
    if state.delivery_format(run)!='web' or policy['owner']!=run['profile'].get('responsible'):
        raise ValueError('Publication policy does not belong to this web run')
    directory,manifest,plan=web.current_build(run)
    inspection=web.current_inspection(run)
    if inspection['status']!='PASS' or set(inspection['request']['browsers'])!={'chromium','webkit'}:
        raise ValueError('Both browser engines must pass on the exact build')
    if not {(1440,900),(1280,600),(390,844)}.issubset({tuple(v) for v in inspection['request']['viewports']}):
        raise ValueError('Required desktop, short viewport and mobile inspection coverage is missing')
    if any(item['rights']=='restricted' for item in plan['media']):
        raise ValueError('A restricted medium needs an explicit diffusion decision before publication')
    quality=state.validate_run(run_dir)
    if quality['status']!='PASS':
        raise ValueError('The current run has not passed its canonical requirements and independent client reviews')
    return run,directory,manifest


def publish_run(run_dir,policy_path):
    path=Path(policy_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('A bounded private workspace publication policy is required')
    policy=validate_policy(json.loads(path.read_text()))
    run,directory,manifest=_publication_ready(run_dir,policy)
    result=_publish_once(run_dir,directory,policy)
    # Rechecking cannot undo a deployment, but prevents stale delivery claims.
    if web.current_build(state.load_run(run_dir))[1]['build_id']!=manifest['build_id']:
        raise ValueError('Build changed during publication; keep deployment receipt for reconciliation')
    return result


def verify_run(run_dir,policy_path):
    path=Path(policy_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('A bounded private workspace publication policy is required')
    policy=validate_policy(json.loads(path.read_text()))
    run,directory,manifest=_publication_ready(run_dir,policy)
    adapter=VercelPreviewAdapter(policy);adapter.project()
    key=hashlib.sha256(web._canonical([run['id'],policy['org_id'],policy['project_id'],manifest['build_id']])).hexdigest()
    ledger=state._safe_path(Path(run['root']),'web/publication/'+key+'.json',exists=False)
    if not ledger.is_file():
        raise ValueError('No deployment checkpoint exists; verify never creates a deployment')
    deployment=adapter.lookup(key,run['id'],manifest['build_id'])
    if not deployment or deployment['status']!='DEPLOYED' or not deployment.get('url'):
        raise ValueError('The deployment is not confirmed ready; preserve its existing checkpoint')
    write_json(ledger,deployment)
    byte_proof=verify_bytes(directory,deployment['url'])
    from .web_timing import require_time,budget,utc_now
    if run['artifacts'].get('web-verification',{}).get('status')=='CURRENT':
        previous=_stored_verification(run,policy=policy,url=deployment['url'])
        if previous['status']=='PASS':
            return dict(previous,reused_browser_evidence=True,byte_proof=byte_proof,
                readback_observed_at=utc_now().isoformat())
    require_time(run)
    output=Path(tempfile.mkdtemp(prefix='public-browser-',dir=ledger.parent))
    # The browser inspector owns a new destination and fresh anonymous contexts.
    output.rmdir()
    _,_,plan=web.current_build(state.load_run(run_dir))
    browser_proof=web.inspect_bundle(directory,plan,output,origin=deployment['url'])
    browser_proof.update(runtime=web._inspection_runtime(),run_id=run['id'])
    (output/'report.json').write_bytes(web._canonical(browser_proof))
    web._check_inspection(Path(run['root']),output/'report.json',manifest['build_id'])
    _publication_ready(run_dir,policy)
    verified_at=utc_now()
    result={'status':'PASS' if browser_proof['status']=='PASS' else 'BLOCKED',
        'scope':'anonymous_public_bytes_and_browser_mechanics_only','url':deployment['url'],
        'build_id':manifest['build_id'],'run_id':run['id'],'creative_quality':'SEPARATE_CANONICAL_REVIEWS',
        'authority':'workspace_publication_policy','authentication_used':False,
        'observed_at':verified_at.isoformat(),'timing':budget(run,now=verified_at),
        'policy_path':str(path.resolve()),'policy_sha256':hashlib.sha256(web._canonical(policy)).hexdigest(),
        'byte_proof':byte_proof,'browser_report':{'path':str((output/'report.json').relative_to(Path(run['root']))),
            'sha256':web._sha(output/'report.json')},'issues':browser_proof['issues']}
    result['delivery_status']='PASS' if result['status']=='PASS' and result['timing']['target_status']=='PASS' else 'FAIL_TIMING' if result['status']=='PASS' else 'BLOCKED'
    if result['status']=='PASS':result['first_verified_at']=verified_at.isoformat()
    result_path=output/'verification.json'
    result_path.write_bytes(web._canonical(result))
    current=state.load_run(run_dir)
    for identifier,file,deps in [
        ('web-deployment',ledger,['artifact:web-build','artifact:web-inspection']),
        ('web-public-browser',output/'report.json',['artifact:web-deployment']),
        ('web-verification',result_path,['artifact:web-deployment','artifact:web-public-browser'])]:
        row=state._artifact_record(current,identifier,file,'internal',deps,reuse_current=True)
        row['metadata']={'scope':'publication'};current['artifacts'][identifier]=row
    state.save_run(run_dir,current)
    return result


def _stored_verification(run,*,policy=None,url=None):
    """Reuse exact immutable browser evidence, never an invented new delivery time."""
    from .composition import _current
    from .web_timing import budget
    _,file=_current(run,'artifact:web-verification');result=json.loads(file.read_text())
    if policy is None:
        path=state._no_symlinks(Path(result['policy_path']))
        if not path.is_file() or path.stat().st_size>65536:raise ValueError('Verified publication policy is unavailable')
        policy=validate_policy(json.loads(path.read_text()))
    if (result.get('status') not in ('PASS','BLOCKED') or result.get('run_id')!=run['id']
            or result.get('authority')!='workspace_publication_policy' or result.get('authentication_used') is not False
            or result.get('policy_sha256')!=hashlib.sha256(web._canonical(policy)).hexdigest()
            or result.get('url')!=_deployment_url(url or result['url'])
            or result.get('build_id')!=web.current_build(run)[1]['build_id']):
        raise ValueError('Stored web verification does not identify this current delivery')
    row,report_path=_current(run,'artifact:web-public-browser')
    if (result['browser_report']!={'path':report_path.relative_to(Path(run['root'])).as_posix(),'sha256':row['sha256']}):
        raise ValueError('Delivery points to a different browser proof')
    report=web._check_inspection(Path(run['root']),report_path,result['build_id'])
    if (report['status']!=result['status'] or report.get('origin')!=result['url']
            or report.get('authentication')!='none_fresh_browser_contexts'
            or (result['status']=='PASS' and {r['engine'] for r in report['browsers']}!={'chromium','webkit'})):
        raise ValueError('Delivery has no complete anonymous browser inspection')
    _,ledger=_current(run,'artifact:web-deployment');deployment=json.loads(ledger.read_text())
    if (deployment.get('url')!=result['url'] or deployment.get('build_id')!=result['build_id']
            or deployment.get('project_id')!=policy['project_id'] or deployment.get('target')!='preview'):
        raise ValueError('Delivery no longer identifies the accepted preview deployment')
    observed=result.get('observed_at',result.get('first_verified_at'))
    timing=budget(run,now=datetime.fromisoformat(observed))
    expected='BLOCKED' if result['status']=='BLOCKED' else 'PASS' if timing['target_status']=='PASS' else 'FAIL_TIMING'
    if (timing!=result['timing'] or result['delivery_status']!=expected
            or (result['status']=='PASS' and result['first_verified_at']!=observed)
            or (result['status']=='BLOCKED' and 'first_verified_at' in result)):
        raise ValueError('The complete first-delivery clock changed')
    return result


def verified_delivery(run,*,policy=None,url=None):
    result=_stored_verification(run,policy=policy,url=url)
    if result['status']!='PASS':raise ValueError('Public browser verification has not passed')
    return result


def publication_report(run):
    """Local readback of stored evidence; never a new live provider assertion."""
    if 'web-verification' not in run['artifacts']:
        return {'status':'NOT_RUN','execution':'NOT_VERIFIED','scope':'stored_exact_web_delivery_evidence','issues':[]}
    try:
        result=verified_delivery(run)
        return {'status':result['delivery_status'],'execution':'VERIFIED_PUBLIC',
            'scope':'stored_exact_web_delivery_evidence_not_fresh_network_readback',
            'url':result['url'],'build_id':result['build_id'],'verified_at':result['first_verified_at'],
            'timing':result['timing'],'issues':[]}
    except (ValueError,OSError,KeyError,TypeError) as error:
        return {'status':'BLOCKED','execution':'NOT_VERIFIED','scope':'stored_exact_web_delivery_evidence',
            'issues':[{'code':'web_verification','message':str(error)}]}


def _anonymous_open(request,**kwargs):
    return build_opener(_NoRedirect).open(request,**kwargs)


def verify_bytes(directory,origin):
    origin=_deployment_url(origin);manifest=web.verify_bundle(directory)
    files=[r for r in manifest['files'] if r['path'].startswith('.vercel/output/static/')]
    marker=web._canonical({'version':1,'build_id':manifest['build_id']})
    files.append({'path':'.vercel/output/static/vertigo-build.json',
                  'sha256':hashlib.sha256(marker).hexdigest(),'size_bytes':len(marker)})
    root=next(row for row in files if row['path']=='.vercel/output/static/index.html')
    files.insert(0,dict(root,url_path=''))
    verified=[];started=time.monotonic()
    for row in files:
        name=row.get('url_path',row['path'].removeprefix('.vercel/output/static/'))
        remaining=45-(time.monotonic()-started)
        if remaining<=0:
            raise ValueError('Anonymous verification deadline exceeded; preserve publication checkpoint')
        request=Request(origin+'/'+quote(name,safe='/'))
        digest=hashlib.sha256();count=0
        try:
            with _anonymous_open(request,timeout=min(10,remaining)) as response:
                if response.status!=200:
                    raise ValueError('The deployment is not anonymously accessible')
                while chunk:=response.read(65536):
                    count+=len(chunk)
                    if count>row['size_bytes']:
                        raise ValueError('Public resource exceeds its frozen bytes')
                    digest.update(chunk)
        except (HTTPError,URLError,TimeoutError) as error:
            raise ValueError('Anonymous readback failed or redirected to authentication') from error
        if count!=row['size_bytes'] or digest.hexdigest()!=row['sha256']:
            raise ValueError('Public deployment differs from the accepted build')
        verified.append({'path':name or '/','sha256':row['sha256'],'size_bytes':count})
    web.verify_bundle(directory)
    return {'status':'PASS','scope':'anonymous_public_bytes_only','build_id':manifest['build_id'],
            'url':origin,'files':verified,'authentication_used':False,'creative_quality':'NOT_ASSESSED'}
