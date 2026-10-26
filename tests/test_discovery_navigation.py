"""Navigation obligations, exercised against real browser/local HTTP fixtures."""
from functools import partial
from http.server import ThreadingHTTPServer
import importlib
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from test_discovery import FixtureHandler

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'skills/proposition/scripts'))
from proposition_runtime import discovery


class NavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(FixtureHandler, directory=str(REPO/'tests/fixtures/site')))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name).resolve()/'capture'

    def test_delayed_banner_is_dismissed_and_menu_states_are_closed(self):
        report = discovery.collect(self.base+'/navigation-contract.html', self.out, allow_local=True, max_pages=1)
        for page in report['pages']:
            self.assertEqual('complete', page.get('exploration', {}).get('status'), page)
            actions = page.get('interactions', [])
            self.assertTrue(any(x['kind']=='overlay' and x['status']=='resolved' for x in actions), actions)
            menus = [x for x in actions if x['kind']=='menu']
            self.assertGreaterEqual(len(menus), 2)
            self.assertTrue(all(x['opened'] and x['closed'] for x in menus), menus)
            self.assertFalse(any('OVERLAPPING-PEER-MENUS' in (self.out/e['text_path']).read_text() for e in page['evidence']))
        self.assertTrue(any(e['url'].endswith('/nested.html') for e in report['link_entries']))

    def test_long_page_and_inner_scroll_have_visible_bottom_and_loaded_images(self):
        report = discovery.collect(self.base+'/navigation-contract.html', self.out, allow_local=True, max_pages=1)
        for page in report['pages']:
            scroll = page.get('exploration', {}).get('scroll', {})
            self.assertTrue(scroll.get('reached_end'), scroll)
            self.assertTrue(any(e.get('scroll_y',0) >= 12000 and e.get('screenshot_path') for e in page['evidence']))
            self.assertTrue(any(x.get('kind')=='inner_scroll' and x['status']=='resolved' for x in page.get('interactions',[])))
            self.assertTrue(any(e.get('visible_images') and any(i.get('alt')=='LATE-IMAGE' and i.get('loaded') for i in e['visible_images']) for e in page['evidence']))

    def test_undismissable_overlay_stays_partial_with_resumable_obligations(self):
        report = discovery.collect(self.base+'/blocked-navigation.html', self.out, allow_local=True, max_pages=1)
        self.assertEqual('partial', report['status'])
        self.assertEqual({'desktop','mobile'}, {x['viewport'] for x in report['coverage'].get('pending_states',[])})
        self.assertTrue(all(p.get('exploration',{}).get('status')=='partial' for p in report['pages']))

    def test_scroll_ceiling_does_not_masquerade_as_complete_and_can_resume(self):
        with patch.object(discovery, 'MAX_SCROLL_STEPS', 2):
            first = discovery.collect(self.base+'/navigation-contract.html', self.out, allow_local=True, max_pages=1)
        self.assertEqual('partial', first['status'])
        self.assertTrue(first['coverage'].get('pending_states'))
        second = discovery.continue_collect(self.out/'discovery.json', self.out.parent/'resume', allow_local=True, max_pages=1)
        views = [p for p in second['pages'] if p['requested_url'].endswith('/navigation-contract.html')]
        self.assertEqual({'desktop','mobile'}, {p['viewport'] for p in views})
        self.assertTrue(all(p.get('exploration',{}).get('status')=='complete' for p in views))

    def test_missing_capture_cannot_be_a_complete_exploration(self):
        from playwright.sync_api import Page
        with patch.object(Page, 'screenshot', side_effect=TimeoutError('fixture screenshot unavailable')):
            report=discovery.collect(self.base+'/desktop.html', self.out, allow_local=True, max_pages=1)
        self.assertEqual('partial', report['status'])
        self.assertTrue(report['sources'])
        self.assertTrue(all(p.get('exploration',{}).get('status')=='partial' for p in report['pages']))

    def test_scrollable_menu_is_observed_before_being_closed(self):
        report=discovery.collect(self.base+'/menu-scroll.html',self.out,allow_local=True,max_pages=1)
        for page in report['pages']:
            panels=[a for a in page['interactions'] if a['kind']=='inner_scroll']
            self.assertTrue(panels)
            self.assertTrue(all(a['status']=='resolved' and a['end_y']+a['viewport_height']>=a['height']-2 for a in panels))

    def test_hover_ceiling_leaves_an_explicit_obligation(self):
        report=discovery.collect(self.base+'/hover-limit.html',self.out,allow_local=True,max_pages=1)
        self.assertEqual('partial',report['status'])
        self.assertTrue(any('hover_menu_budget_exhausted' in p.get('exploration',{}).get('unresolved',[]) for p in report['pages']))


if __name__=='__main__': unittest.main()
