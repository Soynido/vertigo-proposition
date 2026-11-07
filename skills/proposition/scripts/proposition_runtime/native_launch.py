"""Guard one owned native execution. This module does not open a Desktop panel.

The calling lane must open its own observer and supply the native panel receipt.
Queued placement is legitimate: rendering is observed, not human approval.
An owned app-server is never treated as an attachment to another running host.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import re
from urllib.parse import urlsplit

from .transactions import run_lock
from .state import _no_symlinks


def _hash(path):
    path=_no_symlinks(Path(path))
    if not path.is_file() or path.stat().st_size>4*1024*1024:
        raise ValueError('Launch input must be a bounded regular file')
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeLaunch:
    def __init__(self,host,observer,session,*,workspace,prompt,model,effort,inputs,lane_id,panel_open):
        lines=prompt.splitlines()
        if len(lines)!=2 or any(line!=line.strip() or not urlsplit(line).hostname
                              or urlsplit(line).scheme!='https' for line in lines):
            raise ValueError('Launch input must contain exactly the two HTTPS URLs')
        self.host=host;self.observer=observer;self.prompt=prompt
        self.lane_id=lane_id;self.panel_open=panel_open
        self.workspace=_no_symlinks(Path(workspace).absolute())
        self.session=_no_symlinks(Path(session).absolute())
        self.session.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.path=self.session/'launch.json'
        self.model=model;self.effort=effort
        if not inputs or len(inputs)>256:raise ValueError('Installed input inventory is required')
        self.inputs=({str(Path(p).absolute()):sha for p,sha in inputs.items()} if isinstance(inputs,dict) else
                     {str(Path(p).absolute()):_hash(Path(p).absolute()) for p in inputs})
        if any(not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha) for sha in self.inputs.values()):
            raise ValueError('Invalid prepared input hash')
        self.key=hashlib.sha256(json.dumps({'prompt':prompt,'model':model,'effort':effort,
            'workspace':str(self.workspace),'lane_id':self.lane_id,'inputs':self.inputs},sort_keys=True).encode()).hexdigest()

    def _read(self):
        if not self.path.exists():return None
        _no_symlinks(self.path)
        if self.path.stat().st_size>1024*1024:raise ValueError('Launch receipt exceeds budget')
        result=json.loads(self.path.read_text())
        if result.get('key')!=self.key:raise ValueError('Session belongs to different frozen inputs')
        return result

    def _write(self,data):
        fd,name=tempfile.mkstemp(prefix='.launch-',dir=self.session)
        try:
            with os.fdopen(fd,'w') as stream:
                json.dump(data,stream,ensure_ascii=False,sort_keys=True);stream.write('\n')
                stream.flush();os.fsync(stream.fileno())
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def _ready(self):
        if (self.session/'stop.json').exists():raise ValueError('Stopped before native dispatch')
        if not isinstance(self.panel_open,dict) or not self.lane_id or self.panel_open.get('threadId')!=self.lane_id or self.panel_open.get('status') not in ('opened','queued'):
            raise ValueError('UI opening must be accepted in the calling lane before execution')
        if not self.observer.feed.connected:raise ValueError('Native source must connect before execution')
        if getattr(self.host,'outcome_unknown',False):raise ValueError('Host outcome unknown; reconcile before execution')
        if any(_hash(p)!=expected for p,expected in self.inputs.items()):
            raise ValueError('Installed input changed before execution')

    def start(self,*,timeout=15):
        with run_lock(self.session):
            prior=self._read()
            if prior:
                if prior['state']=='RUNNING':return prior['receipt']
                raise ValueError('Launch outcome unknown or already reserved; reconcile without dispatching again')
            self._ready()
            account=self.host.request('account/read',{'refreshToken':False},timeout=timeout)
            if (account.get('account') or {}).get('type')!='chatgpt':
                raise ValueError('ChatGPT subscription authentication required')
            models=self.host.request('model/list',{'includeHidden':True},timeout=timeout)
            available=next((m for m in models.get('data',[]) if m.get('model')==self.model),None)
            if not available or self.effort not in [x.get('reasoningEffort') for x in available.get('supportedReasoningEfforts',[])]:
                raise ValueError('Exact requested model and effort are unavailable')
            record={'key':self.key,'state':'THREAD_INTENT','created_at':time.time(),
                    'inputs':self.inputs,'prompt_sha256':hashlib.sha256(self.prompt.encode()).hexdigest()}
            self._write(record)
            result=self.host.request('thread/start',{'cwd':str(self.workspace),'model':self.model,
                # Preserve the user's effective host policy, including managed
                # restrictions. The observer grants no execution permissions.
                'config':{'model_reasoning_effort':self.effort},
                'ephemeral':False},timeout=timeout)
            result_policy={'approval_policy':result.get('approvalPolicy'),'sandbox':result.get('sandbox')}
            thread=result['thread'];record['thread_id']=thread['id'];self._write(record)
            if result.get('model')!=self.model or result.get('reasoningEffort')!=self.effort:
                raise ValueError('Host resolved a different model or effort')
            instructions={str(Path(p).absolute()) for p in result.get('instructionSources',[])}
            entry=str(self.workspace/'AGENTS.md')
            if entry not in self.inputs or entry not in instructions:
                raise ValueError('Installed workspace instructions were not loaded')
            if not instructions.issubset(self.inputs):
                raise ValueError('Loaded instructions are missing from the frozen input inventory')
            self._ready()
            self.observer.feed.bind_root(thread)
            record['state']='TURN_INTENT';self._write(record)
            result=self.host.request('turn/start',{'threadId':thread['id'],
                'input':[{'type':'text','text':self.prompt,'text_elements':[]}],
                'model':self.model,'effort':self.effort},timeout=timeout)
            receipt={'status':'RUNNING','thread_id':thread['id'],'turn_id':result['turn']['id'],
                'model':self.model,'effort':self.effort,'prompt_sha256':record['prompt_sha256'],
                'execution_policy':result_policy,
                'instruction_sources':sorted(instructions),'ui_ready_at':self.observer.ui_ready_at,
                'panel_open':{'threadId':self.lane_id,'status':self.panel_open['status']}}
            record.update(state='RUNNING',receipt=receipt);self._write(record)
            return receipt

    def reconcile(self,*,timeout=15):
        """Read the owned durable turn; never resume, dispatch or interrupt it."""
        record=self._read();receipt=(record or {}).get('receipt')
        if not receipt:
            return {'status':'UNKNOWN_OUTCOME','reason':'Owned turn identity is missing'}
        return read_owned_turn(self.host,receipt['thread_id'],receipt['turn_id'],timeout=timeout)

    def stop(self,*,timeout=15):
        with run_lock(self.session):
            record=self._read()
            if not record or not record.get('receipt'):
                raise ValueError('Launch outcome unknown; no owned turn available to stop')
            if record.get('stop_receipt'):return record['stop_receipt']
            receipt=record['receipt'];thread_id=receipt['thread_id']
            current=self.host.request('thread/read',{'threadId':thread_id,'includeTurns':False},timeout=timeout)
            status=current['thread']['status']['type']
            if status=='idle':
                observed=self.reconcile(timeout=timeout)
                if observed['status']=='UNKNOWN_OUTCOME':
                    raise ValueError('Host idle without a terminal owned turn; outcome remains unknown')
                result={'status':'ALREADY_IDLE','thread_id':thread_id,'turn_id':receipt['turn_id']}
            elif status=='active':
                turn=_latest_turn(self.host,thread_id,timeout=timeout)
                if turn.get('id')!=receipt['turn_id'] or turn.get('status')!='inProgress':
                    raise ValueError('Active turn is not the owned turn; refusing interruption')
                if record.get('stop_intent'):
                    raise ValueError('Stop outcome unknown; readback has not confirmed completion')
                record['stop_intent']=time.time();self._write(record)
                self.host.request('turn/interrupt',{'threadId':thread_id,'turnId':receipt['turn_id']},timeout=timeout)
                until=time.monotonic()+timeout
                while True:
                    observed=self.reconcile(timeout=max(.1,until-time.monotonic()))
                    if observed['status'] in ('COMPLETED','INTERRUPTED','FAILED'):break
                    if time.monotonic()>=until:
                        raise ValueError('Stop requested; completion remains unconfirmed')
                    time.sleep(.05)
                result={'status':'STOP_CONFIRMED','thread_id':thread_id,'turn_id':receipt['turn_id']}
            else:
                raise ValueError('Native thread state unknown; refusing an inferred STOP')
            record['stop_receipt']=result;self._write(record);return result


def _latest_turn(host,thread_id,*,timeout=15):
    try:
        turns=host.request('thread/turns/list',{'threadId':thread_id,'limit':1,
            'itemsView':'notLoaded','sortDirection':'desc'},timeout=timeout).get('data',[])
    except RuntimeError as error:
        if 'Host request rejected: -32601 list_turns is not supported yet' not in str(error):raise
        # Pinned 0.167 legacy threads expose metadata only through this RPC.
        # Never retain, inspect or forward item contents (including reasoning).
        raw=host.request('thread/read',{'threadId':thread_id,'includeTurns':True},timeout=timeout)['thread']
        if raw.get('id')!=thread_id:return {}
        turns=raw.get('turns',[])[-1:]
    return {k:turns[0].get(k) for k in ('id','status')} if turns else {}


def read_owned_turn(host,thread_id,turn_id,*,timeout=15):
    """A bounded metadata read, including from a new transport after a crash."""
    current=host.request('thread/read',{'threadId':thread_id,'includeTurns':False},timeout=timeout)['thread']
    turn=_latest_turn(host,thread_id,timeout=timeout)
    result={'status':'UNKNOWN_OUTCOME','thread_id':thread_id,'turn_id':turn_id}
    if current.get('id')!=thread_id or turn.get('id')!=turn_id:
        return dict(result,reason='Latest turn does not match the owned turn')
    status={'completed':'COMPLETED','interrupted':'INTERRUPTED','failed':'FAILED'}.get(turn.get('status'))
    if status and current.get('status',{}).get('type') in ('idle','notLoaded','systemError'):
        result['status']=status
    return result
