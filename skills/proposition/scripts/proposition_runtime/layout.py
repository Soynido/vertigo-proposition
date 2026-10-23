"""Assess explicit visible rectangles; complex masks/occlusions stay unmeasured."""
from __future__ import annotations
import math

PHOTO = {'authentic', 'retouched', 'synthetic'}


def overlap(a, b):
    return max(a[0],b[0]) < min(a[0]+a[2],b[0]+b[2]) and max(a[1],b[1]) < min(a[1]+a[3],b[1]+b[3])


def assess_placements(placements, pages):
    issues, photo_area, synthetic_area, visual_area = [], 0, 0, 0
    seen = []
    for row in placements:
        page, kind, rect = row.get('page'), row.get('kind'), row.get('rect')
        if (page not in pages or kind not in PHOTO | {'graphic','unclassified'} or
                not isinstance(rect,list) or len(rect) != 4 or
                any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in rect)):
            issues.append('invalid_placement'); continue
        x,y,w,h = rect
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x+w > pages[page][0] or y+h > pages[page][1]:
            issues.append('unmeasured_crop_or_outside_page'); continue
        if kind == 'unclassified' or row.get('complex_mask') or (kind in PHOTO and not row.get('source_id')):
            issues.append('unclassified_or_unmeasured_media')
        if any(old['page'] == page and overlap(rect,old['rect']) for old in seen):
            issues.append('overlap_requires_visible_mask_measurement')
        seen.append(row)
        visual_area += w*h
        if kind in PHOTO: photo_area += w*h
        if kind == 'synthetic': synthetic_area += w*h
    total = sum(w*h for w,h in pages.values())
    fraction = synthetic_area/photo_area if photo_area and not issues else None
    return {'status':'BLOCKED' if issues or not total else ('FAIL' if fraction is not None and fraction > .2 else 'PASS'),
            'scope':'declared_rectangles_only_not_provenance_or_creative_quality',
            'photo_area':photo_area, 'synthetic_area':synthetic_area,
            'synthetic_photo_fraction':fraction,
            'visual_area_fraction':visual_area/total if total and not issues else None,
            'issues':sorted(set(issues)),
            'note':'No photographs means the photo ratio is not applicable; visual usefulness and rights require review.'}
