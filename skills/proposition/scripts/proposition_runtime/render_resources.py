"""Bounded public render dependencies, fetched at validated literal addresses.

This is not cross-origin navigation. No cookies, credentials, forms, frames,
XHR or video are forwarded. Redirects stay refused and TLS verifies the host.
"""
import asyncio
import hashlib
import http.client
import ipaddress
import socket
import ssl
import sys
import json
import os
import threading
from pathlib import Path
import time
from urllib.parse import urlsplit,urlunsplit
if __package__:
    from . import discovery as d
else:
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    from proposition_runtime import discovery as d

_TYPES={'script','stylesheet','font','image'}
_MAX_BYTES=4*1024*1024


def _fetch(url,allow_local):
    url=d._url(url,allow_local=allow_local,resolve=False);p=urlsplit(url)
    addresses={row[4][0] for row in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global and not (allow_local and ipaddress.ip_address(a).is_loopback) for a in addresses):
        raise ValueError('Non-public render dependency')
    address=sorted(addresses,key=lambda a:(ipaddress.ip_address(a).version,a))[0]
    connection=http.client.HTTPConnection(address,p.port or (443 if p.scheme=='https' else 80),timeout=3)
    until=time.monotonic()+3
    try:
        connection.connect()
        if p.scheme=='https':connection.sock=ssl.create_default_context().wrap_socket(connection.sock,server_hostname=p.hostname)
        connection.request('GET',urlunsplit(('','',p.path or '/',p.query,'')),headers={'Host':p.netloc,'User-Agent':'VERTIGO-Public-Render/1'})
        response=connection.getresponse()
        if response.status!=200:raise ValueError('Render dependency HTTP '+str(response.status)+'; redirects are not followed')
        body=bytearray()
        while len(body)<=_MAX_BYTES:
            remaining=until-time.monotonic()
            if remaining<=0:raise TimeoutError('Render dependency deadline exceeded')
            if connection.sock:connection.sock.settimeout(remaining)
            block=response.read1(min(65536,_MAX_BYTES+1-len(body)))
            if not block:break
            body.extend(block)
        if len(body)>_MAX_BYTES:raise ValueError('Render dependency byte budget exceeded')
        headers={k:v for k,v in response.getheaders() if k.lower() in ('content-type','access-control-allow-origin')}
        return bytes(body),headers
    finally:connection.close()


class RenderResources:
    def __init__(self,allow_local):
        self.allow_local=allow_local;self.tasks={};self.records={};self.bytes=0
        self.slots=asyncio.Semaphore(2)

    async def get(self,url,kind):
        if kind not in _TYPES:raise ValueError('cross_origin_request')
        url=d._url(url,allow_local=self.allow_local,resolve=False)
        if url in self.tasks:return await asyncio.shield(self.tasks[url])
        if len(self.tasks)>=64 or self.bytes+_MAX_BYTES>16*1024*1024:
            raise ValueError('Render resource collection budget exceeded')
        async def fetch():
            async with self.slots:
                process=await asyncio.create_subprocess_exec(sys.executable,str(Path(__file__).resolve()),url,
                    'fixture' if self.allow_local else 'public',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
                try:output,_=await asyncio.wait_for(process.communicate(),5)
                except BaseException:
                    if process.returncode is None:process.kill()
                    await process.wait();raise
                if process.returncode:raise ValueError('Public render dependency unavailable')
                metadata,separator,body=output.partition(b'\n')
                if not separator or len(metadata)>4096 or len(body)>_MAX_BYTES:raise ValueError('Invalid render worker response')
                headers=json.loads(metadata)
            if self.bytes+len(body)>16*1024*1024:raise ValueError('Render resource collection budget exceeded')
            self.bytes+=len(body)
            p=urlsplit(url);safe=urlunsplit((p.scheme,p.netloc,p.path,'',''))
            self.records[url]={'url':safe,'kind':kind,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'status':'fetched'}
            return body,headers
        self.tasks[url]=asyncio.create_task(fetch())
        return await asyncio.shield(self.tasks[url])


if __name__=='__main__':
    # Also bound the worker if its parent is terminated before it can cancel.
    watchdog=threading.Timer(5,lambda:os._exit(124));watchdog.daemon=True;watchdog.start()
    try:
        body,headers=_fetch(sys.argv[1],sys.argv[2]=='fixture')
        sys.stdout.buffer.write(json.dumps(headers).encode()+b'\n'+body)
    finally:watchdog.cancel()
