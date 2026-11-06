"""Launch/STOP invariants at a real local JSON-RPC process boundary.

The protocol fixture does not qualify a model, panel placement or client work.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime.native_host import AppServerClient
from proposition_runtime.native_activity import NativeActivity
try:
    from proposition_runtime.native_launch import NativeLaunch
except ImportError:
    NativeLaunch=None

SERVER=r'''
import json,sys
from pathlib import Path
base=Path(sys.argv[1]);active=False;started=0
for line in sys.stdin:
 r=json.loads(line);m=r['method'];p=r.get('params',{})
 with (base/'calls.jsonl').open('a') as out:out.write(json.dumps(r)+'\n')
 if 'id' not in r:continue
 if m=='initialize':result={}
 elif m=='account/read':result={'account':{'type':'chatgpt'}}
 elif m=='model/list':result={'data':[{'id':'gpt-6-sol','model':'gpt-6-sol','supportedReasoningEfforts':[{'reasoningEffort':'xhigh'}]}],'nextCursor':None}
 elif m=='thread/start':
  result={'thread':{'id':'owned','status':{'type':'idle'}},'model':p['model'],'reasoningEffort':p['config']['model_reasoning_effort'],'instructionSources':[str(base/'AGENTS.md')]}
  if (base/'extra-instructions').exists():result['instructionSources'].append(str(base/'unexpected.md'))
  if (base/'change-input').exists():(base/'AGENTS.md').write_text('Changed during host setup')
 elif m=='turn/start':
  started+=1;active=True;result={'turn':{'id':'t'+str(started),'status':'inProgress'}}
  if (base/'lose-response').exists():continue
 elif m=='thread/read':result={'thread':{'id':'owned','status':{'type':'active' if active else 'idle'}}}
 elif m=='thread/turns/list':result={'data':[{'id':'foreign' if (base/'foreign-turn').exists() else 't'+str(started),'status':'inProgress' if active else 'completed'}],'nextCursor':None}
 elif m=='turn/interrupt':active=False;result={}
 elif m=='fixture/finish':active=False;result={}
 else:result={}
 print(json.dumps({'id':r['id'],'result':result}),flush=True)
'''


class NativeLaunchTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(NativeLaunch,'Native launch preconditions and idempotent STOP are missing')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name).resolve();(self.base/'AGENTS.md').write_text('Installed entrypoint')
        script=self.base/'host.py';script.write_text(SERVER)
        self.feed=NativeActivity();self.observer=SimpleNamespace(ui_ready_at=1,feed=self.feed)
        self.host=AppServerClient(argv=[sys.executable,'-u',str(script),str(self.base)],on_notification=self.feed.observe,on_connection=self.feed.connection)
        self.host.__enter__();self.addCleanup(self.host.close)
        self.launch=NativeLaunch(self.host,self.observer,self.base/'session',workspace=self.base,
            prompt='https://github.com/fixture/kit\nhttps://prospect.example/',model='gpt-6-sol',effort='xhigh',
            inputs=[self.base/'AGENTS.md'],lane_id='calling-lane',
            panel_open={'status':'queued','threadId':'calling-lane'})

    def calls(self):return [json.loads(x) for x in (self.base/'calls.jsonl').read_text().splitlines()]

    def test_missing_same_lane_open_receipt_prevents_any_thread_or_turn_creation(self):
        self.launch.panel_open=None
        with self.assertRaisesRegex(ValueError,'UI'):self.launch.start()
        self.assertNotIn('thread/start',[c['method'] for c in self.calls()])

    def test_preexisting_stop_prevents_dispatch_even_after_panel_open(self):
        (self.launch.session/'stop.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Stopped'):self.launch.start()
        self.assertNotIn('turn/start',[c['method'] for c in self.calls()])

    def test_a_panel_opened_in_another_lane_does_not_satisfy_startup(self):
        self.launch.panel_open={'status':'queued','threadId':'maintainer-lane'}
        with self.assertRaisesRegex(ValueError,'UI'):self.launch.start()
        self.assertNotIn('thread/start',[c['method'] for c in self.calls()])

    def test_correctly_queued_panel_does_not_require_human_viewing(self):
        self.observer.ui_ready_at=None
        result=self.launch.start()
        self.assertEqual('RUNNING',result['status'])
        self.assertEqual('queued',result['panel_open']['status'])
        self.assertIsNone(result['ui_ready_at'])

    def test_disconnected_source_prevents_launch(self):
        self.feed.connection(False)
        with self.assertRaisesRegex(ValueError,'source'):self.launch.start()
        self.assertNotIn('thread/start',[c['method'] for c in self.calls()])

    def test_exact_prompt_requested_model_and_instruction_source_are_preserved(self):
        result=self.launch.start();self.assertEqual('RUNNING',result['status'])
        calls=self.calls();turn=next(c['params'] for c in calls if c['method']=='turn/start')
        self.assertEqual(self.launch.prompt,turn['input'][0]['text'])
        self.assertEqual('gpt-6-sol',turn['model']);self.assertEqual('xhigh',turn['effort'])
        replay=self.launch.start();self.assertEqual(result,replay)
        self.assertEqual(1,len([c for c in self.calls() if c['method']=='turn/start']))

    def test_input_changed_during_host_preparation_never_reaches_a_turn(self):
        (self.base/'change-input').touch()
        with self.assertRaisesRegex(ValueError,'input'):self.launch.start()
        self.assertNotIn('turn/start',[c['method'] for c in self.calls()])

    def test_an_additional_loaded_instruction_source_must_be_in_the_frozen_inventory(self):
        (self.base/'extra-instructions').touch();(self.base/'unexpected.md').write_text('Extra instructions')
        with self.assertRaisesRegex(ValueError,'input inventory'):self.launch.start()
        self.assertNotIn('turn/start',[c['method'] for c in self.calls()])

    def test_idle_stop_does_not_send_a_message_or_create_a_new_turn(self):
        self.launch.start();self.host.request('fixture/finish',{})
        result=self.launch.stop();self.assertEqual('ALREADY_IDLE',result['status'])
        self.assertEqual(result,self.launch.stop())
        calls=self.calls();self.assertEqual(1,len([c for c in calls if c['method']=='turn/start']))
        self.assertNotIn('turn/interrupt',[c['method'] for c in calls])
        self.assertNotIn('turn/steer',[c['method'] for c in calls])

    def test_active_stop_interrupts_only_owned_turn_and_confirms_readback(self):
        self.launch.start();result=self.launch.stop();self.assertEqual('STOP_CONFIRMED',result['status'])
        self.assertEqual(result,self.launch.stop())
        interrupts=[c['params'] for c in self.calls() if c['method']=='turn/interrupt']
        self.assertEqual([{'threadId':'owned','turnId':'t1'}],interrupts)

    def test_a_different_active_turn_is_not_interrupted(self):
        self.launch.start();(self.base/'foreign-turn').touch()
        with self.assertRaisesRegex(ValueError,'owned turn'):self.launch.stop()
        self.assertNotIn('turn/interrupt',[c['method'] for c in self.calls()])

    def test_unknown_launch_response_never_dispatches_again(self):
        (self.base/'lose-response').touch()
        with self.assertRaises(TimeoutError):self.launch.start(timeout=.05)
        with self.assertRaisesRegex(ValueError,'unknown'):self.launch.start()
        self.assertEqual(1,len([c for c in self.calls() if c['method']=='turn/start']))

    def test_a_different_lane_cannot_reuse_another_lanes_launch_receipt(self):
        self.launch.start()
        other=NativeLaunch(self.host,self.observer,self.base/'session',workspace=self.base,
            prompt=self.launch.prompt,model='gpt-6-sol',effort='xhigh',inputs=[self.base/'AGENTS.md'],
            lane_id='other-lane',panel_open={'status':'queued','threadId':'other-lane'})
        with self.assertRaisesRegex(ValueError,'frozen inputs'):other.start()
        self.assertEqual(1,len([c for c in self.calls() if c['method']=='turn/start']))

    def test_prepared_hashes_cannot_be_replaced_by_a_later_constructor_read(self):
        frozen=NativeLaunch(self.host,self.observer,self.base/'frozen',workspace=self.base,
            prompt=self.launch.prompt,model='gpt-6-sol',effort='xhigh',inputs={str(self.base/'AGENTS.md'):'0'*64},
            lane_id='calling-lane',panel_open={'status':'queued','threadId':'calling-lane'})
        with self.assertRaisesRegex(ValueError,'input changed'):frozen.start()
        self.assertNotIn('thread/start',[c['method'] for c in self.calls()])


if __name__=='__main__':unittest.main()
