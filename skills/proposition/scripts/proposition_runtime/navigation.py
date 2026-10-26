"""Bounded visible interactions; transport/network policy stays in Discovery."""
import re

CONTROLS = ('button[aria-expanded], [role="button"][aria-expanded], button[aria-haspopup], '
            'details > summary, button[aria-label*="menu" i], .w-dropdown-toggle')
OVERLAYS = ('[role="dialog"][aria-modal="true"], dialog[open], [id*="cookie" i], '
            '[class*="cookie-banner" i], [id*="consent" i], [class*="consent-banner" i], '
            '[id*="axeptio" i]')
CLOSE = re.compile(r'^(?:continuer sans accepter|tout refuser|refuser(?: tout)?|reject(?: all)?|'
                   r'necessary only|only necessary|fermer|close|dismiss|non merci|no thanks|×|✕|x)$', re.I)
INFO = """e => {let p=[],n=e;while(n&&n!==document.body){p.unshift(n.tagName+':'+[...n.parentElement.children].indexOf(n));n=n.parentElement}return {key:p.join('/'),label:e.getAttribute('aria-label')||e.innerText||'',form:!!e.closest('form'),expanded:e.getAttribute('aria-expanded'),details:e.tagName==='SUMMARY'}}"""
OPEN = """e => e.tagName==='SUMMARY' ? e.parentElement.open : e.getAttribute('aria-expanded')==='true'"""
IMAGES = """() => [...document.images].filter(e=>{let r=e.getBoundingClientRect();return r.width&&r.height&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth}).every(e=>e.complete&&e.naturalWidth>0)"""


