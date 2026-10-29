"""Synthetic public research receipts; never a real market qualification."""
import json
from pathlib import Path
from proposition_runtime import state

TOPICS = ('google_search', 'google_ads', 'meta_ads', 'reviews')


def journal(run):
    root = Path(run['root'])
    (root/'identity.txt').write_text('Synthetic Company, official entity')
    state.add_source(root, 'identity', 'identity.txt', locator=run['url'])
    attempts=[]; topics=[]
    for topic in TOPICS:
        url='https://public.example.test/'+topic
        (root/(topic+'.txt')).write_text('Synthetic public result, not a live search')
        state.add_source(root,topic,topic+'.txt',locator=url)
        attempts.append(dict(id=topic,topic=topic,url=url,status='retrieved',source_id=topic,
            observed_at='2026-10-29T12:00:00+00:00',operation='public_lookup',query='Synthetic Company',
            provider='fixture public source',geography='France',window='snapshot 2026-10-29'))
        topics.append(dict(topic=topic,attempt_ids=[topic],conclusion='observed',
            limits='Synthetic fixture only, no rankings, spend, traffic or buyer preference'))
    data=dict(version=1,attempts=attempts,public_research=dict(version=1,
        entity=dict(name='Synthetic Company',source_ids=['identity'],match_reason='Official page identifier'),topics=topics))
    path=root/'research-public.json';path.write_text(json.dumps(data))
    return path


def install_public_research(run):
    from proposition_runtime.discovery_evidence import reconcile
    return reconcile(run['root'],journal(run))
