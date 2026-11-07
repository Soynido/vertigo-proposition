"""Exercise preview publication; double only the external provider and HTTP boundary."""
import importlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
from unittest.mock import patch
from urllib.error import HTTPError
from proposition_runtime import web, state
from web_fixture import prepare_web,assess_web_fixture


class Provider:
    """External Vercel fixture. No real account, auth or deployment is used."""
    def __init__(self):
        self.project={'id':'prj_fixture','accountId':'team_fixture',
                      'targets':{'production':{'id':'dpl_initial'}},'ssoProtection':None}
        self.deployments=[];self.writes=[];self.uncertain=False;self.missing_reads=0

    def api(self, path, policy):
        if path.startswith('/v9/projects/'):
            return self.project
        if path.startswith('/v6/deployments'):
            if self.missing_reads:
                self.missing_reads-=1;return {'deployments':[],'pagination':{'next':None}}
            return {'deployments':self.deployments,'pagination':{'next':None}}
        if path.startswith('/v13/deployments/'):
            return self.deployments[-1]
        raise AssertionError('Unexpected provider request '+path)

    def cli(self, command, **options):
        self.writes.append({'command':command,'env':options['env']})
        payload=Path(command[command.index('--cwd')+1])
        self.uploaded={p.relative_to(payload).as_posix() for p in payload.rglob('*') if p.is_file()}
        self.link=json.loads((payload/'.vercel/project.json').read_text())
        values={command[i+1].split('=',1)[0]:command[i+1].split('=',1)[1]
                for i,v in enumerate(command) if v=='--meta'}
        self.deployments.append({'uid':'dpl_fixture','id':'dpl_fixture','url':'fixture-run.vercel.app',
            'projectId':'prj_fixture','target':None,'readyState':'READY','meta':values})
        if self.uncertain:
            self.missing_reads=1
            raise subprocess.TimeoutExpired(command,1)
        return subprocess.CompletedProcess(command,0,'https://fixture-run.vercel.app\n','')


