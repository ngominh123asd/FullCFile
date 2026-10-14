"""Verify OCR disagreements against another crop of the same printed pixels.

No vocabulary substitutions, document templates or inferred numeric sequences
are used. A disagreeing reading must survive a second visual recognition pass.
"""
import unicodedata
from difflib import SequenceMatcher

import cv2
import numpy as np
from PIL import Image


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.casefold())
                   if not unicodedata.combining(c))


def _key(text):
    return ''.join(c for c in _fold(text) if c.isalnum())


def _aligned_token(source, reading, index):
    """Find a token at the same position between matching surrounding words."""
    target = reading.split()
    src_keys = [_key(t) for t in source]
    tgt_keys = [_key(t) for t in target]
    matcher = SequenceMatcher(None, src_keys, tgt_keys, autojunk=False)
    for _, a, b, c, d in matcher.get_opcodes():
        if a <= index < b:
            if b-a == d-c:
                return target[c+index-a]
            src_non_empty = [i for i in range(a, b) if src_keys[i]]
            tgt_non_empty = [i for i in range(c, d) if tgt_keys[i]]
            if len(src_non_empty) == len(tgt_non_empty) and index in src_non_empty:
                pos = src_non_empty.index(index)
                return target[tgt_non_empty[pos]]
            if len(src_non_empty) == 1 and len(tgt_non_empty) == 1 and index == src_non_empty[0]:
                return target[tgt_non_empty[0]]
    return None


def _ink_gutter(image, left, right, first, second):
    """Locate interline whitespace instead of trusting overlapping OCR boxes."""
    gap = second-first
    top = max(0, int(first+gap*.25))
    bottom = min(image.shape[0], int(second-gap*.25)+1)
    left, right = max(0, int(left)), min(image.shape[1], int(right))
    if bottom <= top or right <= left:
        return round((first+second)/2)
    ink = np.mean(image[top:bottom,left:right] < 180, axis=1)
    smooth = np.convolve(ink, np.ones(3)/3, mode='same')
    # A one-row gap between an accent and its letter is not an interline
    # gutter. Prefer the widest low-ink band, then its middle, so a detached
    # tone mark stays with the letter even if the detector missed it.
    quiet = np.flatnonzero(smooth<=smooth.min()+.002)
    bands = np.split(quiet,np.where(np.diff(quiet)>1)[0]+1)
    band = max(bands,key=lambda b:(len(b),-abs(top+float(np.median(b))-(first+second)/2)))
    return top+int(np.median(band))


def line_recognition_limits(lines, image_height, image=None, preserve_word_ink=False):
    """Bound each text line by neighboring baselines, even when OCR boxes overlap.

    A tall, damaged word box can include part of the following line. Estimate
    the line center from its ordinary letter boxes before finding midpoints.
    Punctuation and isolated superscripts do not determine the baseline.
    """
    anchors, line_boxes = [], []
    for line in lines:
        boxes = [w['bbox'] for w in line.get('words', [])
                 if any(c.isalnum() for c in w.get('text', ''))]
        if not boxes:
            boxes = [line.get('bbox', [0, 0, 0, image_height])]
        line_boxes.append(line.get('bbox') or [min(b[0] for b in boxes),min(b[1] for b in boxes),
                                               max(b[2] for b in boxes),max(b[3] for b in boxes)])
        heights = [b[3]-b[1] for b in boxes]
        typical = float(np.percentile(heights, 35))
        ordinary = [b for b in boxes if typical*.55 <= b[3]-b[1] <= typical*1.5]
        ordinary = ordinary or boxes
        center = float(np.median([(b[1]+b[3])/2 for b in ordinary]))
        height = float(np.median([b[3]-b[1] for b in ordinary]))
        anchors.append((center, height))
    result = []
    for index, line in enumerate(lines):
        center, height = anchors[index]
        x0, _, x1, _ = line_boxes[index]
        neighbors = [anchor for j, (box, anchor) in enumerate(zip(line_boxes, anchors))
                     if j != index and box[0] < x1 and box[2] > x0
                     and anchor[1] >= height*.5
                     and any(c.isalnum() for c in lines[j].get('text',
                             ' '.join(w.get('text','') for w in lines[j].get('words',[]))))
                     and abs(anchor[0]-center) > min(height, anchor[1])*.6]
        above = [a for a in neighbors if a[0] < center]
        below = [a for a in neighbors if a[0] > center]
        previous = max(above,default=None)
        following = min(below,default=None)
        # A midpoint between baselines is not a whitespace boundary when
        # neighboring lines use different sizes. It can cut an entire tone
        # mark from a large heading or a descender from an underlined label.
        # Reserve the neighboring ordinary glyph bodies, allowing detached
        # marks to occupy the intervening space. Outlier boxes above were
        # excluded so an oversized detection cannot swallow another line.
        low = min(center-height/2,previous[0]+previous[1]/2+1) if previous else 0
        high = max(center+height/2+1,following[0]-following[1]/2-1) if following else image_height
        if image is not None:
            if previous:
                low = _ink_gutter(image,x0,x1,previous[0],center)
            if following:
                high = _ink_gutter(image,x0,x1,center,following[0])
            # Closely spaced underlined text can have more whitespace inside
            # an accented letter than between lines. Do not let that valley
            # clip a confident, normally sized word's observed ink. Oversized
            # detector boxes remain excluded so they cannot absorb a neighbor.
            reliable = [w['bbox'] for w in line.get('words', [])
                        if w.get('confidence',0)>=80 and len(w.get('text',''))>=2
                        and height*.55 <= w['bbox'][3]-w['bbox'][1] <= height*1.8]
            if (preserve_word_ink or line.get('underline')) and len(reliable)>=2:
                top = min(b[1] for b in reliable)-2
                bottom = max(b[3] for b in reliable)+2
                if not previous or top>previous[0]+previous[1]*.15:
                    low = min(low,top)
                if not following or bottom<following[0]-following[1]*.15:
                    high = max(high,bottom)
        if line.get('raster_row_limits'):
            a,b=line['raster_row_limits'];low=max(low,a);high=min(high,b)
        result.append((max(0,round(low)),min(image_height,round(high))))
    return result


