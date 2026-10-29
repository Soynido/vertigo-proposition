"""Trace public host research in Discovery; never infer marketing truth."""
from __future__ import annotations

import json
from pathlib import Path
from . import state

TOPICS = ('google_search', 'google_ads', 'meta_ads', 'reviews')
TASKS = {
    'google_search': 'Find official offer pages and relevant public search results. Record the actual search provider; a host search is not necessarily a Google SERP. No private ranking or traffic inference.',
    'google_ads': 'Try the public Google Ads Transparency Center for the verified advertiser/domain. If inaccessible, try a bounded public search for that entity and record its weaker scope. No spend, targeting, performance or global absence claim.',
    'meta_ads': 'Try the public Meta Ad Library using the verified page/advertiser and an explicit country/status. If blocked, use a bounded public lookup and state that it does not establish library coverage.',
    'reviews': 'Find independently published public reviews of the verified entity. Separate company-curated testimonials, duplicates and republications. Record sample/date/context; no invented ICP, buyer role or user preference.',
}


def text(value, label):
    if not isinstance(value,str) or not value.strip(): raise ValueError('Missing '+label)
    return value


def current_source(run, identifier, *, public=False):
    source=run['sources'].get(identifier)
    if not source or source['status']!='COLLECTED' or not source.get('path'):
        raise ValueError('Research requires collected evidence: '+str(identifier))
    if public and source['kind']!='public': raise ValueError('Research evidence must be public: '+str(identifier))
    if source['kind']=='private': raise ValueError('Private evidence cannot enter public research')
    if state._sha(state._safe_path(Path(run['root']),source['path']))!=source['sha256']:
        raise ValueError('Research evidence changed: '+str(identifier))
    return 'source:'+identifier


def validate(run, data):
    """Validate only declared operations, scope and current evidence links."""
    research=data.get('public_research')
    if research is None: return []
    if research.get('version')!=1: raise ValueError('Unsupported public research contract')
    entity=research['entity'];text(entity.get('name'),'entity name');text(entity.get('match_reason'),'entity match reason')
    if not isinstance(entity.get('source_ids'),list) or not entity['source_ids']:
        raise ValueError('Entity association requires public source evidence')
    refs=[current_source(run,s,public=True) for s in entity['source_ids']]
    attempts={}
    for row in data['attempts']:
        if 'topic' not in row: continue
        if row['topic'] not in TOPICS: raise ValueError('Unknown public research topic')
        identifier=text(row.get('id'),'research attempt id')
        if identifier in attempts: raise ValueError('Duplicate research attempt id')
        attempts[identifier]=row
        for key in ('operation','query','provider','geography','window'): text(row.get(key),'research '+key)
        if row['status']=='retrieved':
            refs.append(current_source(run,row.get('source_id'),public=True))
        elif row['status']=='unavailable':
            refs.append(current_source(run,row.get('trace_source_id')))
            fallback=row.get('fallback',{})
            if not isinstance(fallback,dict) or not (fallback.get('attempt_id') or fallback.get('reason')):
                raise ValueError('Unavailable public research needs a bounded fallback or its real limitation')
            if fallback.get('reason'): text(fallback['reason'],'fallback reason')
        else: raise ValueError('Public research must be read or explicitly unavailable')
    topics=research.get('topics',[])
    if not isinstance(topics,list) or len(topics)!=len(TOPICS) or {r.get('topic') for r in topics}!=set(TOPICS):
        raise ValueError('Public research requires four separate topics')
    used=set()
    for item in topics:
        text(item.get('limits'),'topic scope and limits')
        if item.get('conclusion') not in {'observed','not_found_in_scope','unknown'}:
            raise ValueError('Research conclusion cannot establish global absence or private results')
        ids=item.get('attempt_ids')
        if not isinstance(ids,list) or not ids: raise ValueError('Topic needs actual attempt references')
        rows=[]
        for identifier in ids:
            row=attempts.get(identifier)
            if not row or row['topic']!=item['topic']: raise ValueError('Topic refers to a missing or foreign attempt')
            rows.append(row);used.add(identifier)
        if item['conclusion']!='unknown' and not any(r['status']=='retrieved' for r in rows):
            raise ValueError('An unavailable lookup only supports unknown')
    if used!=set(attempts): raise ValueError('Every research attempt must have a topic outcome')
    for row in attempts.values():
        alternate=row.get('fallback',{}).get('attempt_id')
        if alternate and (alternate==row['id'] or alternate not in attempts or attempts[alternate]['topic']!=row['topic']):
            raise ValueError('Fallback must refer to a different actual attempt for the same topic')
    return list(dict.fromkeys(refs))


def inspect(run):
    if run.get('metadata',{}).get('public_research_contract')!=1:
        return {'status':'NOT_REQUIRED','issues':[],'scope':'legacy_run_without_public_research_contract','topics':[]}
    latest=None
    for identifier in run['metadata'].get('discovery_external_reports',[]):
        artifact=run['artifacts'][identifier];path=state._safe_path(Path(run['root']),artifact['path'])
        if artifact['status']!='CURRENT' or state._sha(path)!=artifact['sha256']:
            raise ValueError('Public research journal changed or stale')
        from .discovery_evidence import _channel_data
        data=_channel_data(run,path)
        if 'public_research' in data: latest=data['public_research']
    issues=[] if latest else ['Missing public research: Google search, Google Ads, Meta Ads and reviews']
    return {'status':'BLOCKED' if issues else 'PASS','issues':issues,'topics':latest['topics'] if latest else [],
            'scope':'operation_and_evidence_trace_only','semantic_truth':'HOST_REVIEW_REQUIRED'}


def prepare(run_dir):
    run=state.load_run(run_dir)
    task={'version':1,'url':run['url'],'stage':'discovery.channels',
          'entity':'Resolve the official entity from current site evidence before external lookups; record name, match_reason and source_ids.',
          'topics':[{'topic':name,'operation':TASKS[name]} for name in TOPICS],
          'bounds':'Read-only public sources, no login, private access, forms, paid provider or CAPTCHA bypass. Reuse current evidence. Stop at sufficient evidence or a documented limitation; no full recrawl.',
          'output':'Use the existing external journal version=1, attempts plus public_research version=1. Follow the exact format in proposition-discovery/references/public-research.md; register public source copies before discovery reconcile.',
          'downstream':'company.v1 records declarations/unknowns; analysis.specialists applies public marketing/research methods; targeted navigation missions then company.v2 and brief.public retain source→need→decision links.',
          'quality':'This task is not executed by the runtime and does not certify searches or commercial value.'}
    path=Path(run['root'])/'public-research-task.json'
    if path.is_symlink(): raise ValueError('Research task path cannot be a symlink')
    path.write_text(json.dumps(task,ensure_ascii=False,indent=2)+'\n')
    return {'status':'PREPARED','native_task_path':str(path),'execution':'HOST_REQUIRED'}
