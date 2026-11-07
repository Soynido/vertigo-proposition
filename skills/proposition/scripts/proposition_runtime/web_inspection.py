"""Observe the actual isolated web build. Never infer a creative or client verdict."""
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import re
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

from . import web


@contextmanager
def serve_bundle(directory, manifest):
    public = Path(directory)/'.vercel/output/static'
    files = {str(p.relative_to(public)):p for p in public.rglob('*') if p.is_file()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != host:
                self.send_error(403); return
            name = unquote(urlsplit(self.path).path).lstrip('/') or manifest['entrypoint']
            file = files.get(name)
            if file is None or file.is_symlink():
                self.send_error(404); return
            size=file.stat().st_size;start=0;end=size-1
            requested=self.headers.get('Range')
            if requested:
                match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
                valid=bool(match and any(match.groups()) and size)
                if valid:
                    first,last=match.groups()
                    if first:
                        start=int(first);end=min(size-1,int(last)) if last else size-1
                    else:
                        suffix=int(last);valid=suffix>0;start=max(0,size-suffix)
                    valid=valid and 0<=start<=end<size
                if not valid:
                    self.send_response(416);self.send_header('Content-Range',f'bytes */{size}')
                    self.send_header('Content-Length','0');self.end_headers();return
            self.send_response(206 if requested else 200)
            self.send_header('Accept-Ranges','bytes')
            if requested:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(end-start+1))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            with file.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                try:
                    while remaining:
                        chunk=stream.read(min(65536,remaining))
                        if not chunk:break
                        self.wfile.write(chunk);remaining-=len(chunk)
                except (BrokenPipeError,ConnectionResetError):pass

    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)


