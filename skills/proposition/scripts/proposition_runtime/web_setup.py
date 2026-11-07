"""Explicit installation-only support. Ordinary runs never create projects."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.error import HTTPError,URLError
from urllib.parse import quote,urlencode,urlsplit
from urllib.request import Request,build_opener
from uuid import uuid4

from . import state,web,web_publication as publication
from .publication import write_json
from .transactions import run_lock,read_json


class RequestRejected(OSError):
    """An explicit provider rejection, distinct from a lost write response."""
    def __init__(self,status,code):
        super().__init__('Vercel rejected the installation request (HTTP '+str(status)+', '+code+')')
        self.status=status;self.provider_code=code


class BootstrapRejected(OSError):
    pass


class BootstrapUnconfirmed(OSError):
    def __init__(self,details):
        super().__init__('Initial deployment outcome is unconfirmed; inspect its private diagnostic')
        self.details=details


def _toolchain():
    source=Path(__file__).parents[2]/'resources/toolchain/vercel'
    lock=source/'package-lock.json'
    version=json.loads((source/'package.json').read_text())['dependencies']['vercel']
    cache=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'vertigo-proposition/tools'/('vercel-'+web._sha(lock)[:20])
    return source,state._external_root(cache),version


def locate_vercel_cli():
    source,cache,version=_toolchain()
    receipt=read_json(cache/'CLI-CHECK.json')
    package=read_json(cache/'node_modules/vercel/package.json')
    executable=state._safe_path(cache,'node_modules/vercel/'+package['bin']['vercel'])
    if (receipt.get('source_lock_sha256')!=web._sha(source/'package-lock.json')
            or package.get('version')!=version or receipt.get('cli_version')!=version
            or receipt.get('executable_sha256')!=web._sha(executable)
            or not os.access(executable,os.X_OK)):
        raise ValueError('Pinned Vercel toolchain changed; do not use an unverified global CLI')
    return str(executable)


def ensure_vercel_cli():
    """Download locked dependencies once, outside the source or any run."""
    source,cache,version=_toolchain()
    if cache.exists():return locate_vercel_cli()
    npm=shutil.which('npm')
    if not npm or not shutil.which('node'):raise ValueError('Initial publication setup requires Node and npm')
    cache.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.vercel-tools-',dir=cache.parent) as folder:
        staging=Path(folder)/'package';staging.mkdir()
        for name in ('package.json','package-lock.json'):shutil.copyfile(source/name,staging/name)
        result=subprocess.run([npm,'ci','--prefix',str(staging),'--ignore-scripts','--no-audit','--no-fund'],
            capture_output=True,text=True,timeout=180)
        if result.returncode:raise ValueError('Pinned Vercel dependency installation failed; no provider write attempted')
        package=read_json(staging/'node_modules/vercel/package.json')
        executable=state._safe_path(staging,'node_modules/vercel/'+package['bin']['vercel'])
        checked=subprocess.run([str(executable),'--version'],capture_output=True,text=True,timeout=15)
        if checked.returncode or not re.search(r'(?<![0-9.])'+re.escape(version)+r'(?![0-9.])',checked.stdout+checked.stderr):
            raise ValueError('The installed pinned Vercel CLI did not verify its actual version')
        write_json(staging/'CLI-CHECK.json',{'source_lock_sha256':web._sha(source/'package-lock.json'),
            'cli_version':version,'executable_sha256':web._sha(executable),'scope':'installation_only_not_deployment'})
        try:os.rename(staging,cache)
        except FileExistsError:pass
    return locate_vercel_cli()


def current_organization():
    path=publication._auth_directory()/'config.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:
        raise ValueError('Log into the Vercel CLI and select an account once during installation')
    value=json.loads(path.read_text()).get('currentTeam')
    if not isinstance(value,str) or not re.fullmatch(r'team_[A-Za-z0-9_-]+',value):
        raise ValueError('The Vercel CLI has no selected organization; configure it at installation')
    return value


def _setup_request(path,policy,*,body=None):
    if not (path.startswith('/v9/projects/') or path.startswith('/v6/deployments?')
            or path.startswith('/v13/deployments/') or (body is not None and path.startswith('/v11/projects?'))):
        raise ValueError('Unsupported installation request')
    data=web._canonical(body) if body is not None else None
    request=Request('https://api.vercel.com'+path,data=data,
        headers={'Authorization':'Bearer '+publication._token(policy),'Content-Type':'application/json'})
    try:
        with build_opener(publication._NoRedirect).open(request,timeout=15) as response:
            payload=response.read(4*1024*1024+1)
        if len(payload)>4*1024*1024:raise ValueError('Installation response exceeds its budget')
        return json.loads(payload)
    except HTTPError as error:
        if error.code==404 and body is None:return None
        if body is not None and error.code in (400,401,402,403,404,422):
            try:
                code=json.loads(error.read(16384)).get('error',{}).get('code','rejected')
                if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',code):code='rejected'
            except (ValueError,AttributeError):code='rejected'
            raise RequestRejected(error.code,code) from error
        raise OSError('Vercel installation request failed; reconcile before any write retry') from error
    except (URLError,TimeoutError) as error:
        raise OSError('Vercel installation outcome is unconfirmed') from error


def _bootstrap_bundle(root,nonce):
    source=root/'source';source.mkdir()
    (source/'index.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow"><title>VERTIGO — propositions</title>'
        '<main><h1>VERTIGO</h1><p>Espace de publication des propositions.</p>'
        '<p>Aucune proposition client sur cette page.</p></main></html>')
    (source/'sources.html').write_text('<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<title>Initialisation</title><p>Page technique VERTIGO. Aucun média prospect.</p>'
        '<p>Installation '+nonce+'</p></html>')
    directory=root/'bundle'
    web.build_bundle(source,directory,{'version':1,'entrypoint':'index.html',
        'sources_page':'sources.html','public_files':['index.html','sources.html']})
    return directory


class InstallationAdapter:
    def __init__(self,org,credential_ref):
        self.policy={'org_id':org,'credential_ref':credential_ref}
        publication._token(self.policy)
        locate_vercel_cli()

    def lookup_project(self,name):
        return _setup_request('/v9/projects/'+quote(name,safe='')+'?'+urlencode({'teamId':self.policy['org_id']}),self.policy)

    def read_project(self,identifier):return self.lookup_project(identifier)

    def create_project(self,name):
        # No update endpoint exists here: no settings of an existing site can
        # be changed. The random reserved name is checked absent before POST.
        return _setup_request('/v11/projects?'+urlencode({'teamId':self.policy['org_id']}),self.policy,
            body={'name':name,'framework':None,'ssoProtection':None,
                  'enablePreviewFeedback':False,'enableProductionFeedback':False})

    def find_bootstrap(self,project,nonce):
        query={'teamId':self.policy['org_id'],'projectId':project['id'],'limit':100,'meta-vertigo_setup':nonce}
        result=_setup_request('/v6/deployments?'+urlencode(query),self.policy)
        rows=[row for row in result.get('deployments',[]) if (row.get('meta') or {}).get('vertigo_setup')==nonce]
        if len(rows)>1:raise ValueError('Multiple initial deployments require reconciliation')
        return rows[0] if rows else None

    def bootstrap(self,project,nonce):
        if (not re.fullmatch(r'[0-9a-f]{32}',nonce)
                or project.get('name')!='vertigo-propositions-'+nonce
                or project.get('accountId')!=self.policy['org_id']
                or (project.get('targets') or {}).get('production')):
            raise ValueError('Initialization is limited to the newly reserved empty project')
        with tempfile.TemporaryDirectory(prefix='vertigo-hosting-setup-') as folder, publication._cli_credentials(self.policy) as auth:
            directory=_bootstrap_bundle(Path(folder),nonce)
            (directory/'.vercel/project.json').write_bytes(web._canonical({'projectId':project['id'],'orgId':self.policy['org_id']}))
            # Vercel requires the first deployment to be production. This contains
            # only the installation page in the newly created isolated project.
            # It cannot receive a prospect path or an existing project argument.
            command=[locate_vercel_cli(),'deploy','--prebuilt','--environment','production','--json','--yes','--no-color',
                '--cwd',str(directory),'--scope',self.policy['org_id'],'--meta','vertigo_setup='+nonce,*auth]
            environment=dict(os.environ,VERCEL_ORG_ID=self.policy['org_id'],VERCEL_PROJECT_ID=project['id'],
                VERCEL_TELEMETRY_DISABLED='1',CI='1')
            result=subprocess.run(command,env=environment,capture_output=True,text=True,timeout=120)
            if result.returncode:
                if 'Vercel CLI version is outdated' in result.stderr:
                    raise BootstrapRejected('Provider rejected this CLI version before deployment creation')
                diagnostic=(result.stdout+'\n'+result.stderr)[-6000:]
                diagnostic=diagnostic.replace(publication._token(self.policy),'[REDACTED]')
                raise BootstrapUnconfirmed({'returncode':result.returncode,'diagnostic':diagnostic})
            url=publication.deployment_stdout(result.stdout)
            return _setup_request('/v13/deployments/'+quote(urlsplit(url).hostname,safe='')+'?'+urlencode({'teamId':self.policy['org_id']}),self.policy)

    def verify_public(self,record,nonce):
        with tempfile.TemporaryDirectory(prefix='vertigo-hosting-check-') as folder:
            directory=_bootstrap_bundle(Path(folder),nonce)
            proof=publication.verify_bytes(directory,publication._deployment_url(record['url']))
            return {'status':'PASS','authentication_used':False,'byte_proof':proof}


def _project(record,receipt):
    if (not isinstance(record,dict) or record.get('name')!=receipt['project_name']
            or record.get('accountId')!=receipt['org_id'] or not record.get('id')
            or (receipt.get('project_id') and record['id']!=receipt['project_id'])):
        raise ValueError('The installation project or organization differs from its reserved identity')
    if record.get('ssoProtection') or record.get('passwordProtection'):
        raise ValueError('New hosting support is protected; keep the checkpoint, never modify an existing site')
    return record


def _deployment(record,receipt):
    if (not record or record.get('projectId')!=receipt['project_id']
            or (record.get('meta') or {}).get('vertigo_setup')!=receipt['nonce']
            or record.get('readyState',record.get('state'))!='READY'):
        raise ValueError('The initialization deployment is not confirmed ready for this installation')
    return publication._deployment_url(record['url'])


def configure_publication(workspace,owner,org_id=None,*,credential_ref='vercel_cli',adapter=None):
    """Explicit initial authority, private policy, zero prospect content."""
    root=state._external_root(workspace)
    if not root.is_dir() or not isinstance(owner,str) or not owner.strip():
        raise ValueError('Publication installation requires an existing workspace and its explicit owner')
    org=org_id or current_organization()
    publication.validate_policy({'version':1,'authority':'workspace_publication_policy','owner':owner,
        'org_id':org,'project_id':'pending','target':'preview','credential_ref':credential_ref})
    private=state._safe_path(root,'.vertigo',exists=False);private.mkdir(exist_ok=True)
    path=state._safe_path(root,'.vertigo/publication-setup.json',exists=False)
    profile_path=state._safe_path(root,'.vertigo/profile.json',exists=False)
    policy_path=state._safe_path(root,'.vertigo/publication-policy.json',exists=False)
    profile=read_json(profile_path) if profile_path.exists() else {}
    if profile.get('responsible') and profile['responsible']!=owner:
        raise ValueError('Workspace publication owner differs from its configured responsible person')
    if adapter is None:ensure_vercel_cli()
    provider=adapter or InstallationAdapter(org,credential_ref)
    with run_lock(private):
        if path.exists():
            receipt=read_json(path)
            if any(receipt.get(k)!=v for k,v in {'workspace':str(root),'owner':owner,'org_id':org,'credential_ref':credential_ref}.items()):
                raise ValueError('Existing publication setup belongs to a different workspace authority')
        else:
            nonce=uuid4().hex
            receipt={'version':1,'workspace':str(root),'owner':owner,'org_id':org,'credential_ref':credential_ref,
                'nonce':nonce,'project_name':'vertigo-propositions-'+nonce,'phase':'RESERVED',
                'authority':'explicit_installation_only','prospect_publication':'NOT_RUN'}
            write_json(path,receipt)
    if receipt['phase']=='READY':
        _project(provider.read_project(receipt['project_id']),receipt)
        return receipt
    project=provider.lookup_project(receipt['project_name'])
    if receipt['phase'] in ('RESERVED','CREATE_REJECTED'):
        if project is not None:raise ValueError('Reserved project name already exists; do not adopt or modify it')
        with run_lock(private):
            current=read_json(path)
            if current['phase'] not in ('RESERVED','CREATE_REJECTED'):return dict(current,status='UNKNOWN_OUTCOME')
            receipt.update(phase='CREATE_STARTED');write_json(path,receipt)
        try:project=provider.create_project(receipt['project_name'])
        except RequestRejected as error:
            receipt.update(phase='CREATE_REJECTED',last_error={'http_status':error.status,'provider_code':error.provider_code})
            with run_lock(private):write_json(path,receipt)
            return dict(receipt,status='BLOCKED')
        except (OSError,subprocess.SubprocessError):return dict(receipt,status='UNKNOWN_OUTCOME')
    if project is None:return dict(receipt,status='UNKNOWN_OUTCOME')
    project=_project(project,receipt)
    with run_lock(private):
        current=read_json(path)
        receipt=current
        if receipt['phase']=='CREATE_STARTED':
            receipt.update(project_id=project['id'],phase='CREATED');write_json(path,receipt)
    record=provider.find_bootstrap(project,receipt['nonce'])
    if record is None and receipt['phase']=='CREATED':
        with run_lock(private):
            current=read_json(path)
            if current['phase']!='CREATED':return dict(current,status='UNKNOWN_OUTCOME')
            receipt.update(phase='BOOTSTRAP_STARTED');write_json(path,receipt)
        try:record=provider.bootstrap(project,receipt['nonce'])
        except BootstrapRejected:
            receipt.update(phase='CREATED',last_error={'code':'cli_version_rejected'})
            with run_lock(private):write_json(path,receipt)
            return dict(receipt,status='BLOCKED')
        except BootstrapUnconfirmed as error:
            receipt.update(last_error=error.details)
            with run_lock(private):write_json(path,receipt)
            return dict(receipt,status='UNKNOWN_OUTCOME')
        except (OSError,subprocess.SubprocessError):return dict(receipt,status='UNKNOWN_OUTCOME')
    if record is None:return dict(receipt,status='UNKNOWN_OUTCOME')
    url=_deployment(record,receipt)
    project=_project(provider.read_project(project['id']),receipt)
    if (project.get('targets') or {}).get('production',{}).get('id')!=record.get('id',record.get('uid')):
        raise ValueError('The new project does not identify this exact initialization deployment')
    proof=provider.verify_public(record,receipt['nonce'])
    if proof.get('status')!='PASS' or proof.get('authentication_used') is not False:
        raise ValueError('Initial hosting URL has not passed anonymous byte verification')
    policy=publication.validate_policy({'version':1,'authority':'workspace_publication_policy','owner':owner,
        'project_id':project['id'],'org_id':org,'target':'preview','credential_ref':credential_ref})
    with run_lock(private):
        write_json(policy_path,policy)
        profile=read_json(profile_path) if profile_path.exists() else {}
        profile.update(responsible=owner,responsible_confirmed=True)
        profile.setdefault('actor',owner)
        profile.setdefault('parameters',{}).update(publication_policy=str(policy_path))
        write_json(profile_path,profile)
        receipt.update(status='READY',phase='READY',initialization_url=url,public_readback=proof,
            policy_path=str(policy_path),per_run_target='preview')
        write_json(path,receipt)
    return receipt
