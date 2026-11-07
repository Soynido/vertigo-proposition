"""Real DOM, scroll and reduced-motion behavior of the reusable mechanisms."""
from pathlib import Path
from contextlib import ExitStack
import tempfile
import unittest
from playwright.sync_api import sync_playwright
from proposition_runtime.browser import launch_browser
from proposition_runtime.web_inspection import serve_bundle

KIT = Path(__file__).resolve().parents[1]/'skills/proposition/resources/web'


class WebMotionTests(unittest.TestCase):
    engine='chromium'
    def test_photo_layers_follow_native_scroll_in_both_directions_and_release_cleanly(self):
        self.assertTrue((KIT/'motion.mjs').is_file(), 'No portable, client-neutral motion mechanism')
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as playwright, ExitStack() as resources:
            root=Path(tmp); public=root/'.vercel/output/static';public.mkdir(parents=True)
            (public/'motion.mjs').write_bytes((KIT/'motion.mjs').read_bytes())
            (public/'index.html').write_text('''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
                <style>body{margin:0}section{height:300vh}.pin{position:sticky;top:0;height:100vh}
                #photo{width:50px;height:50px;background:navy}footer{height:100vh}</style>
                <section id="scene"><div class="pin"><div id="photo"></div><a href="#end">Continue</a></div></section>
                <footer id="end"><a href="#scene">Return</a></footer>
                <script type="module">import{createScrollScene}from'./motion.mjs';
                window.scene=createScrollScene(document.querySelector('#scene'),{layers:[{
                    element:document.querySelector('#photo'),keyframes:[{transform:'translateX(0px)',opacity:1},
                    {transform:'translateX(200px)',opacity:.5}]}]});window.ready=true;</script>''')
            browser=launch_browser(playwright)[0] if self.engine=='chromium' else playwright.webkit.launch(headless=True)
            resources.callback(browser.close)
            context=browser.new_context(viewport={'width':390,'height':844});resources.callback(context.close)
            with serve_bundle(root,{'entrypoint':'index.html'}) as origin:
                page=context.new_page();page.goto(origin);page.wait_for_function('()=>window.ready')
                for progress,want in [(0,0),(.5,100),(1,200),(.5,100),(0,0)]:
                    page.evaluate('(p)=>scene.goTo(p)',progress)
                    page.wait_for_function('(x)=>Math.abs(new DOMMatrix(getComputedStyle(document.querySelector("#photo")).transform).m41-x)<2',arg=want)
                    self.assertAlmostEqual(page.evaluate('scene.progress'),progress,delta=.01)
                page.emulate_media(reduced_motion='reduce')
                page.wait_for_function('()=>getComputedStyle(document.querySelector("#photo")).transform==="none"')
                page.evaluate('scene.goTo(.75)')
                self.assertEqual(page.locator('#photo').evaluate('(e)=>getComputedStyle(e).opacity'),'1')
                # Native keyboard scrolling remains available; the mechanism does not intercept it.
                before=page.evaluate('scrollY');page.keyboard.press('PageDown')
                page.wait_for_function('(y)=>scrollY>y',arg=before)
                page.emulate_media(reduced_motion='no-preference')
                page.evaluate('scene.destroy()')
                self.assertEqual(page.locator('#photo').evaluate('(e)=>getComputedStyle(e).transform'),'none')
                self.assertEqual(page.evaluate('document.body.style.overflow'),'')

class WebKitMotionTests(WebMotionTests):
    engine='webkit'


if __name__=='__main__':unittest.main()
