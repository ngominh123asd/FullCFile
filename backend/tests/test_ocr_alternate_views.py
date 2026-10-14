from copy import deepcopy
import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.services.ocr_image_evidence import without_underline
from app.services.ocr_region_refinement import refine_underlined_line
from app.services.ocr_region_refinement import refine_uncertain_line
from app.services.ocr_native import _merge_visual_words
from app.services.ocr_text_refinement import refine_spacing
from app.services.ocr_text_refinement import refine_weak_accents, refine_with_context
from app.services.ocr_text_refinement import attach_word_limits, word_crop, line_recognition_limits
from app.services.ocr_text_refinement import remove_blank_symbol_words
from app.services.ocr_service import VietOcrOnnxPredictor
from app.services.ocr_typography import _fonts
from app.services.ocr_typography import annotate_lines, line_height_pt


def test_underlined_merged_label_needs_both_readers_and_keeps_source_pixels():
    font = _fonts()[0][3].font_variant(size=36)
    image = Image.new('L', (350, 100), 255)
    draw = ImageDraw.Draw(image)
    box = list(draw.textbbox((20,20), 'Local label:', font=font))
    draw.text((20,20), 'Local label:', font=font, fill=0)
    draw.line((box[0],box[3]+2,box[2],box[3]+2),fill=0,width=2)
    image = np.array(image); original = image.copy()
    line = dict(text='Locallabel:', bbox=box, words=[dict(text='Locallabel:',bbox=box,confidence=30)])
    words = [dict(text=t,confidence=95,bbox=[i*70+4,5,i*70+65,35]) for i,t in enumerate(['Local','label:'])]
    class Reader:
        def __init__(self,text):self.text=text
        def predict(self,crop):return self.text
    wrong = deepcopy(line)
    assert not refine_underlined_line(wrong,image,Reader('Other label:'),lambda c:words,lambda:False)
    assert wrong==line
    assert refine_underlined_line(line,image,Reader('Local label:'),lambda c:words,lambda:False)
    assert line['text']=='Local label:' and line['underline']
    assert len(line['words'])==2
    assert np.array_equal(image,original)


def test_horizontal_letter_strokes_are_not_an_underline():
    image=np.full((60,300),255,np.uint8)
    for x in range(10,260,35):cv2.putText(image,'E',(x,45),cv2.FONT_HERSHEY_SIMPLEX,1,0,2)
    cleaned,found=without_underline(image)
    assert not found and np.array_equal(cleaned,image)


def test_failed_line_segmentation_requires_agreement_of_two_readers():
    line=dict(text='"hiên',confidence=22,bbox=[10,10,180,50],words=[])
    class Reader:
        def __init__(self,text):self.text=text
        def predict(self,image):return self.text
    words=[dict(text=t,confidence=94,bbox=[5+i*45,4,40+i*45,34])
           for i,t in enumerate(['-','Như','trên,'])]
    image=np.full((80,220),255,np.uint8)
    assert not refine_uncertain_line(line,image,Reader('Khác'),lambda c:words,lambda:False)
    assert refine_uncertain_line(line,image,Reader('- Như trên,'),lambda c:words,lambda:False)
    assert line['text']=='- Như trên,' and len(line['words'])==3


def test_scan_rule_attached_to_tail_uses_reliable_baseline_and_independent_text():
    words=[dict(text=t,confidence=96,bbox=[10+i*50,40,50+i*50,70])
           for i,t in enumerate('One two three four five six seven E'.split())]
    words[-1].update(confidence=0,bbox=[360,35,400,125])
    line=dict(text=' '.join(w['text'] for w in words),words=words,bbox=[10,35,400,125],
              confidence=84,recognition_limits=(40,70))
    image=np.full((180,430),255,np.uint8)
    image[35:39,370:380]=0  # Detached tone mark must survive the crop.
    below=dict(text='next line',confidence=96,bbox=[10,90,400,120])
    class Reader:
        def __init__(self,tail):self.tail=tail
        def predict(self,crop):return 'One two three four five six seven '+self.tail
    def read(crop):
        assert crop.shape[0]<60 and np.count_nonzero(crop==0)==40
        result=[dict(w,bbox=[w['bbox'][0]-6,5,w['bbox'][2]-6,35]) for w in words]
        result[1]['confidence']=71  # Identical existing text is not a new guess.
        result[-1].update(text='complete',confidence=96)
        return result
    before=deepcopy(line)
    assert not refine_uncertain_line(line,image,Reader('different'),read,lambda:False,[line,below])
    assert line==before
    assert refine_uncertain_line(line,image,Reader('complete'),read,lambda:False,[line,below])
    assert line['text'].endswith('seven complete')


