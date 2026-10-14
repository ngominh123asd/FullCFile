"""Re-read weak segmentation using line geometry and independent crop views."""
from difflib import SequenceMatcher
import unicodedata

import cv2
import numpy as np
from PIL import Image


def _key(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.casefold())
                   if c.isalnum() and not unicodedata.combining(c))


def refine_uncertain_line(line, image, predictor, read_words, cancelled, neighbors=()):
    """Retry failed page segmentation with two readers of the bounded line."""
    from app.services.ocr_text_refinement import crop_with_accents
    words0=line.get('words',[])
    clipped_tail=bool(len(words0)>=8 and len(words0[-1]['text'])<=2 and words0[-1]['text'].isalpha())
    if (line.get('confidence', 100) >= 60 and not clipped_tail) or cancelled():
        return False
    box=list(line['bbox'])
    limits=line.get('recognition_limits')
    bounded_tail=False
    reliable=[w['bbox'] for w in words0 if w.get('confidence',0)>=85 and len(w['text'])>=2]
    if clipped_tail and len(reliable)>=6:
        typical=float(np.median([b[3]-b[1] for b in reliable]))
        tail=words0[-1]
        if tail.get('confidence',100)<40 and tail['bbox'][3]-tail['bbox'][1]>typical*1.7:
            # A scan rule can attach the last word to the next line. Use the
            # baseline of the reliable words, retaining their tallest accents,
            # instead of rereading both lines or clipping the upper marks.
            top=min(b[1] for b in reliable)
            bottom=round(float(np.quantile([b[3] for b in reliable],.65)))
            low=max(0,round(top-typical*.25))
            high=min(image.shape[0],round(bottom+typical*.2))
            for other in neighbors:
                if other is line or other.get('confidence',0)<80:
                    continue
                a,b,c,d=other['bbox']
                if a>=box[2] or c<=box[0]:continue
                if d<=top:low=max(low,(d+top)//2)
                if b>=bottom:high=min(high,(bottom+b)//2)
            if high>low:
                box[1:4:2]=[top,bottom]
                limits=(low,high)
                bounded_tail=True
    nearby=[n for n in neighbors if n is not line and n.get('confidence',0)>=80
            and abs(n['bbox'][1]-box[1])<max(80,box[3]-box[1])*5
            and n['bbox'][0]<box[2] and n['bbox'][2]>box[0]
            and len(n.get('words',[]))>=8]
    if nearby:
        box[0]=min(box[0],min(n['bbox'][0] for n in nearby))
        box[2]=max(box[2],max(n['bbox'][2] for n in nearby))
    crop, (ox, oy) = crop_with_accents(image, box, limits, True)
    if not crop.size:
        return False
    words = read_words(crop)
    if not words:
        return False
    unchanged_prefix=(bounded_tail and len(words)==len(words0)
                      and [w['text'] for w in words[:-1]]==[w['text'] for w in words0[:-1]]
                      and words[-1]['confidence']>=85)
    if min(w['confidence'] for w in words) < 80 and not unchanged_prefix:
        return False
    candidate = ' '.join(w['text'] for w in words)
    prediction = predictor.predict(Image.fromarray(crop)).strip()
    if _key(candidate) != _key(prediction):
        return False
    if unchanged_prefix and words[-1]['text'].casefold()!=prediction.split()[-1].casefold():
        return False
    # Two readers of the whole bounded line can recover broken segmentation.
    # Similarity to a corrupt fragment alone must not veto matching evidence.
    if not nearby and SequenceMatcher(None,_key(line['text']),_key(candidate)).ratio()<.5:
        return False
    if candidate == line['text']:
        return False
    line.setdefault('ocr_corrections', []).append(dict(before=line['text'], after=candidate,
                                                      method='visual_line_segmentation'))
    line['words'] = [dict(w, bbox=[w['bbox'][0]+ox, w['bbox'][1]+oy,
                                 w['bbox'][2]+ox, w['bbox'][3]+oy]) for w in words]
    line.update(text=candidate, confidence=min(w['confidence'] for w in words),
                word_confidences=[(w['text'], w['confidence']) for w in words])
    boxes = [w['bbox'] for w in line['words']]
    line['bbox'] = [min(b[0] for b in boxes), min(b[1] for b in boxes),
                    max(b[2] for b in boxes), max(b[3] for b in boxes)]
    return True


def refine_underlined_line(line, image, predictor, read_words, cancelled):
    """Recover word boundaries obscured by a printed underline, using pixels."""
    from app.services.ocr_text_refinement import crop_with_accents
    from app.services.ocr_image_evidence import without_underline
    if not line.get('words'):
        return
    crop, (ox, oy) = crop_with_accents(image, line['bbox'], line.get('recognition_limits'), True)
    cleaned, found = without_underline(crop)
    if not found or cancelled():
        return
    original = line['text']
    readings = [predictor.predict(Image.fromarray(view)).strip() for view in (crop, cleaned)]
    digits = lambda text: ''.join(c for c in text if c.isdigit())
    for view in (cleaned, crop):
        words = read_words(view)
        candidate = ' '.join(w['text'] for w in words)
        confidence = sum(w['confidence']*len(w['text']) for w in words)/max(1, sum(len(w['text']) for w in words))
        if (not words or confidence < 80 or min(w['confidence'] for w in words) < 65
                or SequenceMatcher(None, _key(original), _key(candidate)).ratio() < .85):
            continue
        if digits(candidate) != digits(original):
            # Never recover a numeral from an expected list sequence.
            if confidence < 90 or any(digits(r) != digits(candidate) for r in readings):
                continue
        # A dot/descender can touch the underline. The original is therefore
        # another candidate, not just a backup after destructive preprocessing.
        if not any([_key(t) for t in r.split()] == [_key(w['text']) for w in words] for r in readings):
            continue
        if all(any(len(r.split()) == len(words) and r.split()[i].strip('.,:;').casefold() ==
                   word['text'].strip('.,:;').casefold() for r in readings) for i, word in enumerate(words)):
            break
    else:
        return
    line['words'] = [dict(w, bbox=[w['bbox'][0]+ox, w['bbox'][1]+oy,
                                  w['bbox'][2]+ox, w['bbox'][3]+oy]) for w in words]
    line.update(text=candidate, confidence=confidence, underline=True,
                word_confidences=[(w['text'], w['confidence']) for w in words])
    if candidate != original:
        line.setdefault('ocr_corrections', []).append(dict(before=original, after=candidate,
                                                            method='visual_underline_agreement'))
    return True


def span_crop(image, line, start, stop, neighbors=()):
    """Recover faint/tall ink when a detector boxed only a dot or letter stem.

    Adjacent words bound horizontal expansion; neighboring lines bound vertical
    expansion. Never estimate the characters or length of a number from context.
    """
    words=line['words'];group=words[start:stop]
    heights=[w['bbox'][3]-w['bbox'][1] for w in words if w['confidence']>=80]
    height=float(np.median(heights)) if heights else line['bbox'][3]-line['bbox'][1]
    x0=min(w['bbox'][0] for w in group);x1=max(w['bbox'][2] for w in group)
    y0=min(w['bbox'][1] for w in group);y1=max(w['bbox'][3] for w in group)
    if y1-y0 < height*.65:
        y0=min(y0,line['bbox'][1]);y1=max(y1,line['bbox'][3])
    x0=max(0,round(x0-height*.55),words[start-1]['bbox'][2]+1 if start else 0)
    x1=min(image.shape[1],round(x1+height*.55),words[stop]['bbox'][0]-1 if stop<len(words) else image.shape[1])
    low,high=line.get('recognition_limits',(0,image.shape[0]))
    if neighbors:
        boxes=[other['bbox'] for other in neighbors if other is not line
               and other['bbox'][0]<x1 and other['bbox'][2]>x0]
        if not boxes:
            # A short heading in another column cannot constrain this span.
            low,high=0,image.shape[0]
        above=[box[3] for box in boxes if box[3]<=y0]
        below=[box[1] for box in boxes if box[1]>=y1]
        # A damaged word box can overlap a neighboring line. Do not discard
        # the baseline limits simply because no whole box is above/below it.
        low=max(low,(max(above)+y0)//2) if above else low
        high=min(high,(min(below)+y1)//2) if below else high
    y0=max(low,round(y0-height*.4));y1=min(high,round(y1+height*.1)+1)
    return image[y0:y1,x0:x1],[x0,y0,x1,y1]


def refine_overlapping_words(line, image, predictor, read_words, cancelled, neighbors=()):
    """Reread weak, overlapping detector boxes rather than deleting by text.

    A detached quote/stem can be boxed twice and decoded as an extra letter.
    Require matching letters from two readers of the complete bounded span;
    numeric annotations cannot be removed or invented by this path.
    """
    words = line.get('words', [])
    lexical = lambda text: ''.join(c for c in unicodedata.normalize('NFC',text.casefold()) if c.isalnum())
    digits = lambda text: ''.join(c for c in text if c.isdigit())
    for index in range(len(words)-1, -1, -1):
        word = words[index]
        if word.get('confidence',100) >= 65 or any(c.isdigit() for c in word['text']):
            continue
        x0,y0,x1,y1 = word['bbox']
        start,stop = max(0,index-2),min(len(words),index+2)
        others = words[start:index]+words[index+1:stop]
        if not any(min(x1,w['bbox'][2])-max(x0,w['bbox'][0]) >= (x1-x0)*.45
                   and min(y1,w['bbox'][3])-max(y0,w['bbox'][1]) >= (y1-y0)*.4 for w in others):
            continue
        if cancelled():
            return
        crop,box = span_crop(image,line,start,stop,neighbors)
        if not crop.size:
            continue
        reading = read_words(crop)
        if not reading or min(w['confidence'] for w in reading) < 85:
            continue
        candidate = ' '.join(w['text'] for w in reading)
        other = predictor.predict(Image.fromarray(crop)).strip()
        before = ' '.join(w['text'] for w in words[start:stop])
        if (candidate == before or lexical(candidate) != lexical(other)
                or digits(candidate) != digits(before)
                or SequenceMatcher(None,lexical(before),lexical(candidate)).ratio() < .7):
            continue
        replacement = [dict(w,bbox=[w['bbox'][0]+box[0],w['bbox'][1]+box[1],
                                     w['bbox'][2]+box[0],w['bbox'][3]+box[1]]) for w in reading]
        words[start:stop] = replacement
        line['text'] = ' '.join(w['text'] for w in words)
        line['word_confidences'] = [(w['text'],w['confidence']) for w in words]
        line.setdefault('ocr_corrections',[]).append(dict(before=before,after=candidate,
                                                        method='visual_overlap_agreement'))
        # The word indices changed. Reconsider other regions on a later pass.
        return True


def refine_weak_spans(line, prediction, image, predictor, cancelled, recognize_code=None, neighbors=(), recognize_words=None):
    """Repair a split glyph only after complete crops corroborate the reading.

    Confident identifiers and ordinary word disagreements are left to the
    existing token verifier. This path handles weak, incorrectly segmented
    spans which cannot be aligned one token to one token.
    """
    words=line.get('words',[]);source=line['text'].split();target=prediction.split()
    if len(source)!=len(words) or any(t!=w['text'] for t,w in zip(source,words)):
        return
    changes=[]
    for tag,a,b,c,d in SequenceMatcher(None,[_key(t) for t in source],[_key(t) for t in target],autojunk=False).get_opcodes():
        # An absent decoder token is not visual evidence of an empty region.
        # In particular, small footnote markers and punctuation are often
        # omitted by a language decoder even though their ink is present.
        if tag=='equal' or not (0<b-a<=6 and 0<d-c<=6):
            continue
        group=words[a:b]
        if min(w['confidence'] for w in group)>=75:
            continue
        before=' '.join(source[a:b]);proposed=' '.join(target[c:d])
        # Equal-count lexical repairs are already handled with word context.
        # Revisit them here only when geometry is broken or the span is mixed
        # letters/digits/symbols, where the first detector is especially weak.
        height=line['bbox'][3]-line['bbox'][1]
        broken=any(w['bbox'][3]-w['bbox'][1]<height*.4 for w in group)
        if b-a==d-c and not broken and all(t.isalpha() for t in source[a:b]+target[c:d]):
            continue
        if cancelled():
            return
        crop,box=span_crop(image,line,a,b,neighbors)
        if not crop.size:
            continue
        local=predictor.predict(Image.fromarray(crop)).strip()
        if not local or len(local)>max(len(before),len(proposed))*1.5+3:
            continue
        binary=cv2.threshold(crop,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)[1]
        confirmed=predictor.predict(Image.fromarray(binary)).strip()
        independent=[]
        if recognize_words is not None and _key(local)==_key(proposed):
            reading=recognize_words(crop)
            score=sum(w['confidence']*len(w['text']) for w in reading)/max(1,sum(len(w['text']) for w in reading))
            if score>=80 and _key(' '.join(w['text'] for w in reading))==_key(local):
                independent=reading
                local=' '.join(w['text'] for w in reading)
        if local!=confirmed and not independent:
            continue
        corroborated=_key(local)==_key(proposed)
        if recognize_code is not None and any(ch.isdigit() for ch in local):
            reading,confidence=recognize_code(crop)
            corroborated=confidence>=.85 and _key(reading)==_key(local)
            if not corroborated and confidence>=.85:
                # A slanted neighbor can intrude into expanded horizontal
                # padding. Retry against the original right edge, retaining
                # the recovered ascenders and left edge. Accept this view only
                # if the independent recognizer reads the same characters.
                edge=max(w['bbox'][2] for w in group)-box[0]+4
                tighter=crop[:,:min(crop.shape[1],edge)]
                if tighter.size and tighter.shape[1]<crop.shape[1]:
                    third=predictor.predict(Image.fromarray(tighter)).strip()
                    if _key(third)==_key(reading):
                        local=third;corroborated=True
        if not corroborated or _key(local)==_key(before):
            continue
        # Keep observed surrounding punctuation when its glyphs are outside
        # the replacement's alphanumeric span. Do not import guessed symbols.
        if all(not t.isalnum() for t in before) and not any(ch.isalnum() for ch in local):
            continue
        updated=[dict(group[0],text=local,bbox=box,confidence=min(w['confidence'] for w in group))]
        if independent and local==' '.join(w['text'] for w in independent):
            updated=[dict(w,bbox=[w['bbox'][0]+box[0],w['bbox'][1]+box[1],
                                 w['bbox'][2]+box[0],w['bbox'][3]+box[1]]) for w in independent]
        changes.append((a,b,updated,box))
    for a,b,updated,box in reversed(changes):
        line.setdefault('ocr_corrections',[]).append(dict(before=' '.join(source[a:b]),after=' '.join(w['text'] for w in updated),
                                                        bbox=box,method='visual_span_agreement'))
        words[a:b]=updated
    if changes:
        # A crop decoder may restore a word boundary inside one detector box.
        # Keep the span together for geometry; downstream reads must not align
        # its tokens against unrelated neighboring word boxes.
        line['text']=' '.join(w['text'] for w in words)
        line['word_confidences']=[(w['text'],w['confidence']) for w in words]
