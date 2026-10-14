"""Estimate editable text geometry from recognized glyphs, not document templates."""
from functools import lru_cache
from pathlib import Path
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


@lru_cache(maxsize=1)
def _fonts():
    root = Path(__file__).resolve().parents[2]/'fonts'
    families = [('Times New Roman','times',('','bd','i','bi')),
                ('Arial','arial',('','bd','i','bi')),
                ('Calibri','calibri',('','b','i','z'))]
    result = []
    for family,stem,suffixes in families:
        for suffix,(bold,italic) in zip(suffixes,[(False,False),(True,False),(False,True),(True,True)]):
            path = root/(stem+suffix+'.ttf')
            if path.exists():
                result.append((family,bold,italic,ImageFont.truetype(str(path),100)))
    return result


@lru_cache(maxsize=4096)
def _metrics(font_index, text):
    metric = _glyph_metrics(font_index, text)
    return metric[:4] if metric else None


def _body_height(mask, minimum_ratio=.55):
    """Measure letter bodies without detached accents or punctuation tails.

    A missed comma/accent must not make a numeral/word acquire a larger font.
    Apply the same component measurement to the scan and the reference font.
    """
    stats = cv2.connectedComponentsWithStats(mask.astype(np.uint8))[2][1:]
    if not len(stats):
        return 0., 0, False
    tallest = float(stats[:, 3].max())
    bodies = stats[(stats[:, 3] >= tallest*minimum_ratio) & (stats[:, 4] >= tallest)]
    if not len(bodies):
        return tallest, 1, False
    heights = bodies[:, 3]
    uniform = len(heights)>=2 and np.percentile(heights,25)>=np.percentile(heights,75)*.85
    return float(np.median(heights)), len(bodies), uniform


def _height_ratio(height, bodies, reference_height, reference_bodies, uncertain=False):
    # Touching italic letters can combine several glyphs in one component.
    # In that case their component median is not comparable to the font's.
    h, count, uniform = bodies
    rh, reference_count, reference_uniform = reference_bodies
    full_ratio = height/reference_height
    if ((uncertain or (uniform and reference_uniform)) and count and reference_count
            and abs(count-reference_count) <= min(count, reference_count)*.2
            and abs((h/rh)/full_ratio-1)>.10):
        return h/rh
    return full_ratio


@lru_cache(maxsize=4096)
def _glyph_metrics(font_index, text):
    font = _fonts()[font_index][3]
    box = font.getbbox(text)
    image = Image.new('L',(max(1,box[2]-box[0]),max(1,box[3]-box[1])),255)
    ImageDraw.Draw(image).text((-box[0],-box[1]),text,font=font,fill=0)
    ink = np.asarray(image)<160
    ys,xs = np.where(ink)
    if not len(xs):
        return None
    w,h = xs.max()-xs.min()+1,ys.max()-ys.min()+1
    glyph = ink[ys.min():ys.max()+1,xs.min():xs.max()+1].astype(np.float32)
    pattern = cv2.resize(glyph,(160,40),interpolation=cv2.INTER_AREA)
    return float(w),float(h),float(ink.sum()/(w*h)),pattern,_body_height(glyph),_body_height(glyph,.45)


def _measurement_crop(image, word, bounds):
    """Exclude neighboring rules from font measurements, retaining accents.

    This is a measurement view only. Neither OCR text nor source pixels change.
    """
    from app.services.ocr_text_refinement import crop_with_accents
    crop,(_,top)=crop_with_accents(image,word['bbox'],word.get('recognition_limits',bounds),
                                  return_origin=True,padding_ratio=.35)
    if not crop.size:
        return crop
    mask=cv2.threshold(crop,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)[1]
    _,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    clean=crop.copy()
    for k,(x,y,w,h,area) in enumerate(stats[1:],1):
        outside=y+h+top<=word['bbox'][1] or y+top>=word['bbox'][3]
        if outside and w>=h*8:
            clean[labels==k]=255
    return clean


