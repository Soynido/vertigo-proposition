"""Native async visible interactions; same selectors, budgets and policies as navigation."""
import time
from .telemetry import traced
from .navigation import (CONTROLS, OVERLAYS, CLOSE, INFO, OPEN, IMAGES, PANEL_INFO,
                         PANEL_GEOMETRY, IMAGE_OBSERVER, IMAGE_STATUS)

@traced('navigation.scan')
async def panel_candidates(page, scope, mode):
    if mode not in ('legacy', 'batch'):
        raise ValueError('Unknown panel scan')
    locator = scope.locator('body *' if scope is page else '*')
    if mode == 'legacy':
        elements = [(-1, scope)] if scope is not page else []
        elements += list(enumerate((await locator.all())[:2000]))
        return [dict(index=i, **await e.evaluate(PANEL_INFO)) for i, e in elements if await e.is_visible() and await e.evaluate(PANEL_GEOMETRY)]
    script = 'es=>es.slice(0,2000).map((e,index)=>({e,index})).filter(x=>(' + PANEL_GEOMETRY + ')(x.e)).map(x=>({index:x.index,...(' + PANEL_INFO + ')(x.e)}))'
    candidates = await locator.evaluate_all(script)
    if scope is not page and await scope.evaluate(PANEL_GEOMETRY):
        candidates.insert(0, dict(index=-1, **await scope.evaluate(PANEL_INFO)))
    return [c for c in candidates if await (scope if c['index'] == -1 else locator.nth(c['index'])).is_visible()]

async def resolve_panel(page, scope, candidate):
    from playwright.async_api import Error
    locator = scope if candidate['index'] == -1 else scope.locator('body *' if scope is page else '*').nth(candidate['index'])
    try:
        handle = await locator.element_handle(timeout=1000)
    except Error:
        return None
    if handle is not None:
        if await handle.evaluate(PANEL_INFO) == {k: candidate[k] for k in ('token', 'key')} and await handle.is_visible() and await handle.evaluate(PANEL_GEOMETRY):
            return handle
        await handle.dispose()
    return None

class ImageTracker:
    """One page/visit. Unknown generations retain the full pending wait."""

    def __init__(self, page):
        self.page = page
        self.requests = {}

    def note_request(self, url, started=None):
        self.requests[url] = started if started is not None and started > 0 else time.time() * 1000

    async def install(self):
        await self.page.add_init_script(IMAGE_OBSERVER)
        await self.page.evaluate(IMAGE_OBSERVER)
        self.page.on('request', lambda request: self.note_request(request.url, request.timing.get('startTime')) if request.resource_type == 'image' else None)

    @traced('navigation.image_wait')
    async def wait(self):
        states = await self.page.evaluate(IMAGE_STATUS, self.requests)
        if any((not s['loaded'] and (not s['terminal']) for s in states)):
            try:
                await self.page.wait_for_function('requests=>(' + IMAGE_STATUS + ')(requests).every(s=>s.loaded||s.terminal)', arg=self.requests, timeout=750)
            except Exception:
                return False
        return all((s['loaded'] for s in await self.page.evaluate(IMAGE_STATUS, self.requests)))

