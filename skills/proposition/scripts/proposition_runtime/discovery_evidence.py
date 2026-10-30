"""Register physical Discovery evidence in the existing run and stage gates."""
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

from . import state


def _local(root, path):
    return state._safe_path(root, str(Path(path).absolute().relative_to(root)))


def _validate(run, path):
    root=Path(run['root'])
    if path.stat().st_size>32*1024*1024: raise ValueError('Discovery report exceeds byte budget')
    data=json.loads(path.read_text())
    if data.get('schema_version')!='2.0':
        raise ValueError('Legacy or unsupported Discovery report: current navigation evidence is required')
    state._identifier(data['batch_id'])
    if data['input_url']!=run['url']: raise ValueError('Discovery belongs to another run URL')
    for stamp in ('started_at','finished_at'):
        if datetime.fromisoformat(data[stamp]).tzinfo is None: raise ValueError('Discovery dates need timezone')
    if not isinstance(data['pages'],list) or not isinstance(data['sources'],list): raise ValueError('Invalid Discovery inventory')
    from .discovery import _url, _origin
    allowed={_origin(run['url'])}
    if data.get('backend')=='host-browser':
        original=urlsplit(run['url'])
        for page in data['pages']:
            final=urlsplit(page['final_url'])
            if (page['requested_url']==run['url'] and final.hostname in {original.hostname,'www.'+original.hostname}
                    and final.scheme=='https' and final.port in (None,443)
                    and any(r.get('from')==run['url'] and r.get('to')==page['final_url']
                            and r.get('http_status') in (301,302,303,307,308) for r in page.get('redirects',[]))):
                allowed.add(_origin(page['final_url']))
    files={}; sources={}; total=0
    for source in data['sources']:
        identifier=source['id']
        state._identifier(identifier.removeprefix('source:'))
        if identifier in sources: raise ValueError('Duplicate Discovery source')
        sources[identifier]=source
        if datetime.fromisoformat(source['retrieved_at']).tzinfo is None: raise ValueError('Source date needs timezone')
        for artifact in source['artifacts']:
            name=artifact['path'];relative=PurePosixPath(name)
            if (relative.is_absolute() or '\\' in name or ':' in name or any(x in ('','.','..') for x in name.split('/'))):
                raise ValueError('Unsafe Discovery proof path')
            proof=_local(root,path.parent/name)
            if (type(artifact['bytes']) is not int or not 0<artifact['bytes']<=64*1024*1024
                    or not re.fullmatch('[0-9a-f]{64}',artifact['sha256'])
                    or proof.stat().st_size!=artifact['bytes'] or state._sha(proof)!=artifact['sha256']):
                raise ValueError('Discovery proof integrity mismatch')
            if name not in files: total+=artifact['bytes']
            files[name]=proof
    if total>512*1024*1024 or len(files)>6000: raise ValueError('Discovery bundle exceeds byte/file budget')
    pairs=set()
    for page in data['pages']:
        key=(page['requested_url'],page['viewport'])
        if key in pairs or page['viewport'] not in ('desktop','mobile'): raise ValueError('Duplicate/invalid page viewport')
        pairs.add(key)
        for address in (page['requested_url'],page['final_url']):
            if _url(address,allow_local=True,resolve=False)!=address or _origin(address) not in allowed:
                raise ValueError('Foreign or unsafe Discovery destination')
        for evidence in page['evidence']:
            source=sources.get(evidence['source_id'])
            if not source or source['viewport']!=page['viewport'] or source['url']!=page['final_url']:
                raise ValueError('Discovery evidence source binding mismatch')
            names={a['path'] for a in source['artifacts']}
            for field in ('text_path','html_path','screenshot_path'):
                if evidence.get(field) and evidence[field] not in names: raise ValueError('Unbound Discovery proof')
            if evidence.get('screenshot_path'):
                from PIL import Image
                with Image.open(files[evidence['screenshot_path']]) as image: image.verify()
    for entry in data['link_entries']:
        if entry['source_id'] not in sources: raise ValueError('Navigation entry has no observed source')
    for candidate in data.get('social_candidates',[]):
        if not candidate.get('source_ids') or any(ref not in sources for ref in candidate['source_ids']):
            raise ValueError('Structured channel candidate has no observed source')
    return data, files