def split_underlined_labels(lines, image):
    """Keep a partially underlined label separate from its adjacent value.

    The printed rule supplies the boundary. No label vocabulary or document
    template is needed, and the resulting blocks keep their original positions.
    """
    from app.services.ocr_text_refinement import line_recognition_limits, crop_with_accents
    result = []
    for line,limits in zip(lines,line_recognition_limits(lines,image.shape[0],image)):
        words = line.get('words',[])
        if len(words)<4:
            result.append(line);continue
        crop,(ox,oy) = crop_with_accents(image,line['bbox'],limits,True)
        if not crop.size:
            result.append(line);continue
        height = float(np.median([w['bbox'][3]-w['bbox'][1] for w in words if any(c.isalpha() for c in w['text'])] or [crop.shape[0]]))
        rules = cv2.morphologyEx((crop<180).astype(np.uint8),cv2.MORPH_OPEN,
                                 np.ones((1,max(20,round(height*2.5))),np.uint8))
        _,_,stats,_ = cv2.connectedComponentsWithStats(rules)
        ranges = [(x+ox,x+w+ox) for x,y,w,h,_ in stats[1:]
                  if y>=crop.shape[0]*.55 and h<=max(3,height*.22)]
        underlined = [any(min(w['bbox'][2],b)-max(w['bbox'][0],a) >=
                         (w['bbox'][2]-w['bbox'][0])*.65 for a,b in ranges) for w in words]
        count = next((i for i,value in enumerate(underlined) if not value),len(words))
        if not (2<=count<len(words)-1 and not any(underlined[count:])):
            result.append(line);continue
        for group,underline in [(words[:count],True),(words[count:],False)]:
            boxes=[w['bbox'] for w in group]
            result.append(dict(line,words=group,text=' '.join(w['text'] for w in group),
                bbox=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)],
                confidence=sum(w['confidence'] for w in group)/len(group),
                word_confidences=[(w['text'],w['confidence']) for w in group],underline=underline))
    return result


def _gray_pattern(crop):
    ink=(255-crop).astype(np.float32)/255
    yy,xx=np.nonzero(ink>.29)
    if not len(xx):
        return None
    ink=ink[yy.min():yy.max()+1,xx.min():xx.max()+1]
    return ink.shape,cv2.resize(ink,(160,40),interpolation=cv2.INTER_AREA)


@lru_cache(maxsize=512)
def _raster_references(index,text,size):
    font=_fonts()[index][3].font_variant(size=size)
    box=font.getbbox(text)
    image=Image.new('L',(box[2]-box[0]+10,box[3]-box[1]+10),255)
    ImageDraw.Draw(image).text((5-box[0],5-box[1]),text,font=font,fill=0)
    raw=np.asarray(image)
    return [_gray_pattern(cv2.GaussianBlur(raw,(3,3),blur) if blur else raw)
            for blur in (0,.4,.65)]


def _raster_fit(index,text,crop):
    """Compare antialiased ink with fonts rasterized at the observed size.

    Enlarging a tiny screenshot cannot restore thin serifs. Thresholding that
    enlarged ink and comparing it with a 100 px glyph biases fits toward bold
    sans fonts. Retain the gray strokes and fit several native raster sizes.
    """
    measured=_gray_pattern(crop);metric=_glyph_metrics(index,text)
    if measured is None or metric is None:
        return None
    (h,w),pattern=measured
    center=round(h/metric[1]*100);best=None
    for size in range(max(6,center-3),center+4):
        for ref in _raster_references(index,text,size):
            if ref is None:continue
            (rh,rw),reference=ref
            similarity=float(np.sum(pattern*reference)/max(.01,np.linalg.norm(pattern)*np.linalg.norm(reference)))
            cost=.3*abs(math.log((w/h)/(rw/rh)))+.8*(1-similarity)
            candidate=(cost,size*h/rh)
            if best is None or candidate<best:best=candidate
    return best


