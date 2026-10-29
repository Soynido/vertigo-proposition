"""Read-only continuity check for the existing private capability matrix.

This checks accounting and evidence bytes, never the truth of a review or WOW.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


def check(path):
    path = Path(path).resolve()
    issues, open_ids, pending = [], [], []

    def issue(code, capability=None):
        issues.append({'code': code, 'id': capability})

    def present(value):
        return isinstance(value, str) and bool(value.strip())

    def evidence(ref, capability, field):
        if not isinstance(ref, dict) or not present(ref.get('path')) or not present(ref.get('sha256')):
            issue('missing_' + field, capability)
            return
        target = path.parent / ref['path']
        try:
            with os.fdopen(os.open(target, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)), 'rb') as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024 * 1024:
                    issue('unsupported_evidence', capability)
                    return
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != ref['sha256']:
                issue('evidence_changed', capability)
        except OSError:
            issue('evidence_unavailable', capability)

    try:
        with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)), 'rb') as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 4 * 1024 * 1024:
                raise ValueError('unsupported matrix')
            matrix = json.loads(stream.read(4 * 1024 * 1024 + 1))
    except (OSError, ValueError, UnicodeError):
        return {'status': 'INVALID', 'issues': [{'code': 'unreadable_matrix', 'id': None}],
                'open_ids': [], 'active_id': None, 'autonomous_quality': 'NOT_ASSESSED'}
    if not isinstance(matrix, dict):
        matrix = {}
    tracking = matrix.get('integration_followup')
    if not isinstance(tracking, dict):
        tracking = {}
    rows = matrix.get('rows')
    if not isinstance(rows, list):
        rows = []
        issue('missing_rows')
    ids = []
    for row in rows:
        if not isinstance(row, dict) or not present(row.get('id')):
            issue('invalid_row')
            continue
        key = row['id']
        if key in ids:
            issue('duplicate_id', key)
        ids.append(key)
        item = row.get('followup')
        if not isinstance(item, dict):
            issue('missing_followup', key)
            open_ids.append(key)
            continue
        for field in ('owner', 'scope'):
            if not present(item.get(field)):
                issue('missing_' + field, key)
        if item.get('stage') not in ('qualification', 'correction', 'contract', 'integration', 'e2e', 'decision'):
            issue('invalid_stage', key)
        current = item.get('state')
        if current not in ('OPEN', 'BLOCKED', 'CLOSED'):
            issue('invalid_state', key)
        if 'last_evidence' not in item:
            issue('missing_evidence_state', key)
        if item.get('last_evidence') is not None:
            evidence(item['last_evidence'], key, 'last_evidence')
        if current != 'CLOSED':
            open_ids.append(key)
            pending.append({'id': key, 'owner': item.get('owner'), 'stage': item.get('stage'),
                            'next_action': item.get('next_action'), 'blocker': item.get('blocker')})
            if not present(item.get('next_action')):
                issue('missing_next_action', key)
            if current == 'BLOCKED' and not present(item.get('blocker')):
                issue('missing_blocker', key)
            continue
        if item.get('next_action') is not None:
            issue('closed_capability_has_next_action', key)
        closure = item.get('closure')
        if not isinstance(closure, dict):
            closure = {}
        if closure.get('kind') == 'not_admitted':
            if not present(closure.get('reason')):
                issue('missing_exclusion_reason', key)
            evidence(closure.get('decision_receipt'), key, 'decision_receipt')
        elif closure.get('kind') == 'integrated':
            route = closure.get('route')
            if not isinstance(route, dict) or any(not present(route.get(k)) for k in (
                    'canonical_file', 'loaded_by', 'consumer', 'acceptance')):
                issue('missing_route', key)
            for field in ('qualification_receipt', 'integration_receipt', 'e2e_receipt'):
                evidence(closure.get(field), key, field)
        else:
            issue('missing_closure_decision', key)
    inventory = tracking.get('scope_ids')
    if (not isinstance(inventory, list) or not inventory or
            not all(present(key) for key in inventory) or
            len(inventory) != len(set(inventory)) or set(inventory) != set(ids)):
        issue('inventory_mismatch')
    if tracking.get('version') != 1:
        issue('unsupported_tracking_version')
    parent = tracking.get('parent_status')
    if parent not in ('OPEN', 'COMPLETE'):
        issue('invalid_parent_status')
    if open_ids:
        if parent == 'COMPLETE':
            issue('parent_has_open_capabilities')
        if tracking.get('active_id') not in open_ids:
            issue('missing_active_capability')
        if not present(tracking.get('next_action')):
            issue('missing_parent_next_action')
    elif tracking.get('active_id') is not None or tracking.get('next_action') is not None:
        issue('closed_parent_has_active_work')
    return {
        'status': 'INVALID' if issues else ('IN_PROGRESS' if open_ids or parent != 'COMPLETE' else 'TRACKING_COMPLETE'),
        'issues': issues, 'open_ids': open_ids, 'active_id': tracking.get('active_id'),
        'pending': pending,
        'next_action': tracking.get('next_action'), 'autonomous_quality': 'NOT_ASSESSED',
        'scope': 'inventory_continuity_and_evidence_hashes_only',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('matrix', type=Path)
    parser.add_argument('--close', action='store_true', help='Refuse closure while any capability remains open.')
    args = parser.parse_args()
    report = check(args.matrix)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report['status'] == 'INVALID' or
                     (args.close and report['status'] != 'TRACKING_COMPLETE') else 0)