def attach_word_limits(lines, image_height, limit_overlaps=False, image=None, preserve_word_ink=False):
    """Allow tall accents beside a short neighboring heading, by horizontal overlap."""
    def box(line):
        if line.get('bbox'):
            return line['bbox']
        words=line.get('words',[])
        return ([min(w['bbox'][0] for w in words),min(w['bbox'][1] for w in words),
                 max(w['bbox'][2] for w in words),max(w['bbox'][3] for w in words)]
                if words else [0,0,0,image_height])
    boxes_by_line={id(line):box(line) for line in lines}
    pixel_limits = line_recognition_limits(lines,image_height,image,preserve_word_ink) if image is not None else None
    baselines = {}
    if image is not None and preserve_word_ink:
        for line in lines:
            glyphs = [w['bbox'] for w in line.get('words',[]) if any(c.isalnum() for c in w['text'])]
            if not glyphs:
                continue
            typical = float(np.percentile([b[3]-b[1] for b in glyphs],35))
            ordinary = [b for b in glyphs if typical*.55<=b[3]-b[1]<=typical*1.5] or glyphs
            baselines[id(line)] = (float(np.median([(b[1]+b[3])/2 for b in ordinary])),
                                   float(np.median([b[3]-b[1] for b in ordinary])))
    for index,line in enumerate(lines):
        x0,y0,x1,y1 = boxes_by_line[id(line)]
        neighbors = [other for other in lines if other is not line and boxes_by_line[id(other)][0] < x1
                     and boxes_by_line[id(other)][2] > x0 and
                     abs((boxes_by_line[id(other)][1]+boxes_by_line[id(other)][3]-y0-y1)/2) < max(1,y1-y0)*4]
        for word in line.get('words', []):
            left,top,right,bottom = word['bbox']
            boxes = [w['bbox'] for other in neighbors for w in other.get('words',[other])
                     if w['bbox'][0] < right and w['bbox'][2] > left]
            center=(top+bottom)/2
            separate=lambda b: abs((b[1]+b[3])/2-center) > min(bottom-top,b[3]-b[1])*.6
            above = [b[3]+1 for b in boxes if (separate(b) and (b[1]+b[3])/2 < center
                                              if limit_overlaps else b[3] <= top)]
            below = [b[1]-1 for b in boxes if (separate(b) and (b[1]+b[3])/2 > center
                                              if limit_overlaps else b[1] >= bottom)]
            word['recognition_limits'] = (max(above,default=0),min(below,default=image_height))
            if pixel_limits is not None:
                word['recognition_limits'] = pixel_limits[index]
                if preserve_word_ink and id(line) in baselines:
                    center,height = baselines[id(line)]
                    nearby=[]
                    for other in neighbors:
                        if id(other) not in baselines:
                            continue
                        anchor=baselines[id(other)]
                        local=[w['bbox'] for w in other.get('words',[]) if w['bbox'][0]<right
                               and w['bbox'][2]>left and any(c.isalnum() for c in w['text'])
                               and anchor[1]*.5<=w['bbox'][3]-w['bbox'][1]<=anchor[1]*1.8]
                        if not local:
                            continue
                        anchor=(float(np.median([(b[1]+b[3])/2 for b in local])),anchor[1])
                        if anchor[1]>=height*.5 and abs(anchor[0]-center)>height*.6:
                            nearby.append(anchor)
                    above = [a for a in nearby if a[0]<center]
                    below = [a for a in nearby if a[0]>center]
                    low = _ink_gutter(image,left-4,right+5,max(above)[0],center) if above else 0
                    high = _ink_gutter(image,left-4,right+5,center,min(below)[0]) if below else image_height
                    if height*.55<=bottom-top<=height*1.6:
                        low=min(low,top-2);high=max(high,bottom+2)
                    low,high=max(0,low),min(image_height,high)
                    global_low,global_high=pixel_limits[index]
                    word['local_ink_recovered'] = bool(
                        (low<global_low and np.any(image[low:global_low,max(0,left):right]<180)) or
                        (high>global_high and np.any(image[global_high:high,max(0,left):right]<180)))
                    word['recognition_limits'] = (low,high)


