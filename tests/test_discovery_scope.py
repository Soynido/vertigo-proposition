"""Typed resources stay in the inventory; entity exclusions need primary proof."""
import hashlib,json,unittest
import test_state as fixtures
from discovery_fixture import write_report
from proposition_runtime import state,discovery_evidence as de

class DiscoveryScopeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.StateTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.run=self.fixture.new_run();self.path=write_report(self.run)

    def report(self,links,text=None):
        data=json.loads(self.path.read_text())
        data['link_entries']=[{'url':url,'text':label,'source_id':'source:fixture-desktop'} for url,label in links]
        data['coverage']['discovered_urls'].extend(url for url,_ in links)
        if text:
            p=self.path.parent/'desktop.txt';p.write_text(text)
            item=next(a for a in data['sources'][0]['artifacts'] if a['path']=='desktop.txt')
            item.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size)
        self.path.write_text(json.dumps(data));return de.register(self.run['root'],self.path)

    def test_resources_are_reconciled_as_resources_not_missing_mobile_pages(self):
        result=self.report([(self.run['url']+'film.mp4','Film'),(self.run['url']+'brochure.pdf','Brochure')])
        self.assertEqual('PASS',result['status'],result['issues'])
        self.assertEqual({'media','document'},{e['destination_kind'] for e in result['entries']})
        self.assertEqual({'resource_pending'},{e['destination_status'] for e in result['entries']})
        channels=de.inspect_channels(state.load_run(self.run['root']))
        self.assertEqual(2,len(channels['entries']))
        self.assertEqual('BLOCKED',channels['status'])

    def test_a_different_entity_needs_a_bound_primary_quote(self):
        url=self.run['url']+'other-hotel/'
        self.report([(url,'Other Hotel')],text='Current Hotel. Discover Other Hotel in another city.')
        api=getattr(de,'register_scope',None);self.assertTrue(callable(api),'Scope registration is missing')
        path=self.path.parent/'scope.json';data={'version':1,'client_entity':'Current Hotel','destinations':[{
            'url':url,'kind':'other_entity','entity_name':'Other Hotel','source_id':'fixture-desktop',
            'quote':'Discover Other Hotel in another city.','reason':'Separate establishment, not the prospect homepage.'}]}
        path.write_text(json.dumps(data));result=api(self.run['root'],path)
        self.assertEqual('PASS',result['status'],result['issues'])
        self.assertEqual('scoped_other_entity',result['entries'][0]['destination_status'])

    def test_unclassified_html_stays_required(self):
        result=self.report([(self.run['url']+'offer/','Our offer')])
        self.assertEqual('BLOCKED',result['status'])

    def test_observed_html_overrides_a_misleading_image_suffix(self):
        url=self.run['url']+'offer.jpg';data=json.loads(self.path.read_text())
        page=dict(data['pages'][0],requested_url=url,id='page-misleading')
        data['pages'].append(page);data['coverage']['discovered_urls'].append(url)
        self.path.write_text(json.dumps(data));result=de.register(self.run['root'],self.path)
        self.assertEqual('BLOCKED',result['status'])
        self.assertTrue(any(url+' mobile' in issue for issue in result['issues']))

    def test_host_supplement_is_adopted_into_the_same_physical_gate(self):
        data=json.loads(self.path.read_text());data['pages'][1]['status']='partial'
        data['pages'][1]['exploration']['unresolved']=['fixture_failed_state']
        self.path.write_text(json.dumps(data));self.assertEqual('BLOCKED',de.register(self.run['root'],self.path)['status'])
        previous=hashlib.sha256(self.path.read_bytes()).hexdigest()
        host=write_report(self.run,batch='host');data=json.loads(host.read_text());data['backend']='host-browser'
        data['continuation']={'previous_report_sha256':previous};host.write_text(json.dumps(data))
        api=getattr(de,'register_supplement',None);self.assertTrue(callable(api),'Explicit supplement adoption is missing')
        self.assertEqual('PASS',api(self.run['root'],host)['status'])

    def test_invented_scope_quote_does_not_remove_an_obligation(self):
        url=self.run['url']+'other/'
        self.report([(url,'Other')],text='Current Hotel')
        api=getattr(de,'register_scope',None);self.assertTrue(callable(api),'Scope registration is missing')
        path=self.path.parent/'scope.json';path.write_text(json.dumps({'version':1,'client_entity':'Current Hotel',
            'destinations':[{'url':url,'kind':'other_entity','entity_name':'Other Hotel','source_id':'fixture-desktop',
                'quote':'Invented Other Hotel','reason':'Not the prospect'}]}))
        with self.assertRaises(ValueError):api(self.run['root'],path)

if __name__=='__main__':unittest.main()
