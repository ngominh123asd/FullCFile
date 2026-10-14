"""
FileForge Backend - Premium Document Service
High-fidelity Markdown ↔ DOCX conversion with formatting preserved
"""
import os
import uuid
import re
import subprocess
import logging
from pathlib import Path
from typing import Optional
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

logger = logging.getLogger(__name__)

# Canonical font used everywhere — single source of truth for MD → DOCX and MD → PDF
DEFAULT_FONT_NAME = "Times New Roman"
DEFAULT_FONT_SIZE = 13


def set_font(run, bold=False, italic=False, size=DEFAULT_FONT_SIZE, color=None, name=DEFAULT_FONT_NAME):
    """Apply font settings to a run. Uses rFonts XML to ensure the font is
    embedded on every glyph attribute (ascii/hAnsi/cs/eastAsia) so that
    LibreOffice/Word keep the font when exporting to PDF."""
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color

    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    # Set every attribute so the font is locked everywhere
    for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
        rFonts.set(qn(attr), name)


def apply_font_to_style(doc, style_name, font_name=DEFAULT_FONT_NAME, size=DEFAULT_FONT_SIZE,
                        bold=False, color_hex=None):
    """Force the font on a paragraph style (Heading 1, Normal, ...). Without
    this, LibreOffice ignores the per-run font when exporting to PDF because
    it follows the style's font."""
    try:
        style = doc.styles[style_name]
    except KeyError:
        return
    rpr = style.element.get_or_add_rPr()
    rFonts = rpr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rpr.insert(0, rFonts)
    for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
        rFonts.set(qn(attr), font_name)
    style.font.name = font_name
    style.font.size = Pt(size)
    style.font.bold = bold
    if color_hex:
        style.font.color.rgb = RGBColor.from_string(color_hex)


def _set_rfonts_xml(run_or_style_element, font_name):
    """Ensure the <w:rFonts> element has all four glyph attributes set so that
    LibreOffice (and Word) cannot substitute a different font."""
    rPr = getattr(run_or_style_element, '_element', run_or_style_element)
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    for attr in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia'):
        rFonts.set(qn(attr), font_name)


def preserve_docx_fonts(doc):
    """Ensure every run in a DOCX has the four rFonts attributes
    (ascii/hAnsi/cs/eastAsia) all set to the *same* original font name.
    This locks the font so LibreOffice cannot substitute its default on PDF export,
    WITHOUT changing the font itself.  We use set_font() (which calls _set_rfonts_xml)
    so every attribute is overwritten at once."""
    # Runs in paragraphs
    for p in doc.paragraphs:
        for run in p.runs:
            font_name = run.font.name
            if not font_name:
                continue
            # Preserve bold/italic/size from the original; only fix rFonts attrs
            set_font(run,
                     bold=bool(run.bold),
                     italic=bool(run.italic),
                     size=run.font.size.pt if run.font.size else DEFAULT_FONT_SIZE,
                     name=font_name)

    # Runs in table cells
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        font_name = run.font.name
                        if not font_name:
                            continue
                        set_font(run,
                                 bold=bool(run.bold),
                                 italic=bool(run.italic),
                                 size=run.font.size.pt if run.font.size else DEFAULT_FONT_SIZE,
                                 name=font_name)


