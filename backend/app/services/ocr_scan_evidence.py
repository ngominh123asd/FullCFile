"""Resolve scan artefacts from their pixels, without document-specific vocabulary."""
import re
import unicodedata

import cv2
import numpy as np
from PIL import Image


def remove_scan_edge_rules(gray):
    """Inpaint long scan-edge strokes before they join/cut printed characters.

    Only nearly vertical strokes at an outer edge qualify. Repeated horizontal
    intersections identify table borders, which remain for grid detection.
    """
    h,w = gray.shape
    ink = (gray < 210).astype(np.uint8)
    edges = cv2.Canny(gray,60,180)
    segments = cv2.HoughLinesP(edges,1,np.pi/1800,100,minLineLength=h*.3,maxLineGap=h*.08)
    if segments is None:
        return gray
    horizontal = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(20,int(w*.08))),np.uint8))
    mask = np.zeros_like(gray)
    for x0,y0,x1,y1 in segments.reshape(-1,4):
        if abs(y1-y0)<h*.3 or abs(x1-x0)>abs(y1-y0)*.012:
            continue
        mid=(x0+x1)/2
        if w*.16<mid<w*.84:
            continue
        slope=(x1-x0)/(y1-y0);intercept=x0-slope*y0
        xs=np.clip(np.rint(intercept+slope*np.arange(h)).astype(int),0,w-1)
        crossings=np.flatnonzero(horizontal[np.arange(h),xs])
        if len(crossings) and len(np.split(crossings,np.where(np.diff(crossings)>8)[0]+1))>=3:
            continue
        cv2.line(mask,(int(intercept),0),(int(intercept+slope*(h-1)),h-1),255,5)
    if not mask.any():
        return gray
    # Erase the rule only between printed glyphs. Inpainting straight through
    # a crossing replaces real stems/diacritics as well as the scan defect.
    # Nearby lateral ink identifies text rows; a vertical margin retains
    # detached accents too. A lone rule has no such lateral neighbours.
    neighbourhood = np.ones((41,51),np.uint8)
    neighbourhood[:,18:33] = 0
    text_nearby = cv2.dilate((gray < 160).astype(np.uint8),neighbourhood)
    mask[text_nearby != 0] = 0
    return cv2.inpaint(gray,mask,3,cv2.INPAINT_TELEA)


def _refresh(line):
    words = line['words']
    line['text'] = ' '.join(w['text'] for w in words)
    line['word_confidences'] = [(w['text'], w['confidence']) for w in words]
    if words:
        boxes = [w['bbox'] for w in words]
        line['bbox'] = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                        max(b[2] for b in boxes), max(b[3] for b in boxes)]


def without_crop_edge_rule(crop):
    """Exclude a disconnected vertical scan rule from a recognition crop.

    Require collinear narrow fragments spanning both crop edges and most rows.
    Connected letter strokes, punctuation, and an interior vertical glyph stay
    intact. This changes only a reader's view, never the stored source image.
    """
    if not crop.size:return crop
    h,w=crop.shape
    if h<20 or w<40:return crop
    _,labels,stats,_=cv2.connectedComponentsWithStats((crop<180).astype(np.uint8))
    narrow=[k for k,(x,y,cw,ch,area) in enumerate(stats[1:],1)
            if cw<=max(2,h*.045) and (x<w*.08 or x+cw>w*.92)]
    remove=set()
    for k in narrow:
        x,y,cw,ch,_=stats[k]
        group=[j for j in narrow if abs((stats[j,0]+stats[j,2]/2)-(x+cw/2))<=2]
        rows=np.zeros(h,bool)
        for j in group:rows[stats[j,1]:stats[j,1]+stats[j,3]]=True
        if rows[:2].any() and rows[-2:].any() and rows.mean()>.7:
            remove.update(group)
    if not remove:return crop
    clean=crop.copy();clean[np.isin(labels,list(remove))]=255
    return clean


def is_scan_rule_fragment(line, image):
    """Reject an edge rule boxed as a very narrow, tall multi-letter token."""
    x0,y0,x1,y1=line['bbox'];h,w=image.shape
    if (line.get('confidence',100)>=60 or len(line.get('text','').strip())<2
            or not (x1<w*.04 or x0>w*.96) or y1-y0<5*max(1,x1-x0)):
        return False
    yy,xx=np.nonzero(image[max(0,y0):y1,max(0,x0):x1]<180)
    return bool(len(xx) and xx.max()-xx.min()+1 < (yy.max()-yy.min()+1)*.15)