class WebPublicationTests(unittest.TestCase):
    def setUp(self):
        try:self.module=importlib.import_module('proposition_runtime.web_publication')
        except ImportError:self.module=None
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run,self.source,self.plan=prepare_web(self.tmp.name);self.root=Path(self.run['root'])
        web.build_run(self.root,self.source,self.plan)
        self.directory,self.manifest,_=web.current_build(state.load_run(self.root))
        self.policy={'version':1,'authority':'workspace_publication_policy','owner':'fixture-owner',
            'project_id':'prj_fixture','org_id':'team_fixture','target':'preview','credential_ref':'vercel_cli'}
        self.provider=Provider()

    def require(self):
        self.assertIsNotNone(self.module,'No authorized exact-build preview publication adapter')

    def publish(self):
        self.require()
        real_run=subprocess.run;real_which=self.module.shutil.which
        def command_boundary(command,**options):
            return self.provider.cli(command,**options) if command[0]=='/fixture/vercel' else real_run(command,**options)
        def executable(name):
            return '/fixture/vercel' if name=='vercel' else real_which(name)
        with patch.object(self.module,'_api_json',side_effect=self.provider.api), \
             patch.object(self.module.subprocess,'run',side_effect=command_boundary), \
             patch.object(self.module,'_vercel_executable',return_value='/fixture/vercel'):
            return self.module._publish_once(self.root,self.directory,self.policy)

    def test_real_accepted_run_gate_reaches_only_the_external_preview_boundary(self):
        self.require()
        run,source,plan=prepare_web(self.tmp.name,complete_evidence=True)
        root=Path(run['root']);web.build_run(root,source,plan);probe=web.inspect_run(root)
        self.assertEqual(probe['status'],'PASS',probe['issues'])
        assess_web_fixture(run)
        self.assertEqual(state.validate_run(root)['status'],'PASS')
        policy_path=root/'policy.json';policy_path.write_text(json.dumps(self.policy))
        real_run=subprocess.run;real_which=self.module.shutil.which
        def command_boundary(command,**options):
            return self.provider.cli(command,**options) if command[0]=='/fixture/vercel' else real_run(command,**options)
        with patch.object(self.module,'_api_json',side_effect=self.provider.api), \
             patch.object(self.module.subprocess,'run',side_effect=command_boundary), \
             patch.object(self.module,'_vercel_executable',return_value='/fixture/vercel'):
            result=self.module.publish_run(root,policy_path)
        self.assertEqual(result['status'],'DEPLOYED')
        self.assertEqual(len(self.provider.writes),1)
        self.assertEqual(result['build_id'],web.current_build(state.load_run(root))[1]['build_id'])

    def test_exact_prebuilt_payload_is_isolated_and_preview_only(self):
        result=self.publish()
        self.assertEqual(result['status'],'DEPLOYED')
        self.assertEqual(result['url'],'https://fixture-run.vercel.app')
        self.assertEqual(len(self.provider.writes),1)
        command=self.provider.writes[0]['command']
        self.assertIn('--prebuilt',command)
        self.assertEqual(command[command.index('--environment')+1],'preview')
        self.assertNotIn('--prod',command);self.assertNotIn('--public',command)
        self.assertEqual(self.provider.link,{'orgId':'team_fixture','projectId':'prj_fixture'})
        self.assertNotIn('bundle.json',self.provider.uploaded)
        self.assertNotIn('web-plan.json',self.provider.uploaded)
        self.assertTrue(all(p.startswith('.vercel/') for p in self.provider.uploaded))
        repeated=self.publish()
        self.assertEqual(repeated['url'],result['url']);self.assertEqual(len(self.provider.writes),1)

    def test_wrong_project_first_production_or_protected_preview_cannot_trigger_a_write(self):
        self.require()
        for mutation in ('project','initial','protection','policy'):
            provider=Provider();self.provider=provider;policy=dict(self.policy)
            if mutation=='project':provider.project['id']='prj_other'
            elif mutation=='initial':provider.project['targets']={}
            elif mutation=='protection':provider.project['ssoProtection']={'deploymentType':'all_except_custom_domains'}
            else:self.policy=dict(policy,target='production')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.publish()
            self.assertEqual(provider.writes,[])
            self.policy=policy

    def test_uncertain_response_is_reconciled_without_redeploying(self):
        self.provider.uncertain=True
        first=self.publish();self.assertEqual(first['status'],'UNKNOWN_OUTCOME')
        second=self.publish();self.assertEqual(second['status'],'DEPLOYED')
        self.assertEqual(len(self.provider.writes),1)
        self.assertEqual(second['url'],'https://fixture-run.vercel.app')

    def test_old_deployment_with_wrong_metadata_is_not_accepted(self):
        self.require()
        self.provider.deployments=[{'uid':'dpl_wrong','url':'wrong.vercel.app','projectId':'prj_fixture',
            'target':'production','readyState':'READY','meta':{'vertigo_build':self.manifest['build_id']}}]
        result=self.publish()
        self.assertEqual(result['url'],'https://fixture-run.vercel.app')
        self.assertEqual(len(self.provider.writes),1)

    def test_unreviewed_run_cannot_reach_the_provider(self):
        self.require()
        path=self.root/'policy.json';path.write_text(json.dumps(self.policy))
        with patch.object(self.module,'_api_json',side_effect=AssertionError('Provider must not be reached')):
            with self.assertRaises(ValueError):self.module.publish_run(self.root,path)

    def test_partial_viewport_probe_cannot_authorize_publication(self):
        self.require()
        report=web.inspect_run(self.root,viewports=((390,844),))
        self.assertEqual(report['status'],'PASS',report['issues'])
        path=self.root/'policy.json';path.write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(ValueError,'viewport'):
            self.module.publish_run(self.root,path)

    def test_environment_token_is_not_put_in_arguments_or_uploaded_payload(self):
        self.require();self.policy['credential_ref']='env:FIXTURE_DEPLOY_TOKEN'
        original=self.provider.cli;secrets=[]
        def receive(command,**options):
            config=Path(command[command.index('--global-config')+1]);secrets.append(config)
            self.assertEqual(json.loads((config/'auth.json').read_text())['token'],'fixture-private-token')
            self.assertNotIn('fixture-private-token',' '.join(command))
            self.assertEqual((config/'auth.json').stat().st_mode & 0o777,0o600)
            return original(command,**options)
        self.provider.cli=receive
        with patch.dict(self.module.os.environ,{'FIXTURE_DEPLOY_TOKEN':'fixture-private-token'}):
            result=self.publish()
        self.assertEqual(result['status'],'DEPLOYED')
        self.assertTrue(secrets);self.assertFalse(secrets[0].exists())
        self.assertFalse(any('auth' in name for name in self.provider.uploaded))

    def test_unknown_media_rights_are_preserved_for_review_not_relabelled_as_licensed(self):
        self.require()
        data=json.loads(self.plan.read_text());data['media'][0]['rights']='unknown'
        self.plan.write_text(json.dumps(data))
        prepared=state.load_run(self.root)['metadata']['web_plan']
        web.plan_run(self.root,self.source,self.plan,supersedes=prepared['sha256'],reason='Preserve the actual unknown media rights for review')
        web.build_run(self.root,self.source,self.plan)
        report=web.inspect_run(self.root)
        self.assertEqual(report['status'],'PASS',report['issues'])
        # This synthetic run still lacks canonical reviews. Unknown rights are
        # carried to that decision; they do not become a fabricated licence or
        # an invented blanket prohibition on all public-source proposals.
        with self.assertRaisesRegex(ValueError,'canonical requirements'):
            self.module._publication_ready(self.root,self.policy)
        self.assertEqual(json.loads(self.plan.read_text())['media'][0]['rights'],'unknown')

    def test_real_cli_delivery_operations_enforce_the_run_gate(self):
        self.require()
        path=self.root/'policy.json';path.write_text(json.dumps(self.policy))
        cli=Path(__file__).resolve().parents[1]/'skills/proposition/scripts/proposition.py'
        for operation in ('publish','verify'):
            result=subprocess.run([sys.executable,str(cli),'web',operation,str(self.root),
                '--policy',str(path)],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'],'ERROR')

    def test_anonymous_readback_checks_all_public_bytes_and_rejects_login_or_redirect(self):
        self.require()
        public=self.directory/'.vercel/output/static';requests=[]
        class Response(io.BytesIO):
            status=200
            headers={}
        def receive(request,**kwargs):
            requests.append(request)
            self.assertFalse(any(k.lower() in ('authorization','cookie') for k in request.headers))
            name=request.full_url.removeprefix('https://fixture-run.vercel.app/')
            return Response((public/(name or 'index.html')).read_bytes())
        with patch.object(self.module,'_anonymous_open',side_effect=receive):
            result=self.module.verify_bytes(self.directory,'https://fixture-run.vercel.app')
        self.assertEqual(result['status'],'PASS')
        self.assertGreaterEqual(len(requests),5)
        with patch.object(self.module,'_anonymous_open',return_value=Response(b'<html>Login to Vercel</html>')):
            with self.assertRaises(ValueError):self.module.verify_bytes(self.directory,'https://fixture-run.vercel.app')
        with patch.object(self.module,'_anonymous_open',side_effect=HTTPError('https://fixture-run.vercel.app/',302,'Login',{},None)):
            with self.assertRaises(ValueError):self.module.verify_bytes(self.directory,'https://fixture-run.vercel.app')

    def test_public_origin_404_is_not_masked_by_valid_named_files(self):
        public=self.directory/'.vercel/output/static'
        class Response(io.BytesIO):
            status=200
        def receive(request,**kwargs):
            name=request.full_url.removeprefix('https://fixture-run.vercel.app/')
            if not name:
                response=Response(b'Not found');response.status=404;return response
            return Response((public/(name or 'index.html')).read_bytes())
        with patch.object(self.module,'_anonymous_open',side_effect=receive):
            with self.assertRaisesRegex(ValueError,'anonymously'):
                self.module.verify_bytes(self.directory,'https://fixture-run.vercel.app')


if __name__=='__main__':unittest.main()
class WebCLIOutputTests(unittest.TestCase):
    def test_native_cli_structured_success_yields_only_its_deployment_url(self):
        from proposition_runtime import web_publication
        self.assertTrue(callable(getattr(web_publication,'deployment_stdout',None)),
            'Actual non-TTY native CLI JSON output is not parsed')
        result=web_publication.deployment_stdout(json.dumps({'status':'ok',
            'deployment':{'id':'dpl_fixture','url':'https://fixture-run.vercel.app'}}))
        self.assertEqual(result,'https://fixture-run.vercel.app')
        with self.assertRaises(ValueError):
            web_publication.deployment_stdout(json.dumps({'status':'error',
                'deployment':{'url':'https://wrong.vercel.app'}}))

