"""Keep colored seals and attached signature strokes as positioned graphics."""
import base64
import cv2
import numpy as np


def extract_monochrome_graphics(rgb, text_image, lines=()):
    """Retain compact grayscale emblems and simple full-page printed frames.

    Work from connected ink and ruled geometry, never a document name or a
    fixed crop. Text/table regions and multi-rule grids are not illustrations.
    """
    h,w=text_image.shape
    ink=(text_image<150).astype(np.uint8)
    joined=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
    _,labels,stats,_=cv2.connectedComponentsWithStats(joined)
    result=[]
    for x,y,cw,ch,area in stats[1:]:
        if not (.04*h<ch<.25*h and .6<cw/max(1,ch)<1.6 and cw<w*.3 and y<h*.3):
            continue
        if ink[y:y+ch,x:x+cw].mean()<.12:
            continue
        if any(l.get('confidence',0)>=80 and len(l.get('text',''))>=8
               and x<l['bbox'][0] and l['bbox'][2]<x+cw
               and y<l['bbox'][1] and l['bbox'][3]<y+ch for l in lines):
            continue
        x0,y0,x1,y1=max(0,int(x)-3),max(0,int(y)-3),min(w,int(x+cw)+3),min(h,int(y+ch)+3)
        encoded=cv2.imencode('.png',cv2.cvtColor(rgb[y0:y1,x0:x1],cv2.COLOR_RGB2BGR))[1]
        result.append(dict(type='image',role='illustration',bbox=[x0,y0,x1,y1],
                           width_fraction=(x1-x0)/w,align='left',
                           data=base64.b64encode(encoded).decode('ascii')))
    # A cover's frame has only two long horizontal and two long vertical rules.
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);binary=(gray<180).astype(np.uint8)
    horizontal=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((1,max(20,round(w*.65))),np.uint8))
    vertical=cv2.morphologyEx(binary,cv2.MORPH_OPEN,np.ones((max(20,round(h*.65)),1),np.uint8))
    def groups(values):
        indexes=np.flatnonzero(values)
        return np.split(indexes,np.where(np.diff(indexes)>8)[0]+1) if len(indexes) else []
    ys=groups(horizontal.sum(axis=1)>w*.65);xs=groups(vertical.sum(axis=0)>h*.65)
    if len(xs)!=2 or len(ys)!=2:
        # Scanned borders can tilt by a fraction of a degree, so no single
        # row/column contains the complete rule. Require four long surrounding
        # segments; internal table rules prevent this fallback from firing.
        edges=cv2.dilate(cv2.Canny(gray,40,120),np.ones((3,3),np.uint8))
        segments=cv2.HoughLinesP(edges,1,np.pi/1800,100,
                                 minLineLength=min(h,w)*.7,maxLineGap=min(h,w)*.05)
        hs=[];vs=[]
        if segments is not None:
            for a,b,c,d in segments.reshape(-1,4):
                if (abs(c-a)>w*.75 and abs(d-b)<abs(c-a)*.012
                        and h*.015<(b+d)/2<h*.985):
                    hs.append((a,b,c,d))
                elif (abs(d-b)>h*.8 and abs(c-a)<abs(d-b)*.012
                        and w*.015<(a+c)/2<w*.985):
                    vs.append((a,b,c,d))
        def clustered(segments,axis):
            centers=sorted((s[axis]+s[axis+2])/2 for s in segments)
            result=[]
            for center in centers:
                if not result or center-result[-1][-1]>12:result.append([])
                result[-1].append(center)
            return result
        if len(clustered(hs,1))==len(clustered(vs,0))==2:
            horizontal[:]=0;vertical[:]=0
            for a,b,c,d in hs:cv2.line(horizontal,(a,b),(c,d),1,7)
            for a,b,c,d in vs:cv2.line(vertical,(a,b),(c,d),1,7)
            ys=[np.array([round(min(g)),round(max(g))]) for g in clustered(hs,1)]
            xs=[np.array([round(min(g)),round(max(g))]) for g in clustered(vs,0)]
    if len(xs)==len(ys)==2:
        x0,x1=int(xs[0].min()),int(xs[1].max())
        y0,y1=int(ys[0].min()),int(ys[1].max())
        if x1-x0>w*.75 and y1-y0>h*.8:
            x0,y0,x1,y1=max(0,x0-3),max(0,y0-3),min(w,x1+4),min(h,y1+4)
            mask=cv2.dilate(horizontal|vertical,np.ones((3,3),np.uint8))
            local=mask[y0:y1,x0:x1]>0
            crop=rgb[y0:y1,x0:x1]
            alpha=np.where(local,255-gray[y0:y1,x0:x1],0).astype(np.uint8)
            encoded=cv2.imencode('.png',np.dstack([cv2.cvtColor(crop,cv2.COLOR_RGB2BGR),alpha]))[1]
            result.append(dict(type='image',role='page_frame',overlay=True,bbox=[x0,y0,x1,y1],
                               width_fraction=(x1-x0)/w,align='left',data=base64.b64encode(encoded).decode('ascii')))
    return result


