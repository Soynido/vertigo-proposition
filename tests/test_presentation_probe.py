"""A local presentation tool is ready only after a real editable/rendered fixture."""
import importlib
import importlib.util
import unittest
from unittest.mock import patch


class PresentationProbeTests(unittest.TestCase):
    def module(self):
        name = 'proposition_runtime.presentation_probe'
        self.assertIsNotNone(importlib.util.find_spec(name), 'Presentation preflight has not been implemented')
        return importlib.import_module(name)

    def test_missing_renderer_blocks_instead_of_claiming_a_rendered_pptx(self):
        module = self.module()
        with patch.object(module.shutil, 'which', return_value=None):
            result = module.probe()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['rendering'], 'UNAVAILABLE')
        self.assertEqual(result['client_fidelity'], 'NOT_RUN')

    def test_missing_authoring_package_is_reported_without_a_fake_fixture(self):
        module = self.module()
        with patch.object(module.importlib.metadata, 'version',
                          side_effect=importlib.metadata.PackageNotFoundError('python-pptx')):
            result = module.probe()
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['authoring'], 'UNAVAILABLE')
        self.assertEqual(result['editing'], 'NOT_RUN')

    def test_real_fixture_is_edited_rendered_and_rasterized(self):
        module = self.module()
        inventory = module.inventory()
        if not inventory['python_pptx'] or not inventory['renderer']:
            self.skipTest('Optional presentation profile/renderer absent; real starter CI exercises it')
        result = module.probe()
        self.assertEqual(result['status'], 'PASS', result)
        self.assertEqual(result['editing'], 'PASS')
        self.assertEqual(result['rendering'], 'PASS')
        self.assertEqual(result['rasterization'], 'PASS')
        self.assertEqual(result['page_count'], 1)
        self.assertEqual(result['client_fidelity'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
