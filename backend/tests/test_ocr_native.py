import cv2
import numpy as np
import pytest

from app.services.ocr_native import (
    _cell_crop, _normalize_photo, _optical_mark, _prepare_cell,
    _rectify_photo, detect_tables,
)


def draw_grid(image, xs, ys):
    for x in xs:
        cv2.line(image, (x, ys[0]), (x, ys[-1]), 0, 2)
    for y in ys:
        cv2.line(image, (xs[0], y), (xs[-1], y), 0, 2)


def test_independent_tables_at_same_height_are_not_joined():
    image = np.full((800, 1200), 255, np.uint8)
    draw_grid(image, [60, 180, 300, 420], [150, 210, 270, 330, 390])
    draw_grid(image, [700, 820, 940, 1060], [150, 210, 270, 330, 390])
    tables, _ = detect_tables(image)
    assert len(tables) == 2
    assert [(len(t['grid']), len(t['grid'][0])) for t in tables] == [(4, 3), (4, 3)]


def test_missing_internal_border_preserves_merged_cell():
    image = np.full((800, 1000), 255, np.uint8)
    draw_grid(image, [100, 350, 600, 850], [120, 200, 280, 360])
    image[123:198, 348:353] = 255
    tables, _ = detect_tables(image)
    assert len(tables) == 1
    cell = next(c for c in tables[0]['cells'] if c['row'] == c['col'] == 0)
    assert cell['colspan'] == 2
    assert cell['rowspan'] == 1


def test_slanted_grid_edges_do_not_merge_body_columns():
    image = np.full((1600, 1000), 255, np.uint8)
    xs, ys = [80, 160, 360, 500, 700, 900], list(range(80, 1521, 80))
    draw_grid(image, xs, ys)
    image[83:158, 358:363] = 255
    # A small residual shear is common in scanned tables even after deskewing.
    warped = cv2.warpAffine(image, np.float32([[1, .025, -20], [0, 1, 0]]),
                           (1000, 1600), borderValue=255)
    tables, _ = detect_tables(warped)
    assert len(tables) == 1
    assert len(tables[0]['xs']) == len(xs)
    assert len(tables[0]['ys']) == len(ys)
    assert all(c['rowspan'] == c['colspan'] == 1 for c in tables[0]['cells'] if c['row'] > 0)
    assert next(c for c in tables[0]['cells'] if c['row'] == 0 and c['col'] == 1)['colspan'] == 2


def test_light_grid_ink_is_not_lost_against_dark_text():
    image = np.full((800, 1000), 255, np.uint8)
    xs, ys = [100, 350, 600, 850], [120, 230, 340, 450]
    draw_grid(image, xs, ys)
    cv2.line(image, (352, 340), (598, 340), 165, 3)
    for y in [200, 310, 420]:
        cv2.putText(image, '12345', (365, y), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 0, 3)
    tables, _ = detect_tables(image)
    assert len(tables) == 1
    assert len(tables[0]['cells']) == 9
    assert all(c['rowspan'] == c['colspan'] == 1 for c in tables[0]['cells'])


def test_short_subcolumn_and_small_text_strokes_are_distinct_from_rules():
    image=np.full((400,650),255,np.uint8)
    draw_grid(image,[10,110,310,450,630],list(range(10,371,45)))
    # An inner division exists in only two of the eight rows.
    cv2.line(image,(200,235),(200,325),0,2)
    image[278:283,112:199]=255
    # Letter-like stems are long enough for the morphology's initial kernel,
    # but lack the rule intersections needed to enter the removal mask.
    for x in [135,153,172]:
        cv2.line(image,(x,66),(x,99),0,2)
    tables,rules=detect_tables(image)
    assert len(tables)==1
    table=tables[0]
    assert len(table['xs'])==6
    merged=next(c for c in table['cells'] if c['row']==5 and c['col']==1)
    assert merged['rowspan']==2 and merged['colspan']==1
    assert not rules[67:98,133:175].any()
    assert rules[245:315,200].any()