def pdf_to_docx(input_pdf, output_docx):
    """Convert PDF to DOCX preserving layout (paragraphs, tables, images, lists,
    formatting) using the pdf2docx library. pdf2docx uses PyMuPDF for layout
    analysis and python-docx for output — it preserves fonts, sizes, bold/
    italic, alignment, columns, tables, and inline images.
    """
    from pdf2docx import Converter

    cv = Converter(input_pdf)
    try:
        cv.convert(output_docx)
    finally:
        cv.close()

    # Post-process DOCX: standardize margins, fix centered title indents, fix bullet fonts, and clean formatting
    try:
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Pt, Cm
        from docx.oxml.ns import qn
        import re

        doc = Document(output_docx)
        modified = False

        # 1. Standardize page margins across all sections to match the PDF
        for section in doc.sections:
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.0)
            section.top_margin = Cm(2.0)
            section.bottom_margin = Cm(2.0)
            modified = True

        # 2. Fix paragraph formatting and bullet fonts
        pua_bullets = {
            '\uf0b7': '• ', '\uf0a7': '▪ ', '\uf0d8': '➢ ', '\uf076': '❖ ',
            '\uf06e': '■ ', '\uf0fc': '✔ ', '\uf0a8': '◻ ', '\uf0de': '⇒ ',
            '\uf0e0': '✉ ', '\uf034': '✓ ', '\uf075': '◆ ', '\uf02d': '– ',
        }

        for p in doc.paragraphs:
            pf = p.paragraph_format

            # Center aligned (titles, headers): remove left/right/first_line indents that crush width
            if p.alignment == WD_ALIGN_PARAGRAPH.CENTER:
                pf.left_indent = None
                pf.right_indent = None
                pf.first_line_indent = None
                if pf.space_before and pf.space_before.pt > 14:
                    pf.space_before = Pt(12)
                if pf.space_after and pf.space_after.pt > 14:
                    pf.space_after = Pt(6)
                modified = True

            # Left aligned text: remove excessive right indents (> 40 pt) that pinch lines
            if p.alignment in [WD_ALIGN_PARAGRAPH.LEFT, None]:
                if pf.right_indent and pf.right_indent.pt > 40:
                    pf.right_indent = None
                    modified = True
                if pf.space_before and pf.space_before.pt > 16:
                    pf.space_before = Pt(10)
                    modified = True
                if pf.space_after and pf.space_after.pt > 16:
                    pf.space_after = Pt(4)
                    modified = True

            # Clean runs: replace PUA bullet characters & fix Symbol/Wingdings font
            for r in p.runs:
                for pua, rep in pua_bullets.items():
                    if pua in r.text:
                        r.text = r.text.replace(pua, rep)
                        modified = True
                if re.search(r'[\uf000-\uf8ff]', r.text):
                    r.text = re.sub(r'[\uf000-\uf8ff]', '• ', r.text)
                    modified = True

                rPr = r._r.find(qn('w:rPr'))
                if rPr is not None:
                    rFonts_el = rPr.find(qn('w:rFonts'))
                    if rFonts_el is not None:
                        ascii_font = rFonts_el.get(qn('w:ascii'), '')
                        if ascii_font in ['Symbol', 'Wingdings', 'Wingdings 2', 'Wingdings 3']:
                            rFonts_el.set(qn('w:ascii'), 'Times New Roman')
                            rFonts_el.set(qn('w:hAnsi'), 'Times New Roman')
                            rFonts_el.set(qn('w:eastAsia'), 'Times New Roman')
                            modified = True

        # 3. Clean stray standalone or trailing page numbers extracted from PDF footers/headers
        for p in list(doc.paragraphs):
            txt = p.text.strip()
            # Standalone page number paragraph: remove entire paragraph
            if re.match(r'^(?:page\s*\d+|trang\s*\d+|[—–-]\s*\d+\s*[—–-]|\d{1,3})$', txt, re.IGNORECASE):
                p._p.getparent().remove(p._p)
                modified = True
                continue

            # Trailing page numbers attached at end of paragraph (e.g. \n\t2 or \t3)
            runs = list(p.runs)
            if runs:
                last_txt = runs[-1].text.strip()
                if re.match(r'^(?:page\s*\d+|trang\s*\d+|[—–-]\s*\d+\s*[—–-]|\d{1,3})$', last_txt, re.IGNORECASE):
                    p_elm = p._p
                    idx = len(runs) - 1
                    p_elm.remove(runs[idx]._r)
                    idx -= 1
                    while idx >= 0:
                        r = runs[idx]
                        r_txt = r.text.strip()
                        is_break = bool(r._r.findall(qn('w:br')) or r._r.findall(qn('w:tab')) or r.text == '\n' or r.text == '\t')
                        if not r_txt or is_break:
                            p_elm.remove(r._r)
                            idx -= 1
                        else:
                            break
                    modified = True

        # 4. Clean empty paragraphs without drawings/pictures to eliminate blank pages in Word
        for p in list(doc.paragraphs):
            if not p.text.strip() and not p._p.findall(qn('w:drawing')) and not p._p.findall(qn('w:pict')):
                p._p.getparent().remove(p._p)
                modified = True

        # 5. Format tables to center alignment and ensure clean borders
        for table in doc.tables:
            import docx.enum.table
            table.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
            modified = True

        if modified:
            doc.save(output_docx)
    except Exception as e:
        logger.debug(f"Post-processing DOCX failed: {e}")


def process_inline_formatting(paragraph, text, base_size=13, is_bold=False):
    """Parse inline markdown (bold/italic/code) and add runs to paragraph"""
    # Split by tokens: `code`, **bold**, __bold__, *italic*, _italic_
    tokens = re.split(r'(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|(?<!\*)\*[^*]+\*(?!\*)|(?<!\w)_[^_]+_(?!\w))', text)

    for token in tokens:
        if not token:
            continue

        bold = is_bold
        italic = False
        font_name = DEFAULT_FONT_NAME
        content = token
        size = base_size

        if token.startswith('`') and token.endswith('`'):
            font_name = 'Courier New'
            content = token[1:-1]
            size = max(11, base_size - 2)
        elif token.startswith('**') and token.endswith('**'):
            bold = True
            content = token[2:-2]
        elif token.startswith('__') and token.endswith('__'):
            bold = True
            content = token[2:-2]
        elif token.startswith('*') and token.endswith('*'):
            italic = True
            content = token[1:-1]
        elif token.startswith('_') and token.endswith('_'):
            italic = True
            content = token[1:-1]

        run = paragraph.add_run(content)
        set_font(run, bold=bold, italic=italic, size=size, name=font_name)


