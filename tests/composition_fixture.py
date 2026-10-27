"""Fictional evidence for composition controls, never a creative-quality receipt."""
from pathlib import Path
import json
from proposition_runtime import state, preservation
from creative_fixture import make_scene
from experience_fixture import write_artifact


def prepare_plan(run):
    root = Path(run['root'])
    current = state.load_run(root)
    if not current['metadata'].get('creative_selection'):
        from experience_fixture import prepare_experience
        retained = prepare_experience(run)
        preservation.freeze_creatives(root, {'revision': 'r1', 'actor': 'fixture',
            'decision': 'Keep the compared fictional direction.', 'retained': retained})
    current = state.load_run(root)
    make_scene(root, 'deck-plan.png', 'white')
    state.add_artifact(root, 'deck-plan', 'deck-plan.png', 'internal')
    make_scene(root, 'deck-pilot.png', 'grey')
    state.add_artifact(root, 'deck-pilot', 'deck-pilot.png', 'internal')
    coverage = [{'id': f'K{i:02}', 'page': 1, 'anchor': f'zone-{i}',
        'message': 'Fictional task and scoped proposed agency work.',
        'proof': 'source:experience-source', 'claim_status': 'proposed',
        'visual_ref': 'artifact:scene-opening'} for i in range(1, 9)]
    coverage[2]['mechanism'] = 'Explain the material in the shown project states.'
    coverage[5]['effect'] = 'Help the visitor understand the application before requesting a quote.'
    coverage[5]['measurement'] = {
        'acquisition': {'indicator': 'Qualified visits', 'data_status': 'unknown',
                        'reason': 'No private analytics access.'},
        'conversion': {'indicator': 'Quote requests', 'data_status': 'unknown',
                       'reason': 'Measurement is proposed after engagement.'}}
    coverage[6]['mission'] = {'scope': 'Explain the material in the homepage journey.',
        'included': ['Design and implement the scoped homepage'],
        'excluded': ['Replacement of the quote system'],
        'conditions': ['Confirm integration and content rights before implementation']}
    coverage[7]['decision'] = 'Agree the first homepage scope with the prospect.'
    plan = {'version': 1, 'revision': 'composition-r1',
        'inputs_ref': 'artifact:creative-inputs',
        'creative_lock_sha256': current['metadata']['creative_selection']['sha256'],
        'coverage': coverage,
        'visual_plan': [{'role': role, 'render_ref': 'artifact:deck-plan',
                         'inspection': 'Fictional localized layout inspection.'}
                        for role in ('opening', 'proof_to_proposal', 'proposal_to_decision')],
        'pilot': {'render_ref': 'artifact:deck-pilot', 'intention_ref': 'artifact:deck-plan',
                  'comparison': 'Compare hierarchy, legibility, proof and scoped agency value.'},
        'outputs': {'client-source': 'client.html', 'presentation-catalog': 'presentation.json',
                    'client-pdf': 'client.pdf', 'client-pptx': 'client.pptx'}}
    write_artifact(run, 'client-story-map', 'client-story-map.json', plan)
    return plan


def register_client(run):
    """Register tiny fictional final files; other suites inspect real PDF/PPT pixels."""
    root = Path(run['root'])
    outputs = json.loads((root/'client-story-map.json').read_text())['outputs']
    for identifier, filename in outputs.items():
        (root/filename).parent.mkdir(parents=True, exist_ok=True)
        if identifier == 'client-source': (root/filename).write_text('<h1>Fictional scoped agency mission</h1>')
        elif identifier == 'presentation-catalog': (root/filename).write_text('{"elements": []}')
        elif not (root/filename).exists(): (root/filename).write_text('Fictional bytes, not a proposal.')
        state.add_artifact(root, identifier, filename, 'client')
