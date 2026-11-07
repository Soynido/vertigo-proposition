"""Bounded range transport for a large media file; not an H264 decode test."""
from pathlib import Path
import shutil
import tempfile
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from proposition_runtime.web_inspection import serve_bundle
from proposition_runtime.browser import launch_browser

MODULE=Path(__file__).resolve().parents[1]/'skills/proposition/resources/web/scroll-frames.mjs'


class WebRangeTests(unittest.TestCase):
    def test_large_media_range_is_exact_and_readable_without_allocating_the_whole_film(self):
        from playwright.sync_api import sync_playwright
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);public=root/'.vercel/output/static';public.mkdir(parents=True)
            (public/'index.html').write_text('<!doctype html><title>Range transport fixture</title>')
            shutil.copyfile(MODULE,public/'scroll-frames.mjs')
            with (public/'large.bin').open('wb') as stream:
                for _ in range(128):stream.write(b'0'*65536)
                stream.write(b'Z')
            size=8*1024*1024+1
            with serve_bundle(root,{'entrypoint':'index.html'}) as origin,sync_playwright() as pw:
                for engine in ['chromium','webkit']:
                    browser=launch_browser(pw)[0] if engine=='chromium' else pw.webkit.launch(headless=True)
                    try:
                        page=browser.new_page();page.goto(origin+'/')
                        result=page.evaluate('''async size=>{try{
                            const{createMediaReader}=await import('./scroll-frames.mjs');
                            return {bytes:[...await createMediaReader('./large.bin')(size-3,3,new AbortController().signal)]};
                        }catch(e){return{error:String(e)}}}''',size)
                        self.assertEqual(result,{'bytes':[48,48,90]},engine+' '+str(result))
                    finally:browser.close()
                with urlopen(Request(origin+'/large.bin',headers={'Range':'bytes=0-2'})) as response:
                    self.assertEqual(response.status,206)
                    self.assertEqual(response.headers['Content-Range'],f'bytes 0-2/{size}')
                    self.assertEqual(response.read(),b'000')
                with self.assertRaises(HTTPError) as failed:
                    urlopen(Request(origin+'/large.bin',headers={'Range':f'bytes={size}-'}))
                self.assertEqual(failed.exception.code,416)

if __name__=='__main__':unittest.main()
