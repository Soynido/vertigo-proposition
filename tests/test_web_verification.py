"""Accepted-run verification with actual browsers and doubled external transport."""
from datetime import datetime,timedelta
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from proposition_runtime import state,web,web_publication as publication,web_timing
from web_fixture import prepare_web,assess_web_fixture


class WebVerificationTests(unittest.TestCase):
    def _exercise_verification(self, initial_block=False):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp,complete_evidence=True);root=Path(run['root'])
            web.build_run(root,source,plan);inspection=web.inspect_run(root)
            self.assertEqual(inspection['status'],'PASS',inspection['issues'])
            assess_web_fixture(run)
            directory,manifest,_=web.current_build(state.load_run(root))
            policy={'version':1,'authority':'workspace_publication_policy','owner':'fixture-owner',
                'project_id':'prj_fixture','org_id':'team_fixture','target':'preview','credential_ref':'vercel_cli'}
            policy_path=root/'private-policy.json';policy_path.write_text(json.dumps(policy))
            key=hashlib.sha256(web._canonical([run['id'],policy['org_id'],policy['project_id'],manifest['build_id']])).hexdigest()
            ledger=root/'web/publication'/ (key+'.json');ledger.parent.mkdir(parents=True)
            outcome={'status':'DEPLOYED','deployment_id':'dpl_fixture','url':'https://fixture-run.vercel.app',
                'project_id':'prj_fixture','org_id':'team_fixture','target':'preview','operation_key':key,
                'build_id':manifest['build_id']}
            ledger.write_text(json.dumps(outcome))
            class Adapter:
                def __init__(self,policy):pass
                def project(self):return {'id':'prj_fixture'}
                def lookup(self,*args):return outcome
                def deploy(self,*args):raise AssertionError('Verification must never publish')
            class Response(io.BytesIO):
                status=200
                headers={}
            def receive(request,**kwargs):
                name=request.full_url.removeprefix(outcome['url']+'/')
                return Response((directory/'.vercel/output/static'/(name or 'index.html')).read_bytes())
            actual_inspection=web.inspect_bundle;calls=[]
            def inspect(directory,plan,output,**kwargs):
                # Transport is local in this fixture. Both browser engines still
                # render every exact file/state; no remote-provider claim follows.
                calls.append(True);report=actual_inspection(directory,plan,output)
                report['origin']=kwargs['origin']
                if initial_block and len(calls)==1:
                    report['status']='BLOCKED';report['issues']=[{'code':'transient_fixture','detail':'Doubled one-time browser failure'}]
                return report
            start=datetime.fromisoformat(run['created_at'])
            with patch.object(publication,'VercelPreviewAdapter',Adapter), \
                 patch.object(publication,'_anonymous_open',side_effect=receive), \
                 patch.object(web,'inspect_bundle',side_effect=inspect), \
                 patch.object(web_timing,'utc_now',return_value=start+timedelta(seconds=623)):
                if initial_block:
                    with patch.object(web_timing,'utc_now',return_value=start+timedelta(seconds=50)):
                        failed=publication.verify_run(root,policy_path)
                    self.assertEqual(failed['status'],'BLOCKED')
                    self.assertNotIn('first_verified_at',failed)
                    failed_path=root/state.load_run(root)['artifacts']['web-verification']['path']
                    failed_bytes=failed_path.read_bytes()
                first=publication.verify_run(root,policy_path)
                self.assertEqual(first['status'],'PASS');self.assertEqual(first['delivery_status'],'FAIL_TIMING')
                self.assertEqual(first['timing']['wall_seconds'],623)
                with patch.object(web_timing,'utc_now',return_value=start+timedelta(seconds=1400)):
                    again=publication.verify_run(root,policy_path)
                self.assertEqual(len(calls),2 if initial_block else 1)
                if initial_block:self.assertEqual(failed_path.read_bytes(),failed_bytes)
                self.assertEqual(again['first_verified_at'],first['first_verified_at'])
                self.assertEqual(again['timing'],first['timing'])
                self.assertTrue(again['reused_browser_evidence'])
                self.assertEqual(state.validate_run(root)['publication']['execution'],'VERIFIED_PUBLIC')
                proof=root/first['browser_report']['path'];report=json.loads(proof.read_text())
                capture=proof.parent/report['captures'][0]['path'];capture.write_bytes(b'changed proof')
                with patch.object(web_timing,'utc_now',return_value=start+timedelta(seconds=1400)):
                    with self.assertRaises(ValueError):publication.verify_run(root,policy_path)

    def test_verification_reuses_exact_browser_evidence_without_resetting_failed_delivery_time(self):
        self._exercise_verification()

    def test_transient_blocked_public_browser_can_resume_without_resetting_the_run_clock(self):
        self._exercise_verification(initial_block=True)


if __name__=='__main__':unittest.main()
