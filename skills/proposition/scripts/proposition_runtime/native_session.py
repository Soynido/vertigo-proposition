"""Installed same-lane bootstrap for an owned native production context.

The Desktop lane opens the panel. This service observes its own execution tree,
never attaches to another Desktop turn, and cannot manufacture panel approval.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from datetime import datetime,timezone
from uuid import uuid4
from . import state
from .transactions import run_lock,read_json
from .publication import write_json


def workspace_setup(workspace):
    root=state._external_root(workspace);specific=root/'.vertigo/setup-codex.json'
    return read_json(specific if specific.exists() else root/'.vertigo/setup.json')


def input_inventory(workspace):
    root=state._external_root(workspace);setup=workspace_setup(root)
    # Installed skills are protected from run writes, not from read-only hashing.
    dest=state._no_symlinks(Path(setup['skills_destination']).expanduser().absolute())
    if not dest.is_dir():raise ValueError('Installed skills directory is missing')
    manifest=read_json(dest/'.proposition-install.json');files=[dest/'.proposition-install.json']
    for name,expected in manifest['files'].items():
        path=state._safe_path(dest,name)
        if state._sha(path)!=expected:raise ValueError('Installed installation bytes changed')
        files.append(path)
    for folder in [root,*root.parents,Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))]:
        for name in ('AGENTS.md','AGENTS.override.md'):
            path=folder/name
            if path.exists():files.append(state._no_symlinks(path))
    for name in ('setup.json','setup-codex.json','profile.json'):
        path=root/'.vertigo'/name
        if path.exists():files.append(state._no_symlinks(path))
    config=dest/'proposition/installation.json'
    if config.exists():files.append(state._no_symlinks(config))
    return list(dict.fromkeys(files))


def is_worker(workspace,thread_id):
    if not thread_id:return False
    root=state._external_root(workspace);pointer=root/'.vertigo/native/current.json'
    if not pointer.exists():return False
    session=state._external_root(read_json(pointer)['session'])
    if not session.is_relative_to(root/'.vertigo/native'):raise ValueError('Invalid native session path')
    launch=session/'launch.json'
    return launch.exists() and read_json(launch).get('thread_id')==thread_id


def admission_time(workspace,thread_id,site_url):
    for root in (Path(workspace).absolute(),*Path(workspace).absolute().parents):
        pointer=root/'.vertigo/native/current.json'
        if pointer.exists() and is_worker(root,thread_id):
            folder=Path(read_json(pointer)['session']);request=read_json(folder/'request.json')
            if request['prompt'].splitlines()[1]!=site_url:raise ValueError('Native admission belongs to another site')
            return datetime.fromtimestamp(request['created_at'],timezone.utc).isoformat()
    return None


def register_open(session,path,caller):
    folder=state._external_root(session)
    with run_lock(folder):
        owner=read_json(folder/'session.json')['owner_thread_id'];raw=read_json(path)
        if raw.get('isError'):raise ValueError('UI opening failed')
        data=raw if 'status' in raw else json.loads(next(x['text'] for x in raw['content'] if x.get('type')=='text'))
        if caller!=owner or data.get('threadId')!=owner or data.get('status') not in ('opened','queued'):
            raise ValueError('UI must open in the calling lane')
        target=folder/'panel-open.json'
        normalized={'status':data['status'],'threadId':owner}
        if target.exists():
            if read_json(target)!=normalized:raise ValueError('Panel receipt cannot be replaced')
        else:write_json(target,normalized)
        return normalized


def prepare(workspace,prompt,*,model,effort,caller):
    root=state._external_root(workspace)
    from urllib.parse import urlsplit
    if not model or effort not in ('low','medium','high','xhigh','max','ultra'):raise ValueError('Explicit installed model/effort required')
    if len(prompt.splitlines())!=2 or any(urlsplit(x).scheme!='https' or not urlsplit(x).hostname for x in prompt.splitlines()):
        raise ValueError('Exactly the two HTTPS URLs are required')
    if not caller:raise ValueError('Actual calling lane identity is unavailable')
    if is_worker(root,caller):raise ValueError('Native worker must continue the workflow, not bootstrap recursively')
    setup=workspace_setup(root)
    if setup.get('status')!='PASS' or setup.get('installation')!='INSTALLED':raise ValueError('Workspace installation is not confirmed ready')
    if not setup.get('native_observer',{}).get('enabled'):raise ValueError('Native observer is not installed in this workspace')
    from .native_setup import locate_codex_cli
    executable=locate_codex_cli()
    files=input_inventory(root)
    inputs={str(p):state._sha(p) for p in files}
    folder=root/'.vertigo/native';folder.mkdir(parents=True,exist_ok=True)
    with run_lock(folder):
        pointer=folder/'current.json'
        if pointer.exists():
            old=Path(read_json(pointer)['session']);last=old/'result.json'
            previous=_effective_result(old)
            if previous.get('status')=='UNKNOWN_OUTCOME' or (previous.get('status')=='BLOCKED' and (old/'launch.json').exists()):
                raise ValueError('Previous native outcome is unknown; reconcile without a duplicate dispatch')
            prior=read_json(old/'request.json') if (old/'request.json').exists() else {}
            identity={'workspace':str(root),'prompt':prompt,'model':model,'effort':effort,'owner_thread_id':caller,'inputs':inputs}
            if all(prior.get(k)==v for k,v in identity.items()):
                return {'status':'REPLAY','session':str(old),'result':previous}
        session=folder/uuid4().hex;session.mkdir(mode=0o700)
        data={'workspace':str(root),'prompt':prompt,'model':model,'effort':effort,'owner_thread_id':caller,
              'argv':[executable,'app-server','--listen','stdio://'],
              'inputs':inputs,'created_at':time.time()}
        write_json(session/'request.json',data);write_json(pointer,{'session':str(session)})
        launcher=Path(__file__).resolve().parents[1]/'proposition.py'
        child=subprocess.Popen([sys.executable,str(launcher),'native','serve','--session',str(session)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        ready=session/'session.json'
        if ready.exists():return read_json(ready)
        if child.poll() is not None:raise ValueError('Native bootstrap failed; inspect its session checkpoint')
        time.sleep(.05)
    raise ValueError('Observer startup outcome unknown; do not prepare a duplicate session')


def status(session,*,wait=0):
    folder=state._external_root(session);deadline=time.monotonic()+min(30,max(0,wait))
    while True:
        result=folder/'result.json'
        if result.exists() or (folder/'reconciliation.json').exists():return _effective_result(folder)
        if time.monotonic()>=deadline:
            progress=folder/'progress.json'
            return read_json(progress) if progress.exists() else {'status':'WAITING_FOR_PANEL_OPEN','session':str(folder)}
        time.sleep(.2)


def _effective_result(folder):
    original=(read_json(folder/'result.json') if (folder/'result.json').exists() else
              {'status':'UNKNOWN_OUTCOME','scope':'native_execution_not_business_quality','reason':'No final service receipt'})
    path=folder/'reconciliation.json'
    if not path.exists():return original
    recovered=read_json(path)
    try:
        if _reconciliation_inputs_match(folder,recovered.get('input_hashes',{})):
            return recovered['result']
    except (OSError,ValueError):pass
    return original


def _reconciliation_inputs_match(folder,hashes):
    return bool(hashes) and all((not (folder/name).exists()) if sha is None else
        state._sha(state._safe_path(folder,name))==sha for name,sha in hashes.items())


def reconcile(session,caller):
    """Read stored owned turns on a fresh transport; no resume or new turn."""
    from .native_host import AppServerClient
    from .native_launch import read_owned_turn
    from .native_activity import public_text
    folder=state._external_root(session)
    with run_lock(folder):
        request=read_json(folder/'request.json')
        if caller!=request['owner_thread_id']:raise ValueError('Reconciliation belongs to the owner lane')
        original=_effective_result(folder)
        if original['status']!='UNKNOWN_OUTCOME':return original
        result=dict(original,scope='native_execution_not_business_quality',business_quality='NOT_ASSESSED')
        names=('request.json','result.json','launch.json','lifecycle.json')
        if any(not (folder/name).exists() for name in ('launch.json','lifecycle.json')):
            return dict(result,reconciliation_error='Durable owned lifecycle evidence is missing')
        hashes={name:state._sha(folder/name) if (folder/name).exists() else None for name in names}
        launch=read_json(folder/'launch.json');ledger=read_json(folder/'lifecycle.json');owned=launch.get('receipt',{})
        agents=ledger.get('agents',[]);known={ledger.get('root_id')}
        if not owned.get('thread_id') or ledger.get('root_id')!=owned['thread_id'] or not agents or len(agents)>128 or agents[0].get('id')!=owned['thread_id']:
            return dict(result,reconciliation_error='Owned lifecycle root is missing or inconsistent')
        for agent in agents:
            if not agent.get('turn_id') or (agent['id']!=owned['thread_id'] and agent.get('parent_id') not in known):
                return dict(result,reconciliation_error='Descendant ownership or turn identity is incomplete')
            known.add(agent['id'])
        root=next((a for a in agents if a['id']==owned['thread_id']),{})
        if root.get('turn_id')!=owned.get('turn_id'):
            return dict(result,reconciliation_error='Owned root turn changed')
        observed=[];until=time.monotonic()+15
        try:
            with AppServerClient(argv=request['argv'],cwd=request['workspace']) as host:
                for agent in agents:
                    remaining=until-time.monotonic()
                    if remaining<=0:raise TimeoutError('Bounded reconciliation deadline exceeded')
                    observed.append(read_owned_turn(host,agent['id'],agent['turn_id'],timeout=remaining))
        except (ValueError,RuntimeError,OSError,TimeoutError) as error:
            return dict(result,reconciliation_error=public_text(str(error)))
        if any(a['status']=='UNKNOWN_OUTCOME' for a in observed):
            return dict(result,readback=observed)
        if not _reconciliation_inputs_match(folder,hashes):
            raise ValueError('Lifecycle changed during reconciliation; read the current session')
        outcome=dict(status=observed[0]['status'],scope='native_execution_not_business_quality',
            business_quality='NOT_ASSESSED',readback=observed,finished_at=time.time(),reconciled=True)
        write_json(folder/'reconciliation.json',{'input_hashes':hashes,'result':outcome})
        return outcome


def request_stop(session,caller):
    folder=state._external_root(session)
    if read_json(folder/'request.json')['owner_thread_id']!=caller:raise ValueError('STOP belongs to another calling lane')
    done=folder/'result.json'
    if done.exists():
        result=_effective_result(folder)
        return {'status':'RECONCILIATION_REQUIRED' if result['status']=='UNKNOWN_OUTCOME' else 'ALREADY_IDLE','result':result}
    target=state._no_symlinks(folder/'stop.json')
    # Cancellation must remain writable while dispatch holds its reservation.
    # O_EXCL creates one durable signal without replacing an existing request.
    try:fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,'O_NOFOLLOW',0),0o600)
    except FileExistsError:pass
    else:
        with os.fdopen(fd,'w') as out:json.dump({'requested_at':time.time()},out);out.flush();os.fsync(out.fileno())
    return {'status':'STOP_REQUESTED'}


def _terminal(agent):
    return agent.get('status') in ('COMPLETED','FAILED','INTERRUPTED','SHUTDOWN') and agent.get('ended_at') is not None


def serve(session):
    from .native_activity import NativeActivity,public_text
    from .native_host import AppServerClient
    from .native_launch import NativeLaunch
    from .native_observer import make_server
    folder=state._external_root(session);request=read_json(folder/'request.json')
    feed=NativeActivity(journal_dir=folder);server=make_server(feed)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    write_json(folder/'session.json',{'status':'WAITING_FOR_PANEL_OPEN','session':str(folder),
        'owner_thread_id':request['owner_thread_id'],'url':f'http://127.0.0.1:{server.server_port}/#'+server.token,
        'pid':os.getpid()})
    result={'status':'BLOCKED','scope':'native_execution_not_business_quality'};host=None
    def connection(value):
        with feed._lock:
            terminal=bool(feed.agents) and all(_terminal(a) for a in feed.agents.values())
        feed.connection(value,expected=(not value and terminal))
    try:
        until=time.monotonic()+120
        while not (folder/'panel-open.json').exists():
            if (folder/'stop.json').exists():raise ValueError('Stopped before any model turn')
            if time.monotonic()>=until:raise ValueError('Same-lane UI opening receipt is missing; no model turn started')
            time.sleep(.1)
        if (folder/'stop.json').exists():raise ValueError('Stopped before any model turn')
        if any(state._sha(Path(p))!=sha for p,sha in request['inputs'].items()):raise ValueError('Frozen startup inputs changed')
        with AppServerClient(argv=request['argv'],on_notification=feed.observe,on_connection=connection,cwd=request['workspace']) as host:
            launch=NativeLaunch(host,server,folder,workspace=request['workspace'],prompt=request['prompt'],
                model=request['model'],effort=request['effort'],inputs=request['inputs'],
                lane_id=request['owner_thread_id'],panel_open=read_json(folder/'panel-open.json'))
            started=launch.start();write_json(folder/'progress.json',started)
            until=time.monotonic()+max(0,request.get('created_at',time.time())+1200-time.time());last_progress=0;stopping=False
            while True:
                with feed._lock:
                    root=dict(feed.agents.get(started['thread_id'],{}))
                    children=[dict(a) for a in feed.agents.values() if a['id']!=started['thread_id']]
                if _terminal(root) and all(_terminal(a) for a in children):break
                if (folder/'stop.json').exists() or time.monotonic()>=until:
                    stopping=True;result['stop']=launch.stop()
                    break
                if not feed.connected:raise ValueError('Native source disconnected; execution outcome unknown')
                if time.monotonic()-last_progress>=2:
                    snapshot=feed.snapshot()
                    write_json(folder/'lifecycle.json',{'root_id':started['thread_id'],
                        'agents':[{k:a.get(k) for k in ('id','parent_id','turn_id','status','started_at','ended_at')} for a in snapshot['agents']]})
                    write_json(folder/'progress.json',{**started,'last_public_message':root.get('last_output',''),
                        'observed_agents':1+len(children),'observed_at':time.time()});last_progress=time.monotonic()
                time.sleep(.2)
            snapshot=feed.snapshot()
            unresolved=any(not _terminal(a) for a in snapshot['agents'])
            result.update(status='UNKNOWN_OUTCOME' if unresolved else 'INTERRUPTED' if stopping else root.get('status','UNKNOWN_OUTCOME'),launch=started,
                final_public_message=root.get('last_output',''),activity={'agents':snapshot['agents'],'metrics':snapshot['metrics']},
                business_quality='NOT_ASSESSED',diagnostics=sorted(host.diagnostics))
    except Exception as error:
        launch_record=read_json(folder/'launch.json') if (folder/'launch.json').exists() else {}
        with feed._lock:unfinished=any(not _terminal(a) for a in feed.agents.values())
        unknown=bool(host and host.outcome_unknown) or launch_record.get('state')=='TURN_INTENT' or unfinished
        result.update(status='UNKNOWN_OUTCOME' if unknown else 'INTERRUPTED' if (folder/'stop.json').exists() else 'BLOCKED',error=public_text(str(error)))
    finally:
        snapshot=feed.snapshot()
        result.update(activity=snapshot, business_quality='NOT_ASSESSED')
        write_json(folder/'lifecycle.json',{'root_id':feed.root_id,
            'agents':[{k:a.get(k) for k in ('id','parent_id','turn_id','status','started_at','ended_at')} for a in snapshot['agents']]})
        if (folder/'launch.json').exists():result['launch']=read_json(folder/'launch.json').get('receipt')
        result['finished_at']=time.time();write_json(folder/'result.json',result)
        # The model process is closed. Keep only the read-only observer briefly.
        until=time.monotonic()+600
        while time.monotonic()<until and not (folder/'close-view.json').exists():time.sleep(1)
        server.shutdown();server.server_close()
    return result
