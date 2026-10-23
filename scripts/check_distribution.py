"""Check the selected public distribution; this is not a semantic privacy proof."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'skills/proposition/scripts'))


def check(root=ROOT):
    from jsonschema import Draft202012Validator
    result = subprocess.run(['git','ls-files','--cached','-z'],cwd=root,capture_output=True,check=True)
    files = [root/p for p in result.stdout.decode().split('\0') if p]
    if not files:
        return {'status':'BLOCKED','issues':['Git index is empty; select the actual distributable files first']}
    changed = subprocess.run(['git','diff','--name-only','--'],cwd=root,capture_output=True,check=True).stdout.decode().splitlines()
    if changed:
        return {'status':'FAIL','scope':'selected_git_files_and_structure_only',
                'files_checked':0,'issues':['Git index differs from working bytes: '+p for p in changed],
                'semantic_privacy_review':'REQUIRED_SEPARATELY'}
    issues = []
    for path in files:
        relative = path.relative_to(root)
        if path.is_symlink(): issues.append(f'Symlink: {relative}'); continue
        if any(part in {'runs','private','.venv','.codex','downloads','__pycache__'} for part in relative.parts):
            issues.append(f'Private/generated directory: {relative}')
        try: text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        secret = re.search(r'(?:sk-ant-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',text)
        if secret: issues.append(f'Possible secret: {relative}')
        personal_prefix = '/' + 'Users' + '/'
        if re.search(re.escape(personal_prefix) + r'[^/\s]+/|[A-Z]:\\Users\\[^\\\s]+\\',text):
            issues.append(f'Personal absolute path: {relative}')
        if path.suffix == '.md':
            for raw in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
                target = raw.split('#',1)[0].strip('<>')
                if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target): continue
                if not (path.parent / target).is_file(): issues.append(f'Missing local reference: {relative}: {target}')
    skill_files = sorted((root/'skills').glob('*/SKILL.md'))
    if len(skill_files) != 9: issues.append('Expected the nine first-party skills')
    for path in skill_files:
        content = path.read_text()
        if not content.startswith('---\n') or not re.search(r'^description: .+',content,re.M):
            issues.append(f'Missing skill frontmatter: {path.parent.name}')
    package = root/'skills/proposition/scripts/proposition_runtime'
    for path in (package/'contracts').glob('*.schema.json'):
        try: Draft202012Validator.check_schema(json.loads(path.read_text()))
        except Exception: issues.append(f'Invalid JSON schema: {path.name}')
    requirements = json.loads((package/'data/requirements.json').read_text())['requirements']
    if {r['id'] for r in requirements} != {f'R{i:02}' for i in range(1,82)} or len(requirements) != 81:
        issues.append('The requirement registry is incomplete')
    return {'status':'FAIL' if issues else 'PASS','scope':'selected_git_files_and_structure_only',
            'files_checked':len(files),'skills_checked':len(skill_files),'issues':issues,
            'semantic_privacy_review':'REQUIRED_SEPARATELY'}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
