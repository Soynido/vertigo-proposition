"""Explicit active static bundles. Mechanical integrity is never creative approval."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import math
from urllib.parse import unquote, urlsplit

ALLOWED = {'.html', '.css', '.js', '.mjs', '.svg', '.png', '.jpg', '.jpeg',
           '.webp', '.avif', '.gif', '.mp4', '.webm', '.woff', '.woff2', '.json', '.txt'}
PRIVATE = {'state.json', 'profile.json', 'credentials.json', 'setup.json',
           'manifest.json', 'bundle.json', 'vertigo-build.json'}
MAX_FILES = 2048
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_BUNDLE_BYTES = 256 * 1024 * 1024


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or ':' in value
            or '%' in value or value.startswith('/')
            or any(part in ('', '.', '..') or part.startswith('.')
                   for part in value.split('/'))):
        raise ValueError('Public web paths must be relative, portable and non-hidden')
    if PurePosixPath(value).name.lower() in PRIVATE:
        raise ValueError('Private run metadata cannot enter a public bundle')
    if PurePosixPath(value).suffix.lower() not in ALLOWED:
        raise ValueError('Unsupported public web file type')
    return value


def _source_file(root, name):
    path = root / _relative(name)
    if (any(part.is_symlink() for part in [path, *path.parents]
            if part == root or root in part.parents)
            or not path.is_file() or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError('Missing or symlinked public web file: '+name)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('Public web file exceeds the bounded file budget')
    return path


def _resource(value, parent, public_files, *, navigation=False):
    value = value.strip()
    if not value or value.startswith('#'):
        return
    parsed = urlsplit(value)
    if navigation and parsed.scheme in ('https', 'http', 'mailto', 'tel'):
        return
    if value.startswith('data:') and not navigation:
        if not value.startswith(('data:image/', 'data:font/', 'data:application/font')):
            raise ValueError('Unsupported embedded resource')
        return
    if parsed.scheme or parsed.netloc:
        raise ValueError('Critical resources must be bundled, not remote: '+value)
    raw = unquote(parsed.path)
    parts = [] if raw.startswith('/') else list(PurePosixPath(parent).parent.parts)
    for part in raw.lstrip('/').split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if not parts:
                raise ValueError('Resource leaves the public bundle')
            parts.pop()
        else:
            parts.append(part)
    name = '/'.join(parts)
    if name not in public_files:
        raise ValueError('Required resource is absent from the public allowlist: '+name)


class _Resources(HTMLParser):
    def __init__(self, name, public_files):
        super().__init__()
        self.name, self.public_files = name, public_files

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'base':
            raise ValueError('A public bundle must not replace its base origin')
        for key in ('src', 'poster', 'data'):
            if attrs.get(key):
                _resource(attrs[key], self.name, self.public_files)
        if tag == 'link' and attrs.get('href'):
            _resource(attrs['href'], self.name, self.public_files)
        if tag == 'a' and attrs.get('href'):
            _resource(attrs['href'], self.name, self.public_files, navigation=True)
        if attrs.get('srcset'):
            for item in attrs['srcset'].split(','):
                _resource(item.strip().split()[0], self.name, self.public_files)


def _check_resources(source, names):
    for name in names:
        suffix = PurePosixPath(name).suffix.lower()
        if suffix == '.html':
            _Resources(name, names).feed((source/name).read_text(encoding='utf-8'))
        elif suffix == '.css':
            text = (source/name).read_text(encoding='utf-8')
            for match in re.finditer(r'url\(\s*[\'\"]?([^\)\'\"]+)', text):
                _resource(match.group(1), name, names)
            for match in re.finditer(r'@import\s+[\'\"]([^\'\"]+)', text):
                _resource(match.group(1), name, names)
        elif name.endswith(('.mp4.frames.json','.webm.frames.json')):
            film=name.removesuffix('.frames.json')
            index=json.loads((source/name).read_text())
            if film not in names or index.get('sha256') != _sha(_source_file(source,film)):
                raise ValueError('A frame index must match the exact bundled film')


def build_bundle(source, destination, plan):
    """Copy an explicit public tree atomically; never interpret this as a quality gate."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('Source must be an existing non-symlink directory')
    if destination.exists() or destination.is_symlink():
        raise ValueError('Web build exists; never overwrite frozen bytes')
    if plan.get('version') != 1:
        raise ValueError('Unsupported web plan version')
    if plan.get('entrypoint')!='index.html':
        raise ValueError('The delivered deployment root must serve index.html')
    names = plan.get('public_files')
    if (not isinstance(names, list) or not names or len(names) > MAX_FILES
            or len(set(names)) != len(names)):
        raise ValueError('An explicit unique bounded public file list is required')
    for field in ('entrypoint', 'sources_page'):
        if plan.get(field) not in names or not plan[field].endswith('.html'):
            raise ValueError('Entry and sources page must be public HTML files')
    files = [(name, _source_file(source, name)) for name in sorted(names)]
    if sum(path.stat().st_size for _, path in files) > MAX_BUNDLE_BYTES:
        raise ValueError('Web bundle exceeds the bounded byte budget')
    _check_resources(source, set(names))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.web-build-', dir=destination.parent))
    try:
        public = temporary/'.vercel/output/static'
        public.mkdir(parents=True)
        rows = []
        for name, file in files:
            fingerprint = (file.stat().st_ino, file.stat().st_size, file.stat().st_mtime_ns)
            digest = _sha(file)
            target = public/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(file, target)
            if (_sha(target) != digest or _sha(file) != digest
                    or fingerprint != (file.stat().st_ino, file.stat().st_size, file.stat().st_mtime_ns)):
                raise ValueError('Public source changed during the build')
            rows.append({'path':'.vercel/output/static/'+name,
                         'sha256':digest, 'size_bytes':target.stat().st_size})
        config = temporary/'.vercel/output/config.json'
        config.write_bytes(_canonical({'version':3}))
        rows.append({'path':'.vercel/output/config.json', 'sha256':_sha(config),
                     'size_bytes':config.stat().st_size})
        body = {'version':1, 'entrypoint':plan['entrypoint'],
                'sources_page':plan['sources_page'], 'files':rows,
                'plan_sha256':hashlib.sha256(_canonical(plan)).hexdigest()}
        build_id = hashlib.sha256(_canonical(body)).hexdigest()
        manifest = dict(body, build_id=build_id)
        (public/'vertigo-build.json').write_bytes(_canonical({'version':1,'build_id':build_id}))
        (temporary/'bundle.json').write_bytes(_canonical(manifest))
        os.rename(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return dict(manifest, status='PASS', scope='static_build_only',
                creative_quality='NOT_ASSESSED', manifest_path=str(destination/'bundle.json'))


def verify_bundle(directory):
    """Check every frozen byte and reject extra served files."""
    directory = Path(directory)
    manifest = json.loads((directory/'bundle.json').read_text())
    body = {key:value for key,value in manifest.items() if key != 'build_id'}
    if hashlib.sha256(_canonical(body)).hexdigest() != manifest['build_id']:
        raise ValueError('Web manifest identity changed')
    expected = set()
    for row in manifest['files']:
        path = directory/row['path']
        if (not path.is_file() or path.is_symlink()
                or not path.resolve().is_relative_to(directory.resolve())
                or path.stat().st_size != row['size_bytes'] or _sha(path) != row['sha256']):
            raise ValueError('Frozen web file changed: '+row['path'])
        expected.add(row['path'])
    marker = '.vercel/output/static/vertigo-build.json'
    if json.loads((directory/marker).read_text()) != {'version':1,'build_id':manifest['build_id']}:
        raise ValueError('Public build marker changed')
    expected.add(marker)
    actual = {p.relative_to(directory).as_posix()
              for p in (directory/'.vercel/output').rglob('*') if p.is_file() or p.is_symlink()}
    if actual != expected:
        raise ValueError('Unexpected files in the served web tree')
    return dict(manifest, status='PASS', scope='frozen_web_bytes_only', creative_quality='NOT_ASSESSED')


def validate_plan(run, plan, source):
    """Bind the active experience to existing analysis and actual pre-selection evidence."""
    from . import state
    from .composition import _current, _public_proof, commercial_details
    from .preservation import _selection
    from .experience import inspect_experience, _text
    state._schema('web-plan',plan)
    for rows in ('coverage','scenes','actions','controls'):
        for row in plan.get(rows,[]):
            page=row.get('page',plan['entrypoint'])
            if page not in plan['public_files'] or PurePosixPath(page).suffix.lower() not in ('.html','.htm'):
                raise ValueError('Every inspected scene, function, control and action needs a public HTML page')
    if state.delivery_format(run) != 'web' or run.get('metadata', {}).get('web_contract') != 1:
        raise ValueError('This operation requires an initialized web run')
    inputs_row, inputs_path = _current(run, 'artifact:creative-inputs')
    locked=_selection(run)
    if (plan.get('inputs_sha256') != inputs_row['sha256']
            or plan.get('selection_sha256') != run['metadata']['creative_selection']['sha256']):
        raise ValueError('Web plan does not bind the current brief and frozen selection')
    experience = inspect_experience(run, 'creative.direction')
    if experience['status'] != 'PASS':
        raise ValueError('Creative evidence is incomplete: '+'; '.join(experience['issues']))
    coverage = plan.get('coverage', [])
    if len(coverage) != 8 or {r.get('id') for r in coverage} != {f'K{i:02}' for i in range(1,9)}:
        raise ValueError('Web narrative must cover K01-K08, not eight imposed sections')
    dependencies = {'artifact:creative-inputs', 'artifact:creative-experience',
                    'artifact:creative-exploration', 'artifact:creative-reading'}
    for row in coverage:
        _text(row.get('selector'), 'actual rendered commercial selector')
        _text(row.get('meaning'), 'commercial meaning')
        if row.get('claim_status') not in ('observed','declared','proposed','estimate','unknown'):
            raise ValueError('A web claim needs an honest evidence status')
        if not row.get('proofs'):
            raise ValueError('Every commercial function requires current public proof')
        for reference in row['proofs']:
            _public_proof(run, reference)
            dependencies.add(reference)
    dependencies.update(commercial_details(run,{r['id']:r for r in coverage}))
    scenes = plan.get('scenes', [])
    if not scenes or len({s['id'] for s in scenes}) != len(scenes):
        raise ValueError('Web scenes need distinct identities')
    retained={r['id'] for r in locked['retained']};transposed=set()
    for scene in scenes:
        state._identifier(scene['id'])
        for field in ('selector', 'meaning', 'mobile', 'reduced_motion'):
            _text(scene.get(field), 'scene '+field)
        _text(scene.get('interaction'),'actual scene interaction')
        intent_ids=scene.get('intent_ids')
        if (not isinstance(intent_ids,list) or not set(intent_ids).issubset(retained)
                or (scene.get('purpose','prospect')=='prospect' and not intent_ids)):
            raise ValueError('Every prospect scene must identify its frozen visual intentions')
        transposed.update(intent_ids)
        media_paths=scene.get('media_paths')
        if not isinstance(media_paths,list) or not set(media_paths).issubset(plan['public_files']):
            raise ValueError('Scene media must identify the actual public files')
        positions = scene.get('states')
        if (not isinstance(positions, list) or len(positions) < 3 or positions[0] != 0 or positions[-1] != 1
                or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in positions)
                or any(a >= b for a,b in zip(positions, positions[1:]))):
            raise ValueError('Scene inspection needs ordered beginning/intermediate/end states')
    if transposed!=retained:
        raise ValueError('A frozen visual intention was omitted from the active experience plan')
    engine=plan.get('engine',{})
    if engine.get('kind') not in ('portable','custom'):
        raise ValueError('The web plan must identify its actual motion mechanism')
    _text(engine.get('rationale'),'engine adaptation or specific mechanism rationale')
    if not engine.get('files') or any(name not in plan['public_files'] or PurePosixPath(name).suffix not in ('.mjs','.js','.css') for name in engine['files']):
        raise ValueError('The mechanism must identify the actual bundled code')
    if engine['kind']=='portable':
        modules=engine.get('source_modules')
        if not isinstance(modules,list) or not modules:
            raise ValueError('A portable engine needs the received resource identities')
        kit=Path(__file__).parents[2]/'resources/web'
        for module in modules:
            file=_source_file(kit,module['resource'])
            if _sha(file)!=module['sha256']:
                raise ValueError('The portable engine source differs from its installed version')
    inputs = json.loads(inputs_path.read_text())
    actions = plan.get('actions', [])
    prospect = {a['id']:a for a in actions if a.get('purpose') == 'prospect'}
    for expected in inputs['actions']:
        actual = prospect.get(expected['id'])
        if not actual or actual['target'] != expected['target']:
            raise ValueError('The web proposal must retain the evidenced prospect action target')
    if not any(a.get('purpose') == 'vertigo' for a in actions):
        raise ValueError('A separate commercial decision for Vertigo must be inspectable')
    for action in actions:
        _text(action.get('selector'), 'action selector')
        _text(action.get('target'), 'action target')
        if action.get('purpose') not in ('prospect', 'vertigo'):
            raise ValueError('Action purpose must distinguish prospect and Vertigo')
    media = plan.get('media', [])
    declared = set()
    for item in media:
        name = _relative(item['path'])
        if name in declared or name not in plan['public_files']:
            raise ValueError('Media must be unique and explicitly public')
        declared.add(name)
        if item.get('kind') not in ('authentic', 'transformed', 'generated', 'illustration', 'studio'):
            raise ValueError('Media provenance kind is required')
        if item.get('rights') not in ('allowed', 'unknown', 'restricted'):
            raise ValueError('Media diffusion rights must be explicit')
        _text(item.get('changes'), 'media transformation description')
        reference = item['source_ref']
        record = state._resolve(run, reference)
        if (not record or state._stale_reasons(run, Path(run['root']), record)
                or record.get('audience') not in ('public', 'client') or record.get('kind') == 'private'):
            raise ValueError('Private, missing or stale media source')
        dependencies.add(reference)
    media_suffixes = {'.svg','.png','.jpg','.jpeg','.webp','.avif','.gif','.mp4','.webm'}
    if any(PurePosixPath(n).suffix.lower() in media_suffixes and n not in declared for n in plan['public_files']):
        raise ValueError('Every published image or video needs provenance and rights metadata')
    return sorted(dependencies)