async def explore(page, record, capture, *, max_menu_actions, max_scroll_steps, panel_scan='legacy', image_wait_policy='legacy', image_tracker=None):
    if panel_scan not in ('legacy', 'batch') or image_wait_policy not in ('legacy', 'terminal_aware'):
        raise ValueError('Unknown navigation policy')
    actions = record['interactions'] = []
    unresolved = []
    start_url = page.url
    record['exploration'] = {'status': 'partial', 'unresolved': unresolved, 'scroll': {'reached_end': False}, 'bounded': True}

    async def shot(kind, label=None):
        try:
            if image_wait_policy == 'terminal_aware' and image_tracker is not None:
                if not await image_tracker.wait():
                    unresolved.append('visible_images_unavailable')
            else:
                await page.wait_for_function(IMAGES, timeout=750)
        except Exception:
            unresolved.append('visible_images_unavailable')
        await capture(kind, label)
        if not record['evidence'][-1].get('screenshot_path'):
            unresolved.append('screenshot_unavailable')

    async def overlays():
        found = []
        for item in (await page.locator(OVERLAYS).all())[:30]:
            if not await item.is_visible():
                continue
            if await item.evaluate('e=>{let r=e.getBoundingClientRect();return r.width>80&&r.height>40}'):
                found.append(item)
        return found

    async def clear_overlays():
        for _ in range(3):
            visible = await overlays()
            if not visible:
                return True
            dismissed = False
            for overlay in visible:
                for button in (await overlay.locator('button, [role="button"], a').all())[:30]:
                    labels = [value.strip() for value in (await button.get_attribute('aria-label') or '', await button.inner_text())]
                    label = next((value for value in labels if CLOSE.fullmatch(value)), '')
                    if not await button.is_visible() or not label:
                        continue
                    try:
                        await button.click(timeout=1000, no_wait_after=True)
                        await page.wait_for_timeout(100)
                        if not await overlay.is_visible():
                            actions.append({'kind': 'overlay', 'control': label[:200], 'status': 'resolved'})
                            await shot('overlay_closed', label)
                            dismissed = True
                            break
                    except Exception:
                        continue
                if dismissed:
                    break
            if not dismissed:
                actions.append({'kind': 'overlay', 'status': 'unresolved', 'reason': 'no_safe_dismissal'})
                unresolved.append('overlay_not_dismissed')
                return False
        unresolved.append('overlay_budget_exhausted')
        return False
    await page.wait_for_timeout(450)
    await shot('initial')
    if not await clear_overlays():
        return
    handled = set()
    handled_panels = set()

    async def scroll_panels(scope):
        candidates = await panel_candidates(page, scope, panel_scan)
        rescanned = False
        while candidates:
            candidate = candidates.pop(0)
            panel = await resolve_panel(page, scope, candidate)
            if panel is None:
                if not rescanned:
                    candidates = await panel_candidates(page, scope, panel_scan)
                    rescanned = True
                    continue
                unresolved.append('inner_panel_identity_changed')
                break
            key = candidate['key']
            if key in handled_panels:
                await panel.dispose()
                continue
            handled_panels.add(key)
            reached = False
            await panel.scroll_into_view_if_needed(timeout=1000)
            for _ in range(max_scroll_steps):
                await panel.evaluate('e=>e.scrollBy(0,Math.max(60,e.clientHeight*.8))')
                await page.wait_for_timeout(80)
                await shot('inner_scroll')
                geometry = await panel.evaluate('e=>({end_y:e.scrollTop,height:e.scrollHeight,viewport_height:e.clientHeight})')
                if not await panel.is_visible() or geometry['viewport_height'] <= 0:
                    unresolved.append('inner_panel_disappeared')
                    break
                reached = geometry['end_y'] + geometry['viewport_height'] >= geometry['height'] - 2
                if reached:
                    break
            actions.append({'kind': 'inner_scroll', 'status': 'resolved' if reached else 'unresolved', **geometry})
            if not reached:
                unresolved.append('inner_scroll_ceiling')
            await panel.dispose()

    async def menus(depth=0, scope=None):
        if depth > max_menu_actions:
            return
        for control in (await (scope if scope is not None else page).locator(CONTROLS).all())[:80]:
            if not await control.is_visible():
                continue
            info = await control.evaluate(INFO)
            if info['form'] or info['key'] in handled:
                continue
            if len(handled) >= max_menu_actions:
                unresolved.append('menu_budget_exhausted')
                return
            handled.add(info['key'])
            action = {'kind': 'menu', 'control': info['label'][:200], 'opened': False, 'closed': False, 'status': 'unresolved'}
            actions.append(action)
            try:
                if not await clear_overlays():
                    return
                hover_menu = await control.evaluate('e=>!!e.closest(\'.w-dropdown[data-hover="true"]\')')
                delay = await control.evaluate("e=>Math.min(750,Math.max(0,Number(e.closest('.w-dropdown')?.getAttribute('data-delay'))||100))")
                if hover_menu:
                    await control.hover(timeout=1500)
                    await page.wait_for_timeout(delay + 100)
                if not await control.evaluate(OPEN):
                    await control.click(timeout=1500, no_wait_after=True)
                await page.wait_for_timeout(100)
                if page.url != start_url:
                    unresolved.append('menu_navigated')
                    return
                action['opened'] = bool(await control.evaluate(OPEN))
                await shot('menu', info['label'][:200])
                if action['opened']:
                    target = await control.evaluate("e=>{let id=e.getAttribute('aria-controls');return id?'#'+CSS.escape(id):null}")
                    if target:
                        await menus(depth + 1, page.locator(target))
                        await scroll_panels(page.locator(target))
                    elif info['details'] or await control.evaluate("e=>!!e.closest('.w-dropdown')"):
                        await menus(depth + 1, control.locator('..'))
                        await scroll_panels(control.locator('..'))
                    else:
                        unresolved.append('menu_target_not_identified')
                    if hover_menu:
                        await page.mouse.move(0, page.viewport_size['height'] - 1)
                        await page.wait_for_timeout(delay + 100)
                    else:
                        await control.click(timeout=1000, no_wait_after=True)
                        await page.wait_for_timeout(80)
                    action['closed'] = not await control.evaluate(OPEN)
                    await shot('menu_closed', info['label'][:200])
                if action['opened'] and action['closed']:
                    action['status'] = 'resolved'
                else:
                    unresolved.append('menu_state_not_proven')
            except Exception:
                unresolved.append('menu_interaction_failed')
    await menus()
    if page.url != start_url:
        return
    hover_controls = [c for c in await page.locator('nav li:has(ul), nav [aria-haspopup]:not(button):not([role="button"])').all() if await c.is_visible()]
    hover_budget = max(0, max_menu_actions - len(handled))
    if len(hover_controls) > hover_budget:
        unresolved.append('hover_menu_budget_exhausted')
        record['exploration']['remaining_controls'] = [(await c.inner_text())[:200] for c in hover_controls[hover_budget:]]
    for control in hover_controls[:hover_budget]:
        if not await control.is_visible():
            continue
        try:
            await control.hover(timeout=1000)
            await page.wait_for_timeout(100)
            await shot('menu', 'hover')
            await scroll_panels(control)
            await page.mouse.move(0, page.viewport_size['height'] - 1)
            await page.wait_for_timeout(80)
            closed = not await control.evaluate("e=>e.matches(':hover')||e.getAttribute('aria-expanded')==='true'")
            actions.append({'kind': 'menu', 'control': 'hover', 'opened': True, 'closed': closed, 'status': 'resolved' if closed else 'unresolved'})
            if not closed:
                unresolved.append('hover_menu_not_closed')
        except Exception:
            unresolved.append('hover_menu_unavailable')
    if not await clear_overlays():
        return
    for candidate in (await page.locator('[data-w-id][class*="menu" i], [data-w-id][class*="hamburger" i]').all())[:80]:
        if not await candidate.is_visible():
            continue
        if await candidate.evaluate("e=>{const r=e.getBoundingClientRect();return r.width>10&&r.width<130&&r.height>10&&r.height<130&&!e.matches('button,a,[role=button],[aria-expanded]')}"):
            unresolved.append('unsemantic_menu_requires_host_observation')
    await scroll_panels(page)
    await page.evaluate('scrollTo(0,0)')
    previous_height = None
    stable = 0
    for step in range(max_scroll_steps):
        if not await clear_overlays():
            break
        await page.evaluate('scrollBy(0,Math.max(200,innerHeight*.8))')
        await page.wait_for_timeout(120)
        await shot('scroll')
        geometry = await page.evaluate('({y:scrollY,height:document.documentElement.scrollHeight,viewport:innerHeight})')
        bottom = geometry['y'] + geometry['viewport'] >= geometry['height'] - 2
        stable = stable + 1 if bottom and previous_height == geometry['height'] else 0
        previous_height = geometry['height']
        record['exploration']['scroll'].update(geometry, steps=step + 1, reached_end=stable >= 2)
        if stable >= 2:
            break
    if not record['exploration']['scroll']['reached_end']:
        unresolved.append('scroll_ceiling_or_unstable_content')
    record['exploration']['unresolved'] = list(dict.fromkeys(unresolved))
    if not unresolved:
        record['exploration']['status'] = 'complete'
