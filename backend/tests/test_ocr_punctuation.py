import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.ocr_text_refinement import refine_punctuation, word_crop
from app.services.ocr_typography import _fonts


def font():
    return next(f for n,b,i,f in _fonts() if n=='Times New Roman' and not b and not i).font_variant(size=48)


@pytest.mark.parametrize('printed,detected',[
    ('Example:','Example'),('tải.','tải'),('nhận,','nhận'),
    ('(3b).','3b).'),('phải','phải.'),('vướng','vướng.'),
])
def test_punctuation_repairs_need_printed_pixels_and_two_readers(printed,detected):
    im=Image.new('L',(320,120),255);draw=ImageDraw.Draw(im)
    box=list(draw.textbbox((20,20),printed,font=font()))
    draw.text((20,20),printed,font=font(),fill=0)
    line=dict(text=detected,words=[dict(text=detected,bbox=box,confidence=96)])
    class Reader:
        def predict(self,crop):return printed
    refine_punctuation(line,printed,np.array(im),Reader(),lambda:False,
                       lambda c:dict(text=printed,confidence=96))
    assert line['text']==printed
    assert line['words'][0]['bbox']==box


@pytest.mark.parametrize('printed,wrong',[('Example','Example:'),('nhận,','nhận'),('tải.','tải'),('3b).','(3b).')])
def test_even_agreeing_readers_cannot_invent_or_erase_visible_punctuation(printed,wrong):
    im=Image.new('L',(320,120),255);draw=ImageDraw.Draw(im)
    box=list(draw.textbbox((20,20),printed,font=font()))
    draw.text((20,20),printed,font=font(),fill=0)
    line=dict(text=printed,words=[dict(text=printed,bbox=box,confidence=96)])
    class Reader:
        def predict(self,crop):return wrong
    refine_punctuation(line,wrong,np.array(im),Reader(),lambda:False,
                       lambda c:dict(text=wrong,confidence=96))
    assert line['text']==printed


@pytest.mark.parametrize('text,proposal',[
    ('12,50','12.50'),('A-17','A17'),('03/04/2026','03-04-2026'),
    ('example.com','examplecom'),('hợp','họp'),
])
def test_punctuation_pass_never_rewrites_internal_separators_or_letters(text,proposal):
    line=dict(text=text,words=[dict(text=text,bbox=[10,10,190,55],confidence=96)])
    class Reader:
        def predict(self,crop):raise AssertionError('Must not re-read protected data')
    refine_punctuation(line,proposal,np.full((100,220),255,np.uint8),Reader(),lambda:False,None)
    assert line['text']==text


def test_word_crop_excludes_next_line_and_next_word_without_losing_descender():
    im=Image.new('L',(700,200),255);draw=ImageDraw.Draw(im);words=[]
    for text,x in [('alpha',10),('beta',150),('gamma',270),('delta',435),('phải.',550)]:
        printed=text.rstrip('.')
        box=list(draw.textbbox((x,20),printed,font=font()))
        draw.text((x,20),printed,font=font(),fill=0)
        words.append(dict(text=text,bbox=box,confidence=96))
    target=words[-1]
    clean=np.array(im)
    draw.text((600,88),'x',font=font(),fill=0)
    target['bbox'][3]=130
    line=dict(words=words)
    a=word_crop(clean,target,line);b=word_crop(np.array(im),target,line)
    assert np.array_equal(a,b)
    # The descender in the unchanged neighboring word remains in its crop.
    assert np.count_nonzero(word_crop(clean,words[2],line)<180)>0


@pytest.mark.parametrize('printed', ['giao nhận','giao ! nhận'])
def test_standalone_noise_is_removed_only_when_its_shape_is_absent(printed):
    im=Image.new('L',(420,120),255);draw=ImageDraw.Draw(im)
    draw.text((20,20),printed,font=font(),fill=0)
    box=list(draw.textbbox((20,20),printed,font=font()))
    middle=(box[0]+box[2])//2
    line=dict(text='giao ! nhận',words=[
        dict(text='giao',confidence=96,bbox=[box[0],box[1],middle-10,box[3]]),
        dict(text='!',confidence=35,bbox=[middle-10,box[1],middle+10,box[3]]),
        dict(text='nhận',confidence=96,bbox=[middle+10,box[1],box[2],box[3]])])
    class Reader:
        def predict(self,crop):return 'giao nhận'
    refine_punctuation(line,'giao nhận',np.array(im),Reader(),lambda:False,
                       lambda c:dict(text='giao nhận',confidence=96))
    assert line['text']==printed


@pytest.mark.parametrize('printed,detected,isolated,expected',[
    ('cháy,','.cháy,','cháy','cháy,'),
    ('.cháy,','.cháy,','cháy','.cháy,'),
    ('(cháy,','(cháy,','cháy','(cháy,'),
    ('cháy,','.cháy,','.cháy','.cháy,'),
])
def test_prefix_repair_does_not_require_or_change_an_unchanged_suffix(printed,detected,isolated,expected):
    im=Image.new('L',(320,120),255);draw=ImageDraw.Draw(im)
    box=list(draw.textbbox((20,20),printed,font=font()))
    draw.text((20,20),printed,font=font(),fill=0)
    line=dict(text=detected,words=[dict(text=detected,bbox=box,confidence=40)])
    class Reader:
        def predict(self,crop):return isolated
    refine_punctuation(line,'cháy,',np.array(im),Reader(),lambda:False,
                       lambda c:dict(text='cháy,',confidence=96))
    assert line['text']==expected


def test_clipped_foreign_tone_below_baseline_leaves_real_descenders_and_punctuation():
    image=np.full((160,550),255,np.uint8)
    words=[]
    for i in range(5):
        x=20+i*100
        image[40:80,x:x+30]=0
        words.append(dict(text='word',confidence=96,bbox=[x,40,x+30,80]))
    # The last detection includes an unrelated following-line tone on its left.
    target=words[-1];target['bbox']=[405,40,470,105]
    image[88:96,407:411]=0
    # A descender, a comma, and a below-letter dot belong to the word.
    image[78:89,441:445]=0
    image[77:88,452:456]=0
    image[86:89,425:428]=0
    line=dict(words=words)
    expected=image.copy();expected[88:96,407:411]=255
    assert np.array_equal(word_crop(image,target,line),word_crop(expected,target,line))
    # The source image remains untouched and each real low mark survives.
    assert image[90,408]==0
    assert np.count_nonzero(word_crop(image,target,line)<180)>1200
