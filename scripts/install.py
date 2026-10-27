"""Install the complete skill folders without silently replacing local edits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_repo(source: Path, destination: Path, *, update: bool = False) -> dict:
    if Path(destination).is_symlink():
        raise ValueError('Refusing a symlink installation destination')
    source, destination = Path(source).resolve(), Path(destination).resolve()
    skills = sorted(p for p in (source / "skills").iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not skills or not any(p.name == "proposition" for p in skills):
        raise ValueError("Source has no complete proposition skill")
    inventory = {}
    for skill in skills:
        for path in sorted(skill.rglob("*")):
            if path.is_symlink():
                raise ValueError("Refusing a symlink in a distributable skill")
            if (path.is_file() and "__pycache__" not in path.parts
                    and not any(part.endswith('.egg-info') for part in path.parts)
                    and not path.name.endswith((".pyc", ".pyo"))):
                inventory[f"{skill.name}/{path.relative_to(skill).as_posix()}"] = digest(path)
    manifest_path = destination / ".proposition-install.json"
    if manifest_path.is_symlink():
        raise ValueError("Refusing a symlink installation manifest")
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if previous:
        for relative in previous.get('files', {}):
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('Invalid previous installation manifest')
    for skill in skills:
        target = destination / skill.name
        if target.is_symlink():
            raise ValueError('Refusing a symlink skill destination')
        if not target.exists():
            continue
        if not update or previous is None:
            raise ValueError(f"Existing skill {skill.name}; use --update for a managed installation")
        previous_files = {k: v for k, v in previous["files"].items() if k.startswith(skill.name + "/")}
        for relative, expected in previous_files.items():
            current = destination / relative
            if current.is_symlink() or not current.is_file() or digest(current) != expected:
                raise ValueError(f"Locally modified installation: {relative}")
        known = set(previous_files) | {f"{skill.name}/installation.json"}
        for current in target.rglob("*"):
            if current.is_file() and "__pycache__" not in current.parts:
                if current.relative_to(destination).as_posix() not in known:
                    raise ValueError(f"Locally modified installation: untracked {current.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="proposition-install-", dir=destination.parent))
    backup = Path(tempfile.mkdtemp(prefix='proposition-backup-', dir=destination.parent))
    moved_old, moved_new = [], []
    old_manifest = manifest_path.read_bytes() if manifest_path.exists() else None
    try:
        for relative in inventory:
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / "skills" / relative, target)
        config = {"runtime_python": sys.executable, "installation_version": 1}
        (staging / "proposition/installation.json").write_text(json.dumps(config, indent=2) + "\n")
        destination.mkdir(parents=True, exist_ok=True)
        # Backups are retained until every skill and the new manifest are durable.
        for skill in skills:
            target = destination / skill.name
            if target.exists():
                target.rename(backup / skill.name)
                moved_old.append(skill.name)
            shutil.move(str(staging / skill.name), target)
            moved_new.append(skill.name)
        manifest = {"version": 1, "files": inventory, "skills": [p.name for p in skills]}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    except BaseException:
        for name in moved_new:
            shutil.rmtree(destination / name, ignore_errors=True)
        for name in moved_old:
            (backup / name).rename(destination / name)
        if old_manifest is not None:
            manifest_path.write_bytes(old_manifest)
        elif manifest_path.exists():
            manifest_path.unlink()
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dest", required=True, type=Path, help="Explicit Codex skills directory")
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    try:
        result = install_repo(args.source, args.dest, update=args.update)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, f"Installation refused: {error}\n")
    print(json.dumps({"status": "INSTALLED", "skills": result["skills"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