def _register(run_dir, identifier, path, dependencies):
    from . import state
    run = state.load_run(run_dir)
    row = state._artifact_record(run, identifier, path, 'internal', dependencies, reuse_current=True)
    run['artifacts'][identifier] = row
    state.save_run(run_dir, run)
    return row


def plan_run(run_dir,source_dir,plan_path,*,supersedes=None,reason=None):
    """Freeze intent before the first homepage; keep explicit correction history."""
    from . import state
    from .web_timing import require_time
    run=state.load_run(run_dir);root=Path(run['root']);require_time(run)
    source=state._safe_path(root,source_dir,exists=False)
    path=state._safe_path(root,plan_path)
    if path.stat().st_size>4*1024*1024:raise ValueError('Experience plan exceeds its bounded input budget')
    content=path.read_bytes();plan=json.loads(content);digest=hashlib.sha256(content).hexdigest()
    dependencies=validate_plan(run,plan,source)
    previous=run['metadata'].get('web_plan')
    if previous and previous['sha256']==digest:
        if previous['source_directory']!=source.relative_to(root).as_posix():
            raise ValueError('Reserved web source destination cannot change')
        from .composition import _current
        row,_=_current(run,'artifact:web-plan')
        return {'status':'PREPARED','scope':'pre-development_intent_not_client_quality','sha256':row['sha256'],'path':row['path']}
    if previous:
        if (supersedes!=previous['sha256'] or not isinstance(reason,str) or not reason.strip()
                or previous['source_directory']!=source.relative_to(root).as_posix()):
            raise ValueError('A plan correction needs its exact predecessor, reason and reserved destination')
    elif supersedes or reason or (source/plan['entrypoint']).exists():
        raise ValueError('Register the first experience plan before writing the homepage')
    frozen=state._safe_path(root,'web/plans/'+digest+'/plan.json',exists=False)
    frozen.parent.mkdir(parents=True,exist_ok=True)
    if not frozen.exists():
        with frozen.open('xb') as stream:stream.write(content)
    if _sha(frozen)!=digest or _sha(path)!=digest:raise ValueError('Experience plan changed while freezing')
    current=state.load_run(root);validate_plan(current,plan,source)
    if current['metadata'].get('web_plan')!=previous:raise ValueError('Experience plan changed concurrently')
    if current['artifacts'].get('public-input-release',{}).get('status')=='CURRENT':
        dependencies=sorted(set(dependencies)|{'artifact:public-input-release'})
    row=state._artifact_record(current,'web-plan',frozen,'internal',dependencies,reuse_current=True)
    current['artifacts']['web-plan']=row
    current['metadata']['web_plan']={'sha256':digest,'path':row['path'],
        'source_directory':source.relative_to(root).as_posix(),'draft_path':path.relative_to(root).as_posix(),
        'prepared_at':state._now(),'parent_sha256':previous['sha256'] if previous else None,'reason':reason}
    state.save_run(root,current)
    return {'status':'PREPARED','scope':'pre-development_intent_not_client_quality','sha256':digest,'path':row['path']}


