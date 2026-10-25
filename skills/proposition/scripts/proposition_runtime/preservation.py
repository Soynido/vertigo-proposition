"""Fail-closed preservation of retained raster scenes in final PDF and PPTX.

This verifies consumption, not creative quality, selection authority or rights.
Unsupported placements block instead of silently weakening the check.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import posixpath
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image, ImageChops, ImageStat, ImageFilter
import pypdfium2 as pdfium
from . import state
from .artifacts import sha256

NS = {'p':'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
LOCK = 'creative-selection.lock.json'


def _numbers(values, count):
    if (not isinstance(values, list) or len(values) != count
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in values)):
        raise ValueError('Coordinates must be finite numbers')
    return values


def _crop(value):
    l,t,r,b = _numbers(value,4)
    if not (0 <= l < r <= 1 and 0 <= t < b <= 1) or (r-l)*(b-t) < .5:
        raise ValueError('Approved crop must preserve at least half of the scene')
    return value


def freeze_creatives(run_dir, selection):
    """Write once before composition. Do not silently reselect at export time."""
    run=state.load_run(run_dir); root=Path(run['root'])
    if run.get('metadata',{}).get('creative_selection') or (root/LOCK).exists():
        raise ValueError('Creative selection is already frozen; use an explicit new run revision')
    for key in ('revision','actor','decision'):
        if not isinstance(selection.get(key),str) or not selection[key].strip():
            raise ValueError(f'Selection needs {key}')
    retained=selection.get('retained')
    if not isinstance(retained,list) or not retained:
        raise ValueError('At least one retained scene is required')
    rows=[]; identifiers=set()
    for item in retained:
        identifier=state._identifier(item['id'])
        if identifier in identifiers:
            raise ValueError('Duplicate retained creative')
        identifiers.add(identifier)
        path=state._safe_path(root,item['path'])
        with Image.open(path) as im:
            if im.format not in ('PNG','JPEG','WEBP') or min(im.size)<64:
                raise ValueError('Retained scenes need a rendered PNG/JPEG/WebP, at least 64px per side')
            im.verify()
        if item.get('role') not in ('desktop','mobile','board','detail'):
            raise ValueError('Retained scene needs an explicit viewport/role')
        minimum=item.get('min_page_fraction',.15)
        if type(minimum) not in (int,float) or not math.isfinite(minimum) or not .1 <= minimum <= 1:
            raise ValueError('Minimum visible area must be between 0.1 and 1')
        rows.append({'id':identifier,'path':path.relative_to(root).as_posix(),'sha256':sha256(path),
                     'role':item['role'],'crop':_crop(item.get('crop',[0,0,1,1])),
                     'min_page_fraction':minimum})
    data={k:selection[k] for k in ('revision','actor','decision')}
    data.update(run_id=run['id'],retained=rows)
    if run.get('metadata',{}).get('creative_exploration_contract') is not None:
        from .experience import inspect_experience
        report=inspect_experience(run,proposed_selection=rows)
        if report['status']!='PASS':
            raise ValueError('Cannot freeze creative selection: '+'; '.join(report['issues']))
    path=root/LOCK
    with path.open('x',encoding='utf-8') as f:
        f.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    run.setdefault('metadata',{})['creative_selection']={'path':LOCK,'sha256':sha256(path)}
    state.save_run(root,run)
    return {'status':'FROZEN','sha256':sha256(path),'retained':len(rows)}


def _selection(run):
    root=Path(run['root']); binding=run.get('metadata',{}).get('creative_selection')
    if not binding:
        raise ValueError('Missing frozen creative selection')
    path=state._safe_path(root,binding['path'])
    if sha256(path)!=binding['sha256']:
        raise ValueError('Frozen creative selection changed')
    data=json.loads(path.read_text())
    if data['run_id']!=run['id'] or not data['retained']:
        raise ValueError('Selection does not belong to this run or is empty')
    for item in data['retained']:
        if sha256(state._safe_path(root,item['path']))!=item['sha256']:
            raise ValueError(f"Retained creative changed: {item['id']}")
    return data


def _xml(z, name):
    return ET.fromstring(z.read(name))


def _target(z, part, rid):
    relpath=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
    matches=[r for r in _xml(z,relpath) if r.get('Id')==rid]
    if len(matches)!=1 or matches[0].get('TargetMode')=='External':
        raise ValueError('Missing or external presentation relationship')
    target=matches[0].get('Target','')
    name=posixpath.normpath(posixpath.join(posixpath.dirname(part),target)) if not target.startswith('/') else target.lstrip('/')
    if not name.startswith('ppt/') or '..' in PurePosixPath(name).parts:
        raise ValueError('Presentation relationship escapes ppt/')
    return name


def _bounds(shape, width, height):
    transform=shape.find('.//a:xfrm',NS)
    if transform is None or any(transform.get(k,'0') not in ('0','false') for k in ('rot','flipH','flipV')):
        raise ValueError('Unsupported grouped/rotated/unknown placement')
    off=transform.find('a:off',NS); ext=transform.find('a:ext',NS)
    return [int(off.get('x'))/width,int(off.get('y'))/height,
            int(ext.get('cx'))/width,int(ext.get('cy'))/height]


def _pptx_check(z, page, row, item, rect):
    presentation=_xml(z,'ppt/presentation.xml'); size=presentation.find('p:sldSz',NS)
    width,height=int(size.get('cx')),int(size.get('cy'))
    slides=presentation.findall('p:sldIdLst/p:sldId',NS)
    part=_target(z,'ppt/presentation.xml',slides[page-1].get('{'+NS['r']+'}id'))
    slide=_xml(z,part)
    if slide.get('show','1') not in ('1','true'):
        raise ValueError('Retained scene is on a hidden slide')
    tree=slide.find('p:cSld/p:spTree',NS)
    candidates=[]
    for index,shape in enumerate(tree):
        prop=shape.find('p:nvPicPr/p:cNvPr',NS)
        if prop is not None and prop.get('id')==str(row['pptx_shape_id']):
            candidates.append((index,shape,prop))
    if len(candidates)!=1:
        raise ValueError('Retained image is not a unique top-level picture on the final slide')
    index,shape,prop=candidates[0]
    if prop.get('hidden','0') not in ('0','false'):
        raise ValueError('Retained PowerPoint image is hidden')
    properties=shape.find('p:spPr',NS)
    allowed={'xfrm','prstGeom','ln','noFill'}
    if properties is None or any(child.tag.split('}')[-1] not in allowed for child in properties):
        raise ValueError('Unsupported picture effects or geometry')
    geometry=properties.find('a:prstGeom',NS)
    if geometry is not None and (geometry.get('prst')!='rect' or geometry.findall('.//a:gd',NS)):
        raise ValueError('Picture geometry clips the retained scene')
    line=properties.find('a:ln',NS)
    if line is not None and (len(line)!=1 or line[0].tag!='{'+NS['a']+'}noFill'):
        raise ValueError('Painted picture outline can cover the retained scene')
    if shape.find('p:style',NS) is not None:
        raise ValueError('Theme picture effects are unsupported')
    fill=shape.find('p:blipFill',NS)
    if any(child.tag.split('}')[-1] not in {'blip','srcRect','stretch'} for child in fill):
        raise ValueError('Unsupported image fill mode')
    stretches=fill.findall('a:stretch',NS)
    if len(stretches)!=1:
        raise ValueError('An explicit full-image stretch is required')
    fillrect=stretches[0].find('a:fillRect',NS)
    if fillrect is not None and any(int(v)!=0 for v in fillrect.attrib.values()):
        raise ValueError('Picture fill shrinks or offsets the retained image')
    bounds=_bounds(shape,width,height)
    if any(abs(a-b)>.003 for a,b in zip(bounds,rect)):
        raise ValueError('PowerPoint image placement differs from the checked PDF region')
    blip=shape.find('p:blipFill/a:blip',NS)
    if blip is None or list(blip):
        raise ValueError('Missing image or unsupported image effects')
    target=_target(z,part,blip.get('{'+NS['r']+'}embed'))
    if hashlib.sha256(z.read(target)).hexdigest()!=item['sha256']:
        raise ValueError('PowerPoint image was replaced')
    crop=shape.find('p:blipFill/a:srcRect',NS)
    actual=[int(crop.get(k,'0'))/100000 for k in ('l','t','r','b')] if crop is not None else [0,0,0,0]
    l,t,r,b=item['crop']
    if any(abs(a-b)>.0001 for a,b in zip(actual,[l,t,1-r,1-b])):
        raise ValueError('PowerPoint crop differs from frozen crop')
    for overlay in list(tree)[index+1:]:
        # Non-shape metadata has no visible bounds. Groups/effects remain unsupported.
        if overlay.tag.split('}')[-1] not in ('sp','pic','graphicFrame','grpSp','cxnSp'):
            continue
        ox,oy,ow,oh=_bounds(overlay,width,height)
        x,y,w,h=rect
        if min(x+w,ox+ow)>max(x,ox) and min(y+h,oy+oh)>max(y,oy):
            raise ValueError('A later PowerPoint object can cover the retained image')
    return part


def inspect_preservation(run, *, selection_only=False):
    """Re-read actual final bytes every time; never accept a claimed PASS receipt."""
    issues=[]; checks=[]; hashes={}
    try:
        selection=_selection(run)
        if selection_only:
            return {'status':'PASS','scope':'frozen_selection_only','retained':len(selection['retained']),'issues':[]}
        root=Path(run['root']); artifact=run['artifacts'].get('creative-placements')
        if not artifact or artifact['status']!='CURRENT':
            raise ValueError('Missing current creative-placements artifact')
        manifest=state._safe_path(root,artifact['path'])
        if sha256(manifest)!=artifact['sha256']:
            raise ValueError('Placement manifest changed after registration')
        data=json.loads(manifest.read_text()); pdf=state._safe_path(root,data['pdf']); pptx=state._safe_path(root,data['pptx'])
        for kind, path in (('pdf', pdf), ('pptx', pptx)):
            final = run['artifacts'].get('client-' + kind)
            if (not final or final['status'] != 'CURRENT' or final['audience'] != 'client'
                    or state._safe_path(root, final['path']) != path or sha256(path) != final['sha256']):
                raise ValueError('Manifest must reference the exact current client-' + kind + ' artifact')
        hashes={'selection':run['metadata']['creative_selection']['sha256'],
                'placements':sha256(manifest),'pdf':sha256(pdf),'pptx':sha256(pptx)}
        rows=data['placements']; retained={i['id']:i for i in selection['retained']}
        if not isinstance(rows,list) or {r['creative_id'] for r in rows}!=set(retained):
            raise ValueError('Every retained creative must have a placement; unknown IDs are forbidden')
        with pdfium.PdfDocument(str(pdf)) as document, zipfile.ZipFile(pptx) as z:
            occupied=[]
            for row in rows:
                item=retained[row['creative_id']]; page=row['page']
                if type(page) is not int or not 1<=page<=len(document):
                    raise ValueError('Invalid final page number')
                x,y,w,h=_numbers(row['rect'],4)
                if not (0<=x<1 and 0<=y<1 and w>0 and h>0 and x+w<=1.000001 and y+h<=1.000001):
                    raise ValueError('Creative placement is outside the page')
                if w*h<item['min_page_fraction']:
                    raise ValueError('Retained scene was reduced to a thumbnail')
                for other_page,ox,oy,ow,oh in occupied:
                    if page==other_page and min(x+w,ox+ow)>max(x,ox) and min(y+h,oy+oh)>max(y,oy):
                        raise ValueError('Retained scene regions overlap')
                occupied.append((page,x,y,w,h))
                with Image.open(state._safe_path(root,item['path'])) as original:
                    l,t,r,b=item['crop']
                    expected=original.convert('RGB').crop((round(l*original.width),round(t*original.height),round(r*original.width),round(b*original.height)))
                pdfpage=document[page-1]
                try:
                    bitmap=pdfpage.render(scale=2)
                    try:
                        rendered=bitmap.to_pil().convert('RGB')
                    finally:
                        bitmap.close()
                finally:
                    pdfpage.close()
                actual=rendered.crop((round(x*rendered.width),round(y*rendered.height),round((x+w)*rendered.width),round((y+h)*rendered.height)))
                if abs(actual.width/actual.height-expected.width/expected.height)/(expected.width/expected.height)>.02:
                    raise ValueError('Creative aspect ratio changed')
                # Small antialiasing/resampling differences are allowed, not a redesign.
                diff=ImageChops.difference(actual.resize((240,240)),expected.resize((240,240)))
                error=sum(ImageStat.Stat(diff).mean)/(3*255)
                if error>.035:
                    raise ValueError(f"Final PDF pixels differ from retained scene {item['id']}: {error:.4f}")
                # Global averages can hide deletion of a logo or CTA. Check local
                # 10x10 tiles too, after slight blur for rasterization noise.
                local_diff=ImageChops.difference(
                    actual.resize((240,240)).filter(ImageFilter.GaussianBlur(.5)),
                    expected.resize((240,240)).filter(ImageFilter.GaussianBlur(.5)))
                local_error=max(sum(ImageStat.Stat(local_diff.crop((tx,ty,tx+10,ty+10))).mean)/(3*255)
                                for ty in range(0,240,10) for tx in range(0,240,10))
                if local_error>.10:
                    raise ValueError(f"Final PDF has a local content difference in {item['id']}: {local_error:.4f}")
                part=_pptx_check(z,page,row,item,[x,y,w,h])
                checks.append({'creative_id':item['id'],'page':page,'pptx_part':part,'pixel_error':round(error,6),'local_pixel_error':round(local_error,6)})
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError, ET.ParseError, zipfile.BadZipFile, pdfium.PdfiumError) as error:
        issues.append(str(error))
    return {'status':'BLOCKED' if issues else 'PASS','scope':'retained_scene_consumption_only',
            'issues':issues,'checks':checks,'hashes':hashes,'creative_quality':'NOT_ASSESSED'}
