import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.services.ocr_native import _cell_text_bands
from app.services.ocr_typography import _fonts, annotate_lines


def test_cell_rows_keep_accents_and_short_final_line():
    font=_fonts()[0][3].font_variant(size=28)
    image=Image.new('L',(800,120),255);draw=ImageDraw.Draw(image)
    texts=['Một dòng dài có dấu hỏi, dấu nặng và dấu sắc.',
           'Thông tin trong cùng một ô của bảng.', 'Lịch thi']
    boxes=[]
    for y,text in zip([8,43,78],texts):
        boxes.append(draw.textbbox((8,y),text,font=font))
        draw.text((8,y),text,font=font,fill=0)
    bands=_cell_text_bands(np.asarray(image))
    assert len(bands)==3
    for (a,b),box in zip(bands,boxes):
        assert a<=box[1] and b>=box[3]


def test_small_raster_fonts_keep_family_and_emphasis():
    for family,bold,italic in [('Times New Roman',False,False),
                               ('Times New Roman',True,False),('Arial',False,False)]:
        font=next(f for n,b,i,f in _fonts() if (n,b,i)==(family,bold,italic)).font_variant(size=18)
        im=Image.new('L',(260,40),255);draw=ImageDraw.Draw(im)
        text='Thông tin';box=list(draw.textbbox((8,4),text,font=font));draw.text((8,4),text,font=font,fill=0)
        image=cv2.resize(np.asarray(im),None,fx=2,fy=2,interpolation=cv2.INTER_LANCZOS4)
        box=[x*2 for x in box]
        line=dict(text=text,bbox=box,words=[dict(text=text,bbox=box,confidence=97)])
        annotate_lines([line],image,low_resolution=True)
        assert (line['font_name'],line['bold'],line['italic'])==(family,bold,italic)
        assert abs(line['font_size_pt']-18*2*72/300)<1.5
