"""An active web bundle is explicit, portable, immutable, and contains no run state."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    from proposition_runtime import web
except ImportError:
    web = None


class WebBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base/'source'
        self.source.mkdir()
        (self.source/'index.html').write_text('<!doctype html><html lang="fr"><head>'
            '<title>Fixture indépendante</title><link rel="stylesheet" href="style.css">'
            '</head><body><main><h1>Un matériau à explorer</h1>'
            '<img src="image.svg" alt="Illustration géométrique">'
            '<a href="sources.html">Sources</a></main>'
            '<script type="module" src="app.js"></script></body></html>')
        (self.source/'sources.html').write_text('<!doctype html><title>Sources</title><p>Illustration de test.</p>')
        (self.source/'style.css').write_text('body{margin:0} img{width:160px}')
        (self.source/'app.js').write_text('document.documentElement.dataset.interactive="yes";')
        (self.source/'image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160"><rect width="160" height="160" fill="navy"/></svg>')
        (self.source/'private.txt').write_text('PRIVATE_SENTINEL')
        self.plan = {'version':1,'entrypoint':'index.html','sources_page':'sources.html',
            'public_files':['index.html','sources.html','style.css','app.js','image.svg']}

    def build(self, destination=None):
        self.assertIsNotNone(web, 'Active static build is not implemented')
        return web.build_bundle(self.source, destination or self.base/'bundle', self.plan)

    def test_active_module_is_bundled_without_pdf_and_without_unlisted_files(self):
        report = self.build()
        public = self.base/'bundle/.vercel/output/static'
        self.assertTrue((public/'app.js').is_file())
        self.assertFalse((public/'private.txt').exists())
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(report))
        self.assertEqual(json.loads((self.base/'bundle/.vercel/output/config.json').read_text()), {'version':3})
        self.assertEqual(report['scope'], 'static_build_only')
        self.assertEqual(report['creative_quality'], 'NOT_ASSESSED')
        self.assertEqual(web.verify_bundle(self.base/'bundle')['status'], 'PASS')

    def test_changed_asset_or_added_file_invalidates_exact_bundle(self):
        self.build()
        public = self.base/'bundle/.vercel/output/static'
        (public/'app.js').write_text('changed')
        with self.assertRaises(ValueError):web.verify_bundle(self.base/'bundle')

    def test_existing_destination_is_not_overwritten(self):
        self.build()
        with self.assertRaises(ValueError):self.build()
        self.assertEqual((self.base/'bundle/.vercel/output/static/app.js').read_text(),
                         'document.documentElement.dataset.interactive="yes";')

    def test_missing_or_external_required_resource_fails_before_promotion(self):
        for resource in ('missing.js','https://outside.invalid/app.js','file:///etc/passwd'):
            with self.subTest(resource=resource):
                (self.source/'index.html').write_text('<script src="'+resource+'"></script>')
                with self.assertRaises(ValueError):self.build()
                self.assertFalse((self.base/'bundle').exists())

    def test_private_paths_and_symlinks_cannot_enter_explicit_public_list(self):
        self.assertIsNotNone(web, 'Active static build is not implemented')
        (self.source/'state.json').write_text('{}')
        (self.source/'linked.svg').symlink_to(self.source/'image.svg')
        for name in ('../private.txt','state.json','linked.svg','.env'):
            with self.subTest(path=name):
                plan = dict(self.plan, public_files=self.plan['public_files']+[name])
                with self.assertRaises(ValueError):web.build_bundle(self.source,self.base/'bundle',plan)

    def test_sources_page_and_entrypoint_must_be_in_the_public_list(self):
        self.assertIsNotNone(web, 'Active static build is not implemented')
        for field in ('entrypoint','sources_page'):
            with self.subTest(field=field):
                plan = dict(self.plan, **{field:'not-in-public-list.html'})
                with self.assertRaises(ValueError):web.build_bundle(self.source,self.base/'bundle',plan)


if __name__ == '__main__':unittest.main()
