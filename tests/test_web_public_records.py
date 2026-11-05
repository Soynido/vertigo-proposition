"""A creator can resolve cited public evidence without an internal audit dump."""
import json
from pathlib import Path
import tempfile
import unittest
from proposition_runtime import state,web_inputs
from web_fixture import prepare_web


class WebPublicRecordsTests(unittest.TestCase):
    def test_only_cited_public_provenance_is_projected_without_raw_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,_,_=prepare_web(tmp);root=Path(run['root'])
            self.assertTrue(callable(getattr(web_inputs,'public_records',None)),'Cited evidence mapping is missing')
            private=root/'private.txt';private.write_text('PRIVATE_SENTINEL')
            state.add_source(root,'private-unrelated',private,kind='private',audience='internal')
            result=web_inputs.public_records(state.load_run(root))
            self.assertIn('source:experience-source',result)
            self.assertNotIn('source:private-unrelated',result)
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(result))
            self.assertFalse(any('path' in row for row in result.values()))
            self.assertEqual(result['source:experience-source']['raw_file_included'],False)


if __name__=='__main__':unittest.main()
