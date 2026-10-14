"""Native OCR with region-local ruled tables and ordered document elements.

Table cells are first read in a vertical contact sheet. Photos receive selective
neural refinement. Rule geometry determines empty/merged cells, never the text.
"""
from __future__ import annotations

import csv
import io
import os
import re
import logging
import subprocess
import tempfile
import time
import unicodedata
from collections import defaultdict

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def _peaks(values, gap=6):
    groups = []
    for value in values:
        if not groups or value - groups[-1][-1] > gap:
            groups.append([])
        groups[-1].append(int(value))
    return [int(np.mean(group)) for group in groups]


def _deskew(gray, return_matrix=False):
    """Use long printed rules when available; ignore short letter strokes."""
    def result(image, matrix=None):
        return (image, np.eye(2,3) if matrix is None else matrix) if return_matrix else image
    scale = min(1., 1400 / gray.shape[1])
    small = cv2.resize(gray, None, fx=scale, fy=scale)
    edges = cv2.Canny(small, 80, 180)
    lines = cv2.HoughLinesP(edges, 1, np.pi/1800, 100,
                            minLineLength=small.shape[1]*.25, maxLineGap=20)
    angles = []
    if lines is not None:
        for x0, y0, x1, y1 in lines.reshape(-1, 4):
            angle = np.degrees(np.arctan2(y1-y0, x1-x0))
            if abs(angle) < 4:
                angles.append(angle)
    if len(angles) < 3:
        return result(gray)
    angle = float(np.median(angles))
    if abs(angle) < .15:
        return result(gray)
    h, w = gray.shape
    matrix = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
    return result(cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=255), matrix)


def _normalize_photo(gray):
    """Remove uneven illumination without thresholding Vietnamese accents away."""
    paper = (gray > np.percentile(gray, 80)*.82).astype(np.uint8)*255
    paper = cv2.morphologyEx(paper, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
    contours, _ = cv2.findContours(paper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(largest) > gray.size*.5:
            mask = np.zeros_like(gray)
            cv2.drawContours(mask, [largest], -1, 255, cv2.FILLED)
            gray = gray.copy()
            gray[mask == 0] = 255
    size = max(21, int(min(gray.shape) / 45) | 1)
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
    normalized = cv2.divide(gray, background, scale=255)
    # Keep the grayscale evidence: fixed contrast clipping destroys faint
    # accents and makes adjacent strokes indistinguishable in photographs.
    return normalized


def _scan_text_image(rgb):
    """Keep printed strokes while excluding red stamp ink from text recognition.

    Work from color before grayscale conversion: a grayscale scan makes red
    stamps indistinguishable from letters, including stamps in the page margin.
    """
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    channels = rgb.astype(np.int16)
    red = ((channels[:,:,0]-channels[:,:,1] > 45) &
           (channels[:,:,0]-channels[:,:,2] > 35)).astype(np.uint8)
    groups = cv2.dilate(red, np.ones((25,25),np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(groups)
    stamp = np.zeros_like(red)
    h,w = gray.shape
    for k in range(1,count):
        x,y,cw,ch,area = stats[k]
        if ch > h*.025 and (x+cw > w*.85 or (y > h*.55 and .45 < cw/max(1,ch) < 2.5)):
            stamp[labels == k] = 1
    red_fringe = (channels[:,:,0]-np.minimum(channels[:,:,1],channels[:,:,2]) > 15)
    gray[(stamp > 0) & red_fringe] = 255
    # Blue signatures overlapping a detected stamp are also graphics. Limit
    # removal to this connected annotation, preserving colored body text.
    blue = ((channels[:,:,2]-channels[:,:,0] > 40) &
            (channels[:,:,2]-channels[:,:,1] > 20)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(blue,np.ones((15,15),np.uint8)))
    for k in range(1,count):
        if np.any((labels == k) & (stamp > 0)):
            gray[(labels == k) & (channels[:,:,2]-channels[:,:,0] > 15)] = 255
    # A signed seal may sit mid-page over the signature block. Its colored
    # ring and the long signature strokes are graphics wherever they occur;
    # neutral printed glyphs under the seal are not part of this mask.
    from app.services.ocr_graphics import seal_ink_mask
    seal = seal_ink_mask(rgb)
    if seal.any():
        gray[seal] = 255
    return gray


def _merge_visual_words(line, prediction, spacing_only=False):
    """Keep source punctuation, numbers and confident words during neural retry."""
    from difflib import SequenceMatcher
    source = line['text']
    a = list(re.finditer(r'\w+', source))
    b = list(re.finditer(r'\w+', prediction))
    weights, cursor = [], 0
    for word, confidence in line.get('word_confidences', []):
        weights.append((cursor,cursor+len(word),confidence))
        cursor += len(word)+1
    words = line.get('words', [])
    glyph_widths = [(w['bbox'][2]-w['bbox'][0])/max(1,len(w['text'])) for w in words]
    narrow_spaces, cursor = set(), 0
    for previous, current in zip(words, words[1:]):
        cursor += len(previous['text'])
        gap = current['bbox'][0]-previous['bbox'][2]
        if glyph_widths and gap < float(np.median(glyph_widths))*.5:
            narrow_spaces.add(cursor)
        cursor += 1
    def fold(word):
        return ''.join(c for c in unicodedata.normalize('NFD',word.lower()) if not unicodedata.combining(c))
    if spacing_only:
        # Punctuation can share a detector token with the following word.
        # Keep all observed characters; propose only whitespace edits whose
        # immediate surrounding characters agree in the independent reading.
        edits = []
        for tag,x,y,u,v in SequenceMatcher(None,fold(source),fold(prediction),autojunk=False).get_opcodes():
            old,new = source[x:y],prediction[u:v]
            if tag != 'equal' and (not old or old.isspace()) and (not new or new.isspace()):
                edits.append((x,y,new))
        if edits:
            result = source
            for x,y,new in reversed(edits):
                result = result[:x]+new+result[y:]
            return result
    changes = []
    def spaced_source(original, proposed):
        if not spacing_only:
            return proposed
        letters = iter(c for c in original if not c.isspace())
        return ''.join(c if c.isspace() else next(letters) for c in proposed)
    matcher = SequenceMatcher(None,[fold(m.group()) for m in a],[fold(m.group()) for m in b],autojunk=False)
    for tag,i,j,k,l in matcher.get_opcodes():
        # Restore a missing space only when the visual re-read agrees on all
        # letters. Punctuation and identifiers are never split this way.
        if j-i == 1 and l-k > 1 and a[i].group().isalpha() and all(m.group().isalpha() for m in b[k:l]):
            original = a[i]
            if fold(original.group()) == ''.join(fold(m.group()) for m in b[k:l]):
                new = ' '.join(m.group() for m in b[k:l])
                changes.append((original.start(), original.end(), spaced_source(original.group(),new)))
            continue
        if j-i != l-k:
            if j > i and l > k:
                old_span = source[a[i].start():a[j-1].end()]
                new_span = prediction[b[k].start():b[l-1].end()]
                confidence = min((c for x,y,c in weights if x < a[j-1].end() and y > a[i].start()), default=line['confidence'])
                removed_spaces = {a[i].start()+m.start() for m in re.finditer(r'\s',old_span)}
                optical_join = bool(removed_spaces) and removed_spaces <= narrow_spaces
                if ((confidence < 90 or optical_join) and fold(''.join(old_span.split())) == fold(''.join(new_span.split()))
                        and re.fullmatch(r'[\w\s]+',old_span) and re.fullmatch(r'[\w\s]+',new_span)):
                    changes.append((a[i].start(),a[j-1].end(),spaced_source(old_span,new_span)))
            continue
        for original, updated in zip(a[i:j],b[k:l]):
            if spacing_only:
                continue
            old,new = original.group(),updated.group()
            confidence = min((c for x,y,c in weights if x < original.end() and y > original.start()),default=line['confidence'])
            if (old != new and old.isalpha() and new.isalpha()
                    and (confidence < 90 or (source.isupper() and fold(old) == fold(new)))
                    and SequenceMatcher(None,fold(old),fold(new)).ratio() >= .5):
                changes.append((original.start(),original.end(),new.upper() if old.isupper() else new))
    for start,end,new in reversed(changes):
        source = source[:start]+new+source[end:]
    return source


def _refine_scan_lines(lines, image, language, cancelled, refine_numeric=True, source_rgb=None):
    """Re-read uncertain lines independently; never carry decoder state between pages."""
    if language not in ('vi','vie','auto'):
        return
    from PIL import Image
    from app.services.ocr_service import _get_vietocr_onnx_predictor, _get_rapid_engine
    from app.services.ocr_text_refinement import crop_with_accents, refine_with_context, refine_spacing, line_recognition_limits, refine_weak_accents, refine_punctuation
    from app.services.ocr_region_refinement import refine_weak_spans, refine_underlined_line, refine_uncertain_line, refine_overlapping_words
    from app.services.ocr_text_refinement import attach_word_limits
    for line in lines:
        for word in line.get('words', []):
            word.setdefault('source_text',word['text'])
    attach_word_limits(lines,image.shape[0],image=image,preserve_word_ink=True)
    predictor = None
    numeric = []
    for line, limits in zip(lines, line_recognition_limits(lines, image.shape[0], image,preserve_word_ink=True)):
        if cancelled():
            return
        text = line['text']
        x0,y0,x1,y1 = line['bbox']
        line['recognition_limits'] = limits
        crop = crop_with_accents(image, (x0,y0,x1,y1), limits)
        if not crop.size:
            continue
        if re.search(r'\d',text) and sum(c.isalpha() for c in text) <= 2:
            if refine_numeric:
                numeric.append((line,crop))
            continue
        # Confidence measures the recognizer's own certainty, not correctness.
        # Even confident lines may have lost every diacritic. Verify their
        # visual reading too; only disagreements need a further local crop.
        if sum(c.isalpha() for c in text) < 3:
            continue
        # ONNX CUDA availability is independent of whether the installed Torch
        # wheel is CPU-only. ONNX itself chooses an available execution provider.
        predictor = (predictor or _get_vietocr_onnx_predictor(use_gpu=os.getenv('OCR_SCAN_DEVICE','auto').lower() != 'cpu')
                     or _get_vietocr_onnx_predictor(use_gpu=False))
        if predictor is None:
            break
        if line.get('raster_row_limits'):
            from app.services.ocr_raster_text import refine_raster_line
            refine_raster_line(line,image,predictor,
                               lambda crop,quality:_tesseract_words(crop,language,7,cancelled,quality=quality),
                               cancelled)
            continue
        refine_overlapping_words(line,image,predictor,
                                 lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),
                                 cancelled,lines)
        if refine_uncertain_line(line,image,predictor,
                                 lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),cancelled,lines):
            # Segmentation agreement compares letters without tone marks. A
            # recovered line still needs the normal diacritic verification.
            attach_word_limits(lines,image.shape[0],image=image,preserve_word_ink=True)
            crop=crop_with_accents(image,line['bbox'],line.get('recognition_limits'))
        if refine_underlined_line(line,image,predictor,
                                  lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),cancelled):
            # The original view still contains the rule that caused the bad
            # reading. Do not undo the independently verified alternate view.
            continue
        text = line['text']
        # Shorter scan chunks reduce autoregressive decoding cost. Keep the
        # photograph/handwriting recognizer's existing context window unchanged.
        prediction = predictor.predict(Image.fromarray(crop), max_chunk_width=320)
        if prediction and len(text)*.7 <= len(prediction) <= len(text)*1.3+3:
            def recognize_code(word_crop):
                engine=_get_rapid_engine()
                if engine is None:
                    return '',0.
                readings,_=engine.text_rec([cv2.cvtColor(word_crop,cv2.COLOR_GRAY2BGR)])
                return readings[0] if readings else ('',0.)
            refine_weak_spans(line,prediction,image,predictor,cancelled,recognize_code,lines,
                             recognize_words=lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True))
            spaced = _merge_visual_words(line,prediction,spacing_only=True)
            refine_spacing(line,spaced,image,
                           lambda word_crop: _tesseract_words(word_crop,language,7,cancelled,quality=True),cancelled)
            def verify_word(word_crop):
                reading = _tesseract_words(word_crop, language, 7, cancelled, quality=True)
                return {'text':' '.join(w['text'] for w in reading),
                        'confidence':min((w['confidence'] for w in reading),default=0)}
            refine_with_context(line, prediction, image, predictor, cancelled, verify_word=verify_word)
            refine_weak_accents(line, image, predictor, cancelled, verify_word=verify_word)
            refine_punctuation(line, prediction, image, predictor, cancelled, verify_word)
    if predictor is not None and not cancelled() and source_rgb is not None:
        from app.services.ocr_scan_evidence import refine_color_overlap
        refine_color_overlap(lines,source_rgb,predictor,
                             lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),cancelled)
    if predictor is not None and not cancelled():
        from app.services.ocr_structured_text import refine_printed_identifiers
        refine_printed_identifiers(lines,image,predictor,
                                   lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),cancelled)
    if predictor is not None and not cancelled() and any(re.search(r'[/\-][A-ZĐ]{2,}|ngày.+tháng', l['text']) for l in lines):
        from app.services.ocr_structured_text import refine_document_codes, refine_handwritten_dates
        from app.services.ocr_handwriting import predict_handwriting
        engine = _get_rapid_engine()
        if engine is not None:
            def read_identifier(crop):
                readings,_ = engine.text_rec([cv2.cvtColor(crop,cv2.COLOR_GRAY2BGR)])
                return readings[0] if readings else ('',0.)
            refine_document_codes(lines,image,source_rgb,read_identifier,
                                  lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),
                                  predictor,predict_handwriting,cancelled)
            refine_handwritten_dates(lines,image,source_rgb,predictor,read_identifier,
                                     lambda crop:_tesseract_words(crop,language,7,cancelled,quality=True),cancelled)
    if not cancelled() and any(re.search(r'[A-Za-z0-9-]+\.[A-Za-z]{2,}', l['text']) for l in lines):
        from app.services.ocr_structured_text import refine_addresses
        engine = _get_rapid_engine()
        if engine is not None:
            def read_address(crop):
                readings, _ = engine.text_rec([cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)])
                return readings[0] if readings else ('', 0.)
            refine_addresses(lines, image, read_address,
                             lambda crop: _tesseract_words(crop, 'en', 7, cancelled, quality=True),
                             predictor, cancelled)
    if numeric and not cancelled():
        engine = _get_rapid_engine()
        if engine is not None:
            results,_ = engine.text_rec([cv2.cvtColor(crop,cv2.COLOR_GRAY2BGR) for _,crop in numeric])
            for (line,_),(prediction,confidence) in zip(numeric,results):
                if confidence >= .85 and re.fullmatch(r'[\d hHmMsS.,/:=+%()<>−–-]+',prediction):
                    line.update(text=prediction,confidence=float(confidence)*100)