def word_crop(image, word, line):
    from app.services.ocr_scan_evidence import without_crop_edge_rule
    limits=word.get('recognition_limits',line.get('recognition_limits'))
    # A detector sometimes includes the top of the next line in a word box.
    # Bound that outlier by ordinary neighboring words, allowing descenders
    # and below-letter marks. Do not infer a baseline from short labels or
    # mixed-size text without enough agreeing neighbors.
    ordinary=[w['bbox'] for w in line.get('words',[]) if len(w['text'])>=2
              and any(c.isalpha() for c in w['text']) and w.get('confidence',0)>=75]
    lower_bound=None
    baseline=None
    typical=None
    if len(ordinary)>=4:
        typical=float(np.percentile([b[3]-b[1] for b in ordinary],35))
        normal=[b for b in ordinary if typical*.6<=b[3]-b[1]<=typical*1.35]
        if len(normal)>=4:
            bottoms=[b[3] for b in normal]
            if np.percentile(bottoms,75)-np.percentile(bottoms,25)<typical*.3:
                baseline=float(np.median(bottoms))
                lower_bound=round(baseline+typical*.25)
                low,high=limits or (0,image.shape[0])
                limits=(low,min(high,lower_bound))
    crop,(left,top)=crop_with_accents(image,word['bbox'],limits,return_origin=True,padding_ratio=.45)
    x0,_,x1,_=word['bbox']
    preceding=[w['bbox'][2] for w in line.get('words',[]) if w is not word and w['bbox'][2]<=x0]
    following=[w['bbox'][0] for w in line.get('words',[]) if w is not word and w['bbox'][0]>=x1]
    right=min(left+crop.shape[1],min(following)-1) if following else left+crop.shape[1]
    bounded_left=max(left,max(preceding)+1) if preceding else left
    crop=crop[:,max(0,bounded_left-left):max(0,right-left)]
    left=bounded_left
    def finish(view, origin_y):
        view=without_crop_edge_rule(view)
        if baseline is None or not view.size:
            return view
        # An oversized detection can include the top of the next line's tone
        # mark. Only exclude a clipped, small component below this baseline
        # and outside the horizontal extent of the actual letter bodies.
        # Descenders, commas, and dots beneath Vietnamese letters stay intact.
        _,labels,stats,_=cv2.connectedComponentsWithStats((view<180).astype(np.uint8))
        bodies=[s for s in stats[1:] if s[3]>=typical*.5]
        if not bodies:return view
        a=min(s[0] for s in bodies);b=max(s[0]+s[2] for s in bodies)
        foreign=[k for k,(x,y,w,h,area) in enumerate(stats[1:],1)
                 if y+h==view.shape[0] and h<typical*.35
                 and origin_y+y>baseline+typical*.05 and (x+w<=a or x>=b)]
        if foreign:
            view=view.copy();view[np.isin(labels,foreign)]=255
        return view
    if not limits or not crop.size:
        return finish(crop,top)
    # A whitespace valley can lie BETWEEN the tone and circumflex of one
    # letter. Recover detached components outside that valley, but exclude
    # neighboring glyphs cut by the search window. Never whiten source pixels.
    x0,y0,x1,y1=word['bbox'];height=min(y1-y0,typical*1.2) if typical else y1-y0
    pad=max(6,round(height*.45))
    upper=max(0,y0-pad);lower=min(image.shape[0],y1+pad+1)
    if line.get('raster_row_limits'):
        a,b=line['raster_row_limits'];upper=max(upper,a);lower=min(lower,b)
    if lower_bound is not None:
        lower=min(lower,lower_bound)
    if upper>=top and lower<=top+crop.shape[0]:
        return finish(crop,top)
    area=image[upper:lower,left:left+crop.shape[1]]
    _,labels,stats,_=cv2.connectedComponentsWithStats((area<180).astype(np.uint8))
    extras=[]
    for k,(x,y,w,h,ink) in enumerate(stats[1:],1):
        a,b=upper+y,upper+y+h
        if (y==0 or y+h==area.shape[0] or x==0 or x+w==area.shape[1]
                or h>height*.55 or w>height*.8 or ink<3):
            continue
        if (a<top and b<=y0+2) or (b>top+crop.shape[0] and a>=y1-2):
            extras.append((k,a,b))
    if not extras:
        return finish(crop,top)
    new_top=min(top,min(a for _,a,_ in extras)-2)
    new_bottom=max(top+crop.shape[0],max(b for _,_,b in extras)+2)
    result=np.full((new_bottom-new_top,crop.shape[1]),255,np.uint8)
    result[top-new_top:top-new_top+crop.shape[0]]=crop
    for k,a,b in extras:
        mask=labels[a-upper:b-upper]==k
        result[a-new_top:b-new_top][mask]=area[a-upper:b-upper][mask]
    word['local_ink_recovered']=True
    return finish(result,new_top)


def remove_blank_symbol_words(line, image):
    """Discard a weak symbol only when its region has no remaining ink.

    Graphic extraction can leave a detector token in now-empty background.
    Letters and numerals are retained even if their source is very faint.
    """
    kept=[]
    for word in line.get('words',[]):
        x0,y0,x1,y1=word['bbox'];crop=image[max(0,y0):y1,max(0,x0):x1]
        if (word.get('confidence',100)<80 and not any(c.isalnum() for c in word['text'])
                and crop.size and int(crop.min())>=248):
            line.setdefault('ocr_corrections',[]).append(dict(before=word['text'],after='',
                bbox=word['bbox'],method='empty_graphic_region'))
            continue
        kept.append(word)
    if len(kept)!=len(line.get('words',[])):
        line['words']=kept
        line['text']=' '.join(w['text'] for w in kept)
        line['word_confidences']=[(w['text'],w['confidence']) for w in kept]
        if kept:
            boxes=[w['bbox'] for w in kept]
            line['bbox']=[min(b[0] for b in boxes),min(b[1] for b in boxes),
                          max(b[2] for b in boxes),max(b[3] for b in boxes)]


