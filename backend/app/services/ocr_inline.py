"""Recover reduced raised digits from pixels, independently of prose decoding."""
import unicodedata
import math

import cv2
import numpy as np


def script_candidates(line, image):
    """Find raised components beside letters, never accents above letters."""
    words = line.get('words', [])
    heights = [w['bbox'][3]-w['bbox'][1] for w in words
               if any(c.isalnum() for c in w['text'])]
    if not heights:
        return []
    height = float(np.median(heights))
    x0,y0,x1,y1 = line['bbox']
    low,_ = line.get('recognition_limits',(0,image.shape[0]))
    y0 = max(low,y0-round(height*.35))
    x1 = min(image.shape[1], x1+round(height*.5))
    area = image[y0:y1, x0:x1]
    if not area.size:
        return []
    binary = cv2.threshold(area,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)[1]
    _,_,stats,_ = cv2.connectedComponentsWithStats(binary)
    substantial = [s for s in stats[1:] if s[3] >= height*.45 and s[4] >= height]
    if len(substantial) < 3:
        return []
    baseline = float(np.median([y+h for x,y,w,h,a in substantial]))
    glyph_height = float(np.percentile([h for x,y,w,h,a in substantial],75))
    candidates = []
    for x,y,w,h,a in stats[1:]:
        if not (glyph_height*.3 <= h <= glyph_height*.78
                and w >= glyph_height*.12 and a >= glyph_height
                and y+h < baseline-glyph_height*.28):
            continue
        # A diacritic shares the horizontal extent of a full-height letter.
        if any(min(x+w,sx+sw)-max(x,sx) > min(w,sw)*.2
               and sh >= glyph_height*.35 and sy+sh > baseline-glyph_height*.2
               and sy+sh > y+h for sx,sy,sw,sh,sa in stats[1:]):
            continue
        candidates.append([int(x+x0),int(y+y0),int(x+w+x0),int(y+h+y0)])
    groups = []
    for b in sorted(candidates):
        if (groups and b[0]-groups[-1][2] < glyph_height*.2
                and abs(b[1]-groups[-1][1]) < glyph_height*.2):
            groups[-1] = [groups[-1][0],min(b[1],groups[-1][1]),b[2],max(b[3],groups[-1][3])]
        else:
            groups.append(b)
    return groups


def _letters(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.casefold())
                   if c.isalnum() and not unicodedata.combining(c))


def _raised_symbol(image, reading):
    """Disambiguate reduced numerals from full-size quotation marks optically.

    Both isolated recognizers can read a curved double quote as two digits.
    Compare installed glyph outlines, including their aspect ratios, before
    creating a superscript. An ambiguous match leaves the first reading intact.
    """
    from app.services.ocr_typography import _fonts, _glyph_metrics
    if not image.size:
        return None
    mask=cv2.threshold(image,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)[1]
    yy,xx=np.nonzero(mask)
    if not len(xx):
        return None
    mask=mask[yy.min():yy.max()+1,xx.min():xx.max()+1]/255.
    h,w=mask.shape
    pattern=cv2.resize(mask.astype(np.float32),(80,80),interpolation=cv2.INTER_AREA)
    scores={}
    for symbol in dict.fromkeys([reading,'“','”','‘','’']):
        fits=[]
        for i in range(len(_fonts())):
            metric=_glyph_metrics(i,symbol)
            if metric is None:
                continue
            fw,fh,_,reference=metric[:4]
            reference=cv2.resize(reference,(80,80),interpolation=cv2.INTER_AREA)
            fits.append(float(np.mean(abs(pattern-reference)))+.3*abs(math.log((w/h)/(fw/fh))))
        if fits:
            scores[symbol]=min(fits)
    if not scores:
        return None
    ranked=sorted(scores,key=scores.get)
    best=ranked[0]
    # Quote variants can resemble each other; the relevant contest is with
    # the proposed numeral rather than between opening/closing quote styles.
    quote=min(('“','”','‘','’'),key=lambda s:scores.get(s,float('inf')))
    if scores[quote]<.25 and scores[quote]+.06<scores.get(reading,float('inf')):
        return quote
    if reading.isdecimal() and scores[reading]+.04<scores[quote]:
        return reading
    return best if best==reading and not reading.isdecimal() and scores[best]<.25 else None


