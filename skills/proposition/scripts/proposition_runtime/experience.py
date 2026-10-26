"""Evidence gate for a source-led scroll narrative, not an automated WOW judge.

Files and relationships are checked. Artistic distinction, wording, measured
font sizes and the truth of declared observations still require isolated review.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
from . import state
from .artifacts import sha256

STORY_ROLES = {'understanding','evidence','opportunity','creative_world',
               'transformation','agency_value','mission','next_step'}
MANDATE_INPUT_LIMIT = 256 * 1024


def read_mandate_input(path):
    """Bound regular-file checks and reading by bytes and a killable 5s child."""
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('recovery.py')),
            '--read-small',str(path),str(MANDATE_INPUT_LIMIT)],capture_output=True,timeout=5)
    except subprocess.TimeoutExpired as error:
        raise ValueError('Creative mandate input read deadline exceeded (5s)') from error
    if result.returncode!=0 or len(result.stdout)>MANDATE_INPUT_LIMIT:
        raise ValueError('Creative mandate input must be a readable regular file of at most 256 KiB, without symlinks')
    return result.stdout


def _time(value):
    moment=datetime.fromisoformat(_text(value,'dated exploration evidence'))
    if moment.tzinfo is None:
        raise ValueError('Exploration timestamps must include a timezone')
    return moment


def initial_exploration_contract(url, mandate, initialized_at):
    """Pin invocation evidence, not a claim to authenticate its human author."""
    contract={'version':1,'mode':'explore','minimum_candidates':2,
              'selection_policy':'agent_after_comparison'}
    if mandate is None:return contract,None
    try:
        if mandate['version']!=1 or mandate['mode'] not in ('exact_count','external_selection'):
            raise ValueError('Unsupported creative mandate; new runs cannot downgrade exploration')
        count=mandate['candidate_count']
        if type(count) is not int or count<1:
            raise ValueError('Explicit candidate count must be a positive integer')
        policy=mandate.get('selection_policy','agent_after_comparison')
        if policy not in ('agent_after_comparison','keep_open'):
            raise ValueError('Unknown creative selection policy')
        authority=mandate['authority']
        if authority['kind']!='current_user_instruction' or authority['site_url']!=url:
            raise ValueError('A creative exception needs the current user instruction for this site')
        age=(_time(initialized_at)-_time(authority['captured_at'])).total_seconds()
        if not 0<=age<=86400:
            raise ValueError('Creative mandate instruction capture is stale or future-dated')
        path=Path(authority['input_path'])
        if not path.is_absolute():raise ValueError('Instruction capture needs an absolute input path')
        content=read_mandate_input(path);instruction=content.decode('utf-8')
        if hashlib.sha256(content).hexdigest()!=authority['input_sha256']:
            raise ValueError('Creative mandate instruction hash does not match')
        if _text(authority['quote'],'explicit instruction quote') not in instruction:
            raise ValueError('Creative mandate quote is absent from the current instruction')
        contract.pop('minimum_candidates')
        contract.update(mode=mandate['mode'],candidate_count=count,selection_policy=policy,
            authority={**authority,'input_path':'creative-mandate-input.txt'})
        if mandate['mode']=='external_selection':
            ids=mandate['candidate_ids']
            if not isinstance(ids,list) or len(ids)!=count or len(set(ids))!=count:
                raise ValueError('External selection must name exactly the mandated candidate IDs')
            for identifier in ids:state._identifier(identifier)
            contract['candidate_ids']=ids
        return contract,content
    except (KeyError,TypeError,UnicodeError,OSError) as error:
        raise ValueError('Creative mandate lacks a coherent current instruction authority') from error


def exploration_contract(run):
    contract=run.get('metadata',{}).get('creative_exploration_contract')
    if contract is None:return None  # Historical evidence remains readable without recrawling.
    if contract.get('version')!=1 or contract.get('mode') not in ('explore','exact_count','external_selection'):
        raise ValueError('Invalid initialized creative exploration contract')
    if contract['mode']=='explore':
        if contract.get('minimum_candidates')!=2 or contract.get('selection_policy')!='agent_after_comparison':
            raise ValueError('Default exploration cannot be downgraded')
    else:
        authority=contract['authority']
        if authority['input_path']!='creative-mandate-input.txt':
            raise ValueError('Initialized creative mandate authority path changed')
        path=Path(run['root'])/authority['input_path']
        content=read_mandate_input(path)
        if (authority['kind']!='current_user_instruction' or authority['site_url']!=run['url']
                or hashlib.sha256(content).hexdigest()!=authority['input_sha256']
                or authority['quote'] not in content.decode('utf-8')):
            raise ValueError('Initialized creative mandate authority changed')
    return contract


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
    if run['profile']['parameters'].get('proposal_contract')==2:
        opportunity=data['opportunity']
        for field in ('audience','task','change','benefit','scope','alternative'):
            _text(opportunity[field],'opportunity '+field)
        _proof(run,opportunity['proof'])
        for field in ('preserve','adapt','unknown'):
            codes=opportunity['brand_codes'][field]
            if not isinstance(codes,list) or any(not isinstance(c,str) or not c.strip() for c in codes):
                raise ValueError('Brand codes must separate preserved, adaptable and unknown choices')
    _text(data['revision'],'input revision')
    ids=data['direction_ids']
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
        raise ValueError('Direction IDs must be explicit and unique before creation')
    for identifier in ids:state._identifier(identifier)
    contract=exploration_contract(run)
    if contract:
        if contract['mode']=='explore' and len(ids)<contract['minimum_candidates']:
            raise ValueError('Default exploration needs at least two candidate worlds before selection')
        if contract['mode']!='explore' and len(ids)!=contract['candidate_count']:
            raise ValueError('Candidate count differs from the initialized explicit mandate')
        if contract['mode']=='external_selection' and set(ids)!=set(contract['candidate_ids']):
            raise ValueError('Candidate IDs differ from the initialized external selection')
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


def _read_segments(segments, path, earliest, latest, *, complete):
    """Check declared coverage and time bounds, never infer actual comprehension."""
    count=len(path.read_text(encoding='utf-8').splitlines())
    if not isinstance(segments,list) or not segments:
        raise ValueError('Method reading needs explicit completed line segments')
    covered=[]
    for segment in segments:
        start,end=segment['start_line'],segment['end_line']
        if type(start) is not int or type(end) is not int or not 1<=start<=end<=count:
            raise ValueError('Method reading segment is outside the actual reference')
        if not earliest<=_time(segment['read_at'])<=latest:
            raise ValueError('Method reading must follow current inputs and precede receipt registration')
        covered.append((start,end))
    if complete:
        cursor=1
        for start,end in sorted(covered):
            if start>cursor:raise ValueError('Method reading has an unread reference gap')
            cursor=max(cursor,end+1)
        if cursor<=count:raise ValueError('Method reading does not cover the complete entrypoint')


def _method_reading(run, inputs, input_row):
    contract=run.get('metadata',{}).get('creative_reading_contract')
    if contract is None:return None  # Do not retrofit historical evidence.
    if type(contract) is not int or contract!=1:
        raise ValueError('Invalid initialized creative reading contract')
    data,row=_json(run,'creative-reading')
    if type(data['version']) is not int or data['version']!=1 or data['inputs_sha256']!=input_row['sha256']:
        raise ValueError('Method reading belongs to a different creative input version')
    _text(data['reader_id'],'creative reader identity')
    methods={m['family']:m for m in inputs['methods']}; reads=data['methods']
    if len(reads)!=len(methods) or {r['family'] for r in reads}!=set(methods):
        raise ValueError('Method reading must cover the four named families exactly once')
    earliest=_time(input_row['recorded_at']); latest=_time(row['recorded_at'])
    for item in reads:
        reference,path=_artifact(run,methods[item['family']]['reference_ref'])
        if item['read_sha256']!=reference['sha256']:
            raise ValueError('Method reading hash differs from the transmitted reference')
        _read_segments(item['segments'],path,max(earliest,_time(reference['recorded_at'])),latest,complete=True)
    for item in data.get('supporting_reads',[]):
        method=methods[item['family']]; _text(item['purpose'],'linked reference purpose')
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Linked method references must stay inside the public method tree')
        root=Path(method['reference_root'])
        if not root.is_absolute():root=Path(run['root'])/root
        path=root/relative
        from .upstream import _checked
        _checked(path)
        if not path.is_file() or sha256(path)!=item['sha256']:
            raise ValueError('Linked method reading hash differs from its pinned reference')
        _read_segments(item['segments'],path,earliest,latest,complete=False)
    return row


def inspect_creative_inputs(run):
    """Cheap preflight of inputs and declared reading, before any candidate render."""
    try:
        inputs,row=_inputs(run)
        reading=_method_reading(run,inputs,row)
        return {'status':'PASS','scope':'creative_input_reading_consistency_only',
                'reading_contract':'checked' if reading else 'historical_not_required',
                'actual_reading':'REQUIRES_TOOL_RECEIPT_REVIEW','issues':[]}
    except (ValueError,OSError,KeyError,TypeError,IndexError,AttributeError) as error:
        return {'status':'BLOCKED','scope':'creative_input_reading_consistency_only','issues':[str(error)]}


def _reading_before(reading, render, rendered_at=None):
    cutoff=_time(render['recorded_at'])
    if rendered_at is not None:
        cutoff=_time(rendered_at)
        if cutoff>_time(render['recorded_at']):
            raise ValueError('Declared central render cannot follow its artifact registration')
    if reading and _time(reading['recorded_at'])>=cutoff:
        raise ValueError('Method reading receipt must be registered before creative renders; late recovery cannot backdate it')


def _check_exploration(run, inputs, input_row, plan_row, reading=None):
    """Check declared comparison and local registration order, not artistic truth."""
    contract=exploration_contract(run)
    if contract is None:return set(inputs['direction_ids']),None
    data,row=_json(run,'creative-exploration')
    if data['version']!=1 or data['inputs_sha256']!=input_row['sha256']:
        raise ValueError('Exploration belongs to a different creative input version')
    candidates=data['candidates'];ids=set(inputs['direction_ids'])
    if len(candidates)!=len(ids) or {c['id'] for c in candidates}!=ids:
        raise ValueError('Every candidate world needs its own inspected central scene')
    structures=[];fingerprints=set();central_hashes={};inspected=[]
    for candidate in candidates:
        image,fingerprint,_=_render(run,candidate['central_scene_ref'])
        _reading_before(reading,image,_text(candidate['rendered_at'],'central render timestamp') if reading else None)
        if candidate['central_scene_sha256']!=image['sha256']:
            raise ValueError('Candidate central scene hash is stale')
        if fingerprint in fingerprints:
            raise ValueError('Repeated central scene pixels are not distinct candidate worlds')
        fingerprints.add(fingerprint);central_hashes[candidate['id']]=image['sha256']
        _proof(run,candidate['client_anchor'])
        structure=tuple(_text(candidate['structure'][key],key).strip().casefold()
                        for key in ('composition','visual_mechanism','narrative_entry'))
        # Changing a label or scrolling the same world does not declare a new structure.
        if any(sum(a!=b for a,b in zip(structure,other))<2 for other in structures):
            raise ValueError('Candidate worlds need distinct composition and creative structure')
        structures.append(structure)
        _text(candidate['inspection'],'actual central-scene inspection')
        seen=_time(candidate['inspected_at']);inspected.append(seen)
        if not _time(image['recorded_at'])<=seen:
            raise ValueError('A central scene must be registered before its declared inspection')
    comparison=data['comparison']
    compared_ids=comparison['candidate_ids']
    if len(compared_ids)!=len(ids) or set(compared_ids)!=ids:
        raise ValueError('Comparison must account for every rendered candidate world')
    _text(comparison['structural_differences'],'comparison of structural differences')
    compared=_time(comparison['compared_at']);selection=data['selection']
    selected_ids=selection['selected_candidate_ids']
    if not isinstance(selected_ids,list) or not selected_ids or len(set(selected_ids))!=len(selected_ids) or not set(selected_ids).issubset(ids):
        raise ValueError('Selection must retain an explicit nonempty subset of compared candidates')
    if (contract.get('selection_policy')=='keep_open' or contract['mode']=='external_selection') and set(selected_ids)!=ids:
        raise ValueError('The initialized mandate requires keeping every named direction')
    _text(selection['reason'],'selection after rendered comparison')
    selected=_time(selection['selected_at'])
    if not (max(inspected)<=compared<=selected<=_time(row['recorded_at'])<=_time(plan_row['recorded_at'])):
        raise ValueError('Inspection and comparison must precede selection and developed plan registration')
    return set(selected_ids),{'selected_at':selected,'central_hashes':central_hashes}


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


def inspect_experience(run, stage='creative.direction', *, proposed_selection=None):
    """Fail closed on missing evidence; never derive aesthetic scores from JSON."""
    checks=[]
    try:
        inputs,input_row=_inputs(run)
        reading=_method_reading(run,inputs,input_row)
        plan,plan_row=_json(run,'creative-experience')
        if plan['inputs_sha256']!=input_row['sha256'] or plan['revision']!=inputs['revision']:
            raise ValueError('Creative plan is based on a different input revision')
        retained_ids,exploration=_check_exploration(run,inputs,input_row,plan_row,reading)
        directions=plan['directions']
        if len(directions)!=len(retained_ids) or {d['id'] for d in directions}!=retained_ids:
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
            meanings=set();fingerprints=set();roles={};direction_hashes=set()
            for moment in moments:
                _proof(run,moment['proof']);meanings.add(_text(moment['meaning'],'meaning of this moment'))
                row,fingerprint,_=_render(run,moment['render_ref'])
                _reading_before(reading,row)
                if exploration and row['sha256']!=exploration['central_hashes'][direction['id']] and _time(row['recorded_at'])<exploration['selected_at']:
                    raise ValueError('Developed beats must be registered after candidate comparison and selection')
                creative_id=moment['creative_id'];state._identifier(creative_id)
                if creative_id in all_ids:raise ValueError('Creative IDs must be unique across directions and viewports')
                all_ids.add(creative_id);render_hashes[creative_id]=row['sha256']
                direction_hashes.add(row['sha256'])
                fingerprints.add(fingerprint);roles[moment['id']]=moment['role']
            if len(fingerprints)!=len(moments) or len(meanings)!=len(moments):
                raise ValueError('Repeated scene pixels or repeated meaning do not prove a scroll narrative')
            if exploration and exploration['central_hashes'][direction['id']] not in direction_hashes:
                raise ValueError('A selected central scene must be preserved in its developed direction')
            signature=direction['signature']
            if roles.get(signature['moment_id'])!='reveal':
                raise ValueError('The signature moment must be a rendered reveal beyond the opening')
            _proof(run,signature['client_anchor']);_text(signature['visible_change'],'visible client-specific signature')
            mobile=direction['mobile'];row,fingerprint,size=_render(run,mobile['render_ref'])
            _reading_before(reading,row)
            if exploration and _time(row['recorded_at'])<exploration['selected_at']:
                raise ValueError('Developed mobile view must follow candidate comparison and selection')
            if run['profile']['parameters'].get('proposal_contract')==2:
                width=mobile['viewport_width_px']
                if type(width) is not int or not 240<=width<=768:
                    raise ValueError('Mobile needs its actual target CSS viewport width')
                _text(mobile['adaptation'],'actual mobile rearrangement to inspect')
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
        if proposed_selection is not None or run.get('metadata',{}).get('creative_selection'):
            from .preservation import _selection
            locked=proposed_selection if proposed_selection is not None else _selection(run)['retained']
            if len(locked)!=len(all_ids) or {r['id'] for r in locked}!=all_ids or any(r['sha256']!=render_hashes[r['id']] for r in locked):
                raise ValueError('Frozen selection does not preserve all rendered narrative moments')
        if stage in ('client.composition','export.documents','verify.final'):
            _check_story(run,inputs)
        return {'status':'PASS','scope':'experience_evidence_consistency_only','checks':checks,
                'aesthetic_quality':'REQUIRES_ISOLATED_REVIEW','declared_measurements':'REQUIRE_RENDER_REVIEW','issues':[]}
    except (ValueError,OSError,KeyError,TypeError,IndexError,AttributeError) as error:
        return {'status':'BLOCKED','scope':'experience_evidence_consistency_only','checks':checks,'issues':[str(error)]}