def crop_with_accents(image, bbox, limits=None, return_origin=False, padding_ratio=.25):
    """Include detached marks missed by the text detector, without rescaling.

    Keep the original crop when it already contains all ink. Expanding the
    background of every line changes the recognizer's apparent font size.
    Neighboring line midpoints bound the search when lines are closely spaced.
    """
    x0,y0,x1,y1 = bbox
    low, high = limits or (0,image.shape[0])
    pad = max(6,round((y1-y0)*padding_ratio))
    left,right = max(0,x0-4),min(image.shape[1],x1+5)
    top,bottom = max(low,y0-pad),min(high,y1+pad+1)
    area = image[top:bottom,left:right]
    ys = np.nonzero(area < 180)[0]
    if ys.size:
        y0,y1 = min(y0,int(ys.min())+top),max(y1,int(ys.max())+top)
    top,bottom = max(low,y0-4),min(high,y1+5)
    crop = image[top:bottom,left:right]
    return (crop,(left,top)) if return_origin else crop


def refine_spacing(line, spaced, image, read_words, cancelled):
    """Re-read changed word boundaries without importing a decoder's letters."""
    words = line.get('words',[])
    source = line['text'].split()
    if spaced == line['text'] or len(source) != len(words):
        return
    target = spaced.split()
    changes = []
    for tag,a,b,c,d in SequenceMatcher(None,source,target,autojunk=False).get_opcodes():
        if tag == 'equal' or not a < b or not c < d:
            continue
        if ''.join(source[a:b]) != ''.join(target[c:d]):
            continue
        if cancelled():
            return
        group = words[a:b]
        bbox = [min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),
                max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)]
        crop,(ox,oy) = crop_with_accents(image,bbox,line.get('recognition_limits'),return_origin=True)
        recognized = read_words(crop)
        # A different segmentation must be supported by the pixels as well as
        # the first decoder. Only a stronger native reading may revise accents.
        if len(recognized) != d-c or [_key(w['text']) for w in recognized] != [_key(t) for t in target[c:d]]:
            continue
        confidence = min(w['confidence'] for w in group)
        improved = min(w['confidence'] for w in recognized) >= max(80,confidence+8)
        updated = []
        for token,w in zip(target[c:d],recognized):
            x0,y0,x1,y1 = w['bbox']
            updated.append(dict(w,text=_keep_edge_punctuation(token,w['text'],100) if improved else token,
                                confidence=w['confidence'] if improved else confidence,
                                bbox=[x0+ox,y0+oy,x1+ox,y1+oy]))
        changes.append((a,b,updated))
    for a,b,updated in reversed(changes):
        words[a:b] = updated
    if changes:
        line['text'] = ' '.join(w['text'] for w in words)
        line['word_confidences'] = [(w['text'],w['confidence']) for w in words]


def refine_weak_accents(line, image, predictor, cancelled, verify_word=None):
    """Recheck uncertain accents using two isolated views of the same word.

    This pass cannot change letters, add words, alter punctuation or touch codes.
    """
    changed = False
    for word in line.get('words', []):
        token = word['text']
        def core(text):
            indexes = [i for i,c in enumerate(text) if c.isalnum()]
            return text[indexes[0]:indexes[-1]+1] if indexes else ''
        letters = core(token)
        confidence = word.get('confidence',100)
        if not letters.isalpha() or not 3 <= len(letters) <= 30 or cancelled():
            continue
        crop = word_crop(image,word,line)
        if confidence >= (95 if verify_word else 75) and not word.get('local_ink_recovered'):
            continue
        if not crop.size or min(crop.shape) < 12:
            continue
        reading = core(predictor.predict(Image.fromarray(crop)).strip())
        if reading.casefold() == letters.casefold() or not reading.isalpha() or _fold(reading) != _fold(letters):
            continue
        sampled = cv2.resize(crop, None, fx=.65, fy=.65, interpolation=cv2.INTER_AREA)
        confirmed = core(predictor.predict(Image.fromarray(sampled)).strip())
        if reading.casefold() != confirmed.casefold():
            # Downsampling can itself lose a small Vietnamese tone. Confirm
            # against an unscaled threshold view before rejecting that ink.
            binary=cv2.threshold(crop,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)[1]
            if np.array_equal(binary,crop):
                continue
            confirmed=core(predictor.predict(Image.fromarray(binary)).strip())
            if reading.casefold()!=confirmed.casefold():
                continue
        if confidence >= 75:
            independent = verify_word(crop)
            if independent['confidence'] < 80 or core(independent['text']).casefold() != reading.casefold():
                # Compare the full printed token, including punctuation, so
                # parentheses/quotes do not distort registration of the word.
                rendered=_keep_edge_punctuation(token,reading,100)
                if not visual_accent_support(crop,token,rendered):
                    continue
        if letters.isupper():
            reading = reading.upper()
        elif letters.istitle():
            reading = reading.title()
        start = token.index(letters)
        reading = token[:start]+reading+token[start+len(letters):]
        line.setdefault('ocr_corrections', []).append(dict(before=token, after=reading,
                                                           bbox=word['bbox'], method='visual_accent_resampling'))
        word['text'] = reading
        changed = True
    if changed:
        line['text'] = ' '.join(w['text'] for w in line['words'])
        line['word_confidences'] = [(w['text'], w['confidence']) for w in line['words']]