def inspect_bundle(directory, plan, output, *, browsers=('chromium','webkit'),
                   viewports=((1440,900),(1280,600),(390,844)), origin=None):
    from playwright.sync_api import sync_playwright
    from .browser import launch_browser
    manifest = web.verify_bundle(directory)
    if origin is not None:
        address=urlsplit(origin)
        if (address.username or address.password or address.path or address.query or address.fragment
                or address.scheme not in ('http','https')
                or (address.scheme=='http' and address.hostname!='127.0.0.1')):
            raise ValueError('Inspection origin must be HTTPS or an explicit loopback fixture')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Inspection destination must be new')
    output.mkdir(parents=True)
    report = {'version':1,'build_id':manifest['build_id'],'scope':'observed_browser_mechanics_only',
              'creative_quality':'NOT_ASSESSED','independent_review':'NOT_RUN',
              'inspector_sha256':web._sha(Path(__file__)),
              'browsers':[], 'pages':[], 'captures':[], 'scenes':[], 'coverage':[], 'media':[], 'actions':[], 'issues':[]}

    def issue(code, detail, context=None):
        if len(report['issues']) < 100:
            row={'code':code,'detail':str(detail)[:500]}
            if context:row['context']=context
            report['issues'].append(row)

    def capture(browser_page, name, viewport, **details):
        file=output/(name+'-'+str(len(report['captures']))+'.jpg')
        # Fast-forwarding finite animations also changes paused scroll timelines.
        # Capture the actual requested state; never substitute the effect's end.
        browser_page.screenshot(path=str(file),type='jpeg',quality=80,animations='allow')
        report['captures'].append(dict(path=file.name,sha256=web._sha(file),
            viewport=list(viewport),actual_viewport=browser_page.evaluate('([innerWidth,innerHeight])'),**details))

    def inspect_media(document, key):
        for image in document.locator('img').all():
            try:
                if image.is_visible():image.scroll_into_view_if_needed()
                image.evaluate('(img)=>img.decode()')
            except Exception:issue('image_decode',image.get_attribute('src'),key)
        for video in document.locator('video').all():
            try:
                if video.is_visible():video.scroll_into_view_if_needed()
                video.evaluate('''async v => {v.muted=true;v.preload='auto';await v.play();}''')
                video.evaluate('async v => { const until=Date.now()+4000; while(v.currentTime<=0 || v.readyState<2){if(v.error || Date.now()>until)throw new Error("Video did not decode"); await new Promise(r=>setTimeout(r,50));}}')
                sample=video.evaluate('(v)=>({src:v.currentSrc,time:v.currentTime,ready_state:v.readyState,error:v.error?.code||null})')
                video.evaluate('(v)=>v.pause()')
                if sample['error'] or sample['time']<=0:issue('video_decode',sample,key)
                report['media'].append(dict(sample,context=key,muted_for_decode_probe=True))
            except Exception as error:issue('video_decode',error,key)

    def inspect_action(page, action, key, expected_action, navigations):
        locator=page.locator(action['selector'])
        if locator.count()!=1 or not locator.is_visible():
            issue('missing_action',action['id'],key);return
        if locator.get_attribute('href')!=action['target']:
            issue('action_target',action['id'],key);return
        eligible=locator.evaluate('(n)=>n.tabIndex>=0 && !n.closest(\'[inert],[disabled],[aria-disabled="true"]\')')
        if not eligible:
            issue('action_keyboard',action['id'],key);return
        original=page.url.split('#',1)[0]
        for gesture in ('click','Enter'):
            start=len(navigations)
            try:
                page.evaluate('()=>history.replaceState(null,"",location.pathname+location.search)')
                if gesture=='Enter':locator.focus()
                expected=page.evaluate('(target)=>new URL(target,location.href).href',action['target'])
                start=len(navigations)
                expected_action['url']=expected.split('#',1)[0]
                page.evaluate('''target=>{
                    window.__vgActionCleanup?.();
                    const targetNode=()=>{try{return document.getElementById(decodeURIComponent(new URL(target,location.href).hash.slice(1)))}catch{return null}};
                    const snapshot=()=>{const n=targetNode(),r=n?.getBoundingClientRect();return {y:scrollY,visible:!!r&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight}};
                    window.__vgAction={before:snapshot(),event:null,protocol_allowed:false};
                    const capture=e=>{window.__vgAction.before=snapshot();window.__vgAction.event=e};
                    const bubble=e=>{if(/^(mailto:|tel:)/.test(target)){window.__vgAction.protocol_allowed=!e.defaultPrevented;e.preventDefault()}};
                    window.addEventListener('click',capture,{capture:true,once:true});
                    window.addEventListener('click',bubble,{once:true});
                    window.__vgActionAfter=snapshot;
                    window.__vgActionCleanup=()=>{window.removeEventListener('click',capture,true);window.removeEventListener('click',bubble)};
                }''',action['target'])
                # Destination navigation is intercepted as 204 by this probe;
                # waiting for a new document would add a false timeout per link.
                if gesture=='click':locator.click(no_wait_after=True)
                else:locator.press('Enter',no_wait_after=True)
                page.wait_for_timeout(100)
                observed=page.evaluate('''()=>{
                    const s=window.__vgAction,after=window.__vgActionAfter();
                    window.__vgActionCleanup();
                    return {before:s.before,after,url:location.href,protocol_allowed:s.protocol_allowed};
                }''')
                activated=(len(navigations)>start or observed['url']==expected
                    or observed['protocol_allowed'] or
                    (observed['after']['visible'] and (not observed['before']['visible']
                        or abs(observed['after']['y']-observed['before']['y'])>4)))
                if not activated:
                    try:
                        page.wait_for_function('''expected=>{
                            const s=window.__vgAction,after=window.__vgActionAfter();
                            return location.href===expected || s.protocol_allowed ||
                                (after.visible && (!s.before.visible || Math.abs(after.y-s.before.y)>4));
                        }''',arg=expected,timeout=1000)
                        activated=True
                    except Exception:pass
                # The WebKit navigation request may arrive during the bounded
                # wait; use that observed request as well as the DOM outcome.
                activated=activated or len(navigations)>start
                report['actions'].append({'id':action['id'],'context':key,'gesture':gesture,
                    'target':action['target'],'activated':activated,
                    'navigation_intercepted':len(navigations)>start,
                    'scope':'browser_activation_only_no_external_destination_or_protocol_opened'})
                if not activated:issue('action_activation',action['id']+' '+gesture,key)
            except Exception as error:issue('action_activation',action['id']+' '+str(error),key)
            finally:
                expected_action['url']=None
                for popup in list(page.context.pages):
                    if popup!=page:popup.close()
                if len(navigations)>start:
                    # A 204 navigation retains the DOM but may leave a provisional
                    # navigation in the engine. Cancel it before another locator.
                    page.goto(original,wait_until='load',timeout=10000)
        if page.url.split('#',1)[0]!=original:page.goto(original,wait_until='load',timeout=10000)

    documents=[manifest['entrypoint']]+[name for name in plan['public_files']
        if name!=manifest['entrypoint'] and Path(name).suffix.lower() in ('.html','.htm')]

    with (serve_bundle(directory,manifest) if origin is None else nullcontext(origin)) as origin, sync_playwright() as playwright:
        report.update(origin=origin,authentication='none_fresh_browser_contexts')
        for engine in browsers:
            browser=None
            try:
                if engine=='chromium':browser,channel=launch_browser(playwright)
                elif engine=='webkit':browser=playwright.webkit.launch(headless=True);channel='webkit'
                else:raise ValueError('Unsupported inspection engine')
                report['browsers'].append({'engine':engine,'channel':channel,'version':browser.version})
                modes=[(viewport,False) for viewport in viewports]+[(viewports[-1],True)]
                for viewport,reduced in modes:
                    mode_key=f'{engine}-{viewport[0]}x{viewport[1]}-'+('reduced' if reduced else 'normal')
                    key=mode_key
                    context=browser.new_context(viewport={'width':viewport[0],'height':viewport[1]},
                        device_scale_factor=1,reduced_motion='reduce' if reduced else 'no-preference',
                        service_workers='block',accept_downloads=False)
                    try:
                        expected_action={'url':None};navigations=[]
                        def route(request_route):
                            request=request_route.request;url=urlsplit(request.url)
                            if (expected_action['url'] and request.is_navigation_request()
                                    and request.url==expected_action['url'] and request.method=='GET'):
                                navigations.append(request.url);request_route.fulfill(status=204,body='');return
                            if (url.scheme in ('http','https') and request.url.startswith(origin+'/')
                                    and request.method in ('GET','HEAD')):
                                request_route.continue_()
                            else:
                                issue('external_resource','Blocked request: '+request.url,key)
                                request_route.abort()
                        context.route('**/*',route)
                        page=context.new_page();page.set_default_timeout(3000)
                        page.on('pageerror',lambda error:issue('script_error',error,key))
                        def console(message):
                            if message.type=='error':
                                code='external_resource' if 'Content Security Policy' in message.text or 'violates' in message.text else 'console_error'
                                issue(code,message.text,key)
                        page.on('console',console)
                        page.on('response',lambda response:issue('resource_error',str(response.status)+' '+response.url,key) if response.status>=400 else None)
                        for page_index,document_path in enumerate(documents):
                            key=mode_key+'-page-'+str(page_index)
                            try:
                                response=page.goto(origin+('/' if document_path==manifest['entrypoint'] else '/'+document_path),wait_until='load',timeout=10000)
                                if not response or response.status!=200:issue('entry_response','Entry is not200',key)
                                page.evaluate('() => document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))')
                                if page.evaluate('document.documentElement.scrollWidth > innerWidth + 1'):
                                    issue('horizontal_overflow','Content exceeds the actual viewport',key)
                                for row in plan['coverage']:
                                    if row.get('page',manifest['entrypoint'])!=document_path:continue
                                    locator=page.locator(row['selector'])
                                    if locator.count()!=1 or not locator.is_visible() or not locator.inner_text().strip():
                                        issue('missing_content',row['id']+' '+row['selector'],key)
                                    else:
                                        locator.scroll_into_view_if_needed()
                                        report['coverage'].append({'id':row['id'],'context':key,
                                            'page':document_path,'selector':row['selector'],'text':locator.inner_text()[:240]})
                                for action in plan['actions']:
                                    if action.get('page',manifest['entrypoint'])!=document_path:continue
                                    inspect_action(page,action,key,expected_action,navigations)
                                for scene in plan['scenes']:
                                    if scene.get('page',manifest['entrypoint'])!=document_path:continue
                                    locator=page.locator(scene['selector'])
                                    if locator.count()!=1:
                                        issue('missing_scene',scene['id'],key);continue
                                    observed={'id':scene['id'],'context':key,'page':document_path,'reduced_motion':reduced,
                                              'forward_states':[],'reverse_states':[],'positions':[]}
                                    for direction,positions in [('forward',scene['states']),('reverse',list(reversed(scene['states'])))]:
                                        for progress in positions:
                                            position=page.evaluate('''({selector,progress}) => {
                                                const node=document.querySelector(selector),rect=node.getBoundingClientRect();
                                                const target=Math.min(document.documentElement.scrollHeight-innerHeight,
                                                    Math.max(0,rect.top+scrollY+progress*Math.max(0,node.offsetHeight-innerHeight)));
                                                scrollTo({top:target,behavior:'instant'});return target;
                                            }''',{'selector':scene['selector'],'progress':progress})
                                            page.evaluate('() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
                                            actual=page.evaluate('scrollY')
                                            if abs(actual-position)>4:issue('scroll_control',scene['id'],key)
                                            observed[direction+'_states'].append(progress)
                                            observed['positions'].append({'direction':direction,'progress':progress,'scroll_y':actual})
                                            capture(page,key,viewport,kind='scene',scene=scene['id'],direction=direction,
                                                    progress=progress,reduced_motion=reduced,page=document_path)
                                    report['scenes'].append(observed)
                                for control in plan.get('controls',[]):
                                    if control.get('page',manifest['entrypoint'])!=document_path:continue
                                    locator=page.locator(control['selector'])
                                    if locator.count()!=1:issue('missing_control',control['selector'],key);continue
                                    if control.get('key'):locator.press(control['key'])
                                    else:locator.click()
                                    if not page.locator(control['expect_selector']).is_visible():
                                        issue('control_result',control['selector'],key)
                                for frame_index,frame in enumerate(page.frames):
                                    frame_key=key if frame==page.main_frame else key+'-frame-'+str(frame_index)
                                    frame_url=urlsplit(frame.url)
                                    if frame_url.scheme in ('http','https') and not frame.url.startswith(origin+'/'):
                                        issue('external_frame',frame.url,frame_key);continue
                                    if frame==page.main_frame or frame_url.scheme in ('http','https'):
                                        inspect_media(frame,frame_key)
                                    else:issue('uninspected_frame',frame.url,frame_key)
                                capture(page,key+'-document',viewport,
                                    kind='sources' if document_path==manifest['sources_page'] else 'page',
                                    page=document_path,reduced_motion=reduced)
                                report['pages'].append({'page':document_path,'context':key,'reduced_motion':reduced,
                                    'frames':[frame.url for frame in page.frames]})
                            except Exception as error:
                                issue('browser_probe',error,key)

                    except Exception as error:
                        issue('browser_probe',error,key)
                    finally:
                        context.close()
            except Exception as error:
                issue('browser_unavailable',str(error),engine)
            finally:
                if browser:browser.close()
    try:web.verify_bundle(directory)
    except (ValueError,OSError) as error:issue('changed_build',error)
    report['status']='BLOCKED' if report['issues'] else 'PASS'
    (output/'report.json').write_bytes(web._canonical(report))
    return report
