"""Public native activity, without inferring agents from technical CLI spans."""
import json
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
try:
    from proposition_runtime.native_activity import NativeActivity
except ImportError:
    NativeActivity = None


class NativeActivityTests(unittest.TestCase):
    def test_terminal_and_final_public_events_survive_live_window_rollover(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=NativeActivity(journal_dir=Path(tmp).resolve())
            feed.bind_root({'id':'root','status':{'type':'idle'}})
            feed.observe({'method':'turn/started','params':{'threadId':'root','turn':{'id':'turn','status':'inProgress'}}})
            for _ in range(2100):feed.observe({'method':'item/agentMessage/delta','params':{'threadId':'root','itemId':'message','delta':'x'}})
            feed.observe({'method':'item/completed','params':{'threadId':'root','item':{'id':'message','type':'agentMessage','text':'Final public message'}}})
            feed.observe({'method':'turn/completed','params':{'threadId':'root','turn':{'id':'turn','status':'completed'}}})
            events=[json.loads(l) for p in Path(tmp).glob('*.jsonl') for l in p.read_text().splitlines()]
            self.assertTrue(any(e['kind']=='turn.started' for e in events))
            self.assertTrue(any(e['kind']=='turn.completed' for e in events))
            self.assertTrue(any(e.get('text')=='Final public message' for e in events))
            self.assertLess(len(events),20)

    def setUp(self):
        self.assertIsNotNone(NativeActivity, 'Native per-agent activity is not implemented')
        self.feed = NativeActivity(clock=lambda: 1000.0)
        self.feed.bind_root({'id':'root-1','status':{'type':'idle'},'parentThreadId':None})

    def send(self, method, params, at=1001.0):
        return self.feed.observe({'method':method,'params':params}, observed_at=at)

    def test_waiting_view_exists_before_any_thread_or_turn(self):
        empty = NativeActivity(clock=lambda: 1000.0).snapshot(now=1002.0)
        self.assertEqual('WAITING_FOR_HOST', empty['status'])
        self.assertEqual([], empty['agents'])
        self.assertEqual('NOT_ASSESSED', empty['business_quality'])

    def test_public_speech_advances_its_agent_without_shell_activity(self):
        self.send('turn/started', {'threadId':'root-1','turn':{'id':'turn-1','status':'inProgress'}})
        self.send('item/agentMessage/delta', {'threadId':'root-1','turnId':'turn-1','itemId':'msg-1','delta':'Je lis '}, at=1002.0)
        before = self.feed.snapshot(now=1003.0)
        self.send('item/agentMessage/delta', {'threadId':'root-1','turnId':'turn-1','itemId':'msg-1','delta':'les sources.'}, at=1004.0)
        after = self.feed.snapshot(now=1005.0)
        self.assertGreater(after['cursor'], before['cursor'])
        self.assertEqual('Je lis les sources.', after['agents'][0]['last_output'])
        self.assertEqual(1004.0, after['agents'][0]['last_activity_at'])
        self.assertEqual(0, after['metrics']['tools'])
        self.assertEqual('NOT_ASSESSED', after['business_quality'])
        self.assertEqual(4.0, after['agents'][0]['elapsed_seconds'])

    def test_spawned_child_and_nested_child_keep_actual_parents(self):
        def spawn(parent, child, item):
            self.send('item/completed', {'threadId':parent,'turnId':'turn-1','item':{
                'type':'collabAgentToolCall','id':item,'tool':'spawnAgent','status':'completed',
                'senderThreadId':parent,'receiverThreadIds':[child],'agentsStates':{child:{'status':'running'}}}})
        spawn('root-1', 'child-1', 'spawn-1')
        spawn('child-1', 'child-2', 'spawn-2')
        self.send('item/agentMessage/delta', {'threadId':'child-2','turnId':'turn-child','itemId':'msg-c','delta':'Voici mon observation.'})
        agents = {a['id']:a for a in self.feed.snapshot()['agents']}
        self.assertEqual({'root-1','child-1','child-2'}, set(agents))
        self.assertEqual('root-1', agents['child-1']['parent_id'])
        self.assertEqual('child-1', agents['child-2']['parent_id'])
        self.assertEqual('Voici mon observation.', agents['child-2']['last_output'])

    def test_current_native_subagent_activity_registers_child_before_its_public_speech(self):
        self.send('item/completed', {'threadId':'root-1','turnId':'t','item':{
            'type':'subAgentActivity','id':'spawn-current','kind':'started',
            'agentThreadId':'child-current','agentPath':'/observer','model':'gpt-6-sol','reasoningEffort':'xhigh'}})
        self.send('item/agentMessage/delta', {'threadId':'child-current','turnId':'tc','itemId':'mc','delta':'Enfant prêt'})
        agents={a['id']:a for a in self.feed.snapshot()['agents']}
        self.assertIn('child-current',agents)
        self.assertEqual('root-1',agents['child-current']['parent_id'])
        self.assertEqual('Enfant prêt',agents['child-current']['last_output'])

    def test_parent_completion_notice_does_not_overwrite_a_child_failure(self):
        self.send('thread/started',{'thread':{'id':'child-fail','parentThreadId':'root-1','status':{'type':'idle'}}})
        self.send('turn/completed',{'threadId':'child-fail','turn':{'id':'failed-turn','status':'failed'}})
        self.send('item/completed',{'threadId':'root-1','turnId':'t','item':{
            'type':'subAgentActivity','id':'notice','kind':'completed','agentThreadId':'child-fail'}})
        child=next(a for a in self.feed.snapshot()['agents'] if a['id']=='child-fail')
        self.assertEqual('FAILED',child['status'])

    def test_other_sessions_and_private_reasoning_never_enter_public_feed(self):
        cursor = self.feed.snapshot()['cursor']
        self.send('item/agentMessage/delta', {'threadId':'unrelated','turnId':'t','itemId':'m','delta':'UNRELATED'})
        self.send('item/reasoning/summaryTextDelta', {'threadId':'root-1','delta':'PRIVATE'})
        self.send('item/started', {'threadId':'root-1','turnId':'t','item':{'type':'reasoning','id':'r','content':['PRIVATE']}})
        self.assertEqual(cursor, self.feed.snapshot()['cursor'])
        self.assertNotIn('PRIVATE', json.dumps(self.feed.snapshot()))
        self.assertNotIn('UNRELATED', json.dumps(self.feed.snapshot()))

    def test_long_tool_has_running_state_before_its_output_or_completion(self):
        item={'type':'commandExecution','id':'cmd-1','command':'python collect.py','status':'inProgress'}
        self.send('item/started', {'threadId':'root-1','turnId':'t','item':item})
        during=self.feed.snapshot(now=1006.0)
        self.assertEqual('RUNNING', during['tools'][0]['status'])
        self.assertEqual(5.0, during['tools'][0]['elapsed_seconds'])
        self.send('item/commandExecution/outputDelta', {'threadId':'root-1','turnId':'t','itemId':'cmd-1','delta':'Visite en cours'}, at=1007.0)
        self.assertEqual('Visite en cours', self.feed.snapshot()['agents'][0]['last_output'])

    def test_blocked_business_result_is_visible_even_when_native_tool_completed(self):
        item={'type':'commandExecution','id':'cmd-1','command':'proposition discovery check','status':'completed',
              'exitCode':2,'aggregatedOutput':'{"status":"BLOCKED","issues":["Missing mobile"]}'}
        self.send('item/completed', {'threadId':'root-1','turnId':'t','item':item})
        snap=self.feed.snapshot()
        self.assertEqual('BLOCKED', snap['tools'][0]['status'])
        self.assertEqual(1, snap['metrics']['blocked'])
        self.assertEqual('NOT_ASSESSED', snap['business_quality'])

    def test_final_message_replaces_streamed_text_and_duplicate_completion_is_idempotent(self):
        p={'threadId':'root-1','turnId':'t','itemId':'m','delta':'ha'}
        self.send('item/agentMessage/delta',p)
        self.send('item/agentMessage/delta',p)
        self.assertEqual('haha',self.feed.snapshot()['agents'][0]['last_output'])
        final={'threadId':'root-1','turnId':'t','item':{'type':'agentMessage','id':'m','text':'haha!','phase':'commentary'}}
        self.send('item/completed',final)
        before=self.feed.snapshot()['cursor']
        self.send('item/completed',final)
        self.assertEqual(before,self.feed.snapshot()['cursor'])
        self.assertEqual('haha!',self.feed.snapshot()['agents'][0]['last_output'])

    def test_terminal_turn_freezes_wall_time_without_claiming_business_success(self):
        self.send('turn/started', {'threadId':'root-1','turn':{'id':'t','status':'inProgress'}},at=1001.0)
        self.send('turn/completed', {'threadId':'root-1','turn':{'id':'t','status':'interrupted'}},at=1004.0)
        row=self.feed.snapshot(now=1100.0)['agents'][0]
        self.assertEqual('INTERRUPTED',row['status'])
        self.assertEqual(3.0,row['elapsed_seconds'])
        self.assertEqual('NOT_ASSESSED',self.feed.snapshot()['business_quality'])

    def test_host_idle_notification_does_not_erase_interrupted_turn(self):
        self.send('turn/started', {'threadId':'root-1','turn':{'id':'t','status':'inProgress'}})
        self.send('turn/completed', {'threadId':'root-1','turn':{'id':'t','status':'interrupted'}})
        self.send('thread/status/changed', {'threadId':'root-1','status':{'type':'idle'}})
        self.assertEqual('INTERRUPTED', self.feed.snapshot()['agents'][0]['status'])

    def test_native_turn_failure_message_remains_visible_after_disconnect(self):
        self.send('turn/started', {'threadId':'root-1','turn':{'id':'t','status':'inProgress'}})
        self.send('turn/completed', {'threadId':'root-1','turn':{'id':'t','status':'failed',
            'error':{'message':'Requested model is unavailable','codexErrorInfo':'modelNotFound'}}})
        self.feed.connection(False)
        s=self.feed.snapshot()
        self.assertEqual('FAILED',s['agents'][0]['status'])
        self.assertEqual('Requested model is unavailable',s['agents'][0]['last_output'])
        self.assertEqual(1,s['metrics']['failed_agents'])

    def test_disconnected_running_agent_stops_implying_observed_active_time(self):
        clock=[1000.0];feed=NativeActivity(clock=lambda:clock[0])
        feed.bind_root({'id':'parent','status':{'type':'idle'}});feed.connection(True)
        feed.observe({'method':'turn/started','params':{'threadId':'parent','turn':{'id':'t','status':'inProgress'}}},observed_at=1001.0)
        clock[0]=1006.0;feed.connection(False)
        snap=feed.snapshot(now=1100.0)
        self.assertEqual(5.0,snap['agents'][0]['elapsed_seconds'])
        self.assertEqual('SOURCE_UNAVAILABLE',snap['agents'][0]['observation_status'])

    def test_public_previews_redact_credentials_and_are_bounded(self):
        self.send('item/agentMessage/delta',{'threadId':'root-1','turnId':'t','itemId':'m',
            'delta':'Authorization: Bearer secret-value-123 '+('a'*10000)})
        s=self.feed.snapshot()
        self.assertNotIn('secret-value-123',json.dumps(s))
        self.assertLessEqual(len(s['agents'][0]['last_output']),4096)

    def test_reconnect_retains_agent_identity_and_marks_observation_gap(self):
        self.feed.connection(True)
        self.feed.connection(False)
        self.feed.connection(True)
        s=self.feed.snapshot()
        self.assertEqual(['root-1'],[a['id'] for a in s['agents']])
        self.assertIn('HOST_STREAM_GAP',s['diagnostics'])
        self.assertTrue(s['source_connected'])


if __name__=='__main__':unittest.main()