def _keep_edge_punctuation(original, reading, confidence):
    if not reading:
        return reading
    old = [i for i,c in enumerate(original) if c.isalnum()]
    new = [i for i,c in enumerate(reading) if c.isalnum()]
    # When original has no alphanumeric characters (e.g. standalone symbols "'", "*", "?", "¿", "°")
    # but reading DOES contain alphanumeric characters (e.g. digit "1", "2", "3", "4", "9"),
    # accept the visual reading instead of preserving the misrecognized symbol.
    if not old:
        if any(c.isdigit() for c in reading) and len(reading) <= 3:
            return reading
        # A slanted list marker (e.g. f)) can initially be boxed as just '/'.
        # The caller still requires matching complete and local visual reads.
        if confidence < 75 and len(original) == 1 and original in '/)(':
            import re
            if re.fullmatch(r'[A-Za-z][.)/]', reading):
                return reading
        if len(original) == 1:
            return original
        return original if not new or confidence >= 75 else reading
    if confidence < 75 or not new:
        if new:
            prefix, suffix = original[:old[0]], original[old[-1]+1:]
            keep = lambda edge: any(c in '–—' or (unicodedata.category(c) in ('Pi','Pf') and ('“' in original or '”' in reading)) for c in edge)
            return ((prefix if keep(prefix) else reading[:new[0]]) + reading[new[0]:new[-1]+1] +
                    (suffix if keep(suffix) else reading[new[-1]+1:]))
        return reading
    return original[:old[0]]+reading[new[0]:new[-1]+1]+original[old[-1]+1:]


def _agreed_edits(original, proposed, confirmed):
    """Apply only character edits corroborated by both visual readings.

    A disagreement on a trailing quote or punctuation must not block an independently
    agreed correction to the letters inside the same token.
    """
    def edits(reading):
        matcher = SequenceMatcher(None, [c.casefold() for c in original],
                                  [c.casefold() for c in reading], autojunk=False)
        return {(a,b): reading[c:d]
                for tag,a,b,c,d in matcher.get_opcodes() if tag != 'equal'}
    first = edits(proposed)
    second = edits(confirmed)
    result = original
    for (a, b) in sorted(set(first.keys()) & set(second.keys()), reverse=True):
        rep1 = first[(a, b)]
        rep2 = second[(a, b)]
        if rep1.casefold() == rep2.casefold():
            chosen = rep1
        else:
            m = SequenceMatcher(None, [c.casefold() for c in rep1], [c.casefold() for c in rep2], autojunk=False)
            common = ''.join(rep1[i:j] for tag, i, j, k, l in m.get_opcodes() if tag == 'equal')
            if common:
                chosen = common
            else:
                continue
        result = result[:a] + chosen + result[b:]
    return result


def _letter_completion(original, alternative):
    """An insertion within one alphabetic token, never a guessed new word/code."""
    if not original.isalpha() or not alternative.isalpha():
        return False
    old,new = _fold(original),_fold(alternative)
    return (0 < len(new)-len(old) <= 2 and
            all(tag in ('equal','insert') for tag,*_ in SequenceMatcher(None,old,new,autojunk=False).get_opcodes()))


def _candidate(original, alternative, confidence):
    if not alternative or original == alternative:
        return False
    # Preserve case and strong readings of identifiers, dates and amounts.
    if original.casefold() == alternative.casefold():
        return False
    if any(c.isdigit() for c in original+alternative):
        # Allow single/short tokens or non-digit originals (like footnote markers, 'Š', '*', '?', '3')
        # to be replaced by digits from visual re-reading
        if any(c.isdigit() for c in alternative) and (not any(c.isdigit() for c in original) or len(original) <= 2):
            return True
        ratio = SequenceMatcher(None, _key(original), _key(alternative)).ratio()
        if ratio >= 0.75 and confidence < 96:
            return True
        if confidence >= 90:
            return False
        return confidence < 75 or ratio >= 0.5
    # Diacritic changes can be necessary even at high Tesseract confidence.
    if _fold(original) == _fold(alternative):
        return True
    if _letter_completion(original,alternative):
        return True
    if confidence >= 90:
        return False
    return confidence < 75 or SequenceMatcher(None, _key(original), _key(alternative)).ratio() >= .5


def visual_accent_support(crop, original, alternative):
    """Resolve an accent disagreement using glyph shapes, not vocabulary.

    Choose a font by the unchanged letters, then compare only the pixels
    that differ between the two readings. Abstain when the font fit is weak.
    """
    if (not crop.size or _fold(original) != _fold(alternative)
            or len(original) != len(alternative) or original == alternative):
        return False
    from app.services.ocr_typography import _fonts, _metrics
    mask = (crop < 160).astype(np.float32)
    ys,xs = np.nonzero(mask)
    if not len(xs):
        return False
    pattern = cv2.resize(mask[ys.min():ys.max()+1,xs.min():xs.max()+1],(160,40),interpolation=cv2.INTER_AREA)
    # Compare antialiased shapes, rather than rewarding the raster stair-step
    # of one font at tiny scan resolutions. The blur is subpixel in this
    # normalized comparison grid and does not alter the recognized document.
    pattern = cv2.GaussianBlur(pattern,(0,0),.5)
    matches=[]
    for i in range(len(_fonts())):
        a,b = _metrics(i,original),_metrics(i,alternative)
        if a is None or b is None:
            continue
        old,new = a[3],b[3]
        region=cv2.dilate((np.abs(new-old)>.15).astype(np.uint8),np.ones((3,3),np.uint8))
        # If changing a diacritic moves much of the normalized letter body,
        # these font masks are not registered well enough to judge the mark.
        if not region.any() or region.mean()>.25:
            continue
        old=cv2.GaussianBlur(old,(0,0),.5)
        new=cv2.GaussianBlur(new,(0,0),.5)
        unchanged=float(np.sum((pattern-(old+new)/2)**2*(1-region))/max(1,(1-region).sum()))
        old_error=float(np.sum((pattern-old)**2*region)/region.sum())
        new_error=float(np.sum((pattern-new)**2*region)/region.sum())
        matches.append((unchanged,old_error,new_error))
    if matches:
        common,old_error,new_error=min(matches)
        if common<.16 and new_error<old_error*.65 and old_error-new_error>.10:
            return True
    from app.services.ocr_glyph_evidence import registered_accent_support
    return registered_accent_support(crop,original,alternative)


