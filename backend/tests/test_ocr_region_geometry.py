import cv2
import numpy as np
from PIL import Image,ImageDraw
from app.services.ocr_native import _header_columns,_footer_columns
from app.services.ocr_typography import annotate_lines,_fonts
from app.services.ocr_region_refinement import span_crop,refine_weak_spans
from app.services.ocr_graphics import extract_rule_graphics,seal_regions


def test_banner_does_not_block_unequal_header_columns():
    lines=[dict(text='Independent banner',bbox=[230,10,600,30])]
    boxes=[[90,70,300,90],[420,70,820,90],[440,105,790,125],
           [60,145,380,170],[450,145,800,170],[60,175,380,198],
           [100,280,820,305]]
    lines += [dict(text='Text',bbox=b) for b in boxes]
    columns=_header_columns(lines,900,1200)
    assert columns and [len(c) for c in columns]==[3,3]
    assert all(line is not lines[0] for col in columns for line in col)
    assert columns[1][0]['bbox']==boxes[1]


def test_closing_columns_can_be_above_the_middle_and_stop_at_footnote():
    lines=[dict(text='Closing prose',bbox=[70,200,820,230])]
    for y in [270,310,350]:
        lines.extend([dict(text='Recipient',bbox=[70,y,420,y+20]),
                      dict(text='Signature',bbox=[550,y,800,y+20])])
    lines.append(dict(text='Footnote',bbox=[70,1100,820,1120]))
    columns=_footer_columns(lines,900,1200)
    assert columns and [len(c) for c in columns]==[3,3]


def test_numeric_and_uncertain_cells_use_measured_small_font():
    font=next(f for name,b,i,f in _fonts() if name=='Times New Roman' and not b and not i).font_variant(size=25)
    for text,confidence in [('123.456',96),('38,9%',15),('5',95)]:
        im=Image.new('L',(250,70),255);draw=ImageDraw.Draw(im)
        bbox=list(draw.textbbox((10,10),text,font=font));draw.text((10,10),text,font=font,fill=0)
        line=dict(text=text,bbox=bbox,words=[dict(text=text,bbox=bbox,confidence=confidence)])
        annotate_lines([line],np.array(im))
        assert 4.5<=line['font_size_pt']<=7.5


def test_word_recovery_uses_neighbor_overlap_not_a_remote_heading():
    image=np.full((200,400),255,np.uint8);image[75:111,105:145]=0
    line=dict(text='Ab 7?',bbox=[20,90,200,120],recognition_limits=(86,200),words=[
        dict(text='Ab',bbox=[20,90,90,120],confidence=96),
        dict(text='7?',bbox=[105,112,145,116],confidence=0)])
    heading=dict(bbox=[240,60,350,85])
    crop,box=span_crop(image,line,1,2,[heading,line])
    assert box[1]<=78 and np.count_nonzero(crop==0)>=33*40
    heading['bbox']=[100,60,170,85]
    _,box=span_crop(image,line,1,2,[heading,line])
    assert box[1]>=87


def test_weak_split_word_needs_full_crop_agreement():
    line=dict(text='X ample',bbox=[10,20,150,50],words=[
        dict(text='X',confidence=20,bbox=[10,20,35,50]),
        dict(text='ample',confidence=96,bbox=[40,20,150,50])])
    class Reader:
        def predict(self,crop): return 'Example'
    refine_weak_spans(line,'Example',np.full((80,180),255,np.uint8),Reader(),lambda:False)
    assert line['text']=='Example' and len(line['words'])==1
    line['words'][0]['confidence']=98
    refine_weak_spans(line,'Exemplar',np.full((80,180),255,np.uint8),Reader(),lambda:False)
    assert line['text']=='Example'


