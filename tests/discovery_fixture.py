"""Synthetic files for gate tests only; not a visual or live-site qualification."""
import hashlib
import json
from pathlib import Path
from PIL import Image


def write_report(run, batch='fixture'):
    root=Path(run['root'])/'research'/batch
    root.mkdir(parents=True)
    pages=[]; sources=[]
    for view in ('desktop','mobile'):
        stem=view
        (root/(stem+'.txt')).write_text('Synthetic navigation gate fixture')
        (root/(stem+'.html')).write_text('<h1>Synthetic gate fixture</h1>')
        Image.new('RGB',(40,40),'white').save(root/(stem+'.png'))
        artifacts=[]
        for suffix in ('.txt','.html','.png'):
            p=root/(stem+suffix)
            artifacts.append({'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
        sid='source:'+batch+'-'+view
        sources.append({'id':sid,'url':run['url'],'viewport':view,'retrieved_at':'2026-10-26T00:00:00+00:00','artifacts':artifacts})
        pages.append({'id':'page-'+view,'requested_url':run['url'],'final_url':run['url'],'viewport':view,'status':'captured','http_status':200,'attempt':1,
            'evidence':[{'source_id':sid,'kind':'scroll','text_path':stem+'.txt','html_path':stem+'.html','screenshot_path':stem+'.png','scroll_y':0,'height':40,'viewport_height':100,'visible_images':[]}],
            'interactions':[], 'exploration':{'status':'complete','unresolved':[],'bounded':True,'scroll':{'reached_end':True,'y':0,'height':40,'viewport':100}}})
    report={'schema_version':'2.0','batch_id':batch,'input_url':run['url'],'started_at':'2026-10-26T00:00:00+00:00','finished_at':'2026-10-26T00:00:01+00:00','status':'collected','semantic_analysis':'NOT_RUN',
        'pages':pages,'sources':sources,'link_entries':[],'social_candidates':[],'asset_candidates':[],'blocked_requests':[],
        'coverage':{'bounded':True,'exhaustive':False,'frontier':[],'pending_states':[],'attempted_urls':[run['url']],'seen_urls':[run['url']],'discovered_urls':[run['url']]},'limitations':['Synthetic gate fixture, not a quality review']}
    path=root/'discovery.json';path.write_text(json.dumps(report))
    return path


def install_discovery(run):
    from proposition_runtime.discovery_evidence import register
    result=register(run['root'],write_report(run))
    from public_research_fixture import install_public_research
    install_public_research(run)
    return result