def remove_scan_specks(lines, image):
    """Discard impossible multi-stroke symbols represented by a single speck.

    Actual bullets, periods, digits and small references are not candidates.
    A damaged list prefix is trimmed only where isolated dust precedes a full
    glyph; its observed letter/number and delimiter remain unchanged.
    """
    heights = [w['bbox'][3]-w['bbox'][1] for l in lines for w in l.get('words', [])
               if w.get('confidence', 0) >= 90 and len(w['text']) >= 3]
    if not heights:
        return
    typical = float(np.median(heights))
    for line in lines:
        kept = []
        for index, word in enumerate(line.get('words', [])):
            text = word['text']; x0,y0,x1,y1 = word['bbox']
            before = text
            if word.get('confidence', 100) < 60:
                tiny = max(x1-x0, y1-y0) < typical*.23
                if tiny and re.fullmatch(r'[!?:;^ˆ_~.]{1,5}', text) and text != '.':
                    text = ''
                match = re.fullmatch(r'((?:[^\w\s]|_)+)(\d{1,3}(?:\.\d{1,3})*[/.)])', text) if index == 0 else None
                label = re.fullmatch(r"(['’])([^\W\d_][\w]*:)", text) if index == 0 else None
                if (match and len(match[1]) >= 2) or label:
                    crop = image[max(0,y0):y1,max(0,x0):x1]
                    _,_,stats,_ = cv2.connectedComponentsWithStats((crop < 180).astype(np.uint8))
                    bodies = [s for s in stats[1:] if s[3] >= typical*.45]
                    if bodies:
                        edge = min(s[0] for s in bodies)
                        debris = [s for s in stats[1:] if s[0]+s[2] <= edge]
                        if (edge > typical*.3 and debris
                                and all(max(s[2:4]) < typical*.23 for s in debris)
                                and (not label or len(debris)>=2)):
                            text = (match or label)[2]
                            word['bbox'] = [int(x0+edge), y0, x1, y1]
            if text != before:
                line.setdefault('ocr_corrections', []).append(dict(before=before, after=text,
                    bbox=[x0,y0,x1,y1], method='scan_speck_geometry'))
            if text:
                word['text'] = text
                kept.append(word)
        line['words'] = kept
        _refresh(line)


def is_duplicate_diacritic(line, lines, image):
    """Reject a second text box made solely from another line's upper marks.

    Keep the source pixels. Every fragment must sit above, and horizontally
    belong to, an already detected letter body. Raised numeric references and
    standalone small text cannot qualify from size/confidence alone.
    """
    words=line.get('words',[])
    if not words or len(line.get('text',''))>8 or any(c.isdigit() for c in line.get('text','')):
        return False
    for other in lines:
        if other is line or other.get('confidence',0)<85 or len(other.get('words',[]))<4:
            continue
        anchors=[w for w in other['words'] if len(w['text'])>=2 and w.get('confidence',0)>=80]
        if len(anchors)<4:continue
        height=float(np.median([w['bbox'][3]-w['bbox'][1] for w in anchors]))
        baseline=float(np.median([w['bbox'][3] for w in anchors]))
        if line['bbox'][3]-line['bbox'][1]>height*.6 or line['bbox'][3]>baseline-height*.5:
            continue
        owned=True
        for fragment in words:
            a,b,c,d=map(int,fragment['bbox'])
            owners=[w for w in other['words'] if any(q.isalpha() for q in w['text'])
                    and w['bbox'][0]<=a and c<=w['bbox'][2]
                    and w['bbox'][1]-height*.35<=b and d<w['bbox'][3]-height*.4]
            if not owners or c<=a or d<=b:
                owned=False;break
            lower=image[d:min(image.shape[0],round(baseline)),a:c]<180
            if not lower.size or np.count_nonzero(lower.any(axis=0))<(c-a)*.6:
                owned=False;break
        if owned:return True
    return False


def refine_color_overlap(lines, rgb, predictor, read_words, cancelled):
    """Recover weak printed words from the original red channel under a seal.

    Whitening coloured pixels can cut a black glyph at a stamp crossing. The
    unmasked colour channel retains that ink. Two independent recognizers must
    agree on every letter and accent; existing digits cannot be changed here.
    """
    if rgb is None:
        return
    channels = rgb.astype(np.int16)
    red = (channels[:,:,0]-channels[:,:,1] > 15) & (channels[:,:,0]-channels[:,:,2] > 15)
    for line in lines:
        changed = False
        for word in line.get('words', []):
            if cancelled():
                return
            old = word['text']; x0,y0,x1,y1 = word['bbox']
            if word.get('confidence', 100) >= 85 or len(old) < 2 or not any(c.isalpha() for c in old):
                continue
            if not red[y0:y1,x0:x1].size or red[y0:y1,x0:x1].mean() < .015:
                continue
            low, high = line.get('recognition_limits', (0, rgb.shape[0]))
            top, bottom = max(low,y0-5), min(high,y1+6)
            left, right = max(0,x0-5), min(rgb.shape[1],x1+8)
            crop = rgb[top:bottom,left:right,0]
            if not crop.size:
                continue
            reading = read_words(crop)
            if len(reading) != 1 or reading[0]['confidence'] < 85:
                continue
            candidate = reading[0]['text']
            prediction = predictor.predict(Image.fromarray(crop)).strip()
            core = lambda s: ''.join(c for c in unicodedata.normalize('NFC', s.casefold()) if c.isalnum())
            if core(candidate) != core(prediction) or not core(candidate):
                continue
            if any(c.isdigit() for c in word.get('source_text',old)+candidate):
                continue
            if candidate != old:
                line.setdefault('ocr_corrections', []).append(dict(before=old, after=candidate,
                    bbox=word['bbox'], method='original_colour_agreement'))
                word.update(text=candidate, confidence=reading[0]['confidence'], visual_verified=True)
                changed = True
        if changed:
            _refresh(line)
