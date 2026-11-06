"""Bounded public activity from a supported native host stream.

This is an observer, not a dispatcher or a business-quality validator. Unknown
sessions, reasoning items and arbitrary RPC payloads never enter the public feed.
"""
from collections import deque
from copy import deepcopy
import hashlib
import json
import math
import re
import threading
import time

MAX_TEXT = 4096
MAX_AGENTS = 128
MAX_ITEMS = 2048
_ID = re.compile(r'[A-Za-z0-9_.:-]{1,160}\Z')
_SECRET = re.compile(r'(?i)(authorization\s*:\s*(?:bearer\s+)?|bearer\s+|(?:api[_-]?key|access[_-]?token|password|secret)\s*[=:]\s*[\"\x27]?)([^\s\"\x27,;]+)')
_TOOLS = {'commandExecution', 'mcpToolCall', 'dynamicToolCall', 'webSearch', 'fileChange', 'collabAgentToolCall'}
_TERMINAL = {'COMPLETED', 'FAILED', 'INTERRUPTED', 'SHUTDOWN'}


def public_text(value):
    if not isinstance(value, str):
        return ''
    text = _SECRET.sub(lambda m: m[1]+'[redacted]', value[:MAX_TEXT*2])
    return text[:MAX_TEXT]


def _identity(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _status(value):
    return {'inProgress':'RUNNING', 'active':'RUNNING', 'running':'RUNNING',
            'pendingInit':'STARTING', 'idle':'IDLE', 'notLoaded':'NOT_LOADED',
            'completed':'COMPLETED', 'failed':'FAILED', 'errored':'FAILED',
            'systemError':'FAILED', 'interrupted':'INTERRUPTED', 'shutdown':'SHUTDOWN'}.get(value, 'UNKNOWN')


class NativeActivity:
    def __init__(self, *, clock=time.time):
        self.clock = clock
        self.root_id = None
        self.agents = {}
        self.tools = {}
        self.events = deque(maxlen=2000)
        self.cursor = 0
        self.connected = False
        self.disconnected_at = None
        self.diagnostics = set()
        self._messages = {}
        self._completed = {}
        self._lock = threading.RLock()

    def _event(self, kind, agent, now, *, item_id=None, text=None):
        self.cursor += 1
        event = {'seq':self.cursor, 'kind':kind, 'agent_id':agent['id'],
                 'parent_id':agent['parent_id'], 'turn_id':agent['turn_id'],
                 'observed_at':now, 'item_id':item_id}
        if text is not None:
            event['text'] = public_text(text)
        if len(self.events) == self.events.maxlen:
            self.diagnostics.add('EVENT_WINDOW_TRUNCATED')
        self.events.append(event)
        agent['last_activity_at'] = now

    def _register(self, thread_id, parent_id, now, *, role=None):
        if thread_id in self.agents:
            if self.agents[thread_id]['parent_id'] != parent_id:
                self.diagnostics.add('AGENT_PARENT_CONFLICT')
            return self.agents[thread_id]
        if not _identity(thread_id) or (parent_id is not None and parent_id not in self.agents):
            return None
        if len(self.agents) >= MAX_AGENTS:
            self.diagnostics.add('AGENT_BUDGET')
            return None
        row = {'id':thread_id, 'parent_id':parent_id, 'role':public_text(role)[:120] or None,
               'status':'IDLE', 'turn_id':None, 'started_at':None, 'ended_at':None,
               'last_activity_at':now, 'last_output':'', 'source':'codex_app_server'}
        self.agents[thread_id] = row
        self._event('agent.discovered', row, now)
        return row

    def bind_root(self, thread):
        with self._lock:
            identifier = thread.get('id')
            if not _identity(identifier) or thread.get('parentThreadId'):
                raise ValueError('A real root thread identity is required')
            if self.root_id and self.root_id != identifier:
                raise ValueError('Observer root is immutable')
            self.root_id = identifier
            row = self._register(identifier, None, self.clock(), role=thread.get('agentRole'))
            row['status'] = _status(thread.get('status', {}).get('type'))

    def connection(self, connected, *, expected=False):
        with self._lock:
            if self.connected and not connected:
                self.disconnected_at = self.clock()
                if not expected:self.diagnostics.add('HOST_STREAM_GAP')
            if connected:self.disconnected_at = None
            self.connected = bool(connected)

    def _output(self, agent, item_id, text, now, *, append):
        key = (agent['id'], item_id)
        if key not in self._messages and len(self._messages) >= MAX_ITEMS:
            self.diagnostics.add('PUBLIC_ITEM_BUDGET')
            return
        old = self._messages.get(key, '') if append else ''
        value = old + (text if isinstance(text, str) else '')
        if len(value) > MAX_TEXT*2:
            self.diagnostics.add('OUTPUT_PREVIEW_TRUNCATED')
        self._messages[key] = value[:MAX_TEXT*2]
        agent['last_output'] = public_text(self._messages[key])
        self._event('public.output', agent, now, item_id=item_id, text=agent['last_output'])

    def _tool(self, agent, item, now, *, complete):
        identifier = item.get('id')
        if not _identity(identifier):
            return
        key = agent['id']+':'+identifier
        if key not in self.tools and len(self.tools) >= MAX_ITEMS:
            self.diagnostics.add('TOOL_BUDGET')
            return
        label = item.get('tool') or item['type']
        row = self.tools.setdefault(key, {'id':identifier,'agent_id':agent['id'],
            'kind':item['type'],'label':public_text(label)[:120], 'status':'RUNNING',
            'started_at':now, 'ended_at':None, 'exit_code':None, 'business_status':None})
        if complete:
            row['status'] = _status(item.get('status'))
            row['ended_at'] = now
            row['exit_code'] = item.get('exitCode')
            output = item.get('aggregatedOutput')
            if item['type'] == 'commandExecution':
                if isinstance(output, str) and len(output) <= 1024*1024:
                    try:
                        result = json.loads(output)
                        if isinstance(result, dict) and result.get('status') in ('BLOCKED','ERROR','FAIL','FAILED'):
                            row['business_status'] = result['status']
                    except (ValueError, TypeError):
                        pass
                if row['business_status'] == 'BLOCKED':
                    row['status'] = 'BLOCKED'
                elif item.get('exitCode') not in (None, 0) or row['business_status'] in ('ERROR','FAIL','FAILED'):
                    row['status'] = 'FAILED'
            if isinstance(output, str) and output:
                self._output(agent, identifier, output, now, append=False)
            if item['type'] == 'collabAgentToolCall' and item.get('tool') == 'spawnAgent' and item.get('status') == 'completed':
                for child in item.get('receiverThreadIds', [])[:MAX_AGENTS]:
                    if child != agent['id']:
                        created = self._register(child, agent['id'], now)
                        if created:
                            state = item.get('agentsStates', {}).get(child, {}).get('status')
                            created['status'] = _status(state)
        self._event('tool.completed' if complete else 'tool.started', agent, now, item_id=identifier)

    def observe(self, notification, *, observed_at=None):
        with self._lock:
            now = self.clock() if observed_at is None else observed_at
            if not isinstance(now, (int, float)) or not math.isfinite(now):
                raise ValueError('Observation time must be finite')
            method = notification.get('method')
            params = notification.get('params', {})
            if not isinstance(params, dict):
                return
            if method == 'thread/started':
                thread = params.get('thread', {})
                parent = thread.get('parentThreadId')
                source = thread.get('source', {})
                if parent is None and isinstance(source, dict):
                    parent = source.get('subAgent', {})
                    parent = parent.get('thread_spawn', {}).get('parent_thread_id') if isinstance(parent, dict) else None
                if parent in self.agents:
                    self._register(thread.get('id'), parent, now, role=thread.get('agentRole'))
                return
            agent = self.agents.get(params.get('threadId'))
            if agent is None:
                return
            if method == 'thread/status/changed':
                value = _status(params.get('status', {}).get('type'))
                if value == 'IDLE' and agent['status'] in _TERMINAL:
                    # Idle describes the host after a turn, not that turn's
                    # outcome. Keep interruption/failure visible.
                    return
                if value != agent['status']:
                    agent['status'] = value
                    self._event('agent.status', agent, now)
            elif method in ('turn/started', 'turn/completed'):
                turn = params.get('turn', {})
                if not _identity(turn.get('id')):
                    return
                if method == 'turn/started':
                    agent.update(turn_id=turn['id'], status='RUNNING', started_at=now, ended_at=None)
                else:
                    agent.update(turn_id=turn['id'], status=_status(turn.get('status')), ended_at=now)
                    error = turn.get('error')
                    if isinstance(error, dict) and isinstance(error.get('message'), str):
                        self._output(agent, 'error-'+turn['id'], error['message'], now, append=False)
                self._event('turn.started' if method == 'turn/started' else 'turn.completed', agent, now)
            elif method == 'error':
                error = params.get('error')
                if isinstance(error, dict) and isinstance(error.get('message'), str):
                    self._output(agent, 'error-'+str(params.get('turnId','host')), error['message'], now, append=False)
            elif method in ('item/agentMessage/delta','item/commandExecution/outputDelta','item/mcpToolCall/progress'):
                identifier = params.get('itemId')
                if not _identity(identifier):
                    return
                self._output(agent, identifier, params.get('delta', params.get('message', '')), now, append=True)
            elif method in ('item/started','item/completed'):
                item = params.get('item', {})
                if not isinstance(item, dict) or item.get('type') not in _TOOLS|{'agentMessage','subAgentActivity'}:
                    return
                identifier = item.get('id')
                if not _identity(identifier):
                    return
                complete = method == 'item/completed'
                if complete:
                    # Final public content is authoritative; replayed completion
                    # must not append text or create another tool/activity row.
                    public = {k:item.get(k) for k in ('type','status','exitCode','text','aggregatedOutput','receiverThreadIds')}
                    digest = hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest()
                    key = (agent['id'], identifier)
                    if self._completed.get(key) == digest:
                        return
                    if len(self._completed) >= MAX_ITEMS and key not in self._completed:
                        self.diagnostics.add('COMPLETION_BUDGET')
                        return
                    self._completed[key] = digest
                if item['type'] == 'subAgentActivity':
                    # Current app-server emits this native item for collaboration
                    # starts. Its enclosing thread is the actual parent; the
                    # child identity is not reconstructed from a display name.
                    child_id = item.get('agentThreadId')
                    child = self.agents.get(child_id)
                    kind = item.get('kind')
                    if kind == 'started' and child_id != agent['id']:
                        child = self._register(child_id, agent['id'], now, role=item.get('agentPath'))
                        if child:
                            if child['started_at'] is None:child['started_at'] = now
                            if child['status'] == 'IDLE':child['status'] = 'STARTING'
                            child['model'] = public_text(item.get('model'))[:120] or None
                            child['effort'] = public_text(item.get('reasoningEffort'))[:40] or None
                    if child:
                        if kind in ('completed','interrupted') and child['status'] not in _TERMINAL:
                            child['status'] = 'COMPLETED' if kind == 'completed' else 'INTERRUPTED'
                            if child['ended_at'] is None:child['ended_at'] = now
                        self._event('agent.native.'+str(kind), child, now, item_id=identifier)
                elif item['type'] == 'agentMessage':
                    if complete:
                        self._output(agent, identifier, item.get('text',''), now, append=False)
                else:
                    self._tool(agent, item, now, complete=complete)

    def snapshot(self, *, now=None, after=0):
        with self._lock:
            now = self.clock() if now is None else now
            agents = deepcopy(list(self.agents.values()))
            tools = deepcopy(list(self.tools.values()))
            for row in agents+tools:
                start, end = row.get('started_at'), row.get('ended_at')
                horizon = end if end is not None else self.disconnected_at if self.disconnected_at is not None else now
                row['elapsed_seconds'] = max(0.0, horizon-start) if start is not None else None
                row['observation_status'] = 'OBSERVED_END' if end is not None else 'CONNECTED' if self.connected else 'SOURCE_UNAVAILABLE'
            return {'schema':'native-public-activity/1', 'root_id':self.root_id,
                    'status':self.agents[self.root_id]['status'] if self.root_id else 'WAITING_FOR_HOST',
                    'source_connected':self.connected, 'disconnected_at':self.disconnected_at, 'cursor':self.cursor,
                    'reset_required':bool(self.events and after < self.events[0]['seq']-1),
                    'agents':agents, 'tools':tools, 'events':[deepcopy(e) for e in self.events if e['seq']>after],
                    'diagnostics':sorted(self.diagnostics), 'business_quality':'NOT_ASSESSED',
                    'metrics':{'tools':len(tools), 'blocked':sum(t['status']=='BLOCKED' for t in tools),
                               'failed':sum(t['status']=='FAILED' for t in tools),
                               'failed_agents':sum(a['status']=='FAILED' for a in agents), 'tokens':None, 'cost':None}}
