from copy import deepcopy

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.ocr_scan_evidence import (
    is_duplicate_diacritic, remove_scan_specks, without_crop_edge_rule,
)
from app.services.ocr_text_refinement import refine_with_context
from app.services.ocr_typography import _fonts
from app.services.ocr_graphics import extract_marginal_ink


def test_vertical_rule_joined_to_last_word_is_not_cut_out_as_handwriting():
    from app.services.ocr_graphics import extract_inline_annotations
    image=np.full((250,600),255,np.uint8)
    words=[]
    for text,x in [('first',20),('second',140),('third',280),('tail',430)]:
        cv2.putText(image,text,(x,130),cv2.FONT_HERSHEY_SIMPLEX,1,0,2)
        words.append(dict(text=text,confidence=40 if text=='tail' else 96,bbox=[x,98,x+80,132]))
    cv2.line(image,(477,0),(477,249),80,2)
    line=dict(text='first second third tail',words=words,bbox=[20,98,510,132])
    rgb=cv2.cvtColor(image,cv2.COLOR_GRAY2RGB)
    elements,mask=extract_inline_annotations(rgb,image,[line])
    assert not elements and not mask.any()


def test_diacritic_boxes_belong_to_letters_but_numeric_references_stay():
    image=np.full((120,400),255,np.uint8)
    words=[]
    for i,text in enumerate(['one','two','three','four']):
        x=20+90*i
        cv2.rectangle(image,(x,48),(x+40,87),0,-1)
        words.append(dict(text=text,confidence=95,bbox=[x,40,x+42,88]))
    owner=dict(text='one two three four',words=words,confidence=95,bbox=[20,40,332,88])
    cv2.line(image,(32,33),(40,28),0,2)
    fragment=dict(text='M',words=[dict(text='M',confidence=76,bbox=[30,26,44,36])],
                  confidence=76,bbox=[30,26,44,36])
    assert is_duplicate_diacritic(fragment,[owner,fragment],image)
    reference=deepcopy(fragment);reference['text']='2';reference['words'][0]['text']='2'
    assert not is_duplicate_diacritic(reference,[owner,reference],image)
    # A raised character beside a letter, rather than over its body, is not noise.
    separate=deepcopy(fragment);separate['bbox']=[68,26,82,36];separate['words'][0]['bbox']=separate['bbox']
    assert not is_duplicate_diacritic(separate,[owner,separate],image)
    body=deepcopy(fragment);body['bbox']=[30,50,44,75];body['words'][0]['bbox']=body['bbox']
    assert not is_duplicate_diacritic(body,[owner,body],image)


@pytest.mark.parametrize('text,expected',[('_..5.1.','5.1.'),('_..12.3.4.','12.3.4.'),("'Số:",'Số:')])
def test_disconnected_prefix_specks_preserve_section_digits_and_label_colon(text,expected):
    image=np.full((110,300),255,np.uint8)
    image[25:28,10:13]=0;image[55:58,12:15]=0
    cv2.rectangle(image,(50,20),(95,69),0,2)
    line=dict(words=[dict(text=text,confidence=40,bbox=[10,20,100,70]),
                     dict(text='Example',confidence=97,bbox=[125,20,290,70])])
    remove_scan_specks([line],image)
    assert line['words'][0]['text']==expected
    # Real punctuation strokes cannot be removed as tiny disconnected dust.
    cv2.line(image,(13,28),(18,46),0,2)
    line['words'][0].update(text=text,bbox=[10,20,100,70])
    remove_scan_specks([line],image)
    assert line['words'][0]['text']==text


def test_broken_edge_rule_is_excluded_without_erasing_letter_or_period():
    image=np.full((65,140),255,np.uint8)
    cv2.putText(image,'test',(3,43),cv2.FONT_HERSHEY_SIMPLEX,1,0,2)
    image[40:46,112:118]=0
    image[:8,134:136]=100;image[19:,134:136]=100
    original=image.copy();clean=without_crop_edge_rule(image)
    assert np.array_equal(image,original)
    assert np.array_equal(clean[:,:130],original[:,:130])
    assert not np.any(clean[:,134:136]<180)
    # A connected crossing belongs to the text and stays protected.
    cv2.line(image,(120,32),(135,32),0,2)
    assert np.array_equal(without_crop_edge_rule(image),image)


def test_margin_initials_can_touch_a_corner_of_a_printed_line():
    rgb=np.full((1200,900,3),255,np.uint8)
    cv2.line(rgb,(50,1020),(120,990),(20,40,180),3)
    cv2.line(rgb,(70,1045),(125,1005),(20,40,180),3)
    word=dict(text='print',confidence=96,bbox=[128,970,250,990])
    lines=[dict(text='print',words=[word],bbox=word['bbox'],confidence=96)]
    assert any(g['role']=='initials' for g in extract_marginal_ink(rgb,lines))
    word['bbox']=[60,1000,115,1030]
    assert not any(g['role']=='initials' for g in extract_marginal_ink(rgb,lines))


@pytest.mark.parametrize('printed,detected,proposal,expected',[
    ('Tổ','TỔ','Tổ','Tổ'),('TỔ','TỔ','Tổ','TỔ'),('Tổ','Tổ','TỔ','Tổ'),
])
def test_case_change_requires_actual_glyph_shape(printed,detected,proposal,expected):
    font=next(f for n,b,i,f in _fonts() if n=='Arial' and not b and not i).font_variant(size=48)
    image=Image.new('L',(200,120),255);draw=ImageDraw.Draw(image)
    box=list(draw.textbbox((20,20),printed,font=font));draw.text((20,20),printed,font=font,fill=0)
    line=dict(text=detected,words=[dict(text=detected,confidence=90,bbox=box)])
    class Reader:
        def predict(self,crop):return proposal
    refine_with_context(line,proposal,np.array(image),Reader(),lambda:False,
                        lambda c:dict(text=proposal,confidence=75))
    assert line['text']==expected
