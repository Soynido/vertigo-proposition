"""Owned Codex app-server stdio connection; no GUI or transcript scraping.

An instance sees the process it owns. It does not claim to attach to a separate
desktop/Cloud session. It never changes a global daemon, auth file or config.
"""
import json
import os
import queue
import subprocess
import threading
from .native_activity import public_text

MAX_LINE = 4*1024*1024
PUBLIC_NOTIFICATIONS = {
    'thread/started', 'thread/status/changed', 'turn/started', 'turn/completed',
    'item/started', 'item/completed', 'item/agentMessage/delta',
    'item/commandExecution/outputDelta', 'item/mcpToolCall/progress', 'error',
}
PRIVATE_NOTIFICATIONS = [
    'item/reasoning/textDelta', 'item/reasoning/summaryTextDelta',
    'item/reasoning/summaryPartAdded', 'rawResponseItem/completed',
]


class AppServerClient:
    def __init__(self, *, argv=None, on_notification=None, on_connection=None, cwd=None):
        self.argv = argv or ['codex','app-server','--listen','stdio://']
        self.on_notification = on_notification or (lambda event: None)
        self.on_connection = on_connection or (lambda connected: None)
        self._connected = False
        self.cwd = cwd
        self.process = None
        self.outcome_unknown = False
        self._pending = {}
        self._counter = 0
        self._lock = threading.RLock()
        self._reader = None
        self._stderr = None
        self._closed = False
        self.diagnostics = set()

    def __enter__(self):
        env = dict(os.environ)
        # Subscription auth only. Never silently switch to API billing because
        # the invoking shell happens to contain a provider key.
        for key in ('OPENAI_API_KEY','CODEX_API_KEY','ANTHROPIC_API_KEY'):
            env.pop(key, None)
        self.process = subprocess.Popen(self.argv, cwd=self.cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._stderr = threading.Thread(target=self._drain_errors, daemon=True)
        self._reader.start();self._stderr.start()
        try:
            self.request('initialize', {'clientInfo':{'name':'vertigo_observer','title':'VERTIGO observer','version':'1.0.0'},
                'capabilities':{'optOutNotificationMethods':PRIVATE_NOTIFICATIONS}}, timeout=15)
            self.notify('initialized', {})
            self._connection(True)
        except BaseException:
            self.close()
            raise
        return self

    def _connection(self, connected):
        with self._lock:
            if self._connected == connected:return
            self._connected = connected
        try:self.on_connection(connected)
        except Exception:self.diagnostics.add('OBSERVER_CALLBACK_FAILED')

    def _drain_errors(self):
        # Consume bounded chunks so a stderr pipe cannot deadlock the host.
        # Raw provider diagnostics can contain secrets and are never persisted.
        while self.process.stderr.read(4096):
            pass

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(MAX_LINE+1)
                if not line:
                    break
                if len(line) > MAX_LINE or not line.endswith(b'\n'):
                    self.diagnostics.add('HOST_MESSAGE_BUDGET')
                    self.outcome_unknown = True
                    # Keep draining the owned host's pipe. Stopping the reader
                    # would let a large image/log block the producer itself.
                    while line and not line.endswith(b'\n'):
                        line = self.process.stdout.readline(MAX_LINE+1)
                    continue
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError):
                    self.diagnostics.add('INVALID_HOST_MESSAGE')
                    continue
                if not isinstance(message, dict):
                    continue
                if 'id' in message and 'method' in message:
                    # This read-only observer cannot grant approvals or invent
                    # answers. An explicit refusal prevents an invisible wait.
                    self.diagnostics.add('HOST_INTERACTION_UNAVAILABLE')
                    self._send({'id':message['id'],'error':{'code':-32601,
                        'message':'Interactive host request unavailable in this transport; no approval granted'}})
                elif 'id' in message and ('result' in message or 'error' in message):
                    with self._lock:
                        pending = self._pending.get(message['id'])
                    if pending is not None:
                        pending.put(message)
                elif message.get('method') in PUBLIC_NOTIFICATIONS:
                    # No reasoning method or arbitrary notification is forwarded.
                    params = message.get('params', {})
                    item = params.get('item', {}) if isinstance(params, dict) else {}
                    if isinstance(item, dict) and item.get('type') == 'reasoning':
                        continue
                    try:self.on_notification(message)
                    except Exception:self.diagnostics.add('OBSERVER_CALLBACK_FAILED')
        except BaseException:
            self.diagnostics.add('HOST_STREAM_FAILED')
            self.outcome_unknown = True
        finally:
            self._connection(False)
            with self._lock:
                pending = list(self._pending.values())
                if pending and not self._closed:self.outcome_unknown=True
            for target in pending:
                target.put({'error':{'message':'Host connection closed'}})

    def _send(self, message):
        encoded = json.dumps(message,separators=(',',':')).encode()+b'\n'
        if len(encoded) > MAX_LINE:
            raise ValueError('Host request exceeds byte budget')
        with self._lock:
            if self._closed or not self.process or self.process.poll() is not None:
                raise RuntimeError('Host is not connected')
            self.process.stdin.write(encoded);self.process.stdin.flush()

    def notify(self, method, params):
        self._send({'method':method,'params':params})

    def request(self, method, params, *, timeout=15):
        with self._lock:
            if len(self._pending) >= 64:
                raise RuntimeError('Too many pending host requests')
            self._counter += 1
            identifier = str(self._counter)
            target = queue.Queue()
            self._pending[identifier] = target
        try:
            self._send({'id':identifier,'method':method,'params':params})
            try:
                response = target.get(timeout=timeout)
            except queue.Empty:
                self.outcome_unknown = True
                raise TimeoutError('Host response missing; outcome is unknown; reconcile before retry') from None
            if 'error' in response:
                error = response['error'] if isinstance(response['error'],dict) else {}
                code = error.get('code','unavailable')
                raise RuntimeError('Host request rejected: '+str(code)+' '+public_text(error.get('message',''))[:500])
            return response.get('result')
        finally:
            with self._lock:
                self._pending.pop(identifier, None)

    def close(self):
        with self._lock:
            self._closed = True
        if self.process is None:
            return
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill();self.process.wait(timeout=3)
        for worker in (self._reader,self._stderr):
            if worker is not None:
                worker.join(timeout=1)
        for stream in (self.process.stdout,self.process.stderr):
            if stream:
                stream.close()
        self._connection(False)

    def __exit__(self, *args):
        self.close()
