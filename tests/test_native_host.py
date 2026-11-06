"""The protocol boundary is a real subprocess; no model/provider is doubled here."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
try:
    from proposition_runtime.native_host import AppServerClient
except ImportError:
    AppServerClient = None

FAKE = r'''
import json,sys,time
for line in sys.stdin:
 r=json.loads(line);method=r['method']
 if method=='initialize':
  print(json.dumps({'id':r['id'],'result':{'userAgent':'fixture'}}),flush=True)
 elif method=='probe':
  for name,text in [('item/reasoning/textDelta','PRIVATE'),('item/agentMessage/delta','Public output')]:
   print(json.dumps({'method':name,'params':{'threadId':'root','turnId':'t','itemId':'m','delta':text}}),flush=True)
  print(json.dumps({'id':r['id'],'result':{'observed':True}}),flush=True)
 elif method=='slow':time.sleep(2)
 elif method=='eof':break
 elif method=='large':
  print(json.dumps({'method':'item/completed','params':{'item':{'type':'mcpToolCall','result':'x'*(4*1024*1024)}}}),flush=True)
  print(json.dumps({'id':r['id'],'result':{'continued':True}}),flush=True)
 elif method=='approval':
  print(json.dumps({'id':'approval-request','method':'item/commandExecution/requestApproval','params':{}}),flush=True)
  reply=json.loads(sys.stdin.readline())
  print(json.dumps({'id':r['id'],'result':{'denied':bool(reply.get('error'))}}),flush=True)
'''


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(AppServerClient, 'Native app-server transport is not implemented')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.script=Path(self.tmp.name)/'server.py';self.script.write_text(FAKE)

    def test_streamed_public_activity_is_delivered_while_request_is_in_flight(self):
        seen=[]
        with AppServerClient(argv=[sys.executable,'-u',str(self.script)],on_notification=seen.append) as host:
            result=host.request('probe',{},timeout=2)
            self.assertEqual({'observed':True},result)
            self.assertEqual(['item/agentMessage/delta'],[e['method'] for e in seen])
            self.assertNotIn('PRIVATE',json.dumps(seen))

    def test_timeout_is_unknown_and_does_not_resend_the_request(self):
        with AppServerClient(argv=[sys.executable,'-u',str(self.script)]) as host:
            with self.assertRaisesRegex(TimeoutError,'outcome is unknown'):
                host.request('slow',{},timeout=0.05)
            self.assertTrue(host.outcome_unknown)
            self.assertIsNone(host.process.poll())

    def test_owned_transport_connection_lifecycle_reaches_the_observer(self):
        states=[]
        host=AppServerClient(argv=[sys.executable,'-u',str(self.script)])
        host.on_connection=states.append
        with host:host.request('probe',{},timeout=2)
        self.assertEqual([True,False],states)

    def test_oversized_observation_is_dropped_without_blocking_host_responses(self):
        with AppServerClient(argv=[sys.executable,'-u',str(self.script)]) as host:
            result=host.request('large',{},timeout=2)
            self.assertEqual({'continued':True},result)
            self.assertIn('HOST_MESSAGE_BUDGET',host.diagnostics)

    def test_unavailable_interactive_request_is_explicitly_rejected_not_left_hanging(self):
        with AppServerClient(argv=[sys.executable,'-u',str(self.script)]) as host:
            result=host.request('approval',{},timeout=.3)
            self.assertTrue(result['denied'])
            self.assertIn('HOST_INTERACTION_UNAVAILABLE',host.diagnostics)

    def test_lost_inflight_response_marks_outcome_unknown_before_returning(self):
        with AppServerClient(argv=[sys.executable,'-u',str(self.script)]) as host:
            with self.assertRaises(RuntimeError):host.request('eof',{},timeout=1)
            self.assertTrue(host.outcome_unknown)


if __name__=='__main__':unittest.main()
