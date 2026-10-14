from copy import deepcopy

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.services.ocr_typography import _fonts, split_underlined_labels, harmonize_typography
from app.services.ocr_text_refinement import attach_word_limits, word_crop, refine_with_context, line_recognition_limits
from app.services.ocr_structured_text import refine_document_codes
from app.services.ocr_native import _annotate_alignment
from app.services.ocr_graphics import seal_ink_mask


def font(bold=False):
    return next(f for name,b,i,f in _fonts() if name=='Times New Roman' and b==bold and not i).font_variant(size=48)


def test_pixel_gutter_retains_accents_despite_oversized_neighbor_box():
    image=Image.new('L',(700,220),255);draw=ImageDraw.Draw(image);f=font()
    words=[]
    for text,y in [('PREVIOUS',5),('TRUYỀN',70),('FOLLOWING',135)]:
        box=list(draw.textbbox((15,y),text,font=f));draw.text((15,y),text,font=f,fill=0)
        words.append(dict(text=text,bbox=box,confidence=93))
    true_top=words[1]['bbox'][1]
    words[1]['bbox'][1]+=14  # detector saw only the uppercase letter bodies
    words[0]['bbox'][3]=words[1]['bbox'][1]-1
    lines=[dict(text=w['text'],bbox=w['bbox'],words=[w]) for w in words]
    array=np.array(image);attach_word_limits(lines,array.shape[0],image=array)
    assert words[1]['recognition_limits'][0]<true_top
    crop=word_crop(array,words[1],lines[1])
    expected=np.count_nonzero(array[true_top:words[1]['bbox'][3],15:words[1]['bbox'][2]]<180)
    assert np.count_nonzero(crop<180)>=expected


def test_partial_underline_separates_label_and_value_without_changing_text():
    image=Image.new('L',(1100,110),255);draw=ImageDraw.Draw(image);words=[];x=10
    for index,text in enumerate(['Contact','label:','An','ordinary','value']):
        f=font(index<2);box=list(draw.textbbox((x,10),text,font=f));draw.text((x,10),text,font=f,fill=0)
        words.append(dict(text=text,bbox=box,confidence=96));x=box[2]+12
    draw.line((10,60,words[1]['bbox'][2],60),fill=0,width=3)
    line=dict(text=' '.join(w['text'] for w in words),bbox=[10,10,x,65],words=words)
    parts=split_underlined_labels([line],np.array(image))
    assert [l['text'] for l in parts]==['Contact label:','An ordinary value']
    assert [l['underline'] for l in parts]==[True,False]
    assert parts[1]['bbox'][0]==words[2]['bbox'][0]


def test_left_aligned_column_takes_precedence_over_accidental_centering():
    lines=[dict(text='Short value',bbox=[200,10,500,60]),dict(text='A longer value',bbox=[195,90,700,140]),
           dict(text='Third value',bbox=[202,170,760,220])]
    _annotate_alignment(lines,(195,760),column=True)
    assert {l['align'] for l in lines}=={'left'}
    centered=[dict(text='A heading',bbox=[250,10,650,60]),dict(text='Next',bbox=[350,90,550,140])]
    _annotate_alignment(centered,(250,650),column=True)
    assert {l['align'] for l in centered}=={'center'}


def test_handwritten_identifier_requires_independent_numeric_agreement():
    original=dict(text='Ref: X{ /AB-CD',bbox=[5,10,180,50],words=[
        dict(text=t,bbox=b,confidence=c) for t,b,c in
        [('Ref:',[5,10,50,50],95),('X{',[55,10,80,50],25),('/AB-CD',[85,10,180,50],95)]])
    class Reader:
        def predict(self,crop):return '27'
    for hand,expected in [(('27.',.95),'27'),(('21',.96),'X{'),(('27',.65),'X{')]:
        line=deepcopy(original)
        refine_document_codes([line],np.full((70,200),255,np.uint8),None,lambda c:('',0),lambda c:[],
                              Reader(),lambda c:hand,lambda:False)
        assert line['words'][1]['text']==expected
    line=deepcopy(original);line['words'][1].update(text='19',confidence=96);line['text']='Ref: 19 /AB-CD'
    refine_document_codes([line],np.full((70,200),255,np.uint8),None,lambda c:('27',.99),lambda c:[],
                          Reader(),lambda c:('27',.99),lambda:False)
    assert line['words'][1]['text']=='19'


