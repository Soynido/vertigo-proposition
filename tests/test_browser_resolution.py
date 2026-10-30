"""Browser selection, with only the external launch operation simulated."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from proposition_runtime import async_discovery


class BrowserResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_can_use_installed_chromium_when_chrome_is_absent(self):
        launch=getattr(async_discovery,'alaunch_browser',None)
        self.assertTrue(callable(launch),'The actual collector needs the shared browser resolver')
        available=SimpleNamespace(version='fixture-chromium')
        async def external_launch(**options):
            if options.get('channel')=='chrome': raise RuntimeError('not installed')
            return available
        engine=SimpleNamespace(chromium=SimpleNamespace(launch=external_launch))
        with patch.dict('os.environ',{},clear=True):
            browser,selected=await launch(engine)
        self.assertIs(available,browser)
        self.assertEqual('chromium',selected)

    async def test_explicit_unavailable_channel_is_not_silently_substituted(self):
        launch=getattr(async_discovery,'alaunch_browser',None)
        self.assertTrue(callable(launch),'The actual collector needs the shared browser resolver')
        async def external_launch(**options):
            if options.get('channel')=='unavailable-explicit': raise RuntimeError('not installed')
            return SimpleNamespace(version='other-browser')
        engine=SimpleNamespace(chromium=SimpleNamespace(launch=external_launch))
        with patch.dict('os.environ',{'PROPOSITION_BROWSER_CHANNEL':'unavailable-explicit'},clear=True):
            with self.assertRaises(RuntimeError): await launch(engine)