def test_photographed_grid_is_rectified_without_inventing_cells():
    image = np.full((1100, 1400), 215, np.uint8)
    draw_grid(image, [200, 400, 600, 800, 1000, 1200], list(range(200, 901, 70)))
    source = np.float32([[200, 200], [1200, 200], [1200, 900], [200, 900]])
    target = np.float32([[230, 180], [1170, 220], [1230, 900], [180, 880]])
    tilted = cv2.warpPerspective(image, cv2.getPerspectiveTransform(source, target),
                                 (1400, 1100), borderValue=215)
    corrected = _rectify_photo(_normalize_photo(tilted))
    tables, _ = detect_tables(corrected, threshold=210)
    assert len(tables) == 1
    assert len(tables[0]['grid']) == 10
    assert len(tables[0]['grid'][0]) == 5


def test_empty_cell_stays_empty():
    gray = np.full((90, 240), 250, np.uint8)
    cv2.rectangle(gray, (10, 10), (230, 80), 0, 2)
    assert _prepare_cell(_cell_crop(gray, {'bbox': [10, 10, 230, 80]})) is None


def test_numeric_reader_cannot_strip_accents_from_time_unit(monkeypatch):
    from app.services.ocr_native import _enhance_photo_cells
    from app.services import ocr_service
    class Reader:
        def text_rec(self,images):
            return [('07 gio 30',.99)]*len(images),0
    monkeypatch.setattr(ocr_service,'_get_rapid_engine',lambda:Reader())
    table={'grid':[[''] for _ in range(4)]}
    cells=[dict(row=r,col=0,colspan=1,text='07 giờ 30',confidence=95) for r in range(1,4)]
    crop=np.full((40,150),255,np.uint8)
    _enhance_photo_cells([(table,c,crop,crop,crop) for c in cells],'vi',lambda:False,scan=True)
    assert all(c['text']=='07 giờ 30' for c in cells)


@pytest.mark.parametrize('independent,expected', [('< 1,6','< 1,6'), ('< 1,8','< L,ô'), ('kg','< L,ô')])
def test_misread_numeric_letters_need_independent_pixel_reading(monkeypatch, independent, expected):
    from app.services import ocr_native, ocr_service
    class Reader:
        def text_rec(self, images):
            return [('< 1,6',.98)]*len(images),0
    monkeypatch.setattr(ocr_service,'_get_rapid_engine',lambda:Reader())
    monkeypatch.setattr(ocr_native,'_tesseract_words',lambda *a,**kw:
                        [dict(text=t,confidence=90) for t in independent.split()])
    table={'grid':[[''] for _ in range(5)]}
    cells=[dict(row=r,col=0,colspan=1,text=t,confidence=30)
           for r,t in enumerate(['< L,ô','1,2','1,4','1,8'],1)]
    crop=np.full((40,150),255,np.uint8)
    ocr_native._enhance_photo_cells([(table,c,crop,crop,crop) for c in cells],'vi',lambda:False,scan=True)
    assert cells[0]['text']==expected


def test_known_grid_cleanup_does_not_erase_tall_letters_in_short_row():
    image=np.full((32,180),255,np.uint8)
    cv2.putText(image,'DIA',(3,25),cv2.FONT_HERSHEY_SIMPLEX,.8,0,2)
    prepared=_prepare_cell(image,borders_removed=True)
    assert prepared is not None
    clean=prepared[1]
    assert np.count_nonzero(clean<180)>=np.count_nonzero(image<180)*.95


def test_newly_recognized_cell_text_survives_empty_page_segmentation(monkeypatch):
    from app.services import ocr_native, ocr_typography
    image=np.full((120,220),255,np.uint8)
    cv2.putText(image,'8',(80,70),cv2.FONT_HERSHEY_SIMPLEX,1,0,2)
    cell=dict(row=0,col=0,rowspan=1,colspan=1,bbox=[20,20,200,100],text='')
    table=dict(cells=[cell],grid=[['']])
    monkeypatch.setattr(ocr_native,'_tesseract_words',lambda *a,**kw:[])
    monkeypatch.setattr(ocr_native,'_refine_scan_lines',lambda *a,**kw:None)
    monkeypatch.setattr(ocr_typography,'annotate_lines',lambda *a,**kw:None)
    def recognize(crops,*args,**kwargs):
        crops[0][1].update(text='8',confidence=95)
    monkeypatch.setattr(ocr_native,'_enhance_photo_cells',recognize)
    ocr_native._recognize_cells(image,[table],np.zeros_like(image),'vi',lambda:False)
    assert cell['text']==table['grid'][0][0]=='8'
    assert cell['source_lines'][0]['text']=='8'


