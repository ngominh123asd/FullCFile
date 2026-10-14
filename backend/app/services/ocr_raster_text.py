"""Cross-check small table print using bounded rows and independent models."""
import unicodedata

import cv2
from PIL import Image

from app.services.ocr_text_refinement import _aligned_token, _keep_edge_punctuation


def _core(text):
    return ''.join(c for c in unicodedata.normalize('NFC',text.casefold()) if c.isalnum())


def refine_raster_line(line,image,predictor,read_words,cancelled):
    words=line.get('words',[]);source=[w['text'] for w in words]
    if not words or ' '.join(source)!=line['text'] or cancelled():return
    x,y,xx,yy=line['bbox'];a,b=line['raster_row_limits']
    top=max(a,y-4);bottom=min(b,yy+4)
    crop=image[top:bottom,max(0,x-3):xx+3]
    if not crop.size:return
    proposal=predictor.predict(Image.fromarray(crop),max_chunk_width=320)
    if not proposal:return
    candidates={i:_aligned_token(source,proposal,i) for i in range(len(source))}
    if not any(v and v!=source[i] for i,v in candidates.items()):return
    # Model variants and raster scales offer independent character evidence.
    # Their complete row context avoids an adjacent word's stroke being read
    # as a tone on an isolated two-letter token.
    readings=[]
    for quality,scale in ((True,1),(False,1),(False,.5)):
        view=cv2.resize(crop,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA) if scale!=1 else crop
        reading=read_words(view,quality)
        readings.append((reading,' '.join(w['text'] for w in reading)))
    changed=[]
    for i,word in enumerate(words):
        candidate=candidates[i]
        if not candidate or candidate==word['text']:continue
        candidate=_keep_edge_punctuation(word['text'],candidate,100)
        if candidate==word['text']:continue
        evidence=[]
        for reading,text in readings:
            matched=_aligned_token(source,text,i)
            if matched and _core(matched)==_core(candidate):
                evidence.extend(w['confidence'] for w in reading if _core(w['text'])==_core(candidate))
        minimum=80 if any(c.isdigit() for c in word['text']+candidate) else 70
        if not evidence or max(evidence)<minimum:continue
        wx,wy,wxx,wyy=word['bbox']
        left=max(0,wx-2);right=min(image.shape[1],wxx+2)
        if i and words[i-1]['bbox'][2]<=wx:left=max(left,words[i-1]['bbox'][2])
        if i+1<len(words) and words[i+1]['bbox'][0]>wx:right=min(right,words[i+1]['bbox'][0])
        local=image[max(a,wy-2):min(b,wyy+2),left:right]
        if not local.size:continue
        confirmed=predictor.predict(Image.fromarray(local)).strip()
        if _core(confirmed)!=_core(candidate):continue
        changed.append(dict(before=word['text'],after=candidate,method='bounded_raster_agreement'))
        word.update(text=candidate,visual_verified=True)
    if changed:
        line.setdefault('ocr_corrections',[]).extend(changed)
        line['text']=' '.join(w['text'] for w in words)
        line['word_confidences']=[(w['text'],w['confidence']) for w in words]
