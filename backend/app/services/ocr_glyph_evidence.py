"""Compare competing diacritics after registering their unchanged letter bodies."""
from functools import lru_cache
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw


def _body_box(mask):
    stats=cv2.connectedComponentsWithStats((mask>.5).astype(np.uint8))[2][1:]
    if not len(stats):
        return None
    height=max(stats[:,3])
    bodies=[s for s in stats if s[3]>=height*.55 and s[4]>=height]
    if not bodies:
        return None
    return [min(s[0] for s in bodies),min(s[1] for s in bodies),
            max(s[0]+s[2] for s in bodies),max(s[1]+s[3] for s in bodies)]


@lru_cache(maxsize=256)
def _references(index,original,alternative,size=100):
    from app.services.ocr_typography import _fonts
    font=_fonts()[index][3].font_variant(size=size)
    # An opening mark moves all following letters. Register identical lexical
    # bodies before comparing edge punctuation, instead of scoring that shift
    # as if the whole word had changed shape.
    def prefix(text):
        return text[:next((i for i,c in enumerate(text) if c.isalnum()),0)]
    def core(text):
        positions=[i for i,c in enumerate(text) if c.isalnum()]
        return text[positions[0]:positions[-1]+1] if positions else text
    widths=[font.getlength(prefix(t)) for t in (original,alternative)]
    offsets=[max(widths)-w for w in widths] if core(original)==core(alternative) else [0,0]
    a,b=[(box[0]+offset,box[1],box[2]+offset,box[3])
         for box,offset in zip([font.getbbox(original),font.getbbox(alternative)],offsets)]
    left,top=min(a[0],b[0]),min(a[1],b[1])
    width,height=max(a[2],b[2])-left,max(a[3],b[3])-top
    references=[]
    for text,offset in zip((original,alternative),offsets):
        image=Image.new('L',(int(np.ceil(width))+12,int(np.ceil(height))+12))
        ImageDraw.Draw(image).text((6-left+offset,6-top),text,font=font,fill=255)
        references.append(np.asarray(image))
    return references


def registered_accent_support(crop,original,alternative):
    """Require a substantially better mark, choosing the font on shared ink.

    Both spellings are rendered on one baseline. Normalizing each spelling's
    full bounding box separately moves the whole word when a tone is added,
    making a genuine missing mark impossible to compare. Search a small range
    of source scale/offset, then score only the changed mark independently.
    Callers must also establish matching letters and two visual OCR readings.
    """
    from app.services.ocr_typography import _fonts
    target=(crop<160).astype(np.float32)
    observed=_body_box(target)
    if observed is None:
        return False
    best=None
    for index in range(len(_fonts())):
        references=[r.astype(np.float32)/255 for r in _references(index,original,alternative)]
        body=_body_box(np.minimum(*references))
        if body is None:
            continue
        sx=(observed[2]-observed[0])/max(1,body[2]-body[0])
        # Rasterize at the scan's actual size before fitting. Scaling a large
        # composite Vietnamese glyph can move its hinted tone relative to the
        # circumflex by several pixels at normal document resolution.
        size=max(8,min(180,round(sx*100)))
        references=[r.astype(np.float32)/255 for r in _references(index,original,alternative,size)]
        body=_body_box(np.minimum(*references))
        if body is None:
            continue
        sx=(observed[2]-observed[0])/max(1,body[2]-body[0])
        for ratio in (.90,.95,1.,1.05,1.10):
            sy=sx*ratio
            for dy in range(-8,9,2):
                transform=np.float32([[sx,0,observed[0]-body[0]*sx],
                                      [0,sy,observed[1]-body[1]*sy+dy]])
                old,new=[cv2.warpAffine(r,transform,(crop.shape[1],crop.shape[0])) for r in references]
                changed=cv2.dilate((np.abs(old-new)>.18).astype(np.uint8),np.ones((3,3),np.uint8))
                if not changed.any():
                    continue
                shared=(((np.maximum(old,new)>.1)|(target>.5)).astype(np.uint8))*(1-changed)
                if shared.sum()<20:
                    continue
                common=float(np.sum((target-(old+new)/2)**2*shared)/shared.sum())
                old_error=float(np.sum((target-old)**2*changed)/changed.sum())
                new_error=float(np.sum((target-new)**2*changed)/changed.sum())
                score=(common,old_error,new_error)
                if best is None or common<best[0]:
                    best=score
    if best is None:
        return False
    common,old_error,new_error=best
    required_gain=.08 if common<.12 else .12
    return common<.32 and new_error<old_error*.68 and old_error-new_error>required_gain


def punctuation_shape_support(crop,original,alternative):
    if registered_accent_support(crop,original,alternative):
        return True
    # Parentheses/quotes can be as tall as the letters and therefore become
    # the body-registration anchor. Compare the full outline and aspect ratio
    # for this limited prefix case. Callers require exact independent OCR.
    first=lambda t:next((i for i,c in enumerate(t) if c.isalnum()),0)
    if first(original)==first(alternative) and ' ' not in original:
        return False
    from app.services.ocr_typography import _fonts,_metrics
    mask=(crop<160).astype(np.float32);yy,xx=np.nonzero(mask)
    if not len(xx):return False
    mask=mask[yy.min():yy.max()+1,xx.min():xx.max()+1]
    h,w=mask.shape
    pattern=cv2.resize(mask,(160,40),interpolation=cv2.INTER_AREA)
    scores=[]
    for text in (original,alternative):
        values=[]
        for i in range(len(_fonts())):
            metric=_metrics(i,text)
            if metric is None:continue
            fw,fh,_,reference=metric
            values.append(float(np.mean(abs(pattern-reference)))+.3*abs(math.log((w/h)/(fw/fh))))
        scores.append(min(values,default=1.))
    old,new=scores
    return new<.22 and new+.07<old