def recover_inline_scripts(lines, image, read_codes, read_text, cancelled):
    """Use two visual readers; no numbering sequence or numeric coercion."""
    entries = [(line,box) for line in lines for box in script_candidates(line,image)]
    if not entries or cancelled():
        return
    crops = [image[max(0,b[1]-5):b[3]+5,max(0,b[0]-5):b[2]+5] for _,b in entries]
    readings = read_codes(crops)
    for (line,box),crop,(reading,confidence) in zip(entries,crops,readings):
        if cancelled():
            return
        if not (reading.isdecimal() or reading in '“”‘’') or not reading or confidence < .9:
            continue
        confirmation,_ = read_text(crop, isolated=True)
        symbol=_raised_symbol(image[box[1]:box[3],box[0]:box[2]],reading)
        if symbol is None:
            continue
        if confirmation != reading:
            # Prose decoders often disagree on a standalone curved quote.
            # An independent glyph reader plus the outline comparison may
            # confirm that punctuation, but never an uncertain numeral.
            if symbol not in '“”‘’':
                continue
            confirmation,score = read_text(crop, isolated=False)
            if confirmation != reading or score < 60:
                continue
        superscript=symbol.isdecimal()
        words = line.get('words',[])
        overlaps=[(min(box[2],w['bbox'][2])-max(box[0],w['bbox'][0]),i)
                  for i,w in enumerate(words)]
        index=max(overlaps)[1] if overlaps and max(overlaps)[0]>0 else None
        if index is None:
            # A detector can omit a separate marker just after the final word.
            index = next((i for i,w in reversed(list(enumerate(words)))
                          if 0 <= box[0]-w['bbox'][2] < (line['bbox'][3]-line['bbox'][1])*.4),None)
        if index is None:
            continue
        word = words[index]
        if word.get('inline_runs'):
            continue
        wx0,wy0,wx1,wy1 = word['bbox']
        height = line['bbox'][3]-line['bbox'][1]
        if not superscript:
            opening=symbol in '“‘'
            start=stop=index
            if opening and wx1<=box[2]+height*.3 and index+1<len(words):
                if words[index+1]['bbox'][0]<box[2]+height*.4:
                    stop=index+1
            elif not opening and wx0>=box[0]-height*.15 and index:
                start=index-1
            group=words[start:stop+1]
            gx0=min(w['bbox'][0] for w in group);gx1=max(w['bbox'][2] for w in group)
            gy0=min(w['bbox'][1] for w in group);gy1=max(w['bbox'][3] for w in group)
            lo,hi=line.get('recognition_limits',(0,image.shape[0]))
            lo=min(w.get('recognition_limits',(lo,hi))[0] for w in group)
            hi=max(w.get('recognition_limits',(lo,hi))[1] for w in group)
            a,b=(box[2]+1,gx1+3) if opening else (max(0,gx0-3),box[0]-1)
            lexical=image[max(lo,gy0-round(height*.35)):min(hi,gy1+5),a:b]
            if not lexical.size:
                continue
            text,score=read_text(lexical,isolated=False)
            original=' '.join(w['text'] for w in group)
            old_key,new_key=_letters(original),_letters(text)
            matches=old_key.endswith(new_key) if opening else old_key.startswith(new_key)
            if not new_key or not matches or len(old_key)-len(new_key)>2 or score<80:
                continue
            # Preserve the already verified letter accents when just the
            # punctuation boundary was broken by the first detector.
            edge=original[-len(text):] if opening else original[:len(text)]
            if _letters(edge)==new_key:
                text=edge
            repaired=symbol+text if opening else text+symbol
            words[start:stop+1]=[dict(group[0],text=repaired,
                bbox=[min(gx0,box[0]),min(gy0,box[1]),max(gx1,box[2]),max(gy1,box[3])],
                inline_runs=[{'text':repaired}])]
            line.setdefault('ocr_corrections',[]).append(dict(before=original,after=repaired,
                bbox=box,method='visual_quote_shape'))
            continue
        before = ''
        if box[0]-wx0 > height*.3:
            prefix = image[max(0,wy0-4):wy1+5,max(0,wx0-4):box[0]-1]
            before,score = read_text(prefix, isolated=False)
            if not before or score < 70:
                continue
            # Only repair segmentation of the same leading letters. A crop
            # cannot replace a different lexical reading in the parent word.
            if not _letters(word['text']).startswith(_letters(before)):
                continue
            if _letters(word['text'][:len(before)])==_letters(before):
                before=word['text'][:len(before)]
        elif any(c.isalpha() for c in word['text']):
            continue
        after = ''
        if wx1 > box[2]+1:
            tail = image[wy0:wy1,box[2]+1:wx1]
            ink = (tail < 160).astype(np.uint8)
            _,_,stats,_ = cv2.connectedComponentsWithStats(ink)
            dots = [s for s in stats[1:] if s[4]>=3]
            # Preserve an observed baseline period, rather than retaining the
            # quote/bracket that the first OCR made from the raised digit.
            if (len(dots)==1 and dots[0][2]<height*.22 and dots[0][3]<height*.22
                    and dots[0][1]>(wy1-wy0)*.65):
                after = '.'
            elif (len(dots)==2 and all(s[2]<height*.22 and s[3]<height*.28 for s in dots)
                    and abs((dots[0][0]+dots[0][2]/2)-(dots[1][0]+dots[1][2]/2))<height*.12):
                # Two vertically separated punctuation components can be a
                # colon/semicolon after the marker. Preserve the source symbol
                # only when its isolated visual reading agrees.
                padding = cv2.copyMakeBorder(tail,5,5,5,5,cv2.BORDER_CONSTANT,value=255)
                punctuation,score = read_text(padding,isolated=False)
                if score < 50 or punctuation not in (':',';') or not word['text'].endswith(punctuation):
                    continue
                after = punctuation
            elif dots:
                continue
        parts = ([{'text':before}] if before else []) + [dict(text=symbol,bbox=box)]
        if superscript:
            parts[-1]['vertical_align']='superscript'
        if after:
            parts.append({'text':after})
        word['inline_runs'] = parts
        word['text'] = ''.join(p['text'] for p in parts)
        line.setdefault('ocr_corrections',[]).append(dict(after=symbol,bbox=box,
            method='visual_superscript_agreement' if superscript else 'visual_quote_shape'))
    for line in lines:
        if any(w.get('inline_runs') for w in line.get('words',[])):
            parts=[]
            for i,w in enumerate(line['words']):
                if i:
                    parts.append({'text':' '})
                parts.extend(w.get('inline_runs') or [{'text':w['text']}])
            line['inline_runs']=parts
            line['text']=''.join(p['text'] for p in parts)
            line['word_confidences']=[(w['text'],w['confidence']) for w in line['words']]
