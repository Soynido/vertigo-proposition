"""Bounded local technical traces. No prompt, source text, URL or secret fields."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import functools
import hashlib
import inspect
from itertools import islice
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

MAX_EVENT_BYTES = 4096
MAX_EVENTS = 4096
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_FILES = 128
MAX_RUN_BYTES = 64 * 1024 * 1024
MAX_METRIC_EVENTS = 20000
ATTRIBUTES = {'count', 'bytes', 'files', 'captures', 'cache_hits', 'channel',
              'wait_kind', 'role', 'version', 'operation', 'command', 'file_id'}
NAMES = {'cli.command', 'validation.hash', 'reader.json', 'upstream.inspect',
         'research.prepare', 'research.validate', 'research.host', 'strategy.prepare',
         'strategy.validate', 'strategy.read', 'strategy.mission', 'channels.inspect',
         'discovery.inspect', 'discovery.collect', 'navigation.visit', 'navigation.scan',
         'navigation.image_wait', 'navigation.capture', 'evidence.write', 'transaction.commit',
         'export.pdf', 'export.font_wait', 'export.inspect', 'validation.session_hit'}
_current = ContextVar('proposition_trace', default=None)
_parent = ContextVar('proposition_span', default=None)


def _attributes(values):
    if any(k not in ATTRIBUTES for k in values):
        raise ValueError('Telemetry attribute is not allowlisted')
    for value in values.values():
        if type(value) is int and value >= 0:
            continue
        if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', value):
            continue
        raise ValueError('Telemetry attribute must be a counter or technical identifier')
    return values


class TraceRecorder:
    def __init__(self, root, *, max_events=MAX_EVENTS):
        if type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
            raise ValueError('Invalid telemetry event budget')
        self.root = Path(root)
        self.max_events = max_events
        self.trace_id = uuid.uuid4().hex
        self.process_id = uuid.uuid4().hex
        self.clock_domain_id = self.process_id
        self.path = None
        self.events = 0
        self.bytes = 0
        self.diagnostics = []

    def __enter__(self):
        from . import state
        try:
            root = state._external_root(self.root)
            folder = state._safe_path(root, 'telemetry', exists=False)
            folder.mkdir(exist_ok=True)
            total = 0
            files = list(islice(folder.iterdir(), MAX_FILES+1))
            if len(files) >= MAX_FILES-1:
                raise ValueError('Telemetry file budget reached')
            for path in files:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('Telemetry contains a non-regular file')
                total += info.st_size
            if total + MAX_FILE_BYTES > MAX_RUN_BYTES:
                raise ValueError('Telemetry run budget reached')
            self.path = folder / (self.process_id+'.jsonl')
            with self.path.open('x'):
                pass
        except (OSError, ValueError):
            self.diagnostics.append('TELEMETRY_UNAVAILABLE')
            self._partial()
            self.path = None
        self._token = _current.set(self)
        return self

    def __exit__(self, *_):
        _current.reset(self._token)

    def _partial(self):
        from . import state
        try:
            path = state._safe_path(state._external_root(self.root),'telemetry/coverage.partial',exists=False)
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os,'O_NOFOLLOW',0)
            fd = os.open(path,flags,0o600)
            with os.fdopen(fd,'wb') as output:
                output.write(b'partial\n')
        except (OSError,ValueError):
            pass

    def _write(self, event):
        if self.path is None:
            return
        encoded = (json.dumps(event, separators=(',', ':'))+'\n').encode()
        try:
            if (len(encoded) > MAX_EVENT_BYTES or self.events >= self.max_events
                    or self.bytes+len(encoded) > MAX_FILE_BYTES):
                self.diagnostics.append('TELEMETRY_BUDGET_REACHED')
                self._partial()
                self.path = None
                return
            flags = os.O_WRONLY | os.O_APPEND | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
            fd = os.open(self.path, flags)
            with os.fdopen(fd, 'ab') as output:
                if not stat.S_ISREG(os.fstat(output.fileno()).st_mode):
                    raise ValueError('Trace is not a regular file')
                output.write(encoded)
            self.events += 1
            self.bytes += len(encoded)
        except (OSError, ValueError):
            self.diagnostics.append('TELEMETRY_WRITE_FAILED')
            self._partial()
            self.path = None

    def _event(self, event, name, span_id, parent, attributes, status=None, error=None):
        self._write({'schema_version':'1.0', 'run_id':self.root.name,
                     'trace_id':self.trace_id, 'span_id':span_id, 'parent_span_id':parent,
                     'process_id':self.process_id, 'clock_domain_id':self.clock_domain_id,
                     'event':event, 'name':name,
                     'utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                     'monotonic_ns':time.monotonic_ns(), 'status':status,
                     'error_code':error, 'attributes':attributes})

    @contextmanager
    def span(self, name, **attributes):
        if name not in NAMES:
            raise ValueError('Unknown technical span')
        _attributes(attributes)
        identifier = uuid.uuid4().hex
        parent = _parent.get()
        self._event('start', name, identifier, parent, attributes)
        token = _parent.set(identifier)
        status = 'SUCCEEDED'; error = None
        try:
            yield
        except BaseException as failure:
            status = 'CANCELLED' if type(failure).__name__ in ('CancelledError','KeyboardInterrupt','SystemExit') else 'FAILED'
            error = type(failure).__name__[:64]
            raise
        finally:
            self._event('end', name, identifier, parent, attributes, status, error)
            _parent.reset(token)

    def counter(self, name, count=1, **attributes):
        if name not in NAMES or type(count) is not int or count < 0:
            raise ValueError('Invalid technical counter')
        attributes = _attributes({**attributes, 'count':count})
        self._event('counter', name, _parent.get(), _parent.get(), attributes)


def counter(name, count=1, **attributes):
    current = _current.get()
    if current is not None:
        current.counter(name, count, **attributes)


def file_read(name, path, size):
    if _current.get() is not None:
        counter(name, bytes=size, file_id=hashlib.sha256(str(Path(path).absolute()).encode()).hexdigest())


def traced(name):
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def async_call(*args, **kwargs):
                current = _current.get()
                if current is None:
                    return await function(*args, **kwargs)
                with current.span(name):
                    return await function(*args, **kwargs)
            return async_call
        @functools.wraps(function)
        def call(*args, **kwargs):
            current = _current.get()
            if current is None:
                return function(*args, **kwargs)
            with current.span(name):
                return function(*args, **kwargs)
        return call
    return decorate


def _union(intervals):
    end = None; total = 0
    for start, stop in sorted(intervals):
        total += max(0, stop-max(start, end if end is not None else start))
        end = max(end if end is not None else stop, stop)
    return total / 1e9


def metrics(root):
    """Read a bounded inventory without changing a run or creating telemetry."""
    from . import state
    root = state._external_root(root)
    folder = state._safe_path(root, 'telemetry', exists=False)
    result = {'schema_version':'1.0', 'run_id':root.name, 'coverage':'unavailable',
              'command_sessions':[], 'milestones':[], 'work_seconds':None,
              'wait_seconds':None, 'instrumented_union_seconds':None,
              'unique_files_hashed':None, 'repeated_operations':{}, 'counters':{},
              'trace_errors':[], 'tokens_used':None, 'account_tokens_remaining':None}
    if not folder.exists():
        return result
    if not folder.is_dir():
        result.update(coverage='partial',trace_errors=['INVALID_TELEMETRY_DIRECTORY'])
        return result
    spans = {}; ended = {}; domains = {}; total = 0; events = 0; hashed = set()
    paths = sorted(islice(folder.iterdir(), MAX_FILES+1))
    if len(paths) > MAX_FILES:
        result['trace_errors'].append('TELEMETRY_FILE_BUDGET')
    for path in paths[:MAX_FILES]:
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                raise ValueError('Invalid trace file')
            if path.suffix == '.partial':
                raise ValueError('Telemetry budget reached')
            if path.suffix != '.jsonl':
                raise ValueError('Unknown trace entry')
            total += info.st_size
            if total > MAX_RUN_BYTES:
                raise ValueError('Telemetry byte budget reached')
            flags = os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0)
            with os.fdopen(os.open(path, flags), 'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError('Trace must be a regular file')
                for line in iter(lambda: stream.readline(MAX_EVENT_BYTES+1), b''):
                    events += 1
                    if events > MAX_METRIC_EVENTS or len(line) > MAX_EVENT_BYTES:
                        raise ValueError('Telemetry event budget reached')
                    event = json.loads(line)
                    keys = {'schema_version','run_id','trace_id','span_id','parent_span_id',
                            'process_id','clock_domain_id','event','name','utc','monotonic_ns',
                            'status','error_code','attributes'}
                    if (not isinstance(event,dict) or set(event) != keys
                            or event.get('schema_version') != '1.0' or event.get('name') not in NAMES
                            or event.get('run_id') != root.name or not isinstance(event.get('attributes'),dict)):
                        raise ValueError('Invalid trace event')
                    for key in ('trace_id','process_id','clock_domain_id','utc'):
                        if not isinstance(event[key],str) or not event[key]:
                            raise ValueError('Invalid trace identity')
                    if datetime.fromisoformat(event['utc'].replace('Z','+00:00')).tzinfo is None:
                        raise ValueError('Trace needs a dated clock domain')
                    if event['status'] not in (None,'SUCCEEDED','FAILED','CANCELLED'):
                        raise ValueError('Invalid technical status')
                    _attributes(event['attributes'])
                    if type(event['monotonic_ns']) is not int or event['monotonic_ns'] < 0:
                        raise ValueError('Invalid monotone clock')
                    domain = (event['process_id'],event['clock_domain_id'],event['trace_id'])
                    key = (*domain,event['span_id'])
                    if event['event'] == 'start':
                        if key in spans: raise ValueError('Duplicate span start')
                        spans[key] = event
                    elif event['event'] == 'end':
                        if key in ended: raise ValueError('Duplicate span end')
                        ended[key] = event
                    elif event['event'] == 'counter':
                        name = event['name']; values = result['counters']
                        values[name] = values.get(name,0)+event['attributes']['count']
                        if name == 'validation.hash' and event['attributes'].get('file_id'):
                            hashed.add(event['attributes']['file_id'])
                    else:
                        raise ValueError('Invalid trace event kind')
        except (OSError,ValueError,KeyError,TypeError):
            result['trace_errors'].append('INVALID_OR_PARTIAL_TRACE')
    if set(spans) != set(ended):
        result['trace_errors'].append('INCOMPLETE_SPAN')
    children = {(key[:3],event['parent_span_id']) for key,event in spans.items() if event['parent_span_id']}
    work = 0; wait_domains = {}; names = {}
    for key, start in sorted(spans.items()):
        end = ended.get(key)
        if not end: continue
        if end['name'] != start['name'] or end['monotonic_ns'] < start['monotonic_ns']:
            result['trace_errors'].append('MISMATCHED_SPAN');continue
        interval = (start['monotonic_ns'],end['monotonic_ns'])
        domains.setdefault(key[:3],[]).append(interval)
        names[start['name']] = names.get(start['name'],0)+1
        duration = (interval[1]-interval[0])/1e9
        if (key[:3],key[3]) not in children:
            work += duration
        if 'wait' in start['name']:
            wait_domains.setdefault(key[:3],[]).append(interval)
        if start['parent_span_id'] is None:
            result['command_sessions'].append({'trace_id':key[2], 'process_id':key[0],
                'clock_domain_id':key[1], 'wall_seconds':duration,
                'instrumented_union_seconds':None, 'status':end['status']})
    result['coverage'] = 'partial' if result['trace_errors'] or len(domains)>1 else 'complete' if spans else 'unavailable'
    result['work_seconds'] = work if domains else None
    result['wait_seconds'] = sum(_union(v) for v in wait_domains.values()) if wait_domains else None
    result['instrumented_union_seconds'] = _union(next(iter(domains.values()))) if len(domains)==1 and not result['trace_errors'] else None
    for session in result['command_sessions']:
        domain = (session['process_id'],session['clock_domain_id'],session['trace_id'])
        session['instrumented_union_seconds'] = _union(domains[domain]) if domain in domains else None
    result['repeated_operations'] = {k:v for k,v in names.items() if v>1}
    result['repeated_operations'].update({k:v for k,v in result['counters'].items() if v>1})
    result['unique_files_hashed'] = len(hashed) if hashed else None
    return result
