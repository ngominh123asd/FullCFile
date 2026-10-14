"""Export ordered OCR elements without dropping prose or flattening tables."""
from html import escape
import base64
import io
from pathlib import Path


def _elements(page):
    return page.get("elements", [dict(b, type="paragraph") for b in page.get("blocks", [])])


def build_html(data):
    body = []
    for page in data["pages"]:
        body.append('<section class="page">')
        for element in _elements(page):
            kind = element["type"]
            if kind == "table":
                body.append('<table>')
                cells = {(c["row"], c["col"]): c for c in element["cells"]}
                for r, row in enumerate(element["grid"]):
                    body.append('<tr>')
                    for c in range(len(row)):
                        cell = cells.get((r, c))
                        if cell:
                            text = escape(cell["text"]).replace('\n', '<br>')
                            body.append(f'<td rowspan="{cell["rowspan"]}" colspan="{cell["colspan"]}">{text}</td>')
                    body.append('</tr>')
                body.append('</table>')
            elif kind == "header":
                body.append('<div class="header">')
                for column in element["columns"]:
                    body.append('<div>' + '<br>'.join(escape(b["text"]) for b in column) + '</div>')
                body.append('</div>')
            elif kind == 'image':
                body.append(f'<div style="text-align:{element["align"]}"><img alt="" '
                            f'style="width:{element["width_fraction"]*100:.2f}%" '
                            f'src="data:image/png;base64,{element["data"]}"></div>')
            else:
                tag = 'h3' if element.get('is_heading') else 'p'
                align = element.get('align', 'left')
                align = align if align in ('left', 'center', 'right', 'justify') else 'left'
                body.append(f'<{tag} style="text-align:{align}">' + escape(element.get("text", "")).replace('\n', '<br>') + f'</{tag}>')
        body.append('</section>')
    return ('<!DOCTYPE html><html><head><meta charset="utf-8"><title>OCR Result</title>'
            '<style>body{font-family:serif;max-width:1000px;margin:auto;padding:24px}'
            'table{border-collapse:collapse;width:100%;margin:12px 0}td{border:1px solid;padding:5px;vertical-align:top}'
            '.header{display:flex;gap:24px}.header>div{flex:1}.page{break-after:page}</style>'
            '</head><body>' + ''.join(body) + '</body></html>')