def _seal_masks(rgb):
    """Return (box, ink mask, signed) for each seal and the strokes crossing it.

    A seal is a compact colored component; its signature is connected long ink
    touching that component. Printed glyphs are small separate components, so
    they never enter the mask, even when the seal is stamped over them.
    """
    h,w=rgb.shape[:2]
    channels=rgb.astype(np.int16)
    red=((channels[:,:,0]-channels[:,:,1]>45)&(channels[:,:,0]-channels[:,:,2]>35)).astype(np.uint8)
    radius=max(3,round(min(h,w)*.004))
    connected=cv2.dilate(red,np.ones((radius,radius),np.uint8))
    count,labels,stats,_=cv2.connectedComponentsWithStats(connected)
    candidates=[]
    for k in range(1,count):
        x,y,cw,ch,area=stats[k]
        if ch<h*.025 or cw<w*.025 or not .6<cw/max(1,ch)<1.8:
            continue
        patch=red[y:y+ch,x:x+cw]
        if np.count_nonzero(patch)<cw*ch*.025:
            continue
        candidates.append(([int(x),int(y),int(x+cw),int(y+ch)],labels==k))
    if not candidates:
        return []
    # Colored seal pixels, including faint antialiased edges and gold emblem
    # parts. Neutral printed glyphs under the seal are deliberately excluded.
    colored=((channels.max(axis=2)-channels.min(axis=2))>40)&(channels.max(axis=2)>120)
    # Include connected colored handwriting crossing a seal, including strokes
    # extending beyond its ring. Never expand the region through printed lines.
    color_groups=cv2.dilate(colored.astype(np.uint8),np.ones((radius*2+1,radius*2+1),np.uint8))
    _,color_labels,_,_=cv2.connectedComponentsWithStats(color_groups)
    # Seal ink is dark in grayscale; exclude it so the ring itself cannot join
    # unrelated printed glyphs into one large "signature" component.
    # Dark red ring pixels can join a printed surname to the stamp. Such a
    # component must not become a "signature" merely because it is large.
    # Classify neutral strokes separately; connected colored handwriting is
    # already retained above, including the colored portions at crossings.
    neutral = channels.max(axis=2)-channels.min(axis=2) < 40
    ink=(((rgb[:,:,0]<180)&neutral)|(channels.max(axis=2)<120)).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink)
    results=[]
    for box,component in candidates:
        x0,y0,x1,y1=box
        touching=np.unique(color_labels[component&colored])
        mask=np.isin(color_labels,touching[touching>0])&colored
        signed=False
        # Connected long ink touching the seal is typically its signature.
        # Ordinary printed glyphs remain separate and do not expand the area.
        for k,(x,y,cw,ch,area) in enumerate(stats[1:],1):
            is_sig = ((cw>w*.04 and ch>h*.018) or (cw>w*.035 and cw>ch*5)) and cw<w*.6 and ch<h*.25
            if is_sig and x < x1 and x+cw > x0 and y < y1 and y+ch > y0:
                box=[min(box[0],int(x)),min(box[1],int(y)),max(box[2],int(x+cw)),max(box[3],int(y+ch))]
                mask=mask|(labels==k)
                signed=True
        # At a coloured crossing a pen stroke can split into several neutral
        # components. Follow only long, thin continuations near retained ink;
        # a fixed seal rectangle misses the part beyond the ring.
        for _ in range(2):
            near=cv2.dilate(mask.astype(np.uint8),np.ones((radius*2+1,radius*2+1),np.uint8))>0
            for k,(x,y,cw,ch,area) in enumerate(stats[1:],1):
                if cw>w*.01 and cw>ch*5 and ch<h*.025:
                    component=(labels[y:y+ch,x:x+cw]==k)
                    if np.any(near[y:y+ch,x:x+cw]&component):
                        mask[y:y+ch,x:x+cw] |= component
                        signed=True
        # Include faint colored edges only. Dilating an ink mask into neutral
        # pixels erases neighboring letter bodies and their detached accents.
        fringe=((channels.max(axis=2)-channels.min(axis=2))>15)&(channels.max(axis=2)>120)
        mask|=(cv2.dilate(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0)&fringe
        yy,xx=np.nonzero(mask)
        box=[max(0,int(xx.min())-2),max(0,int(yy.min())-2),
             min(w,int(xx.max())+3),min(h,int(yy.max())+3)]
        if not any(b[0]<=box[0] and b[1]<=box[1] and b[2]>=box[2] and b[3]>=box[3] for b,_,_ in results):
            results.append((box,mask,signed))
    return results


def seal_regions(rgb, lines=None):
    return [box for box,_,_ in _seal_masks(rgb)]


def seal_ink_mask(rgb):
    """Actual seal/signature ink, excluding surrounding neutral printed text."""
    mask=np.zeros(rgb.shape[:2],bool)
    for _,ink,_ in _seal_masks(rgb):
        mask|=ink
    return mask


def extract_seal_graphics(rgb, lines=None):
    """Keep seals as positioned graphics.

    Every seal is exported as seal/signature ink on a transparent
    background: printed lines under it (title, signer name) stay editable text
    and the graphic is overlaid at its page position, like the stamp on paper.
    """
    h,w=rgb.shape[:2]
    elements=[]
    for box,mask,signed in _seal_masks(rgb):
        x0,y0,x1,y1=box
        crop=rgb[y0:y1,x0:x1]
        local=mask[y0:y1,x0:x1]
        density=255-crop.min(axis=2).astype(np.int16)
        alpha=np.where(local,np.clip(density*2,0,255),0).astype(np.uint8)
        encoded=cv2.imencode('.png',np.dstack([cv2.cvtColor(crop,cv2.COLOR_RGB2BGR),alpha]))[1]
        elements.append(dict(type='image',role='seal',bbox=box,overlay=True,
                             width_fraction=(x1-x0)/rgb.shape[1],align='left',
                             data=base64.b64encode(encoded).decode('ascii')))
    return elements

def separate_seal_fragments(image,lines,graphics):
    """Keep uncertain punctuation inside a seal as ink, never invented text.

    Letters, numbers and symbols outside the seal stay in the text stream.
    Remaining neutral signature fragments are retained as transparent pixels.
    """
    boxes=[g['bbox'] for g in graphics if g.get('role')=='seal']
    kept=[];fragments=[]
    for line in lines:
        text=line.get('text','');x0,y0,x1,y1=line['bbox']
        inside=any(a<=x0 and x1<=c and b<=y0 and y1<=d for a,b,c,d in boxes)
        if (not inside or line.get('confidence',100)>=60 or not text
                or len(text)>5 or any(c.isalnum() for c in text)):
            kept.append(line);continue
        crop=image[y0:y1,x0:x1]
        if not crop.size:
            kept.append(line);continue
        alpha=255-crop
        encoded=cv2.imencode('.png',np.dstack([np.zeros((*crop.shape,3),np.uint8),alpha]))[1]
        fragments.append(dict(type='image',role='signature_fragment',overlay=True,
                              bbox=[x0,y0,x1,y1],width_fraction=(x1-x0)/image.shape[1],align='left',
                              data=base64.b64encode(encoded).decode('ascii')))
    return kept,fragments


def extract_rule_graphics(rgb,lines):
    """Retain a printed separator which OCR mistook for a word."""
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    result=[]
    for line in lines:
        if line.get('confidence',100)>=60:
            continue
        x0,y0,x1,y1=line['bbox']
        crop=gray[y0:y1,x0:x1]
        if not crop.size or crop.shape[1]<crop.shape[0]*2:
            continue
        ink=(crop<180).astype(np.uint8)
        horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(12,round(crop.shape[1]*.55))),np.uint8))
        if np.count_nonzero(horizontal)<np.count_nonzero(ink)*.75 or not np.any(horizontal):
            continue
        ys=np.nonzero(horizontal)[0]
        if ys.max()-ys.min()+1>max(4,crop.shape[0]*.25):
            continue
        encoded=cv2.imencode('.png',cv2.cvtColor(rgb[y0:y1,x0:x1],cv2.COLOR_RGB2BGR))[1]
        result.append(dict(type='image',role='separator',bbox=[x0,y0,x1,y1],
                           width_fraction=(x1-x0)/rgb.shape[1],align='left',
                           data=base64.b64encode(encoded).decode('ascii')))
    return result


