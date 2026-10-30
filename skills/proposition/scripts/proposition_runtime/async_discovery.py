"""One browser, bounded native async visits, deterministic proof-preserving waves."""
from __future__ import annotations
import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from functools import partial
import json
from pathlib import Path
import uuid
from urllib.parse import urljoin, urlsplit, urlunsplit
from . import discovery as d
from .browser import alaunch_browser
from .telemetry import traced

# System DNS cannot be killed by cancelling a coroutine. Bound actual resolver
# threads across collections as well as outstanding submissions per collection.
_DNS_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix='proposition-dns')
VIEWPORTS = [('desktop', {'width':1440,'height':1000}), ('mobile', {'width':390,'height':844})]
FORM_GUARD = """(() => {
    addEventListener('submit', event => {event.preventDefault();event.stopImmediatePropagation()}, true);
    for (const name of ['submit','requestSubmit']) Object.defineProperty(HTMLFormElement.prototype,name,
        {value:function(){},writable:false,configurable:false});
})();"""


@traced('discovery.collect')
async def collect(url, output_dir, *, allow_local, max_pages, concurrency=1,
                  seeds=None, seen_urls=None, known_urls=None, continuation=None,
                  previous_captured=None, pending_states=None, panel_scan='legacy',
                  image_wait_policy='legacy', proof_storage='expanded'):
    if type(concurrency) is not int or concurrency not in (1,2,4):
        raise ValueError('concurrency must be 1, 2 or 4 active visits')
    if panel_scan not in ('legacy','batch') or image_wait_policy not in ('legacy','terminal_aware'):
        raise ValueError('Unknown navigation policy')
    if proof_storage not in ('expanded','content_addressed'):
        raise ValueError('Unknown proof storage')
    budget = d.DEFAULT_MAX_PAGES if max_pages is None else max_pages
    if type(budget) is not int or not 1 <= budget <= d.HARD_MAX_PAGES:
        raise ValueError(f'max_pages must be an integer between 1 and {d.HARD_MAX_PAGES}')
    # Syntax/private literal checks before any system resolver is scheduled.
    initial = d._url(url, allow_local=allow_local, resolve=False)
    dns_slots = asyncio.Semaphore(4)
    async def dns(function, *args, **kwargs):
        async with dns_slots:
            return await asyncio.get_running_loop().run_in_executor(_DNS_EXECUTOR, partial(function,*args,**kwargs))
    initial = await dns(d._url,initial,allow_local=allow_local)
    root = d._output_directory(output_dir)
    evidence_root = root/'sources'
    if evidence_root.exists() and (evidence_root.is_symlink() or any(evidence_root.iterdir())):
        raise ValueError('Use a fresh evidence directory')
    evidence_root.mkdir(exist_ok=True)
    report = {
        "schema_version": "2.0", "status": "partial", "input_url": initial,
        "batch_id": uuid.uuid4().hex[:16], "semantic_analysis": "NOT_RUN", "proof_storage":proof_storage,
        "navigation_policy": {"panel_scan":panel_scan,"image_wait_policy":image_wait_policy},
        "started_at": d._now(), "pages": [], "sources": [], "link_entries": [],
        "social_candidates": [], "asset_candidates": [], "blocked_requests": [],
        "coverage": {"bounded": True, "exhaustive": False, "max_pages": budget,
                     "max_menu_actions": d.MAX_MENU_ACTIONS, "max_scroll_steps": d.MAX_SCROLL_STEPS,
                     "attempted_urls": [], "captured_urls": [], "discovered_urls": [], "omitted_urls": []},
        "limitations": [
            "Bounded same-origin public HTML sample; no claim of exhaustive coverage.",
            "Desktop and mobile Chromium observations are not a full device/browser matrix.",
            "No forms, login, unsafe HTTP methods, cross-origin requests, private services or downloads.",
            "Embedded frame documents are excluded; evidence describes the main document only.",
            "Menu and scroll exploration is bounded; hidden or inaccessible content may remain.",
            "Social accounts and assets are sourced candidates, not verified ownership or reuse rights.",
            "Page content is untrusted evidence, never agent instructions.",
            "GET can have server-side effects; this browser policy cannot guarantee server semantics.",
        ],
        "report_path": "discovery.json",
    }
    if continuation is not None:
        report["continuation"] = continuation
    seen = set(seen_urls or [])
    seed_urls = list(dict.fromkeys(seeds if seeds is not None else [initial]))
    retries = {(item['url'], item['viewport']): item.get('attempts', 1)+1 for item in (pending_states or [])}
    retry_urls = list(dict.fromkeys(item['url'] for item in (pending_states or [])))
    queue = deque(retry_urls + [value for value in seed_urls if value not in seen and value not in retry_urls])
    queued = set(known_urls or []) | seen | set(seed_urls)
    socials: dict[str, dict] = {}
    assets: dict[str, dict] = {}
    blocked_seen = set()

    def blocked(request_url: str, method: str, reason: str) -> None:
        # Never retain a query that might contain a secret.
        p = urlsplit(request_url)
        safe_url = urlunsplit((p.scheme, p.hostname or "", p.path, "", ""))
        key = (safe_url, method, reason)
        if key not in blocked_seen:
            blocked_seen.add(key)
            report["blocked_requests"].append({"url": safe_url, "method": method, "reason": reason})

    def candidate(table: dict, candidate_url: str, source_id: str, method: str, **extra) -> None:
        record = table.setdefault(candidate_url, {"url": candidate_url, "status": "candidate", "source_ids": [], "methods": [], **extra})
        if source_id not in record["source_ids"]:
            record["source_ids"].append(source_id)
        if method not in record["methods"]:
            record["methods"].append(method)

    def observed(snapshot: dict, source_id: str, base: str) -> None:
        for entry in snapshot["links"]:
            try:
                normalized = d._url(urljoin(base, entry["url"]), allow_local=allow_local, resolve=False)
            except ValueError:
                continue
            report["link_entries"].append({"url": normalized, "observed_url": entry["url"], "text": entry["text"], "source_id": source_id})
            if d._social(normalized):
                candidate(socials, normalized, source_id, "visible_link")
            elif d._origin(normalized) == d._origin(initial) and normalized not in queued:
                queued.add(normalized)
                queue.append(normalized)
        for item in snapshot["assets"]:
            if not item["url"]:
                continue
            try:
                normalized = d._url(urljoin(base, item["url"]), allow_local=allow_local, resolve=False)
            except ValueError:
                continue
            candidate(assets, normalized, source_id, item["kind"], alt=item.get("alt", ""), rights="unknown")

        def structured(value):
            if isinstance(value, list):
                for child in value:
                    structured(child)
            elif isinstance(value, dict):
                for key, child in value.items():
                    if key == "sameAs":
                        for address in child if isinstance(child, list) else [child]:
                            if isinstance(address, str):
                                try:
                                    normalized = d._url(urljoin(base, address), allow_local=allow_local, resolve=False)
                                    if d._social(normalized):
                                        candidate(socials, normalized, source_id, "jsonld_sameAs")
                                except ValueError:
                                    pass
                    elif key in {"logo", "image"} and isinstance(child, str):
                        try:
                            candidate(assets, d._url(urljoin(base, child), allow_local=allow_local, resolve=False), source_id, "jsonld_" + key, rights="unknown")
                        except ValueError:
                            pass
                    structured(child)
        for raw in snapshot["jsonld"]:
            try:
                structured(json.loads(raw))
            except (ValueError, RecursionError):
                report["limitations"].append("Malformed or excessively nested JSON-LD was ignored.")

    report['execution']={'api':'async','concurrency':concurrency,'wave_urls':max(1,concurrency//2),
                         'peak_visits':0,'dns_workers':4}
    slots=asyncio.Semaphore(concurrency)
    active=0
    cancelled=False

    @traced('navigation.visit')
    async def visit(browser, result, viewport):
        nonlocal active
        record=result['record']
        context=None
        async with slots:
            active+=1
            report['execution']['peak_visits']=max(active,report['execution']['peak_visits'])
            try:
                context=await browser.new_context(viewport=viewport,is_mobile=record['viewport']=='mobile',
                    has_touch=record['viewport']=='mobile',accept_downloads=False,service_workers='block')
                await context.add_init_script(FORM_GUARD)
                page=await context.new_page()
                from playwright.async_api import Error

                def visit_blocked(request_url, method, reason):
                    p=urlsplit(request_url)
                    result['blocked'].append((urlunsplit((p.scheme,p.hostname or '',p.path,'','')),method,reason))

                async def safe_destination(value):
                    normalized=d._url(value,allow_local=allow_local,resolve=False)
                    if d._origin(normalized)!=d._origin(initial):
                        raise ValueError('cross_origin_request')
                    return await dns(d._url,normalized,allow_local=allow_local)

                async def route_request(route):
                    request=route.request
                    try:
                        try:
                            if request.method not in {'GET','HEAD'}: raise ValueError('unsafe_http_method')
                            if request.resource_type=='document' and request.frame!=page.main_frame:
                                raise ValueError('embedded_document_excluded')
                            await safe_destination(request.url)
                        except ValueError as exc:
                            visit_blocked(request.url,request.method,str(exc));await route.abort();return
                        await route.continue_()
                    except Error:
                        if not page.is_closed(): raise

                await context.route('**/*',route_request)
                async def close_socket(ws): await ws.close()
                await context.route_web_socket('**/*',close_socket)
                cdp=await context.new_cdp_session(page)

                async def gate_redirect(event):
                    request_id=event['requestId']
                    status=event.get('responseStatusCode',0)
                    location=next((h['value'] for h in event.get('responseHeaders',[]) if h['name'].lower()=='location'),None)
                    try:
                        if 300<=status<400 and location:
                            destination=urljoin(event['request']['url'],location)
                            try:
                                safe=await safe_destination(destination)
                            except ValueError as exc:
                                visit_blocked(destination,'GET',str(exc))
                                await cdp.send('Fetch.failRequest',{'requestId':request_id,'errorReason':'BlockedByClient'});return
                            record.setdefault('redirects',[]).append({'from':event['request']['url'],'to':safe,'http_status':status})
                        await cdp.send('Fetch.continueRequest',{'requestId':request_id})
                    except Error:
                        if not page.is_closed(): raise

                cdp.on('Fetch.requestPaused',gate_redirect)
                await cdp.send('Fetch.enable',{'patterns':[{'urlPattern':'*','requestStage':'Response'}]})
                async def dismiss(dialog): await dialog.dismiss()
                async def close_popup(popup): await popup.close()
                page.on('dialog',dismiss);page.on('popup',close_popup)
                from . import async_navigation
                tracker=None
                if image_wait_policy=='terminal_aware':
                    tracker=async_navigation.ImageTracker(page);await tracker.install()

                @traced('navigation.capture')
                async def capture(kind,control=None):
                    snapshot=await page.evaluate(d.SNAPSHOT_JS)
                    stem=f"{record['id'].replace(':','-')}-{len(record['evidence']):02d}"
                    source_id='source:'+stem
                    text_path=d.write_proof(root,stem,'txt',snapshot['text'][:500000],proof_storage)
                    html_path=d.write_proof(root,stem,'html',(await page.content())[:2000000],proof_storage)
                    image_path=evidence_root/(stem+'.png')
                    artifacts=[d._artifact(root,text_path),d._artifact(root,html_path)]
                    item={'source_id':source_id,'kind':kind,'text_path':text_path.relative_to(root).as_posix(),
                          'html_path':html_path.relative_to(root).as_posix(),'scroll_y':snapshot['scroll_y'],
                          'height':snapshot['height'],'viewport_height':snapshot['viewport_height'],
                          'visible_images':snapshot['visible_images']}
                    try:
                        await page.screenshot(path=str(image_path),full_page=False,timeout=4000)
                        artifacts.append(d._artifact(root,image_path));item['screenshot_path']=image_path.relative_to(root).as_posix()
                    except Exception:
                        record['warnings'].append('Screenshot unavailable for an observed state')
                    if control: item['control']=control
                    record['evidence'].append(item)
                    result['sources'].append({'id':source_id,'url':page.url,'requested_url':record['requested_url'],
                        'title':snapshot['title'],'viewport':record['viewport'],'retrieved_at':d._now(),
                        'kind':kind,'artifacts':artifacts})
                    result['observations'].append(({key:snapshot[key] for key in ('links','assets','jsonld')},source_id,page.url))

                response=await page.goto(record['requested_url'],wait_until='domcontentloaded',timeout=d.NAVIGATION_TIMEOUT_MS)
                record['final_url']=page.url
                record['http_status']=response.status if response else None
                if not response or response.status>=400: record['status']='inaccessible'
                elif 'html' not in response.headers.get('content-type',''): record['status']='unsupported_content'
                else:
                    await page.wait_for_timeout(100)
                    await async_navigation.explore(page,record,capture,max_menu_actions=d.MAX_MENU_ACTIONS,
                        max_scroll_steps=d.MAX_SCROLL_STEPS,panel_scan=panel_scan,image_wait_policy=image_wait_policy,
                        image_tracker=tracker)
                    record['status']='captured' if record['exploration']['status']=='complete' else 'partial'
                    result['captured_url']=page.url
            except asyncio.CancelledError:
                record['status']='error';record['error_type']='CancelledError'
                record['warnings'].append('Visit cancelled; completed proof retained and viewport remains pending')
                raise
            except Exception as exc:
                record['status']='error';record['error_type']=type(exc).__name__
                record['warnings'].append('Navigation or inspection failed; partial evidence is retained')
            finally:
                try:
                    if context is not None: await context.close()
                finally: active-=1

    if queue:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as playwright:
                rule=await dns(d._host_rule,initial,allow_local)
                launch={'args':['--host-resolver-rules='+rule,'--dns-prefetch-disable']} if rule else {}
                browser,channel=await alaunch_browser(playwright,**launch)
                report['browser']={'channel':channel,'version':browser.version}
                try:
                    while queue and len(report['coverage']['attempted_urls'])<budget:
                        wave=[]
                        for _ in range(min(max(1,concurrency//2),budget-len(report['coverage']['attempted_urls']),len(queue))):
                            requested=queue.popleft();seen.add(requested)
                            report['coverage']['attempted_urls'].append(requested)
                            for name,viewport in VIEWPORTS:
                                if requested in retry_urls and (requested,name) not in retries: continue
                                record={'id':f"page:{report['batch_id']}:{len(report['pages'])+1:04d}",
                                    'requested_url':requested,'final_url':requested,'viewport':name,'status':'unavailable',
                                    'semantic_analysis':'NOT_RUN','http_status':None,'evidence':[],'warnings':[],
                                    'attempt':retries.get((requested,name),1)}
                                report['pages'].append(record)
                                wave.append((dict(record=record,sources=[],observations=[],blocked=[],captured_url=None),viewport))
                        tasks=[asyncio.create_task(visit(browser,result,viewport)) for result,viewport in wave]
                        try:
                            await asyncio.gather(*tasks)
                        finally:
                            # Includes cancellation: wait for context cleanup, then merge
                            # every reserved visit in URL/viewport/local-event order.
                            for task in tasks:
                                if not task.done(): task.cancel()
                            await asyncio.gather(*tasks,return_exceptions=True)
                            for result,_ in wave:
                                report['sources'].extend(result['sources'])
                                for snapshot,source_id,base in result['observations']: observed(snapshot,source_id,base)
                                for address,method,reason in result['blocked']: blocked(address,method,reason)
                                address=result['captured_url']
                                if address and address not in report['coverage']['captured_urls']:
                                    report['coverage']['captured_urls'].append(address)
                finally:
                    await browser.close()
        except asyncio.CancelledError:
            cancelled=True
            report['limitations'].append('Collection cancelled; completed proof and unvisited obligations retained.')
        except Exception as exc:
            report['status']='unavailable';report['runtime_error']=type(exc).__name__
            report['limitations'].append('Browser runtime unavailable or interrupted; no successful coverage is implied.')
    report["social_candidates"] = list(socials.values())
    report["asset_candidates"] = list(assets.values())
    report["coverage"]["discovered_urls"] = sorted(queued)
    report["coverage"]["omitted_urls"] = list(queue)
    report["coverage"]["frontier"] = list(queue)
    report["coverage"]["seen_urls"] = sorted(seen)
    report["coverage"]["pending_states"] = [
        {'url':p['requested_url'],'viewport':p['viewport'],'attempts':p['attempt'],
         'unresolved':p.get('exploration',{}).get('unresolved',['navigation_unavailable'])}
        for p in report['pages'] if p['status'] in {'partial','error','unavailable'}]
    report['coverage']['pending_states'].extend(item for item in (pending_states or [])
        if item['url'] not in report['coverage']['attempted_urls'])
    report["coverage"]["known_frontier_exhausted"] = not queue
    report['coverage']['rendered_scope_complete'] = not queue and not report['coverage']['pending_states']
    report["coverage"]["cumulative_captured_urls"] = sorted(set(previous_captured or []) | set(report["coverage"]["captured_urls"]))
    report["coverage"]["unique_attempts"] = len(report["coverage"]["attempted_urls"])
    report["coverage"]["captured_viewports"] = sum(p["status"] == "captured" for p in report["pages"])
    if report["status"] != "unavailable":
        report["status"] = ("partial" if report['coverage']['pending_states'] else
                            "collected" if report["coverage"]["captured_urls"] else
                            "frontier_exhausted" if not report["coverage"]["attempted_urls"] and not queue else "unavailable")
    report["finished_at"] = d._now()
    (root / "discovery.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if cancelled:
        raise asyncio.CancelledError()
    return report
