"""Public research → audiences/needs → missions → model/brief consistency.

Checks current files and declared handoffs, not the truth of an ICP, actual
reading, navigation completion or creative merit. Those need independent review.
"""
from __future__ import annotations

import json
from pathlib import Path
from . import state, upstream
from .public_research import current_source, text
from .telemetry import traced
from .validation import cached, phase

METHODS=('product-marketing','customer-research')
AUDIENCE_FIELDS=('id','role','kind','status','source_ids')
NEED_FIELDS=('id','audience_ids','status','context','delta','decision','recommendation','experience_consequence','alternative','source_group')


@cached('strategy.read')
def read(path):
    from .experience import read_mandate_input
    return json.loads(read_mandate_input(path))


def rows(data, key, *, required=True):
    items=data.get(key)
    if not isinstance(items,list) or len(items)>100 or (required and not items):
        raise ValueError('Expected bounded '+key)
    ids=[state._identifier(r['id']) for r in items]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate '+key+' IDs')
    return dict(zip(ids,items))


def source_refs(run, identifiers, *, public=False):
    if not isinstance(identifiers,list) or not identifiers: raise ValueError('Missing source evidence')
    return [current_source(run,s,public=public) for s in identifiers]


def artifact(run, identifier):
    record=run['artifacts'].get(identifier)
    if not record or record['status']!='CURRENT': raise ValueError('Missing current '+identifier)
    path=state._safe_path(Path(run['root']),record['path'])
    if state._sha(path)!=record['sha256']: raise ValueError('Changed '+identifier)
    for ref in state._dependency_closure(run,['artifact:'+identifier]):
        target=state._resolve(run,ref)
        if not target or target.get('status')=='STALE': raise ValueError('Stale handoff dependency: '+ref)
        if ref.startswith('source:'):current_source(run,ref.split(':',1)[1])
        if ref.startswith('artifact:'):
            if state._sha(state._safe_path(Path(run['root']),target['path']))!=target['sha256']:
                raise ValueError('Changed handoff dependency: '+ref)
    return record,path


def method_reads(data, applied):
    methods=data.get('methods',[])
    if len(methods)!=2 or {m.get('name') for m in methods}!=set(METHODS):
        raise ValueError('Both public strategy methods must be read and adapted')
    spec=next(s for s in upstream._families() if s['id']=='marketingskills')
    for method in methods:
        root=Path(text(method.get('reference_root'),'method source cache'))
        if not root.is_absolute() or root!=root.parents[2]/spec['id']/spec['commit']/'source':
            raise ValueError('Method source must be the complete pinned selected cache')
        if not upstream._inspect(spec,root.parents[2])['complete']: raise ValueError('Incomplete or changed marketing method cache')
        entry=root/('skills/'+method['name']+'/SKILL.md')
        if method.get('commit')!=spec['commit'] or method.get('sha256')!=state._sha(entry):
            raise ValueError('Strategy method differs from locked source')
        if method.get('mode')!='adapted': raise ValueError('URL-only method use must declare its public adaptation')
        text(method.get('adaptation'),'public-only adaptation')
        sections=method.get('read_sections')
        if not isinstance(sections,list) or not sections or any(not isinstance(s,str) or not s.strip() for s in sections):
            raise ValueError('Method needs a declared reading receipt')
        targets=method.get('applied_to')
        if not isinstance(targets,list) or not targets or not set(targets).issubset(applied):
            raise ValueError('Method must identify actual audience/need applications')


@cached('strategy.validate')
@traced('strategy.validate')
def validate(run, data):
    return _validate_content(run,data)


