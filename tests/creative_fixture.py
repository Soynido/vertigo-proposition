"""Real local image/PDF/OOXML fixtures for the preservation boundary."""
import io
import json
from pathlib import Path
import zipfile
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject, DecodedStreamObject


def make_scene(root, name='scene.png', color='navy'):
    image = Image.new('RGB', (240, 120), color)
    ImageDraw.Draw(image).rectangle((20,20,100,100), fill='orange')
    image.save(root / name)
    return root / name


def make_outputs(root, image='scene.png', *, hidden=False, images=None, creative_ids=None):
    names=images or [image]
    ids=creative_ids or ['scene']
    writer=PdfWriter(); placements=[]
    ns='http://schemas.openxmlformats.org/presentationml/2006/main'
    a='http://schemas.openxmlformats.org/drawingml/2006/main'
    r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    rel='http://schemas.openxmlformats.org/package/2006/relationships'
    with zipfile.ZipFile(root/'client.pptx','w') as z:
        slides=''.join(f'<p:sldId id="{255+n}" r:id="s{n}"/>' for n in range(1,len(names)+1))
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{ns}" xmlns:r="{r}"><p:sldIdLst>{slides}</p:sldIdLst><p:sldSz cx="3000000" cy="2000000"/></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="{rel}">'+''.join(f'<Relationship Id="s{n}" Target="slides/slide{n}.xml" Type="{r}/slide"/>' for n in range(1,len(names)+1))+'</Relationships>')
        for n,name in enumerate(names,1):
            with Image.open(root/name) as original: im=original.convert('RGB')
            scale=min(240/im.width,160/im.height);w,h=im.width*scale,im.height*scale;x,y=(300-w)/2,(200-h)/2
            page=writer.add_blank_page(width=300,height=200)
            stream=DecodedStreamObject();stream.set_data(im.tobytes())
            stream.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(im.width),NameObject('/Height'):NumberObject(im.height),NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):writer._add_object(stream)})})
            content=DecodedStreamObject();content.set_data(f'q {w} 0 0 {h} {x} {y} cm /Im1 Do Q'.encode());page[NameObject('/Contents')]=writer._add_object(content)
            z.writestr(f'ppt/slides/slide{n}.xml',f'<p:sld xmlns:p="{ns}" xmlns:a="{a}" xmlns:r="{r}"><p:cSld><p:spTree><p:pic><p:nvPicPr><p:cNvPr id="2" name="scene" hidden="{1 if hidden else 0}"/></p:nvPicPr><p:blipFill><a:blip r:embed="im1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{round(x*10000)}" y="{round(y*10000)}"/><a:ext cx="{round(w*10000)}" cy="{round(h*10000)}"/></a:xfrm></p:spPr></p:pic></p:spTree></p:cSld></p:sld>')
            z.writestr(f'ppt/slides/_rels/slide{n}.xml.rels',f'<Relationships xmlns="{rel}"><Relationship Id="im1" Target="../media/image{n}.png" Type="{r}/image"/></Relationships>')
            z.write(root/name,f'ppt/media/image{n}.png')
            placements.append({'creative_id':ids[n-1],'page':n,'rect':[x/300,y/200,w/300,h/200],'pptx_shape_id':'2'})
    writer.write(root/'client.pdf')
    (root/'placements.json').write_text(json.dumps({'pdf':'client.pdf','pptx':'client.pptx','placements':placements}))


def selection(root):
    make_scene(root)
    return {'revision':'r1','actor':'operator','decision':'Keep the rendered exploration',
            'retained':[{'id':'scene','path':'scene.png','role':'desktop','crop':[0,0,1,1],'min_page_fraction':.15}]}


def install_preservation(run):
    from proposition_runtime import preservation, state
    root=Path(run['root'])
    from experience_fixture import prepare_experience, install_story
    retained=prepare_experience(run)
    data={'revision':'r1','actor':'operator','decision':'Retain the complete fictional experience.','retained':retained}
    make_outputs(root,images=[r['path'] for r in retained],creative_ids=[r['id'] for r in retained])
    preservation.freeze_creatives(root,data)
    install_story(run)
    pdf_path = run['artifacts'].get('client-pdf',{}).get('path','client.pdf')
    if pdf_path != 'client.pdf':
        (root/'client.pdf').replace(root/pdf_path)
        manifest=json.loads((root/'placements.json').read_text()); manifest['pdf']=pdf_path
        (root/'placements.json').write_text(json.dumps(manifest))
    state.add_artifact(root,'client-pdf',pdf_path,'client', ['fact:offer'] if 'offer' in run['facts'] else [])
    state.add_artifact(root,'client-pptx','client.pptx','client')
    state.add_artifact(root,'creative-placements','placements.json','internal')
