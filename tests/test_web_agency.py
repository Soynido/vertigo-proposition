"""Versioned agency assets must load without styling the prospect's own scene."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from proposition_runtime.web_inspection import serve_bundle
from proposition_runtime.browser import launch_browser

ASSETS=Path(__file__).resolve().parents[1]/'skills/proposition/resources/web/agency'


class AgencyAssetsTests(unittest.TestCase):
    def test_all_distributed_agency_asset_bytes_match_their_provenance_manifest(self):
        manifest=json.loads((ASSETS/'MANIFEST.json').read_text())
        self.assertFalse(manifest['files'][0]['source_font_redistributed'])
        for row in manifest['files']:
            data=(ASSETS/row['path']).read_bytes()
            self.assertEqual(len(data),row['size_bytes'],row['path'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'],row['path'])

    def test_fonts_logo_and_white_frame_load_in_both_engines_without_leaking_into_client_styles(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);public=root/'.vercel/output/static';public.mkdir(parents=True)
            shutil.copytree(ASSETS,public/'agency')
            (public/'index.html').write_text('''<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Agency mechanics fixture</title>
                <link rel="stylesheet" href="agency/agency.css"><style>body{margin:0}#client{font-family:serif;background:rgb(10,20,30);color:white}</style>
                <header data-vertigo-agency><div class="vg-frame vg-header"><img class="vg-wordmark" src="agency/vertigo-wordmark.png" alt="VERTIGO"><p>Une proposition à explorer</p></div></header>
                <main id="client"><h1>Own client identity</h1></main></html>''')
            with serve_bundle(root,{'entrypoint':'index.html'}) as origin,sync_playwright() as pw:
                for engine in ['chromium','webkit']:
                    browser=launch_browser(pw)[0] if engine=='chromium' else pw.webkit.launch(headless=True)
                    try:
                        page=browser.new_page(viewport={'width':390,'height':844})
                        page.goto(origin+'/index.html',wait_until='load')
                        page.evaluate('document.fonts.ready')
                        self.assertTrue(page.evaluate('document.fonts.check(\'16px "Vertigo Poppins"\')'),engine)
                        self.assertEqual(page.locator('[data-vertigo-agency]').evaluate('(n)=>getComputedStyle(n).backgroundColor'),'rgb(255, 255, 255)')
                        self.assertEqual(page.locator('#client').evaluate('(n)=>getComputedStyle(n).backgroundColor'),'rgb(10, 20, 30)')
                        self.assertNotIn('Poppins',page.locator('#client').evaluate('(n)=>getComputedStyle(n).fontFamily'))
                        self.assertTrue(page.locator('img').evaluate('(n)=>n.complete && n.naturalWidth>0'))
                        self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth+1'))
                    finally:browser.close()

if __name__=='__main__':unittest.main()
