"""Unchanged native film packets and actual forward/backward canvas decoding."""
from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from playwright.sync_api import sync_playwright
from proposition_runtime import web,state,cli
from proposition_runtime.browser import launch_browser
from proposition_runtime.web_inspection import serve_bundle

KIT=Path(__file__).resolve().parents[1]/'skills/proposition/resources/web'


def make_film(path):
    subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i','color=c=red:s=32x32:r=10:d=1',
        '-f','lavfi','-i','color=c=blue:s=32x32:r=10:d=1',
        '-filter_complex','[0:v][1:v]concat=n=2:v=1:a=0,format=yuv420p',
        '-c:v','libx264','-g','5','-bf','0',str(path)],check=True,timeout=15)


class WebMediaTests(unittest.TestCase):
    engine='chromium'
    def setUp(self):
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('Native film fixture tools unavailable; media capability not qualified')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.film=self.root/'film.mp4';make_film(self.film)

    def index(self):
        self.assertTrue(callable(getattr(web,'index_film',None)), 'No unchanged-film packet preparation')
        return web.index_film(self.film,self.root/'film.mp4.frames.json')

    def test_installed_cli_indexes_run_film_without_replacing_its_bytes(self):
        run=state.init_run('https://fixture.example/',self.root/'runs',delivery_format='web')
        root=Path(run['root']);source=root/'film.mp4';source.write_bytes(self.film.read_bytes())
        target=root/'film.mp4.frames.json'
        result=cli.execute(cli.parser().parse_args(['web','media-index',str(root),
            '--source',str(source),'--output',str(target)]))
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(json.loads(target.read_text())['sha256'],web._sha(source))
        with self.assertRaises(ValueError):
            cli.execute(cli.parser().parse_args(['web','media-index',str(root),
                '--source',str(self.film),'--output',str(target)]))

    def test_index_preserves_source_bytes_and_rejects_replacement(self):
        before=self.film.read_bytes();result=self.index()
        self.assertEqual(self.film.read_bytes(),before)
        self.assertEqual(result['status'],'PASS')
        index=json.loads((self.root/'film.mp4.frames.json').read_text())
        self.assertEqual(index['sha256'],web._sha(self.film))
        self.assertEqual(len(index['packets']),20)
        self.assertAlmostEqual(index['duration'],2,delta=.02)
        self.assertTrue(index['codec'].startswith('avc1.'))
        # The same operation may reuse bytes, but it may not overwrite a different index.
        self.assertEqual(self.index(),result)
        self.film.write_bytes(b'not the indexed film')
        with self.assertRaises(ValueError):self.index()

    def test_actual_frame_decoder_presents_red_blue_red_on_direction_reversal(self):
        self.index()
        self.assertTrue((KIT/'scroll-frames.mjs').is_file(), 'Reference decoder not ported')
        with sync_playwright() as playwright, ExitStack() as resources:
            public=self.root/'.vercel/output/static';public.mkdir(parents=True)
            for name in ('film.mp4','film.mp4.frames.json'):
                (public/name).write_bytes((self.root/name).read_bytes())
            (public/'scroll-frames.mjs').write_bytes((KIT/'scroll-frames.mjs').read_bytes())
            (public/'index.html').write_text('''<!doctype html><canvas width="32" height="32"></canvas>
                <script type="module">import{createScrollFrames,createMediaReader}from'./scroll-frames.mjs';
                const signal=new AbortController().signal,canvas=document.querySelector('canvas'),ctx=canvas.getContext('2d');
                window.failed=false;window.painted=-1;
                window.player=await createScrollFrames('./film.mp4',signal,p=>{
                    ctx.drawImage(p.image,0,0);window.painted=p.time;
                },()=>{window.failed=true},createMediaReader('./film.mp4'),{maxEncodedBytes:512});
                window.ready=true;</script>''')
            browser=launch_browser(playwright)[0] if self.engine=='chromium' else playwright.webkit.launch(headless=True)
            resources.callback(browser.close)
            context=browser.new_context();resources.callback(context.close)
            with serve_bundle(self.root,{'entrypoint':'index.html'}) as origin:
                page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(origin);page.wait_for_function('()=>window.ready',timeout=5000)
                self.assertEqual(errors,[])
                self.assertTrue(page.evaluate('Boolean(window.player)'), 'H.264 WebCodecs unavailable on this tested browser')
                self.assertTrue(page.evaluate('Boolean(player.stats)'), 'Encoded-packet buffer has no observable budget')
                for time,want in [(.2,'red'),(1.5,'blue'),(.2,'red')]:
                    page.evaluate('(time)=>player.seek(time)',time)
                    page.wait_for_function('(time)=>Math.abs(window.painted-time)<.12',arg=time,timeout=5000)
                    pixel=page.locator('canvas').evaluate('(c)=>Array.from(c.getContext("2d").getImageData(16,16,1,1).data)')
                    self.assertGreater(pixel[0 if want=='red' else 2],200,pixel)
                    self.assertLess(pixel[2 if want=='red' else 0],40,pixel)
                    self.assertLessEqual(page.evaluate('player.stats.encodedBytes'),512)
                    self.assertLessEqual(page.evaluate('player.stats.decodedFrames'),24)
                self.assertFalse(page.evaluate('window.failed'))
                page.evaluate('player.destroy()')

    def test_build_refuses_an_index_for_a_different_film(self):
        self.index()
        (self.root/'index.html').write_text('<!doctype html><video src="film.mp4" controls></video>')
        (self.root/'sources.html').write_text('<!doctype html><p>Film de test, créé localement.</p>')
        index_path=self.root/'film.mp4.frames.json'
        index=json.loads(index_path.read_text());index['sha256']='0'*64
        index_path.write_text(json.dumps(index))
        plan={'version':1,'entrypoint':'index.html','sources_page':'sources.html',
              'public_files':['index.html','sources.html','film.mp4','film.mp4.frames.json']}
        with self.assertRaises(ValueError):web.build_bundle(self.root,self.root/'bundle',plan)
        self.assertFalse((self.root/'bundle').exists())

class WebKitMediaTests(WebMediaTests):
    engine='webkit'


if __name__=='__main__':unittest.main()
