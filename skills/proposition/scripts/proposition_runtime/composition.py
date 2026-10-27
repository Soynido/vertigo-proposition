"""Prior deck planning and revision-bound handoffs, never an aesthetic judge."""
from __future__ import annotations

import json
from pathlib import Path

from . import state

FUNCTIONS = {f'K{i:02}' for i in range(1, 9)}
OUTPUTS = {'client-source': '.html', 'presentation-catalog': '.json',
           'client-pdf': '.pdf', 'client-pptx': '.pptx'}
CLIENT_INPUTS = tuple('artifact:'+x for x in
    ('client-source', 'presentation-catalog', 'client-pdf', 'client-pptx',
     'client-story-map', 'client-story', 'composition-plan-review'))
DERIVATIVES = {'sales-source', 'sales-pdf', 'sales-playbook', 'follow-up-register',
               'technical-source', 'technical-pdf', 'technical-handoff', 'client-context'}


def enabled(run):
    return run.get('metadata', {}).get('sales_kit_contract') == 1


def _current(run, reference):
    from .experience import _artifact
    row, path = _artifact(run, reference)
    for dependency in state._dependency_closure(run, [reference]):
        record = state._resolve(run, dependency)
        if record is None or state._stale_reasons(run, Path(run['root']), record):
            raise ValueError('Composition input has changed: '+dependency)
    return row, path


def _public_proof(run, reference):
    from .experience import _proof
    _proof(run, reference)
    record = state._resolve(run, reference)
    if reference.startswith('fact:'):
        if not record.get('public_allowed'):
            raise ValueError('Composition facts need explicit public allowance')
        for identifier in record['source_ids']:
            _public_proof(run, 'source:'+identifier)
    elif record.get('audience') not in ('public', 'client') or record.get('kind') in ('private', 'generated'):
        raise ValueError('Composition proof must be public, never private or generated')


def _plan(run):
    from .experience import _text, _render
    from .preservation import _selection
    plan_row, path = _current(run, 'artifact:client-story-map')
    plan = json.loads(path.read_text())
    if plan['version'] != 1:
        raise ValueError('Unsupported commercial plan version')
    _text(plan['revision'], 'composition revision')
    if plan['inputs_ref'] != 'artifact:creative-inputs':
        raise ValueError('Composition must consume the canonical creative inputs')
    _current(run, plan['inputs_ref'])
    _selection(run)
    if plan['creative_lock_sha256'] != run['metadata']['creative_selection']['sha256']:
        raise ValueError('Composition uses a different frozen creative selection')
    dependencies = {'artifact:client-story-map', plan['inputs_ref']}
    coverage = plan['coverage']
    if len(coverage) != 8 or {row['id'] for row in coverage} != FUNCTIONS:
        raise ValueError('Commercial plan must cover K01-K08 distinctly, not eight pages')
    for row in coverage:
        if row.get('status', 'REQUIRED') != 'REQUIRED':
            raise ValueError('The author cannot exempt a required commercial function')
        if type(row['page']) is not int or row['page'] < 1:
            raise ValueError('Commercial function needs a positive planned page')
        for field in ('anchor', 'message'):
            _text(row[field], 'commercial '+field)
        if row['claim_status'] not in ('observed', 'declared', 'proposed', 'estimate', 'unknown'):
            raise ValueError('Commercial claim needs an honest evidence status')
        _public_proof(run, row['proof']); dependencies.add(row['proof'])
        visual, _ = _current(run, row['visual_ref'])
        if visual['audience'] not in ('public', 'client'):
            raise ValueError('A commercial visual must be in the public project packet')
        dependencies.add(row['visual_ref'])
    by_id = {row['id']: row for row in coverage}
    _text(by_id['K03']['mechanism'], 'shown approach mechanism')
    _text(by_id['K06']['effect'], 'conditional visitor/business effect')
    for lever in ('acquisition', 'conversion'):
        measure = by_id['K06']['measurement'][lever]
        _text(measure['indicator'], lever+' indicator')
        if measure['data_status'] == 'available':
            _public_proof(run, measure['proof']); dependencies.add(measure['proof'])
        elif measure['data_status'] in ('unknown', 'not_applicable'):
            _text(measure['reason'], lever+' measurement limit')
        else:
            raise ValueError('Measurement must separate available, unknown and not_applicable')
    mission = by_id['K07']['mission']
    _text(mission['scope'], 'agency realization scope')
    for field in ('included', 'excluded', 'conditions'):
        values = mission[field]
        if not isinstance(values, list) or not values:
            raise ValueError('Agency mission needs explicit '+field)
        for value in values: _text(value, 'mission '+field)
    _text(by_id['K08']['decision'], 'next client agreement')
    passages = plan['visual_plan']
    if len(passages) != 3 or {row['role'] for row in passages} != {
            'opening', 'proof_to_proposal', 'proposal_to_decision'}:
        raise ValueError('Deck plan must show opening and both decisive commercial bridges')
    for row in passages:
        _current(run, row['render_ref']); _render(run, row['render_ref'])
        _text(row['inspection'], 'localized deck-plan inspection')
        dependencies.add(row['render_ref'])
    pilot = plan['pilot']
    if pilot['intention_ref'] not in {row['render_ref'] for row in passages}:
        raise ValueError('The pilot must refer to the inspected visual intention')
    _current(run, pilot['render_ref']); _render(run, pilot['render_ref'])
    _text(pilot['comparison'], 'pilot comparison to visual intention')
    dependencies.add(pilot['render_ref'])
    if set(plan['outputs']) != set(OUTPUTS):
        raise ValueError('Plan must identify the canonical source, catalogue, PDF and PPTX paths')
    paths = set()
    for identifier, suffix in OUTPUTS.items():
        output = state._safe_path(Path(run['root']), plan['outputs'][identifier], exists=False)
        if output.suffix.lower() != suffix or output in paths:
            raise ValueError('Composition outputs need distinct correctly typed paths')
        paths.add(output)
    return plan, plan_row, sorted(dependencies)


