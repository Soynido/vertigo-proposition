"""Source-only creative input projection. Never fabricate a human approval."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from . import state
from .composition import _current,_public_proof


def _declared_proofs(value):
    if isinstance(value,dict):
        for child in value.values():yield from _declared_proofs(child)
    elif isinstance(value,list):
        for child in value:yield from _declared_proofs(child)
    elif isinstance(value,str) and value.startswith(('source:','fact:')):
        yield value


def public_ids(run):
    _,path=_current(run,'artifact:creative-inputs');inputs=json.loads(path.read_text())
    identifiers={'creative-inputs'}
    identifiers.update(m['reference_ref'].removeprefix('artifact:') for m in inputs['methods'])
    for field in ('media_refs','supporting_public_refs'):
        values=inputs.get(field,[])
        if not isinstance(values,list) or any(not isinstance(v,str) or not v.startswith('artifact:') for v in values):
            raise ValueError('Public supporting inputs require explicit artifact references')
        identifiers.update(v.removeprefix('artifact:') for v in values)
    return sorted(identifiers)


def public_records(run):
    """Only evidence actually cited by the public brief; never private raw files."""
    _,path=_current(run,'artifact:creative-inputs');inputs=json.loads(path.read_text())
    pending=list(set(_declared_proofs(inputs)));result={}
    while pending:
        reference=pending.pop()
        if reference in result:continue
        _public_proof(run,reference);row=state._resolve(run,reference)
        if reference.startswith('fact:'):
            result[reference]={'value':row['value'],'status':row['status'],'source_refs':['source:'+s for s in row['source_ids']]}
            pending+=result[reference]['source_refs']
        else:
            locator=row.get('locator');address=urlsplit(locator or '')
            public_url=locator if address.scheme in ('http','https') and address.hostname and not address.username and not address.password else None
            result[reference]={'kind':row['kind'],'status':row['status'],'sha256':row.get('sha256'),
                'locator':public_url,'observed_at':row['observed_at'],'raw_file_included':False}
    return result


def prepare_release(run_dir,files=None):
    if state.stage_report(run_dir,'brief.public')['status']!='PASS':
        raise ValueError('A current independently assessed public brief is required')
    run=state.load_run(run_dir)
    if state.delivery_format(run)!='web':
        raise ValueError('Automatic public-source projection is specific to web runs')
    _,path=_current(run,'artifact:creative-inputs');inputs=json.loads(path.read_text())
    allowed=set(public_ids(run))
    if files is None:files=sorted(allowed)
    if not files or len(set(files))!=len(files) or not set(files).issubset(allowed):
        raise ValueError('Creative input selection exceeds the canonical public brief allowlist')
    identities={}
    for identifier in files:
        row,_=_current(run,'artifact:'+identifier)
        if row['audience'] not in ('public','client'):
            raise ValueError('A private/internal artifact cannot enter a public creative context')
        leaves=[r for r in state._dependency_closure(run,['artifact:'+identifier]) if r.startswith(('source:','fact:'))]
        if not leaves:raise ValueError('Public creative inputs require actual public source provenance')
        if any(state._resolve(run,r).get('kind')=='private' for r in leaves):
            raise ValueError('Private provenance cannot enter a URL-only public input projection')
        # The canonical brief is a reviewed projection of public observations.
        # Its internal navigation/analysis traces are audit dependencies, not
        # files or client claims to send. Validate the claims it actually cites.
        proofs=set(_declared_proofs(inputs)) if identifier=='creative-inputs' else leaves
        if not proofs:raise ValueError('The public brief needs explicit current public proof')
        for reference in proofs:_public_proof(run,reference)
        identities[identifier]=row['sha256']
    data={'version':1,'run_id':run['id'],'authority':'verified_public_source_projection',
          'brief_review_sha256':state._record_digest(run['stage_reviews']['brief.public']),
          'artifact_hashes':identities,'scope':'creative_inputs_only_not_external_publication'}
    root=Path(run['root']);path=state._safe_path(root,'context/release-'+state._digest(data)+'.json',exists=False)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with path.open('xb') as stream:stream.write(state._canonical(data))
    elif json.loads(path.read_text())!=data:
        raise ValueError('Existing public input projection changed')
    record=state._artifact_record(run,'public-input-release',path,'internal',
        ['artifact:'+identifier for identifier in sorted(identities)],reuse_current=True)
    run['artifacts']['public-input-release']=record;state.save_run(root,run)
    return record


def allowed(run,artifact):
    try:
        row,path=_current(run,'artifact:public-input-release');data=json.loads(path.read_text())
        brief=run['stage_reviews'].get('brief.public')
        return bool(data.get('run_id')==run['id']
            and data.get('authority')=='verified_public_source_projection'
            and brief and brief['status']=='PASS'
            and not state._stale_reasons(run,Path(run['root']),brief)
            and data.get('brief_review_sha256')==state._record_digest(brief)
            and data.get('artifact_hashes',{}).get(artifact['id'])==artifact['sha256']
            and artifact['audience'] in ('public','client'))
    except (ValueError,OSError,KeyError,TypeError):
        return False
