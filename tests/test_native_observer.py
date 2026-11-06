"""Real HTTP/UI projection for a waiting session and native public activity."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime.native_activity import NativeActivity
try:
    from proposition_runtime.native_observer import make_server
except ImportError:
    make_server = None


class NativeObserverTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(make_server,'Pre-run native observer server is not implemented')
        self.feed=NativeActivity()
        self.server=make_server(self.feed)
        self.worker=threading.Thread(target=self.server.serve_forever,daemon=True);self.worker.start()
        self.addCleanup(self.close)
        self.origin='http://127.0.0.1:'+str(self.server.server_port)

    def close(self):
        self.server.shutdown();self.server.server_close();self.worker.join(timeout=2)

    def get(self,path,authorized=True):
        h={'Authorization':'Bearer '+self.server.token} if authorized else {}
        with urllib.request.urlopen(urllib.request.Request(self.origin+path,headers=h),timeout=2) as r:return r.read()

    def test_real_waiting_view_and_feed_work_before_a_run_directory_exists(self):
        self.assertTrue(self.get('/'))
        snap=json.loads(self.get('/api/activity?after=0'))
        self.assertEqual('WAITING_FOR_HOST',snap['status'])
        self.assertEqual([],snap['agents'])
        self.assertEqual('NOT_ASSESSED',snap['business_quality'])
        with self.assertRaises(urllib.error.HTTPError) as fail:self.get('/api/activity',False)
        self.assertEqual(403,fail.exception.code)

    def test_parent_and_child_speech_project_to_real_rows_without_any_command(self):
        self.feed.bind_root({'id':'parent','status':{'type':'idle'}})
        self.feed.observe({'method':'thread/started','params':{'thread':{'id':'child','parentThreadId':'parent','status':{'type':'idle'}}}})
        self.feed.observe({'method':'item/agentMessage/delta','params':{'threadId':'child','turnId':'t','itemId':'m','delta':'Observation publique'}})
        snapshot=self.get('/api/activity')
        js=self.get('/assets/runtime-core.js')
        code=js.decode()+"\nconst fs=require('fs');const s=JSON.parse(fs.readFileSync(0,'utf8'));const p=module.exports.project(s,s.observed_at);console.log(JSON.stringify(p));"
        p=subprocess.run(['node','-e',code],input=snapshot,text=False,capture_output=True,check=True)
        model=json.loads(p.stdout)
        child=next(t for t in model['tasks'] if t.get('agent_id')=='child')
        parent=next(t for t in model['tasks'] if t.get('agent_id')=='parent')
        self.assertEqual(parent['id'],child['parent'])
        self.assertIn('Observation publique',child['detail'])
        self.assertEqual(0,model['metrics']['commands'])
        self.assertTrue(model['nativeAgentsObserved'])

    def test_deterministic_tools_stay_inside_their_real_agents_activity(self):
        self.feed.bind_root({'id':'parent','status':{'type':'idle'}})
        self.feed.observe({'method':'item/completed','params':{'threadId':'parent','turnId':'t','item':{
            'type':'commandExecution','id':'check','command':'check','status':'completed','exitCode':2,
            'aggregatedOutput':'{"status":"BLOCKED"}'}}})
        snapshot=self.get('/api/activity');js=self.get('/assets/runtime-core.js')
        code=js.decode()+"\nconst fs=require('fs');const s=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(module.exports.project(s,s.observed_at)));"
        p=subprocess.run(['node','-e',code],input=snapshot,capture_output=True,check=True)
        model=json.loads(p.stdout)
        rows=[t for t in model['tasks'] if t['id']!='root']
        self.assertEqual(['parent'],[t.get('agent_id') for t in rows])
        self.assertEqual(1,model['totalTasks'])
        self.assertIn('BLOCKED',rows[0]['detail'])
        self.assertEqual(1,model['metrics']['commands'])

    def test_actual_browser_waits_before_host_then_shows_speech_and_interruption(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.goto(self.origin+'/#'+self.server.token)
                expect(page.locator('.vm-status b')).to_have_text('En attente de Codex')
                expect(page.locator('.vm-speed select')).to_have_value('1')
                expect(page.locator('.vm-speed select')).to_be_disabled()
                self.assertIsNotNone(self.server.ui_ready_at)
                self.feed.connection(True)
                self.feed.bind_root({'id':'parent','status':{'type':'idle'}})
                self.feed.observe({'method':'turn/started','params':{'threadId':'parent','turn':{'id':'t','status':'inProgress'}}},observed_at=time.time()-10)
                self.feed.observe({'method':'item/agentMessage/delta','params':{'threadId':'parent','turnId':'t','itemId':'m','delta':'Je lis les sources sans commande.'}})
                expect(page.locator('.vm-root-row .vm-name')).to_have_text('Activité des agents')
                self.assertEqual(0,page.locator('.vm-root-row button').count())
                bar=page.locator('[data-row="agent-parent"] .vm-bar')
                self.assertGreater(bar.bounding_box()['width'],20,'Real short activity must remain visible on the timeline')
                page.get_by_role('button',name='Agent principal · Codex',exact=True).click()
                page.locator('.vm-detail p').filter(has_text='Je lis les sources sans commande.').wait_for()
                expect(page.get_by_role('complementary',name='Activité publique de l’agent')).to_be_visible()
                expect(page.locator('.vs-editor')).to_be_hidden()
                self.feed.observe({'method':'turn/completed','params':{'threadId':'parent','turn':{'id':'t','status':'interrupted'}}})
                self.feed.connection(False)
                expect(page.locator('.vm-status b')).to_have_text('Interrompu')
                self.assertFalse(page.locator('.vm-done').is_visible())
            finally:
                browser.close()


if __name__=='__main__':unittest.main()
