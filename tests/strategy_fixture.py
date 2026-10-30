"""Offline synthetic handoff/cache, for consistency tests only."""
import hashlib
import json
from pathlib import Path
from proposition_runtime import state


def make_analysis(run):
    root=Path(run['root'])
    spec=next(s for s in json.loads((state.DATA_ROOT/'upstream-lock.json').read_text())['families'] if s['id']=='marketingskills')
    tree=root/'fixture-methods'/spec['id']/spec['commit']/'source'
    blobs=[];inventory=[]
    for name in spec['entrypoints']+spec['reference_files']+spec['license_files']:
        file=tree/name;file.parent.mkdir(parents=True,exist_ok=True)
        content=('Synthetic test reference '+name+'\n').encode();file.write_bytes(content)
        blobs.append(dict(path=name,type='blob',mode='100644',size=len(content),sha=hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()))
        inventory.append(dict(path=name,sha256=hashlib.sha256(content).hexdigest()))
    metadata=json.dumps(dict(truncated=False,tree=blobs)).encode();(tree.parent/'tree.json').write_bytes(metadata)
    (tree.parent/'receipt.json').write_text(json.dumps(dict(repository=spec['repository'],commit=spec['commit'],source_paths=spec['source_paths'],
        metadata_sha256=hashlib.sha256(metadata).hexdigest(),inventory=inventory,licenses=[dict(path='LICENSE',sha256=hashlib.sha256((tree/'LICENSE').read_bytes()).hexdigest())])))
    methods=[dict(name=name,commit=spec['commit'],reference_root=str(tree),sha256=hashlib.sha256((tree/entry).read_bytes()).hexdigest(),
        mode='adapted',read_sections=['Synthetic section, not actual method use'],adaptation='Public sources only, no owner validation',applied_to=['a1','n1'])
        for name,entry in zip(('product-marketing','customer-research'),spec['entrypoints'])]
    (root/'strategy-source.txt').write_text('Fictional offer with product details; no market demand proven')
    state.add_source(root,'strategy-source','strategy-source.txt',kind='public',locator=run['url'])
    (root/'mission-trace.txt').write_text('Synthetic browser task trace, not actual user research')
    state.add_source(root,'mission-trace','mission-trace.txt',kind='observation',locator=run['url'])
    data=dict(version=run['metadata'].get('audience_handoff_contract',1),methods=methods,
        audiences=[dict(id='a1',role='Product visitor',kind='site_visitor',status='hypothesis',source_ids=['strategy-source'])],
        needs=[dict(id='n1',audience_ids=['a1'],status='hypothesis',source_ids=['strategy-source'],source_group='official-offer',context='Compare an existing product detail',
            delta='baseline_not_compared',decision='retained',recommendation='Make the sourced product detail accessible',experience_consequence='Show material before the existing quote action',
            alternative='Existing detail may already be sufficient',mission_ids=['m1'])],
        missions=[dict(id='m1',need_ids=['n1'],target=run['url'],task='Locate the product detail',success='Detail visible before quote',stop='No form submission',outcome='completed',source_ids=['mission-trace'],limits='Synthetic trace only')],
        unknowns=['Buyer priority and commercial effect unknown'])
    path=root/'analysis.json';path.write_text(json.dumps(data));return path


def install_strategy(run):
    from proposition_runtime import strategy
    path=make_analysis(run);strategy.register(run['root'],path)
    data=json.loads(path.read_text());summary=strategy.summary(data)
    root=Path(run['root']);(root/'company.json').write_text(json.dumps(dict(audience_need_summary=summary)))
    state.add_artifact(root,'company-evidence-brief','company.json','internal',['artifact:observation-analysis-map'])
    run=state.load_run(root);record=run['artifacts']['creative-inputs'];p=root/record['path'];inputs=json.loads(p.read_text())
    inputs['audience_need_summary']=summary;inputs['observations'][0]['need_ids']=['n1']
    inputs['observations'][0]['proof']='source:strategy-source'
    p.write_text(json.dumps(inputs))
    state.add_artifact(root,'creative-inputs',record['path'],record['audience'],record['dependencies']+['artifact:company-evidence-brief','source:strategy-source'])