def build_run(run_dir, source_dir, plan_path):
    from . import state
    run = state.load_run(run_dir)
    root = Path(run['root'])
    source = state._safe_path(root, source_dir, exists=False)
    if not source.is_dir():
        raise ValueError('Web source directory is missing')
    path = state._safe_path(root, plan_path)
    plan = json.loads(path.read_text())
    dependencies = validate_plan(run, plan, source)
    prepared=run['metadata'].get('web_plan')
    if (not prepared or prepared['sha256']!=_sha(path)
            or prepared['source_directory']!=source.relative_to(root).as_posix()):
        raise ValueError('A current pre-development experience plan is required before building')
    from .composition import _current
    plan_row, frozen_plan=_current(run,'artifact:web-plan')
    if plan_row['sha256']!=prepared['sha256']:raise ValueError('The frozen experience plan differs from its receipt')
    names = plan.get('public_files', [])
    source_files = [{'path':n,'sha256':_sha(_source_file(source,n))} for n in sorted(names)]
    key = hashlib.sha256(_canonical([plan, source_files])).hexdigest()
    directory = state._safe_path(root, 'web/bundles/'+key, exists=False)
    if directory.exists():
        result = verify_bundle(directory)
    else:
        result = build_bundle(source, directory, plan)
    # Recheck the actual consumed source identities before binding the receipt.
    if source_files != [{'path':n,'sha256':_sha(_source_file(source,n))} for n in sorted(names)]:
        raise ValueError('Public source changed before receipt adoption')
    validate_plan(state.load_run(root), json.loads(path.read_text()), source)
    if hashlib.sha256(_canonical(json.loads(path.read_text()))).hexdigest() != result['plan_sha256']:
        raise ValueError('Web plan changed during the build')
    _register(root, 'web-build', directory/'bundle.json', ['artifact:web-plan'])
    _register(root, 'web-sources', source/plan['sources_page'], ['artifact:web-plan'])
    current = state.load_run(root)
    current['metadata']['web_build'] = {'directory':directory.relative_to(root).as_posix(),
        'source_directory':source.relative_to(root).as_posix(),
        'plan_path':frozen_plan.relative_to(root).as_posix(),
        'source_plan_path':path.relative_to(root).as_posix(),'source_plan_sha256':_sha(path), 'source_files':source_files,
        'build_id':result['build_id']}
    state.save_run(root, current)
    return dict(result, run_id=run['id'], creative_quality='NOT_ASSESSED')


