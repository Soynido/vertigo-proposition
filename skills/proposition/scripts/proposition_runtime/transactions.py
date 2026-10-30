"""Short interprocess locks. Preparation, network and renderers stay outside."""
from contextlib import contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import stat
import time
from .validation import phase
from .validation import file_reader

MAX_STATE_BYTES=32*1024*1024
_held=ContextVar('proposition_state_lock',default=None)

class Conflict(ValueError):
    code=3
class Busy(ValueError):
    code=4

@file_reader(4*1024*1024,mode='execution_json')
def read_json(path):
    import json,subprocess,sys
    from .telemetry import file_read
    try:result=subprocess.run([sys.executable,str(Path(__file__).with_name('recovery.py')),'--read-small',str(path),str(4*1024*1024)],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired as error:raise ValueError('Execution input read deadline exceeded (5s)') from error
    if result.returncode or len(result.stdout)>4*1024*1024:raise ValueError('Execution input must be a bounded regular file without symlinks')
    file_read('reader.json',path,len(result.stdout));return json.loads(result.stdout)

class Snapshot(dict):
    """Read fingerprint is process-local, never serialized into business state."""
    def __init__(self,value,base_sha256):
        super().__init__(value);self.base_sha256=base_sha256

@contextmanager
def run_lock(root,timeout=.250):
    from .state import _no_symlinks
    root=Path(root)
    if _held.get() is not None:raise ValueError('Nested state lock is not allowed')
    path=_no_symlinks(root/'.execution.lock')
    fd=os.open(path,os.O_CREAT|os.O_RDWR|getattr(os,'O_NOFOLLOW',0),0o600)
    token=None;locked=False
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('Lock must be a regular file')
        if os.name=='nt' and os.fstat(fd).st_size==0:os.write(fd,b'\0')
        until=time.monotonic()+timeout
        while True:
            try:
                if os.name=='nt':
                    import msvcrt
                    os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
                else:
                    import fcntl
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                locked=True;break
            except (BlockingIOError,PermissionError,OSError) as error:
                import errno
                if getattr(error,'errno',None) not in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):raise
                if time.monotonic()>=until:raise Busy('BUSY: state writer lock unavailable') from error
                time.sleep(min(.01,max(0,until-time.monotonic())))
        info=os.fstat(fd);current=_no_symlinks(path).stat()
        if (info.st_dev,info.st_ino)!=(current.st_dev,current.st_ino):raise Conflict('CONFLICT: lock inode changed')
        token=_held.set(str(root));yield
    finally:
        if token is not None:_held.reset(token)
        if locked:
            if os.name=='nt':
                import msvcrt
                os.lseek(fd,0,os.SEEK_SET);msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

# In-memory domain preparation. Existing validators are reused without IO commits.
_working=ContextVar('proposition_prepared_state',default=None)


def working_state(root):
    workspace=_working.get()
    return workspace if workspace is not None and workspace['root']==str(root) else None


@contextmanager
def prepare_state(root,initial):
    from copy import deepcopy
    if _working.get() is not None:raise ValueError('Nested batch preparation is not allowed')
    workspace={'root':str(root),'state':deepcopy(initial)};token=_working.set(workspace)
    try:yield workspace
    finally:_working.reset(token)


