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


def make_outputs(root, image='scene.png', *, hidden=False):
    im = Image.open(root / image).convert('RGB')
    writer = PdfWriter(); page = writer.add_blank_page(width=300,height=200)
    stream=DecodedStreamObject(); stream.set_data(im.tobytes())
    stream.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),
        NameObject('/Width'):NumberObject(240),NameObject('/Height'):NumberObject(120),
        NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):writer._add_object(stream)})})
    content=DecodedStreamObject(); content.set_data(b'q 240 0 0 120 30 40 cm /Im1 Do Q')
    page[NameObject('/Contents')]=writer._add_object(content)
    writer.write(root/'client.pdf')
    ns='http://schemas.openxmlformats.org/presentationml/2006/main'
    a='http://schemas.openxmlformats.org/drawingml/2006/main'
    r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    with zipfile.ZipFile(root/'client.pptx','w') as z:
        z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{ns}" xmlns:r="{r}"><p:sldIdLst><p:sldId id="256" r:id="s1"/></p:sldIdLst><p:sldSz cx="3000000" cy="2000000"/></p:presentation>')
        z.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="s1" Target="slides/slide1.xml" Type="{r}/slide"/></Relationships>')
        z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{ns}" xmlns:a="{a}" xmlns:r="{r}"><p:cSld><p:spTree><p:pic><p:nvPicPr><p:cNvPr id="2" name="scene" hidden="{1 if hidden else 0}"/></p:nvPicPr><p:blipFill><a:blip r:embed="im1"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="300000" y="400000"/><a:ext cx="2400000" cy="1200000"/></a:xfrm></p:spPr></p:pic></p:spTree></p:cSld></p:sld>')
        z.writestr('ppt/slides/_rels/slide1.xml.rels',f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="im1" Target="../media/image1.png" Type="{r}/image"/></Relationships>')
        z.write(root/image,'ppt/media/image1.png')
    (root/'placements.json').write_text(json.dumps({'pdf':'client.pdf','pptx':'client.pptx','placements':[
        {'creative_id':'scene','page':1,'rect':[.1,.2,.8,.6],'pptx_shape_id':'2'}]}))


def selection(root):
    make_scene(root)
    return {'revision':'r1','actor':'operator','decision':'Keep the rendered exploration',
            'retained':[{'id':'scene','path':'scene.png','role':'desktop','crop':[0,0,1,1],'min_page_fraction':.15}]}


def install_preservation(run):
    from proposition_runtime import preservation, state
    root=Path(run['root'])
    data=selection(root); make_outputs(root)
    preservation.freeze_creatives(root,data)
    pdf_path = run['artifacts'].get('client-pdf',{}).get('path','client.pdf')
    if pdf_path != 'client.pdf':
        (root/'client.pdf').replace(root/pdf_path)
        manifest=json.loads((root/'placements.json').read_text()); manifest['pdf']=pdf_path
        (root/'placements.json').write_text(json.dumps(manifest))
    state.add_artifact(root,'client-pdf',pdf_path,'client', ['fact:offer'] if 'offer' in run['facts'] else [])
    state.add_artifact(root,'client-pptx','client.pptx','client')
    state.add_artifact(root,'creative-placements','placements.json','internal')