def add_paragraph_left_border(p, color_hex="4285F4", size_eighths=24):
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), str(size_eighths))
    left.set(qn('w:space'), '12')
    left.set(qn('w:color'), color_hex)
    pBdr.append(left)
    pPr.append(pBdr)


def set_paragraph_shading(p, color_hex="F0F4FE"):
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    pPr.append(shd)


def md_to_docx(input_md, output_docx):
    """Convert Markdown to a beautiful DOCX preserving all formatting"""
    doc = Document()

    # Margins (Word default 1 inch = 96 pixels)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Core properties
    cp = doc.core_properties
    cp.author = 'FileForge'
    cp.last_modified_by = 'FileForge'
    cp.title = 'Generated by FileForge'
    cp.subject = 'Document Conversion'

    # Normal style
    style = doc.styles['Normal']
    style.font.name = DEFAULT_FONT_NAME
    style.font.size = Pt(DEFAULT_FONT_SIZE)

    with open(input_md, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i].rstrip('\n')
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Code Block
        if stripped.startswith('```'):
            lang = stripped[3:].strip()
            i += 1
            code_lines = []
            while i < num_lines and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i].rstrip('\n'))
                i += 1
            i += 1
            for c_line in code_lines:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.15
                run = p.add_run(c_line if c_line else ' ')
                set_font(run, size=11, name='Courier New')
            doc.add_paragraph()  # spacing
            continue

        # Horizontal rule
        if stripped in ('---', '***', '___'):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run('─' * 40)
            set_font(run, size=10, color=RGBColor(0x9A, 0xA0, 0xA6))
            i += 1
            continue

        # Blockquote / Callout
        if stripped.startswith('>'):
            blockquote_lines = []
            while i < num_lines and lines[i].strip().startswith('>'):
                blockquote_lines.append(lines[i].strip()[1:].strip())
                i += 1

            callout_type = 'QUOTE'
            callout_match = re.match(r'^\[!(NOTE|IMPORTANT|WARNING|TIP|CAUTION)\]', blockquote_lines[0])
            start_idx = 0
            if callout_match:
                callout_type = callout_match.group(1)
                start_idx = 1

            if callout_type == 'NOTE':
                border_color = "4285F4"
                bg_color = "F0F4FE"
                prefix = "Lưu ý: "
            elif callout_type in ('IMPORTANT', 'WARNING', 'CAUTION'):
                border_color = "EA4335"
                bg_color = "FCE8E6"
                prefix = "Quan trọng: "
            elif callout_type == 'TIP':
                border_color = "34A853"
                bg_color = "E6F4EA"
                prefix = "Mẹo: "
            else:
                border_color = "9AA0A6"
                bg_color = "F8F9FA"
                prefix = ""

            clean_lines = [l for l in blockquote_lines[start_idx:] if l]
            if clean_lines:
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.left_indent = Pt(24)
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(6)

                add_paragraph_left_border(p, border_color)
                set_paragraph_shading(p, bg_color)

                if prefix:
                    prefix_run = p.add_run(prefix)
                    set_font(prefix_run, bold=True, size=12)

                combined = " ".join(clean_lines)
                process_inline_formatting(p, combined, base_size=12)

                # Italicize non-prefix text
                for run in p.runs:
                    if run.text != prefix:
                        run.font.italic = True

                doc.add_paragraph()
            continue

        # Table (GFM)
        if stripped.startswith('|') and stripped.endswith('|'):
            table_lines = []
            while i < num_lines and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                table_lines.append(lines[i].strip())
                i += 1

            rows_data = []
            for t_line in table_lines:
                clean_t = t_line.replace(':', '').replace('-', '').replace(' ', '').replace('|', '')
                if not clean_t:
                    continue
                cells = [c.strip() for c in t_line.split('|')[1:-1]]
                rows_data.append(cells)

            if rows_data:
                num_cols = max(len(r) for r in rows_data)
                table = doc.add_table(rows=len(rows_data), cols=num_cols, style='Table Grid')

                for r_idx, row_cells in enumerate(rows_data):
                    for c_idx, cell_text in enumerate(row_cells):
                        if c_idx < num_cols:
                            cell = table.cell(r_idx, c_idx)
                            cell.text = ""
                            p = cell.paragraphs[0]
                            p.paragraph_format.line_spacing = 1.15
                            p.paragraph_format.space_before = Pt(4)
                            p.paragraph_format.space_after = Pt(6)
                            is_header = (r_idx == 0)
                            process_inline_formatting(p, cell_text, base_size=11, is_bold=is_header)

                doc.add_paragraph()
            continue

        # Heading
        header_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if header_match:
            level = len(header_match.group(1))
            text = header_match.group(2)

            # Use built-in heading styles
            try:
                p = doc.add_paragraph(style=f'Heading {min(level, 9)}')
            except KeyError:
                p = doc.add_paragraph()

            p.paragraph_format.line_spacing = 1.3
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.keep_with_next = True

            if level > 2:
                p.paragraph_format.left_indent = Pt(24 * (level - 2))

            size = 22 if level == 1 else (18 if level == 2 else (15 if level == 3 else 13))
            process_inline_formatting(p, text, base_size=size, is_bold=True)
            i += 1
            continue

        # List
        list_match = re.match(r'^(\s*)([-*+]|\d+\.)\s+(.*)', line)
        if list_match:
            indent = list_match.group(1)
            bullet = list_match.group(2)
            content = list_match.group(3)

            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.5
            level = len(indent) // 2
            p.paragraph_format.left_indent = Pt(18 * (level + 1))

            bullet_run = p.add_run(f"{bullet} ")
            set_font(bullet_run)
            process_inline_formatting(p, content)
            i += 1
            continue

        # Regular paragraph
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        process_inline_formatting(p, line)
        i += 1

    doc.save(output_docx)


