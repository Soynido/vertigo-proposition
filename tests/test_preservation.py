"""Catch loss/substitution at composition, not just presence in an asset folder."""
import json
from pathlib import Path
import tempfile
import unittest
from proposition_runtime import state
from creative_fixture import selection, make_outputs, make_scene


class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://example.test/',Path(self.tmp.name)/'runs')
        self.root=Path(self.run['root'])

    def freeze(self):
        from proposition_runtime import preservation
        preservation.freeze_creatives(self.root,selection(self.root))
        make_outputs(self.root)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        state.add_artifact(self.root,'creative-placements','placements.json','internal')
        return preservation

    def codes(self):
        report=state.stage_report(self.root,'client.composition')
        return {i['code'] for i in report['issues']}

    def test_missing_selection_blocks_even_without_other_stage_evidence(self):
        self.assertIn('creative_preservation',self.codes())

    def test_exact_scene_in_both_outputs_passes_preservation(self):
        p=self.freeze()
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'PASS')
        self.assertNotIn('creative_preservation',self.codes())

    def test_omitted_creative_blocks_composition_and_global_validation(self):
        self.freeze()
        data=json.loads((self.root/'placements.json').read_text()); data['placements']=[]
        (self.root/'placements.json').write_text(json.dumps(data))
        state.add_artifact(self.root,'creative-placements','placements.json','internal')
        self.assertIn('creative_preservation',self.codes())
        self.assertIn('creative_preservation',{i['code'] for i in state.validate_run(self.root)['issues']})

    def test_replacement_in_final_files_is_not_saved_by_original_in_folder(self):
        p=self.freeze(); make_scene(self.root,'replacement.png','green')
        make_outputs(self.root,'replacement.png')
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        report=p.inspect_preservation(state.load_run(self.root))
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any('pixels' in i or 'image' in i for i in report['issues']))

    def test_pdf_substitution_alone_blocks(self):
        p=self.freeze(); original=(self.root/'client.pptx').read_bytes()
        make_scene(self.root,'replacement.png','green'); make_outputs(self.root,'replacement.png')
        (self.root/'client.pptx').write_bytes(original)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_hidden_powerpoint_image_blocks_even_with_good_pdf(self):
        p=self.freeze(); make_outputs(self.root,hidden=True)
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_source_mutation_and_lock_replacement_are_rejected(self):
        p=self.freeze(); make_scene(self.root,color='green')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')
        with self.assertRaises(ValueError): p.freeze_creatives(self.root,selection(self.root))

    def test_thumbnail_and_destructive_crop_are_rejected(self):
        p=self.freeze()
        data=json.loads((self.root/'placements.json').read_text()); data['placements'][0]['rect']=[.1,.2,.02,.02]
        (self.root/'placements.json').write_text(json.dumps(data))
        state.add_artifact(self.root,'creative-placements','placements.json','internal')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_replacing_lock_bytes_cannot_remove_a_retained_scene(self):
        p=self.freeze()
        lock=self.root/'creative-selection.lock.json'
        data=json.loads(lock.read_text()); data['retained']=[]; lock.write_text(json.dumps(data))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_manifest_cannot_validate_good_decoys_instead_of_registered_outputs(self):
        p=self.freeze()
        (self.root/'decoy.pdf').write_bytes((self.root/'client.pdf').read_bytes())
        data=json.loads((self.root/'placements.json').read_text()); data['pdf']='decoy.pdf'
        (self.root/'placements.json').write_text(json.dumps(data))
        state.add_artifact(self.root,'creative-placements','placements.json','internal')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_modified_final_output_cannot_use_an_old_receipt(self):
        p=self.freeze()
        with (self.root/'client.pdf').open('ab') as f: f.write(b'\n% changed')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_changed_final_bytes_are_checked_after_reregistration(self):
        p=self.freeze(); make_scene(self.root,'replacement.png','green')
        make_outputs(self.root,'replacement.png')
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def rewrite_slide(self, transform):
        import zipfile
        path=self.root/'client.pptx'
        with zipfile.ZipFile(path) as z: files={name:z.read(name) for name in z.namelist()}
        files['ppt/slides/slide1.xml']=transform(files['ppt/slides/slide1.xml'].decode()).encode()
        with zipfile.ZipFile(path,'w') as z:
            for name,value in files.items(): z.writestr(name,value)
        state.add_artifact(self.root,'client-pptx','client.pptx','client')

    def test_hidden_slide_cannot_count_as_preserved(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('<p:sld xmlns:', '<p:sld show="0" xmlns:',1))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_picture_geometry_cannot_clip_retained_scene(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('</p:spPr>', '<a:prstGeom prst="ellipse"/></p:spPr>'))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_pptx_only_replacement_blocks_even_with_good_pdf(self):
        p=self.freeze(); pdf=(self.root/'client.pdf').read_bytes()
        make_scene(self.root,'replacement.png','green'); make_outputs(self.root,'replacement.png')
        (self.root/'client.pdf').write_bytes(pdf)
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        report=p.inspect_preservation(state.load_run(self.root))
        self.assertEqual(report['status'],'BLOCKED')
        self.assertIn('PowerPoint image was replaced',report['issues'])

    def test_approved_crop_cannot_be_silently_changed(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('<a:blip r:embed="im1"/>','<a:blip r:embed="im1"/><a:srcRect l="20000"/>'))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_freeze_rejects_destructive_crop(self):
        from proposition_runtime import preservation
        data=selection(self.root); data['retained'][0]['crop']=[0,0,.1,.1]
        with self.assertRaisesRegex(ValueError,'half'): preservation.freeze_creatives(self.root,data)

    def test_pptx_fill_cannot_shrink_image_inside_a_large_frame(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('<a:fillRect/>','<a:fillRect l="45000" t="45000" r="45000" b="45000"/>'))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_local_element_erasure_in_pdf_cannot_hide_in_average_error(self):
        from PIL import Image, ImageDraw
        p=self.freeze(); pptx=(self.root/'client.pptx').read_bytes()
        image=Image.open(self.root/'scene.png').convert('RGB')
        ImageDraw.Draw(image).rectangle((20,20,49,59),fill='navy'); image.save(self.root/'erased.png')
        make_outputs(self.root,'erased.png'); (self.root/'client.pptx').write_bytes(pptx)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        report=p.inspect_preservation(state.load_run(self.root))
        self.assertEqual(report['status'],'BLOCKED')
        self.assertTrue(any('local' in issue for issue in report['issues']))

    def test_painted_outline_cannot_cover_the_retained_image(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('</p:spPr>','<a:ln w="20000000"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill></a:ln></p:spPr>'))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'BLOCKED')

    def test_pdf_jpeg_reencoding_is_not_treated_as_content_loss(self):
        from PIL import Image
        p=self.freeze(); pptx=(self.root/'client.pptx').read_bytes()
        Image.open(self.root/'scene.png').convert('RGB').save(self.root/'compressed.jpg',quality=90)
        make_outputs(self.root,'compressed.jpg'); (self.root/'client.pptx').write_bytes(pptx)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'PASS')

    def test_retaining_three_directions_cannot_silently_turn_into_one(self):
        from proposition_runtime import preservation
        data=selection(self.root)
        data['retained'] += [dict(data['retained'][0],id='second'),dict(data['retained'][0],id='third')]
        preservation.freeze_creatives(self.root,data); make_outputs(self.root)
        state.add_artifact(self.root,'client-pdf','client.pdf','client')
        state.add_artifact(self.root,'client-pptx','client.pptx','client')
        state.add_artifact(self.root,'creative-placements','placements.json','internal')
        self.assertIn('creative_preservation',self.codes())

    def test_cli_returns_nonzero_for_loss_and_zero_for_exact_final_files(self):
        import contextlib
        import io
        from proposition_runtime.cli import main
        self.freeze()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['check-creatives',str(self.root)]),0)
            (self.root/'placements.json').write_text('{}')
            self.assertEqual(main(['check-creatives',str(self.root)]),2)

    def test_implicit_full_stretch_from_presentation_exporter_is_supported(self):
        p=self.freeze()
        self.rewrite_slide(lambda s:s.replace('<a:stretch><a:fillRect/></a:stretch>','<a:stretch/>'))
        self.assertEqual(p.inspect_preservation(state.load_run(self.root))['status'],'PASS')
