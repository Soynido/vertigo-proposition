"""Fictional public material for web consistency tests, never a creative benchmark."""
import json
from pathlib import Path
from proposition_runtime import state,web
from proposition_runtime.preservation import freeze_creatives
from experience_fixture import prepare_experience


def prepare_web(root, *, complete_evidence=False):
    run = state.init_run('https://fixture.example/', Path(root)/'runs',
        {'actor':'fixture-author','responsible':'fixture-owner','responsible_confirmed':True,
         'required_reviewers':['review-a','review-b'],'parameters':{}}, delivery_format='web')
    folder = Path(run['root'])
    if complete_evidence:
        from discovery_fixture import install_discovery
        install_discovery(run)
        run=state.load_run(folder);run['metadata']['fixture_strategy']=True
        state.save_run(folder,run)
    retained = prepare_experience(run)
    freeze_creatives(folder, {'revision':'r1','actor':'fixture-author',
        'decision':'Fictional selection, not a claim of human taste.','retained':retained})
    run = state.load_run(folder)
    source = folder/'outputs/web-source'
    source.mkdir(parents=True)
    html=('<!doctype html><html lang="fr"><head><title>Fixture</title>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="stylesheet" href="style.css"></head><body><main>'
        '<section id="opening"><h1>Une matière à explorer</h1><img src="image.svg" alt="Illustration géométrique de test"></section>'
        '<section id="reveal"><h2>Le matériau et son usage</h2><p>Une proposition, sans gain mesuré.</p></section>'
        '<section id="decision"><h2>La mission proposée</h2><p>Définir ensemble un premier parcours.</p>'
        '<a id="quote" href="https://fixture.example/quote">Demander un devis</a>'
        '<a id="next" href="#decision">Choisir le premier parcours</a>'
        '<a href="sources.html">Sources</a></section></main><script type="module" src="app.js"></script></body></html>')
    (source/'style.css').write_text('body{margin:0;font:18px sans-serif}section{min-height:100vh;padding:24px;box-sizing:border-box}img{max-width:100%;width:160px}a{display:block;padding:12px}')
    (source/'app.js').write_text('document.documentElement.dataset.fixtureReady="true";')
    (source/'image.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160"><rect width="160" height="160" fill="navy"/></svg>')
    (source/'sources.html').write_text('<!doctype html><html lang="fr"><title>Sources de la fixture</title><p>Illustration fictive. Aucune promesse de résultat.</p></html>')
    plan={'version':1,'entrypoint':'index.html','sources_page':'sources.html',
        'public_files':['index.html','style.css','app.js','image.svg','sources.html'],
        'inputs_sha256':run['artifacts']['creative-inputs']['sha256'],
        'selection_sha256':run['metadata']['creative_selection']['sha256'],
        'coverage':[{'id':f'K{i:02}','selector':'#decision' if i>5 else '#reveal' if i>1 else '#opening',
                     'proofs':['source:experience-source'],'claim_status':'proposed',
                     'meaning':'Synthetic evidence slot for consistency testing.'}
                    for i in range(1,9)],
        'scenes':[{'id':'material','selector':'main','meaning':'From material to a scoped visitor action',
            'states':[0,.5,1],'mobile':'Stack the content in reading order','reduced_motion':'Static content and actions remain available',
            'intent_ids':[r['id'] for r in retained],'media_paths':['image.svg'],
            'interaction':'Native document scroll retains accessible content and quote action'}],
        'engine':{'kind':'custom','files':['app.js'],'rationale':'Synthetic build fixture only, never an immersive quality claim'},
        'actions':[{'id':'quote','selector':'#quote','target':'https://fixture.example/quote','purpose':'prospect'},
                   {'id':'next','selector':'#next','target':'#decision','purpose':'vertigo'}],
        'media':[{'path':'image.svg','kind':'illustration','source_ref':'source:experience-source',
                  'rights':'allowed','changes':'Geometric fixture only; not a real factual subject.'}]}
    by_id={r['id']:r for r in plan['coverage']}
    by_id['K03']['mechanism']='Show the material and the existing quote action in one journey.'
    by_id['K06'].update(effect='A clearer explanation could support the visitor decision; unmeasured.',
        measurement={lever:{'indicator':indicator,'data_status':'unknown','reason':'No prospect analytics access in this fixture'}
            for lever,indicator in [('acquisition','Qualified visits'),('conversion','Completed quote requests')]})
    by_id['K07']['mission']={'scope':'First material journey','included':['Concept and implementation'],
        'excluded':['Full catalogue migration'],'conditions':['Confirm scope and media rights']}
    by_id['K08']['decision']='Agree the first material journey to prototype.'
    plan_path = folder/'web-plan.json'
    plan_path.write_text(json.dumps(plan))
    web.plan_run(folder,source,plan_path)
    (source/'index.html').write_text(html)
    return run, source, plan_path


def assess_web_fixture(run):
    """Synthetic schema receipts only; never an assertion of real agent independence."""
    root=Path(run['root']);current=state.load_run(root)
    reviewed={'artifact:'+name:row['sha256'] for name,row in current['artifacts'].items()}
    evidence=list(reviewed)
    for row in state._requirements(current):
        if row['stage_id'] not in ('internal.handoffs','publication.approved'):
            state.record_evaluation(root,row['id'],{'status':'PASS','applicable':True,'unknowns':[],
                'evidence':evidence,'reason':'Synthetic contract fixture, not client qualification'})
    def receipt(reviewer,stage=None):
        data={'run_id':run['id'],'reviewer_id':reviewer,'author_id':current['profile']['actor'],
            'context_isolated':True,'author_context_inherited':False,'verdict_shared':False,
            'method':'synthetic-schema-fixture-not-an-actual-review','artifact_hashes':reviewed}
        if stage:data['stage_id']=stage
        name='fixture-receipt-'+(stage or reviewer);path=root/(name+'.json')
        path.write_text(json.dumps(data));state.add_artifact(root,name,path,'internal',evidence)
        return name
    for reviewer in current['profile']['required_reviewers']:
        state.record_evaluation(root,'quality',{'reviewer_id':reviewer,'status':'PASS','scores':[2,2,2,2,2],
            'independence':{'receipt_id':receipt(reviewer)},'evidence':evidence,'unknowns':[]})
    for stage in state._quality_stages(current):
        state.record_stage_review(root,stage,{'reviewer_id':'fixture-stage-reviewer','status':'PASS','scores':[2,2,2,2,2],
            'independence':{'receipt_id':receipt('fixture-stage-reviewer',stage)},'evidence':evidence,'unknowns':[],
            'criterion_evidence':{r['id']:evidence for r in state._stages(current)[stage]['criteria']}})
    return state.load_run(root)
