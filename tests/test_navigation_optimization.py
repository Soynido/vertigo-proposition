"""Equal-work local browser regressions, no external website."""
import inspect
import sys
from pathlib import Path
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime import navigation,discovery
from proposition_runtime.browser import launch_browser
from playwright.sync_api import sync_playwright


class NavigationOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start();cls.browser,_=launch_browser(cls.pw)
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.pw.stop()
    def setUp(self):
        self.context=self.browser.new_context();self.addCleanup(self.context.close);self.page=self.context.new_page()
    def panels(self,scope,mode):
        self.assertTrue(hasattr(navigation,'panel_candidates'),'Grouped candidate selection missing')
        return navigation.panel_candidates(self.page,scope,mode)
    def test_equal_candidates_visibility_order_and_scope(self):
        self.page.set_content('<style>.p{width:100px;height:90px;overflow:auto}.p>i{display:block;height:200px}</style><div id="root" class="p"><div class="p" id="a"><i></i></div><div class="p" id="hidden" style="visibility:hidden"><i></i></div><div class="p" id="transparent" style="opacity:0"><i></i></div><i></i></div><div class="p" id="outside" style="position:absolute;top:4000px"><i></i></div>')
        for scope in (self.page,self.page.locator('#root')):
            a=self.panels(scope,'legacy');b=self.panels(scope,'batch')
            self.assertEqual([x['key'] for x in a],[x['key'] for x in b])
            self.assertEqual([x['token'] for x in a],[x['token'] for x in b])
        self.assertEqual(-1,self.panels(self.page.locator('#root'),'batch')[0]['index'])
    def test_limit_applies_before_filter(self):
        self.page.set_content('<style>div{height:90px;width:100px;overflow:auto}div:after{content:"";display:block;height:200px}</style>'+('<span></span>'*1999)+'<div id="last"></div><div id="excluded"></div>')
        self.assertEqual([1999],[x['index'] for x in self.panels(self.page,'batch')])
        self.assertEqual([x['key'] for x in self.panels(self.page,'legacy')],[x['key'] for x in self.panels(self.page,'batch')])
    def test_replaced_candidate_is_not_interacted_with(self):
        self.page.set_content('<div style="width:100px;height:90px;overflow:auto"><p style="height:200px">a</p></div>')
        candidate=self.panels(self.page,'batch')[0]
        self.assertTrue(hasattr(navigation,'resolve_panel'),'Candidate identity check missing')
        self.page.locator('div').evaluate('e=>e.outerHTML=e.outerHTML')
        self.assertIsNone(navigation.resolve_panel(self.page,self.page,candidate))
    def test_removed_candidate_becomes_an_unresolved_identity(self):
        self.page.set_content('<div style="width:100px;height:90px;overflow:auto"><p style="height:200px">a</p></div>')
        candidate=self.panels(self.page,'batch')[0];self.page.locator('div').evaluate('e=>e.remove()')
        failure=None
        try: result=navigation.resolve_panel(self.page,self.page,candidate)
        except Exception as error: failure=error;result='unexpected failure'
        self.assertIsNone(failure,'A missing candidate must trigger bounded rescan, not abort navigation')
        self.assertIsNone(result)
    def tracker(self):
        self.assertTrue(hasattr(navigation,'ImageTracker'),'Terminal generation observer missing')
        tracker=navigation.ImageTracker(self.page);tracker.install();return tracker
    def test_terminal_error_skips_wait_but_remains_unavailable(self):
        tracker=self.tracker()
        self.page.route('https://fixture.test/**',lambda r:r.fulfill(status=404,body='missing'))
        self.page.goto('data:text/html,<img width="100" height="100" src="https://fixture.test/missing.png">')
        self.page.wait_for_timeout(80)
        with patch.object(self.page,'wait_for_function',wraps=self.page.wait_for_function) as wait:
            self.assertFalse(tracker.wait());self.assertFalse(tracker.wait())
            self.assertEqual(0,wait.call_count)
    def test_same_url_retry_and_new_node_reopen_pending_750(self):
        tracker=self.tracker();calls=[]
        self.page.route('https://fixture.test/**',lambda r:r.fulfill(status=404,body='missing'))
        self.page.goto('data:text/html,<img width="100" height="100" src="https://fixture.test/missing.png">');self.page.wait_for_timeout(80)
        self.assertFalse(tracker.wait())
        # Observe a new request without relying on the browser cache to issue a retry.
        tracker.note_request('https://fixture.test/missing.png')
        with patch.object(self.page,'wait_for_function',side_effect=lambda *a,**kw:calls.append(kw['timeout'])):
            self.assertFalse(tracker.wait());self.assertFalse(tracker.wait())
        self.assertEqual([750,750],calls)
        self.page.locator('img').evaluate('e=>e.outerHTML="<img width=100 height=100>"')
        with patch.object(self.page,'wait_for_function',side_effect=lambda *a,**kw:calls.append(kw['timeout'])):
            self.assertFalse(tracker.wait())
        self.assertEqual(750,calls[-1])
    def test_src_change_reopens_pending(self):
        tracker=self.tracker();self.page.route('https://fixture.test/**',lambda r:r.fulfill(status=404,body='missing'))
        self.page.goto('data:text/html,<img width=100 height=100 src="https://fixture.test/old.png">');self.page.wait_for_timeout(80)
        self.assertFalse(tracker.wait())
        pending=[]
        self.page.route('https://fixture.test/new.png',lambda route:pending.append(route))
        self.page.locator('img').evaluate('e=>e.src="https://fixture.test/new.png"');self.page.wait_for_timeout(30)
        self.assertEqual(1,len(pending))
        with patch.object(self.page,'wait_for_function',side_effect=TimeoutError) as wait:
            tracker.wait();self.assertIsNotNone(wait.call_args);self.assertEqual(750,wait.call_args.kwargs['timeout'])
        pending[0].abort();self.page.wait_for_timeout(30)
    def test_collector_switches_are_explicit(self):
        self.assertIn('panel_scan',inspect.signature(discovery.collect).parameters)
        self.assertIn('image_wait_policy',inspect.signature(discovery.continue_collect).parameters)