def current_build(run):
    from . import state
    from .composition import _current
    metadata = run.get('metadata', {}).get('web_build')
    if not metadata:
        raise ValueError('No current web build')
    row, path = _current(run, 'artifact:web-build')
    root = Path(run['root'])
    directory = state._safe_path(root, metadata['directory'], exists=False)
    if path != directory/'bundle.json':
        raise ValueError('Web build receipt points to a different bundle')
    result = verify_bundle(directory)
    if result['build_id'] != metadata['build_id']:
        raise ValueError('Web build identity does not match this run')
    source = state._safe_path(root, metadata['source_directory'], exists=False)
    if _sha(state._safe_path(root,metadata['source_plan_path']))!=metadata['source_plan_sha256']:
        raise ValueError('Source experience plan changed after the accepted build')
    for file in metadata['source_files']:
        if _sha(_source_file(source, file['path'])) != file['sha256']:
            raise ValueError('Web source changed since the accepted build')
    plan_row, plan_path = _current(run, 'artifact:web-plan')
    plan = json.loads(plan_path.read_text())
    if hashlib.sha256(_canonical(plan)).hexdigest() != result['plan_sha256']:
        raise ValueError('Web plan no longer matches the frozen bundle')
    validate_plan(run, plan, source)
    return directory, result, plan


