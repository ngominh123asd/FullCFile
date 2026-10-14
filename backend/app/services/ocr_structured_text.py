"""Verify printed addresses with visual readers, without a domain dictionary."""
import re
from difflib import SequenceMatcher

import cv2
import numpy as np
from PIL import Image

from app.services.ocr_region_refinement import span_crop
from app.services.ocr_text_refinement import _agreed_edits


_DOMAIN = r'(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}'
_ADDRESS = re.compile(r'(?:[A-Za-z0-9._%+\-]+@|https?://)?' + _DOMAIN + r'(?:[/?#]\S*)?')


def refine_handwritten_dates(lines, image, rgb, predictor, read_ascii, read_words, cancelled):
    """Recover a split date only when independent full-line reads agree.

    Blue ink supplies the positions of handwritten fields. No date value is
    inferred from document metadata, a filename or an expected calendar date.
    """
    if rgb is None:
        return
    date = re.compile(r'ngày\s*(\d{1,2})\s*tháng\s*(\d{1,2})\s*năm\s*(\d{4})',re.I)
    from app.services.ocr_text_refinement import _fold
    for line in list(lines):
        if cancelled():
            return
        if 'ngày' not in line['text'].casefold() or 'tháng' not in line['text'].casefold():
            continue
        x0,y0,x1,y1=line['bbox'];height=y1-y0
        peers=[other for other in lines if other is not line and 'năm' in other['text'].casefold()
               and abs((other['bbox'][1]+other['bbox'][3]-y0-y1)/2)<height*.6
               and 0<=other['bbox'][0]-x1<height*3]
        selected=[line]+peers
        right=max(l['bbox'][2] for l in selected)+8
        top=max(0,y0-round(height*.25));bottom=min(image.shape[0],y1+round(height*.25))
        color=rgb[top:bottom,max(0,x0-5):right];left=max(0,x0-5)
        channels=color.astype(np.int16)
        blue=(channels[:,:,2]-channels[:,:,0]>15)&(channels[:,:,2]-channels[:,:,1]>10)
        if blue.sum()<30:
            continue
        crop=cv2.cvtColor(color,cv2.COLOR_RGB2GRAY)
        prediction=predictor.predict(Image.fromarray(crop)).strip();match=date.search(prediction)
        if not match:
            continue
        expected=''.join(match.groups())
        verified=False
        ys,xs=np.nonzero(crop<200)
        tight=crop[ys.min():ys.max()+1,xs.min():xs.max()+1]
        padded=cv2.copyMakeBorder(tight,6,6,6,6,cv2.BORDER_CONSTANT,value=255)
        for view in (crop,cv2.resize(crop,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA),padded):
            reading,score=read_ascii(view)
            folded=re.sub(r'\s+','',_fold(reading))
            candidate=re.search(r'ngay(\d{1,2})thang(\d{1,2})nam(\d{4})',folded)
            if score>=.85 and candidate and ''.join(candidate.groups())==expected:
                verified=True;break
        if not verified:
            continue
        clear=crop.copy();clear[blue]=255
        printed=read_words(clear)
        labels={w['text'].casefold().strip('.,:;'):i for i,w in enumerate(printed)}
        if not all(k in labels for k in ('ngày','tháng','năm')):
            continue
        # Keep the reliably observed place name/punctuation when removing blue
        # handwriting has joined its printed words in the secondary reading.
        day_start=printed[labels['ngày']]['bbox'][0]
        prefix=[dict(w,bbox=[w['bbox'][0]-left,w['bbox'][1]-top,w['bbox'][2]-left,w['bbox'][3]-top])
                for w in line['words'] if w['bbox'][2]<=left+day_start and w['confidence']>=85]
        if prefix:
            printed=prefix+printed[labels['ngày']:]
            labels={w['text'].casefold().strip('.,:;'):i for i,w in enumerate(printed)}
        additions=[]
        for label,end,value in [('ngày','tháng',match[1]),('tháng','năm',match[2])]:
            a=printed[labels[label]]['bbox'][2];b=printed[labels[end]]['bbox'][0]
            ys,xs=np.nonzero(blue[:,max(0,a-4):b])
            if not len(xs):
                break
            additions.append(dict(text=value,confidence=90.,handwritten=True,visual_verified=True,
                bbox=[int(xs.min()+max(0,a-4)),int(ys.min()),int(xs.max()+max(0,a-4)+1),int(ys.max()+1)]))
        if len(additions)!=2:
            continue
        words=sorted(printed+additions,key=lambda w:w['bbox'][0])
        candidate=' '.join(w['text'] for w in words)
        if not date.search(candidate) or date.search(candidate).groups()!=match.groups():
            continue
        for w in words:
            w['bbox']=[w['bbox'][0]+left,w['bbox'][1]+top,w['bbox'][2]+left,w['bbox'][3]+top]
        before=' '.join(l['text'] for l in selected)
        line.update(words=words,text=candidate,confidence=min(w['confidence'] for w in words),
                    bbox=[min(w['bbox'][0] for w in words),min(w['bbox'][1] for w in words),
                          max(w['bbox'][2] for w in words),max(w['bbox'][3] for w in words)],
                    word_confidences=[(w['text'],w['confidence']) for w in words])
        line.setdefault('ocr_corrections',[]).append(dict(before=before,after=candidate,method='visual_date_agreement'))
        for peer in peers:
            lines.remove(peer)


