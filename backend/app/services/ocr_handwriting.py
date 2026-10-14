"""Local, optional handwriting refinement for colored ink in photographed grids."""
from functools import lru_cache
from pathlib import Path
from threading import Lock
import os

import cv2
import numpy as np

_lock = Lock()


def colored_ink(rgb):
    saturation = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)[:, :, 1]
    baseline = max(25, float(np.percentile(saturation, 75)) + 15)
    return np.clip((saturation.astype(float)-baseline)*5, 0, 255).astype(np.uint8)


def handwriting_crop(ink, cell):
    """Follow the ink line beyond a printed border, stopping at neighboring ink."""
    x0, y0, x1, y1 = cell['bbox']
    h = y1-y0
    left, right = x0+3, x1-3
    top, bottom = max(0, y0-h//2), min(ink.shape[0], y1+h//2)
    patch = ink[top:bottom, left:right]
    profile = np.sum(patch > 70, axis=1).astype(np.float32)
    smoothed = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 11), 0).ravel()
    start, stop = max(0, y0-top+h//6), min(len(profile), y1-top+h//4)
    if stop <= start or smoothed[start:stop].max(initial=0) < 3:
        return None
    peak = start+int(np.argmax(smoothed[start:stop]))
    # Search the valleys half a row either side of this ink line. This avoids
    # assigning an entire connected word to the next row when descenders touch.
    lo0, lo1 = max(0, peak-int(h*.8)), max(1, peak-int(h*.25))
    hi0, hi1 = min(len(profile)-1, peak+int(h*.25)), min(len(profile), peak+int(h*.8))
    a = lo0+int(np.argmin(smoothed[lo0:lo1]+.12*np.abs(np.arange(lo0,lo1)-(peak-h*.55))))
    b = hi0+int(np.argmin(smoothed[hi0:hi1]+.12*np.abs(np.arange(hi0,hi1)-(peak+h*.55))))+1
    patch = patch[a:b]
    ys, xs = np.where(patch > 70)
    if len(xs) < 30 or max(xs)-min(xs) < h*.9:
        return None  # isolated ticks, row numbers and blue speckles
    crop = 255-patch[max(0,min(ys)-2):max(ys)+3, max(0,min(xs)-2):max(xs)+3]
    return cv2.copyMakeBorder(crop, 4, 4, 6, 6, cv2.BORDER_CONSTANT, value=255)


@lru_cache(maxsize=1)
def _model():
    path = Path(os.environ.get('OCR_MODEL_DIR', '/app/models'))/'handwriting'/'transformerocr.pth'
    if not path.is_file():
        return None
    import torch
    from vietocr.tool.translate import build_model
    from app.services.ocr_service import _get_vietocr_default_config
    config = _get_vietocr_default_config()
    torch.set_num_threads(min(2, os.cpu_count() or 1))
    model, vocab = build_model(config)
    model.load_state_dict(torch.load(path, map_location='cpu', weights_only=True))
    model.eval()
    return model, vocab


def predict_handwriting(crop):
    """Keep this model off the normal printed-text path and serialize its use."""
    import torch
    from PIL import Image
    from vietocr.tool.translate import process_input, translate
    with _lock:
        loaded = _model()
        if loaded is None:
            return None
        model, vocab = loaded
        with torch.inference_mode():
            sequence, confidence = translate(
                process_input(Image.fromarray(crop).convert('RGB'), 32, 32, 512),
                model, max_seq_length=64)
        return vocab.decode(sequence[0].tolist()), float(confidence[0])


def refine_handwriting(gray, rgb, tables, cancelled):
    import logging
    import re
    from collections import defaultdict
    from app.services.ocr_service import _get_rapid_engine
    ink = colored_ink(rgb)
    for table in tables:
        columns = defaultdict(list)
        for cell in table['cells']:
            if cell['text']:
                columns[cell['col']].append(cell['text'])
        for cell in table['cells']:
            if cancelled():
                return
            values = columns[cell['col']]
            text = cell['text']
            if not text or len(values) < 3:
                continue
            if sum(s in ('x','X','v','V','✓','+') for s in values) >= len(values)*.6:
                from app.services.ocr_native import _optical_mark
                x0,y0,x1,y1 = cell['bbox']
                pad = (y1-y0)//3
                top,bottom = max(0,y0-pad),min(ink.shape[0],y1+pad)
                patch = ink[top:bottom,x0+3:x1-3]
                n,labels,stats,centers = cv2.connectedComponentsWithStats((patch>70).astype(np.uint8))
                mask = np.zeros_like(patch)
                for k in range(1,n):
                    if stats[k,cv2.CC_STAT_AREA]>=8 and y0 <= centers[k,1]+top < y1:
                        mask[labels==k] = 255
                mark = _optical_mark(255-mask)
                if mark:
                    cell['text'] = mark
                    table['grid'][cell['row']][cell['col']] = mark
                continue
            # Printed text and isolated attendance marks keep their existing
            # path. Colored ink alone is not sufficient evidence of handwriting.
            # Choose a recognizer by observed glyph mix, not by a school-class
            # or telephone schema. Never insert digits or coerce a cell type.
            alphabetic = sum(c.isalpha() for s in values for c in s)
            alphanumeric = sum(c.isalnum() for s in values for c in s)
            is_text = alphabetic > alphanumeric*.6
            mixed_code = 0 < alphabetic < alphanumeric*.6
            x0,y0,x1,y1 = cell['bbox']
            inside = ink[y0+3:y1-3, x0+3:x1-3]
            dark = gray[y0+3:y1-3, x0+3:x1-3] < 170
            if np.count_nonzero(inside > 70) < max(30, np.count_nonzero(dark)*.25):
                continue
            crop = handwriting_crop(ink, cell)
            if crop is None:
                continue
            cell['needs_review'] = True
            cell['review_reason'] = 'Chữ viết tay: cần đối chiếu ảnh gốc, nhất là dấu tiếng Việt và chữ số.'
            try:
                if is_text:
                    result = predict_handwriting(crop)
                    if result:
                        prediction, confidence = result
                        prediction = prediction.strip()
                        if confidence >= .8 and len(prediction.split()) <= len(text.split())+1:
                            cell.update(text=prediction, confidence=min(79., confidence*100))
                else:
                    engine = _get_rapid_engine()
                    result, _ = engine.text_rec(cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR))
                    prediction, confidence = result[0]
                    if mixed_code and (confidence < .85 or not any(c.isalpha() for c in prediction)):
                        result_hand = predict_handwriting((crop >= 150).astype(np.uint8)*255)
                        if result_hand:
                            prediction, confidence = result_hand
                            prediction = prediction.strip()
                    if confidence >= .75 and prediction.strip():
                        cell.update(text=prediction, confidence=min(79., confidence*100))
                table['grid'][cell['row']][cell['col']] = cell['text']
            except Exception:
                logging.getLogger(__name__).warning('Handwriting refinement unavailable; keeping initial reading', exc_info=True)
