"""Explicit local setup. Review this file before running an unfamiliar checkout."""
from pathlib import Path
import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv


STARTER_BEGIN='<!-- BEGIN VERTIGO PROPOSITION STARTER -->'
STARTER_END='<!-- END VERTIGO PROPOSITION STARTER -->'


def workspace_entry(workspace,host,update):
    path=workspace/('AGENTS.md' if host=='codex' else 'CLAUDE.md')
    if path.is_symlink() or (path.exists() and (not path.is_file() or path.stat().st_size>1024*1024)):
        raise ValueError('Workspace instructions must be a bounded regular file')
    previous=path.read_text() if path.exists() else ''
    skill='.agents/skills/proposition/SKILL.md' if host=='codex' else '.claude/skills/proposition/SKILL.md'
    block=(STARTER_BEGIN+'\n# VERTIGO propositions\n'
        'When a task gives the Vertigo Proposition repository URL followed by a prospect URL, '
        f'read `{skill}` and follow its installed contracts. The standard delivery is web; '
        'honor an explicit documents request when initializing a new run. '
        f'Read `.vertigo/setup-{host}.json` for the installed launcher (legacy fallback `.vertigo/setup.json`) and `.vertigo/profile.json` for private configuration. '
        'For a Codex workspace with native_observer.enabled, read the principal skill reference '
        '`references/native-startup.md` before init: the calling lane opens its own view; the identified native worker continues without recursive bootstrap. '
        'Keep runs outside the source checkout. Do not modify or push to the distribution repository.\n'+STARTER_END)
    if STARTER_BEGIN in previous or STARTER_END in previous:
        if previous.count(STARTER_BEGIN)!=1 or previous.count(STARTER_END)!=1:
            raise ValueError('Ambiguous managed workspace instructions')
        start=previous.index(STARTER_BEGIN);end=previous.index(STARTER_END)+len(STARTER_END)
        old=previous[start:end];receipt=workspace/('.vertigo/setup-'+host+'.json')
        expected=json.loads(receipt.read_text()).get('entrypoint_block_sha256') if receipt.is_file() and not receipt.is_symlink() else None
        if not update or hashlib.sha256(old.encode()).hexdigest()!=expected:
            raise ValueError('Managed workspace instructions were edited or are not owned by this installation')
        content=previous[:start]+block+previous[end:]
    else:
        content=previous+('\n\n' if previous else '')+block+'\n'
    return path,content,hashlib.sha256(block.encode()).hexdigest()


