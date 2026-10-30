"""Command-local stable read phases, never a persistent trust cache."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from itertools import chain
import functools
import hashlib
import json
from pathlib import Path
import stat

from .telemetry import counter

_active = ContextVar('proposition_validation', default=None)


def _identity(path, *, directory=False):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('Validation refuses symbolic links')
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('Validation input must be a regular file or declared directory')
    return (info.st_dev,info.st_ino,info.st_mode,info.st_size,info.st_mtime_ns,info.st_ctime_ns)


class ValidationSession:
    def __init__(self, *, max_bytes=8*1024*1024):
        if type(max_bytes) is not int or not 1 <= max_bytes <= 32*1024*1024:
            raise ValueError('Invalid validation cache budget')
        self.max_bytes = max_bytes
        self.cached_bytes = 0
        self.files = {}
        self.trees = {}
        self.values = {}

    def __enter__(self):
        if _active.get() is not None:
            raise ValueError('Nested validation phases must reuse the active session')
        self.token = _active.set(self)
        return self

    def __exit__(self, kind, *_):
        try:
            if kind is None:
                self.verify()
        finally:
            self.invalidate()
            _active.reset(self.token)

    def observe(self, path):
        path = Path(path).absolute()
        identity = _identity(path)
        previous = self.files.get(path)
        if previous is not None and previous != identity:
            raise ValueError('Validation input changed during the stable phase')
        self.files[path] = identity
        if len(self.files)>20000:
            raise ValueError('Validation file inventory budget reached')
        return path

    def watch_tree(self, path):
        path = Path(path).absolute()
        if not path.exists():
            inventory = None
        else:
            inventory = []
            for index, item in enumerate(chain([path],path.rglob('*'))):
                if index > 20000:
                    raise ValueError('Validation tree exceeds the inventory budget')
                directory = item.is_dir()
                inventory.append((str(item.relative_to(path)), _identity(item,directory=directory)))
            inventory = tuple(sorted(inventory))
        if path in self.trees and self.trees[path] != inventory:
            raise ValueError('Method inventory changed during the stable phase')
        self.trees[path] = inventory

    def verify(self):
        try:
            for path, identity in self.files.items():
                if _identity(path) != identity:
                    raise ValueError('Validation input changed during the stable phase')
            for path in tuple(self.trees):
                self.watch_tree(path)
        except OSError as error:
            raise ValueError('Validation input disappeared during the stable phase') from error

    def invalidate(self):
        self.files.clear();self.trees.clear();self.values.clear()
        self.cached_bytes = 0

    def store(self, key, value):
        size = len(value) if isinstance(value,bytes) else len(json.dumps(value,ensure_ascii=False).encode())
        if len(self.values)<4096 and self.cached_bytes+size<=self.max_bytes:
            self.values[key] = deepcopy(value)
            self.cached_bytes += size

    def read(self, path, mode, loader):
        path = self.observe(path)
        key = ('file',mode,str(path))
        if key not in self.values:
            value = loader()
            self.observe(path)
            self.store(key,value)
            return value
        else:
            counter('validation.session_hit')
        return self.values[key]

    def memo(self, key, loader):
        self.verify()
        if key not in self.values:
            value = loader()
            self.verify()
            self.store(key,value)
            return deepcopy(value)
        else:
            counter('validation.session_hit')
        return deepcopy(self.values[key])


def invalidate():
    session = _active.get()
    if session is not None:
        session.invalidate()


def commit_guard():
    """Freeze the read inventory outside the lock; only stat checks at commit."""
    session=_active.get()
    if session is None:return lambda:None
    session.verify()
    entries={(path,False):identity for path,identity in session.files.items()}
    absent=[]
    for root,inventory in session.trees.items():
        if inventory is None:absent.append(root);continue
        for relative,identity in inventory:
            entries[(root/relative,stat.S_ISDIR(identity[2]))]=identity
    def verify():
        for (path,directory),identity in entries.items():
            if _identity(path,directory=directory)!=identity:raise ValueError('Validation input changed before commit')
        if any(path.exists() or path.is_symlink() for path in absent):raise ValueError('Validation inventory changed before commit')
    return verify


def file_hash(path, loader):
    session = _active.get()
    return loader() if session is None else session.read(path, 'sha256', loader)


def file_reader(limit, *, mode):
    def decorate(function):
        @functools.wraps(function)
        def call(path):
            session = _active.get()
            if session is None:
                return function(path)
            return session.read(path,(mode,limit),lambda:function(path))
        return call
    return decorate


def _normal(value):
    if isinstance(value,Path): return str(value.absolute())
    if isinstance(value,dict): return {k:_normal(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_normal(v) for v in value]
    return value


def cached(name, *, tree=False):
    def decorate(function):
        @functools.wraps(function)
        def call(*args, **kwargs):
            session = _active.get()
            if session is None:
                return function(*args, **kwargs)
            if tree:
                spec,root = args
                session.watch_tree(Path(root)/spec['id']/spec['commit'])
            encoded = json.dumps(_normal([args,kwargs]),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            key = ('result',name,hashlib.sha256(encoded).hexdigest())
            return session.memo(key,lambda:function(*args,**kwargs))
        return call
    return decorate


def phase(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        if _active.get() is not None:
            return function(*args, **kwargs)
        with ValidationSession():
            return function(*args, **kwargs)
    return call


def fresh_phase(function):
    @functools.wraps(function)
    def call(*args, **kwargs):
        previous = _active.get()
        if previous is not None:
            previous.invalidate()
        token = _active.set(None)
        try:
            with ValidationSession():
                return function(*args, **kwargs)
        finally:
            _active.reset(token)
            if previous is not None:
                previous.invalidate()
    return call
