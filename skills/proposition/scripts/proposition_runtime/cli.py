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


def doctor(*, check_presentations=False, delivery_format='documents'):
    if delivery_format not in ('web','documents'):raise ValueError('Unknown delivery format')
    dependencies = {}
    for name in ('jsonschema', 'playwright', 'pypdf', 'pypdfium2', 'Pillow'):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    browser = {'status': 'UNAVAILABLE'}
    browsers={'chromium':browser}
    if delivery_format=='web':browsers['webkit']={'status':'UNAVAILABLE'}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            from .browser import launch_browser
            try:
                instance, channel = launch_browser(p)
                browser = {'status': 'AVAILABLE', 'version': instance.version, 'channel': channel}
                browsers['chromium']=browser
                instance.close()
            except Exception:
                pass
            if delivery_format=='web':
                try:
                    instance=p.webkit.launch(headless=True)
                    browsers['webkit']={'status':'AVAILABLE','version':instance.version}
                    instance.close()
                except Exception:
                    pass
    except ImportError:
        pass
    from . import presentation_probe
    presentation = presentation_probe.probe() if check_presentations else {
        'status': 'NOT_TESTED', 'tools': presentation_probe.inventory(), 'client_fidelity': 'NOT_RUN'}
    ready = all(dependencies.values()) and all(v['status']=='AVAILABLE' for v in browsers.values())
    if check_presentations: ready = ready and presentation['status'] == 'PASS'
    return {'status': 'PASS' if ready else 'BLOCKED',
            'scope': 'local_runtime_only', 'python': platform.python_version(), 'dependencies': dependencies,
            'browser': browser, 'browsers':browsers, 'delivery_format':delivery_format,
            'contracts': state.CONTRACT_ROOT.is_dir(), 'registry': state.DATA_ROOT.is_dir(),
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
    s=sub.add_parser('native');s.add_argument('operation',choices=['setup','context','prepare','serve','opened','status','stop','close-view'])
    s.add_argument('--workspace',type=Path);s.add_argument('--session',type=Path);s.add_argument('--receipt',type=Path)
    s.add_argument('--repo-url');s.add_argument('--site-url');s.add_argument('--model');s.add_argument('--effort');s.add_argument('--wait',type=float,default=0)
    doctor_parser = sub.add_parser('doctor')
    doctor_parser.add_argument('--presentations', action='store_true', help='Test a real local editable/rendered PPTX fixture')
    doctor_parser.add_argument('--delivery-format',choices=['web','documents'],default='documents')
    s=sub.add_parser('publication-setup');s.add_argument('workspace',type=Path)
    s.add_argument('--owner',required=True);s.add_argument('--org')
    s.add_argument('--credential-ref',default='vercel_cli',help='Private CLI login or env:VARIABLE reference, never an inline token')
    s = sub.add_parser('init'); s.add_argument('url'); s.add_argument('--runs-root', type=Path, default=default_runs()); s.add_argument('--profile', type=Path); s.add_argument('--creative-mandate', type=Path); s.add_argument('--audience-handoff-contract', type=int, choices=[1,2], default=2); s.add_argument('--execution-config', type=Path)
    s.add_argument('--delivery-format', choices=['web', 'documents'], help='Explicit format; omitted keeps the profile or legacy documents')
    s = sub.add_parser('collect'); s.add_argument('url', nargs='?'); s.add_argument('--output', required=True, type=Path); s.add_argument('--allow-local-fixture', action='store_true'); s.add_argument('--max-pages', type=int); s.add_argument('--frontier', type=Path)
    s.add_argument('--run-dir',type=Path)
    s.add_argument('--concurrency',type=int,choices=[1,2,4])
    s.add_argument('--proof-storage',choices=['expanded','content_addressed'])
    s.add_argument('--panel-scan',choices=['legacy','batch']);s.add_argument('--image-wait-policy',choices=['legacy','terminal_aware'])
    s = sub.add_parser('prepare-inputs'); s.add_argument('run_dir', type=Path); s.add_argument('manifest', type=Path); s.add_argument('--output', required=True, type=Path); s.add_argument('--timeout-seconds', type=float, default=5)
    s = sub.add_parser('preprocess'); s.add_argument('run_dir', type=Path); s.add_argument('--mode', choices=['auto','codex','cloudflare'])
    s = sub.add_parser('strategy'); s.add_argument('operation', choices=['prepare','register','check']); s.add_argument('run_dir', type=Path); s.add_argument('--report', type=Path); s.add_argument('--cache', type=Path); s.add_argument('--stage', choices=['analysis.specialists','company.v2','brief.public'],default='brief.public')
    s = sub.add_parser('history'); s.add_argument('operation', choices=['collect','register','check']); s.add_argument('run_dir', type=Path); s.add_argument('--urls', nargs='*', default=[]); s.add_argument('--report', type=Path)
    s = sub.add_parser('discovery'); s.add_argument('operation', choices=['register','supplement','scope','check','reconcile','channels','research-plan']); s.add_argument('run_dir', type=Path); s.add_argument('--report', type=Path)
    for command in ('validate', 'receipt', 'workbench', 'next-stage', 'check-experience'):
        s = sub.add_parser(command); s.add_argument('run_dir', type=Path)
        if command == 'check-experience':
            s.add_argument('--stage', choices=['creative.direction','client.composition','export.documents','verify.final'], default='creative.direction')
            modes=s.add_mutually_exclusive_group()
            modes.add_argument('--inputs-only', action='store_true', help='Check current inputs and reading receipt before rendering candidates')
            modes.add_argument('--composition-plan-only', action='store_true', help='Check and register the deck plan/pilot before complete outputs exist')
    s = sub.add_parser('measure'); s.add_argument('run_dir', type=Path); s.add_argument('--quota-remaining-percent', type=float); s.add_argument('--quota-source')
    s = sub.add_parser('metrics'); s.add_argument('run_dir', type=Path); s.add_argument('--format', choices=['json','markdown'], default='json')
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
    s = sub.add_parser('apply-batch'); s.add_argument('run_dir',type=Path);s.add_argument('batch',type=Path)
    s = sub.add_parser('ready-tasks');s.add_argument('run_dir',type=Path);s.add_argument('--capabilities',type=Path,required=True)
    s = sub.add_parser('claim-task');s.add_argument('run_dir',type=Path);s.add_argument('task_id');s.add_argument('--request',type=Path,required=True)
    s = sub.add_parser('task-event');s.add_argument('run_dir',type=Path);s.add_argument('event',type=Path)
    s = sub.add_parser('accept-task-result');s.add_argument('run_dir',type=Path);s.add_argument('result',type=Path)
    s = sub.add_parser('execution-status');s.add_argument('run_dir',type=Path)
    s = sub.add_parser('web');s.add_argument('operation',choices=['preflight','budget','release','media-index','plan','build','inspect','publish','verify']);s.add_argument('run_dir',type=Path)
    s.add_argument('--source',type=Path);s.add_argument('--plan',type=Path)
    s.add_argument('--output',type=Path,help='Run-local unchanged-film index destination; media-index only')
    s.add_argument('--supersedes',help='Exact predecessor SHA256 for an explicit experience-plan correction')
    s.add_argument('--reason',help='Reason for the experience-plan correction; no silent reselection')
    s.add_argument('--policy',type=Path,help='Private workspace publication policy; contains credential references only')
    s.add_argument('--browser',choices=['chromium','webkit'],action='append',help='Default: both engines; a partial probe does not qualify the missing engine')
    s.add_argument('--retry',action='store_true',help='Keep the previous inspection and create a new attempt')
    return p


def execute(a):
    from .validation import phase
    stable = a.command in ('validate','next-stage','stage-report','receipt') or (a.command=='strategy' and a.operation=='check')
    return phase(_execute)(a) if stable else _execute(a)


def _execute(a):
    c = a.command
    if c=='native':
        import os
        from . import native_session as native
        caller=os.environ.get('CODEX_THREAD_ID')
        if a.operation=='setup':
            from .native_setup import ensure_codex_cli
            return {'status':'AVAILABLE','executable':ensure_codex_cli(),'scope':'isolated_transport_not_host_qualification'}
        if a.operation in ('context','prepare'):
            if not a.workspace:raise ValueError('Native startup requires the installed workspace')
            if a.operation=='context':return {'status':'WORKER' if native.is_worker(a.workspace,caller) else 'LAUNCHER'}
            setup=native.workspace_setup(a.workspace);config=setup.get('native_observer',{})
            if not a.repo_url or not a.site_url:raise ValueError('Native preparation requires exactly the repository and prospect URLs')
            return native.prepare(a.workspace,a.repo_url+'\n'+a.site_url,
                model=a.model or config.get('model'),effort=a.effort or config.get('effort'),caller=caller)
        if not a.session:raise ValueError('Native operation requires its session path')
        if a.operation=='serve':return native.serve(a.session)
        if a.operation=='opened':
            if not a.receipt:raise ValueError('Actual panel-opening receipt is required')
            return native.register_open(a.session,a.receipt,caller)
        if a.operation=='status':return native.status(a.session,wait=a.wait)
        if a.operation=='stop':return native.request_stop(a.session,caller)
        if a.operation=='close-view':
            if read_json(a.session/'request.json')['owner_thread_id']!=caller:raise ValueError('View belongs to another lane')
            if not (a.session/'result.json').exists():raise ValueError('Do not close the view while execution is active')
            from .publication import write_json
            write_json(a.session/'close-view.json',{'requested':True});return {'status':'VIEW_CLOSE_REQUESTED'}
    if c=='publication-setup':
        from .web_setup import configure_publication
        result=configure_publication(a.workspace,a.owner,a.org,credential_ref=a.credential_ref)
        return {key:result[key] for key in ('status','phase','authority','project_name','project_id',
            'policy_path','per_run_target','prospect_publication') if key in result}
    if c == 'web':
        from . import web
        if a.operation=='preflight':
            from .web_publication import preflight_run
            if a.source or a.output or a.plan or a.browser or a.retry or a.supersedes or a.reason:
                raise ValueError('web preflight checks the installed policy only, without writes')
            return preflight_run(a.run_dir,a.policy)
        if a.operation=='plan':
            if not a.source or not a.plan or a.output or a.policy or a.browser or a.retry:
                raise ValueError('web plan requires --source and --plan before writing the homepage')
            return web.plan_run(a.run_dir,a.source,a.plan,supersedes=a.supersedes,reason=a.reason)
        if a.supersedes or a.reason:raise ValueError('Plan revision arguments belong to web plan only')
        if a.operation=='budget':
            from .web_timing import budget
            if a.source or a.output or a.plan or a.policy or a.browser or a.retry:
                raise ValueError('web budget is a read-only complete run clock')
            return budget(state.load_run(a.run_dir))
        if a.operation=='release':
            from .web_inputs import prepare_release
            if a.source or a.output or a.plan or a.policy or a.browser or a.retry:
                raise ValueError('web release uses the assessed canonical public input allowlist')
            row=prepare_release(a.run_dir)
            return {'status':'PREPARED','scope':'creative_inputs_only_not_external_publication',
                'authority':'verified_public_source_projection','path':row['path'],'sha256':row['sha256']}
        if a.operation=='media-index':
            if not a.source or not a.output or a.plan or a.policy or a.browser or a.retry:
                raise ValueError('web media-index requires only --source and --output within the run')
            run=state.load_run(a.run_dir);root=Path(run['root'])
            if state.delivery_format(run)!='web':raise ValueError('web media-index requires a web run')
            source=state._safe_path(root,a.source);output=state._safe_path(root,a.output,exists=False)
            return web.index_film(source,output)
        if a.output:raise ValueError('--output belongs to web media-index only')
        if a.operation in ('publish','verify'):
            from . import web_publication
            if a.source or a.plan or a.browser or a.retry:
                raise ValueError('Publication consumes the accepted registered build and browser checks')
            policy=a.policy or state.load_run(a.run_dir)['profile']['parameters'].get('publication_policy')
            if not policy:
                raise ValueError('The private workspace publication policy is not configured')
            result=(web_publication.publish_run if a.operation=='publish' else web_publication.verify_run)(a.run_dir,policy)
            return {key:result[key] for key in ('status','scope','url','build_id','run_id','authority','authentication_used','timing','delivery_status') if key in result}
        if a.operation=='build':
            if not a.source or not a.plan or a.browser or a.retry or a.policy:
                raise ValueError('web build requires --source and --plan; browser options belong to inspect')
            result=web.build_run(a.run_dir,a.source,a.plan)
            return {key:result[key] for key in ('status','scope','creative_quality','build_id','manifest_path','run_id') if key in result}
        if a.source or a.plan or a.policy:
            raise ValueError('web inspect consumes the registered exact build, not replacement inputs')
        result=web.inspect_run(a.run_dir,browsers=tuple(a.browser or ['chromium','webkit']),retry=a.retry)
        row=state.load_run(a.run_dir)['artifacts']['web-inspection']
        return {key:result[key] for key in ('status','scope','creative_quality','build_id','run_id')} | {
            'report_path':str(a.run_dir/row['path']), 'capture_count':len(result['captures']),
            'issue_count':len(result['issues']),'issues':result['issues'][:3]}
    if c in ('ready-tasks','claim-task','task-event','accept-task-result','execution-status'):
        from . import execution
        from .transactions import read_json as read_execution_json
        if c=='ready-tasks':return execution.ready_tasks(a.run_dir,read_execution_json(a.capabilities))
        if c=='claim-task':return execution.claim_task(a.run_dir,a.task_id,read_execution_json(a.request))
        if c=='task-event':return execution.task_event(a.run_dir,read_execution_json(a.event))
        if c=='accept-task-result':return execution.accept_task_result(a.run_dir,read_execution_json(a.result))
        return execution.execution_status(a.run_dir)
    if c=='apply-batch':
        from .transactions import apply_batch,read_json as read_execution_json
        return apply_batch(a.run_dir,read_execution_json(a.batch))
    if c == 'metrics':
        from .telemetry import metrics
        return metrics(a.run_dir)
    if c=='strategy':
        from . import strategy
        if a.operation=='prepare': return strategy.prepare(a.run_dir,a.cache)
        if a.operation=='register':
            if not a.report: raise ValueError('strategy register requires --report')
            return strategy.register(a.run_dir,a.report)
        state.invalidate_changed(a.run_dir)
        return strategy.inspect(state.load_run(a.run_dir),a.stage)
    if c == 'preprocess':
        from .preprocessing import prepare
        return prepare(a.run_dir,mode=a.mode)
    if c == 'discovery':
        if a.operation=='research-plan':
            from .public_research import prepare
            return prepare(a.run_dir)
        from . import discovery_evidence
        if a.operation in ('register','reconcile','scope','supplement'):
            if not a.report: raise ValueError('discovery register/reconcile requires --report')
            method={'scope':'register_scope','supplement':'register_supplement'}.get(a.operation,a.operation)
            return getattr(discovery_evidence,method)(a.run_dir, a.report)
        state.invalidate_changed(a.run_dir)
        inspect=discovery_evidence.inspect_channels if a.operation=='channels' else discovery_evidence.inspect_discovery
        return inspect(state.load_run(a.run_dir))
    if c in ('freeze-creatives', 'check-creatives'):
        from .preservation import freeze_creatives, inspect_preservation
        return freeze_creatives(a.run_dir, read_json(a.selection)) if c == 'freeze-creatives' else inspect_preservation(state.load_run(a.run_dir))
    if c == 'doctor': return doctor(check_presentations=a.presentations,delivery_format=a.delivery_format)
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
            creative_mandate=json.loads(read_mandate_input(a.creative_mandate)) if a.creative_mandate else None,
            audience_handoff_contract=a.audience_handoff_contract,
            execution_config=read_json(a.execution_config) if a.execution_config else None,
            delivery_format=a.delivery_format)
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
        from .transactions import execution_metadata
        config={'concurrency':1,'panel_scan':'legacy','image_wait_policy':'legacy','proof_storage':'expanded'}
        excluded=None
        if a.run_dir:
            run=state.load_run(a.run_dir);config.update({k:v for k,v in execution_metadata(run)['config'].items() if k in config})
            source=read_json(a.frontier)['input_url'] if a.frontier else a.url
            if source!=run['url']:raise ValueError('Collection must use the run URL')
            state._safe_path(Path(run['root']),str(a.output.absolute().relative_to(Path(run['root']))),exists=False)
            from .discovery_evidence import current_exclusions
            excluded=list(current_exclusions(run))
        config={k:getattr(a,k) if getattr(a,k) is not None else v for k,v in config.items()}
        if a.frontier:
            if a.url: raise ValueError('Use the prior report URL when continuing; do not supply a replacement URL')
            return continue_collect(a.frontier,a.output,allow_local=a.allow_local_fixture,max_pages=a.max_pages,excluded_urls=excluded,**config)
        if not a.url: raise ValueError('A URL or --frontier prior report is required')
        return collect(a.url, a.output, allow_local=a.allow_local_fixture, max_pages=a.max_pages,excluded_urls=excluded,**config)
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
        if getattr(args,'run_dir',None) is not None and args.command not in ('metrics','ready-tasks','execution-status'):
            from .telemetry import TraceRecorder
            with TraceRecorder(args.run_dir) as trace:
                with trace.span('cli.command', command=args.command,**({'operation':args.operation} if hasattr(args,'operation') else {})) as observation:
                    result = execute(args)
                    if isinstance(result,dict) and isinstance(result.get('status'),str):observation['business_status']=result['status'].upper()
        else:
            result = execute(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        if args.command in ('apply-batch','ready-tasks','claim-task','task-event','accept-task-result','execution-status') and getattr(error,'code',None) in (3,4):
            print(json.dumps({'status':{3:'CONFLICT',4:'BUSY'}[error.code],'message':str(error)},ensure_ascii=False))
            return error.code
        print(json.dumps({'status':'ERROR','message':str(error)},ensure_ascii=False))
        return 1
    if args.command == 'metrics' and args.format == 'markdown':
        print('# Mesures locales\n\nCouverture : '+result['coverage']+'\n\nTemps hôte et tokens : inconnus.\n\n```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```')
    else:
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    if args.command=='ready-tasks':return 0
    if args.command in ('claim-task','task-event','accept-task-result'):
        if result.get('status')=='UNKNOWN_OUTCOME':return 5
        if result.get('status')=='REJECTED_STALE':return 3
    if args.command in ('web','publication-setup') and result.get('status')=='UNKNOWN_OUTCOME':return 5
    return 2 if str(result.get('status', '')).upper() in ('FAIL','BLOCKED','STALE','PARTIAL','UNAVAILABLE') else 0


if __name__ == '__main__':
    raise SystemExit(main())