def _approval(run):
    from .experience import _time
    binding = run.get('metadata', {}).get('composition_approval')
    if not binding:
        raise ValueError('Missing prior composition approval; prepare the visual plan before manufacturing')
    row, path = _current(run, 'artifact:composition-plan-review')
    receipt = json.loads(path.read_text())
    if (binding['sha256'] != row['sha256'] or receipt['run_id'] != run['id']
            or receipt['plan_sha256'] != run['artifacts']['client-story-map']['sha256']):
        raise ValueError('Composition approval belongs to a different run or plan')
    if _time(row['recorded_at']) < _time(receipt['accepted_at']):
        raise ValueError('Invalid composition approval chronology')
    return receipt, row


def review_plan(run_dir):
    """CLI preflight records a hash-bound receipt before any complete output exists."""
    state.invalidate_changed(run_dir)
    run = state.load_run(run_dir)
    try:
        if not enabled(run):
            raise ValueError('Historical run: retain its original scope; use a fresh run for this contract')
        plan, plan_row, dependencies = _plan(run)
        try:
            receipt, _ = _approval(run)
            return {'status': 'PASS', 'scope': 'composition_evidence_only', 'receipt': receipt,
                    'quality': 'REQUIRES_EXACT_ARTIFACT_REVIEW', 'issues': []}
        except (ValueError, KeyError):
            pass
        for output in plan['outputs'].values():
            if state._safe_path(Path(run['root']), output, exists=False).exists():
                raise ValueError('Complete output already exists: a late plan cannot regularize it')
        receipt = {'version': 1, 'run_id': run['id'], 'revision': plan['revision'],
            'plan_sha256': plan_row['sha256'], 'accepted_at': state._now(),
            'outputs': plan['outputs'], 'creative_lock_sha256': plan['creative_lock_sha256'],
            'scope': 'composition_evidence_only'}
        folder = Path(run['root'])/'composition'; folder.mkdir(exist_ok=True)
        path = folder/('approval-'+state._digest(receipt)+'.json')
        with path.open('x') as stream: json.dump(receipt, stream, ensure_ascii=False, indent=2)
        row = state.add_artifact(run_dir, 'composition-plan-review', path, 'internal', dependencies)
        run = state.load_run(run_dir)
        run['metadata']['composition_approval'] = {'sha256': row['sha256']}
        state.save_run(run_dir, run)
        return {'status': 'PASS', 'scope': 'composition_evidence_only', 'receipt': receipt,
                'quality': 'REQUIRES_EXACT_ARTIFACT_REVIEW', 'issues': []}
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        return {'status': 'BLOCKED', 'scope': 'composition_evidence_only', 'issues': [str(error)]}