def register(run_dir, report_path):
    """Evidence files must already be inside RUN_DIR, never copied implicitly."""
    state.invalidate_changed(run_dir)
    run=state.load_run(run_dir);root=Path(run['root'])
    path=_local(root,report_path)
    data,files=_validate(run,path)
    batch='discovery-'+data['batch_id']
    previous=run['artifacts'].get(batch)
    if previous:
        if previous['sha256']!=state._sha(path) or previous['status']!='CURRENT':
            raise ValueError('Changed Discovery requires a fresh revision and report')
        return inspect_discovery(run)
    registered=run['metadata'].get('discovery_reports',[])
    continuation=data.get('continuation')
    if registered:
        known={run['artifacts'][x]['sha256'] for x in registered}
        if not continuation or continuation.get('previous_report_sha256') not in known:
            raise ValueError('Additional Discovery batch must continue registered evidence')
    dependencies=[]
    for index,(name,proof) in enumerate(files.items()):
        identifier=f'{batch}-proof-{index:04d}'
        run['artifacts'][identifier]=state._artifact_record(run,identifier,proof.relative_to(root).as_posix(),'internal')
        dependencies.append('artifact:'+identifier)
    for source in data['sources']:
        identifier=source['id'].removeprefix('source:')
        primary=next((x for x in source['artifacts'] if x['path'].endswith('.txt')),source['artifacts'][0])
        record=state._source_record(run,identifier,files[primary['path']].relative_to(root).as_posix(),kind='observation',locator=source['url'])
        record['observed_at']=source['retrieved_at']
        if identifier in run['sources']: raise ValueError('Discovery source identity already registered')
        run['sources'][identifier]=record
        dependencies.append('source:'+identifier)
    run['artifacts'][batch]=state._artifact_record(run,batch,path.relative_to(root).as_posix(),'internal',dependencies)
    registered=[*registered,batch]
    run['metadata']['discovery_reports']=registered
    run['artifacts']['site-discovery']=state._artifact_record(run,'site-discovery',path.relative_to(root).as_posix(),'internal',['artifact:'+x for x in registered])
    state.save_run(root,run)
    return inspect_discovery(run)


def inspect_discovery(run):
    """Mechanical completeness/integrity only. Exact pixels still need review."""
    issues=[];pages={};entries=[];known=set();last=None;origins=set()
    from .discovery import _origin
    root=Path(run['root'])
    registered=run.get('metadata',{}).get('discovery_reports',[])
    if not registered or not run['artifacts'].get('site-discovery'):
        return {'status':'BLOCKED','issues':['Current physical Discovery receipt is missing'],'scope':'navigation_evidence_only','entries':[]}
    try:
        for identifier in [*registered,'site-discovery']:
            artifact=run['artifacts'][identifier]
            path=state._safe_path(root,artifact['path'])
            if artifact['status']!='CURRENT' or state._sha(path)!=artifact['sha256']: raise ValueError('Discovery receipt is stale or changed')
            if identifier=='site-discovery': continue
            data,_=_validate(run,path);last=data
            known.update(data['coverage']['discovered_urls'])
            for page in data['pages']:
                pages[(page['requested_url'],page['viewport'])]=page
                if page['status']=='captured': pages[(page['final_url'],page['viewport'])]=page
                origins.add(_origin(page['requested_url']));origins.add(_origin(page['final_url']))
            entries.extend(dict(e,entry_id=f'{data["batch_id"]}-{index:04d}') for index,e in enumerate(data['link_entries']))
            entries.extend({'url':c['url'],'source_ids':c['source_ids'],'entry_id':f'{data["batch_id"]}-social-{index:04d}',
                            'origin':'structured_candidate','methods':c.get('methods',[])}
                           for index,c in enumerate(data.get('social_candidates',[]))
                           if not any(e['url']==c['url'] for e in data['link_entries']))
        if not last: raise ValueError('No registered Discovery batch')
        known.update(e['url'] for e in entries if _origin(e['url']) in origins)
        for url in known|{run['url']}:
            for view in ('desktop','mobile'):
                page=pages.get((url,view))
                if page is None: issues.append(f'Unattempted destination/viewport: {url} {view}');continue
                if page['status'] in ('inaccessible','unsupported_content') and url!=run['url']: continue
                exploration=page.get('exploration',{})
                scrolls=[e for e in page['evidence'] if e.get('kind')=='scroll']
                endpoint=scrolls[-1] if scrolls else {}
                geometry_complete=(endpoint.get('height',0)>0 and endpoint.get('viewport_height',0)>0
                    and endpoint.get('scroll_y',0)+endpoint.get('viewport_height',0)>=endpoint.get('height',0)-2)
                if (page['status']!='captured' or exploration.get('status')!='complete'
                        or exploration.get('unresolved')!=[] or exploration.get('scroll',{}).get('reached_end') is not True or not geometry_complete
                        or any(image.get('loaded') is not True for e in page['evidence'] for image in e.get('visible_images',[]))
                        or not page['evidence'] or any(not e.get('screenshot_path') for e in page['evidence'])
                        or any(a.get('status')!='resolved' for a in page.get('interactions',[]))):
                    issues.append(f'Incomplete navigation: {url} {view}')
        for entry in entries:
            views=[pages.get((entry['url'],v)) for v in ('desktop','mobile')]
            entry['destination_status']='attempted' if all(views) else 'external_pending' if _origin(entry['url']) not in origins else 'pending'
    except (OSError,ValueError,KeyError,TypeError) as error:
        issues.append('Invalid Discovery receipt: '+str(error)[:240])
    return {'status':'BLOCKED' if issues else 'PASS','issues':issues,'scope':'navigation_evidence_only',
            'entries':entries,'semantic_analysis':'NOT_INFERRED','visual_quality':'NOT_INFERRED'}