def fit_measured_table_rows(table):
    """Keep measured cells from growing because of uncertain font/leading fits.

    Remove excess leading first. Only reduce oversized text when its natural
    line boxes exceed the source cell height; never clip or truncate content.
    Vertical merges use their complete span, not a single constituent row.
    """
    from docx.shared import Pt
    from docx.oxml.ns import qn
    rows=list(table.rows)
    if not rows or any(row.height is None for row in rows):
        return
    cols=len(table.columns);cells=table._cells;groups={}
    for index,cell in enumerate(cells):
        group=groups.setdefault(cell._tc, [cell,set()])
        group[1].add(index//cols)
    for cell,indices in groups.values():
        available=max(1,sum(rows[i].height.pt for i in indices)-.2)
        metrics=[]
        for paragraph in cell.paragraphs:
            fmt=paragraph.paragraph_format
            pitch=fmt.line_spacing
            if not hasattr(pitch,'pt'):
                continue
            metrics.append((paragraph,max(1,paragraph.text.count('\n')+1),pitch.pt))
        total=sum(lines*pitch for _,lines,pitch in metrics)
        factor=min(1,available/max(total,1))
        if factor<.6 and sum(lines for _,lines,_ in metrics)>1:
            # Large multiline discrepancies indicate additional content. Let
            # Word grow the row rather than making that content unreadable.
            # A single line, however, cannot have a natural line box taller
            # than the measured cell; isolated glyph fits can be outliers.
            continue
        if factor<1:
            for paragraph,_,pitch in metrics:
                paragraph.paragraph_format.line_spacing=Pt(pitch*factor)
                for run in paragraph.runs:
                    if run.font.size:
                        run.font.size=Pt(max(1,int(run.font.size.pt*factor*2)/2))
                for size in paragraph._p.xpath('./w:pPr/w:rPr/w:sz'):
                    size.set(qn('w:val'),str(max(2,int(int(size.get(qn('w:val')))*factor))))
            total*=factor
        leading=sum((p.paragraph_format.space_before.pt if p.paragraph_format.space_before else 0)+
                    (p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 0) for p,_,_ in metrics)
        if leading>max(0,available-total):
            ratio=max(0,available-total)/leading
            for p,_,_ in metrics:
                fmt=p.paragraph_format
                if fmt.space_before:fmt.space_before=Pt(fmt.space_before.pt*ratio)
                if fmt.space_after:fmt.space_after=Pt(fmt.space_after.pt*ratio)


def build_docx(data, output_path):
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_ROW_HEIGHT_RULE
    from statistics import median
    from app.services.ocr_typography import line_height_pt
    alignments = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
                  'right': WD_ALIGN_PARAGRAPH.RIGHT, 'justify': WD_ALIGN_PARAGRAPH.JUSTIFY}
    doc = Document()
    doc.core_properties.keywords = 'fileforge:source-pages'
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.top_margin = section.bottom_margin = Inches(.55)
    section.left_margin = section.right_margin = Inches(.7)
    normal = doc.styles['Normal']
    normal.font.name, normal.font.size = 'Times New Roman', Pt(11)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.

    def box_of(element):
        if element.get('bbox'):
            return element['bbox']
        boxes = [b['bbox'] for col in element.get('columns',[]) for b in col]
        return ([min(b[0] for b in boxes),min(b[1] for b in boxes),
                 max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None)

    def write_paragraph(paragraph, source, left, right, scale, cell=False):
        if not source.get('text','').strip():
            # Empty continuation cells must not impose an 11 pt minimum on a
            # thin source row or the continuation of a vertically merged cell.
            paragraph.clear()
            paragraph.paragraph_format.line_spacing = Pt(1)
            mark = OxmlElement('w:rPr')
            size = OxmlElement('w:sz');size.set(qn('w:val'),'2');mark.append(size)
            paragraph._p.get_or_add_pPr().append(mark)
            paragraph.add_run().font.size = Pt(1)
            return 1.
        lines = source.get('source_lines') or [source]
        if cell:
            text_lines = source.get('text','').split('\n')
            if not source.get('source_lines'):
                # A cell's own bbox is absolute page geometry, while cell
                # paragraphs are positioned relative to the cell (left=0).
                # Without cell-relative line boxes, write the text only.
                lines = [{'text':t} for t in text_lines]
            elif len(lines)==1:
                # Cell refinement may have replaced an entire single-line reading.
                lines = [dict(lines[0],text=source.get('text',''))]
            elif [l.get('text','') for l in lines] != text_lines:
                # Refinement changed a multi-line cell; keep geometry only when
                # the line count still matches the final reading.
                lines = ([dict(l,text=t) for l,t in zip(lines,text_lines)]
                         if len(lines)==len(text_lines) else [{'text':t} for t in text_lines])
        boxes = [line['bbox'] for line in lines if line.get('bbox')]
        fmt = paragraph.paragraph_format
        fmt.space_after = Pt(0)
        fmt.space_before = Pt(0)
        sizes = [line.get('font_size_pt',11) for line in lines]
        # The paragraph mark participates in Word/LibreOffice's line metrics.
        # Leaving it at the Normal style's 11 pt makes a 6 pt table cell grow
        # despite every visible run having the correct measured size.
        mark = OxmlElement('w:rPr')
        mark_size = OxmlElement('w:sz')
        mark_size.set(qn('w:val'),str(round(max(sizes)*2)))
        mark.append(mark_size)
        paragraph._p.get_or_add_pPr().append(mark)
        gaps = [b[1]-a[1] for a,b in zip(boxes,boxes[1:]) if b[1]>a[1]]
        natural_height = max(line_height_pt(l.get('font_name','Times New Roman'),l.get('font_size_pt',11),
                                           l.get('bold',False),l.get('italic',False)) for l in lines)
        pitch = max(natural_height,median(gaps)*scale) if gaps else natural_height
        fmt.line_spacing = Pt(pitch)
        align = source.get('align','left')
        if cell and boxes:
            # Centering is geometric, including merged captions and numbers.
            start,end = min(b[0] for b in boxes),max(b[2] for b in boxes)
            if (min(start-left,right-end) >= (right-left)*.04 and
                    all(abs((b[0]+b[2]-left-right)/2) <= max((right-left)*.035,median(sizes)/scale*.3) for b in boxes)):
                align = 'center'
            elif (start-left >= (right-left)*.15 and
                  all(0 <= right-b[2] <= max((right-left)*.07,median(sizes)/scale*.35) for b in boxes)):
                # A right-anchored label/amount uses the cell's full width.
                # Simulating it with a large left indent makes a slightly
                # different Word glyph advance wrap the final digit.
                align = 'right'
        paragraph.alignment = alignments.get(align,WD_ALIGN_PARAGRAPH.LEFT)
        if boxes and align=='left':
            start = min(b[0] for b in boxes)
            fmt.left_indent = Pt(max(0,(start-left)*scale))
            fmt.first_line_indent = Pt((boxes[0][0]-start)*scale)
        for i,line in enumerate(lines):
            if i:
                line_break = paragraph.add_run()
                line_break.font.size = Pt(line.get('font_size_pt',11))
                line_break.add_break()
            pieces = line.get('inline_runs') or [{'text':line.get('text','')}]
            if ''.join(p['text'] for p in pieces) != line.get('text',''):
                pieces = [{'text':line.get('text','')}]
            runs=[]
            for piece in pieces:
                run = paragraph.add_run(piece['text'])
                run.font.name = line.get('font_name','Times New Roman')
                run.font.size = Pt(line.get('font_size_pt',11))
                run.bold = line.get('bold',bool(source.get('is_heading')))
                run.italic = line.get('italic',False)
                run.underline = line.get('underline',False)
                if piece.get('vertical_align') == 'superscript':
                    run.font.superscript = True
                runs.append(run)
            if line.get('bbox') and line.get('font_size_pt'):
                from app.services.ocr_typography import text_width_pt
                measured = text_width_pt(line.get('text',''),run.font.name,run.font.size.pt,run.bold,run.italic)
                # The usable paragraph/cell width, not the ink box of a short
                # line, determines whether text needs tighter spacing. Scaling
                # every line to its OCR box made adjacent glyphs look thinner.
                target = (right-left)*scale
                if align=='left':
                    target -= max(0,line['bbox'][0]-left)*scale
                # Word/LibreOffice can differ slightly from FreeType's kerning
                # and glyph advances; reserve a small layout tolerance.
                target *= .97
                if measured and target<measured:
                    # Retain glyph proportions. Small negative tracking can
                    # accommodate font-metric differences without scaleX/w:w.
                    # Larger discrepancies may wrap rather than distort text.
                    tracking = max(-run.font.size.pt*.08,(target-measured)/max(1,len(line.get('text',''))-1))
                    for run in runs:
                        spacing = OxmlElement('w:spacing')
                        spacing.set(qn('w:val'),str(round(tracking*20)))
                        run._r.get_or_add_rPr().append(spacing)
        return pitch*len(lines)

    for page_idx, page in enumerate(data["pages"]):
        landscape = page.get('page_w',0) > page.get('page_h',1)
        if page_idx:
            section = doc.add_section(WD_SECTION.NEW_PAGE)
            # The section marker is structural, not an extra visible blank line.
            marker = doc.paragraphs[-1]
            marker.paragraph_format.space_before = marker.paragraph_format.space_after = Pt(0)
            marker.paragraph_format.line_spacing = Pt(1)
            marker.add_run().font.size = Pt(1)
        pw = page.get('page_width_pt',841.68 if landscape else 595.44)
        ph = page.get('page_height_pt',595.44 if landscape else 841.68)
        section.page_width, section.page_height = Pt(pw),Pt(ph)
        scale = pw/max(1,page.get('page_w',pw/0.24))
        elements = _elements(page)
        boxes = [box_of(e) for e in elements if e['type']!='image' and box_of(e)]
        left = min(b[0] for b in boxes) if boxes else .7*72/scale
        right = max(b[2] for b in boxes) if boxes else (pw-.7*72)/scale
        top = min(b[1] for b in boxes) if boxes else .55*72/scale
        section.left_margin = Pt(max(0,left*scale))
        section.right_margin = Pt(max(0,pw-right*scale))
        section.top_margin = Pt(max(0,top*scale))
        # A scanned page may contain text almost at its lower edge. Reserve
        # the font's line box below the measured ink, instead of imposing a
        # fixed bottom margin that pushes the final row onto another page.
        sizes = [line.get('font_size_pt',11) for element in elements
                 for line in element.get('source_lines',[]) if line.get('text')]
        line_box = median(sizes or [11])*1.25
        content_bottom = max((b[3] for b in boxes),default=(ph-28-line_box)/scale)*scale
        section.bottom_margin = Pt(min(28,max(0,ph-content_bottom-line_box)))
        available = section.page_width - section.left_margin - section.right_margin
        flow_bottom = top*scale
        for element in elements:
            kind = element["type"]
            bbox = box_of(element)
            # Track the rendered line boxes, not only the OCR ink boxes.
            # Otherwise font leading is added a second time at every paragraph
            # and gradually pushes the final lines onto an extra page.
            gap = max(0,bbox[1]*scale-flow_bottom) if bbox else 0
            if kind in ('table','header') and gap>2:
                spacer = doc.add_paragraph()
                spacer.paragraph_format.line_spacing = Pt(max(1,gap))
                spacer.paragraph_format.space_after = Pt(0)
                spacer.add_run().font.size = Pt(1)
                flow_bottom += gap
            if kind == 'table':
                rows, cols = len(element['grid']), len(element['grid'][0])
                table = doc.add_table(rows=rows, cols=cols)
                table.style = 'Table Grid'
                table.autofit = False
                rule_sizes = table.style.element.xpath('./w:tblPr/w:tblBorders/w:insideH/@w:sz')
                row_rule_width = int(rule_sizes[0])/8 if rule_sizes else 0
                xs = element['xs']
                indent = OxmlElement('w:tblInd')
                indent.set(qn('w:w'),str(round((xs[0]-left)*scale*20)))
                indent.set(qn('w:type'),'dxa')
                table._tbl.tblPr.append(indent)
                margins = OxmlElement('w:tblCellMar')
                for edge in ('top','left','bottom','right'):
                    item = OxmlElement('w:'+edge)
                    item.set(qn('w:w'),'0')
                    item.set(qn('w:type'),'dxa')
                    margins.append(item)
                table._tbl.tblPr.append(margins)
                for c, column in enumerate(table.columns):
                    column.width = Pt((xs[c+1]-xs[c])*scale)
                    for cell in column.cells:
                        cell.width = column.width
                # Source cells are disjoint, so their original grid anchors
                # stay valid while merges are applied. Rebuilding python-docx's
                # complete grid for every lookup is quadratic on large tables.
                grid_cells = table._cells
                for source in element['cells']:
                    r, c = source['row'], source['col']
                    cell = grid_cells[r*cols+c]
                    if source['rowspan'] > 1 or source['colspan'] > 1:
                        cell = cell.merge(grid_cells[(r+source['rowspan']-1)*cols+c+source['colspan']-1])
                    cell.text = ''
                    cell_width = xs[c+source['colspan']]-xs[c]
                    write_paragraph(cell.paragraphs[0],source,0,cell_width,scale,cell=True)
                    source_lines = source.get('source_lines',[])
                    if source_lines:
                        cell.paragraphs[0].paragraph_format.space_before = Pt(max(0,source_lines[0]['bbox'][1]*scale-2))
                for r,row in enumerate(table.rows):
                    if 'ys' in element:
                        # The style contributes a shared rule to each row's
                        # rendered extent. Source grid coordinates
                        # already include that rule; avoid accumulating it a
                        # second time over many rows.
                        row.height = Pt(max(1,(element['ys'][r+1]-element['ys'][r])*scale-row_rule_width))
                        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
                # python-docx retains empty paragraphs in the continuation
                # cells of vertical merges; collapse their paragraph marks too.
                from docx.text.paragraph import Paragraph
                for empty in table._tbl.xpath('.//w:tc/w:p[not(.//w:t)]'):
                    write_paragraph(Paragraph(empty,table),{'text':''},0,0,scale,cell=True)
                fit_measured_table_rows(table)
                flow_bottom += (bbox[3]-bbox[1])*scale if bbox else rows*line_height_pt('Times New Roman',11)
            elif kind == 'header':
                table = doc.add_table(rows=1, cols=2)
                table.autofit = False
                margins = OxmlElement('w:tblCellMar')
                for edge in ('top','left','bottom','right'):
                    item = OxmlElement('w:'+edge)
                    item.set(qn('w:w'),'0')
                    item.set(qn('w:type'),'dxa')
                    margins.append(item)
                table._tbl.tblPr.append(margins)
                cols = element['columns']
                split = (max(b['bbox'][2] for b in cols[0])+min(b['bbox'][0] for b in cols[1]))/2
                bounds = [left,split,right]
                for c,column in enumerate(table.columns):
                    column.width = Pt((bounds[c+1]-bounds[c])*scale)
                    column.cells[0].width = column.width
                borders = OxmlElement('w:tblBorders')
                for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
                    item = OxmlElement('w:' + edge)
                    item.set(qn('w:val'), 'nil')
                    borders.append(item)
                table._tbl.tblPr.append(borders)
                column_ends = []
                for c, column in enumerate(element['columns']):
                    previous = flow_bottom
                    for i, block in enumerate(column):
                        paragraph = table.cell(0,c).paragraphs[0] if i == 0 else table.cell(0,c).add_paragraph()
                        extent = write_paragraph(paragraph,block,bounds[c],bounds[c+1],scale)
                        before = max(0,block['bbox'][1]*scale-previous)
                        paragraph.paragraph_format.space_before = Pt(before)
                        previous += before+extent
                    column_ends.append(previous)
                flow_bottom = max(column_ends,default=flow_bottom)
            elif kind == 'image':
                # Marginal graphics belong to the source page, outside the
                # body flow. Attach them to an existing paragraph so they
                # cannot create a blank page after a nearly full text page.
                paragraph = doc.paragraphs[-1] if bbox and doc.paragraphs else doc.add_paragraph()
                if not bbox:
                    paragraph.alignment = alignments.get(element.get('align'),WD_ALIGN_PARAGRAPH.LEFT)
                picture = paragraph.add_run().add_picture(io.BytesIO(base64.b64decode(element['data'])),
                    width=Pt((bbox[2]-bbox[0])*scale) if bbox else int(available*element['width_fraction']))
                if bbox:
                    inline = picture._inline
                    anchor = OxmlElement('wp:anchor')
                    for key,value in {'distT':'0','distB':'0','distL':'0','distR':'0','simplePos':'0',
                                      'relativeHeight':'0','behindDoc':'1' if element.get('overlay') else '0',
                                      'locked':'0','layoutInCell':'1','allowOverlap':'1'}.items():
                        anchor.set(key,value)
                    simple = OxmlElement('wp:simplePos');simple.set('x','0');simple.set('y','0');anchor.append(simple)
                    for axis,value in [('H',bbox[0]),('V',bbox[1])]:
                        position = OxmlElement('wp:position'+axis);position.set('relativeFrom','page')
                        offset = OxmlElement('wp:posOffset');offset.text = str(int(Pt(value*scale)))
                        position.append(offset);anchor.append(position)
                    for child in list(inline):
                        if child.tag == qn('wp:docPr'):
                            anchor.append(OxmlElement('wp:wrapNone'))
                        anchor.append(child)
                    inline.getparent().replace(inline,anchor)
            else:
                paragraph = doc.add_paragraph()
                extent = write_paragraph(paragraph,element,left,right,scale)
                paragraph.paragraph_format.space_before = Pt(gap)
                flow_bottom += gap+extent
    doc.save(output_path)


def build_xlsx(data, output_path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Side, PatternFill
    from openpyxl.comments import Comment
    from openpyxl.utils import get_column_letter
    workbook = Workbook()
    workbook.remove(workbook.active)
    border = Border(**{edge: Side(style='thin', color='808080') for edge in ('left','right','top','bottom')})
    for i, page in enumerate(data['pages']):
        sheet = workbook.create_sheet(f'Page {i+1}')
        row = 1
        for element in _elements(page):
            if element['type'] == 'image':
                from openpyxl.drawing.image import Image
                image = Image(io.BytesIO(base64.b64decode(element['data'])))
                image.width, image.height = image.width*.32, image.height*.32
                sheet.add_image(image, f'A{row}')
                row += max(1,round(image.height/20))+1
            elif element['type'] == 'table':
                for source in element['cells']:
                    r, c = row+source['row'], 1+source['col']
                    cell = sheet.cell(r, c, source['text'])
                    cell.data_type = 's'  # OCR text is data, never an Excel formula.
                    cell.alignment = Alignment(wrap_text=True, vertical='top')
                    cell.border = border
                    if source.get('needs_review'):
                        cell.comment = Comment(source['review_reason'], 'FileForge OCR')
                        cell.fill = PatternFill('solid', fgColor='FFF3CD')
                    if source['rowspan'] > 1 or source['colspan'] > 1:
                        sheet.merge_cells(start_row=r, start_column=c,
                                          end_row=r+source['rowspan']-1, end_column=c+source['colspan']-1)
                    sheet.column_dimensions[get_column_letter(c)].width = 24
                row += len(element['grid']) + 1
            else:
                texts = ([b['text'] for col in element['columns'] for b in col]
                         if element['type'] == 'header' else [element.get('text','')])
                for text in texts:
                    cell = sheet.cell(row, 1, text)
                    cell.data_type = 's'
                    row += 1
    workbook.save(output_path)


def build_pdf(data, output_path):
    # The HTML path preserves Vietnamese fonts, multiple tables and merged cells.
    from weasyprint import HTML
    HTML(string=build_html(data), base_url=str(Path(__file__).parent)).write_pdf(output_path)