def write_private_json(path,data):
    descriptor,name=tempfile.mkstemp(prefix='.setup-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w') as stream:
            json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument('--dest', type=Path, help='Explicit skills destination; legacy default is ~/.codex/skills')
    target.add_argument('--workspace', type=Path, help='Own workspace: install into its .agents/skills, outside the source kit')
    parser.add_argument('--browser', action='store_true', help='Download the pinned Playwright Chromium build')
    parser.add_argument('--host',choices=['codex','claude'],default='codex')
    parser.add_argument('--delivery-format',choices=['web','documents'],default='web')
    parser.add_argument('--owner',help='Explicit invoking owner for the private workspace profile; never a client review approval')
    parser.add_argument('--with-publication',action='store_true',help='Explicit one-time creation and verification of isolated Vercel hosting support')
    parser.add_argument('--vercel-org',help='Optional Vercel organization; otherwise use the CLI selected organization')
    parser.add_argument('--vercel-credential-ref',help='Private credential reference: vercel_cli or env:VARIABLE; never a token value')
    parser.add_argument('--with-upstream', action='store_true', help='Fetch pinned open source skill distributions without executing them')
    parser.add_argument('--with-native-observer',action='store_true',help='Explicit Codex Desktop native transport and same-lane observer setup')
    parser.add_argument('--native-model');parser.add_argument('--native-effort',choices=['low','medium','high','xhigh','max','ultra'])
    parser.add_argument('--with-presentations', action='store_true', help='Install the locked python-pptx profile and test authoring, editing and rendering')
    parser.add_argument('--with-system-deps', action='store_true', help='Explicitly install Linux browser/LibreOffice packages; requires root, never invokes sudo')
    parser.add_argument('--update', action='store_true')
    a = parser.parse_args()
    if a.with_native_observer and (not a.workspace or a.host!='codex' or not a.native_model or not a.native_effort):
        parser.error('--with-native-observer requires a Codex workspace and explicitly selected --native-model / --native-effort')
    if (a.native_model or a.native_effort) and not a.with_native_observer:parser.error('Native model settings require --with-native-observer')
    if a.with_publication and (not a.workspace or not a.owner or a.delivery_format!='web'):
        parser.error('--with-publication requires a web workspace and its explicit --owner')
    if a.vercel_org and not a.with_publication:parser.error('--vercel-org requires --with-publication')
    if a.vercel_credential_ref and not a.with_publication:parser.error('--vercel-credential-ref requires --with-publication')
    if sys.version_info < (3,11): parser.error('Python 3.11 or newer is required')
    root = Path(__file__).resolve().parents[1]
    workspace = a.workspace.expanduser() if a.workspace else None
    if workspace:
        if workspace.is_symlink() or not workspace.is_dir():
            parser.error('--workspace must be an existing non-symlink directory')
        workspace = workspace.resolve()
        if workspace.is_relative_to(root):
            parser.error('The workspace must be outside the distribution checkout')
        host_folder='.agents' if a.host=='codex' else '.claude'
        for folder in (workspace/host_folder,workspace/host_folder/'skills',workspace/'.vertigo',
                       workspace/'.vertigo/setup.json',workspace/('.vertigo/setup-'+a.host+'.json'),workspace/'.vertigo/profile.json'):
            if folder.is_symlink():
                parser.error('Workspace installation directories cannot be symlinks')
    if a.host=='claude' and not workspace:parser.error('Claude installation requires an explicit project workspace')
    destination = (workspace/('.agents/skills' if a.host=='codex' else '.claude/skills') if workspace else
                   (a.dest or Path.home() / '.codex/skills').expanduser())
    if destination.resolve().is_relative_to(root):
        parser.error('Install skills outside the distribution checkout')
    if a.with_system_deps:
        if sys.platform != 'linux' or not hasattr(os, 'geteuid') or os.geteuid() != 0:
            parser.error('--with-system-deps requires an explicitly authorized root Linux setup; no automatic elevation')
        if not (a.browser or a.with_presentations):
            parser.error('--with-system-deps requires --browser or --with-presentations')
        if a.with_presentations and not shutil.which('apt-get'):
            parser.error('The explicit system presentation install requires apt-get; install a renderer separately')
    runtime = root / '.venv'
    if runtime.is_symlink(): parser.error('The local runtime cannot be a symlink')
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    launcher = destination.resolve() / 'proposition/scripts/proposition.py'
    report = {'status': 'BLOCKED', 'installation': 'NOT_COMPLETED', 'scope': 'installation_and_local_tools_only',
              'host':a.host,'delivery_format':a.delivery_format,'autonomous_delivery':'NOT_QUALIFIED',
              'source_checkout': str(root), 'skills_destination': str(destination.resolve()),
              'launcher': str(launcher), 'host_capabilities': 'NOT_VERIFIED_BY_INSTALLER',
              'prospect_e2e': 'NOT_RUN', 'profile': 'presentations' if a.with_presentations else 'core',
              'required_mcp': [], 'source_write_access_required': False}
    previous_setup=workspace/('.vertigo/setup-'+a.host+'.json') if workspace else None
    report['native_observer']=(json.loads(previous_setup.read_text()).get('native_observer',{'enabled':False})
        if a.update and previous_setup and previous_setup.is_file() else {'enabled':False})
    for key, revision in (('source_commit', 'HEAD'), ('source_tree', 'HEAD^{tree}')):
        try:
            resolved = subprocess.run(['git','-C',str(root),'rev-parse',revision],
                                      capture_output=True,text=True,check=True,timeout=5)
            report[key] = resolved.stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            report[key] = None
    try:
        changed = subprocess.run(['git','-C',str(root),'status','--porcelain'],
                                 capture_output=True,text=True,check=True,timeout=5)
        report['source_worktree_dirty'] = bool(changed.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        report['source_worktree_dirty'] = None
    phase = 'venv'
    try:
        entry=workspace_entry(workspace,a.host,a.update) if workspace else None
        if not python.is_file():
            venv.EnvBuilder(with_pip=not bool(shutil.which('uv')), symlinks=os.name != 'nt').create(runtime)
        phase = 'dependencies'
        lock = root / ('requirements-presentations.lock' if a.with_presentations else 'requirements.lock')
        if shutil.which('uv'):
            command = ['uv','pip','install','--python',str(python),'--require-hashes','-r',str(lock)]
        else:
            command = [str(python),'-m','pip','install','--require-hashes','-r',str(lock)]
        subprocess.run(command,check=True)
        phase = 'browser'
        if a.browser:
            command = [str(python),'-m','playwright','install']
            if a.with_system_deps: command.append('--with-deps')
            subprocess.run(command + (['chromium','webkit'] if a.delivery_format=='web' else ['chromium']),check=True)
        phase = 'presentation_renderer'
        if a.with_system_deps and a.with_presentations:
            subprocess.run(['apt-get','update'],check=True,timeout=600)
            subprocess.run(['apt-get','install','-y','--no-install-recommends',
                            'libreoffice-impress','fonts-dejavu-core'],check=True,timeout=900)
        phase = 'skills'
        command = [str(python),str(root/'scripts/install.py'),'--dest',str(destination),'--source',str(root)]
        if a.update: command.append('--update')
        subprocess.run(command,check=True)
        report['installation'] = 'INSTALLED'
        if workspace:
            phase='workspace_entrypoint'
            private=workspace/'.vertigo';private.mkdir(exist_ok=True)
            profile_path=private/'profile.json'
            profile=json.loads(profile_path.read_text()) if profile_path.is_file() else {
                'actor':None,'responsible':None,'responsible_confirmed':False,
                'required_reviewers':['review-a','review-b'],'parameters':{}}
            profile.setdefault('parameters',{})['delivery_format']=a.delivery_format
            if a.owner:
                profile.update(actor=a.owner,responsible=a.owner,responsible_confirmed=True)
            write_private_json(profile_path,profile)
            entry[0].write_text(entry[1]);report.update(entrypoint=str(entry[0]),entrypoint_block_sha256=entry[2],
                workspace_profile=str(profile_path),workspace_owner_configured=bool(profile.get('responsible_confirmed')))
        phase = 'upstream'
        if a.with_upstream:
            subprocess.run([str(python),str(launcher),'upstream','fetch'],check=True)
        if a.with_native_observer:
            phase='native_transport'
            checked=subprocess.run([str(python),str(launcher),'native','setup'],capture_output=True,text=True,check=True,timeout=210)
            transport=json.loads(checked.stdout)
            if transport.get('status')!='AVAILABLE':raise ValueError('Native transport installation is not confirmed')
            report['native_observer']={'enabled':True,'model':a.native_model,'effort':a.native_effort,
                'execution':'owned_app_server','scope':'production_execution_tree_not_separate_desktop_turn','transport':transport}
        if a.with_publication:
            phase='publication_setup'
            command=[str(python),str(launcher),'publication-setup',str(workspace),'--owner',a.owner]
            if a.vercel_org:command+=['--org',a.vercel_org]
            if a.vercel_credential_ref:command+=['--credential-ref',a.vercel_credential_ref]
            publication=subprocess.run(command,check=False,capture_output=True,text=True,timeout=180)
            report['publication']=json.loads(publication.stdout)
            if publication.returncode or report['publication'].get('status')!='READY':
                raise ValueError('Publication installation is not confirmed ready; keep its checkpoint, do not blindly retry')
        phase = 'doctor'
        command = [str(python),str(launcher),'doctor','--delivery-format',a.delivery_format]
        if a.with_presentations: command.append('--presentations')
        checked = subprocess.run(command,check=False,capture_output=True,text=True,timeout=150)
        report['doctor_exit'] = checked.returncode
        report['doctor'] = json.loads(checked.stdout)
        report['status'] = 'PASS' if checked.returncode == 0 and report['doctor']['status'] == 'PASS' else 'BLOCKED'
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        report['error'] = str(error)
    report['phase'] = phase
    report['checked_at'] = datetime.now(timezone.utc).isoformat()
    report['next'] = ('Verify remaining host capabilities; then publish the Cloud environment or reload local skills. '
                      'A fresh task receives only repository URL + website URL. Keep the source checkout for its runtime.')
    if workspace:
        receipt = workspace / '.vertigo/setup.json'
        receipt.parent.mkdir(exist_ok=True)
        receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2) + '\n')
        (workspace/('.vertigo/setup-'+a.host+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
