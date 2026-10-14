"""Alternate recognition views which retain the unmodified source evidence."""
import cv2
import numpy as np


def without_underline(image):
    """Remove a long baseline rule from an alternate view of a text crop.

    This view is never used to erase the source page. Two readers must still
    corroborate a replacement; descenders touching the rule may be incomplete.
    """
    if not image.size or image.shape[1] < 30:
        return image, False
    height, width = image.shape[:2]
    ink = (image < 180).astype(np.uint8)*255
    rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN,
                            np.ones((1, max(20, round(width*.55))), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(rules)
    mask = np.zeros_like(ink, dtype=bool)
    for k in range(1, count):
        x, y, w, h, _ = stats[k]
        if y >= height*.55 and h <= max(2, height*.12) and w >= width*.55:
            mask |= labels == k
    if not mask.any():
        return image, False
    # Opening retains the solid centre of a scanned rule, but can leave its
    # antialiased edge behind. Cover that one-pixel fringe in this alternate
    # view too; the untouched crop remains the independent source evidence.
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    cleaned = image.copy()
    cleaned[mask] = 255
    return cleaned, True
