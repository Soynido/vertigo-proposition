"""Exercise the actual browser probe; no synthetic PASS or mock browser."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
from PIL import Image
from proposition_runtime import web
from web_fixture import prepare_web


class WebInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run,self.source,self.plan_path=prepare_web(self.tmp.name)
        self.plan=json.loads(self.plan_path.read_text());self.base=Path(self.tmp.name)

    def inspect(self):
        self.assertTrue(callable(getattr(web,'inspect_bundle',None)),
                        'The real active browser inspector is not implemented')
        bundle=self.base/'bundle';web.build_bundle(self.source,bundle,self.plan)
        return web.inspect_bundle(bundle,self.plan,self.base/'inspection',
            browsers=('chromium',),viewports=((1280,600),(390,844)))

    def test_real_module_and_scrolled_states_are_rendered_at_actual_dimensions(self):
        report=self.inspect()
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertEqual(report['creative_quality'],'NOT_ASSESSED')
        self.assertEqual(report['independent_review'],'NOT_RUN')
        self.assertTrue(report['captures'])
        self.assertEqual({tuple(c['viewport']) for c in report['captures']}, {(1280,600),(390,844)})
        for capture in report['captures']:
            with Image.open(self.base/'inspection'/capture['path']) as im:
                self.assertEqual(im.size,tuple(capture['viewport']))
        self.assertEqual(report['scenes'][0]['forward_states'],[0,.5,1])
        self.assertEqual(report['scenes'][0]['reverse_states'],[1,.5,0])
        self.assertTrue(any(r['reduced_motion'] for r in report['scenes']))

    def test_active_script_failure_is_reported_instead_of_certifying_a_poster(self):
        (self.source/'app.js').write_text('throw new Error("FIXTURE_SCRIPT_FAILURE")')
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any('FIXTURE_SCRIPT_FAILURE' in str(i) for i in report['issues']))

    def test_same_browser_probe_can_examine_an_already_served_origin(self):
        from proposition_runtime.web_inspection import serve_bundle
        bundle=self.base/'bundle';manifest=web.build_bundle(self.source,bundle,self.plan)
        with serve_bundle(bundle,manifest) as origin:
            report=web.inspect_bundle(bundle,self.plan,self.base/'inspection',
                browsers=('chromium',),viewports=((390,844),),origin=origin)
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertEqual(report['origin'],origin)
        self.assertEqual(report['authentication'],'none_fresh_browser_contexts')

    def test_dynamic_external_request_is_blocked_and_visible_in_receipt(self):
        (self.source/'app.js').write_text('fetch("https://outside.invalid/private-target").catch(()=>{});')
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='external_resource' for i in report['issues']))

    def test_invented_action_destination_or_invisible_sales_selector_fails(self):
        self.plan['actions'][0]['target']='https://different.invalid/'
        self.plan['coverage'][0]['selector']='#nonexistent'
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='action_target' for i in report['issues']))
        self.assertTrue(any(i['code']=='missing_content' for i in report['issues']))

    def test_captures_preserve_paused_scroll_animation_instead_of_fast_forwarding(self):
        (self.source/'app.js').write_text('''const layer=document.createElement('div');
            layer.id='animated-layer';layer.style.cssText='position:fixed;left:0;top:0;width:40px;height:40px;background:rgb(0,0,128);z-index:99';
            document.body.append(layer);const animation=layer.animate([{transform:'translateX(0px)'},{transform:'translateX(200px)'}],
            {duration:1000,fill:'both'});animation.pause();
            function update(){animation.currentTime=scrollY/(document.documentElement.scrollHeight-innerHeight)*1000}
            addEventListener('scroll',update);update();''')
        report=self.inspect()
        self.assertEqual(report['status'],'PASS',report['issues'])
        first=next(c for c in report['captures'] if c.get('progress')==0 and c.get('direction')=='forward')
        with Image.open(self.base/'inspection'/first['path']) as image:
            pixel=image.convert('RGB').getpixel((10,10))
            self.assertLess(pixel[0],30,pixel)
            self.assertGreater(pixel[2],90,pixel)

    def test_each_native_video_is_actually_decoded_not_only_the_first_one(self):
        ffmpeg=shutil.which('ffmpeg')
        if not ffmpeg:self.skipTest('ffmpeg unavailable: native-video fixture not qualified')
        for name,color in [('a','navy'),('b','green')]:
            target=self.source/('clip-'+name+'.mp4')
            subprocess.run([ffmpeg,'-loglevel','error','-f','lavfi','-i',
                'color=c='+color+':s=32x32:r=10','-t','1','-c:v','libx264',
                '-pix_fmt','yuv420p','-movflags','+faststart',str(target)],check=True,timeout=10)
            self.plan['public_files'].append(target.name)
        path=self.source/'index.html';path.write_text(path.read_text().replace('</main>',
            '<video src="clip-a.mp4" controls playsinline></video>'
            '<video src="clip-b.mp4" controls playsinline></video></main>'))
        report=self.inspect()
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertEqual(len(report['media']),6)
        self.assertEqual({Path(r['src']).name for r in report['media']},{'clip-a.mp4','clip-b.mp4'})
        self.assertTrue(all(r['time']>0 and not r['error'] for r in report['media']))

    def test_broken_video_is_not_replaced_by_an_unqualified_poster_success(self):
        target=self.source/'bad.mp4';target.write_bytes(b'not a video')
        self.plan['public_files'].append(target.name)
        path=self.source/'index.html';path.write_text(path.read_text().replace('</main>',
            '<video src="bad.mp4" poster="image.svg" controls></video></main>'))
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='video_decode' for i in report['issues']))

    def test_additional_public_html_and_its_scenes_are_really_examined(self):
        self.plan['public_files'].append('experience.html')
        (self.source/'experience.html').write_text('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><main style="height:220vh">Another experience</main><script>throw new Error("SECOND_PAGE_FAILURE")</script>')
        self.plan['scenes'].append(dict(self.plan['scenes'][0],id='experience',page='experience.html'))
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any('SECOND_PAGE_FAILURE' in str(i) for i in report['issues']))
        self.assertTrue(any(s.get('page')=='experience.html' and s['forward_states']==[0,.5,1]
                            for s in report['scenes']))

    def test_an_embedded_image_decode_failure_cannot_hide_behind_a_valid_top_document(self):
        (self.source/'embedded.html').write_text('<!doctype html><p>Embedded experience</p><img src="data:image/png;base64,YmFk" alt="broken fixture">')
        self.plan['public_files'].append('embedded.html')
        path=self.source/'index.html';path.write_text(path.read_text().replace('</main>',
            '<iframe title="Embedded fixture" src="embedded.html"></iframe></main>'))
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='image_decode' and 'frame' in i.get('context','') for i in report['issues']))

    def test_a_neutralized_link_or_keyboard_excluded_action_cannot_pass_from_its_href(self):
        path=self.source/'index.html';path.write_text(path.read_text().replace('id="quote"','id="quote" tabindex="-1"').replace('id="next"','id="next" onclick="event.preventDefault()"'))
        report=self.inspect()
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any(i['code']=='action_keyboard' for i in report['issues']))
        self.assertTrue(any(i['code']=='action_activation' for i in report['issues']))

    def test_a_custom_scroll_action_with_prevent_default_remains_observable(self):
        path=self.source/'index.html';path.write_text(path.read_text().replace('id="next"',
            'id="next" onclick="event.preventDefault();document.querySelector(\'#opening\').scrollIntoView({behavior:\'smooth\'});"'))
        self.plan['actions'][1]['target']='#opening'
        path.write_text(path.read_text().replace('href="#decision"','href="#opening"'))
        report=self.inspect()
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertTrue(report['actions'])

    def test_external_origins_use_browser_url_normalization_in_both_engines(self):
        path=self.source/'index.html';path.write_text(path.read_text().replace('https://fixture.example/quote','https://fixture.example').replace('</main>',
            '<a id="normalized" href="HTTPS://Fixture.Example:443/">Canonical origin action</a></main>'))
        self.plan['actions'][0]['target']='https://fixture.example'
        self.plan['actions'].append({'id':'normalized','selector':'#normalized','target':'HTTPS://Fixture.Example:443/','purpose':'prospect'})
        bundle=self.base/'bundle';web.build_bundle(self.source,bundle,self.plan)
        report=web.inspect_bundle(bundle,self.plan,self.base/'inspection',browsers=('chromium','webkit'),viewports=((390,844),))
        self.assertEqual(report['status'],'PASS',report['issues'])
        self.assertTrue(report['actions'])
        self.assertTrue(all(r['activated'] for r in report['actions']))


if __name__=='__main__':unittest.main()