def refine_printed_identifiers(lines, image, predictor, read_words, cancelled):
    """Resolve code disagreements using the original and thresholded glyphs."""
    from app.services.ocr_text_refinement import word_crop
    for line in lines:
        changed=False
        for word in line.get('words',[]):
            old=word['text']
            if word.get('handwritten') or not re.search(r'\d+[-/:]\d{2,}',old):
                continue
            if cancelled():
                return
            crop=word_crop(image,word,line)
            if not crop.size:
                continue
            candidate=predictor.predict(Image.fromarray(crop)).strip().replace(' ','')
            if candidate==old or not re.fullmatch(r'[\w/().,:;–-]+',candidate):
                continue
            if not re.search(r'\d+[-/:]\d{2,}',candidate):
                continue
            for view in (crop,cv2.threshold(crop,160,255,cv2.THRESH_BINARY)[1]):
                words=read_words(view)
                if (words and min(w['confidence'] for w in words)>=85 and
                        ''.join(w['text'] for w in words).casefold()==candidate.casefold()):
                    line.setdefault('ocr_corrections',[]).append(dict(before=old,after=candidate,
                        bbox=word['bbox'],method='visual_code_agreement'))
                    word.update(text=candidate,visual_verified=True);changed=True;break
        if changed:
            line['text']=' '.join(w['text'] for w in line['words'])
            line['word_confidences']=[(w['text'],w['confidence']) for w in line['words']]