def test_dark_colored_ring_does_not_turn_touching_printed_name_into_signature():
    image=Image.new('RGB',(900,1200),'white');draw=ImageDraw.Draw(image)
    draw.text((450,740),'Nguyễn Example',font=font(True),fill='black')
    rgb=np.array(image);cv2.circle(rgb,(485,700),75,(160,0,0),4)
    printed=(rgb[:,:,0]<50)&(rgb[:,:,1]<50)&(rgb[:,:,2]<50)
    mask=seal_ink_mask(rgb)
    assert np.count_nonzero(mask&printed)<np.count_nonzero(printed)*.05
    assert mask[(rgb[:,:,0]==160)&(rgb[:,:,1]==0)].all()


def test_decoder_cannot_add_unverified_edge_punctuation():
    line=dict(text='Printed label',bbox=[5,10,160,50],words=[
        dict(text='Printed',bbox=[5,10,85,50],confidence=94),
        dict(text='label',bbox=[90,10,160,50],confidence=20)])
    class Reader:
        def predict(self,crop):return 'Printed label?'
    for reading,expected in [('label','Printed label'),('label?','Printed label?')]:
        current=deepcopy(line)
        refine_with_context(current,'Printed label?',np.full((70,200),255,np.uint8),Reader(),lambda:False,
                            verify_word=lambda c:dict(text=reading,confidence=95))
        assert current['text']==expected


def test_ink_valley_cannot_clip_a_confident_accented_word(monkeypatch):
    import app.services.ocr_text_refinement as refinement
    monkeypatch.setattr(refinement,'_ink_gutter',lambda *args:90)
    lines=[dict(bbox=[0,10,100,60],words=[dict(text='Earlier',bbox=[0,10,100,60],confidence=96)]),
           dict(bbox=[0,80,200,140],underline=True,words=[dict(text='Word',bbox=[0,100,70,140],confidence=96),
               dict(text='phối',bbox=[80,80,150,140],confidence=96)])]
    assert line_recognition_limits(lines,200,np.full((200,250),255,np.uint8))[1][0]<=78
    lines[1]['underline']=False
    assert line_recognition_limits(lines,200,np.full((200,250),255,np.uint8))[1][0]==90
    assert line_recognition_limits(lines,200,np.full((200,250),255,np.uint8),preserve_word_ink=True)[1][0]<=78


def test_shared_label_glyph_sizes_restore_measurement_without_bolding_values():
    labels=[]
    for index,size in enumerate([14,14,12]):
        y=100+index*60
        labels.append(dict(text=f'Shared label {index}',bbox=[10,y,250,y+50],underline=True,
            font_name='Times New Roman',font_size_pt=size,bold=True,italic=False,
            words=[dict(text=t,bbox=[x,y,x+80,y+40]) for t,x in [('Shared',10),('label',100)]]))
    value=dict(text='An ordinary value',font_name='Times New Roman',font_size_pt=14,bold=False,italic=False)
    pages=[dict(elements=[dict(type='header',columns=[labels,[value]])])]
    harmonize_typography(pages)
    assert [l['font_size_pt'] for l in labels]==[14,14,14]
    assert not value['bold']


def test_tight_glyph_evidence_can_resolve_accent_with_neighboring_noise(monkeypatch):
    import app.services.ocr_text_refinement as refinement
    image=np.full((80,200),255,np.uint8)
    line=dict(text='học bồng bằng',bbox=[0,10,180,60],words=[
        dict(text=t,bbox=[i*60,10,i*60+50,60],confidence=96) for i,t in enumerate(['học','bồng','bằng'])])
    class Reader:
        def predict(self,crop):return 'học bổng bằng'
    # A fitted changed glyph is independent evidence; surrounding noise is
    # deliberately rejected. Neither an inferred vocabulary nor a bare
    # decoder disagreement can authorize this change.
    monkeypatch.setattr(refinement,'visual_accent_support',lambda crop,a,b:crop.shape==(50,50))
    refine_with_context(line,'học bổng bằng',image,Reader(),lambda:False,
                        verify_word=lambda crop:dict(text='bồng',confidence=96))
    assert line['text']=='học bổng bằng'


def test_address_retry_verifies_faint_italic_text_without_case_only_veto():
    from app.services.ocr_structured_text import refine_addresses
    line=dict(text='Alice(A)example.org',bbox=[10,10,190,50],words=[
        dict(text='Alice(A)example.org',bbox=[10,10,190,50],confidence=35)])
    calls=[]
    def second_reader(crop):
        calls.append(crop)
        return [dict(text='alice@example.org',confidence=20 if len(calls)==1 else 92)]
    refine_addresses([line],np.full((70,220),255,np.uint8),
                     lambda crop:('alice@example.org',.99),second_reader,None,lambda:False)
    assert len(calls)==2
    assert line['text']=='alice@example.org'
