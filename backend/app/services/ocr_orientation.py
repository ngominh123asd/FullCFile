"""Determine scan orientation before discovering rows, columns or reading order."""
import os
import re
import subprocess
import tempfile
import time

import cv2
import numpy as np


def rotate_image(image, angle):
    operations = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
                  270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    return cv2.rotate(image,operations[angle]) if angle in operations else image


def detect_rotation(gray, cancelled, read_words):
    """Use glyph orientation, with reading-quality arbitration if uncertain.

    Long grid rules must be removed from the orientation probe: on dense
    sideways tables they can dominate OSD's glyph sample and reverse its vote.
    The original pixels remain untouched for actual OCR and table extraction.
    """
    if cancelled():
        return 0
    scale = min(1.,2600/max(gray.shape))
    probe = cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    ink = (probe < 180).astype(np.uint8)
    length = max(40,round(min(probe.shape)*.035))
    horizontal = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,length),np.uint8))
    vertical = cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((length,1),np.uint8))
    probe[cv2.dilate(horizontal|vertical,np.ones((3,3),np.uint8))>0] = 255
    process = None
    with tempfile.NamedTemporaryFile(suffix='.png') as file:
        cv2.imwrite(file.name,probe)
        try:
            process = subprocess.Popen(['tesseract',file.name,'stdout','-l','osd','--psm','0'],
                                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                       env=dict(os.environ,OMP_THREAD_LIMIT='1'))
            started = time.monotonic()
            while True:
                try:
                    output,_ = process.communicate(timeout=.25)
                    break
                except subprocess.TimeoutExpired:
                    if cancelled() or time.monotonic()-started > 15:
                        return 0
            if process.returncode:
                return 0
        except OSError:
            return 0
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()
    output = output.decode('utf-8',errors='replace')
    angle = re.search(r'Rotate:\s*(\d+)',output)
    confidence = re.search(r'Orientation confidence:\s*([\d.]+)',output)
    if not angle or not confidence:
        return 0
    angle = int(angle[1])
    if not angle or angle not in (90,180,270):
        return 0
    if float(confidence[1]) >= 10:
        return angle
    candidates = (0,90,270) if angle in (90,270) else (0,180)
    scores = {}
    for candidate in candidates:
        if cancelled():
            return 0
        words = read_words(rotate_image(probe,candidate))
        scores[candidate] = sum(sum(c.isalpha() for c in w['text'])*w['confidence']/100
                                for w in words if w['confidence'] >= 65)
    best = max(scores,key=scores.get)
    return best if scores[best] >= max(30,scores[0]*1.5) else 0
