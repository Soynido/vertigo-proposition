"""Historical evidence must not become an invented current diagnosis."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from proposition_runtime import state
try:
    from proposition_runtime import history
except ImportError:
    history = None


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run=state.init_run('https://example.test/',Path(self.tmp.name)/'runs')
        self.root=Path(self.run['root'])

    def module(self):
        self.assertIsNotNone(history,'Historical provenance contract is missing')
        return history

    def report(self):
        return {'schema_version':'site-history/1','revision':'history-r1','collected_at':'2026-10-25T12:00:00+00:00',
                'mode':'auto','outcome':'LIMITED','entity_source_refs':[],
                'limits':{},'attempts':[],'snapshots':[],'comparisons':[],
                'unknowns':['No comparable archive available']}

    def save(self,data):
        p=self.root/'history/report.json'; p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(data));return p

    def captured(self):
        module=self.module();data=self.report();path=self.save(data)
        index={'archived_snapshots':{'closest':{'available':True,'status':'200','timestamp':'20180601000000','url':'https://web.archive.org/web/20180601000000/https://example.test/'}}}
        (path.parent/'index.json').write_text(json.dumps(index));(path.parent/'old.html').write_text('<h1>Old fixture</h1>')
        (self.root/'identity.txt').write_text('Identity compared against current source')
        state.add_source(self.root,'identity','identity.txt')
        snapshot=module.availability_snapshot(index,'https://example.test/',None)
        snapshot.update(id='old',retrieved_at=data['collected_at'],index_source_ref='source:index',index_path='index.json',content_source_ref='source:old-content',content_path='old.html',entity_match='confirmed',entity_evidence=['source:identity'])
        data['snapshots']=[snapshot]
        return data,path

    def test_unavailable_history_is_optional_without_mutating_profile(self):
        module=self.module(); before=copy.deepcopy(state.load_run(self.root)['profile'])
        report=self.report();report['outcome']='UNAVAILABLE'
        module.register(self.root,self.save(report))
        run=state.load_run(self.root)
        self.assertEqual(run['profile'],before)
        self.assertFalse(run['sources']['site-history-history-r1']['required'])
        self.assertEqual(module.inspect_history(run)['status'],'PASS')

    def test_compared_status_requires_actual_comparisons(self):
        report=self.report();report['outcome']='COMPARED'
        with self.assertRaises(ValueError):self.module().register(self.root,self.save(report))

    def test_capture_target_is_not_substituted_for_actual_capture(self):
        module=self.module()
        capture=module.availability_snapshot({'archived_snapshots':{'closest':{'available':True,'timestamp':'20180601000000','url':'https://web.archive.org/web/20180601000000/https://example.test/','status':'200'}}},'https://example.test/','20200101')
        self.assertEqual(capture['requested_target_at'],'20200101')
        self.assertEqual(capture['archive_captured_at'],'2018-06-01T00:00:00+00:00')
        self.assertEqual(capture['entity_match'],'unknown')

    def test_replay_cannot_redirect_to_live_or_private_url(self):
        module=self.module()
        for value in ['http://127.0.0.1/admin','https://example.test/','https://web.archive.org.evil.test/web/123/https://example.test/','https://web.archive.org/save/https://example.test/']:
            with self.subTest(url=value),self.assertRaises(ValueError):module.safe_archive_url(value)

    def test_history_synthesis_change_invalidates_fact_but_not_unrelated_fact(self):
        module=self.module();p=self.save(self.report());module.register(self.root,p)
        (self.root/'live.txt').write_text('Current observation')
        state.add_source(self.root,'live','live.txt')
        state.add_fact(self.root,'stable','current offer',['live'])
        state.add_fact(self.root,'history-use',{'note':'bounded historical outcome'},['site-history-history-r1'])
        p.write_text(p.read_text()+'\n')
        result=state.invalidate_changed(self.root)
        self.assertIn('fact:history-use',result['invalidated'])
        self.assertEqual(state.load_run(self.root)['facts']['stable']['status'],'CONFIRMED')

    def test_malformed_dates_and_invented_update_field_are_rejected(self):
        module=self.module();report=self.report();report['site_last_updated_at']='2020'
        with self.assertRaises(ValueError):module.register(self.root,self.save(report))
        report=self.report();report['collected_at']='not a date'
        with self.assertRaises(ValueError):module.register(self.root,self.save(report))

    def test_index_only_is_not_a_comparison(self):
        module=self.module();report=self.report()
        report['comparisons']=[{'historical_source_ref':'source:missing','current_source_ref':'source:missing-current','observation':'Old design','page_zone':'header','difference_type':'visual','limitation':'','client_allowed':True}]
        with self.assertRaises(ValueError):module.register(self.root,self.save(report))

    def test_unsupported_history_policy_is_rejected_before_network(self):
        module=self.module()
        with self.assertRaises(ValueError):module.policy({'history_mode':'silently-ignore'})
        with self.assertRaises(ValueError):module.policy({'history_deadline_seconds':-1})

    def test_replay_cannot_disagree_with_recorded_capture_timestamp(self):
        module=self.module(); report=self.report()
        candidate=module.availability_snapshot({'archived_snapshots':{'closest':{'available':True,'timestamp':'20180601000000','url':'https://web.archive.org/web/20180601000000/https://example.test/','status':'200'}}},'https://example.test/',None)
        candidate.update(id='old',retrieved_at=report['collected_at'],index_source_ref='source:index',index_path='index.json',content_source_ref=None,content_path=None)
        candidate['archive_captured_at']='2020-01-01T00:00:00+00:00'; report['snapshots']=[candidate]
        path=self.save(report);(path.parent/'index.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'timestamp'):module.register(self.root,path)

    def test_stream_cannot_exceed_absolute_deadline_or_byte_limit(self):
        module=self.module()
        class Response:
            headers={}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read1(self,n):return b'x'*n
        class Opener:
            def open(self,*args,**kwargs):return Response()
        reader=module.ArchiveReader(module.policy({}));reader.opener=Opener()
        with self.assertRaisesRegex(ValueError,'byte budget'):
            reader.fetch('https://archive.org/wayback/available?url=example.test',5)
        reader.deadline=0
        with self.assertRaises(TimeoutError):reader.fetch('https://archive.org/wayback/available?url=example.test',5)

    def test_modified_registered_report_requires_a_new_revision(self):
        module=self.module();path=self.save(self.report());module.register(self.root,path)
        data=self.report();data['unknowns'].append('changed interpretation');path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'revision'):module.register(self.root,path)

    def test_index_provenance_is_registered_even_when_no_capture_is_found(self):
        module=self.module(); data=self.report()
        directory=self.root/'history';directory.mkdir();(directory/'index.json').write_text('{"archived_snapshots":{}}')
        data['attempts']=[{'original_url':'https://example.test/','requested_target_at':None,'status':'UNAVAILABLE','index_path':'index.json','index_locator':'https://archive.org/wayback/available?url=example.test','index_source_ref':'source:empty-index'}]
        module.register(self.root,self.save(data))
        run=state.load_run(self.root)
        self.assertIn('empty-index',run['sources'])
        self.assertIn('source:empty-index',run['artifacts']['site-history']['dependencies'])

    def test_registration_retry_keeps_original_provenance_unchanged(self):
        module=self.module();path=self.save(self.report());module.register(self.root,path)
        before=state.load_run(self.root)['sources']['site-history-history-r1']
        module.register(self.root,path)
        self.assertEqual(before,state.load_run(self.root)['sources']['site-history-history-r1'])

    def test_replay_origin_must_match_its_claimed_original(self):
        module=self.module(); report=self.report()
        candidate=module.availability_snapshot({'archived_snapshots':{'closest':{'available':True,'timestamp':'20180601000000','url':'https://web.archive.org/web/20180601000000/https://example.test/','status':'200'}}},'https://example.test/',None)
        candidate.update(id='old',retrieved_at=report['collected_at'],index_source_ref='source:index',index_path='index.json',content_source_ref=None,content_path=None)
        candidate['original_url']='https://different.test/';report['snapshots']=[candidate]
        path=self.save(report);(path.parent/'index.json').write_text('{}')
        with self.assertRaises(ValueError):module.register(self.root,path)

    def test_raw_index_must_substantiate_the_claimed_capture(self):
        module=self.module();data,path=self.captured();path.write_text(json.dumps(data))
        (path.parent/'index.json').write_text('{}')
        with self.assertRaises(ValueError):module.register(self.root,path)
        self.assertNotIn('site-history',state.load_run(self.root)['artifacts'])

    def test_archived_capture_cannot_be_its_own_current_counterpart(self):
        module=self.module();data,path=self.captured();path.write_text(json.dumps(data));module.register(self.root,path)
        data['revision']='history-r2';data['outcome']='COMPARED'
        data['comparisons']=[{'historical_source_ref':'source:old-content','current_source_ref':'source:old-content','observation':'Changed offer','page_zone':'offer','difference_type':'content','limitation':'','client_allowed':True}]
        other=path.parent/'r2.json';other.write_text(json.dumps(data))
        with self.assertRaises(ValueError):module.register(self.root,other)

    def test_text_file_cannot_be_a_visual_render(self):
        module=self.module();data,path=self.captured()
        (self.root/'current.txt').write_text('current');state.add_source(self.root,'current','current.txt')
        (self.root/'fake.txt').write_text('no pixels');state.add_artifact(self.root,'fake','fake.txt','internal')
        data['snapshots'][0].update(render_completeness='complete',render_ref='artifact:fake',missing_assets=[],live_resource_contamination=False)
        data['outcome']='COMPARED';data['comparisons']=[{'historical_source_ref':'source:old-content','current_source_ref':'source:current','observation':'Changed design','page_zone':'header','difference_type':'visual','limitation':'','client_allowed':True}]
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):module.register(self.root,path)

    def test_overlong_revision_cannot_leave_half_a_registration(self):
        module=self.module();data=self.report();data['revision']='r'*128;path=self.save(data)
        with self.assertRaises(ValueError):module.register(self.root,path)
        run=state.load_run(self.root)
        self.assertNotIn('site-history',run['artifacts']);self.assertEqual(run['sources'],{})

    def test_optional_old_fact_without_current_consumers_does_not_block_revision(self):
        module=self.module();data,path=self.captured();path.write_text(json.dumps(data));module.register(self.root,path)
        state.add_fact(self.root,'old-note',{'temporal_scope':'historical_observation','archive_captured_at':data['snapshots'][0]['archive_captured_at']},['site-history-history-r1','old-content'],required=False)
        data['revision']='history-r2';other=path.parent/'r2.json';other.write_text(json.dumps(data));module.register(self.root,other)
        state.invalidate_changed(self.root)
        self.assertEqual(module.inspect_history(state.load_run(self.root))['status'],'PASS')

    def test_unavailable_attempt_index_is_not_current_evidence(self):
        module=self.module();data=self.report();path=self.save(data)
        (path.parent/'index.json').write_text('{"archived_snapshots":{}}')
        data['attempts']=[{'original_url':'https://example.test/','requested_target_at':None,'status':'UNAVAILABLE','index_path':'index.json','index_locator':'https://archive.org/wayback/available?url=example.test','index_source_ref':'source:empty-index'}]
        path.write_text(json.dumps(data));module.register(self.root,path)
        state.add_fact(self.root,'bad-current',{'temporal_scope':'current_observation','value':'current offering'},['empty-index'])
        self.assertEqual(module.inspect_history(state.load_run(self.root))['status'],'BLOCKED')

    def test_attributed_capture_with_real_dependent_pixels_can_be_compared(self):
        from PIL import Image
        module=self.module();data,path=self.captured();path.write_text(json.dumps(data));module.register(self.root,path)
        (self.root/'current.txt').write_text('Current fixture observation')
        state.add_source(self.root,'current','current.txt')
        Image.new('RGB',(400,300),'navy').save(self.root/'historical-render.png')
        state.add_artifact(self.root,'render','historical-render.png','internal',['source:old-content'])
        data['revision']='history-r2';data['outcome']='COMPARED'
        data['snapshots'][0].update(render_completeness='complete',render_ref='artifact:render',missing_assets=[],live_resource_contamination=False)
        data['comparisons']=[{'historical_source_ref':'source:old-content','current_source_ref':'source:current','observation':'Fictional layout compared','page_zone':'header','difference_type':'visual','limitation':'Synthetic consistency fixture, not a real historical visual review','client_allowed':False}]
        second=path.parent/'r2.json';second.write_text(json.dumps(data));module.register(self.root,second)
        self.assertEqual(module.inspect_history(state.load_run(self.root))['status'],'PASS')

    def test_changed_raw_capture_cannot_be_silently_reused(self):
        module=self.module();data,path=self.captured();path.write_text(json.dumps(data));module.register(self.root,path)
        (path.parent/'old.html').write_text('Changed bytes')
        with self.assertRaises(ValueError):module.collect(self.root)

    def test_optional_fact_consumed_by_live_evaluation_is_not_ignored(self):
        module=self.module();data=self.report();path=self.save(data)
        (path.parent/'index.json').write_text('{"archived_snapshots":{}}')
        data['attempts']=[{'original_url':'https://example.test/','requested_target_at':None,'status':'UNAVAILABLE','index_path':'index.json','index_locator':'https://archive.org/wayback/available?url=example.test','index_source_ref':'source:empty-index'}]
        path.write_text(json.dumps(data));module.register(self.root,path)
        state.add_fact(self.root,'optional-current',{'temporal_scope':'current_observation','value':'current offer'},['empty-index'],required=False)
        state.record_evaluation(self.root,'R01',{'status':'PASS','applicable':True,'evidence':['fact:optional-current'],'unknowns':[],'reason':'Fixture of an actual current consumer'})
        self.assertEqual(module.inspect_history(state.load_run(self.root))['status'],'BLOCKED')


if __name__=='__main__': unittest.main()