def _initials_crop(rgb):
    """Remove neutral print cut by the edge of a coloured initials crop.

    Keep all coloured strokes, including their dark connected portions. Only
    disconnected, neutral components touching the crop edge can be fragments
    of neighboring editable text; interior ink is deliberately left intact.
    """
    channels=rgb.astype(np.int16)
    colour=channels.max(axis=2)-channels.min(axis=2)>35
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    _,labels,stats,_=cv2.connectedComponentsWithStats((gray<220).astype(np.uint8))
    clean=rgb.copy();h,w=gray.shape
    for k,(x,y,cw,ch,_) in enumerate(stats[1:],1):
        if x>0 and y>0 and x+cw<w and y+ch<h:
            continue
        component=labels==k
        if not np.any(colour & component):
            clean[component]=255
    return clean


def erase_initials_ink(image,graphic):
    """Erase only extracted signature pixels, preserving adjacent printed ink."""
    x0,y0,x1,y1=graphic['bbox']
    crop=cv2.imdecode(np.frombuffer(base64.b64decode(graphic['data']),np.uint8),cv2.IMREAD_GRAYSCALE)
    if crop is None or crop.shape!=(y1-y0,x1-x0):
        return
    image[y0:y1,x0:x1][crop<245]=255


def extract_marginal_ink(rgb, lines=()):
    """Retain tiny coloured certification blocks and isolated margin initials.

    These are source pixels, not guessed text. Ordinary body headings, coloured
    dates and readable printed text at a margin are excluded by their geometry.
    """
    h,w=rgb.shape[:2];channels=rgb.astype(np.int16)
    colour=channels.max(axis=2)-channels.min(axis=2)>35
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    top=gray[:round(h*.06)]
    joined=cv2.dilate((top<200).astype(np.uint8),np.ones((15,35),np.uint8))
    _,labels,stats,_=cv2.connectedComponentsWithStats(joined)
    boxes=[]
    for x,y,cw,ch,area in stats[1:]:
        if (y<h*.025 and ch<h*.05 and cw>w*.08 and y+ch<top.shape[0]
                and colour[y:y+ch,x:x+cw].sum()>80):
            boxes.append(([int(x),int(y),int(x+cw),int(y+ch)],'certification'))
    blue=((channels[:,:,2]-channels[:,:,0]>30)&(channels[:,:,2]-channels[:,:,1]>15)).astype(np.uint8)
    _,labels,stats,_=cv2.connectedComponentsWithStats(cv2.dilate(blue,np.ones((11,11),np.uint8)))
    for x,y,cw,ch,area in stats[1:]:
        if not ((x>w*.75 or x+cw<w*.25) and y>h*.8 and cw>w*.02 and ch>h*.02):
            continue
        # A padded pen box can touch a few pixels of the preceding line.
        # Test substantial overlap with actual printed words, not the whole
        # line rectangle; a corner contact must not turn initials into text.
        if any(word.get('confidence',0)>=75 and len(word['text'])>=2 and
               max(0,min(x+cw,word['bbox'][2])-max(x,word['bbox'][0])) *
               max(0,min(y+ch,word['bbox'][3])-max(y,word['bbox'][1])) >
               (word['bbox'][2]-word['bbox'][0])*(word['bbox'][3]-word['bbox'][1])*.25
               for l in lines for word in l.get('words',[l])):
            continue
        boxes.append(([int(x),int(y),int(x+cw),int(y+ch)],'initials'))
    result=[]
    for box,role in boxes:
        x0,y0,x1,y1=box
        crop=rgb[y0:y1,x0:x1]
        if role=='initials':
            crop=_initials_crop(crop)
        encoded=cv2.imencode('.png',cv2.cvtColor(crop,cv2.COLOR_RGB2BGR))[1]
        result.append(dict(type='image',role=role,bbox=box,width_fraction=(x1-x0)/w,
                           align='left',data=base64.b64encode(encoded).decode('ascii')))
    return result