def _is_duplicate_fragment(line, lines, graphic_boxes=()):
    """Reject uncertain accent fragments overlapping a better complete line."""
    if len(line['text']) > 8 or line['confidence'] >= 60:
        return False
    x0, y0, x1, y1 = line['bbox']
    height = y1-y0
    for other in lines:
        if other is line or other['confidence'] < max(70, line['confidence']+25):
            continue
        left, top, right, bottom = other['bbox']
        overlap = min(y1, bottom)-max(y0, top)
        near_graphic = any(b[0]<=x0<=b[2] and b[1]<=y0<=b[3] for b in graphic_boxes)
        if (near_graphic and not any(c.isdigit() for c in line['text']) and len(line['text'])<=4
                and left-(bottom-top)*.5<=x0 and x1<=right+(bottom-top)*.5
                and height<bottom-top and overlap>=height*.25):
            return True
        if (left <= x0 and x1 <= right and height < (bottom-top)*.95
                and overlap >= height*.4 and abs(y0-top) < (bottom-top)*.55):
            return True
    return False


def _is_graphic_residue(line, original, cleaned, graphic_boxes=()):
    """Reject weak fragments whose ink belonged almost entirely to a stamp.

    Confidence alone cannot discard text. Require that color-based graphic
    separation removed most original ink and left only sparse edge fragments.
    Printed text overlapping a stamp still retains its dense neutral strokes.
    """
    if line['confidence'] >= 70:
        return False
    x0,y0,x1,y1 = line['bbox']
    before = original[y0:y1,x0:x1] < 180
    after = cleaned[y0:y1,x0:x1] < 180
    if (not any(c.isdigit() for c in line.get('text','')) and len(line.get('text',''))<=4
            and x1-x0>(y1-y0)*5
            and any(b[0]<=x0 and x1<=b[2] and b[1]<=y0 and y1<=b[3] for b in graphic_boxes)
            and after.size and after.mean()<.12 and after.sum()<before.sum()*.5):
        return True
    return bool(after.size and after.mean() < .08 and after.sum() < before.sum()*.2)