def contract_hashes():
    from . import state
    root=state.RESOURCE_ROOT.parents[2]
    return {p.relative_to(root).as_posix():state._sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.md','.txt')}


def execution_metadata(run):
    from copy import deepcopy
    existing=run.get('metadata',{}).get('execution')
    if existing is not None:return deepcopy(existing)
    return {'schema_version':'1.0','writer_version':'transactions-1.0','revision':0,
            'config':{'concurrency':1,'panel_scan':'legacy','image_wait_policy':'legacy','proof_storage':'expanded','max_host_tasks':1},
            'attempts':{},'receipts':{}}


def _operation(root, operation):
    from . import state
    from copy import deepcopy
    name=operation['op'];args=deepcopy(operation['args']);run=state.load_run(root)
    if name.startswith('source.'):
        identifier=args.pop('source_id');observed=args.pop('observed_at',None);proof=args.pop('observation_proof',None)
        record=state._source_record(run,identifier,**args)
        if name=='source.reobserve':
            from .discovery_evidence import _validate
            from datetime import datetime
            descriptor=proof['file'];path=state._safe_path(Path(root),descriptor['path'])
            if state._sha(path)!=descriptor['sha256'] or path.stat().st_size!=descriptor['size_bytes']:raise ValueError('Invalid new observation proof')
            data,files=_validate(run,path);source=next((s for s in data['sources'] if s['id']==proof['source_id']),None)
            if (not source or source['url']!=record['locator'] or datetime.fromisoformat(source['retrieved_at'])!=datetime.fromisoformat(observed)
                    or datetime.fromisoformat(observed).tzinfo is None or record['path'] not in {files[a['path']].relative_to(root).as_posix() for a in source['artifacts']}):
                raise ValueError('New observation does not bind URL/date/capture')
            previous=run['sources'].get(identifier)
            if previous and datetime.fromisoformat(observed)<=datetime.fromisoformat(previous['observed_at']):
                raise ValueError('A new observation requires a newer evidenced capture')
            record['observed_at']=observed
            record['metadata']={'observation_proof':proof}
        else:
            old=run['sources'].get(identifier)
            ignored={'observed_at'}|({'status'} if old and old['status']=='STALE' else set())
            if old and all(old.get(k)==v for k,v in record.items() if k not in ignored):record=old
        run['sources'][identifier]=record;state.save_run(root,run);return
    if name=='artifact.register':
        identifier=args.pop('artifact_id')
        if identifier=='strategy-draft':
            from . import strategy
            strategy.validate_draft(run,read_json(state._safe_path(Path(root),args['path'])))
        elif identifier.startswith('strategy-mission-'):
            from . import strategy
            _,draft_path=strategy.artifact(run,'strategy-draft')
            strategy.validate_mission(run,read_json(draft_path),identifier.removeprefix('strategy-mission-'),read_json(state._safe_path(Path(root),args['path'])))
        elif identifier.startswith('research-topic-'):
            from . import public_research
            public_research.validate_topic(run,read_json(state._safe_path(Path(root),args['path'])),identifier.removeprefix('research-topic-'))
        run['artifacts'][identifier]=state._artifact_record(run,identifier,reuse_current=True,**args);state.save_run(root,run);return
    if name=='fact.register':
        identifier=args.pop('fact_id');old=deepcopy(run['facts'].get(identifier));state.add_fact(root,identifier,**args);current=state.load_run(root);new=current['facts'][identifier]
        ignored={'recorded_at'}|({'status'} if old and old['status']=='STALE' else set())
        if old and all(old.get(k)==v for k,v in new.items() if k not in ignored):current['facts'][identifier]=old;state.save_run(root,current)
        return
    if name=='evaluation.record':state.record_evaluation(root,args['requirement_id'],args['evaluation']);return
    if name=='checkpoint.record':state.record_checkpoint(root,args['checkpoint_id'],args['stage_id'],args['checkpoint']);return
    if name=='stage-review.record':state.record_stage_review(root,args['stage_id'],args['review']);return
    if name=='strategy.register':
        from . import strategy
        result=strategy.register(root,state._safe_path(Path(root),args['report_path']))
    elif name=='discovery.register':
        from . import discovery_evidence
        result=discovery_evidence.register(root,state._safe_path(Path(root),args['report_path']))
    elif name=='discovery.reconcile':
        from . import discovery_evidence
        result=discovery_evidence.reconcile(root,state._safe_path(Path(root),args['receipts_path']))
    else:raise ValueError('Unsupported batch operation')
    # The domain has validated the files. Its business gate can remain BLOCKED
    # while valid partial observations are retained for continuation.
    return result


def _check_preconditions(run,batch):
    from . import state
    if run['id']!=batch['run_id'] or state._digest(run['profile'])!=batch['expected_profile_hash']:raise Conflict('CONFLICT: run/profile changed')
    revision=execution_metadata(run)['revision']
    if batch['expected_state_revision'] is not None and batch['expected_state_revision']!=revision:raise Conflict('CONFLICT: state revision changed')
    refs=set(batch['expected_inputs'])
    if not state._dependency_closure(run,refs).issubset(refs):raise ValueError('Expected inputs must include their transitive closure')
    for ref,digest in batch['expected_inputs'].items():
        record=state._resolve(run,ref)
        if not record or record.get('status')=='STALE' or state._record_digest(record)!=digest:raise Conflict('CONFLICT: input changed '+ref)


def _current_validity(run,receipt):
    from . import state
    result={}
    for ref in receipt['record_refs']:
        record=state._resolve(run,ref)
        if not record:result[ref]='MISSING';continue
        try:
            stale=state._stale_reasons(run,Path(run['root']),record)
            result[ref]='STALE' if record.get('status')=='STALE' or stale or state._record_digest(record)!=receipt['record_hashes_after_commit'][ref] else 'CURRENT'
        except (ValueError,OSError,KeyError):result[ref]='UNKNOWN'
    return result


def _output_refs(run,operations):
    from . import state
    refs=set()
    simple={'source.register':('source','source_id'),'source.reobserve':('source','source_id'),
            'fact.register':('fact','fact_id'),'artifact.register':('artifact','artifact_id'),
            'checkpoint.record':('checkpoint','checkpoint_id'),'stage-review.record':('stage_review','stage_id')}
    for operation in operations:
        name=operation['op'];args=operation['args']
        if name in simple:
            kind,key=simple[name];refs.add(kind+':'+args[key])
        elif name=='evaluation.record':
            refs.add('review:'+args['evaluation']['reviewer_id'] if args['requirement_id']=='quality' else 'evaluation:'+args['requirement_id'])
        else:
            refs.add('artifact:'+{'strategy.register':'observation-analysis-map','discovery.register':'site-discovery','discovery.reconcile':'discovery-channels'}[name])
            path=args.get('report_path',args.get('receipts_path'))
            relative=state._safe_path(Path(run['root']),path).relative_to(run['root']).as_posix()
            refs.update('artifact:'+key for key,value in run['artifacts'].items() if value['path']==relative)
    return refs


@phase
def apply_batch(run_dir,batch,*,_task_adoption=None):
    """Prepare with domain validators; short guarded merge and one durable write."""
    from copy import deepcopy
    from . import state
    from .validation import _identity, invalidate, commit_guard
    state._schema('operation-batch',batch)
    supplied=batch['payload_sha256'];payload={k:v for k,v in batch.items() if k!='payload_sha256'}
    if state._digest(payload)!=supplied:raise ValueError('Batch payload hash mismatch')
    root=state._external_root(run_dir);base=state.load_run(root);execution=execution_metadata(base);old=execution['receipts'].get(batch['operation_id'])
    if old:
        if old['payload_sha256']!=supplied:raise Conflict('CONFLICT: operation ID reused with another payload')
        return {'status':'REPLAYED','receipt':old,'current_validity':_current_validity(base,old)}
    if len(execution['receipts'])>=4096:raise ValueError('Execution receipt budget reached; retain history and checkpoint')
    _check_preconditions(base,batch)
    actual=contract_hashes()
    if batch['expected_contracts']!=actual:raise Conflict('CONFLICT: canonical contracts changed')
    contract_root=state.RESOURCE_ROOT.parents[2];identities={contract_root/p:_identity(contract_root/p) for p in actual}
    with prepare_state(root,base) as workspace:
        for operation in batch['operations']:_operation(root,operation)
        prepared=deepcopy(workspace['state'])
    state._validate_structure(prepared)
    changed={}
    for kind,collection in state._COLLECTIONS.items():
        for key,value in prepared[collection].items():
            if value!=base[collection].get(key):changed[kind+':'+key]=value
    needed=set()
    for record in changed.values():
        if record.get('status')!='STALE':needed.update(state._dependency_closure(prepared,record.get('dependencies',[])))
    if {r for r in needed if state._resolve(base,r)}-set(batch['expected_inputs']):raise ValueError('Batch omitted used input preconditions')
    output_refs=set(changed)|_output_refs(prepared,batch['operations'])
    before_files=deepcopy(base)
    for ref in output_refs:
        kind,key=ref.split(':',1);before_files[state._COLLECTIONS[kind]].pop(key,None)
    files=state._prepared_file_inputs(before_files,prepared)
    metadata_delta={k:v for k,v in prepared.get('metadata',{}).items() if k!='execution' and v!=base.get('metadata',{}).get(k)}
    guard=commit_guard()
    with run_lock(root):
        current=state.load_run(root);existing=execution_metadata(current)['receipts'].get(batch['operation_id'])
        if existing:
            if existing['payload_sha256']!=supplied:raise Conflict('CONFLICT: operation ID reused')
            replay=existing
        else:
            replay=None;_check_preconditions(current,batch)
            for path,identity in {**identities,**files}.items():
                if _identity(path)!=identity:raise Conflict('CONFLICT: prepared file or contract changed')
            guard()
            for ref,record in changed.items():
                if state._resolve(current,ref)!=state._resolve(base,ref):raise Conflict('CONFLICT: output changed '+ref)
                kind,key=ref.split(':',1);current[state._COLLECTIONS[kind]][key]=record
            for key,value in metadata_delta.items():
                if current['metadata'].get(key)!=base['metadata'].get(key):raise Conflict('CONFLICT: adoption metadata changed')
                current['metadata'][key]=value
            state._validate_active_graph(current)
            output_refs.update(state._invalidate_dependencies(current))
            execution=execution_metadata(current)
            if len(execution['receipts'])>=4096:raise ValueError('Execution receipt budget reached')
            if _task_adoption is not None:
                # Internal caller supplies only a previously verified attempt
                # identity; adoption and business records share this one commit.
                attempt=execution['attempts'].get(_task_adoption['attempt_id'])
                if not attempt or attempt['state']!='SUCCEEDED' or attempt['request_hash']!=_task_adoption['request_hash'] or attempt['result_ref']!=_task_adoption['result_ref']:
                    raise Conflict('CONFLICT: task changed before atomic adoption')
                attempt['state']='COMMITTED';attempt['commit_operation_id']=batch['operation_id']
            receipt={'operation_id':batch['operation_id'],'payload_sha256':supplied,'committed_revision':execution['revision']+1,'committed_at':state._now().replace('+00:00','Z'),'record_refs':sorted(output_refs),'record_hashes_after_commit':{ref:state._record_digest(state._resolve(current,ref)) for ref in output_refs}}
            execution['receipts'][batch['operation_id']]=receipt;current['metadata']['execution']=execution
            state._validate_structure(current);state._save_locked(root,current)
    invalidate()
    if replay:return {'status':'REPLAYED','receipt':replay,'current_validity':_current_validity(state.load_run(root),replay)}
    return {'status':'COMMITTED','receipt':receipt,'current_validity':_current_validity(state.load_run(root),receipt)}
