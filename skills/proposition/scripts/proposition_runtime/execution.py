"""Optional local task protocol. Never launches a model, browser or provider."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import os
import re
import stat
from uuid import uuid4
from . import state,transactions,upstream
from .validation import phase,commit_guard,invalidate

ACTIVE={'CLAIMED','DISPATCHING','RUNNING','SUCCEEDED','UNKNOWN_OUTCOME'}
FINGERPRINT_FIELDS=('run_id','task_key','stage_id','scope','input_parameters','input_hashes','profile_hash','contract_hashes','packet_plan','output_destinations')


def _now():return datetime.now(timezone.utc)
def _utc(value):return value.isoformat().replace('+00:00','Z')
def _time(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Execution date requires a timezone')
    return parsed

def _relative(value):
    if not isinstance(value,str) or not value or '\\' in value or ':' in value or any(p in ('','.','..') for p in value.split('/')) or value.startswith('/'):
        raise ValueError('Execution path must be portable and run-relative')
    return value

def _specs():
    data=transactions.read_json(state.DATA_ROOT/'task-specs.json');state._schema('task-specs',data)
    return data['tasks']

def _parameters(run,spec):
    config=transactions.execution_metadata(run)['config']
    result={'attempt_limit':2,'budget_seconds':600,'stop':'Retain candidates and report limits; no blind retry after dispatch','max_host_tasks':config['max_host_tasks']}
    if spec['task_key']=='discovery.site.collect':
        result.update(url=run['url'],max_pages=10,concurrency=config['concurrency'],panel_scan=config['panel_scan'],image_wait_policy=config['image_wait_policy'],proof_storage=config['proof_storage'],allow_local_fixture=False,frontier_descriptor=None)
    if spec.get('topic'):result['topic']=spec['topic']
    if spec.get('mission_id'):result['mission_id']=spec['mission_id']
    return result

def _variants(run):
    result=[]
    from .public_research import TOPICS
    for original in _specs():
        if original['task_key']=='research.topic':
            for topic in TOPICS:
                spec=deepcopy(original);spec.update(task_key='research.topic.'+topic,topic=topic,completed_by=['research-topic-'+topic]);spec['outputs']['report']['name']=topic+'.json';result.append(spec)
        elif original['task_key']=='research.reconcile':
            spec=deepcopy(original);spec['inputs']+=['research-topic-'+topic for topic in TOPICS];result.append(spec)
        elif original['task_key'] in ('strategy.mission','strategy.reconcile'):
            row=run['artifacts'].get('strategy-draft')
            if not row or row['status']!='CURRENT':result.append(original);continue
            from . import strategy
            path=state._safe_path(Path(run['root']),row['path']);draft=transactions.read_json(path);strategy.validate_draft(run,draft)
            if original['task_key']=='strategy.mission':
                for mission in draft['proposed_missions']:
                    spec=deepcopy(original);spec.update(task_key='strategy.mission.'+mission['id'],mission_id=mission['id'],completed_by=['strategy-mission-'+mission['id']]);spec['inputs']+=['strategy-mission-'+i for i in mission['depends_on']];spec['outputs']['report']['name']='mission-'+mission['id']+'.json';result.append(spec)
            else:
                spec=deepcopy(original);spec['inputs']+=['strategy-mission-'+m['id'] for m in draft['proposed_missions']];result.append(spec)
        elif original['task_key'] in ('export.documents.consolidate','verify.final.inspect'):
            from .composition import CLIENT_INPUTS,DERIVATIVES
            spec=deepcopy(original)
            required={ref.split(':',1)[1] for ref in CLIENT_INPUTS}
            if state.delivery_scope(run)!='client': required |= DERIVATIVES-{'client-context'}
            if original['task_key']=='verify.final.inspect':required |= {'client-context','export-consolidation'}
            spec['inputs']=list(dict.fromkeys(spec['inputs']+sorted(required)));result.append(spec)
        elif original['task_key'].startswith('review.client.'):

            spec=deepcopy(original);index=0 if original['task_key'].endswith('review_a') else 1;reviewers=run['profile']['required_reviewers']
            spec['reviewer_id']=reviewers[index];result.append(spec)
        else:result.append(original)
    for stage_id in state._quality_stages(run):
        producers=[s for s in result if s['stage_id']==stage_id]
        completed=list(dict.fromkeys(i for s in producers for i in s['completed_by']))
        required=list(dict.fromkeys(completed+[i for s in producers for i in s['inputs']]))
        if stage_id in ('client.composition','review.client'):
            from .composition import CLIENT_INPUTS
            required=list(dict.fromkeys(required+[ref.split(':',1)[1] for ref in CLIENT_INPUTS]))
        if not completed or not all(run['artifacts'].get(i,{}).get('status')=='CURRENT' for i in completed):continue
        result.append({'task_key':'stage-review.'+stage_id,'stage_id':stage_id,'inputs':required,'completed_by':['stage-review-receipt-'+stage_id,'stage-review-report-'+stage_id],'methods':[],'capabilities':['host.fresh_context'],'packet':'review_inputs','isolation':'independent_review','audiences':['public','client','sales','technical','internal'],'outputs':{'receipt':{'name':'independence.json','kind':'file','audience':'internal'},'report':{'name':'review.json','kind':'file','audience':'internal'}},'skill':'proposition-quality'})
    return result

def _completed(run,spec):
    if spec['task_key'].startswith('stage-review.'):
        row=run['stage_reviews'].get(spec['stage_id'])
        return bool(row and row['status']!='STALE')
    if spec['task_key'].startswith('review.client.'):
        row=run['reviews'].get(spec['reviewer_id'])
        return bool(row and row['status']!='STALE')
    required={'artifact:'+i for i in spec['inputs']}
    return bool(spec['completed_by']) and all(run['artifacts'].get(i,{}).get('status')=='CURRENT' and required.issubset(set(state._dependency_closure(run,['artifact:'+i]))) for i in spec['completed_by'])

def _destinations(run,spec,seed):
    result={role:'outputs/tasks/'+seed+'/'+details['name'] for role,details in spec['outputs'].items()}
    if spec['task_key']=='discovery.site.collect':return {'discovery-report':'research/capture-'+seed+'/discovery.json','discovery-material':'research/capture-'+seed+'/sources'}
    if spec['task_key'].startswith('client.composition.'):
        from .composition import OUTPUTS
        if spec['task_key']=='client.composition.plan':
            result.update({key:'outputs/client/'+seed+'/'+key+suffix for key,suffix in OUTPUTS.items()})
        else:
            row=run['artifacts'].get('client-story-map')
            if not row or row['status']!='CURRENT':raise ValueError('Composition requires its current plan and reserved destinations')
            path=state._safe_path(Path(run['root']),row['path']);plan=transactions.read_json(path)
            if set(plan['outputs'])!=set(OUTPUTS):raise ValueError('Composition plan must preserve all four destinations')
            for key,value in plan['outputs'].items():
                _relative(value)
                if Path(value).suffix!=OUTPUTS[key]:raise ValueError('Reserved client destination has the wrong type')
            result.update(plan['outputs'])
    return result

def _creator_context(run,spec):
    if spec['isolation']!='continue_public':return None
    current=run['artifacts'].get('creative-inputs')
    if not current:raise ValueError('Creator continuation needs current public inputs')
    contexts=set()
    for attempt in transactions.execution_metadata(run)['attempts'].values():
        if attempt['state']!='COMMITTED':continue
        request=_request(run['root'],attempt)
        if request['task_key']!='creative.direction.prepare' or request['input_hashes'].get('artifact:creative-inputs')!=state._record_digest(current):continue
        contexts.update(_attempt_contexts(run['root'],attempt))
    if len(contexts)!=1:raise ValueError('Continue the one evidenced original creator; no replacement context may be invented')
    if spec['task_key']=='creative.direction.explore':
        from .experience import _inputs,_method_reading
        inputs,row=_inputs(run)
        if _method_reading(run,inputs,row) is None:raise ValueError('Creative reading must precede exploration')
    return next(iter(contexts))

def _live(attempt,now):
    return attempt['state'] in ACTIVE and not (attempt['state']=='CLAIMED' and attempt['dispatch_key'] is None and _time(attempt['claim_expires_at'])<now)

def _request_path(root,attempt):return Path(root)/'.execution/inputs'/attempt/'request.json'

def _request(root,attempt):
    path=_request_path(root,attempt['attempt_id']);data=transactions.read_json(path);state._schema('task-request',data)
    if data['kind']!='request' or data['request_hash']!=attempt['request_hash'] or state._digest({k:v for k,v in data.items() if k!='request_hash'})!=data['request_hash']:
        raise transactions.Conflict('CONFLICT: immutable task request changed')
    return data

def _inputs(run,refs):
    closure=state._dependency_closure(run,refs);result={}
    for ref in sorted(closure):
        record=state._resolve(run,ref)
        if not record or record.get('status')=='STALE':raise ValueError('Missing current task input '+ref)
        result[ref]=state._record_digest(record)
    return result

def _check_inputs(run,request):
    if run['id']!=request['run_id'] or state._digest(run['profile'])!=request['profile_hash']:raise transactions.Conflict('CONFLICT: task run/profile changed')
    for ref,digest in request['input_hashes'].items():
        record=state._resolve(run,ref)
        if not record or record.get('status')=='STALE' or state._record_digest(record)!=digest:raise transactions.Conflict('CONFLICT: task input changed '+ref)

def _descriptor(root,path,role,audience):
    return {'path':path.relative_to(root).as_posix(),'sha256':state._sha(path),'size_bytes':path.stat().st_size,'role':role,'audience':audience}

def _file(root,descriptor):
    path=state._safe_path(Path(root),_relative(descriptor['path']))
    if path.stat().st_size!=descriptor['size_bytes'] or state._sha(path)!=descriptor['sha256']:raise transactions.Conflict('CONFLICT: execution proof changed')
    return path

def _method_files(families):
    if not families:return {},[]
    cache=upstream._cache_root(None);files={};roots=[]
    for identifier in families:
        spec=next(s for s in upstream._families() if s['id']==identifier)
        if not upstream._inspect(spec,cache)['complete']:raise ValueError('Pinned method unavailable: upstream fetch --family '+identifier)
        source=cache/identifier/spec['commit'];roots.append((spec,source))
        for path in sorted(source.rglob('*')):
            state._no_symlinks(path)
            if path.is_file():files['upstreams/'+identifier+'/'+spec['commit']+'/'+path.relative_to(source).as_posix()]=path
    return files,roots

def _instruction_files(skill):
    canonical=state.RESOURCE_ROOT.parents[2];root=canonical/skill
    pending=[p for p in root.rglob('*') if p.is_file() and p.suffix=='.md'];seen=set()
    while pending:
        path=pending.pop();state._no_symlinks(path)
        if path in seen:continue
        seen.add(path)
        if len(seen)>6000:raise ValueError('Instruction reference inventory budget exceeded')
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                target=target.split('#',1)[0]
                if not target or '://' in target:continue
                link=(path.parent/target).resolve()
                if canonical in link.parents and link.is_file() and link.suffix in ('.md','.json','.txt'):pending.append(link)
    return seen

def _task_schemas(run,spec):
    names={'task-request','task-result','execution-reading'}
    key=spec['task_key']
    if key=='strategy.understand':names.add('strategy-draft')
    elif key.startswith('strategy.mission.'):names.add('strategy-mission')
    elif key=='strategy.reconcile' and state._contract_version(run,'audience_handoff_contract')==2:names.add('strategy-report-v2')
    if spec['isolation']=='independent_review':names.update(('review-receipt','quality-review','evaluation'))
    return {name:state.CONTRACT_ROOT/(name+'.schema.json') for name in sorted(names)}

def _plan(run,spec,parameters):
    required=['artifact:'+key for key in spec['inputs']]
    hashes=_inputs(run,required)
    contracts=transactions.contract_hashes();methods,_=_method_files(spec['methods'])
    contracts.update({key:state._sha(path) for key,path in methods.items()})
    selected=[]
    for ref in hashes:
        record=state._resolve(run,ref)
        if not record.get('path'):continue
        if spec['packet']=='creative_public':
            if not ref.startswith('artifact:') or record['audience'] not in ('client','public') or not record.get('public_allowed'):continue
        elif spec['packet']=='review_inputs' and ref not in required:continue
        path=state._safe_path(Path(run['root']),record['path']);selected.append(_descriptor(Path(run['root']),path,'input',record.get('audience','internal')))
    selected=list({f['path']:f for f in selected}.values())
    seed=state._digest({'run_id':run['id'],'key':spec['task_key'],'inputs':hashes,'parameters':parameters})[:16]
    destinations=_destinations(run,spec,seed)
    result={'schema_version':'1.0','kind':'plan','task_key':spec['task_key'],'stage_id':spec['stage_id'],'run_id':run['id'],'scope':state.delivery_scope(run),'input_parameters':parameters,'input_hashes':hashes,'profile_hash':state._digest(run['profile']),'contract_hashes':contracts,'packet_plan':{'kind':spec['packet'],'files':selected,'record_refs':required,'allowed_audiences':spec['audiences']},'packet':None,'output_roles':list(spec['outputs']),'output_destinations':destinations,'required_capabilities':spec['capabilities'],'isolation':{'mode':spec['isolation'],'creator_context_ref':None}}
    result['isolation']['creator_context_ref']=_creator_context(run,spec)
    result['task_fingerprint']=state._digest({k:result[k] for k in FINGERPRINT_FIELDS});result['task_id']='task-'+result['task_fingerprint'][:24]
    state._schema('task-request',result);return result

@phase
def ready_tasks(run_dir,host):
    state._schema('host-capabilities',host);_time(host['observed_at']);run=state.load_run(run_dir);view=deepcopy(run);state._invalidate_view(view)
    available={c['id'] for c in host['capabilities'] if c['status']=='AVAILABLE'}
    stages=state._quality_stages(view);stage=next((sid for sid in stages if state._stage_report(view,sid)['status']!='PASS'),None)
    config=transactions.execution_metadata(run)['config'];ready=[];blocked=[]
    for spec in _variants(view):
        if spec['stage_id']!=stage:continue
        if state.delivery_scope(run)=='client' and spec['stage_id']=='internal.handoffs':continue
        reasons=[]
        if set(spec['capabilities'])-available:reasons.append('Required host capability not reported AVAILABLE')
        if _completed(view,spec):
            reasons.append('Current outputs exist; finish the existing stage gate/review instead of regenerating them')
        parameters=_parameters(run,spec)
        try:plan=_plan(view,spec,parameters)
        except (ValueError,OSError,KeyError) as error:reasons.append(str(error));plan=None
        if reasons:blocked.append({'task_key':spec['task_key'],'stage_id':spec['stage_id'],'reasons':reasons})
        else:ready.append(plan)
    return {'status':'READY' if ready else 'BLOCKED','ready':ready,'blocked':blocked,'stage_id':stage,'scope':'pure_host_reported_inventory_not_usage_or_business_pass'}


def _plan_header(request):
    state._schema('task-request',request)
    if request['kind']!='plan':raise ValueError('claim-task requires the ready-tasks plan')
    expected=state._digest({k:request[k] for k in FINGERPRINT_FIELDS})
    if request['task_fingerprint']!=expected or request['task_id']!='task-'+expected[:24]:raise ValueError('Task fingerprint mismatch')

def _check_plan(run,request):
    _plan_header(request)
    spec=next((s for s in _variants(run) if s['task_key']==request['task_key']),None)
    if spec is None:raise ValueError('Unknown task key')
    view=deepcopy(run);state._invalidate_view(view)
    stage=next((sid for sid in state._quality_stages(view) if state._stage_report(view,sid)['status']!='PASS'),None)
    if spec['stage_id']!=stage:raise ValueError('Task is not in the first incomplete stage')
    rebuilt=_plan(view,spec,_parameters(run,spec))
    if rebuilt!=request:raise transactions.Conflict('CONFLICT: task plan changed or was altered')
    return spec


def _existing(root,run,task_id,fingerprint):
    for attempt in transactions.execution_metadata(run)['attempts'].values():
        if attempt['task_id']!=task_id:continue
        request=_request(root,attempt)
        if request['task_fingerprint']!=fingerprint:raise transactions.Conflict('CONFLICT: truncated task ID collision')
        if _live(attempt,_now()) or attempt['state']=='COMMITTED':return attempt,request
    return None


def _copy_exclusive(source,target,*,readonly=True):
    target.parent.mkdir(parents=True,exist_ok=True);state._no_symlinks(target)
    state._no_symlinks(source)
    fd=os.open(source,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as incoming:
        info=os.fstat(incoming.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size>512*1024*1024:raise ValueError('Snapshot source must be a bounded regular file')
        copied=0
        with target.open('xb') as outgoing:
            while True:
                chunk=incoming.read(min(1024*1024,info.st_size-copied+1))
                if not chunk:break
                copied+=len(chunk)
                if copied>info.st_size:raise transactions.Conflict('CONFLICT: input grew during snapshot')
                outgoing.write(chunk)
        if copied!=info.st_size:raise transactions.Conflict('CONFLICT: input shrank during snapshot')
    target.chmod(0o444 if readonly else 0o644)
    if state._sha(source)!=state._sha(target):raise transactions.Conflict('CONFLICT: input changed during snapshot')

def _write_frozen(path,data):
    encoded=state._canonical(data)+b'\n'
    if len(encoded)>4*1024*1024:raise ValueError('Execution JSON exceeds its bounded reader budget')
    with path.open('xb') as stream:stream.write(encoded)
    path.chmod(0o444)


def _freeze_packet(root,directory,run,plan,spec):
    if plan['packet_plan']['kind']=='none':return None
    kind=plan['packet_plan']['kind'];private=kind=='private_internal';selected=plan['packet_plan']['files']
    if kind=='creative_public':
        from .experience import require_packet_methods
        if state._stage_report(run,'brief.public')['status']!='PASS':raise ValueError('Creative packet requires the current public brief gate')
        require_packet_methods(run,[d['path'] for d in selected])
    files=[];sources={};snapshots=[]
    for descriptor in selected:
        if descriptor['audience'] not in plan['packet_plan']['allowed_audiences']:raise ValueError('Input audience outside the task allowlist')
        if kind=='creative_public':
            row=next((r for r in run['artifacts'].values() if r['path']==descriptor['path']),None)
            if not row or row['status']!='CURRENT' or not row['public_allowed'] or not row.get('approval',{}):raise ValueError('Creative input is not explicitly approved')
            if not row['approval'].get('actor') or row['approval'].get('sha256')!=descriptor['sha256']:raise ValueError('Creative approval is not bound to exact bytes')
            if not any(r.startswith(('source:','fact:')) for r in state._dependency_closure(run,['artifact:'+row['id']])):raise ValueError('Creative input lacks source provenance')
        sources['files/'+descriptor['path']]=(_file(root,descriptor),descriptor['role'],descriptor['audience'])
    methods,roots=_method_files(spec['methods'])
    for name,path in methods.items():sources[name]=(path,'method','public')
    # Role instructions and linked references are frozen together. Mutable
    # prepare JSON and upstream cache paths are never handed to the worker.
    for path in sorted(_instruction_files(spec['skill'])):
        sources['canonical/'+path.relative_to(state.RESOURCE_ROOT.parents[2]).as_posix()]=(path,'instruction','public')
    schemas=_task_schemas(run,spec)
    for name,path in schemas.items():
        sources['canonical/'+path.relative_to(state.RESOURCE_ROOT.parents[2]).as_posix()]=(path,'schema','public')
    if len(sources)>6000 or sum(p.stat().st_size for p,_,_ in sources.values())>512*1024*1024:raise ValueError('Frozen packet budget exceeded')
    for name,(source,role,audience) in sources.items():
        target=directory/name;_copy_exclusive(source,target);files.append(_descriptor(root,target,role,audience))
    if private:
        for ref in plan['input_hashes']:
            snapshots.append({'ref':ref,'digest':plan['input_hashes'][ref],'value':deepcopy(state._resolve(run,ref))})
    native={'task_key':plan['task_key'],'input_parameters':plan['input_parameters'],'inputs':[d for d in files if d['role']=='input'],'instructions':[d for d in files if d['role']=='instruction'],'methods':[{'family':s['id'],'commit':s['commit'],'reference_root':str(directory/'upstreams'/s['id']/s['commit']/'source'),'entrypoints':[str(directory/'upstreams'/s['id']/s['commit']/'source'/e) for e in s['entrypoints']]} for s,_ in roots],'output_destinations':plan['output_destinations'],'isolation':plan['isolation'],'execution':'HOST_REQUIRED_NOT_ATTESTED'}
    native['schemas']={name:str(directory/'canonical'/path.relative_to(state.RESOURCE_ROOT.parents[2])) for name,path in schemas.items()}
    if plan['task_key'].startswith('strategy.') and roots:
        from . import strategy
        method=next(m for m in native['methods'] if m['family']=='marketingskills');family=next(s for s,_ in roots if s['id']=='marketingskills')
        native['task']=strategy.task_data(run,method['reference_root'],family['commit'],family['entrypoints'])
        if plan['task_key']=='strategy.understand':native['task']['output']='strategy-draft.schema.json: proposed_missions only, no executed/completed/blocked outcome. Do not register observation-analysis-map before actual mission outcomes.'
    if spec.get('mission_id'):
        from . import strategy
        _,draft_path=strategy.artifact(run,'strategy-draft');draft=transactions.read_json(draft_path)
        native['mission']=next(m for m in draft['proposed_missions'] if m['id']==spec['mission_id'])
        native['mission_output']='strategy-mission.schema.json; retain the exact prepared task/target/success and record only actual outcome, sources and limits.'
    elif plan['task_key'].startswith('research.'):
        from . import public_research
        native['task']=public_research.task_data(run)
        if spec.get('topic'):native['task']['topics']=[t for t in native['task']['topics'] if t['topic']==spec['topic']]
    native['reading_boundary']='Read the frozen input and method paths above. Record snapshots retain original provenance paths; those are not invitations to read mutable source/cache files.'
    native['operation_boundary']='Write candidates only under .work/attempt_id/ using the exact work paths declared below. Propose closed operations in TaskResult; do not call state registration, review, freeze, adoption or publication writers from the worker. The coordinator retains those authorities and all canonical gates.'
    native['adoption_contract']={'output_artifact_ids':spec['completed_by'],'reviewer_id':spec.get('reviewer_id'),'stage_id':spec['stage_id'],'outputs':spec['outputs'],'result_schema':native['schemas']['task-result'],'work_prefix':'.work/'+directory.name+'/','quality':'No business PASS follows from a technical receipt; record actual evidence and limits.'}
    if spec['isolation']=='independent_review':
        native['adoption_contract']['rubric']=state._stages()[spec['stage_id']]
        native['adoption_contract']['requirements']=[r for r in state._requirements() if r['stage_id']==spec['stage_id']]
    native_path=directory/'native-task.json';_write_frozen(native_path,native);files.append(_descriptor(root,native_path,'native-task','internal' if private else 'public'))
    role_entry=(directory/'canonical'/spec['skill']/'SKILL.md').relative_to(root).as_posix()
    required_reads=[d['path'] for d in files if d['role'] in ('input','native-task','schema') or d['path']==role_entry]
    for method in native['methods']:
        required_reads.extend(Path(p).relative_to(root).as_posix() for p in method['entrypoints'])
    manifest={'schema_version':'1.0','scope':'internal_execution' if private else kind,'task_id':plan['task_id'],'files':files,'required_reads':sorted(set(required_reads)),'record_snapshots':snapshots,'source_record_hashes':plan['input_hashes']}
    state._schema('execution-inputs',manifest);path=directory/'manifest.json';_write_frozen(path,manifest)
    return {'kind':kind,'manifest_path':path.relative_to(root).as_posix(),'manifest_hash':state._sha(path),'files':files}

def _validate_packet(root,packet):
    path=state._safe_path(Path(root),_relative(packet['manifest_path']))
    if state._sha(path)!=packet['manifest_hash']:raise transactions.Conflict('CONFLICT: packet manifest changed')
    manifest=transactions.read_json(path);state._schema('execution-inputs',manifest)
    if manifest['files']!=packet['files']:raise ValueError('Packet file inventory differs from its manifest')
    for descriptor in manifest['files']:_file(root,descriptor)
    if not set(manifest['required_reads']).issubset({d['path'] for d in manifest['files']}):raise ValueError('Mandatory reading is outside the frozen inventory')
    for snapshot in manifest['record_snapshots']:
        if state._record_digest(snapshot['value'])!=snapshot['digest'] or manifest['source_record_hashes'].get(snapshot['ref'])!=snapshot['digest']:raise ValueError('Snapshot record binding changed')
    return manifest

@phase
def claim_task(run_dir,task_id,request):
    root=state._external_root(run_dir);run=state.load_run(root);_plan_header(request)
    if task_id!=request['task_id']:raise ValueError('Selected task ID mismatch')
    existing=_existing(root,run,task_id,request['task_fingerprint'])
    if existing:
        response={'status':existing[0]['state'],'attempt':existing[0],'request':existing[1],'dispatch_granted':False,'request_path':str(_request_path(root,existing[0]['attempt_id']))}
        if existing[0]['state']=='COMMITTED':
            receipt=transactions.execution_metadata(run)['receipts'].get(existing[0]['commit_operation_id'])
            if receipt is None:raise ValueError('Committed attempt is missing its receipt')
            response.update(receipt=receipt,current_validity=transactions._current_validity(run,receipt))
        return response
    spec=_check_plan(run,request)
    execution=transactions.execution_metadata(run)
    if len(execution['attempts'])>=1024:raise ValueError('Attempt budget reached; retain history and checkpoint')
    if sum(a['task_id']==task_id for a in execution['attempts'].values())>=request['input_parameters']['attempt_limit']:raise ValueError('Task attempt limit reached; diagnose before a new explicit revision')
    active=sum(_live(a,_now()) for a in execution['attempts'].values())
    if active>=execution['config']['max_host_tasks']:raise ValueError('Host task reservation budget reached')
    attempt_id='attempt-'+uuid4().hex;directory=root/'.execution/inputs'/attempt_id
    directory.mkdir(parents=True,exist_ok=False)
    packet=_freeze_packet(root,directory,run,request,spec)
    actual=deepcopy(request);actual.update(kind='request',packet=packet);actual['request_hash']=state._digest(actual);state._schema('task-request',actual)
    path=directory/'request.json';_write_frozen(path,actual)
    contracts,_=_method_files(spec['methods'])
    for source in contracts.values():state._sha(source)
    guard=commit_guard();now=_now();attempt={'attempt_id':attempt_id,'task_id':task_id,'request_hash':actual['request_hash'],'state':'CLAIMED','claimed_at':_utc(now),'claim_expires_at':_utc(now+timedelta(seconds=120)),'dispatch_key':None,'host_job_ref':None,'events':[],'result_ref':None,'commit_operation_id':None}
    with transactions.run_lock(root):
        current=state.load_run(root);_check_inputs(current,request);guard()
        # Only bounded state checks under lock; no packet, cache or reader work.
        current_execution=transactions.execution_metadata(current);attempts=current_execution['attempts']
        for row in attempts.values():
            if row['state']=='CLAIMED' and row['dispatch_key'] is None and not _live(row,now):
                row['state']='CANCELLED';row['events'].append({'schema_version':'1.0','event_id':'evt-'+uuid4().hex,'attempt_id':row['attempt_id'],'kind':'cancelled','observed_at':_utc(now),'evidence_ref':None,'payload':{'reason':'Reservation expired before dispatch intent','never_dispatched':True}})
        other=next((a for a in attempts.values() if a['task_id']==task_id and a['state'] in ACTIVE|{'COMMITTED'}),None)
        if other:reused=deepcopy(other)
        else:
            reused=None;execution=current_execution
            if sum(a['state'] in ACTIVE for a in execution['attempts'].values())>=execution['config']['max_host_tasks']:raise ValueError('Host task reservation budget reached')
            if sum(a['task_id']==task_id for a in execution['attempts'].values())>=request['input_parameters']['attempt_limit']:raise ValueError('Task attempt limit reached')
            execution['attempts'][attempt_id]=attempt;current['metadata']['execution']=execution;state._validate_structure(current);state._save_locked(root,current)
    invalidate()
    if reused:
        old_request=_request(root,reused)
        if old_request['task_fingerprint']!=request['task_fingerprint']:raise transactions.Conflict('CONFLICT: truncated task ID collision')
        return {'status':reused['state'],'attempt':reused,'request':old_request,'dispatch_granted':False,'request_path':str(_request_path(root,reused['attempt_id']))}
    return {'status':'CLAIMED','attempt':attempt,'request':actual,'dispatch_granted':False,'request_path':str(path)}


def _proof(root,descriptor):
    if descriptor is None:raise ValueError('Current host/result proof is required')
    path=_file(root,descriptor);return transactions.read_json(path)

def _attempt_contexts(root,attempt):
    # A lost dispatch response may leave only the reconciled host readback.
    contexts=set()
    for event in attempt.get('events',[]):
        if event['kind'] in ('dispatched','reconciled'):
            value=_proof(root,event['evidence_ref']).get('context_ref')
            if isinstance(value,str) and value.strip():contexts.add(value)
    return contexts


def _isolation_proof(root,run,attempt,request,proof):
    mode=request['isolation']['mode']
    if mode=='coordinator':return
    context=proof.get('context_ref')
    if not isinstance(context,str) or not context.strip():raise ValueError('Host receipt needs the actual context identity')
    previous=_attempt_contexts(root,attempt)
    if previous and previous!={context}:raise ValueError('Host readback changed the established attempt context')
    if mode=='continue_public':
        if context!=request['isolation']['creator_context_ref']:raise ValueError('Creative continuation changed its creator context')
        return
    if proof.get('fresh_context') is not True:raise ValueError('Fresh creator/reviewer context requires its host receipt')
    for other in transactions.execution_metadata(run)['attempts'].values():
        if other['attempt_id']==attempt['attempt_id']:continue
        if context in _attempt_contexts(root,other):raise ValueError('Creator/reviewer context was already used in this run')

def _result(root,descriptor,attempt):
    result=_proof(root,descriptor);state._schema('task-result',result)
    if result['attempt_id']!=attempt['attempt_id'] or result['request_hash']!=attempt['request_hash'] or result['task_id']!=attempt['task_id']:raise ValueError('Result identity mismatch')
    if result['status']!='SUCCEEDED':raise ValueError('Only a successful candidate may enter SUCCEEDED')
    return result

def _check_current(run,request,spec):
    view=deepcopy(run);state._invalidate_view(view);_check_inputs(view,request)
    methods,_=_method_files(spec['methods']);actual=transactions.contract_hashes()
    actual.update({key:state._sha(path) for key,path in methods.items()})
    if actual!=request['contract_hashes']:raise transactions.Conflict('CONFLICT: task contracts or selected methods changed')

def _read_receipt(root,result,request,attempt):
    packet=request['packet']
    if packet is None:
        if result['consumed_packet_hash'] is not None or result['read_receipt_ref'] is not None:raise ValueError('An initial collection consumes its hashed parameters, not a fabricated packet')
        return
    manifest=_validate_packet(root,packet)
    if result['consumed_packet_hash']!=packet['manifest_hash']:raise ValueError('Result did not consume the requested packet')
    receipt=_proof(root,result['read_receipt_ref']);state._schema('execution-reading',receipt)
    _time(receipt['observed_at'])
    if any(receipt[key]!=expected for key,expected in {'attempt_id':attempt['attempt_id'],'request_hash':attempt['request_hash'],'manifest_hash':packet['manifest_hash'],'host_job_ref':attempt['host_job_ref']}.items()):raise ValueError('Reading receipt does not bind the dispatched worker and packet')
    inventory={d['path']:d for d in manifest['files']};read={d['path']:d for d in receipt['read_files']}
    if len(read)!=len(receipt['read_files']) or any(path not in inventory or any(descriptor[k]!=inventory[path][k] for k in ('sha256','size_bytes')) for path,descriptor in read.items()):raise ValueError('Reading receipt names unverified packet bytes')
    required=set(manifest['required_reads'])
    if not required.issubset(read):raise ValueError('Reading receipt omits mandatory inputs or skill entrypoints')
    if request['isolation']['mode'] in ('fresh_public','continue_public','independent_review') and receipt['kind']!='agent_declared_reading':raise ValueError('This role requires its actual agent reading receipt; a mechanical copy is insufficient')

def _output_mapping(root,attempt,request,spec,outputs):
    prefix='.work/'+attempt['attempt_id']+'/';mapping={};roles=set();seen=set()
    for descriptor in outputs:
        source=_file(root,descriptor);relative=_relative(descriptor['path']);role=descriptor['role'];details=spec['outputs'].get(role)
        if details is None or descriptor['audience']!=details['audience'] or not relative.startswith(prefix):raise ValueError('Output is outside this attempt or role/audience contract')
        if relative in seen:raise ValueError('Duplicate output descriptor')
        seen.add(relative);subpath=relative[len(prefix):];destination=request['output_destinations'][role]
        if details['kind']=='file':
            if subpath!=details['name'] or role in roles:raise ValueError('Fixed output must use its declared full work path')
        else:
            work_prefix=details.get('work_prefix',details['name'])+'/'
            if not subpath.startswith(work_prefix):raise ValueError('Tree output is outside its declared work prefix')
            destination+='/'+subpath[len(work_prefix):]
        destination=_relative(destination)
        if destination in mapping:raise ValueError('Two outputs map to the same destination')
        mapping[destination]=(source,descriptor);roles.add(role)
    if {r for r,details in spec['outputs'].items() if not details.get('optional',False)}-roles:raise ValueError('Task omitted required output roles')
    return mapping

def _check_operations(run,request,spec,operations,mapping):
    key=spec['task_key'];domain={'discovery.site.collect':'discovery.register','research.reconcile':'discovery.reconcile','strategy.reconcile':'strategy.register'}.get(key)
    for operation in operations:
        name=operation['op'];args=operation['args']
        research_role=key.startswith(('research.topic.','strategy.','analysis.specialists.','company.'))
        if name=='source.register' and research_role:
            if args.get('path') not in mapping or args.get('kind')=='private' or (args['source_id'] in run['sources'] and 'source:'+args['source_id'] not in request['input_hashes']):raise ValueError('Source registration is outside current task outputs or authority')
            continue
        if name=='fact.register' and research_role:
            if args['fact_id'] in run['facts'] and 'fact:'+args['fact_id'] not in request['input_hashes']:raise ValueError('Fact replacement lacks its current input precondition')
            continue
        if key.startswith('stage-review.') and name in ('stage-review.record','evaluation.record'):
            if name=='stage-review.record' and args['stage_id']!=spec['stage_id']:raise ValueError('Review cannot change another stage')
            if name=='evaluation.record' and args['requirement_id'] not in {r['id'] for r in state._requirements() if r['stage_id']==spec['stage_id']}:raise ValueError('Assessment is outside the reviewed stage')
            continue
        if key.startswith('review.client.') and name=='evaluation.record':
            if args['requirement_id']!='quality' or args['evaluation'].get('reviewer_id')!=spec['reviewer_id']:raise ValueError('Client review changed its assigned reviewer')
            continue
        if domain:
            if name!=domain:raise ValueError('Operation is outside the selected task role')
        elif name!='artifact.register':raise ValueError('Operation is outside the selected task role')
        elif args['artifact_id'] not in spec['completed_by']:
            details=mapping.get(args.get('path'))
            protected={i for role in _specs() for i in role['completed_by']}|{'composition-plan-review','creative-placements'}
            if details is None or spec['outputs'][details[1]['role']]['kind']!='tree' or args['artifact_id'] in run['artifacts'] or args['artifact_id'] in protected:
                raise ValueError('Undeclared artifact or overwrite outside the task role')
        field='path' if name=='artifact.register' else 'report_path' if name in ('discovery.register','strategy.register') else 'receipts_path'
        if args.get(field) not in mapping:raise ValueError('Adoption operation does not reference a reserved output')
        if name=='artifact.register' and args['audience']!=mapping[args[field]][1]['audience']:raise ValueError('Artifact audience differs from its declared output')

def _reject_stale(root,attempt):
    with transactions.run_lock(root):
        current=state.load_run(root);execution=transactions.execution_metadata(current);row=execution['attempts'][attempt['attempt_id']]
        if row['state']=='REJECTED_STALE':return
        if row['state']!='SUCCEEDED' or row['request_hash']!=attempt['request_hash']:raise transactions.Conflict('CONFLICT: attempt changed before stale rejection')
        row['state']='REJECTED_STALE';current['metadata']['execution']=execution;state._validate_structure(current);state._save_locked(root,current)
    invalidate()

def _check_future_outputs(request,plan):
    from .composition import OUTPUTS
    expected={key:request['output_destinations'][key] for key in OUTPUTS}
    if plan.get('outputs')!=expected:raise ValueError('Candidate composition plan changed destinations reserved before planning')

@phase
def accept_task_result(run_dir,result):
    state._schema('task-result',result);root=state._external_root(run_dir);run=state.load_run(root);attempt=transactions.execution_metadata(run)['attempts'].get(result['attempt_id'])
    if not attempt:raise ValueError('Unknown result attempt')
    request=_request(root,attempt)
    if attempt['state'] not in ('SUCCEEDED','COMMITTED'):raise ValueError('Result is not an adoptable successful candidate')
    stored=_result(root,attempt['result_ref'],attempt)
    if stored!=result:raise transactions.Conflict('CONFLICT: supplied result differs from the received candidate')
    for key in ('run_id','task_id','request_hash','input_hashes','profile_hash','contract_hashes'):
        if result[key]!=request[key]:raise ValueError('Result changed requested identity or preconditions')
    if attempt['state']=='COMMITTED':
        receipt=transactions.execution_metadata(run)['receipts'].get(attempt['commit_operation_id'])
        if receipt is None:raise ValueError('Committed task has no atomic operation receipt')
        return {'status':'REPLAYED','receipt':receipt,'current_validity':transactions._current_validity(run,receipt)}
    spec=next(s for s in _variants(run) if s['task_key']==request['task_key']);_read_receipt(root,result,request,attempt)
    mapping=_output_mapping(root,attempt,request,spec,result['outputs']);_check_operations(run,request,spec,result['operations'],mapping)
    if spec['task_key']=='client.composition.plan':
        operation=next((o for o in result['operations'] if o['op']=='artifact.register' and o['args']['artifact_id']=='client-story-map'),None)
        if operation is None:raise ValueError('Composition planning must register its current plan')
        _check_future_outputs(request,transactions.read_json(mapping[operation['args']['path']][0]))
    if spec['task_key']=='strategy.understand':
        from . import strategy
        operation=next((o for o in result['operations'] if o['op']=='artifact.register' and o['args']['artifact_id']=='strategy-draft'),None)
        if operation is None:raise ValueError('Strategy understanding must produce its proposed-mission draft')
        strategy.validate_draft(run,transactions.read_json(mapping[operation['args']['path']][0]))
    if spec['task_key']=='strategy.reconcile':
        operation=next(o for o in result['operations'] if o['op']=='strategy.register');final=transactions.read_json(mapping[operation['args']['report_path']][0]);actual={}
        for identifier in spec['inputs']:
            if identifier.startswith('strategy-mission-'):
                row=run['artifacts'][identifier];mission=transactions.read_json(state._safe_path(root,row['path']));actual[mission['id']]=mission
        if {m['id']:m for m in final['missions']}!=actual:raise ValueError('Final strategy replaced or invented an actual mission outcome')
    try:_check_current(run,request,spec)
    except transactions.Conflict as error:
        _reject_stale(root,attempt);return {'status':'REJECTED_STALE','reason':str(error),'attempt_id':attempt['attempt_id'],'publication':'NOT_ADOPTED'}
    # Every collision is checked before the first copy. A previous failed commit
    # may leave an identical candidate; it is verified and never overwritten.
    for destination,(source,descriptor) in mapping.items():
        target=state._safe_path(root,destination,exists=False)
        if target.exists() and (not target.is_file() or target.stat().st_size!=descriptor['size_bytes'] or state._sha(target)!=descriptor['sha256']):raise transactions.Conflict('CONFLICT: reserved destination already contains different bytes')
    for destination,(source,descriptor) in mapping.items():
        target=state._safe_path(root,destination,exists=False)
        if not target.exists():_copy_exclusive(source,target,readonly=False)
        if state._sha(target)!=descriptor['sha256']:raise transactions.Conflict('CONFLICT: output changed during publication')
    # The final transaction rechecks the same frozen files/inputs under its
    # existing commit guard and commits the attempt with its business records.
    batch={'schema_version':'1.0','operation_id':'op-adopt-'+attempt['attempt_id'].removeprefix('attempt-'),'run_id':run['id'],'expected_inputs':request['input_hashes'],'expected_contracts':transactions.contract_hashes(),'expected_profile_hash':request['profile_hash'],'expected_state_revision':None,'operations':result['operations']}
    batch['payload_sha256']=state._digest(batch)
    return transactions.apply_batch(root,batch,_task_adoption={'attempt_id':attempt['attempt_id'],'request_hash':attempt['request_hash'],'result_ref':attempt['result_ref']})

@phase
def task_event(run_dir,event):
    state._schema('task-event',event);_time(event['observed_at']);root=state._external_root(run_dir);run=state.load_run(root);attempt=transactions.execution_metadata(run)['attempts'].get(event['attempt_id'])
    if attempt is None:raise ValueError('Unknown attempt')
    request=_request(root,attempt);kind=event['kind'];payload=event['payload'];proof=None;result_ref=None
    previous=next((e for e in attempt['events'] if e['event_id']==event['event_id']),None)
    if previous is not None:
        if previous!=event:raise transactions.Conflict('CONFLICT: event ID reused with another payload')
        return {'status':attempt['state'],'attempt':attempt,'dispatch_granted':False}
    if kind in ('dispatched','failed','reconciled') or (kind=='cancelled' and attempt['state']!='CLAIMED'):
        proof=_proof(root,event['evidence_ref'])
        if proof.get('attempt_id')!=attempt['attempt_id'] or proof.get('request_hash')!=attempt['request_hash']:raise ValueError('Host proof belongs to another attempt/request')
        if attempt['dispatch_key'] is not None and proof.get('dispatch_key')!=attempt['dispatch_key']:raise ValueError('Host proof does not bind the persisted dispatch key')
        if attempt['host_job_ref'] is not None and proof.get('host_job_ref')!=attempt['host_job_ref']:raise ValueError('Host proof belongs to another host job')
        if kind in ('dispatched','reconciled'):_isolation_proof(root,run,attempt,request,proof)
    if kind=='result_ready':
        proof=_proof(root,event['evidence_ref'])
        if event['evidence_ref']['path']!=payload['result_path'] or event['evidence_ref']['sha256']!=payload['result_sha256']:raise ValueError('Result proof binding mismatch')
        _result(root,event['evidence_ref'],attempt)
    if kind=='reconciled' and payload['observed_state']=='SUCCEEDED':
        if payload['result_path'] is None or payload['result_sha256'] is None:raise ValueError('Reconciled success needs its result')
        path=state._safe_path(root,_relative(payload['result_path']));result_ref={'path':payload['result_path'],'sha256':payload['result_sha256'],'size_bytes':path.stat().st_size}
        _result(root,result_ref,attempt)
    guard=commit_guard();granted=False
    with transactions.run_lock(root):
        current=state.load_run(root);execution=transactions.execution_metadata(current);row=execution['attempts'][attempt['attempt_id']]
        previous=next((e for e in row['events'] if e['event_id']==event['event_id']),None)
        if previous:
            if previous!=event:raise transactions.Conflict('CONFLICT: event ID reused with another payload')
            return {'status':row['state'],'attempt':row,'dispatch_granted':False}
        guard();before=row['state']
        if kind in ('dispatched','reconciled') and request['isolation']['mode'] in ('fresh_public','independent_review') and execution['revision']!=transactions.execution_metadata(run)['revision']:raise transactions.Conflict('CONFLICT: recheck context isolation after the intervening state write')
        if kind=='dispatch_intent':
            if before!='CLAIMED':
                if row['dispatch_key']==payload['dispatch_key']:return {'status':before,'attempt':row,'dispatch_granted':False}
                raise transactions.Conflict('CONFLICT: dispatch was already attempted')
            if _now()>_time(row['claim_expires_at']):raise ValueError('Reservation expired before dispatch')
            row['state']='DISPATCHING';row['dispatch_key']=payload['dispatch_key'];granted=True
        elif kind=='dispatched':
            if before!='DISPATCHING' or proof.get('state')!='RUNNING' or proof.get('host_job_ref')!=payload['host_job_ref']:raise ValueError('Dispatched event lacks a matching running host receipt')
            row['state']='RUNNING';row['host_job_ref']=payload['host_job_ref']
        elif kind=='unknown_outcome':
            if before not in ('DISPATCHING','RUNNING') or payload['last_known_state']!=before:raise ValueError('Invalid unknown-outcome transition')
            row['state']='UNKNOWN_OUTCOME'
        elif kind=='result_ready':
            if before!='RUNNING':raise ValueError('Result requires an actually dispatched attempt')
            row['state']='SUCCEEDED';row['result_ref']=event['evidence_ref']
        elif kind=='failed':
            if before not in ('DISPATCHING','RUNNING') or proof.get('state')!='FAILED' or proof.get('host_terminal_status')!=payload['host_terminal_status']:raise ValueError('Failure requires terminal host evidence')
            row['state']='FAILED'
        elif kind=='cancelled':
            if before not in ACTIVE:raise ValueError('Cannot cancel a terminal attempt retroactively')
            if before=='CLAIMED' and payload['never_dispatched'] and row['dispatch_key'] is None:row['state']='CANCELLED'
            elif proof and proof.get('state')=='CANCELLED':row['state']='CANCELLED'
            else:raise ValueError('Cancellation needs evidence of its actual scope')
        elif kind=='reconciled':
            observed=payload['observed_state']
            if before!='UNKNOWN_OUTCOME' or proof.get('state')!=observed or proof.get('host_job_ref')!=payload['host_job_ref']:raise ValueError('Reconciliation needs matching host readback')
            row['state']=observed;row['host_job_ref']=payload['host_job_ref']
            if observed=='SUCCEEDED':
                row['result_ref']=result_ref
        else:raise ValueError('Unsupported task event')
        if len(row['events'])>=256:raise ValueError('Attempt event budget reached')
        row['events'].append(deepcopy(event));current['metadata']['execution']=execution;state._validate_structure(current);state._save_locked(root,current)
    invalidate();return {'status':row['state'],'attempt':row,'dispatch_granted':granted}

@phase
def execution_status(run_dir):
    run=state.load_run(run_dir);execution=transactions.execution_metadata(run)
    return {'status':'OBSERVED','attempts':execution['attempts'],'revision':execution['revision'],'business_quality':'NOT_ASSESSED','host_usage':'VERIFY_ACTUAL_RECEIPTS'}
