"""Optional decisions must save work without dropping primary evidence."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime import state, preprocessing as pre


class PreprocessingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.run=Path(state.init_run('https://example.com',self.base/'runs')['root'])
        self.cache=self.base/'cache'

    def source(self,sid,text,**kwargs):
        (self.run/(sid+'.txt')).write_text(text)
        state.add_source(self.run,sid,sid+'.txt',locator='https://example.com/'+sid,
                         audience=kwargs.pop('audience','public'),**kwargs)

    def fake(self,payload,config,timeout):
        return {'model':'clef','answers':{key:{'type':'choice','choice':'tracking',
            'probabilities':{x:1.0 if x=='tracking' else 0.0 for x in pre.TOPICS},'confidence':1.0}
            for key in payload['questions']},'usage':{'input_tokens':100,'output_tokens':0}}

    def test_no_configuration_uses_same_durable_packet_without_network(self):
        self.source('s','Public company text')
        with patch.object(pre,'cloudflare_request',side_effect=AssertionError('network forbidden')):
            result=pre.prepare(self.run,cache_root=self.cache,config={})
        self.assertEqual(0,result['requests']);self.assertEqual('CODEX_REQUIRED',result['status'])
        packet=json.loads(Path(result['packet_path']).read_text())
        self.assertEqual('Public company text',packet['records'][0]['text'])
        self.assertTrue(Path(result['native_task_path']).is_file())

    def test_private_sources_and_secret_text_never_enter_public_packet(self):
        self.source('private','PRIVATE_SENTINEL',kind='private',audience='internal')
        self.source('secret','Authorization: Bearer SECRET_SENTINEL_1234567890123456')
        self.source('clean','Public cookie policy')
        result=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        text=Path(result['packet_path']).read_text()
        self.assertNotIn('PRIVATE_SENTINEL',text);self.assertNotIn('SECRET_SENTINEL',text)
        packet=json.loads(text);self.assertEqual({'private','secret'},{r['source_id'] for r in packet['excluded']})

    def test_chunk_dedup_keeps_all_locations_and_never_truncates(self):
        text=('Public rooms and services. '*150)
        self.source('a',text);self.source('b',text)
        result=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        packet=json.loads(Path(result['packet_path']).read_text())
        self.assertLess(len(packet['records']),len(packet['locations']))
        for sid in ['a','b']:
            locations=sorted((x for x in packet['locations'] if x['source_id']==sid),key=lambda x:x['start'])
            self.assertEqual(0,locations[0]['start']);self.assertEqual(len(text),locations[-1]['end'])
            self.assertTrue(all(a['end']==b['start'] for a,b in zip(locations,locations[1:])))

    def test_valid_remote_cache_saves_calls_across_runs_and_keeps_cookie_source(self):
        self.source('S046','Cookies and retargeting Facebook pixel')
        config={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        with patch.object(pre,'cloudflare_request',side_effect=self.fake) as request:
            first=pre.prepare(self.run,config=config,cache_root=self.cache)
            second=pre.prepare(self.run,config=config,cache_root=self.cache)
        self.assertEqual(1,request.call_count);self.assertEqual(1,first['requests']);self.assertEqual(0,second['requests'])
        self.assertEqual(1,second['cache_hits']);self.assertEqual('SUGGESTIONS_READY',second['status'])
        self.assertIn('S046',Path(second['packet_path']).read_text());self.assertNotIn('TOKEN_SENTINEL',json.dumps(second))
        other=Path(state.init_run('https://example.com',self.base/'runs')['root'])
        (other/'cookie.txt').write_text('Cookies and retargeting Facebook pixel')
        state.add_source(other,'different-id','cookie.txt',locator='https://example.com/new-path',audience='public')
        with patch.object(pre,'cloudflare_request',side_effect=AssertionError('cache missed')):
            third=pre.prepare(other,config=config,cache_root=self.cache)
        self.assertEqual(1,third['cache_hits']);self.assertEqual(0,third['requests'])

    def test_invalid_response_or_timeout_falls_back_once_without_error_secrets(self):
        self.source('s','Cookie tracking policy')
        config={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        for error in [TimeoutError('TOKEN_SENTINEL'),ValueError('TOKEN_SENTINEL')]:
            self.source('s','Cookie tracking policy '+type(error).__name__)
            with self.subTest(error=type(error).__name__), patch.object(pre,'cloudflare_request',side_effect=error) as request:
                result=pre.prepare(self.run,config=config,cache_root=self.base/type(error).__name__)
                again=pre.prepare(self.run,config=config,cache_root=self.base/type(error).__name__)
                self.assertEqual(1,request.call_count);self.assertEqual('CODEX_REQUIRED',result['status'])
                self.assertEqual(0,again['requests']);self.assertNotIn('TOKEN_SENTINEL',json.dumps(result))
                self.assertIn('Cookie tracking policy',Path(result['packet_path']).read_text())

    def test_paid_unknown_or_stale_policy_never_calls_provider(self):
        self.source('s','Public content')
        for conf in [{},{'free_plan_confirmed':False},{'free_plan_confirmed':True,'confirmed_at':'2020-01-01T00:00:00+00:00'}]:
            conf.update(account_id='a'*32,token='TOKEN_SENTINEL')
            with patch.object(pre,'cloudflare_request',side_effect=AssertionError('forbidden')):
                result=pre.prepare(self.run,mode='cloudflare',config=conf,cache_root=self.cache)
            self.assertEqual(0,result['requests']);self.assertEqual('CODEX_REQUIRED',result['status'])

    def test_missing_extra_or_invalid_choice_is_rejected_not_cached(self):
        self.source('s','Public content')
        config={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        def invalid(payload,config,timeout):
            response=self.fake(payload,config,timeout);response['answers']['unknown']=next(iter(response['answers'].values()));return response
        with patch.object(pre,'cloudflare_request',side_effect=invalid):
            result=pre.prepare(self.run,config=config,cache_root=self.cache)
        self.assertEqual('CODEX_REQUIRED',result['status']);self.assertEqual(0,result['validated_batches'])

    def test_primary_source_mutation_changes_packet_and_does_not_reuse_suggestions(self):
        self.source('s','First company offer')
        first=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        self.source('s','Changed company offer')
        second=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        self.assertNotEqual(first['packet_sha256'],second['packet_sha256'])
        self.assertEqual(0,second['cache_hits'])

    def test_duplicate_json_keys_are_invalid(self):
        with self.assertRaises(ValueError):pre.decode_response('{"answers":{},"answers":{}}')

    def test_unavailable_local_copy_is_bounded_and_remains_local_work(self):
        self.source('s','Public content')
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('read',5)):
            result=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        self.assertEqual('CODEX_REQUIRED',result['status'])
        self.assertEqual(0,result['unique_excerpts'])
        self.assertEqual('source_read_unavailable',result['excluded_sources'][0]['reason'])

    def test_run_receipt_prevents_retries_after_global_cache_eviction(self):
        self.source('s','Cookie policy')
        conf={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        with patch.object(pre,'cloudflare_request',side_effect=TimeoutError()):
            first=pre.prepare(self.run,config=conf,cache_root=self.cache)
        for path in self.cache.glob('*.json'):path.unlink()
        with patch.object(pre,'cloudflare_request',side_effect=AssertionError('unexpected retry')) as request:
            second=pre.prepare(self.run,config=conf,cache_root=self.cache)
        self.assertEqual(0,request.call_count);self.assertEqual(0,second['requests'])
        self.assertEqual('CODEX_REQUIRED',second['status'])

    def test_cache_pruning_only_removes_own_old_entries_and_respects_size_limit(self):
        self.cache.mkdir();keep=self.cache/'unrelated.txt';keep.write_text('preserve')
        for n in range(4):(self.cache/(str(n)*64+'.json')).write_bytes(b'x'*100)
        removed=pre.prune_cache(self.cache,max_bytes=150)
        self.assertTrue(keep.is_file());self.assertEqual(3,removed)
        self.assertLessEqual(sum(p.stat().st_size for p in self.cache.glob('*.json')),150)

    def test_signed_url_across_chunk_boundary_cannot_leak_parameters(self):
        prefix=' https://example.com/?sig='
        self.source('s','x'*(pre.CHUNK_CHARS-len(prefix))+prefix+'SIGNED_SENTINEL')
        result=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        packet=json.loads(Path(result['packet_path']).read_text())
        self.assertNotIn('SIGNED_SENTINEL',json.dumps(packet['records']))
        self.assertTrue(packet['locations'])

    def test_json_secret_keys_are_excluded(self):
        self.source('s','{"api_key":"SECRET_SENTINEL_1234567890123456"}')
        result=pre.prepare(self.run,mode='codex',cache_root=self.cache)
        self.assertEqual(0,result['unique_excerpts'])
        self.assertNotIn('SECRET_SENTINEL',Path(result['packet_path']).read_text())

    def test_codex_pass_cannot_erase_an_attempt_before_cache_eviction(self):
        self.source('s','Cookie policy')
        conf={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        with patch.object(pre,'cloudflare_request',side_effect=TimeoutError()):
            pre.prepare(self.run,config=conf,cache_root=self.cache)
        pre.prepare(self.run,mode='codex',cache_root=self.cache)
        for path in self.cache.glob('*.json'):path.unlink()
        with patch.object(pre,'cloudflare_request',side_effect=AssertionError('retry')) as request:
            result=pre.prepare(self.run,config=conf,cache_root=self.cache)
        self.assertEqual(0,request.call_count);self.assertEqual(0,result['requests'])

    def test_interrupted_attempt_is_persisted_before_the_request(self):
        self.source('s','Cookie policy')
        conf={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        with patch.object(pre,'cloudflare_request',side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):pre.prepare(self.run,config=conf,cache_root=self.cache)
        with patch.object(pre,'cloudflare_request',side_effect=AssertionError('retry')) as request:
            result=pre.prepare(self.run,config=conf,cache_root=self.cache)
        self.assertEqual(0,request.call_count);self.assertEqual('CODEX_REQUIRED',result['status'])

    def test_invalid_answers_keep_observed_usage_and_timeouts_keep_usage_unknown(self):
        self.source('s','Public content')
        conf={'account_id':'a'*32,'token':'TOKEN_SENTINEL','free_plan_confirmed':True,'confirmed_at':pre.now()}
        def invalid(payload,config,timeout):
            result=self.fake(payload,config,timeout);result['answers']['extra']={};result['usage']['input_tokens']=123;return result
        with patch.object(pre,'cloudflare_request',side_effect=invalid):
            result=pre.prepare(self.run,config=conf,cache_root=self.cache)
        self.assertEqual('CODEX_REQUIRED',result['status']);self.assertEqual(123,result['input_tokens_this_call'])
        self.source('s','Changed public content')
        with patch.object(pre,'cloudflare_request',side_effect=TimeoutError()):
            result=pre.prepare(self.run,config=conf,cache_root=self.cache)
        self.assertIsNone(result['input_tokens_this_call']);self.assertEqual(1,result['requests_with_unknown_usage'])