def test_overlapping_fragment_recovery_keeps_small_numbers_and_needs_agreement():
    from app.services.ocr_region_refinement import refine_overlapping_words
    source=dict(text='the f “word',bbox=[10,10,180,45],words=[
        dict(text='the',confidence=95,bbox=[10,10,80,45]),
        dict(text='f',confidence=25,bbox=[65,8,85,47]),
        dict(text='“word',confidence=45,bbox=[85,10,180,45])])
    words=[dict(text=t,confidence=96,bbox=b) for t,b in
           [('the',[4,5,74,40]),('“word',[79,5,174,40])]]
    class Reader:
        def __init__(self,text):self.text=text
        def predict(self,crop):return self.text
    image=np.full((70,220),255,np.uint8)
    candidate=deepcopy(source)
    assert not refine_overlapping_words(candidate,image,Reader('another word'),lambda c:words,lambda:False)
    assert candidate==source
    assert refine_overlapping_words(candidate,image,Reader('the "word'),lambda c:words,lambda:False)
    assert candidate['text']=='the “word'
    candidate=deepcopy(source);candidate['words'][1]['text']='1'
    assert not refine_overlapping_words(candidate,image,Reader('the "word'),lambda c:words,lambda:False)
    assert candidate['words'][1]['text']=='1'


def test_span_crop_keeps_baseline_bounds_when_neighbor_boxes_overlap():
    from app.services.ocr_region_refinement import span_crop
    image=np.full((150,220),255,np.uint8)
    line=dict(text='word',bbox=[20,45,160,100],recognition_limits=(50,95),words=[
        dict(text='word',confidence=30,bbox=[20,45,160,100])])
    neighbors=[line,dict(bbox=[20,10,160,60]),dict(bbox=[20,90,160,140])]
    crop,box=span_crop(image,line,0,1,neighbors)
    assert box[1]==50 and box[3]==95
    assert crop.shape[0]==45


def test_confident_one_letter_error_needs_exact_independent_crop_reading():
    class Reader:
        def predict(self,crop):return 'form'
    for reading,confidence,expected in [('form',96,'form'),('farm',96,'farm'),('form',60,'farm')]:
        source=dict(text='farm',words=[dict(text='farm',confidence=96,bbox=[10,10,150,50])])
        refine_with_context(source,'form',np.full((70,200),255,np.uint8),Reader(),lambda:False,
                            verify_word=lambda c:dict(text=reading,confidence=confidence))
        assert source['text']==expected


def test_long_unbroken_word_is_not_cut_at_a_low_ink_column():
    image=np.zeros((50,1200),np.uint8)
    image[:40,380:390]=255  # Weak columns, but a ten-pixel stroke still crosses.
    assert VietOcrOnnxPredictor._find_word_boundary_cuts(image,400)==[0,1200]
    image[:,780:800]=255
    cuts=VietOcrOnnxPredictor._find_word_boundary_cuts(image,400)
    assert cuts==[0,789,1200]
    assert all(np.all(image[:,c]==255) for c in cuts[1:-1])


def test_spacing_recovery_preserves_punctuation_and_does_not_import_letters():
    line=dict(text='ALPHABETA,GAMMA..',confidence=35,words=[
        dict(text='ALPHABETA,GAMMA..',confidence=35,bbox=[0,0,300,40])])
    proposed=_merge_visual_words(line,'ALPHA BETA, GAMMA',spacing_only=True)
    assert proposed=='ALPHA BETA, GAMMA..'
    words=[dict(text=t,confidence=95,bbox=[i*80,0,i*80+70,35]) for i,t in enumerate(['ALPHA','BETA,','GAMMA'])]
    refine_spacing(line,proposed,np.full((60,350),255,np.uint8),lambda crop:words,lambda:False)
    assert line['text']=='ALPHA BETA, GAMMA..'
    assert len(line['words'])==3


def test_weak_accent_retry_cannot_change_letters_or_trust_one_view():
    for readings,expected in [(['côté','côté'],'côté'),(['côté','côtè'],'côtè'),(['code'],'côtè')]:
        line=dict(text='côtè',words=[dict(text='côtè',confidence=30,bbox=[5,5,150,40])])
        it=iter(readings)
        class Reader:
            def predict(self,crop):return next(it)
        refine_weak_accents(line,np.full((60,170),255,np.uint8),Reader(),lambda:False)
        assert line['text']==expected


def test_quote_misreading_cannot_introduce_an_unverified_letter():
    line=dict(text='“café”',words=[dict(text='“café”',confidence=25,bbox=[5,5,150,40])])
    class Reader:
        def predict(self,crop):return 'écafé'
    refine_with_context(line,'écafé',np.full((60,170),255,np.uint8),Reader(),lambda:False,
                        verify_word=lambda crop:dict(text='“café”',confidence=95))
    assert line['text']=='“café”'


def test_adjacent_smaller_heading_cannot_cut_large_word_accents():
    image=np.full((170,500),255,np.uint8)
    image[45:65,330:450]=0  # A smaller preceding heading on the right.
    image[85:120,20:200]=0
    image[72:77,60:65]=0  # Detached accent missed by the word detector.
    upper=dict(text='Title',bbox=[330,45,450,65],words=[dict(text='Title',bbox=[330,45,450,65])])
    word=dict(text='été',bbox=[20,85,200,120])
    lower=dict(text='été example',bbox=[20,85,470,120],words=[word,dict(text='example',bbox=[330,85,470,120])])
    lines=[upper,lower]
    attach_word_limits(lines,image.shape[0])
    lower['recognition_limits']=line_recognition_limits(lines,image.shape[0])[1]
    crop=word_crop(image,word,lower)
    assert np.count_nonzero(crop==0)==35*180+5*5


