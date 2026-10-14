from copy import deepcopy

import cv2
import numpy as np

from app.services.ocr_scan_evidence import remove_scan_specks, remove_scan_edge_rules, refine_color_overlap, is_scan_rule_fragment
from app.services.ocr_text_refinement import _keep_edge_punctuation
from app.services.ocr_native import _is_duplicate_fragment
from app.services.ocr_text_refinement import attach_word_limits
from app.services.ocr_structured_text import refine_printed_identifiers, refine_handwritten_dates
from app.services.ocr_graphics import extract_marginal_ink, _initials_crop, erase_initials_ink
from app.services.ocr_text_refinement import refine_with_context
from app.services.ocr_typography import harmonize_typography


def test_monochrome_emblem_and_cover_frame_remain_graphics():
    from app.services.ocr_graphics import extract_monochrome_graphics
    image=np.full((1400,1000,3),255,np.uint8)
    cv2.rectangle(image,(35,35),(965,1365),(0,0,0),2)
    cv2.circle(image,(500,180),65,(40,40,40),-1)
    cv2.circle(image,(500,180),30,(255,255,255),-1)
    cv2.putText(image,'DOCUMENT',(350,380),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    elements=extract_monochrome_graphics(image,cv2.cvtColor(image,cv2.COLOR_RGB2GRAY))
    assert sorted(e['role'] for e in elements)==['illustration','page_frame']
    frame=next(e for e in elements if e['role']=='page_frame')
    import base64
    decoded=cv2.imdecode(np.frombuffer(base64.b64decode(frame['data']),np.uint8),cv2.IMREAD_UNCHANGED)
    assert frame['overlay'] and decoded.shape[2]==4
    assert decoded[100:-100,100:-100,3].sum()==0
    # Repeated interior rulings are a table, not a cover frame.
    cv2.line(image,(35,700),(965,700),(0,0,0),2)
    assert not any(e['role']=='page_frame' for e in extract_monochrome_graphics(image,cv2.cvtColor(image,cv2.COLOR_RGB2GRAY)))


def test_speck_filter_keeps_bullets_and_small_numeric_references():
    anchor=dict(text='Printed',confidence=96,bbox=[30,20,130,70])
    tiny=lambda text:dict(text=text,confidence=25,bbox=[10,30,14,34])
    lines=[dict(words=[deepcopy(anchor),tiny(s)]) for s in ['ˆ.','!','1','.','•','-']]
    remove_scan_specks(lines,np.full((120,160),255,np.uint8))
    assert [l['text'] for l in lines]==['Printed','Printed','Printed 1','Printed .','Printed •','Printed -']


def test_signature_fragments_stay_pixels_but_names_and_digits_stay_text():
    from app.services.ocr_graphics import separate_seal_fragments
    image=np.full((120,240),255,np.uint8)
    cv2.line(image,(45,40),(66,20),50,2)
    lines=[dict(text=t,confidence=30,bbox=box) for t,box in
           [('⁄..',[40,15,70,45]),('Tạ Anh Tuấn',[40,50,150,80]),
            ('1',[75,20,85,40]),('?', [180,15,200,40])]]
    kept,graphics=separate_seal_fragments(image,lines,[dict(role='seal',bbox=[10,10,160,100])])
    assert [l['text'] for l in kept]==['Tạ Anh Tuấn','1','?']
    assert len(graphics)==1 and graphics[0]['overlay']
    import base64
    decoded=cv2.imdecode(np.frombuffer(base64.b64decode(graphics[0]['data']),np.uint8),cv2.IMREAD_UNCHANGED)
    assert np.array_equal(decoded[:,:,3],255-image[15:45,40:70])


def test_noisy_prefix_loses_only_separate_tiny_specks():
    image=np.full((100,220),255,np.uint8)
    cv2.rectangle(image,(12,56),(14,58),0,-1)
    cv2.rectangle(image,(50,20),(68,68),0,2)
    cv2.line(image,(76,20),(71,68),0,2)
    line=dict(words=[dict(text='._.2/',confidence=28,bbox=[10,18,82,70]),
                     dict(text='Example',confidence=97,bbox=[95,20,210,70])])
    remove_scan_specks([line],image)
    assert line['text']=='2/ Example'
    assert line['words'][0]['bbox'][0]>=48
    # A real horizontal stroke is not dust and cannot be stripped this way.
    cv2.line(image,(12,56),(35,56),0,2)
    line['words'][0].update(text='._.2/',bbox=[10,18,82,70])
    remove_scan_specks([line],image)
    assert line['text']=='._.2/ Example'


def test_scan_rule_removal_preserves_table_intersections():
    image=np.full((900,600),255,np.uint8)
    cv2.line(image,(550,10),(550,890),0,2)
    cleaned=remove_scan_edge_rules(image)
    assert np.count_nonzero(cleaned[:,548:553]<100)<20
    for y in [100,300,500,700]:
        cv2.line(image,(20,y),(550,y),0,2)
    assert np.array_equal(remove_scan_edge_rules(image),image)


def test_scan_rule_does_not_erase_crossing_print_or_detached_accents():
    image=np.full((900,600),255,np.uint8)
    cv2.line(image,(550,10),(550,890),100,2)
    cv2.putText(image,'text',(491,450),cv2.FONT_HERSHEY_SIMPLEX,.9,30,2)
    cv2.line(image,(543,422),(552,417),30,2)
    cleaned=remove_scan_edge_rules(image)
    printed = image < 50
    assert np.array_equal(cleaned[printed],image[printed])
    assert np.count_nonzero(cleaned[30:350,548:553]<150)<20


def test_colour_retry_requires_independent_agreement_and_preserves_numbers():
    rgb=np.full((100,240,3),255,np.uint8);rgb[20:80,20:220]=(200,50,50)
    class Reader:
        def predict(self,crop):return 'Hóa,'
    for text,source,reading,expected in [('Hia,','Hia,','Hóa,','Hóa,'),
                                         ('Hia,','Hia,','Hoa,','Hia,'),
                                         ('A12','A12','Hóa,','A12')]:
        line=dict(words=[dict(text=text,source_text=source,confidence=30,bbox=[20,20,220,80])])
        refine_color_overlap([line],rgb,Reader(),lambda c:[dict(text=reading,confidence=96)],lambda:False)
        assert line['words'][0]['text']==expected


def test_short_letter_marker_can_be_recovered_but_confident_punctuation_stays():
    assert _keep_edge_punctuation('/','f)',54)=='f)'
    assert _keep_edge_punctuation('/','f)',96)=='/'
    assert _keep_edge_punctuation('/','free text',54)=='/'


def test_seal_fragment_does_not_clip_a_printed_name_or_remove_a_reference():
    name=dict(text='Trần Example',confidence=90,bbox=[200,150,500,200])
    fragment=dict(text='TA',confidence=10,bbox=[190,135,280,170])
    seal=[[100,20,600,190]]
    assert _is_duplicate_fragment(fragment,[name,fragment],seal)
    fragment['text']='1'
    assert not _is_duplicate_fragment(fragment,[name,fragment],seal)


def test_word_crop_keeps_accent_beside_an_unrelated_descender():
    image=np.full((160,300),255,np.uint8)
    def word(text,b):return dict(text=text,bbox=b,confidence=96)
    previous=dict(text='Previous descender',bbox=[10,20,250,66],words=[
        word('Previous',[10,20,100,46]),word('descender',[160,20,250,66])])
    current=dict(text='marked word',bbox=[10,65,250,95],words=[
        word('marked',[10,65,100,95]),word('word',[160,65,250,95])])
    for line in [previous,current]:
        for w in line['words']:
            x,y,z,t=w['bbox'];cv2.rectangle(image,(x,y),(z-1,t-1),0,-1)
    image[54:58,38:46]=0
    attach_word_limits([previous,current],160,image=image,preserve_word_ink=True)
    low,high=current['words'][0]['recognition_limits']
    assert low<=54 and high>=95
    assert low>=46


def test_identifier_correction_requires_independent_matching_digits():
    image=np.full((100,400),255,np.uint8);image[30:60,20:300]=0
    class Reader:
        def predict(self,c):return '123/2026/NĐ-CP'
    for reading,expected in [('123/2026/NĐ-CP','123/2026/NĐ-CP'),
                             ('128/2026/NĐ-CP','123/2026/VĐ-CP')]:
        line=dict(text='123/2026/VĐ-CP',words=[dict(text='123/2026/VĐ-CP',bbox=[20,30,300,60],confidence=96)])
        refine_printed_identifiers([line],image,Reader(),lambda c:[dict(text=reading,confidence=95)],lambda:False)
        assert line['text']==expected


def test_marginal_coloured_certification_stays_an_image_not_misspelled_text():
    rgb=np.full((1200,900,3),255,np.uint8)
    cv2.circle(rgb,(530,30),12,(220,30,40),2)
    cv2.putText(rgb,'SIGNED',(550,27),cv2.FONT_HERSHEY_SIMPLEX,.3,(0,0,0),1)
    cv2.putText(rgb,'2026',(550,41),cv2.FONT_HERSHEY_SIMPLEX,.3,(0,0,0),1)
    cv2.putText(rgb,'BODY HEADING',(200,150),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    result=extract_marginal_ink(rgb)
    assert len(result)==1 and result[0]['role']=='certification'
    assert result[0]['bbox'][3]<80


def test_context_decoder_cannot_override_independently_correct_tokens():
    image=np.full((100,400),255,np.uint8)
    for original,candidate,confidence in [('PCCC','PCC',85),('1:2020','11:2020',92),
                                          ('I,','1,',86),('nêu','nếu',97)]:
        class Reader:
            def predict(self,crop):return candidate
        line=dict(text=original,bbox=[20,20,250,70],words=[dict(
            text=original,bbox=[20,20,250,70],confidence=confidence)])
        refine_with_context(line,candidate,image,Reader(),lambda:False,
                            verify_word=lambda crop:dict(text=original,confidence=97))
        assert line['text']==original


def test_unreadable_letter_token_can_still_use_matching_visual_context():
    image=np.full((100,400),255,np.uint8)
    class Reader:
        def predict(self,crop):return 'PLAN'
    line=dict(text='PLLAN',bbox=[20,20,250,70],words=[dict(
        text='PLLAN',bbox=[20,20,250,70],confidence=0)])
    refine_with_context(line,'PLAN',image,Reader(),lambda:False,
                        verify_word=lambda c:dict(text='PLLAN',confidence=0))
    assert line['text']=='PLAN'


def test_appendix_font_does_not_change_cover_letter_family():
    serif=dict(text='A serif cover letter',font_name='Times New Roman',font_size_pt=13,
               font_fits={'Times New Roman':[.3,False,False,13],'Arial':[.35,False,False,12]})
    sans=dict(text='A long technical appendix using a sans serif font',font_name='Arial',font_size_pt=12)
    pages=[dict(elements=[dict(type='paragraph',source_lines=[serif])])]
    pages.extend(dict(elements=[dict(type='paragraph',source_lines=[deepcopy(sans)])]) for _ in range(5))
    harmonize_typography(pages)
    assert serif['font_name']=='Times New Roman' and serif['font_size_pt']==13


def test_blue_initials_on_either_margin_are_preserved_without_ocr_letters():
    rgb=np.full((1200,900,3),255,np.uint8)
    for x in [30,750]:
        cv2.line(rgb,(x,1120),(x+65,1080),(25,50,190),3)
        cv2.line(rgb,(x+35,1140),(x+45,1070),(25,50,190),3)
    result=extract_marginal_ink(rgb)
    assert len(result)==2 and all(x['role']=='initials' for x in result)


def test_initials_crop_excludes_cut_print_but_keeps_coloured_and_connected_ink():
    rgb=np.full((100,120,3),255,np.uint8)
    cv2.line(rgb,(0,2),(0,18),(0,0,0),3)  # Clipped neighboring glyph.
    cv2.line(rgb,(25,80),(105,30),(25,50,190),3)
    cv2.line(rgb,(105,30),(119,20),(0,0,0),3)  # Dark end of same stroke.
    cv2.circle(rgb,(50,10),2,(0,0,0),-1)  # Interior punctuation is retained.
    original=rgb.copy();clean=_initials_crop(rgb)
    assert np.all(clean[:22,:4]==255)
    assert np.array_equal(clean[:,20:],original[:,20:])
    assert np.array_equal(rgb,original)


def test_initials_erasure_keeps_neighboring_print_for_ocr():
    import base64
    rgb=np.full((100,120,3),255,np.uint8)
    cv2.line(rgb,(0,2),(0,18),(0,0,0),3)
    cv2.line(rgb,(25,80),(105,30),(25,50,190),3)
    graphic=dict(bbox=[0,0,120,100],data=base64.b64encode(cv2.imencode('.png',
        cv2.cvtColor(_initials_crop(rgb),cv2.COLOR_RGB2BGR))[1]).decode())
    body=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);before=body.copy()
    erase_initials_ink(body,graphic)
    assert np.array_equal(body[:22,:4],before[:22,:4])
    assert np.all(body[:,20:]==255)


def test_scan_rule_fragment_filter_preserves_print_and_numeric_references():
    image=np.full((1000,800),255,np.uint8)
    cv2.line(image,(3,100),(3,300),0,1)
    line=dict(text='lui .',confidence=20,bbox=[0,100,8,301])
    assert is_scan_rule_fragment(line,image)
    for text,confidence in [('1',20),('II',96)]:
        assert not is_scan_rule_fragment(dict(line,text=text,confidence=confidence),image)
    assert not is_scan_rule_fragment(dict(line,bbox=[200,100,208,301]),image)
    printed=dict(text='Print',confidence=40,bbox=[0,350,30,370])
    cv2.putText(image,'A',(0,368),cv2.FONT_HERSHEY_SIMPLEX,.6,0,1)
    assert not is_scan_rule_fragment(printed,image)