def annotate_lines(lines, image, dpi=300, low_resolution=False):
    """Fit font metrics to several confident word images in each line.

    Font family is an approximation among installed fonts. Measurements retain
    relative heading sizes, emphasis and source line height across documents.
    """
    fonts = _fonts()
    if not fonts:
        return
    from app.services.ocr_text_refinement import attach_word_limits, line_recognition_limits, word_crop
    from app.services.ocr_image_evidence import without_underline
    limits = line_recognition_limits(lines, image.shape[0], image)
    attach_word_limits(lines,image.shape[0],limit_overlaps=True,image=image)
    fitted = []
    for line, bounds in zip(lines, limits):
        samples = []
        words = line.get('words', [])
        if words and ' '.join(w['text'] for w in words) != line.get('text'):
            # A corroborated re-reading can repair punctuation or segmentation.
            # Its text must be paired with the same ink, not stale token text.
            words = [dict(text=line['text'],bbox=line['bbox'],confidence=line.get('confidence',0))]
        words = sorted(words,key=lambda w:len(w['text']),reverse=True)
        handwriting = [w['bbox'] for w in words if w.get('handwritten')]
        for word in words:
            # Verified handwritten numerals do not have typeset font metrics.
            # Measure the printed code around them, excluding touching labels.
            if (word.get('handwritten') or any(word['bbox'][0]<b[2] and word['bbox'][2]>b[0] for b in handwriting)
                    or (word['confidence']<80 and not word.get('visual_verified'))
                    or len(word['text'])<3 or not any(c.isalnum() for c in word['text'])):
                continue
            crop = word_crop(image,word,line) if low_resolution else _measurement_crop(image, word, bounds)
            if not crop.size:
                continue
            crop, _ = without_underline(crop)
            mask = cv2.threshold(crop,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)[1]
            ys,xs = np.where(mask)
            if len(xs):
                w,h = xs.max()-xs.min()+1,ys.max()-ys.min()+1
                glyph = (mask[ys.min():ys.max()+1,xs.min():xs.max()+1]>0).astype(np.float32)
                samples.append((word['text'],w,h,len(xs)/(w*h),cv2.resize(glyph,(160,40),interpolation=cv2.INTER_AREA),_body_height(glyph),crop))
            if len(samples)>=3:
                break
        if not samples:
            continue
        fits = []
        for i,(family,bold,italic,font) in enumerate(fonts):
            costs,sizes = [],[]
            for text,w,h,density,pattern,body_height,crop in samples:
                if low_resolution:
                    fit=_raster_fit(i,text,crop)
                    if fit:
                        costs.append(fit[0]);sizes.append(fit[1]*72/dpi)
                    continue
                metric = _glyph_metrics(i,text)
                if metric is None:
                    continue
                fw,fh,fd,reference,reference_height,_ = metric
                similarity = float(np.sum(pattern*reference)/max(1.,np.linalg.norm(pattern)*np.linalg.norm(reference)))
                costs.append(abs(math.log((w/h)/(fw/fh)))+.15*abs(math.log(density/fd))+.8*(1-similarity))
                # OCR can join separated tokens or omit a character while its
                # box still spans all the ink. Width then inflates the inferred
                # point size. Glyph height is independent of that word spacing.
                scale = _height_ratio(h,body_height,fh,reference_height)
                # A wrong/missed stacked accent can increase the detected
                # height while the letter widths are unchanged. For a single
                # alphabetic token use the smaller supported dimension. Never
                # use width alone for joined words or numeric punctuation.
                if text.isalpha() and .72*scale <= w/fw < scale:
                    scale = w/fw
                sizes.append(scale*100*72/dpi)
            if costs:
                fits.append((float(np.median(costs)),i,float(np.median(sizes))))
        if not fits:
            continue
        # A blurred/upsampled word may fit regular and bold almost equally.
        # Require an actual improvement over the same family's regular face
        # before adding emphasis; tiny score noise must not bold random lines.
        regular={(fonts[k][0],fonts[k][2]):cost for cost,k,_ in fits if not fonts[k][1]}
        margins={}
        for cost,k,_ in fits:
            name,is_bold,is_italic,_=fonts[k]
            if is_bold and (name,is_italic) in regular:
                margins.setdefault(name,{})['italic' if is_italic else 'roman']=regular[(name,is_italic)]-cost
        line['font_bold_margins']=margins
        fits=[fit for fit in fits if not fonts[fit[1]][1] or
              regular.get((fonts[fit[1]][0],fonts[fit[1]][2]),float('inf'))>fit[0]+.025]
        if low_resolution:
            upright={(fonts[k][0],fonts[k][1]):cost for cost,k,_ in fits if not fonts[k][2]}
            fits=[fit for fit in fits if not fonts[fit[1]][2] or
                  upright.get((fonts[fit[1]][0],fonts[fit[1]][1]),float('inf'))>fit[0]+.025]
        _,i,size = min(fits)
        if not 3 <= size <= 72:
            continue
        family,bold,italic,_ = fonts[i]
        # Retain the best variant of every family. Isolated glyph images can
        # favour a wrong family; document harmonization chooses among these.
        per_family = {}
        for cost,k,variant_size in fits:
            name,b,it,_ = fonts[k]
            if 3 <= variant_size <= 72 and (name not in per_family or cost < per_family[name][0]):
                per_family[name] = [round(cost,4),b,it,round(variant_size*2)/2]
        line.update(font_name=family,font_size_pt=round(size*2)/2,bold=bold,italic=italic,
                    font_fits=per_family)
        line['font_fit_error'] = min(fits)[0]
        line['font_ink_height'] = float(np.median([s[2] for s in samples]))
        fitted.append((line,fits))
    # A slightly damaged line should not switch family inside an otherwise
    # uniform text region. Strong local evidence can still retain mixed fonts.
    if len(fitted)>=4:
        from collections import Counter
        family,count = Counter(line['font_name'] for line,_ in fitted).most_common(1)[0]
        if count/len(fitted)>=.65:
            for line,fits in fitted:
                preferred = [fit for fit in fits if fonts[fit[1]][0]==family]
                if line['font_name']!=family and preferred and min(preferred)[0]<min(fits)[0]+.12:
                    _,i,size = min(preferred)
                    name,bold,italic,_ = fonts[i]
                    line.update(font_name=name,font_size_pt=round(size*2)/2,bold=bold,italic=italic)
    # A badly clipped/misread token can have no plausible font fit. Compare
    # only nearby lines in the same column with similar physical ink height;
    # a separate heading or footnote must retain its own size and emphasis.
    for line,_ in fitted:
        if line.get('font_fit_error',0)<=.4:
            continue
        height=line['font_ink_height'];x,y,_,_=line['bbox']
        neighbors=[other for other,_ in fitted if other is not line and
                   other.get('font_fit_error',1)<.38 and
                   abs(other['bbox'][0]-x)<height*.8 and abs(other['bbox'][1]-y)<height*6 and
                   abs(other['font_size_pt']/line['font_size_pt']-1)<.22]
        if len(neighbors)>=3:
            from collections import Counter
            style,count=Counter((other['font_name'],other['bold'],other['italic']) for other in neighbors).most_common(1)[0]
            if count/len(neighbors)>=.75:
                size=float(np.median([other['font_size_pt'] for other in neighbors
                                      if (other['font_name'],other['bold'],other['italic'])==style]))
                line.update(font_name=style[0],bold=style[1],italic=style[2],font_size_pt=size)
    # Short labels and single digits still have measurable ink. Use a fitted
    # regional family when available, then scale its glyph height to the crop.
    # Leaving these lines unmeasured makes tiny table cells inherit 11 pt text.
    from collections import Counter
    family = Counter(line['font_name'] for line,_ in fitted).most_common(1)
    font_index = next((i for i,(name,bold,italic,_) in enumerate(fonts)
                       if name == (family[0][0] if family else 'Times New Roman')
                       and not bold and not italic),0)
    for line, bounds in zip(lines, limits):
        if 'font_size_pt' in line:
            continue
        sizes=[]
        for word in line.get('words',[]):
            if not any(c.isalnum() for c in word['text']):
                continue
            crop=_measurement_crop(image,word,bounds)
            crop, _ = without_underline(crop)
            metric=_glyph_metrics(font_index,word['text'])
            if crop.size and metric:
                mask=cv2.threshold(crop,0,255,cv2.THRESH_BINARY_INV|cv2.THRESH_OTSU)[1]
                ys=np.nonzero(mask)[0]
                if ys.size:
                    sizes.append(_height_ratio(ys.max()-ys.min()+1,_body_height(mask,.45),metric[1],metric[5],
                                               uncertain=word.get('confidence',0)<80)*100*72/dpi)
        if sizes and 3<=np.median(sizes)<=72:
            line.update(font_name=fonts[font_index][0],font_size_pt=round(float(np.median(sizes))*2)/2,
                        bold=False,italic=False)
        elif fitted:
            # A dash/percent fragment has no stable letter-height measurement.
            # Inherit its region's measured size rather than the DOCX default.
            nearest=sorted(fitted,key=lambda item:abs(item[0]['bbox'][1]-line['bbox'][1]))[:5]
            size=float(np.median([other['font_size_pt'] for other,_ in nearest]))
            line.update(font_name=fonts[font_index][0],font_size_pt=size,bold=False,italic=False)