def pdf_to_md(input_pdf, output_md):
    """Convert a PDF file to Markdown using PyMuPDF.

    Strategy: render each page with `get_text("markdown")` (MuPDF's built-in
    markdown export) which detects headings, lists, code, and tables. We fall
    back to plain text extraction if markdown returns nothing.
    """
    import fitz  # PyMuPDF

    md_lines = []
    doc = fitz.open(input_pdf)

    try:
        for page_index, page in enumerate(doc):
            page_num = page_index + 1

            # Prefer markdown extraction (MuPDF 1.24+ supports it via "md")
            md_text = ""
            try:
                md_text = page.get_text("md") or ""
            except Exception:
                md_text = ""

            if not md_text.strip():
                # Fallback to plain text
                md_text = page.get_text("text") or ""

            md_text = md_text.strip()
            if not md_text:
                continue

            # Normalize excessive blank lines
            cleaned = re.sub(r"\n{3,}", "\n\n", md_text)

            if page_index > 0:
                md_lines.append("")
            md_lines.append(f"<!-- Page {page_num} -->")
            md_lines.append("")
            md_lines.append(cleaned)
    finally:
        doc.close()

    final = "\n".join(md_lines).strip() + "\n"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(final)


def iter_block_items(parent):
    # Document from python-docx is a factory function, not a class,
    # so we check for the .element attribute instead of isinstance.
    if hasattr(parent, 'element'):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._element

    for child in parent_elm.iterchildren():
        if child.tag.endswith('}p'):
            yield Paragraph(child, parent)
        elif child.tag.endswith('}tbl'):
            yield Table(child, parent)


def get_paragraph_markdown(p):
    """Convert Word paragraph back to Markdown"""
    runs = []
    for child in p._p.iterchildren():
        tag = child.tag
        if tag.endswith('}r'):
            runs.append(Run(child, p))
        elif tag.endswith('}hyperlink'):
            for sub in child.iterchildren():
                if sub.tag.endswith('}r'):
                    runs.append(Run(sub, p))

    if not runs:
        return p.text or ""

    merged = []
    current_text = ""
    current_bold = None
    current_italic = None
    current_code = None

    for r in runs:
        text = r.text
        if text is None:
            continue
        bold = bool(r.bold)
        italic = bool(r.italic)
        font_name = (r.font.name or "").lower()
        code = 'courier' in font_name

        if current_bold is None:
            current_text = text
            current_bold = bold
            current_italic = italic
            current_code = code
        elif current_bold == bold and current_italic == italic and current_code == code:
            current_text += text
        else:
            merged.append((current_text, current_bold, current_italic, current_code))
            current_text = text
            current_bold = bold
            current_italic = italic
            current_code = code

    if current_bold is not None:
        merged.append((current_text, current_bold, current_italic, current_code))

    md_text = ""
    for text, bold, italic, code in merged:
        if not text:
            continue
        stripped = text.strip()
        if not stripped:
            md_text += text
            continue
        is_punct = not any(c.isalnum() for c in stripped)

        if code:
            formatted = f"`{stripped}`"
        elif bold and italic and not is_punct:
            formatted = f"***{stripped}***"
        elif bold and not is_punct:
            formatted = f"**{stripped}**"
        elif italic and not is_punct:
            formatted = f"*{stripped}*"
        else:
            formatted = stripped

        leading = text[:len(text) - len(text.lstrip())]
        trailing = text[len(text.rstrip()):]
        md_text += leading + formatted + trailing

    return md_text