def test_misread_horizontal_rule_is_preserved_as_graphic():
    image=np.full((200,500,3),255,np.uint8)
    cv2.line(image,(70,65),(300,65),(0,0,0),2)
    line=dict(text='noise',confidence=0,bbox=[60,45,310,90])
    assert len(extract_rule_graphics(image,[line]))==1
    cv2.putText(image,'Text',(75,85),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    assert extract_rule_graphics(image,[line])==[]


def test_numeric_retry_requires_an_independent_visual_reading():
    line=dict(text='A 8?? Z',bbox=[5,10,250,50],words=[
        dict(text='A',bbox=[5,10,40,50],confidence=95),
        dict(text='8??',bbox=[65,45,150,49],confidence=0),
        dict(text='Z',bbox=[210,10,250,50],confidence=95)])
    readings=iter(['8B3','8B3','883'])
    class Reader:
        def predict(self,crop): return next(readings)
    refine_weak_spans(line,'A 8B3 Z',np.full((80,300),255,np.uint8),Reader(),lambda:False,
                      recognize_code=lambda crop:('883',.96))
    assert line['text']=='A 883 Z'


def test_seal_at_mid_page_keeps_attached_signature_but_not_neighbor_text():
    image=np.full((1200,900,3),255,np.uint8)
    cv2.circle(image,(650,420),75,(220,0,0),3)
    cv2.line(image,(620,380),(820,470),(0,0,0),3)
    cv2.putText(image,'Body',(50,380),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    boxes=seal_regions(image,[])
    assert len(boxes)==1 and boxes[0][0]>500 and boxes[0][2]>=820


def test_unsigned_stamp_does_not_absorb_or_erase_crossing_printed_text():
    import base64
    from app.services.ocr_graphics import extract_seal_graphics,seal_ink_mask
    from app.services.ocr_native import _scan_text_image
    image=np.full((1200,900,3),255,np.uint8)
    cv2.rectangle(image,(70,190),(220,300),(220,0,0),3)
    cv2.putText(image,'Editable text',(180,210),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0),2)
    cv2.putText(image,'Note',(100,275),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,200),2)
    lines=[dict(text='Editable text',bbox=[180,185,410,218])]
    graphic=extract_seal_graphics(image,lines)[0]
    assert graphic['overlay'] and graphic['bbox'][2]<240
    mask=seal_ink_mask(image)
    black=np.all(image==0,axis=2)
    assert not np.any(mask&black)
    assert np.all(_scan_text_image(image)[black]==0)
    decoded=cv2.imdecode(np.frombuffer(base64.b64decode(graphic['data']),np.uint8),cv2.IMREAD_UNCHANGED)
    x0,y0,x1,y1=graphic['bbox']
    assert decoded.shape[2]==4
    assert not np.any(decoded[:,:,3][black[y0:y1,x0:x1]])


def test_tinted_signature_crossing_red_seal_keeps_whole_pen_stroke():
    from app.services.ocr_graphics import seal_ink_mask
    image=np.full((1200,900,3),255,np.uint8)
    cv2.circle(image,(650,620),75,(220,0,0),3)
    cv2.line(image,(580,580),(810,675),(90,35,35),4)
    mask=seal_ink_mask(image)
    signature=(image[:,:,0]==90)&(image[:,:,1]==35)
    assert np.all(mask[signature])


def test_inline_pen_mark_is_preserved_without_erasing_printed_descenders():
    from app.services.ocr_graphics import extract_inline_annotations
    image=Image.new('RGB',(720,230),'white');draw=ImageDraw.Draw(image)
    font=_fonts()[0][3].font_variant(size=40)
    words=[]
    for x,text in [(10,'Some'),(110,'printed'),(250,'words'),(370,'glyphs')]:
        box=list(draw.textbbox((x,35),text,font=font))
        draw.text((x,35),text,font=font,fill='black')
        words.append(dict(text=text,bbox=box,confidence=96))
    line=dict(words=words+[dict(text='p',bbox=[505,42,560,105],confidence=15)],bbox=[10,42,560,105])
    rgb=np.array(image);before=rgb.copy()
    cv2.line(rgb,(538,44),(510,108),(0,0,0),4)
    cv2.line(rgb,(512,108),(562,86),(0,0,0),4)
    elements,mask=extract_inline_annotations(rgb,cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),[line])
    assert len(elements)==1 and elements[0]['overlay']
    assert np.any(mask[:,505:565])
    assert not np.any(mask[:,:500])
    # Misrecognized normal descenders cannot be discarded on confidence alone.
    words[-1]['confidence']=15
    plain=dict(words=words,bbox=[10,42,495,80])
    assert extract_inline_annotations(before,cv2.cvtColor(before,cv2.COLOR_RGB2GRAY),[plain])[0]==[]