def text_width_pt(text, family, size, bold=False, italic=False):
    for name,b,i,font in _fonts():
        if (name,b,i)==(family,bold,italic):
            return font.getlength(text)*size/100
    return None


def line_height_pt(family, size, bold=False, italic=False):
    """Use the selected font's ascent/descent, including room for diacritics."""
    for name,b,i,font in _fonts():
        if (name,b,i)==(family,bold,italic):
            ascent,descent = font.getmetrics()
            return (ascent+descent)*size/100
    return size*1.2


def _weight(line):
    return max(1,len(line.get('text','').strip()))


def _snap_sizes(lines, ratio, floor):
    """Snap measured sizes to the heaviest nearby size cluster.

    Measurement noise of a scan is about half a point for body text and grows
    for tiny table glyphs. Distinct typographic levels (e.g. 13 vs 14 pt
    titles, or 10 pt footnotes) stay separate clusters.
    """
    from collections import Counter
    weights = Counter()
    for line in lines:
        if line.get('font_size_pt'):
            weights[line['font_size_pt']] += _weight(line)
    centers = []
    tolerance = lambda center: max(floor,center*ratio)
    for size,_ in sorted(weights.items(),key=lambda item:(-item[1],item[0])):
        if not any(abs(size-c) <= tolerance(c) for c in centers):
            centers.append(size)
    for line in lines:
        size = line.get('font_size_pt')
        near = [c for c in centers if size and abs(size-c) <= tolerance(c)]
        if near:
            line['font_size_pt'] = near[0]
    return centers


