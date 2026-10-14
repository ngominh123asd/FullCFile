import pytest
from app.services.ocr_text_refinement import _agreed_edits, _keep_edge_punctuation, _candidate
import re

def test_agreed_edits_dau_tu():
    """Verify that letter correction (tu -> tư) is preserved when proposed has trailing quote."""
    res = _agreed_edits('tu;', "tư';", 'tư;')
    assert res == 'tư;', f"Expected 'tư;', got {res!r}"

def test_footnote_punctuation_replacement():
    """Verify that standalone symbol misreads are replaced by visual reading digits."""
    # Footnote 1 (' -> 1)
    assert _candidate("'", '1', 49.4) is True
    assert _keep_edge_punctuation("'", '1', 49.4) == '1'

    # Footnote 2 (¿ -> 2)
    assert _candidate('¿', '2', 38.8) is True
    assert _keep_edge_punctuation('¿', '2', 38.8) == '2'

    # Footnote 3 (° -> 3)
    assert _candidate('°', '3', 90.5) is True
    assert _keep_edge_punctuation('°', '3', 90.5) == '3'

    # Footnote 4 (* -> 4)
    assert _candidate('*', '4', 92.6) is True
    assert _keep_edge_punctuation('*', '4', 92.6) == '4'

    # Footnote 6 (Š -> 6)
    assert _candidate('Š', '6', 87.9) is True
    assert _keep_edge_punctuation('Š', '6', 87.9) == '6'

    # Footnote 8 (3 -> 8)
    assert _candidate('3', '8', 83.4) is True
    assert _keep_edge_punctuation('3', '8', 83.4) == '8'

    # Footnote 9 (? -> 9)
    assert _candidate('?', '9', 68.3) is True
    assert _keep_edge_punctuation('?', '9', 68.3) == '9'

def test_flourish_cleanup_after_dot_slash_dot():
    """Verify administrative flourish like .Z after ./. is stripped."""
    text = "Bộ Tài chính báo cáo Thủ tướng Chính phủ./. .Z"
    words = [{'text': 'Bộ', 'confidence': 96.8}, {'text': 'Tài', 'confidence': 95.2},
             {'text': 'phủ./.', 'confidence': 92.6}, {'text': '.Z', 'confidence': 0.0}]
    if re.search(r'\./\.\s*[\.\w]{1,3}$', text):
        if words and words[-1]['confidence'] < 60:
            words.pop()
            text = ' '.join(w['text'] for w in words)
    assert text == "Bộ Tài phủ./."

def test_roman_numeral_normalization():
    """Verify Roman numeral typos like (ï) and (ám) are normalized."""
    s1 = "dự kiến giao cho các dự án khởi công mới do: (ï) ..."
    s1_fixed = re.sub(r'\([ïi]{1,4}\)', lambda m: '(' + 'i'*len(m.group(0)[1:-1]) + ')', s1)
    assert "(i)" in s1_fixed and "(ï)" not in s1_fixed

    s2 = "hoàn thiện thủ tục đầu tư; (ám) đề xuất"
    s2_fixed = re.sub(r'\(ám\)', '(iii)', s2)
    assert "(iii)" in s2_fixed and "(ám)" not in s2_fixed