def test_photo_normalization_retains_faint_gray_strokes():
    image=np.full((200,350),225,np.uint8)
    cv2.putText(image,'Faint',(35,110),cv2.FONT_HERSHEY_SIMPLEX,1.5,190,2)
    output=_normalize_photo(image)
    assert np.all(output[image==190]<240)
    assert np.all(output[image==190]>160)


def test_broken_slanted_border_does_not_become_text():
    gray = np.full((64,240),255,np.uint8)
    for y in (1,18,37,53):
        cv2.line(gray,(220+y//10,y),(222+y//10,min(62,y+10)),70,3)
    assert _prepare_cell(gray, photo=True) is None
    cv2.putText(gray,'1',(90,46),cv2.FONT_HERSHEY_SIMPLEX,1.1,0,2)
    assert _prepare_cell(gray, photo=True) is not None


def test_stamp_removal_preserves_black_text_and_colored_heading():
    from app.services.ocr_native import _scan_text_image
    rgb = np.full((800,600,3),255,np.uint8)
    cv2.circle(rgb,(555,580),35,(200,0,0),3)
    cv2.putText(rgb,'ABC',(90,90),cv2.FONT_HERSHEY_SIMPLEX,1,(220,0,0),2)
    cv2.putText(rgb,'123',(420,584),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    out = _scan_text_image(rgb)
    assert out[580,590] == 255
    assert np.count_nonzero(out[60:100,80:170] < 180) > 50
    assert np.count_nonzero(out[550:590,420:490] < 180) > 50


def test_visual_retry_preserves_punctuation_numbers_and_confident_words():
    from app.services.ocr_native import _merge_visual_words
    line={'text':'“Sinlt viên 5 tốt” — 2026', 'confidence':90,
          'word_confidences':[('“Sinlt',50),('viên',98),('5',98),('tốt”',98),('—',90),('2026',98)]}
    assert _merge_visual_words(line,'?Sinh viện 6 tốt? ? 2027') == '“Sinh viên 5 tốt” — 2026'


def test_higher_scan_resolution_does_not_multiply_decoder_chunks():
    from PIL import Image
    from app.services.ocr_service import VietOcrOnnxPredictor
    predictor = VietOcrOnnxPredictor.__new__(VietOcrOnnxPredictor)
    shapes=[]
    predictor._predict_single_chunk=lambda crop, **kwargs: shapes.append(crop.size) or 'text'
    line=np.full((32,2200),255,np.uint8)
    for x in range(12,2180,70):
        cv2.rectangle(line,(x,8),(x+48,26),0,-1)
    predictor.predict(Image.fromarray(line))
    low=len(shapes)
    shapes.clear()
    predictor.predict(Image.fromarray(cv2.resize(line,None,fx=3,fy=3)))
    assert len(shapes)==low
    assert all(w*32/h <= 1200 for w,h in shapes)


def test_confident_lines_are_verified_without_unconfirmed_changes(monkeypatch):
    from app.services.ocr_native import _refine_scan_lines
    from app.services import ocr_service
    calls=[]
    class Predictor:
        def predict(self, image, **kwargs):
            calls.append(image.size)
            return '- Văn bản rõ'
    monkeypatch.setattr(ocr_service, '_get_vietocr_onnx_predictor', lambda **kwargs: Predictor())
    line={'text':'- Văn bản rõ', 'bbox':[0,0,150,30], 'confidence':85,
          'word_confidences':[('-',10),('Văn',98),('bản',97),('rõ',99)]}
    _refine_scan_lines([line],np.full((40,160),255,np.uint8),'vi',lambda:False)
    assert line['text']=='- Văn bản rõ'
    assert len(calls)==1


def test_duplicate_accents_require_overlap_with_a_better_complete_line():
    from app.services.ocr_native import _is_duplicate_fragment
    main = {'text': 'A complete text line', 'bbox': [516, 1280, 820, 1318], 'confidence': 80}
    fragment = {'text': '^ „.s', 'bbox': [591, 1264, 701, 1296], 'confidence': 15}
    separate = dict(fragment, bbox=[591, 1220, 701, 1252])
    outside = dict(fragment, bbox=[840, 1264, 950, 1296])
    confident = dict(fragment, confidence=95)
    lines = [main, fragment, separate, outside, confident]
    assert _is_duplicate_fragment(fragment, lines)
    assert not any(_is_duplicate_fragment(line, lines) for line in [main, separate, outside, confident])


@pytest.mark.parametrize('caption', ['Text spanning columns', '12:30 - 14:45', 'Bảng tổng hợp'])
def test_scan_merged_caption_is_not_sent_to_numeric_recognizer(monkeypatch, caption):
    from app.services.ocr_native import _enhance_photo_cells
    from app.services import ocr_service
    calls = []
    class Engine:
        def text_rec(self, images):
            calls.append(len(images))
            return [(s, .99) for s in ['-12', '+3.5', '0017']], None
    monkeypatch.setattr(ocr_service, '_get_rapid_engine', lambda: Engine())
    table = {'grid': [['', '', '', ''] for _ in range(5)]}
    cells = [dict(row=0, col=0, colspan=1, text='Column'),
             dict(row=1, col=0, colspan=4, text=caption)]
    cells.extend(dict(row=r, col=0, colspan=1, text=s) for r,s in enumerate(['-12', '+3.5', '0017'], 2))
    crop = np.full((50, 200), 255, np.uint8)
    _enhance_photo_cells([(table, c, crop, crop, crop) for c in cells], 'vi', lambda: False, scan=True)
    assert calls == [3]
    assert cells[1]['text'] == caption
    assert [c['text'] for c in cells[2:]] == ['-12', '+3.5', '0017']


@pytest.mark.parametrize('scale', [1, 3])
@pytest.mark.parametrize('title', ['A new document', 'TIÊU ĐỀ KHÁC', 'عنوان المستند'])
def test_centered_layout_depends_on_geometry_not_document_wording(scale, title):
    from app.services.ocr_native import _annotate_alignment
    from app.services.ocr_service import _merge_lines_into_paragraphs
    lines = [
        {'text': title, 'bbox': [350, 50, 650, 90]},
        {'text': 'Subtitle', 'bbox': [250, 110, 750, 150]},
        {'text': 'Body prose starts here', 'bbox': [100, 190, 900, 230]},
        {'text': '- A list entry', 'bbox': [100, 300, 350, 340]},
    ]
    for line in lines:
        line['bbox'] = [x*scale for x in line['bbox']]
    _annotate_alignment(lines, (100*scale, 900*scale))
    assert [l['align'] for l in lines] == ['center', 'center', 'left', 'left']
    paragraphs = _merge_lines_into_paragraphs(lines, 1000*scale)
    assert paragraphs[0]['text'] == title
    assert paragraphs[1]['text'] == 'Subtitle'
    assert paragraphs[2]['text'] == 'Body prose starts here'


def test_visual_spacing_retry_does_not_change_letters_or_identifiers():
    from app.services.ocr_native import _merge_visual_words
    source = {'text': 'AlphaBeta code AB-001', 'confidence': 95}
    assert _merge_visual_words(source, 'Alpha Beta code AB-002') == 'Alpha Beta code AB-001'
    assert _merge_visual_words({'text': 'REPORT', 'confidence': 95}, 'SPORT') == 'REPORT'
    assert _merge_visual_words({'text': 'Value 1 2.50', 'confidence': 60}, 'Value 12.50') == 'Value 12.50'
    assert _merge_visual_words({'text': 'Value 1 2.50', 'confidence': 95}, 'Value 12.50') == 'Value 1 2.50'


@pytest.mark.parametrize('ending', ['cực.', 'nhân.', 'text.', 'fin.'])
def test_short_final_word_is_not_a_list_marker_or_new_paragraph(ending):
    from app.services.ocr_service import _merge_lines_into_paragraphs
    lines = [
        {'text': '- A sentence continues to the next line', 'bbox': [120, 100, 900, 145]},
        {'text': ending, 'bbox': [100, 170, 180, 205]},
        {'text': '2. New section', 'bbox': [120, 235, 460, 280]},
    ]
    result = _merge_lines_into_paragraphs(lines, 1000)
    assert result[0]['text'].endswith(' '+ending)
    assert result[1]['text'] == '2. New section'
    assert not result[0]['is_heading']


def test_cross_tick_and_blank_are_distinct():
    cross = np.full((50, 60), 255, np.uint8)
    cv2.line(cross, (15, 12), (44, 38), 0, 3)
    cv2.line(cross, (15, 38), (44, 12), 0, 3)
    # Disconnected neighboring-row ink must not alter the glyph's bounds.
    cv2.line(cross, (49, 2), (51, 3), 0, 1)
    tick = np.full((50, 60), 255, np.uint8)
    cv2.line(tick, (12, 26), (24, 38), 0, 3)
    cv2.line(tick, (24, 38), (46, 10), 0, 3)
    assert _optical_mark(cross) == 'x'
    assert _optical_mark(tick) == '✓'
    assert _optical_mark(np.full((50, 60), 255, np.uint8)) is None


def test_cell_cleanup_retains_one_pixel_decimal_point_and_accent():
    image=np.full((50,100),255,np.uint8)
    for x in (20,40,65):
        cv2.rectangle(image,(x,18),(x+7,34),0,-1)
    image[34,55]=0
    image[13,23]=0
    prepared=_prepare_cell(image,borders_removed=True,return_origin=True)
    assert prepared is not None
    binary,gray,_,(ox,oy)=prepared
    for x,y in [(55,34),(23,13)]:
        assert gray[y-(oy-2),x-(ox-2)]==0
        assert binary[y-(oy-2),x-(ox-2)]==0


@pytest.mark.parametrize('confirmation,expected', [('8.431','8.431'),('8.481','8.43]')])
def test_confident_numeric_replacement_requires_corresponding_pixels(monkeypatch,confirmation,expected):
    from app.services import ocr_native,ocr_service
    class Engine:
        def text_rec(self,images):
            return [('8.431',.99)]*len(images),None
    monkeypatch.setattr(ocr_service,'_get_rapid_engine',lambda:Engine())
    monkeypatch.setattr(ocr_native,'_tesseract_words',lambda *a,**kw:[dict(text=confirmation,confidence=95)])
    table={'grid':[[''] for _ in range(4)]}
    cells=[dict(row=i,col=0,colspan=1,text='8.43]',confidence=95) for i in range(1,4)]
    crop=np.full((40,160),255,np.uint8)
    ocr_native._enhance_photo_cells([(table,c,crop,crop,crop) for c in cells],'vi',lambda:False,scan=True)
    assert all(c['text']==expected for c in cells)


def test_weak_isolated_code_is_retried_without_changing_a_confident_unit(monkeypatch):
    from app.services import ocr_native,ocr_service
    class Engine:
        def text_rec(self,images):
            assert len(images)==1
            return [('2',.99)],None
    monkeypatch.setattr(ocr_service,'_get_rapid_engine',lambda:Engine())
    monkeypatch.setattr(ocr_native,'_tesseract_words',lambda *a,**kw:[dict(text='2',confidence=95)])
    table={'grid':[[''] for _ in range(3)]}
    cells=[dict(row=1,col=0,colspan=1,text='j',confidence=0),
           dict(row=2,col=0,colspan=1,text='m',confidence=96)]
    crop=np.full((40,160),255,np.uint8)
    ocr_native._enhance_photo_cells([(table,c,crop,crop,crop) for c in cells],'vi',lambda:False,scan=True)
    assert [c['text'] for c in cells]==['2','m']


def test_export_preserves_empty_cells_leading_zeroes_and_literal_text(tmp_path):
    from openpyxl import load_workbook
    from app.services.ocr_native_export import build_xlsx
    grid = [['Tên', 'SĐT', 'Ghi chú'], ['Học sinh', '0012345678', ''], ['=1+1', '', 'x']]
    table = {'type': 'table', 'grid': grid, 'cells': [
        {'row': r, 'col': c, 'rowspan': 1, 'colspan': 1, 'text': value}
        for r, row in enumerate(grid) for c, value in enumerate(row)
    ]}
    path = tmp_path/'result.xlsx'
    build_xlsx({'pages': [{'elements': [table]}]}, path)
    sheet = load_workbook(path).active
    assert sheet['B2'].value == '0012345678'
    assert sheet['A3'].value == '=1+1'
    assert sheet['A3'].data_type == 's'
    assert sheet['C2'].value is None
    assert sheet['C3'].value == 'x'