def _channel_data(run,path):
    if path.stat().st_size>4*1024*1024: raise ValueError('External journal exceeds byte budget')
    data=json.loads(path.read_text())
    if (not isinstance(data,dict) or type(data.get('version')) is not int
            or data['version']!=1 or not isinstance(data.get('attempts'),list)):
        raise ValueError('Invalid external attempt journal')
    if len(data['attempts'])>5000: raise ValueError('External journal exceeds attempt budget')
    from .discovery import _url
    for row in data['attempts']:
        if not isinstance(row,dict): raise ValueError('External attempt must be an object')
        if not isinstance(row.get('url'),str): raise ValueError('External destination must be a string')
        if _url(row['url'],allow_local=False,resolve=False)!=row['url']: raise ValueError('Invalid external destination')
        if not isinstance(row.get('status'),str) or row['status'] not in {'retrieved','unavailable','document_not_analyzed','excluded'}:
            raise ValueError('Invalid external issue')
        if not isinstance(row.get('observed_at'),str): raise ValueError('External attempt needs a date')
        if datetime.fromisoformat(row['observed_at']).tzinfo is None: raise ValueError('External attempt needs timezone')
        if row.get('source_id') is not None: state._identifier(row['source_id'])
        source=run['sources'].get(row.get('source_id'))
        if row['status'] in {'retrieved','document_not_analyzed'}:
            if not source or source['status']!='COLLECTED' or source.get('locator')!=row['url']:
                raise ValueError('Retrieved external issue requires its collected source')
            if not source.get('path') or state._sha(state._safe_path(Path(run['root']),source['path']))!=source['sha256']:
                raise ValueError('External source is no longer current')
        elif not isinstance(row.get('reason'),str) or not row['reason'].strip():
            raise ValueError('Unavailable/excluded external issue needs a reason')
    from .public_research import validate
    validate(run,data)
    return data


def _channel_reports(run):
    """Read the current bundle's bindings, keeping superseded history separate."""
    history=run.get('metadata',{}).get('discovery_external_reports',[])
    if not history: return []
    if any(identifier not in run['artifacts'] for identifier in history):
        raise ValueError('External history contains a missing journal')
    bundle=run['artifacts'].get('discovery-channels');root=Path(run['root'])
    if not bundle or bundle['status']!='CURRENT' or state._stale_reasons(run,root,bundle):
        raise ValueError('External reconciliation bundle is stale or changed')
    identifiers=[]
    for ref in bundle['dependencies']:
        if not ref.startswith('artifact:') or ref.split(':',1)[1] not in history:
            raise ValueError('External reconciliation has an unregistered journal')
        identifier=ref.split(':',1)[1];artifact=run['artifacts'][identifier]
        if artifact['status']!='CURRENT' or state._stale_reasons(run,root,artifact):
            raise ValueError('External journal is stale or changed')
        identifiers.append(identifier)
    return identifiers


