"""Evidence gate for a source-led scroll narrative, not an automated WOW judge.

Files and relationships are checked. Artistic distinction, wording, measured
font sizes and the truth of declared observations still require isolated review.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from . import state
from .artifacts import sha256

STORY_ROLES = {'understanding','evidence','opportunity','creative_world',
               'transformation','agency_value','mission','next_step'}


def _text(value, label):
    if not isinstance(value,str) or not value.strip():
        raise ValueError(f'Missing {label}')
    return value


def _artifact(run, reference):
    if not isinstance(reference,str) or not reference.startswith('artifact:'):
        raise ValueError('An artifact reference is required')
    row=run['artifacts'].get(reference.removeprefix('artifact:'))
    if not row or row['status']!='CURRENT':
        raise ValueError('Missing current artifact: '+reference)
    path=state._safe_path(Path(run['root']),row['path'])
    if sha256(path)!=row['sha256']:
        raise ValueError('Artifact bytes changed: '+reference)
    return row,path


def _json(run, identifier):
    row,path=_artifact(run,'artifact:'+identifier)
    return json.loads(path.read_text()),row


def _proof(run, reference):
    if not isinstance(reference,str) or ':' not in reference:
        raise ValueError('A registered source or fact proof is required')
    kind,identifier=reference.split(':',1)
    if kind=='fact':
        row=run['facts'].get(identifier)
        if not row or row['status']!='CONFIRMED' or row['value'] is None or not row['source_ids']:
            raise ValueError('Unsupported fact: '+reference)
        for source in row['source_ids']:
            _proof(run,'source:'+source)
    elif kind=='source':
        row=run['sources'].get(identifier)
        if not row or row['status']!='COLLECTED' or row['kind']=='generated' or not row.get('path'):
            raise ValueError('Missing observed source: '+reference)
        if sha256(state._safe_path(Path(run['root']),row['path']))!=row['sha256']:
            raise ValueError('Source bytes changed: '+reference)
    else:
        raise ValueError('Client evidence must identify a source or fact, not an assertion')


def _render(run, reference):
    row,path=_artifact(run,reference)
    with Image.open(path) as image:
        if image.format not in ('PNG','JPEG','WEBP') or min(image.size)<64:
            raise ValueError('Moment must have an actual readable raster render')
        fingerprint=hashlib.sha256(str(image.size).encode()+image.convert('RGB').tobytes()).hexdigest()
        size=image.size
    return row,fingerprint,size


def _inputs(run):
    data,row=_json(run,'creative-inputs')
    _text(data['revision'],'input revision')
    ids=data['direction_ids']
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
        raise ValueError('Direction IDs must be explicit and unique before creation')
    for identifier in ids:state._identifier(identifier)
    specs={s['id']:s for s in json.loads((state.DATA_ROOT/'upstream-lock.json').read_text())['families'] if s.get('default',True)}
    methods=data['methods']
    if len(methods)!=len(specs) or {m['family'] for m in methods}!=set(specs):
        raise ValueError('All four named upstream families must be transmitted')
    for method in methods:
        if method['commit']!=specs[method['family']]['commit']:
            raise ValueError('Method version differs from the installed upstream lock')
        reference,_=_artifact(run,method['reference_ref'])
        source_root=Path(_text(method['reference_root'],'complete public method tree'))
        if not source_root.is_absolute(): source_root=Path(run['root'])/source_root
        from .upstream import _checked
        _checked(source_root)
        from .upstream import _inspect
        spec=specs[method['family']]
        expected=source_root.parents[2]/spec['id']/spec['commit']/'source'
        if source_root!=expected or not _inspect(spec,source_root.parents[2])['complete']:
            raise ValueError('Method handoff needs its verified complete pinned source cache')
        entry=source_root/specs[method['family']]['entrypoints'][0]
        _checked(entry)
        if not entry.is_file() or sha256(entry)!=reference['sha256']:
            raise ValueError('Method handoff lacks its matching complete source reference')
    observations=data['observations']
    if not observations or len({o['id'] for o in observations})!=len(observations):
        raise ValueError('Observed findings need unique decisions before the creative brief')
    for finding in observations:
        _proof(run,finding['proof']);_text(finding['reason'],'selection reason')
        if finding['decision'] not in ('retained','excluded'):
            raise ValueError('Every finding must be retained or explicitly excluded')
        if finding['decision']=='retained':_text(finding['benefit'],'intended client benefit')
    if not any(o['decision']=='retained' for o in observations):
        raise ValueError('Creative brief needs at least one retained sourced opportunity')
    actions=data['actions']
    if not actions or len({a['id'] for a in actions})!=len(actions):
        raise ValueError('Existing important actions need an explicit unique inventory')
    for action in actions:
        _proof(run,action['proof']);_text(action['label'],'existing action label')
        if urlsplit(action['target']).scheme not in ('http','https','mailto','tel'):
            raise ValueError('Action target must be an observed usable URL')
    return data,row


def require_packet_methods(run, selected_files):
    """An isolated creator must receive the named method index and reference files."""
    inputs,_=_inputs(run)
    required={"creative-inputs"}|{m["reference_ref"].removeprefix("artifact:") for m in inputs["methods"]}
    selected=set()
    for requested in selected_files:
        row=run['artifacts'].get(requested)
        if row is None:
            row=next((a for a in run['artifacts'].values() if a['path']==str(requested)),None)
        if row: selected.add(row['id'])
    if not required.issubset(selected):
        raise ValueError('Creative packet omits named method inputs or references')


def _check_story(run, inputs):
    story,_=_json(run,'client-story')
    rows=story['pages']
    if not STORY_ROLES.issubset({r['role'] for r in rows}):
        raise ValueError('Client story omits a required commercial function')
    _,pdf=_artifact(run,'artifact:client-pdf')
    from pypdf import PdfReader
    count=len(PdfReader(pdf).pages)
    for row in rows:
        if type(row['page']) is not int or not 1<=row['page']<=count:
            raise ValueError('Story references a page absent from the final PDF')
        _text(row['message'],'page message');_proof(run,row['proof'])
    decisions=story['observation_decisions']
    if len(decisions)!=len(inputs['observations']) or {d['id'] for d in decisions}!={o['id'] for o in inputs['observations']}:
        raise ValueError('Every observed finding needs a story placement or motivated exclusion')
    findings={o['id']:o for o in inputs['observations']}
    for decision in decisions:
        _text(decision['reason'],'story selection reason')
        if findings[decision['id']]['decision']=='retained':
            if type(decision.get('page')) is not int or not 1<=decision['page']<=count:
                raise ValueError('A retained finding disappeared from the client story')
    _text(story['next_step']['decision'],'next client decision')
    _text(story['next_step']['followup'],'concrete next exchange')


def inspect_experience(run, stage='creative.direction'):
    """Fail closed on missing evidence; never derive aesthetic scores from JSON."""
    checks=[]
    try:
        inputs,input_row=_inputs(run)
        plan,_=_json(run,'creative-experience')
        if plan['inputs_sha256']!=input_row['sha256'] or plan['revision']!=inputs['revision']:
            raise ValueError('Creative plan is based on a different input revision')
        directions=plan['directions']
        if len(directions)!=len(inputs['direction_ids']) or {d['id'] for d in directions}!=set(inputs['direction_ids']):
            raise ValueError('A retained direction was dropped or an unbriefed direction added')
        all_ids=set(); render_hashes={}
        actions={a['id']:a for a in inputs['actions']}
        for direction in directions:
            # A static proposal is not evidence of implemented animation.
            if direction['motion_status']!='static_intent':
                raise ValueError('Implemented motion needs separate prototype qualification; this gate proves static intent only')
            moments=direction['moments']
            if len(moments)<3 or not {'opening','reveal','action'}.issubset({m['role'] for m in moments}):
                raise ValueError('A hero alone cannot demonstrate opening, reveal and action')
            if len({m['id'] for m in moments})!=len(moments):
                raise ValueError('Duplicate moment ID')
            if moments[0]['role']!='opening' or moments[-1]['role']!='action' or not any(m['role']=='reveal' for m in moments[1:-1]):
                raise ValueError('Opening, reveal and action must occur in that narrative order')
            positions=[m['scroll_position'] for m in moments]
            if (any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in positions)
                    or any(a>=b for a,b in zip(positions,positions[1:]))):
                raise ValueError('Scroll moments must describe a forward, finite progression')
            meanings=set();fingerprints=set();roles={}
            for moment in moments:
                _proof(run,moment['proof']);meanings.add(_text(moment['meaning'],'meaning of this moment'))
                row,fingerprint,_=_render(run,moment['render_ref'])
                creative_id=moment['creative_id'];state._identifier(creative_id)
                if creative_id in all_ids:raise ValueError('Creative IDs must be unique across directions and viewports')
                all_ids.add(creative_id);render_hashes[creative_id]=row['sha256']
                fingerprints.add(fingerprint);roles[moment['id']]=moment['role']
            if len(fingerprints)!=len(moments) or len(meanings)!=len(moments):
                raise ValueError('Repeated scene pixels or repeated meaning do not prove a scroll narrative')
            signature=direction['signature']
            if roles.get(signature['moment_id'])!='reveal':
                raise ValueError('The signature moment must be a rendered reveal beyond the opening')
            _proof(run,signature['client_anchor']);_text(signature['visible_change'],'visible client-specific signature')
            mobile=direction['mobile'];row,fingerprint,size=_render(run,mobile['render_ref'])
            if fingerprint in fingerprints or size[1]<=size[0]:
                raise ValueError('Mobile must be a separate portrait composition, not the desktop image')
            identifier=mobile['creative_id'];state._identifier(identifier)
            if identifier in all_ids:raise ValueError('Mobile creative ID is not unique')
            all_ids.add(identifier);render_hashes[identifier]=row['sha256']
            font=mobile['action_text_px']
            if type(font) not in (int,float) or not math.isfinite(font) or font<14:
                raise ValueError('Critical mobile action text must meet the internal 14px readability floor')
            proposed=direction['actions']
            if len(proposed)!=len(actions) or {a['id'] for a in proposed}!=set(actions) or mobile['action_id'] not in actions:
                raise ValueError('An existing important action is omitted')
            for action in proposed:
                if roles.get(action['moment_id'])!='action':
                    raise ValueError('Action needs a rendered arrival moment, not only a hero label')
                _text(action['label'],'proposed action label')
                original=actions[action['id']]
                if action['disposition']=='preserved' and action['target']==original['target']:
                    continue
                if action['disposition']!='changed_with_approval':
                    raise ValueError('Existing action target changed without explicit approval')
                _text(action['reason'],'approved action change reason')
                _,approval=_artifact(run,action['approval_ref'])
                evidence=json.loads(approval.read_text())
                if (evidence['action_id']!=action['id'] or evidence['from']!=original['target']
                        or evidence['to']!=action['target'] or evidence['decision']!='approved'
                        or not evidence.get('actor') or not evidence.get('authority_proof')):
                    raise ValueError('Approval does not bind the exact action change')
                _artifact(run,evidence['authority_proof'])
            checks.append({'direction':direction['id'],'moments':len(moments),'mobile':'present','actions':'accounted_for'})
        applications=plan['method_applications'];methods={m['family']:m for m in inputs['methods']}
        if len(applications)!=len(methods) or {a['family'] for a in applications}!=set(methods):
            raise ValueError('Four named method applications must reach the creative role')
        for application in applications:
            reference,_=_artifact(run,methods[application['family']]['reference_ref'])
            if application['mode'] not in ('adapted','native') or application['read_sha256']!=reference['sha256']:
                raise ValueError('Method unavailable or read receipt differs from the transmitted reference')
            if application['mode']=='native':
                _,receipt_path=_artifact(run,application['execution_ref'])
                receipt=json.loads(receipt_path.read_text())
                if (receipt.get('family')!=application['family'] or receipt.get('reference_sha256')!=reference['sha256']
                        or receipt.get('status')!='PASS' or not receipt.get('outputs')):
                    raise ValueError('Native execution needs a bound successful execution receipt')
                for output in receipt['outputs']:_artifact(run,output)
            _text(application['application'],'specific method application')
            if not application['moment_ids'] or not set(application['moment_ids']).issubset(all_ids):
                raise ValueError('Method application must identify actual rendered creative IDs')
        # Preserve every retained beat, not just the preferred hero, at downstream montage.
        if run.get('metadata',{}).get('creative_selection'):
            from .preservation import _selection
            locked=_selection(run)['retained']
            if {r['id'] for r in locked}!=all_ids or any(r['sha256']!=render_hashes[r['id']] for r in locked):
                raise ValueError('Frozen selection does not preserve all rendered narrative moments')
        if stage in ('client.composition','export.documents','verify.final'):
            _check_story(run,inputs)
        return {'status':'PASS','scope':'experience_evidence_consistency_only','checks':checks,
                'aesthetic_quality':'REQUIRES_ISOLATED_REVIEW','declared_measurements':'REQUIRE_RENDER_REVIEW','issues':[]}
    except (ValueError,OSError,KeyError,TypeError,IndexError,AttributeError) as error:
        return {'status':'BLOCKED','scope':'experience_evidence_consistency_only','checks':checks,'issues':[str(error)]}
