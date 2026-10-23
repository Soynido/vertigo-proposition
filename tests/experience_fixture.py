"""Fictional evidence graphs. They exercise consistency, never aesthetic quality."""
import json
import hashlib
from PIL import Image
from pathlib import Path
from proposition_runtime import state
from creative_fixture import make_scene


def write_artifact(run,identifier,name,data):
    root=Path(run['root']);p=root/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data) if not isinstance(data,str) else data)
    return state.add_artifact(root,identifier,name,'public')


def prepare_inputs(run):
    root=Path(run['root'])
    (root/'observation.txt').write_text('Fictional manufacturer, existing quote action and sourced material proof.')
    state.add_source(root,'experience-source','observation.txt',kind='public',audience='public')
    proof='source:experience-source'
    families=[]; applications=[]
    specs=json.loads((state.DATA_ROOT/'upstream-lock.json').read_text())['families']
    for spec in specs:
        identifier='method-'+spec['id']
        reference=write_artifact(run,identifier,'methods/'+spec['id']+'.md','Synthetic test reference, not an upstream source authenticity test: '+spec['id'])
        state.add_source(root,identifier,'methods/'+spec['id']+'.md',kind='public',audience='public',locator='https://github.com/'+spec['repository']+'/blob/'+spec['commit']+'/'+spec['entrypoints'][0])
        reference=state.add_artifact(root,identifier,'methods/'+spec['id']+'.md','public',['source:'+identifier])
        tree=root/'fixture-methods'/spec['id']/spec['commit']/'source'
        entry=tree/spec['entrypoints'][0];entry.parent.mkdir(parents=True,exist_ok=True)
        entry.write_bytes((root/('methods/'+spec['id']+'.md')).read_bytes())
        # Offline synthetic cache: integrity fixture, never a real upstream usage receipt.
        for name in spec['entrypoints']+spec['license_files']:
            file=tree/name
            if not file.exists():
                file.parent.mkdir(parents=True,exist_ok=True);file.write_text('Synthetic test reference '+name)
        blobs=[];inventory=[]
        for file in sorted(tree.rglob('*')):
            if not file.is_file():continue
            content=file.read_bytes();name=file.relative_to(tree).as_posix()
            blobs.append({'path':name,'type':'blob','mode':'100644','size':len(content),
                          'sha':hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()})
            inventory.append({'path':name,'sha256':hashlib.sha256(content).hexdigest()})
        metadata=json.dumps({'truncated':False,'tree':blobs}).encode()
        (tree.parent/'tree.json').write_bytes(metadata)
        (tree.parent/'receipt.json').write_text(json.dumps({'commit':spec['commit'],'repository':spec['repository'],
            'metadata_sha256':hashlib.sha256(metadata).hexdigest(),'inventory':inventory,'licenses':spec['license_files']}))
        families.append({'family':spec['id'],'commit':spec['commit'],'reference_ref':'artifact:'+identifier,'reference_root':str(tree)})
        applications.append({'family':spec['id'],'mode':'adapted','read_sha256':reference['sha256'],
                             'application':'Check a specific aspect of the rendered evidence.',
                             'moment_ids':['a-opening','a-reveal','a-action']})
    inputs={'revision':'r1','direction_ids':['a'],'methods':families,
            'observations':[{'id':'o1','proof':proof,'decision':'retained','reason':'Demonstrate the real material before the quote action.','benefit':'Understand the product before requesting a quote.'}],
            'actions':[{'id':'quote','proof':proof,'target':'https://fixture.example/quote','label':'Request a quote'}]}
    source=write_artifact(run,'creative-inputs','creative-inputs.json',inputs)
    source=state.add_artifact(root,'creative-inputs','creative-inputs.json','public',[proof]+[m['reference_ref'] for m in families])
    return inputs,source,applications


def prepare_experience(run):
    root=Path(run['root']);inputs,source,applications=prepare_inputs(run)
    proof='source:experience-source'
    moments=[];retained=[]
    for name,color,role in [('opening','navy','opening'),('reveal','green','reveal'),('action','purple','action'),('mobile','teal','mobile')]:
        filename='scene.png' if name=='opening' else 'scene-'+name+'.png'
        make_scene(root,filename,color)
        if name=='mobile':
            with Image.open(root/filename) as im: im.resize((390,844)).save(root/filename)
        state.add_artifact(root,'scene-'+name,filename,'public')
        retained.append({'id':'a-'+name,'path':filename,'role':'mobile' if name=='mobile' else 'desktop','crop':[0,0,1,1],'min_page_fraction':.15})
        if role!='mobile':moments.append({'id':name,'role':role,'creative_id':'a-'+name,'render_ref':'artifact:scene-'+name,
                            'meaning':{'opening':'Recognize the manufacturer.','reveal':'See how the material changes the light.','action':'Request the existing quote.'}[name],
                            'proof':proof,'scroll_position':{'opening':0,'reveal':.5,'action':1}[name]})
    plan={'revision':'r1','inputs_sha256':source['sha256'],'method_applications':applications,
          'directions':[{'id':'a','signature':{'moment_id':'reveal','client_anchor':proof,'visible_change':'Material opens to reveal its effect on the room.'},
                         'motion_status':'static_intent','moments':moments,
                         'mobile':{'creative_id':'a-mobile','render_ref':'artifact:scene-mobile','action_text_px':16,'action_id':'quote'},
                         'actions':[{'id':'quote','target':'https://fixture.example/quote','moment_id':'action','label':'Request a quote','disposition':'preserved'}]}]}
    write_artifact(run,'creative-experience','creative-experience.json',plan)
    return retained


def install_story(run):
    roles=('understanding','evidence','opportunity','creative_world','transformation','agency_value','mission','next_step')
    write_artifact(run,'client-story','client-story.json',{'pages':[{'role':role,'page':min(i+1,4),
        'message':'A specific message about this fictional manufacturer.', 'proof':'source:experience-source'} for i,role in enumerate(roles)],
        'observation_decisions':[{'id':'o1','page':2,'reason':'The retained material proof supports the proposal.'}],
        'next_step':{'decision':'Choose a direction and the first product journey.', 'followup':'Discuss the scoped proposal with the confirmed project owner.'}})