def _validate_content(run,data,*,proposed=False):
    expected = state._contract_version(run,'audience_handoff_contract') or 1
    if type(data.get('version')) is not int or data['version']!=expected:
        raise ValueError('Strategic handoff version does not match the initialized contract')
    if expected == 2 and not proposed:
        state._schema('strategy-report-v2',data)
    audiences=rows(data,'audiences');needs=rows(data,'needs');missions=rows(data,'missions',required=False)
    if set(audiences)&set(needs) or (set(audiences)|set(needs))&set(missions): raise ValueError('Handoff IDs must be globally distinct')
    method_reads(data,set(audiences)|set(needs))
    refs=[]
    for row in audiences.values():
        text(row.get('role'),'audience role')
        if row.get('kind') not in {'site_visitor','vertigo_buyer'} or row.get('status') not in {'declared','attributed','hypothesis'}:
            raise ValueError('A public audience is declared, attributed or hypothetical; never a validated priority ICP')
        refs.extend(source_refs(run,row.get('source_ids'),public=True))
    for row in needs.values():
        ids=row.get('audience_ids')
        if not isinstance(ids,list) or not ids or not set(ids).issubset(audiences): raise ValueError('Need has no traced audience')
        if row.get('status') not in {'observed','declared','hypothesis','unknown'}: raise ValueError('Invalid need evidence status')
        if row.get('delta') not in {'new','corroboration','reformulation','baseline_not_compared'}: raise ValueError('Missing nature of contribution')
        if row.get('delta')!='baseline_not_compared': refs.extend(source_refs(run,row.get('baseline_source_ids')))
        refs.extend(source_refs(run,row.get('source_ids'),public=True))
        for key in ('context','source_group','recommendation','alternative'):text(row.get(key),'need '+key)
        if row.get('decision') not in {'retained','excluded','deferred'}: raise ValueError('Need needs an explicit decision')
        ids=row.get('mission_ids')
        if not isinstance(ids,list) or not set(ids).issubset(missions): raise ValueError('Unknown navigation mission')
        if row['decision']=='retained':
            if row['status']=='unknown': raise ValueError('Unknown need cannot justify a retained opportunity')
            text(row.get('experience_consequence'),'visible experience consequence')
            if not ids: raise ValueError('Retained need must reach a navigation mission')
        else:
            text(row.get('reason'),'reason for not retaining need')
            row.setdefault('experience_consequence','')
        if any(row['id'] not in missions[mid].get('need_ids',[]) for mid in ids): raise ValueError('Need/mission links must agree')
    from .discovery import _url
    for row in missions.values():
        ids=row.get('need_ids')
        if not isinstance(ids,list) or not ids or not set(ids).issubset(needs): raise ValueError('Mission needs a traced need')
        if any(row['id'] not in needs[nid]['mission_ids'] for nid in ids): raise ValueError('Mission/need links must agree')
        if _url(row['target'],allow_local=False,resolve=False)!=row['target']: raise ValueError('Invalid mission target')
        for key in ('task','success','stop')+(() if proposed else ('limits',)):text(row.get(key),'mission '+key)
        if not proposed:
            if row.get('outcome') not in {'completed','blocked'}: raise ValueError('Mission must have an actual outcome')
            if row['outcome']=='blocked':text(row.get('reason'),'blocked mission reason')
        refs.extend(source_refs(run,row.get('source_ids')))
    unknowns=data.get('unknowns')
    if not isinstance(unknowns,list) or any(not isinstance(u,str) or not u.strip() for u in unknowns): raise ValueError('Unknowns must remain explicit')
    if run.get('metadata',{}).get('public_research_contract')==1:
        from .discovery_evidence import inspect_channels
        result=inspect_channels(run)
        if result['status']!='PASS': raise ValueError('Current public research must precede analysis: '+'; '.join(result['issues']))
        refs.append('artifact:discovery-channels')
    return list(dict.fromkeys(refs))


@phase
def validate_draft(run,data):
    """Validate sourced proposals without asserting any navigation outcome."""
    state._schema('strategy-draft',data)
    projected={key:data[key] for key in ('methods','audiences','needs','unknowns')}
    projected.update(version=data['handoff_version'],missions=data['proposed_missions'])
    refs=_validate_content(run,projected,proposed=True)
    missions=rows(projected,'missions',required=False);visited=set();visiting=set()
    def visit(identifier):
        if identifier in visiting:raise ValueError('Cyclic proposed mission dependency')
        if identifier in visited:return
        if identifier not in missions:raise ValueError('Unknown proposed mission dependency')
        visiting.add(identifier)
        for dependency in missions[identifier]['depends_on']:visit(dependency)
        visiting.remove(identifier);visited.add(identifier)
    for identifier in missions:visit(identifier)
    return refs

def validate_mission(run,draft,identifier,data):
    state._schema('strategy-mission',data)
    planned=next((m for m in draft['proposed_missions'] if m['id']==identifier),None)
    if planned is None or any(data.get(k)!=planned[k] for k in ('id','need_ids','target','task','success','stop')):raise ValueError('Mission result changed its prepared target, task or success criterion')
    text(data['limits'],'actual mission limits')
    if data['outcome']=='blocked':text(data.get('reason'),'actual blocked mission reason')
    return source_refs(run,data['source_ids'])


def summary(data):
    result = {'audiences':[{k:r[k] for k in AUDIENCE_FIELDS} for r in data['audiences']],
            'needs':[{k:r.get(k,'') for k in NEED_FIELDS} for r in data['needs']],
            'unknowns':data['unknowns']}
    if data['version'] == 2:
        result['version'] = 2
        for source, projected in zip(data['needs'],result['needs']):
            projected['mission_ids'] = list(source['mission_ids'])
        result['missions'] = [{k:r[k] for k in ('id','need_ids','outcome','limits','source_ids')}
                              | ({'reason':r['reason']} if r['outcome']=='blocked' else {}) for r in data['missions']]
        retained = {r['id'] for r in data['needs'] if r['decision']=='retained'}
        limitations = ['Mission « '+r['task']+' » bloquée : '+r['reason']+'. Limite : '+r['limits']
                       for r in data['missions'] if r['outcome']=='blocked' and retained.intersection(r['need_ids'])]
        result['unknowns'] = list(dict.fromkeys([*data['unknowns'],*limitations]))
        state._schema('strategy-summary-v2',result)
    return result