def harmonize_typography(pages):
    """Make recognized typography consistent across a scanned document.

    Glyph-shape family fits are unreliable line by line, so a dominant family
    is used per page; each line keeps its own best weight and style within that
    family. A serif cover letter must not inherit the font of a long sans-serif
    attachment. Sizes are snapped to page-level clusters,
    each table to its own dominant size, and a paragraph to one size.
    """
    if len(pages)>1:
        for page in pages:
            harmonize_typography([page])
        return
    from collections import Counter
    body, paragraphs, tables = [], [], []
    for page in pages:
        for element in page.get('elements',[]):
            kind = element.get('type')
            if kind == 'paragraph':
                lines = element.get('source_lines') or [element]
                body.extend(lines)
                paragraphs.append(lines)
            elif kind == 'header':
                for column in element.get('columns',[]):
                    body.extend(column)
            elif kind == 'table':
                cell_lines, bare = [], []
                for cell in element.get('cells',[]):
                    measured = [l for l in cell.get('source_lines',[]) if l.get('font_size_pt')]
                    cell_lines.extend(measured)
                    if cell.get('text','').strip():
                        bare.extend([l for l in cell.get('source_lines',[]) if not l.get('font_size_pt')]
                                    or ([] if measured else [cell]))
                tables.append((cell_lines,bare))
    every = body+[line for lines,_ in tables for line in lines]
    families = Counter()
    for line in every:
        if line.get('font_name'):
            families[line['font_name']] += _weight(line)
    if not families:
        return
    family = families.most_common(1)[0][0]
    for line in every:
        fit = (line.get('font_fits') or {}).get(family)
        if fit and line.get('font_name') != family:
            current = (line.get('font_fits') or {}).get(line.get('font_name'))
            if current and current[0]<.4 and fit[0] > current[0]+.12:
                # Strong evidence of a different family (e.g. a sans-serif
                # heading in a serif document) must survive harmonization.
                continue
            _,bold,italic,size = fit
            line.update(bold=bold,italic=italic,font_size_pt=size)
        if line.get('font_name'):
            line['font_name'] = family
    # Adjacent underlined labels often lose a descender to their rule during
    # measurement. Shared printed words supply a size reference without
    # assuming that every label or every column has the same point size.
    for page in pages:
        for element in page.get('elements',[]):
            if element.get('type')!='header':
                continue
            for column in element.get('columns',[]):
                labels=[l for l in column if l.get('underline') and l.get('font_size_pt')]
                for line in labels:
                    words={w['text']:w['bbox'] for w in line.get('words',[]) if w['text'].isalpha()}
                    sizes=[]
                    h=line['bbox'][3]-line['bbox'][1]
                    for other in labels:
                        if abs(other['bbox'][1]-line['bbox'][1])>h*5:
                            continue
                        shared=[(words[w['text']],w['bbox']) for w in other.get('words',[]) if w['text'] in words]
                        if len(shared)<2:
                            continue
                        ratios=[(a[2]-a[0])/max(1,b[2]-b[0]) for a,b in shared]
                        if all(.92<=ratio<=1.08 for ratio in ratios):
                            sizes.append(other['font_size_pt'])
                    if len(sizes)>=3:
                        line['_label_size']=float(np.median(sizes))
                for line in labels:
                    if '_label_size' in line:
                        line['font_size_pt']=line.pop('_label_size')
    # A single ambiguous scan line must not switch to a different family in
    # the middle of a paragraph/table. Choose at the region level; separate
    # headings and footnotes still retain their own family and size.
    for lines in paragraphs + [lines for lines,_ in tables]:
        votes = Counter()
        for line in lines:
            if line.get('font_name'):
                votes[line['font_name']] += _weight(line)
        if len(votes) < 2:
            continue
        regional_family = votes.most_common(1)[0][0]
        for line in lines:
            fit = (line.get('font_fits') or {}).get(regional_family)
            if fit and line.get('font_name') != regional_family:
                _,bold,italic,size = fit
                line.update(font_name=regional_family,bold=bold,italic=italic,font_size_pt=size)
    _snap_sizes(body,.04,.5)
    for lines in paragraphs:
        sizes = Counter()
        for line in lines:
            if line.get('font_size_pt'):
                sizes[line['font_size_pt']] += _weight(line)
        if len(sizes) > 1:
            common = sizes.most_common(1)[0][0]
            for line in lines:
                # A paragraph's body has a shared point size. Raised/lowered
                # annotations are represented explicitly by inline run styles,
                # not by enlarging/shrinking the complete surrounding line.
                if line.get('font_size_pt'):
                    line['font_size_pt'] = common
        # Scan noise can give one ordinary continuation a marginally better
        # bold fit. Resolve only such isolated, weak fits inside a predominantly
        # regular paragraph. Keep strong emphasis and leading headings intact.
        weight=sum(_weight(line) for line in lines)
        regular_weight=sum(_weight(line) for line in lines if not line.get('bold'))
        if len(lines)>=3 and regular_weight>=weight*.70:
            for index,line in enumerate(lines):
                if index==0 or not line.get('bold') or lines[index-1].get('bold'):
                    continue
                fit=(line.get('font_fits') or {}).get(line.get('font_name'))
                margins=(line.get('font_bold_margins') or {}).get(line.get('font_name'),{})
                margin=margins.get('italic' if line.get('italic') else 'roman')
                if fit and fit[0]>.12 and margin is not None and margin<.06:
                    line['bold']=False
    for lines,bare in tables:
        # Cluster measurement noise only. A genuinely small annotation or a
        # larger heading in the same table must keep its own typographic level.
        centers = _snap_sizes(lines,.13,.5)
        table_size = centers[0] if centers else 10.0
        for cell in bare:
            cell.update(font_name=family,font_size_pt=table_size,bold=False,italic=False)