def convert_table_to_markdown(table):
    """Convert Word table back to Markdown"""
    md_rows = []
    if len(table.rows) == 0:
        return ""

    # Detect alignments from first row
    first_aligns = []
    for cell in table.rows[0].cells:
        align = ":---"
        for p in cell.paragraphs:
            if p.alignment == 1:
                align = ":---:"
                break
            elif p.alignment == 2:
                align = "---:"
                break
        first_aligns.append(align)

    for i, row in enumerate(table.rows):
        row_paragraphs = []
        for cell in row.cells:
            parts = []
            for p in cell.paragraphs:
                txt = get_paragraph_markdown(p).strip()
                if txt:
                    parts.append(txt)
            row_paragraphs.append(parts)

        max_p = max((len(parts) for parts in row_paragraphs), default=0)
        if max_p == 0:
            empty_cells = [" " for _ in row.cells]
            md_rows.append(f"| {' | '.join(empty_cells)} |")
            if i == 0:
                md_rows.append(f"| {' | '.join(first_aligns)} |")
            continue

        for k in range(max_p):
            cells = []
            for parts in row_paragraphs:
                cell_text = parts[k] if k < len(parts) else ""
                cell_text = cell_text.replace("|", "\\|")
                cells.append(cell_text)
            md_rows.append(f"| {' | '.join(cells)} |")
            if i == 0 and k == 0:
                md_rows.append(f"| {' | '.join(first_aligns)} |")

    return "\n".join(md_rows) + "\n"


def docx_to_md(input_docx, output_md):
    """Convert DOCX back to Markdown preserving formatting"""
    doc = Document(input_docx)
    md_lines = []
    in_code = False
    code_lines = []

    for item in iter_block_items(doc):
        if isinstance(item, Table):
            if in_code:
                md_lines.append("```")
                md_lines.extend(code_lines)
                md_lines.append("```")
                md_lines.append("")
                in_code = False

            if md_lines and md_lines[-1] != "":
                md_lines.append("")
            md_lines.append(convert_table_to_markdown(item))
            continue

        if isinstance(item, Paragraph):
            p = item
            text = p.text
            style_name = (p.style.name.lower() if p.style else "")

            # Code block detection
            font_names = [r.font.name for r in p.runs if r.font and r.font.name]
            is_code = any(fn and 'courier' in fn.lower() for fn in font_names)

            if is_code:
                if not in_code:
                    in_code = True
                    code_lines = []
                code_lines.append(text)
                continue
            else:
                if in_code:
                    md_lines.append("```")
                    md_lines.extend(code_lines)
                    md_lines.append("```")
                    md_lines.append("")
                    in_code = False

            if not text.strip():
                if md_lines and md_lines[-1] != "":
                    md_lines.append("")
                continue

            md_text = get_paragraph_markdown(p)

            # Headings
            if style_name.startswith('heading '):
                try:
                    level = int(style_name.split(' ')[1])
                except (ValueError, IndexError):
                    level = 1
                if md_lines and md_lines[-1] != "":
                    md_lines.append("")
                md_lines.append(f"{'#' * level} {md_text}")
                md_lines.append("")
                continue

            # Lists
            is_list = 'list' in style_name or style_name in ('bullet', 'list bullet')

            if is_list:
                stripped = md_text.lstrip(' \t')
                if not (stripped.startswith('-') or stripped.startswith('*') or re.match(r'^\d+\.', stripped)):
                    md_lines.append(f"- {md_text.strip()}")
                else:
                    md_lines.append(md_text)
                continue

            # Normal paragraph
            if md_lines and md_lines[-1] != "":
                md_lines.append("")
            md_lines.append(md_text)

    if in_code:
        md_lines.append("```")
        md_lines.extend(code_lines)
        md_lines.append("```")

    with open(output_md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_lines))


