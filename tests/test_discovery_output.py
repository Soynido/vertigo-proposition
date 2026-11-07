"""Consumer CLI returns bounded evidence pointers, not repeated navigation inventories."""
import contextlib,io,json,sys,unittest
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/proposition/scripts'))
from proposition_runtime import cli,state,discovery_evidence,telemetry
import test_state as fixtures
from discovery_fixture import write_report

class DiscoveryOutputTests(unittest.TestCase):
    def setUp(self):
        f=fixtures.StateTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.run=f.new_run();self.root=Path(self.run['root']);self.path=write_report(self.run)
        d=json.loads(self.path.read_text());d['link_entries']=[{'url':self.run['url'],'observed_url':self.run['url'],'text':'Venue','source_id':'source:fixture-desktop'} for _ in range(5000)]
        self.path.write_text(json.dumps(d));discovery_evidence.register(self.root,self.path)
    def test_cli_default_is_compact_and_keeps_full_report_provenance(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=cli.main(['discovery','check',str(self.root)])
        self.assertEqual(0,code)
        self.assertLess(len(output.getvalue()),8192)
        d=json.loads(output.getvalue());self.assertEqual(5000,d['entry_count']);self.assertEqual(1,d['destination_count'])
        self.assertTrue(d['reports']);self.assertEqual(5000,len(json.loads(self.path.read_text())['link_entries']))
    def test_one_check_reuses_hashes_and_the_next_check_detects_changed_bytes(self):
        with telemetry.TraceRecorder(self.root):
            result=cli.execute(cli.parser().parse_args(['discovery','check',str(self.root)]))
        self.assertEqual('PASS',result['status'])
        events=[json.loads(l) for p in (self.root/'telemetry').glob('*.jsonl') for l in p.read_text().splitlines()]
        hashes=Counter()
        for e in events:
            if e['name']=='validation.hash':hashes[e['attributes'].get('file_id')]+=e['attributes']['count']
        self.assertTrue(hashes);self.assertEqual(1,max(hashes.values()))
        (self.path.parent/'desktop.txt').write_text('Changed after check')
        self.assertEqual('BLOCKED',cli.execute(cli.parser().parse_args(['discovery','check',str(self.root)]))['status'])

    def test_explicit_full_output_retains_the_historical_inventory_interface(self):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=cli.main(['discovery','check',str(self.root),'--full-output'])
        self.assertEqual(0,code)
        self.assertEqual(5000,len(json.loads(output.getvalue())['entries']))

if __name__=='__main__':unittest.main()