def extract_inline_annotations(rgb, gray, lines):
    """Preserve outlying pen strokes beside a printed line as actual ink.

    A weak trailing OCR token can combine printed punctuation with handwriting.
    Only components extending well below the neighboring printed baseline are
    separated. Small raised references and ordinary descenders stay text.
    """
    elements = []
    removed = np.zeros(gray.shape, np.uint8)
    for line in lines:
        words = line.get('words', [])
        if not words or words[-1].get('confidence', 100) >= 60:
            continue
        anchors = [w for w in words[:-1] if w.get('confidence', 0) >= 40 and len(w['text']) >= 3]
        if len(anchors) < 2:
            continue
        height = float(np.median([w['bbox'][3]-w['bbox'][1] for w in anchors]))
        baseline = float(np.median([w['bbox'][3] for w in anchors]))
        x0,y0,x1,y1 = words[-1]['bbox']
        pad = round(height*.25)
        x0,y0,x1,y1 = max(0,x0-pad),max(0,y0-pad),min(gray.shape[1],x1+pad),min(gray.shape[0],y1+pad)
        crop = gray[y0:y1,x0:x1]
        _,labels,stats,_ = cv2.connectedComponentsWithStats((crop<180).astype(np.uint8))
        candidates = [k for k,(x,y,w,h,area) in enumerate(stats[1:],1)
                      if h>height*1.2 and y+y0+h>baseline+height*.35
                      and y+y0<baseline-height*.35 and area>height*2]
        # A scan-edge rule can cross the last word on many lines. Its local
        # segment is not a handwritten annotation and must never take the
        # connected printed letters with it.
        candidates = [k for k in candidates
                      if stats[k,3] < height*2.3 and stats[k,2] > height*.4
                      and stats[k,1]>1 and stats[k,1]+stats[k,3]<crop.shape[0]-1]
        capitals = all(w['text'].isupper() for w in anchors)
        if capitals:
            bodies = [s for s in stats[1:] if s[3] >= height*.6]
            if bodies:
                edge = max(s[0]+s[2] for s in bodies)
                flat = [k for k,(x,y,w,h,area) in enumerate(stats[1:],1)
                        if x>=edge and w>height*.6 and h<height*.55 and area>height]
                candidates.extend(flat)
        if not candidates:
            continue
        start = min(stats[k,0] for k in candidates)
        # A second disconnected pen stroke can overlap the first horizontally.
        selected = [k for k,(x,y,w,h,area) in enumerate(stats[1:],1)
                    if x>=start and (y+y0+h>baseline+height*.35 or k in candidates) and area>height]
        mask = np.isin(labels, selected)
        yy,xx = np.nonzero(mask)
        if not len(xx):
            continue
        local = cv2.dilate(mask.astype(np.uint8),np.ones((3,3),np.uint8))>0
        removed[y0:y1,x0:x1] |= local.astype(np.uint8)
        left,top,right,bottom = max(0,xx.min()-2),max(0,yy.min()-2),min(crop.shape[1],xx.max()+3),min(crop.shape[0],yy.max()+3)
        rgba = np.dstack([cv2.cvtColor(rgb[y0:y1,x0:x1],cv2.COLOR_RGB2BGR),local.astype(np.uint8)*255])
        encoded = cv2.imencode('.png',rgba[top:bottom,left:right])[1]
        elements.append(dict(type='image',role='annotation',overlay=True,
            bbox=[int(x0+left),int(y0+top),int(x0+right),int(y0+bottom)],
            align='left',width_fraction=float(right-left)/rgb.shape[1],
            data=base64.b64encode(encoded).decode('ascii')))
    return elements, removed
