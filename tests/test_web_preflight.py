"""Before research, fail on absent credentials or wrong hosting without a write."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from proposition_runtime import state,web_publication as publication


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.policy={'version':1,'authority':'workspace_publication_policy','owner':'owner',
            'project_id':'prj_fixture','org_id':'team_fixture','target':'preview',
            'credential_ref':'env:VERTIGO_TEST_CREDENTIAL'}
        self.path=self.root/'policy.json';self.path.write_text(json.dumps(self.policy))
        self.run=state.init_run('https://fixture.example/',self.root/'runs',delivery_format='web',
            profile={'responsible':'owner','responsible_confirmed':True,
                     'parameters':{'publication_policy':str(self.path)}})

    def test_current_credentials_and_project_are_read_before_any_build_or_provider_write(self):
        project={'id':'prj_fixture','accountId':'team_fixture','targets':{'production':{'id':'initial'}},'ssoProtection':None}
        before=(Path(self.run['root'])/'state.json').read_bytes()
        with patch.object(publication,'_vercel_executable',return_value='/fixture/vercel'), \
             patch.object(publication,'_token',return_value='PRIVATE_SENTINEL'), \
             patch.object(publication,'_api_json',return_value=project) as api:
            result=publication.preflight_run(self.run['root'])
            self.assertEqual(result['status'],'READY')
            self.assertEqual(result['provider_writes'],0)
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(result))
            self.assertEqual(api.call_count,1)
            self.assertTrue(api.call_args.args[0].startswith('/v9/projects/'))
        self.assertEqual((Path(self.run['root'])/'state.json').read_bytes(),before)

    def test_missing_runtime_credential_and_changed_authority_fail_early(self):
        with patch.object(publication,'_vercel_executable',return_value='/fixture/vercel'), \
             patch.object(publication,'_token',side_effect=ValueError('Unavailable')), \
             patch.object(publication,'_api_json') as api:
            with self.assertRaisesRegex(ValueError,'Unavailable'):publication.preflight_run(self.run['root'])
            api.assert_not_called()
        self.policy['owner']='different';self.path.write_text(json.dumps(self.policy))
        with self.assertRaises(ValueError):publication.preflight_run(self.run['root'])

if __name__=='__main__':unittest.main()