def alternate_accent_support(crop, original, alternative, verify_word):
    """Corroborate tone-only edits with two independent binarized OCR views.

    The grayscale reader may confuse a faint hook with a tilde. A change still
    needs the same letters and agreement of both threshold views, in addition
    to the caller's two neural readings. Identifiers cannot enter this path.
    """
    if (_fold(original)!=_fold(alternative) or original==alternative
            or any(c.isdigit() for c in original+alternative) or not crop.size):
        return False
    threshold,binary=cv2.threshold(crop,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)
    softer=cv2.threshold(crop,min(240,threshold+40),255,cv2.THRESH_BINARY)[1]
    if np.array_equal(binary,softer):
        return False
    core=lambda s: ''.join(c for c in unicodedata.normalize('NFC',s.casefold()) if c.isalpha())
    for view in (binary,softer):
        reading=verify_word(view)
        if reading['confidence']<60 or core(reading['text'])!=core(alternative):
            return False
    return True


def refine_punctuation(line, prediction, image, predictor, cancelled, verify_word):
    """Verify edge marks separately from letters, preserving numbers and case.

    The lexical pass intentionally retains confidently observed punctuation.
    A missing mark or a mark made from neighboring ink needs isolated visual
    agreement and a better glyph fit before that protection can be lifted.
    """
    import re
    from app.services.ocr_glyph_evidence import registered_accent_support,punctuation_shape_support
    words=line.get('words',[]);source=[w['text'] for w in words]
    updates={}
    removed=set()
    split=lambda t:re.fullmatch(r'([\W_]*)([^\W_](?:.*[^\W_])?)([\W_]*)',t)
    for index,word in enumerate(words):
        if cancelled():return
        original=word['text'];candidate=_aligned_token(source,prediction,index)
        old,new=split(original),split(candidate or '')
        if (not old or not new or original==candidate or
                old[2].casefold()!=new[2].casefold() or
                len(old[1]+old[3]+new[1]+new[3])>6 or word.get('inline_runs')):
            continue
        # Never alter internal separators in dates, codes, URLs or decimals.
        proposed=new[1]+old[2]+new[3]
        if proposed==original:continue
        crop=word_crop(image,word,line)
        if not crop.size:continue
        core=lambda t:''.join(c for c in t.casefold() if c.isalnum())
        independent=verify_word(crop)
        if independent['confidence']<80 or core(independent['text'])!=core(proposed):
            binary=cv2.threshold(crop,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)[1]
            if np.array_equal(binary,crop):continue
            independent=verify_word(binary)
        if independent['confidence']<80 or core(independent['text'])!=core(proposed):continue
        if old[1]!=new[1] and independent['text'].casefold()!=proposed.casefold():continue
        isolated=predictor.predict(Image.fromarray(crop)).strip()
        local=split(isolated)
        if not local or local[2].casefold()!=old[2].casefold():continue
        # Verify each changed edge. Disagreement on an unchanged comma must
        # neither erase that comma nor block repair of a spurious prefix.
        if old[1]!=new[1] and local[1]!=new[1]:continue
        if old[3]!=new[3] and local[3]!=new[3]:continue
        if not punctuation_shape_support(crop,original,proposed):continue
        updates[index]=proposed
    predicted=prediction.split()
    for index,word in enumerate(words[1:-1],1):
        if cancelled():return
        if not word['text'] or any(c not in '!?^ˆ_' for c in word['text']) or word.get('inline_runs'):
            continue
        neighbors=[words[index-1]['text'],words[index+1]['text']]
        if not all(any(c.isalnum() for c in t) for t in neighbors):continue
        if not any([_key(t) for t in predicted[i:i+2]]==[_key(t) for t in neighbors]
                   for i in range(len(predicted)-1)):continue
        group=words[index-1:index+2]
        box=[min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),
             max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)]
        crop=word_crop(image,dict(bbox=box),line)
        original=' '.join(w['text'] for w in group);proposed=' '.join(neighbors)
        independent=verify_word(crop)
        if independent['confidence']<80 or independent['text'].casefold()!=proposed.casefold():continue
        if predictor.predict(Image.fromarray(crop)).strip().casefold()!=proposed.casefold():continue
        if punctuation_shape_support(crop,original,proposed):removed.add(index)
    if updates or removed:
        for index,after in updates.items():
            word=words[index]
            line.setdefault('ocr_corrections',[]).append(dict(before=word['text'],after=after,
                bbox=word['bbox'],method='punctuation_pixel_agreement'))
            word['text']=after
        for index in removed:
            line.setdefault('ocr_corrections',[]).append(dict(before=words[index]['text'],after='',
                bbox=words[index]['bbox'],method='punctuation_pixel_agreement'))
        words=[w for i,w in enumerate(words) if i not in removed]
        line['words']=words
        line['text']=' '.join(w['text'] for w in words)
        line['word_confidences']=[(w['text'],w['confidence']) for w in words]


