"""Web uses the existing stages and anchored reviews without documentary exports."""
import json
from pathlib import Path
import tempfile
import unittest
from proposition_runtime import state,web
from web_fixture import prepare_web,assess_web_fixture

WEB_INPUTS=('web-plan','web-build','web-inspection','web-sources',
            'creative-inputs','creative-experience','creative-exploration','creative-reading')


class WebStageTests(unittest.TestCase):
    def test_complete_web_gate_accepts_current_evidence_and_still_needs_both_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp,complete_evidence=True);root=Path(run['root'])
            web.build_run(root,source,plan);probe=web.inspect_run(root)
            self.assertEqual(probe['status'],'PASS',probe['issues'])
            current=assess_web_fixture(run)
            result=state.validate_run(root)
            self.assertEqual(result['status'],'PASS',result['issues'])
            self.assertFalse({'client-pdf','client-pptx'} & set(current['artifacts']))
            del current['reviews']['review-b'];state.save_run(root,current)
            result=state.validate_run(root)
            self.assertNotEqual(result['status'],'PASS')
            self.assertTrue(any(i['code']=='missing_review' and i['id']=='review-b' for i in result['issues']))

    def test_export_stage_accepts_current_web_evidence_without_pdf_or_pptx(self):
        with tempfile.TemporaryDirectory() as tmp:
            run,source,plan=prepare_web(tmp);root=Path(run['root'])
            web.build_run(root,source,plan)
            probe=web.inspect_run(root)
            self.assertEqual(probe['status'],'PASS',probe['issues'])
            current=state.load_run(root)
            self.assertTrue(set(WEB_INPUTS).issubset(current['artifacts']),
                            'Build/inspection did not register the complete web reviewer packet')
            self.assertFalse({'client-pdf','client-pptx'} & set(current['artifacts']))
            evidence=['artifact:'+name for name in WEB_INPUTS]
            for row in state._requirements(current):
                if row['stage_id']=='export.documents':
                    state.record_evaluation(root,row['id'],{'status':'PASS','applicable':True,'evidence':evidence,
                        'unknowns':[],'reason':'Synthetic format routing fixture; not a client quality verdict'})
            receipt={'run_id':run['id'],'reviewer_id':'stage-reviewer','author_id':'fixture-author',
                'stage_id':'export.documents','context_isolated':True,'author_context_inherited':False,
                'verdict_shared':False,'method':'synthetic-schema-fixture-not-an-actual-agent-review',
                'artifact_hashes':{'artifact:'+name:current['artifacts'][name]['sha256'] for name in WEB_INPUTS}}
            path=root/'review.json';path.write_text(json.dumps(receipt))
            state.add_artifact(root,'stage-receipt',path,'internal',evidence)
            state.record_stage_review(root,'export.documents',{'reviewer_id':'stage-reviewer','status':'PASS',
                'scores':[2,2,2,2,2],'independence':{'receipt_id':'stage-receipt'},'evidence':evidence,'unknowns':[],
                'criterion_evidence':{key:evidence for key in ['audiences','editable','text','render','portable']}})
            result=state.stage_report(root,'export.documents')
            self.assertEqual(result['status'],'PASS',result['issues'])
            (source/'app.js').write_text('a changed active experience')
            result=state.stage_report(root,'export.documents')
            self.assertNotEqual(result['status'],'PASS')
            self.assertTrue(any(i['code']=='web_delivery' for i in result['issues']),result['issues'])


if __name__=='__main__':unittest.main()