def test_isolated_accent_recheck_retains_observed_quotes():
    line=dict(text='“côtè”',words=[dict(text='“côtè”',confidence=30,bbox=[5,5,150,40])])
    class Reader:
        def predict(self,crop):return 'côté?'
    refine_weak_accents(line,np.full((60,170),255,np.uint8),Reader(),lambda:False)
    assert line['text']=='“côté”'


def test_confident_accent_correction_requires_an_independent_reader():
    for other,expected in [('côtè','côtè'),('côté','côté')]:
        line=dict(text='côtè',words=[dict(text='côtè',confidence=91,bbox=[5,5,150,40])])
        class Reader:
            def predict(self,crop):return 'côté'
        refine_weak_accents(line,np.full((60,170),255,np.uint8),Reader(),lambda:False,
                            verify_word=lambda c:dict(text=other,confidence=95))
        assert line['text']==expected


def test_underlined_missing_number_needs_both_views_and_rebuilds_overlapping_boxes():
    font = _fonts()[1][3].font_variant(size=36)
    image = Image.new('L', (350, 100), 255); draw = ImageDraw.Draw(image)
    box = list(draw.textbbox((20,20), 'Stage 7:', font=font))
    draw.text((20,20), 'Stage 7:', font=font, fill=0)
    draw.line((box[0],box[3]+2,box[2],box[3]+2),fill=0,width=2)
    image=np.array(image)
    words=[dict(text=t,confidence=96,bbox=[i*90+4,5,i*90+80,35]) for i,t in enumerate(['Stage','7:'])]
    for readings,accepted in [(['Stage 7:','Stage 7:'],True),(['Stage 1:','Stage 7:'],False)]:
        line=dict(text='Stage:',bbox=box,words=[dict(text='Stage:',bbox=box,confidence=30)])
        it=iter(readings)
        class Reader:
            def predict(self,crop):return next(it)
        assert bool(refine_underlined_line(line,image,Reader(),lambda c:words,lambda:False))==accepted
        assert line['text']==('Stage 7:' if accepted else 'Stage:')


def test_adjacent_underline_cannot_inflate_font_measurement():
    image=Image.new('L',(700,200),255);draw=ImageDraw.Draw(image)
    font=_fonts()[1][3].font_variant(size=50);lines=[]
    for y in [15,85]:
        words=[]
        for x,text in [(20,'Local'),(180,'label')]:
            b=list(draw.textbbox((x,y),text,font=font));draw.text((x,y),text,font=font,fill=0)
            words.append(dict(text=text,bbox=b,confidence=96))
        box=[20,min(w['bbox'][1] for w in words),words[-1]['bbox'][2],max(w['bbox'][3] for w in words)]
        draw.line((box[0],box[3]+3,box[2],box[3]+3),fill=0,width=2)
        lines.append(dict(text='Local label',bbox=box,words=words))
    annotate_lines(lines,np.array(image))
    assert all(11<=l['font_size_pt']<=13 for l in lines)
    assert abs(lines[0]['font_size_pt']-lines[1]['font_size_pt'])<=.5


def test_single_and_multiple_lines_use_explicit_source_aware_leading(tmp_path):
    from app.services.ocr_native_export import build_docx
    from docx import Document
    from docx.enum.text import WD_LINE_SPACING
    line=lambda text,y:dict(text=text,bbox=[20,y,300,y+35],font_name='Times New Roman',font_size_pt=12)
    a,b,c=line('A short entry',20),line('A longer entry',100),line('continued here',200)
    path=tmp_path/'spacing.docx'
    build_docx(dict(pages=[dict(page_w=2480,page_h=3508,elements=[dict(type='paragraph',text=a['text'],source_lines=[a],bbox=a['bbox']),
                   dict(type='paragraph',text=b['text']+' '+c['text'],source_lines=[b,c],bbox=[20,100,300,235])])]),path)
    paragraphs=[p for p in Document(path).paragraphs if p.text.strip()]
    assert all(p.paragraph_format.line_spacing_rule==WD_LINE_SPACING.EXACTLY for p in paragraphs)
    assert abs(paragraphs[0].paragraph_format.line_spacing.pt-line_height_pt('Times New Roman',12))<.1
    assert 23.9<paragraphs[1].paragraph_format.line_spacing.pt<24.2


def test_blank_symbol_filter_retains_faint_ink_and_small_numbers():
    im=np.full((50,200),255,np.uint8);im[10:30,60:70]=220
    line=dict(text='© © 7',words=[dict(text=t,confidence=30,bbox=[x,5,x+30,40]) for t,x in [('©',5),('©',50),('7',100)]])
    remove_blank_symbol_words(line,im)
    assert line['text']=='© 7'
    assert len(line['ocr_corrections'])==1