def historical_channel_refs(run):
    """Exclude only replaced journal evidence unused by every other record."""
    try:
        active=set(_channel_reports(run))
    except (OSError,ValueError,KeyError,TypeError):
        return set()
    if not active: return set()
    retired={'artifact:'+identifier for identifier in run['metadata']['discovery_external_reports']
             if identifier not in active and run['artifacts'][identifier]['status']=='STALE'}
    protected=[kind+':'+identifier for kind,collection in state._COLLECTIONS.items()
               if kind!='source' for identifier in run[collection]
               if kind+':'+identifier not in retired]
    historical=state._dependency_closure(run,retired)-state._dependency_closure(run,protected)
    return {ref for ref in historical if ref in retired or
            (ref.startswith('source:') and (state._resolve(run,ref) or {}).get('kind') in ('public','observation'))}


def reconcile(run_dir,receipts_path):
    state.invalidate_changed(run_dir)
    run=state.load_run(run_dir);root=Path(run['root']);path=_local(root,receipts_path)
    data=_channel_data(run,path)
    identifier='channel-attempts-'+state._sha(path)[:16]
    dependencies=['source:'+row['source_id'] for row in data['attempts'] if row.get('source_id')]
    from .public_research import validate
    dependencies.extend(validate(run,data))
    before=state._canonical(run)
    previous_record=run['artifacts'].get(identifier)
    run['artifacts'][identifier]=state._artifact_record(run,identifier,path.relative_to(root).as_posix(),
                                                      'internal',dependencies,reuse_current=True)
    if run['artifacts'][identifier]['status']!='CURRENT': return inspect_channels(run)
    previous=run['metadata'].get('discovery_external_reports',[])
    run['metadata']['discovery_external_reports']=list(dict.fromkeys([*previous,identifier]))
    active=['artifact:'+name for name in run['metadata']['discovery_external_reports']
            if run['artifacts'][name]['status']=='CURRENT']
    bundle=run['artifacts'].get('discovery-channels')
    bundle_path=path.relative_to(root).as_posix()
    if (previous_record==run['artifacts'][identifier] and bundle and bundle['status']=='CURRENT'
            and set(bundle['dependencies'])==set(active)):
        bundle_path=bundle['path']
    run['artifacts']['discovery-channels']=state._artifact_record(run,'discovery-channels',bundle_path,
                                                              'internal',active,reuse_current=True)
    if state._canonical(run)!=before: state.save_run(root,run)
    return inspect_channels(run)


def inspect_channels(run):
    site=inspect_discovery(run)
    entries=[e for e in site['entries'] if e['destination_status']=='external_pending']
    issues=list(site['issues']);outcomes={};root=Path(run['root'])
    try:
        for identifier in _channel_reports(run):
            artifact=run['artifacts'][identifier];path=state._safe_path(root,artifact['path'])
            if artifact['status']!='CURRENT' or state._sha(path)!=artifact['sha256']: raise ValueError('External journal is stale or changed')
            for row in _channel_data(run,path)['attempts']: outcomes[row['url']]=row
        for entry in entries:
            row=outcomes.get(entry['url'])
            entry.update(identity='candidate',analyzed=False)
            if row:
                entry.update(destination_status=row['status'],external_source_id=row.get('source_id'),observed_at=row['observed_at'])
            else: issues.append('External destination not attempted: '+entry['url'])
    except (OSError,ValueError,TypeError,KeyError) as error:
        issues.append('Invalid external reconciliation: '+str(error)[:240])
    research={'status':'BLOCKED','issues':[],'topics':[]}
    try:
        from .public_research import inspect
        research=inspect(run);issues.extend(research['issues'])
    except (OSError,ValueError,TypeError,KeyError) as error:
        issues.append('Invalid public research: '+str(error)[:240])
    return {'status':'BLOCKED' if issues else 'PASS','issues':issues,'entries':entries,'public_research':research,
            'scope':'external_attempt_reconciliation_only','identity':'NOT_INFERRED','analysis':'NOT_INFERRED','rights':'NOT_INFERRED'}
