"""Locate recurring marginal graphics by pixels, without recognizing their text."""
from collections import defaultdict

import cv2
import numpy as np


def repeated_footer_regions(pdf_bytes, cancelled=lambda: False):
    """Return relative page boxes for isolated graphics repeated in the margin.

    These regions are retained as images by the exporter, not discarded. The
    same mechanism works on flattened scans and on PDFs with separate logos.
    Unique footnotes and body content do not qualify as repeated graphics.
    """
    import fitz
    strips = []
    origins = []
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        if len(doc) < 3:
            return {}
        for page in doc:
            if cancelled():
                return {}
            scale = 800/page.rect.width
            clip = fitz.Rect(0, page.rect.height*.9, page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale), clip=clip,
                                 colorspace=fitz.csGRAY, alpha=False)
            strips.append(np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width).copy())
            origins.append((pix.x,pix.y,page.rect.width*scale,page.rect.height*scale))
    found = defaultdict(list)
    # A few representative pages suffice to propose templates; validate each
    # against all pages so a one-off note never becomes a running footer.
    for page_index in np.linspace(0,len(strips)-1,min(5,len(strips)),dtype=int):
        gray = strips[page_index]
        mask = cv2.dilate((gray < 190).astype(np.uint8),np.ones((5,9),np.uint8))
        contours,_ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x,y,w,h = cv2.boundingRect(contour)
            if not (25 <= w <= gray.shape[1]*.3 and 8 <= h <= gray.shape[0]*.65):
                continue
            x0,y0 = max(0,x-3),max(0,y-3)
            x1,y1 = min(gray.shape[1],x+w+3),min(gray.shape[0],y+h+3)
            template = gray[y0:y1,x0:x1]
            if template.std() < 12:
                continue
            matches = []
            for other_index,other in enumerate(strips):
                if cancelled():
                    return {}
                if other.shape[0] < template.shape[0] or other.shape[1] < template.shape[1]:
                    continue
                score = cv2.matchTemplate(other,template,cv2.TM_CCOEFF_NORMED)
                _,similarity,_,(mx,my) = cv2.minMaxLoc(score)
                if similarity >= .92 and abs(mx-x0) <= gray.shape[1]*.03:
                    ox,oy,pw,ph = origins[other_index]
                    matches.append((other_index,[(mx+ox)/pw,(my+oy)/ph,
                                                 (mx+ox+template.shape[1])/pw,
                                                 (my+oy+template.shape[0])/ph]))
            if len(matches) < max(3,len(strips)*.6):
                continue
            for i,box in matches:
                if not any(min(box[2],b[2]) > max(box[0],b[0]) and
                           min(box[3],b[3]) > max(box[1],b[1]) for b in found[i]):
                    found[i].append(box)
    return dict(found)