def inspect_bundle(*args, **kwargs):
    from .web_inspection import inspect_bundle as inspect_actual_bundle
    return inspect_actual_bundle(*args, **kwargs)


def index_film(*args, **kwargs):
    from .web_media import index_film as prepare_unchanged_film
    return prepare_unchanged_film(*args, **kwargs)


def _inspection_runtime():
    return {'binding_sha256':_sha(Path(__file__)),
            'inspector_sha256':_sha(Path(__file__).with_name('web_inspection.py'))}


def _check_inspection(root, path, build_id):
    from . import state
    path = state._safe_path(root, path)
    report = json.loads(path.read_text())
    if (report.get('build_id') != build_id or report.get('runtime') != _inspection_runtime()
            or report.get('scope') != 'observed_browser_mechanics_only'
            or report.get('status') not in ('PASS','BLOCKED')
            or (report.get('status')=='PASS' and not report.get('captures'))):
        raise ValueError('Inspection does not bind the current build and inspector')
    for row in report['captures']:
        file = _source_file(path.parent, row['path'])
        if (_sha(file) != row['sha256'] or row['actual_viewport'] != row['viewport']):
            raise ValueError('Inspection capture changed or has the wrong actual viewport')
    return report


def inspect_run(run_dir, *, browsers=('chromium','webkit'),
                viewports=((1440,900),(1280,600),(390,844)), retry=False):
    """Inspect immutable bytes, preserve prior receipts, and register no aesthetic verdict."""
    from . import state
    run = state.load_run(run_dir)
    root = Path(run['root'])
    directory, manifest, plan = current_build(run)
    request = {'browsers':list(browsers),'viewports':[list(v) for v in viewports]}
    runtime = _inspection_runtime()
    key = hashlib.sha256(_canonical([manifest['build_id'],request,runtime])).hexdigest()
    destination = state._safe_path(root, 'web/inspections/'+key, exists=False)
    if retry:
        attempt = 1
        while destination.exists():
            attempt += 1
            destination = state._safe_path(root, 'web/inspections/'+key+'-'+str(attempt), exists=False)
    if destination.exists():
        result = _check_inspection(root, destination/'report.json', manifest['build_id'])
        if result.get('request') != request:
            raise ValueError('Existing inspection used a different request')
    else:
        result = inspect_bundle(directory,plan,destination,browsers=browsers,viewports=viewports)
        result.update(request=request,runtime=runtime,run_id=run['id'])
        (destination/'report.json').write_bytes(_canonical(result))
        _check_inspection(root,destination/'report.json',manifest['build_id'])
    # A changed source, selection or build while the browser was running is not adopted.
    current_directory, current, _ = current_build(state.load_run(root))
    if current['build_id'] != manifest['build_id'] or current_directory != directory:
        raise ValueError('The web build changed during inspection')
    _register(root,'web-inspection',destination/'report.json',['artifact:web-build'])
    return result


def current_inspection(run):
    from .composition import _current
    _, manifest, _ = current_build(run)
    _, path = _current(run,'artifact:web-inspection')
    return _check_inspection(Path(run['root']),path,manifest['build_id'])


def inspect_delivery(run):
    try:
        current_build(run)
        report=current_inspection(run)
        if (report['status']!='PASS' or set(report['request']['browsers'])!={'chromium','webkit'}
                or not {(1440,900),(1280,600),(390,844)}.issubset({tuple(v) for v in report['request']['viewports']})):
            raise ValueError('The exact web build needs both engines, desktop/mobile sizes and reduced-motion checks')
        return {'status':'PASS','scope':'web_evidence_consistency_only',
                'creative_quality':'REQUIRES_EXACT_ISOLATED_REVIEWS','issues':[]}
    except (ValueError,OSError,KeyError,TypeError) as error:
        return {'status':'BLOCKED','scope':'web_evidence_consistency_only','issues':[str(error)]}