def bind_dependencies(run, identifier, dependencies):
    """Keep generic registration usable; gates reject incomplete derived packets."""
    dependencies = list(dependencies)
    if enabled(run):
        wanted = []
        if identifier in {*OUTPUTS, 'client-story'}:
            wanted = ['artifact:composition-plan-review', 'artifact:client-story-map']
            if identifier not in ('client-source', 'client-story'):
                wanted.append('artifact:client-source')
            if identifier == 'client-story': wanted.append('artifact:client-pdf')
        elif identifier in DERIVATIVES:
            wanted = list(CLIENT_INPUTS)
        dependencies.extend(ref for ref in wanted if state._resolve(run, ref) is not None)
    return list(dict.fromkeys(dependencies))


def inspect_final(run, page_count):
    """Called by the existing experience gate, after its creative checks."""
    if not enabled(run): return
    from .experience import _time
    plan, _, _ = _plan(run)
    receipt, receipt_row = _approval(run)
    if receipt['creative_lock_sha256'] != plan['creative_lock_sha256']:
        raise ValueError('Composition receipt uses another creative lock')
    for identifier in OUTPUTS:
        row, path = _current(run, 'artifact:'+identifier)
        if path != state._safe_path(Path(run['root']), receipt['outputs'][identifier]):
            raise ValueError('Final output differs from the planned revision: '+identifier)
        if (_time(row['recorded_at']) <= _time(receipt_row['recorded_at'])
                or path.stat().st_mtime < _time(receipt['accepted_at']).timestamp()):
            raise ValueError('Final output predates its prior composition approval')
        closure = state._dependency_closure(run, row['dependencies'])
        if 'artifact:composition-plan-review' not in closure:
            raise ValueError('Final output is not bound to its prior composition approval')
    _, story_path = _current(run, 'artifact:client-story')
    story = json.loads(story_path.read_text())
    placements = story['kit_coverage']
    if len(placements) != 8 or {row['id'] for row in placements} != FUNCTIONS:
        raise ValueError('Final story must localize K01-K08 in the exact exports')
    for row in placements:
        if type(row['page']) is not int or not 1 <= row['page'] <= page_count:
            raise ValueError('Commercial function references a missing final page')
        if not isinstance(row['anchor'], str) or not row['anchor'].strip():
            raise ValueError('Commercial function needs its exact final zone')


def handoff_issues(run):
    if not enabled(run): return []
    issues = []
    identifiers = ({'client-context'} if state.delivery_scope(run) == 'client' else DERIVATIVES) & set(run['artifacts'])
    if state.delivery_scope(run) != 'client':
        identifiers |= {'sales-playbook', 'follow-up-register', 'technical-handoff'}
    # Sources/PDF/context created before the client packet must also be rebound.
    # Their absence here does not require exports prematurely at internal.handoffs.
    for identifier in sorted(identifiers):
        try:
            row, _ = _current(run, 'artifact:'+identifier)
            if not set(CLIENT_INPUTS).issubset(state._dependency_closure(run, row['dependencies'])):
                raise ValueError('Handoff must bind the current client source, story, catalogue and exports')
        except (ValueError, KeyError, OSError, TypeError) as error:
            issues.append(identifier+': '+str(error))
    return issues