def explore(page, record, capture, *, max_menu_actions, max_scroll_steps):
    actions = record['interactions'] = []
    unresolved = []
    start_url = page.url
    record['exploration'] = {'status': 'partial', 'unresolved': unresolved,
                             'scroll': {'reached_end': False}, 'bounded': True}

    def shot(kind, label=None):
        try:
            page.wait_for_function(IMAGES, timeout=750)
        except Exception:
            unresolved.append('visible_images_unavailable')
        capture(kind, label)
        if not record['evidence'][-1].get('screenshot_path'):
            unresolved.append('screenshot_unavailable')

    def overlays():
        found = []
        for item in page.locator(OVERLAYS).all()[:30]:
            if not item.is_visible(): continue
            if item.evaluate("e=>{let r=e.getBoundingClientRect();return r.width>80&&r.height>40}"):
                found.append(item)
        return found

    def clear_overlays():
        # Ordinary visible controls only. No DOM hiding or forced clicks.
        for _ in range(3):
            visible = overlays()
            if not visible: return True
            dismissed = False
            for overlay in visible:
                for button in overlay.locator('button, [role="button"], a').all()[:30]:
                    labels = [value.strip() for value in (button.get_attribute('aria-label') or '', button.inner_text())]
                    label = next((value for value in labels if CLOSE.fullmatch(value)), '')
                    if not button.is_visible() or not label: continue
                    try:
                        button.click(timeout=1000, no_wait_after=True)
                        page.wait_for_timeout(100)
                        if not overlay.is_visible():
                            actions.append({'kind':'overlay','control':label[:200],'status':'resolved'})
                            shot('overlay_closed', label)
                            dismissed = True
                            break
                    except Exception:
                        continue
                if dismissed: break
            if not dismissed:
                actions.append({'kind':'overlay','status':'unresolved','reason':'no_safe_dismissal'})
                unresolved.append('overlay_not_dismissed')
                return False
        unresolved.append('overlay_budget_exhausted')
        return False

    page.wait_for_timeout(450)
    shot('initial')
    if not clear_overlays():
        return
    handled = set()

    handled_panels=set()

    def scroll_panels(scope):
        panels=scope.locator('body *' if scope is page else '*').all()[:2000]
        if scope is not page: panels=[scope,*panels]
        for panel in panels:
            if not panel.is_visible(): continue
            relevant=panel.evaluate("e=>{let r=e.getBoundingClientRect();return r.width>80&&r.height>60&&e.scrollHeight>e.clientHeight+20&&/auto|scroll/.test(getComputedStyle(e).overflowY)}")
            if not relevant: continue
            key=panel.evaluate(INFO)['key']
            if key in handled_panels: continue
            handled_panels.add(key)
            reached=False
            panel.scroll_into_view_if_needed(timeout=1000)
            for _ in range(max_scroll_steps):
                panel.evaluate("e=>e.scrollBy(0,Math.max(60,e.clientHeight*.8))")
                page.wait_for_timeout(80)
                shot('inner_scroll')
                geometry=panel.evaluate('e=>({end_y:e.scrollTop,height:e.scrollHeight,viewport_height:e.clientHeight})')
                if not panel.is_visible() or geometry['viewport_height']<=0:
                    unresolved.append('inner_panel_disappeared');break
                reached=geometry['end_y']+geometry['viewport_height']>=geometry['height']-2
                if reached: break
            actions.append({'kind':'inner_scroll','status':'resolved' if reached else 'unresolved',**geometry})
            if not reached: unresolved.append('inner_scroll_ceiling')

    def menus(depth=0, scope=None):
        if depth > max_menu_actions: return
        for control in (scope if scope is not None else page).locator(CONTROLS).all()[:80]:
            if not control.is_visible(): continue
            info = control.evaluate(INFO)
            if info['form'] or info['key'] in handled: continue
            if len(handled) >= max_menu_actions:
                unresolved.append('menu_budget_exhausted'); return
            handled.add(info['key'])
            action = {'kind':'menu','control':info['label'][:200], 'opened':False, 'closed':False, 'status':'unresolved'}
            actions.append(action)
            try:
                if not clear_overlays(): return
                hover_menu=control.evaluate("e=>!!e.closest('.w-dropdown[data-hover=\"true\"]')")
                delay=control.evaluate("e=>Math.min(750,Math.max(0,Number(e.closest('.w-dropdown')?.getAttribute('data-delay'))||100))")
                if hover_menu:
                    control.hover(timeout=1500)
                    page.wait_for_timeout(delay+100)
                if not control.evaluate(OPEN): control.click(timeout=1500, no_wait_after=True)
                page.wait_for_timeout(100)
                if page.url != start_url:
                    unresolved.append('menu_navigated'); return
                action['opened'] = bool(control.evaluate(OPEN))
                shot('menu', info['label'][:200])
                if action['opened']:
                    target=control.evaluate("e=>{let id=e.getAttribute('aria-controls');return id?'#'+CSS.escape(id):null}")
                    if target:
                        menus(depth+1,page.locator(target))
                        scroll_panels(page.locator(target))
                    elif info['details'] or control.evaluate("e=>!!e.closest('.w-dropdown')"):
                        menus(depth+1,control.locator('..'))
                        scroll_panels(control.locator('..'))
                    else:
                        unresolved.append('menu_target_not_identified')
                    if hover_menu:
                        page.mouse.move(0,page.viewport_size['height']-1)
                        page.wait_for_timeout(delay+100)
                    else:
                        control.click(timeout=1000, no_wait_after=True)
                        page.wait_for_timeout(80)
                    action['closed'] = not control.evaluate(OPEN)
                    shot('menu_closed', info['label'][:200])
                if action['opened'] and action['closed']: action['status']='resolved'
                else: unresolved.append('menu_state_not_proven')
            except Exception:
                unresolved.append('menu_interaction_failed')

    menus()
    if page.url != start_url: return
    hover_controls=[c for c in page.locator('nav li:has(ul), nav [aria-haspopup]:not(button):not([role="button"])').all() if c.is_visible()]
    hover_budget=max(0,max_menu_actions-len(handled))
    if len(hover_controls)>hover_budget:
        unresolved.append('hover_menu_budget_exhausted')
        record['exploration']['remaining_controls']=[c.inner_text()[:200] for c in hover_controls[hover_budget:]]
    for control in hover_controls[:hover_budget]:
        if not control.is_visible(): continue
        try:
            control.hover(timeout=1000); page.wait_for_timeout(100)
            shot('menu', 'hover')
            scroll_panels(control)
            page.mouse.move(0, page.viewport_size['height']-1)
            page.wait_for_timeout(80)
            closed = not control.evaluate("e=>e.matches(':hover')||e.getAttribute('aria-expanded')==='true'")
            actions.append({'kind':'menu','control':'hover','opened':True,'closed':closed,'status':'resolved' if closed else 'unresolved'})
            if not closed: unresolved.append('hover_menu_not_closed')
        except Exception:
            unresolved.append('hover_menu_unavailable')
    if not clear_overlays(): return

    # A small unlabelled interaction can be the only mobile navigation entry.
    # Do not click arbitrary containers or certify that an unseen menu is covered.
    for candidate in page.locator('[data-w-id][class*="menu" i], [data-w-id][class*="hamburger" i]').all()[:80]:
        if not candidate.is_visible(): continue
        if candidate.evaluate("e=>{const r=e.getBoundingClientRect();return r.width>10&&r.width<130&&r.height>10&&r.height<130&&!e.matches('button,a,[role=button],[aria-expanded]')}"):
            unresolved.append('unsemantic_menu_requires_host_observation')

    scroll_panels(page)

    page.evaluate('scrollTo(0,0)')
    previous_height=None
    stable=0
    for step in range(max_scroll_steps):
        if not clear_overlays(): break
        page.evaluate('scrollBy(0,Math.max(200,innerHeight*.8))')
        page.wait_for_timeout(120)
        shot('scroll')
        geometry=page.evaluate('({y:scrollY,height:document.documentElement.scrollHeight,viewport:innerHeight})')
        bottom=geometry['y']+geometry['viewport']>=geometry['height']-2
        stable=stable+1 if bottom and previous_height==geometry['height'] else 0
        previous_height=geometry['height']
        record['exploration']['scroll'].update(geometry, steps=step+1, reached_end=stable>=2)
        if stable>=2: break
    if not record['exploration']['scroll']['reached_end']: unresolved.append('scroll_ceiling_or_unstable_content')
    record['exploration']['unresolved']=list(dict.fromkeys(unresolved))
    if not unresolved: record['exploration']['status']='complete'