def refine_with_context(line, prediction, image, predictor, cancelled, verify_word=None):
    """Accept a changed token only if a local visual re-read corroborates it."""
    words = line.get('words', [])
    source = line['text'].split()
    if len(words) != len(source) or any(w['text'] != t for w, t in zip(words, source)):
        return
    replacements = {}
    contexts = {}
    for index, (word, token) in enumerate(zip(words, source)):
        if cancelled():
            return
        alternative = _aligned_token(source, prediction, index)
        if (verify_word is not None and alternative and token!=alternative
                and token.casefold()==alternative.casefold()
                and token.isalpha() and alternative.isalpha()):
            # Case can be misread even when every accent is present. Require
            # two literal crop readings and the printed glyph shape, rather
            # than applying sentence/title capitalization from language rules.
            crop=word_crop(image,word,line)
            independent=verify_word(crop)
            from app.services.ocr_glyph_evidence import registered_accent_support
            if (independent['confidence']>=70 and independent['text']==alternative
                    and predictor.predict(Image.fromarray(crop)).strip()==alternative
                    and registered_accent_support(crop,token,alternative)):
                replacements[index]=alternative
            continue
        if (token.endswith('.') and token[:-1].isalpha() and len(token)>=4
                and alternative==token[:-1] and verify_word is not None):
            # A low Vietnamese tone or scan speck can be read as a terminal
            # period. Removing it needs independent OCR AND absent period ink;
            # preserve actual punctuation, abbreviations, codes and amounts.
            crop=word_crop(image,word,line)
            independent=verify_word(crop)
            from app.services.ocr_glyph_evidence import registered_accent_support
            if (independent['confidence']>=85 and independent['text']==alternative
                    and registered_accent_support(crop,token,alternative)):
                replacements[index]=alternative
                continue
        alternative = _keep_edge_punctuation(token, alternative, word['confidence'])
        if not _candidate(token, alternative, word['confidence']):
            # A recognizer can be confidently wrong about a single printed
            # letter. Only reopen this case when two independent crop readers
            # agree exactly; confidence or language context alone is not enough.
            if (not alternative or not token.isalpha() or not alternative.isalpha()
                    or len(token) != len(alternative) or word['confidence'] < 90
                    or sum(a.casefold()!=b.casefold() for a,b in zip(token,alternative)) != 1
                    or verify_word is None):
                continue
            crop = word_crop(image,word,line)
            independent = verify_word(crop)
            if (independent['confidence'] < 90 or independent['text'].casefold() != alternative.casefold()
                    or predictor.predict(Image.fromarray(crop)).strip().casefold() != alternative.casefold()):
                continue
        start, stop = max(0, index-1), min(len(words), index+2)
        key = start, stop
        if key not in contexts:
            neighbors = words[start:stop]
            x0 = min(w['bbox'][0] for w in neighbors)
            y0 = min(w['bbox'][1] for w in neighbors)
            x1 = max(w['bbox'][2] for w in neighbors)
            y1 = max(w['bbox'][3] for w in neighbors)
            crop = crop_with_accents(image, (x0,y0,x1,y1), line.get('recognition_limits'))
            if not crop.size:
                continue
            if start == 0 and stop == len(words):
                # Short lines already fill the first crop. Change the visual
                # input instead of counting an identical inference twice.
                crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
            contexts[key] = predictor.predict(Image.fromarray(crop))
        confirmation = _aligned_token(source[start:stop], contexts[key], index-start)
        if confirmation is None:
            continue
        confirmation = _keep_edge_punctuation(token, confirmation, word['confidence'])
        proposal = alternative
        alternative = _agreed_edits(token, proposal, confirmation)
        isolated = None
        if (proposal.casefold() != confirmation.casefold()
                and (confirmation.casefold()==token.casefold()
                     or _candidate(token, confirmation, word['confidence']))):
            if cancelled():
                return
            crop = word_crop(image,word,line)
            isolated = _keep_edge_punctuation(token, predictor.predict(Image.fromarray(crop)).strip(), word['confidence'])
            # A third visual reading can break a tie between two different
            # proposals. It cannot introduce an uncorroborated replacement.
            third = _agreed_edits(token, proposal, isolated)
            if third == token:
                third = _agreed_edits(token, confirmation, isolated)
            if third != token:
                alternative = third
        if alternative == token:
            continue
        # A decoder may turn a nearby pen stroke into new punctuation. Repeated
        # predictions from that decoder are not independent evidence for adding
        # an edge symbol to a word which the first reader saw without it.
        kept_edges = _keep_edge_punctuation(token,alternative,100)
        old_core = [i for i,c in enumerate(token) if c.isalnum()]
        new_core = [i for i,c in enumerate(alternative) if c.isalnum()]
        if old_core and new_core:
            old_edges = token[:old_core[0]]+token[old_core[-1]+1:]
            new_edges = alternative[:new_core[0]]+alternative[new_core[-1]+1:]
            if new_edges and new_edges!=old_edges:
                independent = verify_word(word_crop(image,word,line)) if verify_word else None
                if not independent or independent['confidence']<80 or _agreed_edits(token,alternative,independent['text'])!=alternative:
                    alternative = kept_edges
        if alternative == token:
            continue
        lexical = lambda text: ''.join(c for c in text if c.isalpha())
        if _letter_completion(lexical(token),lexical(alternative)):
            # A detector can confidently box two printed letters as one. Both
            # contextual readings still need an independent isolated crop to
            # restore letters; confidence alone must not veto visible ink.
            if verify_word is None:
                continue
            crop = word_crop(image,word,line)
            independent = verify_word(crop)
            if (independent['confidence'] < 80 or
                    lexical(independent['text']).casefold() != lexical(alternative).casefold()):
                continue
        old_marks = {c for c in unicodedata.normalize('NFD',token) if unicodedata.combining(c)}
        new_marks = {c for c in unicodedata.normalize('NFD',alternative) if unicodedata.combining(c)}
        independently_confirmed = False
        glyph_confirmed = False
        if (verify_word is not None and word['confidence'] >= 75 and
                _fold(token) == _fold(alternative)):
            # Repeating the same decoder can repeat the same accent bias.
            # Replacing an existing strong diacritic requires an independent
            # recognizer on the isolated word, not another language-model vote.
            crop = word_crop(image,word,line)
            independent = verify_word(crop)
            if independent['confidence'] >= 80:
                agreed = _agreed_edits(token,alternative,independent['text'] or token)
            else:
                agreed = token
            if agreed == token:
                # Tesseract can repeat a confident accent error at every
                # crop scale. Compare changed glyph pixels and independent
                # threshold views before overriding the grayscale reading.
                supported = visual_accent_support(crop,token,alternative)
                if not supported and len(old_marks)==len(new_marks):
                    # Expanded crops can include a tiny stroke from the
                    # neighboring line. Also compare the detector's own
                    # box when exchanging (not removing) an accent.
                    x0,y0,x1,y1=word['bbox']
                    supported = visual_accent_support(image[max(0,y0):y1,max(0,x0):x1],token,alternative)
                if not supported and len(new_marks)>=len(old_marks):
                    # Segmentation can change Tesseract's tone reading
                    # with a single pixel of surrounding whitespace. The
                    # detector's padded box offers a second bounded view;
                    # both independent thresholds must confirm the same
                    # accent already read in the neural context crops.
                    # This route cannot remove a detected accent.
                    x0,y0,x1,y1=word['bbox']
                    tight=image[max(0,y0-3):y1+3,max(0,x0-3):x1+3]
                    supported=alternate_accent_support(tight,token,alternative,verify_word)
                if not supported:
                    supported = alternate_accent_support(crop,token,alternative,verify_word)
                if not supported:
                    continue
                glyph_confirmed = True
            else:
                alternative = agreed
            independently_confirmed = True
        # Losing a confidently detected accent needs one more view of the
        # actual word. Language context alone can suppress a faint printed mark.
        marks = lambda text: sum(bool(unicodedata.combining(c)) for c in unicodedata.normalize('NFD',text))
        if word['confidence'] >= 90 and marks(alternative) < marks(token) and not independently_confirmed:
            if cancelled():
                return
            if isolated is None:
                crop = word_crop(image,word,line)
                isolated = _keep_edge_punctuation(token, predictor.predict(Image.fromarray(crop)).strip(), word['confidence'])
            alternative = _agreed_edits(token, alternative, isolated)
            if alternative == token:
                continue
        if token.isupper() and len(token)>1:
            alternative = alternative.upper()
        elif token[:1].isupper() and token[1:].islower():
            alternative = alternative[:1].upper()+alternative[1:]
        # Multiple contextual crops still use the same decoder. They can
        # repeat an insertion/deletion (PCCC -> PCC, 1:2020 -> 11:2020), or
        # invent a tone on an already correct high-confidence word. Require
        # independent pixel recognition before overriding these readings.
        if verify_word is not None and (
                (word['confidence'] >= 75 and _key(token) != _key(alternative))
                or word['confidence'] >= 90):
            crop = word_crop(image,word,line)
            independent = verify_word(crop)
            core = lambda value: ''.join(c for c in unicodedata.normalize('NFC',value.casefold()) if c.isalnum())
            if (not glyph_confirmed and
                    (independent['confidence'] < 80 or core(independent['text']) != core(alternative))):
                continue
            if word['confidence'] >= 90 and _fold(token)==_fold(alternative) and not glyph_confirmed:
                x0,y0,x1,y1=word['bbox']
                tight=image[max(0,y0-3):y1+3,max(0,x0-3):x1+3]
                other=verify_word(tight)
                if other['confidence']<80 or core(other['text'])!=core(alternative):
                    continue
        replacements[index] = alternative
    if not replacements:
        return
    updated = [dict(w, text=replacements.get(i, w['text'])) for i, w in enumerate(words)]
    line.setdefault('ocr_corrections',[]).extend([
        {'before': source[i], 'after': value, 'bbox': words[i]['bbox'], 'method': 'visual_context_agreement'}
        for i, value in replacements.items()
    ])
    line['words'] = updated
    line['word_confidences'] = [(w['text'], w['confidence']) for w in updated]
    line['text'] = ' '.join(w['text'] for w in updated)