def optimize_docx_tables(docx_path: str):
    """
    Ensure document margins and table layouts fit A4 page dimensions perfectly:
    - 2-column signature/header layout tables span full printable width (50%/50%).
    - Wide multi-column data tables are proportionally fitted so right columns are never cut off.
    - Page margins are adjusted (1.2cm L/R, 1.5cm T/B) so top and bottom text never gets cut off.
    """
    try:
        from docx import Document
        from docx.shared import Cm
        from docx.oxml.ns import qn
        import docx.enum.table

        doc = Document(docx_path)
        modified = False

        # 1. Standardize page dimensions & margins
        for s in doc.sections:
            s.page_width = Cm(21.0)
            s.page_height = Cm(29.7)
            s.left_margin = Cm(1.2)
            s.right_margin = Cm(1.2)
            s.top_margin = Cm(1.5)
            s.bottom_margin = Cm(1.5)
            modified = True

        # Printable width: 21.0cm - 2.4cm = 18.6cm = 527.3pt = ~10545 dxa
        printable_w_dxa = int((21.0 - 2.4) / 2.54 * 72 * 20)
        half_dxa = printable_w_dxa // 2

        # 2. Adjust tables so they fit perfectly within printable width without overflowing
        for t in doc.tables:
            t.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
            tblPr = t._tbl.tblPr
            tblW = tblPr.find(qn('w:tblW'))

            # 2-column header or signature layout table -> 50% / 50%
            if len(t.columns) == 2:
                if tblW is not None:
                    tblW.set(qn('w:w'), str(printable_w_dxa))
                    tblW.set(qn('w:type'), 'dxa')
                tblGrid = t._tbl.tblGrid
                if tblGrid is not None:
                    for gc in tblGrid.findall(qn('w:gridCol')):
                        gc.set(qn('w:w'), str(half_dxa))
                for row in t.rows:
                    if len(row.cells) == 2:
                        for c in row.cells:
                            tcPr = c._tc.get_or_add_tcPr()
                            tcW = tcPr.get_or_add_tcW()
                            tcW.set(qn('w:w'), str(half_dxa))
                            tcW.set(qn('w:type'), 'dxa')
                modified = True
            else:
                # Multi-column data table -> ensure total width fits within printable width
                current_cols = t._tbl.tblGrid.findall(qn('w:gridCol')) if t._tbl.tblGrid is not None else []
                col_widths = [int(gc.get(qn('w:w'), '0')) for gc in current_cols]
                total_curr_dxa = sum(col_widths)
                if total_curr_dxa > printable_w_dxa:
                    ratio = printable_w_dxa / total_curr_dxa
                    new_col_dxas = [int(w * ratio) for w in col_widths]
                    diff = printable_w_dxa - sum(new_col_dxas)
                    new_col_dxas[-1] += diff
                    for gc, new_w in zip(current_cols, new_col_dxas):
                        gc.set(qn('w:w'), str(new_w))
                    for row in t.rows:
                        for c, new_w in zip(row.cells, new_col_dxas):
                            tcPr = c._tc.get_or_add_tcPr()
                            tcW = tcPr.get_or_add_tcW()
                            tcW.set(qn('w:w'), str(new_w))
                            tcW.set(qn('w:type'), 'dxa')
                    if tblW is not None:
                        tblW.set(qn('w:w'), str(printable_w_dxa))
                        tblW.set(qn('w:type'), 'dxa')
                    modified = True

        if modified:
            doc.save(docx_path)
    except Exception as e:
        logger.debug(f"optimize_docx_tables error: {e}")


