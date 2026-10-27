"""Explicit local operations used by the Codex skill, never a hidden autonomous LLM."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import html
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

from . import state


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def default_runs():
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'vertigo-proposition/runs'


def measure(run_dir, *, quota=None, source=None):
    run = state.load_run(run_dir)
    path = Path(run_dir) / 'metrics.json'
    previous = read_json(path) if path.is_file() else {}
    if quota is not None:
        if not 0 <= quota <= 100 or not source:
            raise ValueError('Quota needs a percentage from 0 to 100 and an observed source')
        previous.update(quota_remaining_percent=quota, quota_source=source,
                        quota_observed_at=datetime.now(timezone.utc).isoformat())
    elapsed = max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(run['created_at'])).total_seconds())
    remaining = previous.get('quota_remaining_percent')
    result = {'wall_seconds': round(elapsed, 2), 'active_seconds': None,
              'tokens_used': None, 'account_tokens_remaining': None,
              'quota_remaining_percent': remaining,
              'quota_source': previous.get('quota_source'),
              'quota_observed_at': previous.get('quota_observed_at'),
              'stop_for_quota': remaining is not None and remaining <= 25,
              'scope': 'wall time since run creation; token counts not exposed by this runtime'}
    quota_text = 'NON DISPONIBLE' if remaining is None else f'{remaining:g} % (relevé enregistré)'
    result['footer'] = (f"Temps écoulé : {int(elapsed // 60)} min {int(elapsed % 60):02d} s | "
                        f"Tokens utilisés : NON DISPONIBLES | Tokens compte restants : NON DISPONIBLES | "
                        f"Quota restant : {quota_text}")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def doctor(*, check_presentations=False):
    dependencies = {}
    for name in ('jsonschema', 'playwright', 'pypdf', 'pypdfium2', 'Pillow'):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    browser = {'status': 'UNAVAILABLE'}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            from .browser import launch_browser
            try:
                instance, channel = launch_browser(p)
                browser = {'status': 'AVAILABLE', 'version': instance.version, 'channel': channel}
                instance.close()
            except Exception:
                pass
    except ImportError:
        pass
    from . import presentation_probe
    presentation = presentation_probe.probe() if check_presentations else {
        'status': 'NOT_TESTED', 'tools': presentation_probe.inventory(), 'client_fidelity': 'NOT_RUN'}
    ready = all(dependencies.values()) and browser['status'] == 'AVAILABLE'
    if check_presentations: ready = ready and presentation['status'] == 'PASS'
    return {'status': 'PASS' if ready else 'BLOCKED',
            'scope': 'local_runtime_only', 'python': platform.python_version(), 'dependencies': dependencies,
            'browser': browser, 'contracts': state.CONTRACT_ROOT.is_dir(), 'registry': state.DATA_ROOT.is_dir(),
            'creative_quality': 'NOT_RUN', 'fresh_agent_contexts': 'HOST_REQUIRED', 'image_editing': 'HOST_REQUIRED',
            'sites': 'ADAPTER_NOT_CONFIGURED', 'private_connector': 'ADAPTER_NOT_CONFIGURED',
            'live_publication': 'NOT_RUN', 'slash_command': 'HOST_DEPENDENT',
            'presentations': presentation, 'required_mcp': [], 'host_capabilities': 'NOT_VERIFIED_BY_RUNTIME'}


def workbench(run_dir):
    run = state.load_run(run_dir)
    verdict = state.validate_run(run_dir)
    esc = lambda value: html.escape(str(value))
    sections = []
    for label, items in [('Sources', run['sources']), ('Faits retenus', run['facts']),
                         ('Livrables', run['artifacts']), ('Évaluations', run['evaluations'])]:
        rows = ''.join(f'<tr><td>{esc(key)}</td><td>{esc(item.get("status", "UNKNOWN"))}</td>'
                       f'<td>{esc(item.get("audience", "interne"))}</td>'
                       f'<td>{esc(item.get("path", item.get("locator", "")))}</td></tr>' for key, item in items.items())
        sections.append(f'<section><h2>{label}</h2><table><tr><th>ID</th><th>État</th><th>Audience</th><th>Preuve</th></tr>{rows}</table></section>')
    document = ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Vue interne</title>'
                '<style>body{font:16px system-ui;margin:3rem auto;max-width:1100px;padding:0 24px;color:#202124;background:#f6f5f1}'
                'h1{font-size:44px}section{background:white;padding:24px;margin:20px 0;border:1px solid #ddd}'
                'td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}table{width:100%;overflow-wrap:anywhere}</style>'
                f'<h1>Vue interne de validation</h1><p>{esc(run["id"])} · {esc(run["url"])}</p>'
                f'<p>État global : <strong>{esc(verdict["status"])}</strong>. Cette vue ne certifie pas la qualité créative.</p>'
                '<p>Les valeurs des notes et des faits privés ne sont pas recopiées dans cette vue.</p>' + ''.join(sections) + '</html>')
    target = Path(run_dir) / 'workbench.html'
    target.write_text(document, encoding='utf-8')
    return {'path': str(target), 'scope': 'private_local_index', 'status': 'PREPARED', 'quality': verdict['status']}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    doctor_parser = sub.add_parser('doctor')
    doctor_parser.add_argument('--presentations', action='store_true', help='Test a real local editable/rendered PPTX fixture')
    s = sub.add_parser('init'); s.add_argument('url'); s.add_argument('--runs-root', type=Path, default=default_runs()); s.add_argument('--profile', type=Path); s.add_argument('--creative-mandate', type=Path)
    s = sub.add_parser('collect'); s.add_argument('url', nargs='?'); s.add_argument('--output', required=True, type=Path); s.add_argument('--allow-local-fixture', action='store_true'); s.add_argument('--max-pages', type=int); s.add_argument('--frontier', type=Path)
    s = sub.add_parser('prepare-inputs'); s.add_argument('run_dir', type=Path); s.add_argument('manifest', type=Path); s.add_argument('--output', required=True, type=Path); s.add_argument('--timeout-seconds', type=float, default=5)
    s = sub.add_parser('preprocess'); s.add_argument('run_dir', type=Path); s.add_argument('--mode', choices=['auto','codex','cloudflare'])
    s = sub.add_parser('history'); s.add_argument('operation', choices=['collect','register','check']); s.add_argument('run_dir', type=Path); s.add_argument('--urls', nargs='*', default=[]); s.add_argument('--report', type=Path)
    s = sub.add_parser('discovery'); s.add_argument('operation', choices=['register','check','reconcile','channels']); s.add_argument('run_dir', type=Path); s.add_argument('--report', type=Path)
    for command in ('validate', 'receipt', 'workbench', 'next-stage', 'check-experience'):
        s = sub.add_parser(command); s.add_argument('run_dir', type=Path)
        if command == 'check-experience':
            s.add_argument('--stage', choices=['creative.direction','client.composition','export.documents','verify.final'], default='creative.direction')
            modes=s.add_mutually_exclusive_group()
            modes.add_argument('--inputs-only', action='store_true', help='Check current inputs and reading receipt before rendering candidates')
            modes.add_argument('--composition-plan-only', action='store_true', help='Check and register the deck plan/pilot before complete outputs exist')
    s = sub.add_parser('measure'); s.add_argument('run_dir', type=Path); s.add_argument('--quota-remaining-percent', type=float); s.add_argument('--quota-source')
    for command in ('source', 'fact', 'plan'):
        s = sub.add_parser(command); s.add_argument('run_dir', type=Path); s.add_argument('json_file', type=Path)
    s = sub.add_parser('artifact'); s.add_argument('run_dir', type=Path); s.add_argument('id'); s.add_argument('file'); s.add_argument('--audience', required=True, choices=['public','client','sales','technical','internal']); s.add_argument('--depends', nargs='*', default=[])
    s = sub.add_parser('evaluate'); s.add_argument('run_dir', type=Path); s.add_argument('requirement_id'); s.add_argument('json_file', type=Path)
    s = sub.add_parser('stage-review'); s.add_argument('run_dir', type=Path); s.add_argument('stage_id'); s.add_argument('json_file', type=Path)
    s = sub.add_parser('stage-report'); s.add_argument('run_dir', type=Path); s.add_argument('stage_id')
    s = sub.add_parser('packet'); s.add_argument('run_dir', type=Path); s.add_argument('--output', required=True, type=Path); s.add_argument('--files', required=True, nargs='+')
    s = sub.add_parser('context-packet'); s.add_argument('run_dir', type=Path); s.add_argument('--output', required=True, type=Path); s.add_argument('--files', required=True, nargs='+')
    s = sub.add_parser('export'); s.add_argument('source', type=Path); s.add_argument('output', type=Path); s.add_argument('--audience', choices=['client','sales','technical'], default='client')
    s = sub.add_parser('inspect'); s.add_argument('pdf', type=Path); s.add_argument('--output', type=Path, required=True); s.add_argument('--audience', choices=['client','sales','technical'], default='client'); s.add_argument('--max-pages', type=int)
    s = sub.add_parser('approve'); s.add_argument('run_dir', type=Path); s.add_argument('--plan-hash', required=True); s.add_argument('--actor', required=True); s.add_argument('--evidence', type=Path, required=True)
    s = sub.add_parser('publish'); s.add_argument('run_dir', type=Path); s.add_argument('--adapter', choices=['fixture'], required=True)
    s = sub.add_parser('upstream'); s.add_argument('operation', choices=['status','fetch']); s.add_argument('--family'); s.add_argument('--cache', type=Path)
    s = sub.add_parser('freeze-creatives'); s.add_argument('run_dir', type=Path); s.add_argument('selection', type=Path)
    s = sub.add_parser('check-creatives'); s.add_argument('run_dir', type=Path)
    s = sub.add_parser('layout'); s.add_argument('manifest', type=Path)
    return p


def execute(a):
    c = a.command
    if c == 'preprocess':
        from .preprocessing import prepare
        return prepare(a.run_dir,mode=a.mode)
    if c == 'discovery':
        from . import discovery_evidence
        if a.operation in ('register','reconcile'):
            if not a.report: raise ValueError('discovery register/reconcile requires --report')
            return getattr(discovery_evidence,a.operation)(a.run_dir, a.report)
        state.invalidate_changed(a.run_dir)
        inspect=discovery_evidence.inspect_channels if a.operation=='channels' else discovery_evidence.inspect_discovery
        return inspect(state.load_run(a.run_dir))
    if c in ('freeze-creatives', 'check-creatives'):
        from .preservation import freeze_creatives, inspect_preservation
        return freeze_creatives(a.run_dir, read_json(a.selection)) if c == 'freeze-creatives' else inspect_preservation(state.load_run(a.run_dir))
    if c == 'doctor': return doctor(check_presentations=a.presentations)
    if c == 'history':
        from . import history
        if a.operation == 'collect': return history.collect(a.run_dir,a.urls)
        if a.operation == 'register':
            if not a.report:raise ValueError('history register requires --report')
            return history.register(a.run_dir,a.report)
        state.invalidate_changed(a.run_dir)
        return history.inspect_history(state.load_run(a.run_dir))
    if c == 'prepare-inputs':
        from .recovery import prepare_inputs
        return prepare_inputs(a.run_dir, a.manifest, a.output, timeout_seconds=a.timeout_seconds)
    if c == 'layout':
        from .layout import assess_placements
        data = read_json(a.manifest)
        return assess_placements(data['placements'], data['pages'])
    if c == 'init':
        from .experience import read_mandate_input
        return state.init_run(a.url, a.runs_root, read_json(a.profile) if a.profile else None,
            creative_mandate=json.loads(read_mandate_input(a.creative_mandate)) if a.creative_mandate else None)
    if c == 'validate': return state.validate_run(a.run_dir)
    if c == 'next-stage': return state.next_stage(a.run_dir)
    if c == 'check-experience':
        from .experience import inspect_experience, inspect_creative_inputs
        state.invalidate_changed(a.run_dir)
        if a.inputs_only:return inspect_creative_inputs(state.load_run(a.run_dir))
        if a.composition_plan_only:
            from .composition import review_plan
            return review_plan(a.run_dir)
        return inspect_experience(state.load_run(a.run_dir), a.stage)
    if c == 'measure': return measure(a.run_dir, quota=a.quota_remaining_percent, source=a.quota_source)
    if c == 'workbench': return workbench(a.run_dir)
    if c == 'source':
        payload = read_json(a.json_file); identifier = payload.pop('id'); return state.add_source(a.run_dir, identifier, **payload)
    if c == 'fact':
        payload = read_json(a.json_file); identifier = payload.pop('id'); return state.add_fact(a.run_dir, identifier, **payload)
    if c == 'artifact': return state.add_artifact(a.run_dir, a.id, a.file, a.audience, a.depends)
    if c == 'evaluate': return state.record_evaluation(a.run_dir, a.requirement_id, read_json(a.json_file))
    if c == 'stage-review': return state.record_stage_review(a.run_dir, a.stage_id, read_json(a.json_file))
    if c == 'stage-report': return state.stage_report(a.run_dir, a.stage_id)
    if c == 'packet': return state.build_public_packet(a.run_dir, a.output, a.files)
    if c == 'context-packet': return state.build_context_packet(a.run_dir, a.output, a.files)
    if c == 'collect':
        from .discovery import collect, continue_collect
        if a.frontier:
            if a.url: raise ValueError('Use the prior report URL when continuing; do not supply a replacement URL')
            return continue_collect(a.frontier,a.output,allow_local=a.allow_local_fixture,max_pages=a.max_pages)
        if not a.url: raise ValueError('A URL or --frontier prior report is required')
        return collect(a.url, a.output, allow_local=a.allow_local_fixture, max_pages=a.max_pages)
    if c in ('export','inspect'):
        from .artifacts import export_pdf, inspect_pdf
        return export_pdf(a.source,a.output,audience=a.audience) if c == 'export' else inspect_pdf(a.pdf,a.output,audience=a.audience,max_pages=a.max_pages)
    if c in ('plan','approve','publish'):
        from .publication import prepare_plan, approve_plan, publish_plan, FixtureAdapter
        if c == 'plan': return prepare_plan(a.run_dir, read_json(a.json_file))
        if c == 'approve': return approve_plan(a.run_dir, a.plan_hash, a.actor, a.evidence)
        return publish_plan(a.run_dir, FixtureAdapter(a.run_dir / 'fixture-store.json'))
    if c == 'upstream':
        from . import upstream
        return upstream.fetch(family=a.family,cache=a.cache) if a.operation == 'fetch' else upstream.status(cache=a.cache)
    if c == 'receipt':
        run = state.load_run(a.run_dir); verdict = state.validate_run(a.run_dir)
        return {'run_id':run['id'], 'quality':verdict['status'], 'coverage':verdict['coverage'],
                'counts':{k:len(run[k]) for k in ('sources','facts','artifacts','evaluations','reviews')},
                'artifacts':{key:{k:item[k] for k in ('path','sha256','audience','status')} for key,item in run['artifacts'].items()},
                'stages':verdict.get('stages',{}), 'publication':verdict.get('publication'),
                'metrics':measure(a.run_dir), 'external_publication':'NOT_INFERRED_FROM_LOCAL_RECEIPT'}
    raise ValueError('Unsupported command')


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result = execute(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({'status':'ERROR','message':str(error)},ensure_ascii=False))
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 2 if str(result.get('status', '')).upper() in ('FAIL','BLOCKED','STALE','PARTIAL','UNAVAILABLE') else 0


if __name__ == '__main__':
    raise SystemExit(main())