def refine_document_codes(lines, image, rgb, read_ascii, read_words, predictor, read_handwriting, cancelled):
    """Verify uncertain handwritten identifiers separately from printed suffixes.

    A separator followed by an uppercase code selects the region. Its number
    comes only from two visual models, never a filename, template or sequence.
    """
    from app.services.ocr_text_refinement import crop_with_accents, line_recognition_limits
    key = lambda text: ''.join(c.casefold() for c in text if c.isalnum())
    def number(crop):
        padded = cv2.copyMakeBorder(crop,6,6,10,10,cv2.BORDER_CONSTANT,value=255)
        candidate = predictor.predict(Image.fromarray(padded)).strip()
        if not re.fullmatch(r'\d{1,8}',candidate):
            return None
        other,score = read_ascii(padded)
        if other == candidate and score>=.9:
            return candidate,float(score)*100
        try:
            alternative = read_handwriting(padded)
        except (ImportError, OSError, RuntimeError):
            # Optional handwriting weights/runtime may be unavailable. Keep
            # the observed reading instead of guessing or failing the page.
            return None
        if alternative and alternative[1]>=.9 and alternative[0].strip().rstrip('.,') == candidate:
            return candidate,float(alternative[1])*100
        return None
    def placed(words, x, y):
        return [dict(w,bbox=[w['bbox'][0]+x,w['bbox'][1]+y,w['bbox'][2]+x,w['bbox'][3]+y]) for w in words]
    for line,limits in zip(lines,line_recognition_limits(lines,image.shape[0],image)):
        words = line.get('words',[])
        # A black handwritten prefix can touch the slash and be joined to the
        # printed year. Search observed inter-glyph gaps, then verify each side.
        if re.match(r"^[^\w]*Số:",line['text'],re.I) and len(words)>=2:
            group=words[1:];box=[min(w['bbox'][0] for w in group),min(w['bbox'][1] for w in group),
                                max(w['bbox'][2] for w in group),max(w['bbox'][3] for w in group)]
            pad=round((box[3]-box[1])*.35)
            ox=max(0,box[0]-5);oy=max(limits[0],box[1]-pad)
            crop=image[oy:min(limits[1],box[3]+pad+1),ox:min(image.shape[1],box[2]+6)]
            full=predictor.predict(Image.fromarray(crop)).strip()
            code=re.fullmatch(r'((?:\d\s*){1,8})/((?:19|20)\d{2}/[A-ZĐ][A-ZĐ-]+)',full)
            if code:
                digits=re.sub(r'\s+','',code[1]);suffix=code[2]
                profile=np.mean(crop<180,axis=0)
                gaps=np.flatnonzero(profile<.02)
                gaps=gaps[(gaps>crop.shape[0]*.4)&(gaps<min(crop.shape[1]*.5,crop.shape[0]*3))]
                cuts=[int(np.median(g)) for g in np.split(gaps,np.where(np.diff(gaps)>1)[0]+1) if len(g)]
                # A handwritten '1' may touch the separator; probe a narrow
                # band at the first printed token instead of requiring a gap.
                boundary=group[1]['bbox'][0]-ox if len(group)>1 else crop.shape[0]*len(digits)*.5
                cuts+=list(range(max(1,round(boundary)),min(crop.shape[1]//2,round(boundary+crop.shape[0]*.6)),4))
                for cut in cuts:
                    verified=number(crop[:,:cut])
                    if not verified or verified[0]!=digits:
                        continue
                    printed=read_words(crop[:,cut:])
                    if (not printed or min(w['confidence'] for w in printed)<80 or
                            key(''.join(w['text'] for w in printed))!=key(suffix)):
                        continue
                    candidate=digits+'/'+suffix
                    before=line['text'];prefix=dict(words[0])
                    line.update(words=[prefix,dict(text=candidate,confidence=verified[1],visual_verified=True,
                                                   handwritten=True,bbox=box)],
                                text=prefix['text']+' '+candidate,
                                word_confidences=[(prefix['text'],prefix['confidence']),(candidate,verified[1])])
                    line.setdefault('ocr_corrections',[]).append(dict(before=before,after=line['text'],method='split_identifier_agreement'))
                    words=line['words'];break
        if not re.search(r'[/\-][A-ZĐ]{2,}',line['text']) or not any(w.get('confidence',100)<75 for w in words):
            continue
        if cancelled():
            return
        before = line['text'];changed = False
        crop,(ox,oy) = crop_with_accents(image,line['bbox'],limits,True)
        if rgb is not None and crop.size:
            color = rgb[oy:oy+crop.shape[0],ox:ox+crop.shape[1]].astype(np.int16)
            blue = (color[:,:,2]-color[:,:,0]>25)&(color[:,:,2]-color[:,:,1]>15)
            ys,xs = np.nonzero(blue)
            if len(xs)>30 and 5<xs.max()-xs.min()<crop.shape[1]*.45:
                a,b = int(xs.min()),int(xs.max())+1
                top,bottom = int(ys.min()),int(ys.max())+1
                weak = any(w['confidence']<75 and w['bbox'][0]<b+ox and w['bbox'][2]>a+ox for w in words)
                digits = crop[top:bottom,a:b].copy()
                digits[~blue[top:bottom,a:b]]=255
                verified = number(digits) if weak else None
                if verified and a>0 and b<crop.shape[1]:
                    clear = crop.copy();clear[blue]=255
                    # Handwriting can touch a printed colon. Recognize the
                    # prefix with full-line context instead of slicing its
                    # final printed stroke at the colored component's edge.
                    prefix = [w for w in read_words(clear) if w['bbox'][2]<=a+max(3,(bottom-top)*.25)]
                    suffix = read_words(clear[:,b:])
                    printed = ' '.join(w['text'] for w in prefix+suffix)
                    corroborated = predictor.predict(Image.fromarray(clear)).strip()
                    if (prefix and suffix and min(w['confidence'] for w in prefix+suffix)>=75
                            and key(printed)==key(corroborated)
                            and re.search(r'[/\-][A-ZĐ]{2,}',printed)):
                        printed_words = placed(prefix,ox,oy)+placed(suffix,ox+b,oy)
                        for word in printed_words:
                            word['visual_verified'] = True
                        words = printed_words[:len(prefix)]+[dict(text=verified[0],confidence=verified[1],
                                 handwritten=True,bbox=[ox+a,oy+top,ox+b,oy+bottom])]+printed_words[len(prefix):]
                        changed = True
        if not changed:
            for index,word in enumerate(words[:-1]):
                if (word['confidence']>=75 or len(word['text'])>8 or
                        not re.match(r'^/[A-ZĐ]{2,}',words[index+1]['text'])):
                    continue
                local = crop_with_accents(image,word['bbox'],limits,padding_ratio=.35)
                verified = number(local) if local.size else None
                if verified:
                    word.update(text=verified[0],confidence=verified[1],handwritten=True);changed=True
        if changed:
            boxes = [w['bbox'] for w in words]
            line.update(words=words,text=' '.join(w['text'] for w in words),
                confidence=sum(w['confidence'] for w in words)/len(words),
                bbox=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                word_confidences=[(w['text'],w['confidence']) for w in words])
            line.setdefault('ocr_corrections',[]).append(dict(before=before,after=line['text'],method='visual_identifier_agreement'))


def refine_addresses(lines, image, read_ascii, read_words, predictor, cancelled):
    """Every changed character needs an independent visual confirmation.

    Syntax selects regions worth rereading; it never supplies a missing '@',
    letter, suffix or domain. The full candidate must be observed by the ASCII
    recognizer and corroborated by edits from the other visual readers.
    """
    for line in lines:
        words = line.get('words', [])
        changed = False
        for index, word in enumerate(words):
            before = word['text']
            if not re.search(_DOMAIN, before) or word.get('confidence', 100) >= 95:
                continue
            if cancelled():
                return
            crop, _ = span_crop(image, line, index, index+1, lines)
            if not crop.size:
                continue
            candidate, confidence = read_ascii(crop)
            candidate = candidate.strip()
            if (confidence < .93 or candidate == before or not _ADDRESS.fullmatch(candidate)
                    or SequenceMatcher(None, before.casefold(), candidate.casefold()).ratio() < .65):
                continue
            independent = read_words(crop)
            if not independent or min(w['confidence'] for w in independent) < 50:
                # Faint italic addresses can be much clearer to the second
                # reader after thresholding. The ASCII candidate still comes
                # from the untouched crop, and every edit needs agreement.
                alternate = cv2.threshold(crop,0,255,cv2.THRESH_BINARY|cv2.THRESH_OTSU)[1]
                independent = read_words(alternate)
                if not independent or min(w['confidence'] for w in independent) < 50:
                    continue
            other = ''.join(w['text'] for w in independent)
            if SequenceMatcher(None, candidate.casefold(), other.casefold()).ratio() < .85:
                continue
            verified = _agreed_edits(before, candidate, other)
            if verified.casefold() != candidate.casefold() and predictor is not None:
                if cancelled():
                    return
                contextual = predictor.predict(Image.fromarray(crop)).strip()
                verified = _agreed_edits(verified, candidate, contextual)
            if verified.casefold() != candidate.casefold():
                continue
            line.setdefault('ocr_corrections', []).append(dict(
                before=before, after=candidate, bbox=word['bbox'], method='visual_address_agreement'))
            word.update(text=candidate, confidence=confidence*100)
            changed = True
        if changed:
            line['text'] = ' '.join(w['text'] for w in words)
            line['word_confidences'] = [(w['text'], w['confidence']) for w in words]