def _rectify_photo(gray, return_matrix=False):
    """Estimate perspective from cell borders, excluding aligned text strokes.

    Closed quadrilateral holes provide reliable rule segments. A Hough transform
    of those segments (rather than all text edges) estimates the two grid axes.
    If there is no sufficiently large grid, leave the image geometry alone.
    """
    height, width = gray.shape
    def result(image, matrix=None):
        return (image, np.eye(3) if matrix is None else matrix) if return_matrix else image
    ink = cv2.morphologyEx((gray < 210).astype(np.uint8) * 255, cv2.MORPH_CLOSE,
                           np.ones((3, 3), np.uint8))
    contours, hierarchy = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return result(gray)
    vertical, horizontal = np.zeros_like(gray), np.zeros_like(gray)
    count = 0
    for contour, relation in zip(contours, hierarchy.reshape(-1, 4)):
        if relation[3] < 0 or cv2.contourArea(contour) < height * width * .00014:
            continue
        quad = cv2.approxPolyDP(contour, .025 * cv2.arcLength(contour, True), True).reshape(-1, 2)
        if len(quad) != 4 or not cv2.isContourConvex(quad):
            continue
        _, _, w, h = cv2.boundingRect(quad)
        if w < width*.014 or h < height*.01 or h > height*.2 or cv2.contourArea(contour)/(w*h) < .6:
            continue
        count += 1
        for a, b in zip(quad, np.roll(quad, -1, axis=0)):
            dx, dy = b-a
            if abs(dx) < abs(dy)*.2:
                cv2.line(vertical, a, b, 255, 2)
            if abs(dy) < abs(dx)*.12:
                cv2.line(horizontal, a, b, 255, 2)
    if count < 12:
        return result(gray)

    def axes(mask, is_vertical):
        extent = height if is_vertical else width
        segments = cv2.HoughLinesP(mask, 1, np.pi/1800, 70,
                                    minLineLength=extent*.25, maxLineGap=extent*.03)
        if segments is None:
            return []
        candidates = []
        for x0, y0, x1, y1 in segments.reshape(-1, 4):
            if is_vertical:
                if abs(y1-y0) < extent*.2:
                    continue
                slope = (x1-x0)/(y1-y0)
                intercept = x0-slope*y0
            else:
                if abs(x1-x0) < extent*.2:
                    continue
                slope = (y1-y0)/(x1-x0)
                intercept = y0-slope*x0
            candidates.append([intercept+slope*extent/2, slope, intercept, np.hypot(x1-x0, y1-y0)])
        clusters = []
        for item in sorted(candidates):
            if not clusters or item[0]-np.mean([a[0] for a in clusters[-1]]) > min(height, width)*.006:
                clusters.append([])
            clusters[-1].append(item)
        return [np.average(group, axis=0, weights=np.array(group)[:, 3]) for group in clusters]

    vs, hs = axes(vertical, True), axes(horizontal, False)
    if len(vs) < 3 or len(hs) < 4:
        return result(gray)

    # Perspective makes the slopes vary smoothly across the grid. Individual
    # holes may touch a glyph and have a bad corner; do not let one such hole
    # determine the full-page warp.
    for family, extent in ((vs, height), (hs, width)):
        positions = np.array([line[0] for line in family])
        slopes = np.array([line[1] for line in family])
        keep = np.ones(len(family), dtype=bool)
        for _ in range(3):
            fit = np.polyfit(positions[keep], slopes[keep], 1)
            residual = np.abs(slopes-np.polyval(fit, positions))
            keep = residual < max(.003, 2.5*float(np.median(residual)))
            if np.count_nonzero(keep) < 3:
                break
        for line in family:
            line[1] = np.polyval(fit, line[0])
            line[2] = line[0]-line[1]*extent/2

    def intersection(v, h):
        x = (v[2]+v[1]*h[2])/(1-v[1]*h[1])
        return [x, h[1]*x+h[2]]

    source = np.float32([intersection(vs[0], hs[0]), intersection(vs[-1], hs[0]),
                         intersection(vs[-1], hs[-1]), intersection(vs[0], hs[-1])])
    x0, x1, y0, y1 = vs[0][0], vs[-1][0], hs[0][0], hs[-1][0]
    if x1-x0 < width*.2 or y1-y0 < height*.15:
        return result(gray)
    target = np.float32([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    matrix = cv2.getPerspectiveTransform(source, target)
    return result(cv2.warpPerspective(gray, matrix, (width, height), flags=cv2.INTER_CUBIC, borderValue=255), matrix)


def detect_tables(gray, threshold=None):
    """Find independent grids using local dimensions, even on mixed text pages."""
    height, width = gray.shape
    _, ink = cv2.threshold(gray, threshold or 0, 255,
                           cv2.THRESH_BINARY_INV | (cv2.THRESH_OTSU if threshold is None else 0))
    # A page-wide threshold follows dark text and can lose lighter grid ink.
    # Local contrast is used only to find rules, never to alter OCR pixels.
    local_ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 31, 10)
    ink = ink | local_ink
    vertical = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                              np.ones((max(30, height // 40), 1), np.uint8))
    horizontal = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                                np.ones((1, max(40, width // 30)), np.uint8))
    connected = cv2.dilate(vertical | horizontal, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables = []
    table_rules = np.zeros_like(gray)
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w < width * .15 or h < max(40, height * .025):
            continue
        vm = vertical[y:y+h, x:x+w]
        hm = horizontal[y:y+h, x:x+w]
        vc, _ = cv2.findContours(vm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hc, _ = cv2.findContours(hm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        def joined_rule(box, perpendicular, vertical_axis):
            xx,yy,ww,hh=box
            # A short rule may divide only one group of rows/columns. Accept
            # it when it terminates on two perpendicular rules, not according
            # to its fraction of the entire table's height/width.
            if vertical_axis:
                crossing=np.any(perpendicular[max(0,yy-3):yy+hh+3,
                                                max(0,xx-3):xx+ww+3],axis=1)
            else:
                crossing=np.any(perpendicular[max(0,yy-3):yy+hh+3,
                                                max(0,xx-3):xx+ww+3],axis=0)
            hits=_peaks(np.flatnonzero(crossing),gap=3)
            length=hh if vertical_axis else ww
            return len(hits)>=2 and hits[-1]-hits[0]>=length*.75
        valid_v=[c for c in vc if (lambda b:b[3]>h*.3 or
                 (b[3]>b[2]*5 and joined_rule(b,hm,True)))(cv2.boundingRect(c))]
        valid_h=[c for c in hc if (lambda b:b[2]>w*.25 or
                 (b[2]>b[3]*5 and joined_rule(b,vm,False)))(cv2.boundingRect(c))]
        xs = _peaks(sorted(xx+ww//2 for xx,yy,ww,hh in map(cv2.boundingRect,valid_v)))
        ys = _peaks(sorted(yy+hh//2 for xx,yy,ww,hh in map(cv2.boundingRect,valid_h)))
        # Continuations may consist of one tall row with several real columns.
        if len(xs) < 3 or len(ys) < 2:
            continue
        # Require real intersections; decorative rules are not a grid.
        intersections = sum(bool(np.any(vm[max(0, yy-8):yy+9, max(0, xx-8):xx+9])
                                 and np.any(hm[max(0, yy-8):yy+9, max(0, xx-8):xx+9]))
                            for xx in xs for yy in ys)
        if intersections < 6:
            continue
        # Morphology also finds upright letter stems in short table images.
        # Only confirmed grid rules may be erased from recognition crops.
        local_rules=np.zeros((h,w),np.uint8)
        cv2.drawContours(local_rules,valid_v+valid_h,-1,255,cv2.FILLED)
        table_rules[y:y+h,x:x+w]|=local_rules
        rows, cols = len(ys)-1, len(xs)-1
        def rule_windows(contours, positions, vertical_axis):
            windows = []
            for i, position in enumerate(positions):
                radii = [8]
                for xx, yy, ww, hh in map(cv2.boundingRect, contours):
                    start, length = (xx, ww) if vertical_axis else (yy, hh)
                    if abs(start+length/2-position) <= 6:
                        radii.append(max(position-start, start+length-position)+3)
                distances = [abs(position-p) for p in positions if p != position]
                # Follow the observed drift of this rule, without reaching a
                # neighboring rule or inventing a border in a merged header.
                windows.append(int(min(max(radii), min(distances)*.35)))
            return windows
        v_windows = rule_windows(valid_v, xs, True)
        h_windows = rule_windows(valid_h, ys, False)
        parent = list(range(rows * cols))

        def root(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        def join(a, b):
            parent[root(b)] = root(a)

        # A missing internal border indicates a merged cell. Empty text does not.
        for r in range(rows):
            cell_h = ys[r+1] - ys[r] if r + 1 < rows else (ys[-1] - ys[-2] if rows > 1 else 30)
            inset_y = min(5, max(0, (cell_h-1)//3))
            iy0, iy1 = ys[r]+inset_y, ys[r+1]-inset_y
            for c in range(cols):
                k = r * cols + c
                cell_w = xs[c+1] - xs[c] if c + 1 < cols else (xs[-1] - xs[-2] if cols > 1 else 30)
                inset_x = min(5, max(0, (cell_w-1)//3))
                ix0, ix1 = xs[c]+inset_x, xs[c+1]-inset_x
                if c + 1 < cols:
                    win_v = v_windows[c+1]
                    edge_v = vm[iy0:iy1, max(0, xs[c+1]-win_v):min(w, xs[c+1]+win_v+1)]
                    has_v = False
                    if edge_v.size and np.mean(np.any(edge_v, axis=1)) >= .55:
                        has_v = True
                    else:
                        patch_ink_v = ink[y+iy0:y+iy1, x+max(0, xs[c+1]-win_v):x+min(w, xs[c+1]+win_v+1)]
                        k_h = max(8, min(25, (ys[r+1]-ys[r]-10)//3))
                        loc_v = (cv2.morphologyEx(patch_ink_v, cv2.MORPH_OPEN, np.ones((min(k_h, patch_ink_v.shape[0]), 1), np.uint8))
                                 if patch_ink_v.size else patch_ink_v)
                        if loc_v.size and np.mean(np.any(loc_v, axis=1)) >= .70:
                            has_v = True
                    if threshold is None and has_v:
                        patch_gray = gray[y+iy0:y+iy1, x+max(0,xs[c+1]-win_v):x+min(w,xs[c+1]+win_v+1)]
                        if patch_gray.size and np.median(patch_gray) < 225:
                            # Texture in a shaded heading is not a cell edge.
                            strict = (cv2.GaussianBlur(patch_gray,(3,3),0) < 130).astype(np.uint8)
                            strict = cv2.morphologyEx(strict,cv2.MORPH_OPEN,np.ones((max(8,min(25,cell_h//3)),1),np.uint8))
                            has_v = np.mean(np.any(strict,axis=1)) >= .55
                    if not has_v:
                        join(k, k+1)
                if r + 1 < rows:
                    win_h = h_windows[r+1]
                    edge_h = hm[max(0, ys[r+1]-win_h):min(h, ys[r+1]+win_h+1), ix0:ix1]
                    has_h = False
                    if edge_h.size and np.mean(np.any(edge_h, axis=0)) >= .55:
                        has_h = True
                    else:
                        patch_ink_h = ink[y+max(0, ys[r+1]-win_h):y+min(h, ys[r+1]+win_h+1), x+ix0:x+ix1]
                        k_w = max(8, min(25, (xs[c+1]-xs[c]-10)//3))
                        loc_h = (cv2.morphologyEx(patch_ink_h, cv2.MORPH_OPEN, np.ones((1, min(k_w, patch_ink_h.shape[1])), np.uint8))
                                 if patch_ink_h.size else patch_ink_h)
                        if loc_h.size and np.mean(np.any(loc_h, axis=0)) >= .70:
                            has_h = True
                    if not has_h:
                        join(k, k+cols)
        groups = defaultdict(list)
        for k in range(rows * cols):
            groups[root(k)].append(divmod(k, cols))
        cells = []
        for members in groups.values():
            r0, c0 = map(min, zip(*members))
            r1, c1 = map(max, zip(*members))
            # Broken borders can produce an L shape: keep those cells separate.
            rectangles = [(r0, c0, r1, c1)] if len(members) == (r1-r0+1)*(c1-c0+1) else [
                (r, c, r, c) for r, c in members]
            for r0, c0, r1, c1 in rectangles:
                cells.append({"row": r0, "col": c0, "rowspan": r1-r0+1, "colspan": c1-c0+1,
                              "bbox": [x+xs[c0], y+ys[r0], x+xs[c1+1], y+ys[r1+1]],
                              "border_search": max(v_windows[c0], v_windows[c1+1],
                                                   h_windows[r0], h_windows[r1+1]), "text": ""})
        tables.append({"type": "table", "bbox": [x+xs[0], y+ys[0], x+xs[-1], y+ys[-1]],
                       "xs": [x+xx for xx in xs], "ys": [y+yy for yy in ys],
                       "cells": sorted(cells, key=lambda c: (c["row"], c["col"])),
                       "grid": [[""] * cols for _ in range(rows)]})
    return sorted(tables, key=lambda t: (t["bbox"][1], t["bbox"][0])), table_rules




def _tesseract_words(gray, language, psm, cancelled, quality=False, whitelist=None):
    if cancelled():
        return []
    lang = {"auto": "vie", "vi": "vie", "en": "eng"}.get(language, language)
    command = [os.environ.get("TESSERACT_CMD", "tesseract"), "stdin", "stdout", "-l", lang,
               "--psm", str(psm), "--dpi", "300", "-c", "tessedit_create_tsv=1"]
    if whitelist:
        command.extend(['-c', 'tessedit_char_whitelist='+whitelist])
    tessdata = os.environ.get("OCR_TESSDATA_DIR")
    best_dir = os.path.join(os.environ.get('OCR_MODEL_DIR','/app/models'),'tessdata_best')
    if quality and not tessdata and all(os.path.isfile(os.path.join(best_dir,l+'.traineddata')) for l in lang.split('+')):
        tessdata = best_dir
    if tessdata:
        command.extend(["--tessdata-dir", tessdata])
    ok, encoded = cv2.imencode(".pgm", gray)
    if not ok:
        raise RuntimeError("Could not encode OCR image")
    env = dict(os.environ, OMP_THREAD_LIMIT="1")
    # A file avoids stalled stdin pipes when several pages start simultaneously.
    # communicate(timeout=...) can then be retried without a partially sent image.
    image_file = tempfile.NamedTemporaryFile(suffix=".pgm", delete=False)
    try:
        image_file.write(encoded.tobytes())
    finally:
        image_file.close()
    command[1] = image_file.name
    process = None
    started = time.monotonic()
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env)
        while True:
            try:
                stdout, stderr = process.communicate(timeout=.5)
                break
            except subprocess.TimeoutExpired:
                if cancelled():
                    process.kill()
                    process.communicate()
                    return []
                if time.monotonic() - started > 120:
                    raise TimeoutError("Tesseract exceeded 120 seconds for one image")
        if process.returncode:
            raise RuntimeError("Tesseract failed: " + stderr.decode("utf-8", errors="replace")[-1500:])
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        os.unlink(image_file.name)
    words = []
    for row in csv.DictReader(io.StringIO(stdout.decode("utf-8")), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = unicodedata.normalize("NFC", (row.get("text") or "").strip())
        if row.get("level") != "5" or not text:
            continue
        x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        words.append({"text": text, "confidence": float(row["conf"]), "bbox": [x, y, x+w, y+h],
                      "line": tuple(row[k] for k in ("block_num", "par_num", "line_num"))})
    return words


def _lines(words, page_idx, split_columns=True):
    grouped = defaultdict(list)
    for word in words:
        grouped[word["line"]].append(word)
    lines = []
    for group in grouped.values():
        group.sort(key=lambda w: w["bbox"][0])
        # Tesseract may combine both sides of an official header into one line.
        # Split only large physical gaps, then preserve the separate columns.
        chunks = [[]]
        median_h = np.median([w["bbox"][3]-w["bbox"][1] for w in group])
        gaps = [b['bbox'][0]-a['bbox'][2] for a,b in zip(group,group[1:])
                if b['bbox'][0] > a['bbox'][2]]
        # Normal inter-word gap is ~0.25..0.5 line height. Any gap > 2.2 line heights
        # (or > 70px) is a physical column split or tab, not inter-word spacing.
        split_gap = min(max(median_h*2.2, 70.0), max(median_h*1.3, float(np.median(gaps))*2.5 if gaps else 70.0))
        for word in group:
            if split_columns and chunks[-1] and word["bbox"][0] - chunks[-1][-1]["bbox"][2] > split_gap:
                chunks.append([])
            chunks[-1].append(word)
        for chunk in chunks:
            box = [min(w["bbox"][0] for w in chunk), min(w["bbox"][1] for w in chunk),
                   max(w["bbox"][2] for w in chunk), max(w["bbox"][3] for w in chunk)]
            lines.append({"text": " ".join(w["text"] for w in chunk), "bbox": box,
                          "source_paragraph": chunk[0]["line"][:2],
                          "words": chunk,
                          "word_confidences": [(w['text'],w['confidence']) for w in chunk],
                          "min_confidence": min(w['confidence'] for w in chunk),
                          "confidence": sum(w["confidence"] for w in chunk)/len(chunk), "page": page_idx+1})
    return sorted(lines, key=lambda b: (b["bbox"][1], b["bbox"][0]))


def _column_region(candidates, width):
    """Find a contiguous region with a repeated physical column gutter.

    The region can start below an unrelated signature banner and can end above
    footnotes. Its position on the page and its wording do not identify it.
    """
    candidates=sorted(candidates,key=lambda line:(line['bbox'][1],line['bbox'][0]))
    splits = []
    for a in candidates:
        for b in candidates:
            ax0,ay0,ax1,ay1 = a['bbox']
            bx0,by0,bx1,by1 = b['bbox']
            overlap = min(ay1,by1)-max(ay0,by0)
            if bx0-ax1 > max(width*.025,min(ay1-ay0,by1-by0)*1.2) and overlap > min(ay1-ay0,by1-by0)*.3:
                split = (ax1+bx0)/2
                if width*.2 < split < width*.8:
                    for gutter in (split,ax1+width*.005,bx0-width*.005):
                        splits.append((gutter,min(ay0,by0)))
    best = None
    for split,start in splits:
        left,right = [],[]
        for line in candidates:
            x0,y0,x1,y1 = line['bbox']
            if y0 < start:
                continue
            if x0 < split < x1:
                if sum(c.isalnum() for c in line.get('text', '')) == 0 or line.get('confidence', 100) < 50:
                    continue
                break
            (left if x1 <= split else right).append(line)
        if len(left)<2 or len(right)<2:
            continue
        if abs(left[0]['bbox'][1]-right[0]['bbox'][1]) > max(
                left[0]['bbox'][3]-left[0]['bbox'][1],right[0]['bbox'][3]-right[0]['bbox'][1]):
            continue
        if best is None or len(left)+len(right)>sum(map(len,best)):
            best = left,right
    return best


def _header_columns(lines, width, height):
    region = _column_region([line for line in lines if line['bbox'][1]<height*.32], width)
    if region and region[0][0]['bbox'][1] < height * 0.18:
        return region
    return None


def _footer_columns(lines, width, height):
    return _column_region(lines,width)


def _annotate_alignment(lines, bounds, column=False):
    """Infer centering from balanced physical margins, independent of wording."""
    left, right = bounds
    extent = max(1, right-left)
    left_anchored = False
    if column and len(lines)>=2:
        starts = [l['bbox'][0] for l in lines]
        centers = [(l['bbox'][0]+l['bbox'][2])/2 for l in lines]
        height = float(np.median([l['bbox'][3]-l['bbox'][1] for l in lines]))
        left_anchored = (max(starts)-min(starts)<height*.8 and
                         (max(starts)-min(starts))*2+3<max(centers)-min(centers))
    for index, line in enumerate(lines):
        x0, y0, x1, y1 = line['bbox']
        text = line['text'].strip()
        line['align'] = 'left'
        if left_anchored:
            continue
        # List markers and numbered outlines anchor at the left margin.
        if re.match(r'^(?:[-+•*–—]|\w+[.)])\s', text):
            continue
        balanced = abs((x0+x1-left-right)/2) <= max((y1-y0)*.5, extent*.025)
        inset = min(x0-left, right-x1) >= extent*.04
        if balanced and (inset or column):
            if not column and index+1 < len(lines):
                following = lines[index+1]
                nx0,ny0,nx1,ny1 = following['bbox']
                same_paragraph = (line.get('source_paragraph') is not None and
                                  line['source_paragraph'] == following.get('source_paragraph'))
                # An indented first line may have accidentally balanced margins.
                # Its following line, baseline gap and source paragraph reveal
                # the continuation. Real centered titles remain independent.
                if (same_paragraph and x1-x0 > extent*.6 and nx0 < x0-(y1-y0)*.5
                        and 0 <= ny0-y1 <= max(y1-y0,ny1-ny0)*1.2):
                    continue
            line['align'] = 'center'


def _cell_crop(gray, cell, rules=None):
    """Refine each edge locally: paper can remain slightly curved after a warp."""
    x0, y0, x1, y1 = cell["bbox"]
    w, h = x1-x0, y1-y0
    margin = max(6, min(18, int(h*.22)), cell.get('border_search', 0))
    left, top = max(0, x0-margin), max(0, y0-margin)
    crop = gray[top:min(gray.shape[0], y1+margin), left:min(gray.shape[1], x1+margin)]
    ink = (rules[top:top+crop.shape[0], left:left+crop.shape[1]] if rules is not None
           else (crop < 200).astype(np.uint8)*255)
    hm = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((1, max(20, w//4)), np.uint8))
    vm = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((max(20, h//2), 1), np.uint8))

    def edge(position, horizontal):
        mask = hm if horizontal else vm.T
        offset = top if horizontal else left
        cross0, cross1 = ((x0-left+5, x1-left-5) if horizontal else (y0-top+5, y1-top-5))
        center = position-offset
        start, stop = max(0, center-margin), min(mask.shape[0], center+margin+1)
        strip = mask[start:stop, cross0:cross1]
        if not strip.size:
            return 0., float(position)
        contours, _ = cv2.findContours(strip, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0., float(position)
        contour = max(contours, key=lambda c: cv2.boundingRect(c)[2])
        if cv2.boundingRect(contour)[2] < (cross1-cross0)*.45:
            return 0., float(position)
        vx, vy, cx, cy = cv2.fitLine(contour, cv2.DIST_HUBER, 0, .01, .01).flatten()
        slope = float(vy/vx) if abs(vx) > .1 else 0.
        intercept = float(cy+start+offset-slope*(cx+cross0+(left if horizontal else top)))
        return slope, intercept

    ht, hb, vl, vr = edge(y0, True), edge(y1, True), edge(x0, False), edge(x1, False)

    def intersection(v, h):
        x = (v[1]+v[0]*h[1])/(1-v[0]*h[0])
        return [x-left, h[0]*x+h[1]-top]

    quad = np.float32([intersection(vl, ht), intersection(vr, ht),
                       intersection(vr, hb), intersection(vl, hb)])
    target = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    matrix = cv2.getPerspectiveTransform(quad, target)
    aligned = cv2.warpPerspective(crop, matrix, (w, h), borderValue=255)
    if rules is not None:
        mask = rules[top:top+crop.shape[0], left:left+crop.shape[1]]
        mask = cv2.warpPerspective(mask, matrix, (w, h), flags=cv2.INTER_NEAREST)
        aligned[cv2.dilate(mask, np.ones((3,3),np.uint8)) > 0] = 255
    return aligned[2:-2, 2:-2]


def _remove_distant_speckles(binary):
    """Discard tiny detached scan debris, retaining punctuation and accents.

    Small components are kept near full-sized glyphs. A font-relative measure
    avoids assuming a document DPI, language, or particular character value.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(255-binary)
    parts = stats[1:]
    if len(parts)<4:
        return binary
    reference = float(np.percentile(parts[:,3],80))
    anchors = [s for s in parts if s[3]>=max(8,reference*.55) and s[4]>=reference*2
               and s[2]<s[3]*3]
    if len(anchors)<3:
        return binary
    glyph_h = float(np.median([s[3] for s in anchors]))
    # Stacked diacritics can be separated from the main glyph by another
    # accent. Grow proximity through those components instead of measuring
    # every tiny mark against the main letter alone.
    protected = [s for s in parts if s[3]>=glyph_h*.28]
    pending = [(k,stats[k]) for k in range(1,count) if stats[k,3]<glyph_h*.28]
    while pending:
        remaining = []
        for k,(x,y,w,h,area) in pending:
            nearby = any(max(0,ax-(x+w),x-(ax+aw)) <= glyph_h and
                         max(0,ay-(y+h),y-(ay+ah)) <= glyph_h*.35
                         for ax,ay,aw,ah,_ in protected)
            if nearby:
                protected.append(stats[k])
            else:
                remaining.append((k,stats[k]))
        if len(remaining)==len(pending):
            break
        pending = remaining
    for k,_ in pending:
        binary[labels==k] = 255
    return binary


def _prepare_cell(crop, photo=False, return_origin=False, borders_removed=False, preserve_gray=False):
    if not crop.size or np.count_nonzero(crop < 150) < max(8, crop.size*.0005):
        return None
    if not photo and np.median(crop) < 225:
        # Flatten textured gray/green table headings before binarization.
        background = cv2.morphologyEx(crop,cv2.MORPH_CLOSE,np.ones((35,35),np.uint8))
        crop = cv2.divide(crop,background,scale=255)
    level, _ = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    binary = (crop > min(190, level)).astype(np.uint8)*255
    original_binary = binary.copy()
    inv = 255-binary
    ch, cw = crop.shape
    if not borders_removed:
        # An otherwise empty crop can contain a dashed/slanted outer edge.
        # Require several disconnected pieces spanning almost the full height
        # and no ink elsewhere; a single narrow numeral is not sufficient.
        parts=cv2.connectedComponentsWithStats(inv)[2][1:]
        yy,xx=np.nonzero(inv)
        if (len(parts)>=3 and len(xx) and yy.max()-yy.min()>=ch*.8 and
                xx.max()-xx.min()<ch*.20 and
                (xx.max()<cw*.10 or xx.min()>cw*.90) and
                np.ptp(parts[:,1]+parts[:,3]/2)>=ch*.6):
            return None
    hr = cv2.morphologyEx(inv, cv2.MORPH_OPEN, np.ones((1, max(15, cw//3)), np.uint8))
    vr = cv2.morphologyEx(inv, cv2.MORPH_OPEN, np.ones((max(15, ch//2), 1), np.uint8))
    b_my = max(6, min(14, int(ch * 0.18)))
    b_mx = max(6, min(14, int(cw * 0.12)))
    hr[b_my:-b_my, :] = 0
    vr[:, b_mx:-b_mx] = 0
    borders = cv2.dilate(hr | vr, np.ones((2, 2), np.uint8)) > 0
    if borders_removed:
        # The measured grid mask was already erased by _cell_crop. Repeating
        # edge morphology here mistakes tall letters in tight rows for rules.
        borders[:] = False
    binary[borders] = 255
    binary[[0, 1, -2, -1], :] = 255
    binary[:, [0, 1, -2, -1]] = 255
    # Residual horizontal rules inside a merged cell have no letter-like
    # thickness. Remove only long, thin components, not arbitrary punctuation.
    horizontal_fragments = cv2.morphologyEx(255-binary, cv2.MORPH_OPEN,
                                           np.ones((1, max(30, cw//5)), np.uint8))
    if photo:
        binary[cv2.dilate(horizontal_fragments, np.ones((3, 3), np.uint8)) > 0] = 255
    # Size alone cannot identify scan noise: a small period or detached tone
    # mark can occupy only one or two dark pixels. Proximity filtering below
    # removes distant debris while keeping these marks beside printed glyphs.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(255-binary)
    for k in range(1, count):
        cx, cy, c_w, c_h, area = stats[k]
        is_edge = (cy <= 2 or cy + c_h >= ch - 2 or cx <= 2 or cx + c_w >= cw - 2)
        if not borders_removed and is_edge and (c_w >= cw * 0.35 or (c_w / max(1, c_h) >= 3.0 and c_h <= 6) or (c_h / max(1, c_w) >= 3.0 and c_w <= 6)):
            binary[labels == k] = 255
        # A curved/slanted outer rule can sit inside the nominal crop. Require
        # both a near-edge position and a span close to the full cell height;
        # do not treat an ordinary narrow digit in the middle as a border.
        near_side = cx+c_w < cw*.2 or cx > cw*.8
        if not borders_removed and near_side and c_h >= ch*.75 and c_h/max(1, c_w) >= 4:
            ys_line, xs_line = np.where(labels == k)
            covariance = np.cov(np.stack((xs_line, ys_line)))
            eigenvalues = np.linalg.eigvalsh(covariance)
            if eigenvalues[-1] > max(1., eigenvalues[0])*40:
                binary[labels == k] = 255
    binary = _remove_distant_speckles(binary)
    ys, xs = np.where(binary < 180)
    if len(xs) < 8:
        return None
    y0, y1, x0, x1 = max(0, min(ys)-3), min(ch, max(ys)+4), max(0, min(xs)-3), min(cw, max(xs)+4)
    clean_gray = crop.copy()
    # Preserve antialiased accents for neural OCR; the binary mask is only for
    # locating content. Whiten removed rule/noise pixels, not every light pixel.
    removed = (original_binary < 255) & (binary == 255)
    if not preserve_gray:
        clean_gray[borders | (cv2.dilate(removed.astype(np.uint8),np.ones((3,3),np.uint8))>0)] = 255
    result = (binary[y0:y1, x0:x1], clean_gray[y0:y1, x0:x1], crop)
    return (*result,(int(x0)+2,int(y0)+2)) if return_origin else result


def _optical_mark(binary):
    """Read an isolated cross from its two intersecting diagonal strokes."""
    count, labels, stats, _ = cv2.connectedComponentsWithStats((binary < 128).astype(np.uint8))
    if count < 2:
        return None
    largest = 1+int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[largest, cv2.CC_STAT_AREA] < np.count_nonzero(binary < 128)*.6:
        return None
    ys, xs = np.where(labels == largest)
    if len(xs) < 12:
        return None
    ink = (labels[min(ys):max(ys)+1, min(xs):max(xs)+1] == largest).astype(np.uint8)*255
    h, w = ink.shape
    if min(h, w) < 8 or not .45 < w/h < 2.5:
        return None
    segments = cv2.HoughLinesP(ink, 1, np.pi/180, max(5, min(h, w)//4),
                               minLineLength=max(h, w)*.3, maxLineGap=3)
    if segments is None:
        return None
    positive, negative = [], []
    for x0, y0, x1, y1 in segments.reshape(-1, 4):
        if x1 == x0:
            continue
        m = (y1-y0)/(x1-x0)
        if .2 < abs(m) < 5:
            (positive if m > 0 else negative).append((m, y0-m*x0, min(x0, x1), max(x0, x1)))
    tick = False
    for a, b, ax0, ax1 in positive:
        for c, d, cx0, cx1 in negative:
            x = (d-b)/(a-c)
            y = a*x+b
            af, cf = (x-ax0)/(ax1-ax0), (x-cx0)/(cx1-cx0)
            if .15*w < x < .85*w and .15*h < y < .8*h and .15 < af < .85 and .15 < cf < .85:
                return "x"
            if .15*w < x < .75*w and .65*h <= y <= 1.15*h:
                tick = True
    return "✓" if tick else None


def _enhance_photo_cells(crops, language, cancelled, scan=False):
    """Batch codes with a visual recognizer; use VietOCR for Vietnamese lines."""
    from PIL import Image
    from app.services.ocr_service import _get_rapid_engine, _get_vietocr_onnx_predictor
    columns = defaultdict(list)
    for item in crops:
        columns[(id(item[0]), item[1]["col"])].append(item)
    numeric, marks = set(), set()
    for key, items in columns.items():
        values = [item[1]["text"] for item in items if item[1]["row"] > 0 and item[1]["text"]]
        if len(values) >= 3 and sum(bool(re.search(r"\d", s)) for s in values) / len(values) >= .65:
            numeric.add(key)
        elif len(values) >= 3 and sum(len(s) <= 3 and all(not c.isalnum() or c in "xXvV" for c in s)
                                     for s in values) / len(values) >= .5:
            marks.add(key)
    def weak_short_token(cell):
        return 0 < len(cell['text'].strip()) <= 2 and cell.get('confidence',100)<50

    code_items = [item for item in crops if ((id(item[0]), item[1]["col"]) in numeric
                  or weak_short_token(item[1])
                  or (item[1]['text'].strip() and not any(c.isalpha() for c in item[1]['text'])))
                  and '\n' not in item[1]['text'] and (not scan or (item[1]['row']>0
                  and item[1]['colspan']==1 and sum(c.isalpha() for c in item[1]['text']) <= 3))]
    if code_items and not cancelled():
        try:
            engine = _get_rapid_engine()
            if engine is not None:
                # A binary mask can erase a faint digit even when the reader
                # reports high confidence for the remaining digit. Keep the
                # cleaned grayscale strokes for codes as well as prose.
                code_images = [cv2.cvtColor(item[3],cv2.COLOR_GRAY2BGR) for item in code_items]
                results_clean, _ = engine.text_rec(code_images)
                retry_indices = []
                retry_crops = []
                for idx, (item, (text, conf)) in enumerate(zip(code_items, results_clean)):
                    clean_res = text.strip()
                    has_digits = bool(re.search(r"\d", clean_res))
                    if conf < 0.85 or not has_digits or re.search(r'\d[.,]{2,}\d', clean_res):
                        if len(item) > 4 and item[4] is not None:
                            retry_indices.append(idx)
                            retry_crops.append(cv2.cvtColor(item[4], cv2.COLOR_GRAY2BGR))
                if retry_crops:
                    results_retry, _ = engine.text_rec(retry_crops)
                    for idx, (text_r, conf_r) in zip(retry_indices, results_retry):
                        text_c, conf_c = results_clean[idx]
                        c_clean = text_c.strip()
                        r_clean = text_r.strip()
                        c_has = bool(re.search(r"\d", c_clean))
                        r_has = bool(re.search(r"\d", r_clean))
                        malformed = bool(re.search(r'\d[.,]{2,}\d',c_clean))
                        valid_retry = r_has and not re.search(r'\d[.,]{2,}\d',r_clean) and conf_r >= .7
                        if (malformed and valid_retry) or (not c_has and r_has) or (r_has and conf_r > conf_c):
                            results_clean[idx] = (text_r, conf_r)
                        elif not c_has and not r_has and conf_r > conf_c:
                            results_clean[idx] = (text_r, conf_r)

                for item, (text, confidence) in zip(code_items, results_clean):
                    clean_res = text.strip()
                    curr_text = item[1]["text"]
                    curr_has_digits = bool(re.search(r"\d", curr_text))
                    rapid_has_digits = bool(re.search(r"\d", clean_res))
                    min_conf = 0.50 if (not curr_has_digits and rapid_has_digits) else 0.80
                    if (id(item[0]), item[1]['col']) not in numeric:
                        min_conf = .85
                    if confidence >= min_conf and re.fullmatch(r"[\dA-Za-z .,/():=+%<>−–-]+", text):
                        final_text = clean_res if (clean_res and any(c.isalnum() for c in clean_res)) else text
                        def independently_confirmed():
                            for scale in (2,1):
                                view = (cv2.resize(item[3],None,fx=scale,fy=scale)
                                        if scale>1 else item[3])
                                readings = _tesseract_words(view,'en',7,cancelled,quality=True)
                                if (readings and min(w['confidence'] for w in readings)>=50 and
                                        ''.join(w['text'] for w in readings)==re.sub(r'\s','',final_text)):
                                    return True
                            return False
                        # A Latin code reader cannot override words or their
                        # accents inside an otherwise numeric time/unit cell.
                        if any(c.isalpha() for c in curr_text) and (
                                ''.join(c for c in curr_text if c.isalpha()).casefold()!=
                                ''.join(c for c in final_text if c.isalpha()).casefold()):
                            # A numeric column may contain a digit misread as
                            # a letter. Require a second, unrestricted reader
                            # to agree; real words/units remain protected.
                            short_code = sum(c.isalpha() for c in final_text)<=3
                            if (((id(item[0]),item[1]['col']) not in numeric and not weak_short_token(item[1])) or not short_code
                                    or confidence < .9 or sum(c.isalpha() for c in curr_text)>2):
                                continue
                            if not independently_confirmed():
                                continue
                        elif (curr_has_digits and item[1].get('confidence',0)>=80
                              and re.sub(r'\s','',curr_text)!=re.sub(r'\s','',final_text)):
                            # A confident numeric reading is not replaced by
                            # another model's confidence alone, including its
                            # decimal/group separators and arithmetic symbols.
                            if not independently_confirmed():
                                continue
                        if scan and re.search(r'\d[.,]{2,}\d', final_text):
                            readings = _lines(_tesseract_words(item[3], 'en', 7, cancelled), 0)
                            best = max(readings, key=lambda line: line['confidence'], default={})
                            alternative = best.get('text', '')
                            if (best.get('confidence', 0) >= 85
                                    and re.sub(r'\D', '', alternative) == re.sub(r'\D', '', final_text)
                                    and not re.search(r'\d[.,]{2,}\d', alternative)):
                                final_text = alternative
                                confidence = min(confidence, best['confidence']/100)
                        item[1].update(text=final_text, confidence=float(confidence)*100)
        except Exception:
            logger.warning("Table code recognizer unavailable; keeping native OCR", exc_info=True)
    predictor = None
    if not scan and language in ("vi", "vie", "auto") and not cancelled():
        predictor = _get_vietocr_onnx_predictor()
    for item in crops:
        if cancelled():
            break
        table, cell, binary, clean_gray = item[:4]
        full_crop = item[4] if len(item) > 4 else clean_gray
        key = id(table), cell["col"]
        text = cell["text"]
        if key in marks:
            mark = _optical_mark(binary)
            if mark:
                cell.update(text=mark, confidence=85.)
        elif (predictor is not None and (key not in numeric or cell["row"] == 0)
              and "\n" not in text and sum(c.isalpha() for c in text) >= (1 if cell['row']==0 else 2)):
            try:
                prediction = predictor.predict(Image.fromarray(full_crop if cell['row']==0 and len(text)<4 else clean_gray))
                # Reject decoder repetitions or additional words unsupported by
                # the first reading. Never correct names from a dictionary.
                if prediction and len(prediction.split()) <= len(text.split()) and len(prediction) <= len(text)*1.3+3:
                    cell["text"] = prediction.upper() if text.isupper() else prediction
                    if prediction != text:
                        cell["confidence"] = min(cell.get("confidence", 0.), 85.)
            except Exception:
                logger.warning("Vietnamese cell refinement failed; keeping native OCR", exc_info=True)
        elif predictor is not None and key in numeric and cell["row"] > 0 and not bool(re.search(r"\d", cell["text"])):
            try:
                prediction = predictor.predict(Image.fromarray(full_crop))
                pred_clean = prediction.strip()
                if bool(re.search(r"\d", pred_clean)) and re.fullmatch(r"[\dA-Za-z .,/():+%<>−–-]+", pred_clean):
                    cell["text"] = pred_clean
                    cell["confidence"] = 75.
            except Exception:
                pass
        table["grid"][cell["row"]][cell["col"]] = cell["text"]


def _cell_text_bands(image):
    """Locate printed rows before OCR can merge tightly spaced cell lines."""
    ink=(image<180).astype(np.uint8)
    stats=cv2.connectedComponentsWithStats(ink)[2][1:]
    bodies=[h for x,y,w,h,area in stats if h>=6 and area>=h*1.5 and .15<w/max(1,h)<4]
    if not bodies:return [(0,image.shape[0])]
    height=float(np.median(bodies));counts=ink.sum(axis=1)
    rows=np.flatnonzero(counts>=max(2,float(counts.max())*.025))
    if not len(rows):return [(0,image.shape[0])]
    groups=np.split(rows,np.where(np.diff(rows)>max(2,round(height*.22)))[0]+1)
    groups=[g for g in groups if g[-1]-g[0]+1>=height*.4]
    if len(groups)<2:return [(0,image.shape[0])]
    boundaries=[0]+[int((a[-1]+b[0])//2) for a,b in zip(groups,groups[1:])]+[image.shape[0]]
    return list(zip(boundaries,boundaries[1:]))


def _recognize_cells(gray, tables, rules, language, cancelled, photo=False, low_resolution=False):
    crops = []
    for table in tables:
        for cell in table["cells"]:
            # Scanned paper can have the same curved cell edges as a photo.
            # Follow each local border before trimming, preserving nearby accents.
            # Use the page's rule mask even for photos: a curved outer border
            # can survive local cleanup as several short character-like pieces.
            crop = _cell_crop(gray, cell, rules=rules)
            prepared = _prepare_cell(crop, photo=photo, return_origin=True,
                                     borders_removed=rules is not None,preserve_gray=low_resolution)
            if prepared is None:
                continue
            cell['content_origin'] = prepared[-1]
            crops.append((table, cell, *prepared[:3]))
    index = 0
    while index < len(crops) and not cancelled():
        batch, sheet_height = [], 20
        while index < len(crops):
            item = crops[index]
            step = item[2].shape[0] + 36
            if batch and sheet_height + step > 10000:
                break
            batch.append(item)
            sheet_height += step
            index += 1
        sheet_width = max(item[2].shape[1] for item in batch) + 40
        sheet = np.full((sheet_height, sheet_width), 255, np.uint8)
        visual_sheet = sheet.copy()
        locations, top = [], 20
        for item in batch:
            table, cell, crop = item[0], item[1], item[2]
            h, w = crop.shape
            sheet[top:top+h, 20:20+w] = crop
            if visual_sheet is not None:
                visual_sheet[top:top+h, 20:20+w] = item[3]
            locations.append((top, top+h, table, cell))
            top += h + 36
        # Small table print needs more samples per glyph than page prose.
        # Read grayscale (retaining faint marks), and return boxes to the
        # original coordinate system before layout or font measurements.
        components=cv2.connectedComponentsWithStats((sheet<128).astype(np.uint8))[2][1:]
        heights=[h for x,y,w,h,area in components if h>=6 and area>=h*1.5 and .15<w/max(1,h)<4]
        recognition_scale=min(3,max(1,round(36/float(np.median(heights))))) if heights else 1
        recognition_image=(cv2.resize(visual_sheet,None,fx=recognition_scale,fy=recognition_scale,
                                     interpolation=cv2.INTER_CUBIC) if recognition_scale>1 else visual_sheet)
        words = _tesseract_words(recognition_image, language, 6, cancelled, quality=True)
        if recognition_scale>1:
            for word in words:
                word['bbox']=[round(v/recognition_scale) for v in word['bbox']]
        cell_lines=[]
        for top, bottom, table, cell in locations:
            selected = [word for word in words
                        if top <= (word["bbox"][1]+word["bbox"][3])/2 < bottom]
            if low_resolution:
                item=next(item for item in batch if item[1] is cell)
                alternate=[]
                for band_index,(a,b) in enumerate(_cell_text_bands(item[3])):
                    view=cv2.copyMakeBorder(item[3][a:b],4,4,4,4,cv2.BORDER_CONSTANT,value=255)
                    reading=_tesseract_words(view,language,7,cancelled,quality=True)
                    for word in reading:
                        x,y,xx,yy=word['bbox']
                        alternate.append(dict(word,bbox=[x+16,y+top+a-4,xx+16,yy+top+a-4],
                                             line=(0,0,band_index)))
                quality=lambda ws:sum(w['confidence']*len(w['text']) for w in ws)/max(1,sum(len(w['text']) for w in ws))
                # Keep complete, confident contact-sheet detections. Separate
                # rows repair collapsed segmentation, but must not replace a
                # multi-line header with a short fragment or damage a date.
                if (alternate and len({w['line'] for w in alternate})>=len({w['line'] for w in selected})
                        and quality(alternate)>quality(selected)+2):
                    selected=alternate
            # Column boundaries are already known inside a cell. Large word
            # gaps are justification, not additional lines or page columns.
            lines = _lines(selected, 0, split_columns=False)
            if low_resolution:
                bands=_cell_text_bands(item[3])
                for line in lines:
                    centers=[(w['bbox'][1]+w['bbox'][3])/2-top for w in line['words']]
                    center=float(np.median(centers))
                    a,b=next(((a,b) for a,b in bands if a<=center<b),(0,item[3].shape[0]))
                    line['raster_row_limits']=(top+a,top+b)
            cell_lines.append((top,table,cell,selected,lines))
        # Verify the contact sheet together: isolated numeric cells use a
        # single batched reader rather than hundreds of one-cell calls.
        all_lines=[line for _,_,_,_,lines in cell_lines for line in lines]
        _refine_scan_lines(all_lines,visual_sheet,language,cancelled,refine_numeric=False)
        # Measure typography after the final visual code reading. Otherwise
        # a missed comma in stale word metadata can inflate a digit's size.
        for _,table,cell,selected,lines in cell_lines:
            cell['text'] = '\n'.join(line['text'] for line in lines)
            cell['confidence'] = sum(w['confidence'] for w in selected)/len(selected) if selected else 0.
        _enhance_photo_cells(batch,language,cancelled,scan=True)
        for top,_,cell,_,lines in cell_lines:
            if len(lines)==1 and lines[0]['text']!=cell['text']:
                lines[0].update(text=cell['text'],confidence=cell['confidence'])
            elif not lines and cell['text'].strip():
                item=next(item for item in batch if item[1] is cell)
                yy,xx=np.nonzero(item[2]<180)
                if len(xx):
                    box=[int(xx.min()+20),int(yy.min()+top),int(xx.max()+21),int(yy.max()+top+1)]
                    word=dict(text=cell['text'],bbox=box,confidence=cell['confidence'])
                    lines.append(dict(text=cell['text'],bbox=box,confidence=cell['confidence'],
                                      words=[word],word_confidences=[(word['text'],word['confidence'])]))
        all_lines=[line for _,_,_,_,lines in cell_lines for line in lines]
        from app.services.ocr_typography import annotate_lines
        annotate_lines(all_lines,visual_sheet,low_resolution=low_resolution)
        for top,table,cell,selected,lines in cell_lines:
            # Line boxes are relative to the cell for both scans and photos;
            # the DOCX writer positions cell paragraphs from the cell's edge.
            ox,oy = cell['content_origin']
            cell['source_lines'] = [dict(line,bbox=[line['bbox'][0]-20+ox,line['bbox'][1]-top+oy,
                line['bbox'][2]-20+ox,line['bbox'][3]-top+oy]) for line in lines]
            cell["text"] = "\n".join(line["text"] for line in lines)
            cell["confidence"] = (sum(line["confidence"] for line in lines) /
                                   len(lines) if lines else 0.)
            table["grid"][cell["row"]][cell["col"]] = cell["text"]


def process_page(args):
    """Read page layout natively, with selective neural recognition for photos."""
    from app.services.ocr_service import is_ocr_job_cancelled, _merge_lines_into_paragraphs
    page_idx, pdf_bytes, pil_img, preserve_tables, language, options = args[:6]
    options = options or {}
    cancelled = lambda: is_ocr_job_cancelled(options.get("job_id"))
    if cancelled():
        return {"page_idx": page_idx, "blocks": [], "table_grid": None, "page_text": ""}
    marginal_images = []
    rotation = 0
    if pdf_bytes is not None:
        import fitz
        with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
            pix = document[page_idx].get_pixmap(dpi=300, colorspace=fitz.csRGB, alpha=False)
            rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()
            for box in options.get('_footer_regions', {}).get(page_idx, []):
                import base64
                x0,y0,x1,y1 = [round(v*(pix.width if k%2 == 0 else pix.height)) for k,v in enumerate(box)]
                crop = rgb[max(0,y0):min(pix.height,y1),max(0,x0):min(pix.width,x1)]
                if not crop.size:
                    continue
                encoded = cv2.imencode('.png',cv2.cvtColor(crop,cv2.COLOR_RGB2BGR))[1]
                marginal_images.append({'type':'image', 'role':'footer',
                                        'data':base64.b64encode(encoded).decode('ascii'),
                                        'bbox':[x0,y0,x1,y1],
                                        'width_fraction':box[2]-box[0],
                                        'align':'right' if box[0] > .5 else 'left'})
                rgb[max(0,y0-2):y1+3,max(0,x0-2):x1+3] = 255
            # A separate tiny image below the scanned sheet is scanner branding.
            # It is not part of the page's text or table content.
            for image_info in document[page_idx].get_images():
                for rect in document[page_idx].get_image_rects(image_info[0]):
                    if rect.y0 > document[page_idx].rect.height*.94 and rect.width < document[page_idx].rect.width*.25:
                        x0,y0,x1,y1 = (int(v*300/72) for v in rect)
                        rgb[max(0,y0-2):y1+3,max(0,x0-2):x1+3] = 255
            unfiltered_gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
            gray = _scan_text_image(rgb)
            from app.services.ocr_orientation import detect_rotation, rotate_image
            rotation = detect_rotation(gray,cancelled,
                                       lambda probe: _tesseract_words(probe,language,6,cancelled))
            gray = rotate_image(gray,rotation)
            unfiltered_gray = rotate_image(unfiltered_gray,rotation)
            source_rgb = rotate_image(rgb,rotation)
            for element in marginal_images:
                x0,y0,x1,y1 = element['bbox']
                if rotation == 90:
                    element['bbox'] = [pix.height-y1,x0,pix.height-y0,x1]
                elif rotation == 180:
                    element['bbox'] = [pix.width-x1,pix.height-y1,pix.width-x0,pix.height-y0]
                elif rotation == 270:
                    element['bbox'] = [y0,pix.width-x1,y1,pix.width-x0]
                if rotation:
                    decoded = cv2.imdecode(np.frombuffer(base64.b64decode(element['data']),np.uint8),cv2.IMREAD_COLOR)
                    element['data'] = base64.b64encode(cv2.imencode('.png',rotate_image(decoded,rotation))[1]).decode('ascii')
    else:
        source_rgb = np.asarray(pil_img.convert("RGB"))
        unfiltered_gray = cv2.cvtColor(source_rgb, cv2.COLOR_RGB2GRAY)
        gray = _scan_text_image(source_rgb)
    if pdf_bytes is None:
        # Check if the image is already a clean, flat document/screenshot with a bright uniform background
        is_clean_doc = bool(np.mean(gray) > 210 and np.percentile(gray, 90) >= 235)
        if is_clean_doc:
            photo = False
            gray, deskew_matrix = _deskew(gray, return_matrix=True)
            source_rgb = cv2.warpAffine(source_rgb, deskew_matrix, (gray.shape[1], gray.shape[0]),
                                        flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))
            unfiltered_gray = cv2.warpAffine(unfiltered_gray, deskew_matrix, (gray.shape[1], gray.shape[0]),
                                             flags=cv2.INTER_CUBIC, borderValue=255)
            matrix = np.eye(3)
        else:
            photo = True
            gray, matrix = _rectify_photo(_normalize_photo(gray), return_matrix=True)
            source_rgb=cv2.warpPerspective(source_rgb,matrix,(gray.shape[1],gray.shape[0]),
                                           flags=cv2.INTER_CUBIC,borderValue=(255,255,255))
            unfiltered_gray=cv2.warpPerspective(unfiltered_gray,matrix,(gray.shape[1],gray.shape[0]),
                                                flags=cv2.INTER_CUBIC,borderValue=255)
    else:
        photo = False
        gray, deskew_matrix = _deskew(gray, return_matrix=True)
        unfiltered_gray = cv2.warpAffine(unfiltered_gray,deskew_matrix,
                                        (gray.shape[1],gray.shape[0]),flags=cv2.INTER_CUBIC,borderValue=255)
        source_rgb=cv2.warpAffine(source_rgb,deskew_matrix,(gray.shape[1],gray.shape[0]),
                                 flags=cv2.INTER_CUBIC,borderValue=(255,255,255))
        for element in marginal_images:
            x0,y0,x1,y1 = element['bbox']
            corners = cv2.transform(np.float32([[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]]),deskew_matrix)[0]
            element['bbox'] = [float(corners[:,0].min()),float(corners[:,1].min()),
                               float(corners[:,0].max()),float(corners[:,1].max())]
    height, width = gray.shape
    from app.services.ocr_scan_evidence import remove_scan_edge_rules
    gray = remove_scan_edge_rules(gray)
    tables, rules = detect_tables(gray, threshold=210 if photo else None) if preserve_tables else ([], None)
    body = gray.copy()
    for table in tables:
        x0, y0, x1, y1 = table["bbox"]
        body[max(0,y0-6):y1+7, max(0,x0-6):x1+7] = 255
    lines = _lines(_tesseract_words(body, language, 3, cancelled, quality=True), page_idx)
    from app.services.ocr_typography import split_underlined_labels
    lines = split_underlined_labels(lines,body)
    from app.services.ocr_graphics import extract_seal_graphics, extract_rule_graphics, extract_inline_annotations, extract_marginal_ink, extract_monochrome_graphics
    annotations, annotation_mask = extract_inline_annotations(source_rgb,body,lines)
    if annotations:
        body[annotation_mask>0] = 255
        # Re-read the remaining printed pixels instead of deleting a guessed
        # suffix from a token which may also contain legitimate punctuation.
        for line in lines:
            x0,y0,x1,y1=line['bbox']
            if not np.any(annotation_mask[y0:y1,x0:x1]):
                continue
            from app.services.ocr_text_refinement import crop_with_accents
            crop,(ox,oy)=crop_with_accents(body,line['bbox'],return_origin=True)
            words=_tesseract_words(crop,language,7,cancelled,quality=True)
            if words:
                line.update(text=' '.join(w['text'] for w in words),
                            confidence=sum(w['confidence'] for w in words)/len(words),
                            words=[dict(w,bbox=[w['bbox'][0]+ox,w['bbox'][1]+oy,w['bbox'][2]+ox,w['bbox'][3]+oy]) for w in words],
                            word_confidences=[(w['text'],w['confidence']) for w in words])
                boxes = [word['bbox'] for word in line['words']]
                line['bbox'] = [min(b[0] for b in boxes),min(b[1] for b in boxes),
                                max(b[2] for b in boxes),max(b[3] for b in boxes)]
    marginal_images.extend(annotations)
    marginal_ink=extract_marginal_ink(source_rgb,lines)
    graphics=[g for g in extract_seal_graphics(source_rgb,lines)
              if not any(m['bbox'][0]<=g['bbox'][0] and m['bbox'][1]<=g['bbox'][1] and
                         m['bbox'][2]>=g['bbox'][2] and m['bbox'][3]>=g['bbox'][3] for m in marginal_ink)]
    graphics.extend(marginal_ink)
    graphics.extend(extract_rule_graphics(source_rgb,lines))
    graphics.extend(extract_monochrome_graphics(source_rgb,body,lines))
    from app.services.ocr_graphics import separate_seal_fragments
    lines,fragments=separate_seal_fragments(body,lines,graphics)
    graphics.extend(fragments)
    for graphic in graphics:
        x0,y0,x1,y1=graphic['bbox']
        inside = lambda line: (x0<=(line['bbox'][0]+line['bbox'][2])/2<=x1
                               and y0<=(line['bbox'][1]+line['bbox'][3])/2<=y1)
        if graphic.get('overlay'):
            # Text stays editable even when an overlapping stamp makes its
            # reading uncertain. Pixel evidence below identifies residue.
            continue
        if graphic.get('role')=='initials':
            from app.services.ocr_graphics import erase_initials_ink
            erase_initials_ink(body,graphic)
        else:
            body[y0:y1,x0:x1]=255
        lines=[line for line in lines if not inside(line)]
    marginal_images.extend(graphics)
    lines = [l for l in lines if not _is_graphic_residue(l, unfiltered_gray, gray,
                   [g['bbox'] for g in graphics if g.get('role')=='seal'])]
    # Small, uncertain text can be a footnote or exponent. Size and OCR
    # confidence alone are not evidence that the region is empty/noise.
    lines = [l for l in lines if not _is_duplicate_fragment(l, lines,
                  [g['bbox'] for g in graphics if g.get('role')=='seal'])]
    lines = [l for l in lines if not (l['bbox'][1]>height*.9 and re.fullmatch(r'\d{1,4}',l['text']))]
    from app.services.ocr_text_refinement import remove_blank_symbol_words
    from app.services.ocr_scan_evidence import remove_scan_specks, is_scan_rule_fragment, is_duplicate_diacritic
    lines = [line for line in lines if not is_duplicate_diacritic(line,lines,body)]
    lines = [line for line in lines if not is_scan_rule_fragment(line,body)]
    remove_scan_specks(lines,body)
    for line in lines:
        remove_blank_symbol_words(line,body)
    lines=[line for line in lines if line['text'].strip()]
    _refine_scan_lines(lines, body, language, cancelled, source_rgb=source_rgb)
    from app.services.ocr_inline import recover_inline_scripts
    from app.services.ocr_service import _get_rapid_engine, _get_vietocr_onnx_predictor
    def read_codes(crops):
        engine = _get_rapid_engine()
        return (engine.text_rec([cv2.cvtColor(c,cv2.COLOR_GRAY2BGR) for c in crops])[0]
                if engine is not None else [])
    def read_inline(crop, isolated=False):
        if isolated and language in ('vi','vie','auto'):
            from PIL import Image
            predictor = _get_vietocr_onnx_predictor(use_gpu=os.getenv('OCR_SCAN_DEVICE','auto').lower()!='cpu')
            if predictor is not None:
                return predictor.predict(Image.fromarray(crop)).strip(),100.
        words = _tesseract_words(cv2.resize(crop,None,fx=2,fy=2),language,
                                 10 if isolated else 7,cancelled,quality=True)
        return ' '.join(w['text'] for w in words),min((w['confidence'] for w in words),default=0)
    recover_inline_scripts(lines,body,read_codes,read_inline,cancelled)
    from app.services.ocr_typography import annotate_lines
    low_resolution = pdf_bytes is None and pil_img.info.get('ocr_source_scale',1)>1
    annotate_lines(lines,body,low_resolution=low_resolution)
    if tables:
        _recognize_cells(gray, tables, rules, language, cancelled, photo=photo,low_resolution=low_resolution)
        if photo and language in ('vi', 'vie', 'auto'):
            from app.services.ocr_handwriting import refine_handwriting
            rgb = cv2.warpPerspective(np.asarray(pil_img.convert('RGB')), matrix,
                                       (width, height), borderValue=(255,255,255))
            refine_handwriting(gray, rgb, tables, cancelled)
    header_cols = _header_columns(lines,width,height)
    header_ids = {id(b) for col in (header_cols or []) for b in col}
    remaining = [b for b in lines if id(b) not in header_ids]
    footer_cols = _footer_columns(remaining,width,height)
    footer_ids = {id(b) for col in (footer_cols or []) for b in col}
    remaining = [b for b in remaining if id(b) not in footer_ids]
    boxes = [b['bbox'] for b in remaining] + [t['bbox'] for t in tables]
    if boxes:
        bounds = (float(np.percentile([b[0] for b in boxes], 10)),
                  float(np.percentile([b[2] for b in boxes], 90)))
        _annotate_alignment(remaining, bounds)
    for columns in (header_cols, footer_cols):
        for column in columns or []:
            _annotate_alignment(column, (min(b['bbox'][0] for b in column),
                                        max(b['bbox'][2] for b in column)), column=True)
    elements = []
    regions=list(tables)
    for columns in (header_cols,footer_cols):
        if columns:
            boxes=[b['bbox'] for col in columns for b in col]
            regions.append({'type':'header','columns':columns,'bbox':[
                min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]})
    for region in sorted(regions,key=lambda e:e['bbox'][1]):
        preceding = [b for b in remaining if b["bbox"][1] < region["bbox"][1]]
        remaining = [b for b in remaining if b["bbox"][1] >= region["bbox"][1]]
        elements.extend(dict(p, type="paragraph") for p in _merge_lines_into_paragraphs(preceding, width))
        elements.append(region)
    elements.extend(dict(p, type="paragraph") for p in _merge_lines_into_paragraphs(remaining, width))
    elements.extend(marginal_images)
    parts = []
    for element in elements:
        if element["type"] == "table":
            parts.append("\n".join("\t".join(row) for row in element["grid"]))
        elif element["type"] == "header":
            parts.extend("\n".join(b["text"] for b in col) for col in element["columns"])
        elif element["type"] == "image":
            continue
        else:
            parts.append(element["text"])
    cell_blocks = [dict(cell, page=page_idx+1) for table in tables for cell in table["cells"] if cell["text"]]
    return {"page_idx": page_idx, "page_w": width, "page_h": height,
            "page_width_pt": width*72/300, "page_height_pt": height*72/300,
            "rotation_applied": rotation if not photo else 0, "blocks": lines+cell_blocks,
            "tables": tables, "elements": elements, "header_cols": header_cols,
            "table_grid": tables[0]["grid"] if len(tables) == 1 else None,
            "page_text": "\n\n".join(parts)}
