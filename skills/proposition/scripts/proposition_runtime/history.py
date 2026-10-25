"""Optional Wayback evidence: bounded retrieval, never an inferred update date.

The collector retrieves indexes and passive HTML only. It does not render old
sites, verify entity identity, compare their pixels or infer business problems.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from proposition_runtime import state
from proposition_runtime.discovery import _url

DEFAULTS = {'history_mode':'auto', 'history_deadline_seconds':90,
            'history_request_seconds':8, 'history_max_requests':8,
            'history_max_urls':2, 'history_max_captures':4}


def policy(parameters):
    result={k:parameters.get(k,v) for k,v in DEFAULTS.items()}
    if result['history_mode'] not in ('auto','off'):
        raise ValueError('history_mode must be auto or off')
    for key,maximum in [('history_deadline_seconds',90),('history_request_seconds',8),
                        ('history_max_requests',8),('history_max_urls',2),('history_max_captures',4)]:
        if type(result[key]) not in (int,float) or not 0 < result[key] <= maximum:
            raise ValueError('Invalid bounded history policy: '+key)
    for key in ('history_max_requests','history_max_urls','history_max_captures'):
        if type(result[key]) is not int: raise ValueError('History counts must be integers')
    return result


def safe_archive_url(value):
    parts=urlsplit(value)
    if parts.scheme!='https' or parts.username or parts.password or parts.port not in (None,443):
        raise ValueError('Only public HTTPS archive endpoints are allowed')
    if parts.hostname=='archive.org' and parts.path=='/wayback/available':
        return value
    if parts.hostname!='web.archive.org' or not re.fullmatch(r'/web/\d{14}(?:id_)?/https?://.+',parts.path):
        raise ValueError('Not an allowed Wayback replay URL')
    original=re.sub(r'^/web/\d{14}(?:id_)?/','',parts.path)
    _url(original,allow_local=False,resolve=False)
    return value


def _date(value):
    try:
        parsed=datetime.fromisoformat(value)
        if parsed.tzinfo is None: raise ValueError('Timezone required')
    except (ValueError,TypeError):
        raise ValueError('Historical evidence needs an explicit ISO date and timezone') from None
    return parsed


def availability_snapshot(data, original, target):
    closest=data.get('archived_snapshots',{}).get('closest',{})
    if not closest.get('available') or str(closest.get('status'))!='200': return None
    timestamp=closest.get('timestamp','')
    if not re.fullmatch(r'\d{14}',timestamp): raise ValueError('Malformed archive timestamp')
    captured=datetime.strptime(timestamp,'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
    replay=closest['url']
    if replay.startswith('http://web.archive.org/'): replay='https://'+replay[len('http://'):]
    safe_archive_url(replay)
    parsed=urlsplit(replay)
    embedded=re.sub(r'^/web/\d{14}(?:id_)?/','',parsed.path)
    if parsed.query:embedded+='?'+parsed.query
    if _url(embedded,allow_local=False,resolve=False).rstrip('/') != original.rstrip('/'):
        raise ValueError('Replay belongs to a different original URL')
    if urlsplit(replay).path.split('/')[2].removesuffix('id_')!=timestamp:
        raise ValueError('Replay timestamp differs from index timestamp')
    return {'original_url':original,'requested_target_at':target,
            'archive_captured_at':captured.isoformat(),'replay_url':replay,
            'entity_match':'unknown','entity_evidence':[],
            'render_completeness':'not_rendered','render_ref':None,
            'missing_assets':['No archived CSS/images rendered by this collector'],
            'live_resource_contamination':None}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


class ArchiveReader:
    def __init__(self, limits):
        self.deadline=time.monotonic()+limits['history_deadline_seconds']
        self.limits=limits;self.requests=0
        self.opener=build_opener(NoRedirect())

    def fetch(self, url, maximum):
        # No browser or secondary-resource downloads: zero secondary requests.
        for hop in range(4):
            safe_archive_url(url)
            remaining=self.deadline-time.monotonic()
            if remaining<=0 or self.requests>=self.limits['history_max_requests']:
                raise TimeoutError('Historical request budget exhausted')
            self.requests+=1
            request=Request(url,headers={'User-Agent':'Vertigo-Proposition/0.1 (historical evidence)'})
            try:
                response=self.opener.open(request,timeout=min(remaining,self.limits['history_request_seconds']))
            except HTTPError as error:
                if error.code in (301,302,303,307,308) and hop<3:
                    url=urljoin(url,error.headers.get('Location',''));error.close();continue
                error.close();raise ValueError('Archive request failed with HTTP '+str(error.code)) from None
            with response:
                if int(response.headers.get('Content-Length',0))>maximum:
                    raise ValueError('Archive response exceeds byte budget')
                result=bytearray()
                while True:
                    remaining=self.deadline-time.monotonic()
                    if remaining<=0: raise TimeoutError('Historical deadline exhausted')
                    chunk=response.read1(min(65536,maximum-len(result)+1))
                    if not chunk: break
                    result.extend(chunk)
                    if len(result)>maximum: raise ValueError('Archive response exceeds byte budget')
                return bytes(result)
        raise ValueError('Archive redirect budget exhausted')


def _write(path, data):
    temporary=path.with_suffix('.partial')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)


def _worker(request_path):
    request=json.loads(Path(request_path).read_text());out=Path(request['output'])
    report=request['report'];reader=ArchiveReader(report['limits'])
    report_path=out/'report.json'
    for original in request['urls']:
        for target in (None,str(datetime.now(timezone.utc).year-2)+'0101'):
            if len(report['snapshots'])>=report['limits']['history_max_captures']: break
            number=len(report['attempts']);identifier=f"{report['revision']}-{number}"
            query={'url':original}
            if target:query['timestamp']=target
            api='https://archive.org/wayback/available?'+urlencode(query)
            attempt={'original_url':original,'requested_target_at':target,'status':'UNAVAILABLE'}
            report['attempts'].append(attempt);_write(report_path,report)
            try:
                raw=reader.fetch(api,1024*1024);index=out/(identifier+'-index.json');index.write_bytes(raw)
                attempt.update(index_path=index.name,index_locator=api,index_source_ref='source:'+identifier+'-index')
                candidate=availability_snapshot(json.loads(raw),original,target)
                if candidate is None:attempt['reason']='No accessible capture returned';continue
                if any(x['replay_url']==candidate['replay_url'] for x in report['snapshots']):
                    attempt.update(status='DUPLICATE');continue
                candidate.update(id=identifier,retrieved_at=state._now(),index_source_ref='source:'+identifier+'-index',
                                 index_path=index.name,content_source_ref=None,content_path=None)
                report['snapshots'].append(candidate);attempt['status']='INDEX_ONLY';_write(report_path,report)
                replay=re.sub(r'(/web/\d{14})(?:id_)?/',r'\1id_/',candidate['replay_url'])
                content=reader.fetch(replay,5*1024*1024);path=out/(identifier+'.html');path.write_bytes(content)
                candidate.update(content_path=path.name,content_source_ref='source:'+identifier+'-content')
                attempt['status']='RETRIEVED_NOT_RENDERED'
            except (OSError,ValueError,TimeoutError,KeyError) as error:
                attempt['reason']=type(error).__name__+': '+str(error)[:180]
            finally:
                report['outcome']='LIMITED' if report['snapshots'] else 'UNAVAILABLE'
                report['request_count']=reader.requests
                _write(report_path,report)
    report['unknowns']=['Historical entity identity, visual rendering and comparisons require inspection; no last-update date inferred.']
    _write(report_path,report)


def collect(run_dir, urls=()):
    state.invalidate_changed(run_dir)
    run=state.load_run(run_dir);root=Path(run['root']);limits=policy(run['profile']['parameters'])
    if 'site-history' in run['artifacts']:
        result=inspect_history(run)
        if result['status']!='PASS': raise ValueError('Existing history changed: revise explicitly before recollecting')
        return {'status':'PASS','reused':True,'scope':'historical_retrieval_only','artifact':'site-history'}
    selected=list(dict.fromkeys([run['url'],*urls]))
    if len(selected)>limits['history_max_urls']:raise ValueError('Too many historical target URLs')
    selected=[_url(u,allow_local=False,resolve=False) for u in selected]
    if any(urlsplit(u).netloc!=urlsplit(selected[0]).netloc for u in selected):
        raise ValueError('Historical targets must belong to the confirmed current host')
    import uuid
    revision='history-'+uuid.uuid4().hex[:12];out=root/'research'/revision;out.mkdir(parents=True)
    report={'schema_version':'site-history/1','revision':revision,'collected_at':state._now(),
            'mode':limits['history_mode'],'outcome':'OFF' if limits['history_mode']=='off' else 'UNAVAILABLE',
            'entity_source_refs':[],'limits':limits,'attempts':[],'snapshots':[],'comparisons':[],'unknowns':[]}
    path=out/'report.json';_write(path,report)
    if limits['history_mode']=='auto':
        request=out/'request.json';request.write_text(json.dumps({'output':str(out),'urls':selected,'report':report}))
        try:
            result=subprocess.run([sys.executable,str(Path(__file__)),str(request)],
                                  timeout=limits['history_deadline_seconds'],capture_output=True,text=True)
            if result.returncode:raise ValueError('Historical worker failed; partial evidence retained')
        except (subprocess.TimeoutExpired,ValueError):
            report=json.loads(path.read_text());report['unknowns'].append('Historical worker deadline/failure; no retry loop')
            _write(path,report)
    return register(root,path)


def _validate(run, path):
    data=json.loads(path.read_text())
    state._schema('site-history',data)
    _date(data['collected_at']);state._identifier(data['revision'])
    state._identifier('site-history-'+data['revision'])
    if data['outcome']=='COMPARED' and not data['comparisons']:raise ValueError('COMPARED needs inspected comparisons')
    snapshots={}
    for snapshot in data['snapshots']:
        captured=_date(snapshot['archive_captured_at']);_date(snapshot['retrieved_at'])
        safe_archive_url(snapshot['replay_url'])
        stamp=urlsplit(snapshot['replay_url']).path.split('/')[2].removesuffix('id_')
        if captured.astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')!=stamp:
            raise ValueError('Replay timestamp differs from the recorded capture timestamp')
        availability_snapshot({'archived_snapshots':{'closest':{'available':True,'status':'200','timestamp':stamp,'url':snapshot['replay_url']}}},snapshot['original_url'],snapshot['requested_target_at'])
        index_path=state._safe_path(Path(run['root']),str((path.parent/snapshot['index_path']).resolve().relative_to(Path(run['root']))))
        actual=availability_snapshot(json.loads(index_path.read_text()),snapshot['original_url'],snapshot['requested_target_at'])
        if not actual or actual['archive_captured_at']!=snapshot['archive_captured_at'] or actual['replay_url']!=snapshot['replay_url']:
            raise ValueError('Raw index does not substantiate the declared capture')
        if (snapshot['content_source_ref'] is None)!=(snapshot['content_path'] is None):
            raise ValueError('A capture needs both content path and reference, or neither')
        if snapshot['content_source_ref']:snapshots[snapshot['content_source_ref']]=snapshot
        if snapshot['entity_match']=='confirmed' and not snapshot['entity_evidence']:
            raise ValueError('Historical identity needs evidence, not just the current domain')
        for ref in snapshot['entity_evidence']:
            if not ref.startswith('source:') or ref[7:] not in run['sources']:
                raise ValueError('Missing historical entity evidence')
    for row in data['comparisons']:
        snapshot=snapshots.get(row['historical_source_ref'])
        if not snapshot or snapshot['entity_match']!='confirmed':raise ValueError('Comparison needs a confirmed historical subject')
        source=run['sources'].get(row['current_source_ref'].removeprefix('source:'))
        if not source or source['status']!='COLLECTED':raise ValueError('Comparison needs a collected counterpart')
        if row['difference_type']=='visual' and snapshot['render_completeness']!='complete':
            raise ValueError('An index or incomplete replay does not prove a visual difference')
        if row['difference_type']=='visual' and not snapshot['render_ref']:
            raise ValueError('Visual comparison needs an inspected render')
        if row['difference_type']=='visual':
            render=run['artifacts'].get(snapshot['render_ref'][9:])
            if not render or render['status']!='CURRENT' or state._sha(state._safe_path(Path(run['root']),render['path']))!=render['sha256']:
                raise ValueError('Historical render is missing or no longer current')
            from .experience import _render
            try:_render(run,snapshot['render_ref'])
            except (OSError,ValueError):raise ValueError('Historical visual evidence must contain readable rendered pixels') from None
            if snapshot['content_source_ref'] not in state._dependency_closure(run,[snapshot['render_ref']]):
                raise ValueError('Historical render must depend on the actual archived content')
            if snapshot['missing_assets'] or snapshot['live_resource_contamination'] is not False:
                raise ValueError('Incomplete or mixed-date rendering cannot substantiate a full visual comparison')
        known_history=_historical_sources(run,data)
        if row['current_source_ref'] in known_history or row['current_source_ref']==row['historical_source_ref']:
            raise ValueError('A historical source is not a current comparison counterpart')
    return data


def register(run_dir, report_path):
    state.invalidate_changed(run_dir)
    run=state.load_run(run_dir);root=Path(run['root'])
    path=state._safe_path(root,str(Path(report_path).resolve().relative_to(root)))
    data=_validate(run,path);revision=data['revision'];dependencies=[]
    previous=run['artifacts'].get('site-history')
    if previous and previous['sha256']==state._sha(path) and previous['status']=='CURRENT':
        synthesis=run['sources'].get('site-history-'+revision)
        if not synthesis or synthesis['status']!='COLLECTED' or synthesis['sha256']!=previous['sha256']:
            raise ValueError('Historical bundle lacks its current synthesis source')
        return {'status':'PASS','reused':True,'scope':'historical_evidence_registration_only','artifact':'site-history'}
    if previous and previous['status']!='CURRENT' and 'site-history-'+revision in run['sources']:
        raise ValueError('Changed historical inputs require a new revision')
    if previous and state._sha(path)!=previous['sha256']:
        prior_source=run['sources'].get('site-history-'+revision)
        if prior_source:raise ValueError('Changed history requires a new revision and file')
    inputs={}
    for attempt in data['attempts']:
        if attempt.get('index_path'):
            inputs[attempt['index_source_ref']]=(attempt['index_path'],attempt['index_locator'])
    for item in data['snapshots']:
        for field,ref,locator in [('index_path','index_source_ref',item['replay_url']),('content_path','content_source_ref',item['replay_url'])]:
            if item[field] is None:continue
            inputs.setdefault(item[ref],(item[field],locator))
        dependencies.extend(item['entity_evidence'])
        if item['render_ref']:dependencies.append(item['render_ref'])
    for comparison in data['comparisons']:dependencies.append(comparison['current_source_ref'])
    # Resolve every input before modifying state; malformed evidence cannot partly register.
    resolved=[]
    for ref,(relative,locator) in inputs.items():
        state._identifier(ref.removeprefix('source:'))
        local=state._safe_path(root,str((path.parent/relative).resolve().relative_to(root)))
        resolved.append((ref,local,locator))
    for ref,local,locator in resolved:
        identifier=ref.removeprefix('source:')
        record=state._source_record(run,identifier,local.relative_to(root).as_posix(),kind='public',locator=locator,required=False)
        existing=run['sources'].get(identifier)
        stable_keys=('path','sha256','locator','status','kind','required','audience')
        if not existing or any(existing.get(k)!=record.get(k) for k in stable_keys):
            run['sources'][identifier]=record
        dependencies.append(ref)
    run['artifacts']['site-history']=state._artifact_record(run,'site-history',path.relative_to(root).as_posix(),'internal',dependencies)
    run['sources']['site-history-'+revision]=state._source_record(run,'site-history-'+revision,path.relative_to(root).as_posix(),required=False,kind='observation')
    state.save_run(root,run)  # One validated atomic commit for sources + artifact + synthesis.
    return {'status':'PASS','scope':'historical_evidence_registration_only','outcome':data['outcome'],
            'path':str(path),'artifact':'site-history','source_id':'site-history-'+revision,
            'visual_analysis':'NOT_INFERRED','last_update_date':None}


def _historical_sources(run,data):
    result={s[f] for s in data['snapshots'] for f in ('index_source_ref','content_source_ref') if s[f]}
    result.update(a['index_source_ref'] for a in data['attempts'] if a.get('index_source_ref'))
    # Include prior revisions and unavailable-index sources, not only latest captures.
    for identifier,source in run['sources'].items():
        locator=urlsplit(source.get('locator') or '')
        if identifier.startswith('site-history-') or locator.hostname=='web.archive.org' or (locator.hostname=='archive.org' and locator.path=='/wayback/available'):
            result.add('source:'+identifier)
    return result


def inspect_history(run):
    artifact=run['artifacts'].get('site-history')
    if not artifact:return {'status':'PASS','scope':'optional_history_not_registered','issues':[]}
    issues=[]
    try:
        path=state._safe_path(Path(run['root']),artifact['path'])
        if state._sha(path)!=artifact['sha256'] or artifact['status']!='CURRENT':raise ValueError('Historical evidence changed')
        data=_validate(run,path)
        synthesis='site-history-'+data['revision']
        history_sources=_historical_sources(run,data)
        roots=[kind+':'+key for kind in ('artifact','evaluation','review','stage_review','checkpoint')
               for key,row in run[state._COLLECTIONS[kind]].items() if row['status']!='STALE']
        active=state._dependency_closure(run,roots)
        for identifier,fact in run['facts'].items():
            if not fact.get('required',True) and 'fact:'+identifier not in active:continue
            if not isinstance(fact['value'],dict):continue
            value=fact['value'];scope=value.get('temporal_scope')
            if scope=='historical_observation':
                if synthesis not in fact['source_ids']:raise ValueError('Historical fact lacks tracked synthesis dependency')
                matches=[s for s in data['snapshots'] if s['content_source_ref'] and s['content_source_ref'][7:] in fact['source_ids']]
                if not matches or any(s['entity_match']!='confirmed' for s in matches):raise ValueError('Historical fact needs an inspected attributed capture')
                if value.get('archive_captured_at') not in [s['archive_captured_at'] for s in matches]:raise ValueError('Historical fact capture date mismatch')
            if scope=='current_observation' and fact['source_ids'] and all('source:'+s in history_sources for s in fact['source_ids']):
                raise ValueError('Historical-only evidence cannot prove a current observation')
    except (ValueError,OSError,KeyError,TypeError) as error:issues.append(str(error))
    return {'status':'BLOCKED' if issues else 'PASS','scope':'historical_provenance_only','issues':issues}


if __name__=='__main__':_worker(sys.argv[1])
