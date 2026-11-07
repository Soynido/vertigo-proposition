"""One-time isolated Vercel provisioning, with the external provider doubled."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace


class Provider:
    def __init__(self):
        self.project=None;self.created=0;self.bootstraps=0
        self.lose_create=False;self.lose_bootstrap=False;self.deployment=None

    def lookup_project(self,name):return self.project
    def create_project(self,name):
        self.created+=1
        if self.lose_create:raise TimeoutError('Unknown creation outcome')
        self.project={'id':'prj_fixture','name':name,'accountId':'team_fixture','targets':{},'ssoProtection':None}
        return self.project
    def read_project(self,identifier):return self.project
    def find_bootstrap(self,project,nonce):return self.deployment
    def bootstrap(self,project,nonce):
        self.bootstraps+=1
        self.deployment={'id':'dpl_fixture','url':'https://fixture-setup.vercel.app',
            'projectId':project['id'],'readyState':'READY','meta':{'vertigo_setup':nonce},'target':'production'}
        self.project['targets']={'production':{'id':'dpl_fixture'}}
        if self.lose_bootstrap:raise TimeoutError('Unknown bootstrap outcome')
        return self.deployment
    def verify_public(self,record,nonce):return {'status':'PASS','authentication_used':False}


class WebSetupTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('proposition_runtime.web_setup'),'Isolated publication setup missing')
        from proposition_runtime import web_setup
        self.setup=web_setup
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.provider=Provider()

    def install(self):
        return self.setup.configure_publication(self.root,'fixture-owner','team_fixture',adapter=self.provider)

    def test_new_isolated_support_is_provisioned_once_and_the_private_profile_is_linked(self):
        private=self.root/'.vertigo';private.mkdir()
        (private/'profile.json').write_text(json.dumps({'actor':'fixture-owner','parameters':{'keep':'existing'}}))
        result=self.install();again=self.install()
        self.assertEqual(result['status'],'READY');self.assertEqual(again,result)
        self.assertEqual((self.provider.created,self.provider.bootstraps),(1,1))
        self.assertTrue(self.provider.project['name'].startswith('vertigo-propositions-'))
        policy=json.loads((private/'publication-policy.json').read_text())
        self.assertEqual(policy['target'],'preview');self.assertEqual(policy['credential_ref'],'vercel_cli')
        self.assertNotIn('token',policy)
        self.assertEqual((private/'publication-policy.json').stat().st_mode & 0o777,0o600)
        profile=json.loads((private/'profile.json').read_text())
        self.assertEqual(profile['parameters']['keep'],'existing')
        self.assertEqual(Path(profile['parameters']['publication_policy']),private/'publication-policy.json')

    def test_uncertain_create_is_not_an_authorization_for_a_second_creation(self):
        self.provider.lose_create=True
        result=self.install();self.assertEqual(result['status'],'UNKNOWN_OUTCOME')
        self.assertEqual(self.install()['status'],'UNKNOWN_OUTCOME')
        self.assertEqual(self.provider.created,1);self.assertEqual(self.provider.bootstraps,0)
        self.assertFalse((self.root/'.vertigo/publication-policy.json').exists())

    def test_a_definite_rejected_creation_is_recorded_and_can_resume_the_same_reserved_name(self):
        original=self.provider.create_project
        def rejected(name):raise self.setup.RequestRejected(400,'bad_request')
        self.provider.create_project=rejected
        result=self.install()
        self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['phase'],'CREATE_REJECTED')
        reserved=result['project_name'];self.provider.create_project=original
        result=self.install()
        self.assertEqual(result['status'],'READY');self.assertEqual(result['project_name'],reserved)
        self.assertEqual(self.provider.created,1)

    def test_lost_bootstrap_response_is_reconciled_without_deploying_twice(self):
        self.provider.lose_bootstrap=True
        self.assertEqual(self.install()['status'],'UNKNOWN_OUTCOME')
        self.assertEqual(self.install()['status'],'READY')
        self.assertEqual((self.provider.created,self.provider.bootstraps),(1,1))

    def test_an_existing_unowned_project_is_not_modified(self):
        self.provider.project={'id':'prj_existing','name':'existing-site','accountId':'team_fixture'}
        with self.assertRaises(ValueError):self.install()
        self.assertEqual((self.provider.created,self.provider.bootstraps),(0,0))

    def test_wrong_account_or_protected_project_never_becomes_a_publish_policy(self):
        original=self.provider.create_project
        def wrong(name):
            project=original(name);project['accountId']='team_other';return project
        self.provider.create_project=wrong
        with self.assertRaises(ValueError):self.install()
        self.assertFalse((self.root/'.vertigo/publication-policy.json').exists())
        self.assertEqual(self.provider.bootstraps,0)

    def test_only_the_fixed_installation_page_can_use_the_initial_production_target(self):
        nonce='a'*32
        adapter=object.__new__(self.setup.InstallationAdapter)
        adapter.policy={'org_id':'team_fixture','credential_ref':'vercel_cli'}
        project={'id':'prj_fixture','accountId':'team_fixture','name':'vertigo-propositions-'+nonce,'targets':{}}
        commands=[]
        def deploy(command,**kwargs):
            commands.append(command)
            self.assertEqual(command[command.index('--environment')+1],'production')
            folder=Path(command[command.index('--cwd')+1]);public=folder/'.vercel/output/static'
            self.assertEqual({p.name for p in public.iterdir()},{'index.html','sources.html','vertigo-build.json'})
            self.assertIn('Aucune proposition client', (public/'index.html').read_text())
            return SimpleNamespace(returncode=0,stdout='https://fixture-setup.vercel.app',stderr='')
        with patch.object(self.setup,'locate_vercel_cli',return_value='/fixture/vercel'), \
             patch.object(self.setup.subprocess,'run',side_effect=deploy), \
             patch.object(self.setup,'_setup_request',return_value={'id':'dpl_fixture'}):
            self.assertEqual(adapter.bootstrap(project,nonce)['id'],'dpl_fixture')
            for wrong in [dict(project,name='existing-site'),dict(project,targets={'production':{'id':'existing'}})]:
                with self.assertRaises(ValueError):adapter.bootstrap(wrong,nonce)
        self.assertEqual(len(commands),1)


if __name__=='__main__':unittest.main()
