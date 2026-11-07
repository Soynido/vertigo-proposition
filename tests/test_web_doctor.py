"""Web readiness needs both real browser engines; documentary behavior is kept."""
from unittest.mock import patch,MagicMock
import unittest
from proposition_runtime import cli


class WebDoctorTests(unittest.TestCase):
    def probe(self,webkit_available):
        browser=MagicMock(version='fixture-browser')
        runtime=MagicMock()
        if webkit_available:runtime.__enter__.return_value.webkit.launch.return_value=browser
        else:runtime.__enter__.return_value.webkit.launch.side_effect=RuntimeError('Not installed')
        with patch('playwright.sync_api.sync_playwright',return_value=runtime), \
             patch('proposition_runtime.browser.launch_browser',return_value=(browser,'fixture')):
            return cli.doctor(delivery_format='web')

    def test_a_missing_second_engine_blocks_web_readiness(self):
        result=self.probe(False)
        self.assertEqual(result['status'],'BLOCKED')
        self.assertEqual(result['browsers']['webkit']['status'],'UNAVAILABLE')
        self.assertEqual(result['creative_quality'],'NOT_RUN')

    def test_two_engines_pass_only_local_readiness_not_autonomous_delivery(self):
        result=self.probe(True)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(set(result['browsers']),{'chromium','webkit'})
        self.assertEqual(result['live_publication'],'NOT_RUN')
        self.assertEqual(result['host_capabilities'],'NOT_VERIFIED_BY_RUNTIME')


if __name__=='__main__':unittest.main()