class DocumentService:
    """Premium document conversion service"""

    async def convert(
        self,
        input_path: str,
        output_format: str,
        options: Optional[dict] = None,
    ) -> dict:
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Input file not found: {input_path}")

        output_dir = "/tmp/fileforge_outputs"
        os.makedirs(output_dir, exist_ok=True)

        output_filename = f"{uuid.uuid4()}.{output_format}"
        output_path = os.path.join(output_dir, output_filename)

        input_ext = Path(input_path).suffix.lstrip(".").lower()

        # Markdown ↔ DOCX: high-fidelity
        if input_ext == "md" and output_format in ("docx", "md"):
            if output_format == "docx":
                md_to_docx(input_path, output_path)
            else:
                import shutil
                shutil.copy(input_path, output_path)
        elif input_ext == "docx" and output_format == "md":
            docx_to_md(input_path, output_path)
        elif input_ext == "docx" and output_format == "txt":
            # DOCX → TXT
            doc = Document(input_path)
            parts = []
            for para in doc.paragraphs:
                parts.append(para.text)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(parts))
        elif input_ext == "docx" and output_format == "pdf":
            # DOCX → PDF: preserve 100% of the original document's fonts, formatting, and styles
            pdf_created = False

            # Strategy 1: Word COM on Windows (best native fidelity)
            if os.name == 'nt':
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                    try:
                        from win32com.client import Dispatch
                        wd = Dispatch('Word.Application')
                        wd.Visible = False
                        wd.DisplayAlerts = 0
                        doc_obj = wd.Documents.Open(os.path.abspath(input_path))
                        doc_obj.ExportAsFixedFormat(
                            OutputFileName=os.path.abspath(output_path),
                            ExportFormat=17,
                        )
                        doc_obj.Close(False)
                        wd.Quit()
                        pdf_created = os.path.exists(output_path)
                    finally:
                        pythoncom.CoUninitialize()
                except Exception as e:
                    logger.warning(f"Word COM DOCX→PDF failed: {e}")
                    pdf_created = False

            # Strategy 2: LibreOffice (converts original DOCX with embedded fonts & exact layout)
            if not pdf_created:
                output_dir = os.path.dirname(output_path)
                result = subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "pdf",
                     "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                expected_pdf = os.path.join(output_dir, f"{Path(input_path).stem}.pdf")
                if os.path.exists(expected_pdf):
                    if expected_pdf != output_path:
                        os.rename(expected_pdf, output_path)
                    pdf_created = True

            # Strategy 3: WeasyPrint fallback
            if not pdf_created:
                try:
                    import html
                    from weasyprint import HTML
                    doc = Document(input_path)
                    html_parts = [
                        '<!DOCTYPE html><html><head><meta charset="utf-8">'
                        '<style>body { font-family: "Times New Roman", serif; font-size: 13pt; line-height: 1.5; padding: 2cm; } '
                        'p { margin-bottom: 1em; }</style></head><body>'
                    ]
                    for p in doc.paragraphs:
                        if p.text.strip():
                            html_parts.append(f'<p>{html.escape(p.text)}</p>')
                    html_parts.append('</body></html>')
                    HTML(string='\n'.join(html_parts)).write_pdf(output_path)
                    pdf_created = os.path.exists(output_path)
                except Exception as e:
                    logger.warning(f"WeasyPrint fallback failed: {e}")

            if not pdf_created:
                raise RuntimeError(
                    "Could not convert DOCX to PDF. "
                    "Ensure Microsoft Word or LibreOffice is installed."
                )
        elif input_ext == "md" and output_format == "pdf":
            # MD → DOCX → PDF. After generating the DOCX, lock Times New Roman
            # everywhere (MD has no original font — use the canonical default).
            intermediate = output_path.replace(".pdf", ".docx")
            md_to_docx(input_path, intermediate)

            doc = Document(intermediate)
            # Force TNR on styles so LibreOffice uses it on export
            for style_name in ('Normal', 'Heading 1', 'Heading 2', 'Heading 3',
                                'Heading 4', 'Heading 5', 'Heading 6'):
                apply_font_to_style(doc, style_name, font_name=DEFAULT_FONT_NAME,
                                    size=DEFAULT_FONT_SIZE)
            heading_sizes = {1: 22, 2: 18, 3: 15, 4: 13, 5: 13, 6: 13}
            for level, sz in heading_sizes.items():
                apply_font_to_style(doc, f'Heading {level}', font_name=DEFAULT_FONT_NAME,
                                    size=sz, bold=True)
            # Re-apply per-run font with full rFonts attrs
            for p in doc.paragraphs:
                for run in p.runs:
                    current = (run.font.name or "").lower()
                    if 'courier' in current:
                        set_font(run, bold=run.bold or False, italic=run.italic or False,
                                 size=11, name='Courier New')
                    else:
                        set_font(run, bold=run.bold or False, italic=run.italic or False,
                                 size=run.font.size.pt if run.font.size else DEFAULT_FONT_SIZE,
                                 name=DEFAULT_FONT_NAME)
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            for run in p.runs:
                                current = (run.font.name or "").lower()
                                if 'courier' in current:
                                    set_font(run, bold=run.bold or False,
                                             italic=run.italic or False,
                                             size=11, name='Courier New')
                                else:
                                    set_font(run, bold=run.bold or False,
                                             italic=run.italic or False,
                                             size=run.font.size.pt if run.font.size else 11,
                                             name=DEFAULT_FONT_NAME)
            doc.save(intermediate)

            intermediate_dir = os.path.dirname(intermediate)
            subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", intermediate_dir, intermediate],
                capture_output=True, text=True, timeout=60
            )
            base = Path(intermediate).stem
            expected_pdf = os.path.join(intermediate_dir, f"{base}.pdf")
            if os.path.exists(expected_pdf):
                if expected_pdf != output_path:
                    os.rename(expected_pdf, output_path)
            if os.path.exists(intermediate):
                os.remove(intermediate)
        elif input_ext == "pdf" and output_format == "md":
            # PDF → Markdown via PyMuPDF
            pdf_to_md(input_path, output_path)
        elif input_ext == "pdf" and output_format == "txt":
            # PDF → plain text via PyMuPDF
            import fitz
            out_doc = fitz.open(input_path)
            try:
                parts = []
                for page in out_doc:
                    parts.append(page.get_text("text"))
            finally:
                out_doc.close()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(parts))
        elif input_ext == "pdf" and output_format == "docx":
            # PDF → DOCX: extract text + font info via PyMuPDF, write DOCX with
            # the original fonts mapped to Windows equivalents.
            pdf_to_docx(input_path, output_path)
        elif input_ext == "docx" and output_format == "html":
            subprocess.run(
                ["pandoc", input_path, "-o", output_path, "--from", "docx", "--to", "html", "--standalone"],
                capture_output=True, text=True
            )
        elif input_ext in ("doc", "rtf"):
            # DOC (Word 97-2003 binary format, HTML/XML export) & RTF conversion via LibreOffice
            base = Path(input_path).stem
            if output_format == "docx":
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                expected_docx = os.path.join(output_dir, f"{base}.docx")
                if not os.path.exists(expected_docx):
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "docx:Office Open XML Text", "--outdir", output_dir, input_path],
                        capture_output=True, text=True, timeout=60
                    )
                if os.path.exists(expected_docx):
                    if expected_docx != output_path:
                        os.rename(expected_docx, output_path)
                    optimize_docx_tables(output_path)
            elif output_format == "pdf":
                # Convert to formatted DOCX first, optimize layout, then render to PDF for pristine spacing
                intermediate_docx = os.path.join(output_dir, f"{base}_{uuid.uuid4().hex[:8]}.docx")
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                base_docx = os.path.join(output_dir, f"{base}.docx")
                if not os.path.exists(base_docx):
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "docx:Office Open XML Text", "--outdir", output_dir, input_path],
                        capture_output=True, text=True, timeout=60
                    )
                if os.path.exists(base_docx):
                    os.rename(base_docx, intermediate_docx)
                    optimize_docx_tables(intermediate_docx)
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, intermediate_docx],
                        capture_output=True, text=True, timeout=60
                    )
                    expected_pdf = intermediate_docx.replace(".docx", ".pdf")
                    if os.path.exists(expected_pdf):
                        if expected_pdf != output_path:
                            os.rename(expected_pdf, output_path)
                    if os.path.exists(intermediate_docx):
                        os.remove(intermediate_docx)
                else:
                    # Fallback direct export
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, input_path],
                        capture_output=True, text=True, timeout=60
                    )
                    expected_pdf = os.path.join(output_dir, f"{base}.pdf")
                    if not os.path.exists(expected_pdf):
                        subprocess.run(
                            ["libreoffice", "--headless", "--convert-to", "pdf:writer_web_pdf_Export", "--outdir", output_dir, input_path],
                            capture_output=True, text=True, timeout=60
                        )
                    if os.path.exists(expected_pdf):
                        if expected_pdf != output_path:
                            os.rename(expected_pdf, output_path)
            elif output_format == "md":
                intermediate = output_path.replace(".md", f".{uuid.uuid4().hex}.docx")
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                expected_docx = os.path.join(output_dir, f"{base}.docx")
                if not os.path.exists(expected_docx):
                    subprocess.run(
                        ["libreoffice", "--headless", "--convert-to", "docx:Office Open XML Text", "--outdir", output_dir, input_path],
                        capture_output=True, text=True, timeout=60
                    )
                if os.path.exists(expected_docx):
                    if expected_docx != intermediate:
                        os.rename(expected_docx, intermediate)
                    docx_to_md(intermediate, output_path)
                    if os.path.exists(intermediate):
                        os.remove(intermediate)
            elif output_format == "txt":
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "txt:Text", "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                expected_txt = os.path.join(output_dir, f"{base}.txt")
                if os.path.exists(expected_txt):
                    if expected_txt != output_path:
                        os.rename(expected_txt, output_path)
            elif output_format == "html":
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "html:XHTML", "--outdir", output_dir, input_path],
                    capture_output=True, text=True, timeout=60
                )
                expected_html = os.path.join(output_dir, f"{base}.html")
                if os.path.exists(expected_html):
                    if expected_html != output_path:
                        os.rename(expected_html, output_path)
        elif input_ext == "md" and output_format == "html":
            subprocess.run(
                ["pandoc", input_path, "-o", output_path, "--from", "markdown", "--to", "html", "--standalone"],
                capture_output=True, text=True
            )
        elif output_format == "txt":
            with open(input_path, "rb") as f:
                content = f.read()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content.decode("utf-8", errors="ignore"))
        else:
            raise ValueError(f"Unsupported conversion: {input_ext} → {output_format}")

        if not os.path.exists(output_path):
            raise RuntimeError("Conversion produced no output")

        return {
            "output_path": output_path,
            "format": output_format,
            "size": os.path.getsize(output_path),
        }


document_service = DocumentService()