@phase
def register(run_dir, report_path):
    state.invalidate_changed(run_dir);run=state.load_run(run_dir)
    path=state._safe_path(Path(run['root']),report_path)
    data=read(path);refs=validate(run,data)
    identifier='observation-analysis-map'
    record=state._artifact_record(run,identifier,path.relative_to(run['root']).as_posix(),
                                  'internal',refs,reuse_current=True)
    if record!=run['artifacts'].get(identifier):
        run['artifacts'][identifier]=record
        state.save_run(run_dir,run)
    return inspect(run,'analysis.specialists')


def inspect(run, stage='brief.public'):
    try:
        version=state._contract_version(run,'audience_handoff_contract')
    except ValueError as error:
        return {'status':'BLOCKED','issues':[str(error)],'scope':'unsupported_audience_handoff_contract'}
    if version is None:
        return {'status':'NOT_REQUIRED','issues':[],'scope':'legacy_run_without_audience_handoff_contract'}
    try:
        _,path=artifact(run,'observation-analysis-map');data=read(path);validate(run,data)
        if stage!='analysis.specialists':
            model,_path=artifact(run,'company-evidence-brief')
            if 'artifact:observation-analysis-map' not in state._dependency_closure(run,model['dependencies']):
                raise ValueError('Company model must depend on analyzed audiences and needs')
            if read(_path).get('audience_need_summary')!=summary(data): raise ValueError('Company model lost an audience/need status, consequence or unknown')
        if stage not in {'analysis.specialists','company.v2'}:
            brief,_path=artifact(run,'creative-inputs');inputs=read(_path)
            if 'artifact:company-evidence-brief' not in state._dependency_closure(run,brief['dependencies']):
                raise ValueError('Creative brief must depend on reconciled company model')
            if inputs.get('audience_need_summary')!=summary(data): raise ValueError('Creative brief lost the public audience/need summary')
            for need in data['needs']:
                if need['decision']!='retained':continue
                observations=[o for o in inputs['observations'] if need['id'] in o.get('need_ids',[]) and o.get('decision')=='retained']
                if not observations: raise ValueError('Retained need absent from creative observations: '+need['id'])
                if not any(set('source:'+s for s in need['source_ids']).issubset(state._dependency_closure(run,[o['proof']])) for o in observations):
                    raise ValueError('Creative observation lost need provenance')
        result = {'status':'PASS','issues':[],'scope':'declared_handoff_and_current_evidence_only','actual_reading_navigation_and_semantics':'HOST_REVIEW_REQUIRED'}
        if version == 2:
            result['audience_need_summary'] = summary(data)
        return result
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
        return {'status':'BLOCKED','issues':[str(error)[:300]],'scope':'declared_handoff_and_current_evidence_only'}


def task_data(run,root,commit,entrypoints):
    root=Path(root)
    version = state._contract_version(run,'audience_handoff_contract') or 1
    task={'version':version,'url':run['url'],'stage':'analysis.specialists','methods':[
        {'name':name,'commit':commit,'reference_root':str(root),
         'entrypoint':str(root/entry),'sha256':state._sha(root/entry)}
        for name,entry in zip(METHODS,entrypoints)],
        'references':[str(p) for p in sorted(root.rglob('*')) if p.is_file()],
        'instructions':'Read both SKILL files and useful linked references. Apply product-marketing public draft first, then customer-research existing/public signals. No primary research, private tools, owner validation or invented ICP. Reuse current public research. Separate new/corroboration/reformulation from baseline; deduplicate source groups. Derive and execute bounded navigation missions without form submission, then reconcile model V2 and public brief. Follow proposition-strategy/references/audience-handoff.md; record actual reading and limitations.',
        'output':f'observation-analysis-map version={version} via strategy register; preserve its audience_need_summary in company-evidence-brief and creative-inputs. For V2, keep mission IDs, outcomes, public limits/reasons and source references; blocked missions remain limits, never invented user findings. This is host work, not runtime method execution.'}
    return task


def prepare(run_dir, cache=None):
    run=state.load_run(run_dir);package=upstream.fetch('marketingskills',cache)
    if package['status']!='COMPLETE': return {'status':'BLOCKED','package':package}
    family=package['families'][0];root=Path(family['source_path'])
    task=task_data(run,root,family['commit'],family['entrypoints'])
    path=Path(run['root'])/'strategy-task.json'
    if path.is_symlink(): raise ValueError('Strategy task cannot be a symlink')
    path.write_text(json.dumps(task,ensure_ascii=False,indent=2)+'\n')
    return {'status':'PREPARED','native_task_path':str(path),'execution':'HOST_REQUIRED'}
