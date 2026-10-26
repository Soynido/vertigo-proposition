"""Browser selection, with only the external launch operation simulated."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from proposition_runtime import discovery


class BrowserResolutionTests(unittest.TestCase):
    def test_default_can_use_installed_chromium_when_chrome_is_absent(self):
        launch=getattr(discovery,'launch_browser',None)
        self.assertTrue(callable(launch),'The actual collector needs the shared browser resolver')
        available=SimpleNamespace(version='fixture-chromium')
        def external_launch(**options):
            if options.get('channel')=='chrome': raise RuntimeError('not installed')
            return available
        engine=SimpleNamespace(chromium=SimpleNamespace(launch=external_launch))
        with patch.dict('os.environ',{},clear=True):
            browser,selected=launch(engine)
        self.assertIs(available,browser)
        self.assertEqual('chromium',selected)

    def test_explicit_unavailable_channel_is_not_silently_substituted(self):
        launch=getattr(discovery,'launch_browser',None)
        self.assertTrue(callable(launch),'The actual collector needs the shared browser resolver')
        def external_launch(**options):
            if options.get('channel')=='unavailable-explicit': raise RuntimeError('not installed')
            return SimpleNamespace(version='other-browser')
        engine=SimpleNamespace(chromium=SimpleNamespace(launch=external_launch))
        with patch.dict('os.environ',{'PROPOSITION_BROWSER_CHANNEL':'unavailable-explicit'},clear=True):
            with self.assertRaises(RuntimeError): launch(engine)
