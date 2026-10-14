"""DOCX table geometry shared by preview parsing and pagination."""
import re
import base64
from docx.oxml.ns import qn
from html import escape


def safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def page_setup(section):
    setup = {}
    for key, attr in (
        ('width_pt', 'page_width'), ('height_pt', 'page_height'),
        ('top_pt', 'top_margin'), ('bottom_pt', 'bottom_margin'),
        ('left_pt', 'left_margin'), ('right_pt', 'right_margin')
    ):
        val = getattr(section, attr, None)
        if val is not None and hasattr(val, 'pt'):
            setup[key] = float(val.pt)
        elif val is not None:
            setup[key] = safe_float(val, default=72.0)
        else:
            if 'width' in key:
                setup[key] = 595.3
            elif 'height' in key:
                setup[key] = 841.9
            else:
                setup[key] = 72.0
    return setup


def paragraph_css(info):
    parts = [f'text-align:{info.get("align","left")}']
    for key, css in [('font_size', 'font-size'), ('margin_top_pt', 'margin-top'),
                    ('margin_bottom_pt', 'margin-bottom'), ('indent_left_pt', 'margin-left'),
                    ('indent_right_pt', 'margin-right'), ('first_line_pt', 'text-indent')]:
        if key in info and info[key] is not None:
            parts.append(f'{css}:{safe_float(info[key]):.2f}pt')
    if info.get('line_height_pt'):
        parts.append(f'line-height:{safe_float(info["line_height_pt"]):.2f}pt')
    elif info.get('line_spacing'):
        parts.append(f'line-height:{safe_float(info["line_spacing"]):.3f}')
    return escape(';'.join(parts), quote=True)


def run_images(run, part):
    """Render embedded raster images only; never load external relationships."""
    items, height = [], 0.0
    try:
        for drawing in run.findall(qn('w:drawing')):
            extent = next(drawing.iter(qn('wp:extent')), None)
            if extent is None:
                continue
            width = safe_float(extent.get('cx', '0')) / 12700.0
            image_height = safe_float(extent.get('cy', '0')) / 12700.0
            anchor = drawing.find(qn('wp:anchor'))
            positioning = ''
            if anchor is not None:
                offsets = []
                for axis in ('H', 'V'):
                    position = anchor.find(qn('wp:position' + axis))
                    offset = position.find(qn('wp:posOffset')) if position is not None else None
                    if position is None or position.get('relativeFrom') != 'page' or offset is None or offset.text is None:
                        break
                    offsets.append(safe_float(offset.text) / 12700.0)
                if len(offsets) == 2:
                    positioning = f'position:absolute;left:{offsets[0]:.2f}pt;top:{offsets[1]:.2f}pt;'
            for blip in drawing.iter(qn('a:blip')):
                identity = blip.get(qn('r:embed'))
                if not identity or identity not in part.related_parts:
                    continue
                image_part = part.related_parts[identity]
                if image_part.content_type not in ('image/png', 'image/jpeg', 'image/gif'):
                    continue
                data = base64.b64encode(image_part.blob).decode('ascii')
                items.append(f'<img alt="" src="data:{image_part.content_type};base64,{data}" '
                             f'style="{positioning}width:{width:.2f}pt;max-width:100%;height:auto"/>')
                if not positioning:
                    height = max(height, image_height)
    except Exception:
        pass
    return ''.join(items), height


def run_text(run):
    """Read inline content in XML order, including breaks between text nodes."""
    parts = []
    for child in run:
        if child.tag == qn('w:t'):
            parts.append(child.text or '')
        elif child.tag == qn('w:tab'):
            parts.append('\t')
        elif child.tag == qn('w:cr') or (child.tag == qn('w:br') and
                child.get(qn('w:type'), 'textWrapping') == 'textWrapping'):
            parts.append('\n')
        elif child.tag == qn('w:noBreakHyphen'):
            parts.append('\u2011')
        elif child.tag == qn('w:softHyphen'):
            parts.append('\u00ad')
    return ''.join(parts)


def parse_table(table, parse_paragraph, styles):
    widths = [safe_float(c.get(qn('w:w'), '0')) / 20.0 for c in table.findall('./' + qn('w:tblGrid') + '/' + qn('w:gridCol'))]
    props = table.find(qn('w:tblPr'))
    borders = props.find(qn('w:tblBorders')) if props is not None else None
    if borders is None and props is not None:
        style = props.find(qn('w:tblStyle'))
        if style is not None:
            style_id = style.get(qn('w:val'))
            if styles is not None:
                for entry in styles:
                    if entry.get(qn('w:styleId')) == style_id:
                        borders = entry.find('./' + qn('w:tblPr') + '/' + qn('w:tblBorders'))
                        break
    has_borders = borders is not None and any(
        hasattr(edge, 'get') and edge.get(qn('w:val'), 'none') not in ('none', 'nil', '0', '')
        for edge in borders
    )
    rows, geometry, heights, active = [], [], [], {}
    for tr in table.findall(qn('w:tr')):
        row_height = tr.find('./' + qn('w:trPr') + '/' + qn('w:trHeight'))
        measured_height = safe_float(row_height.get(qn('w:val'), '0')) / 20.0 if row_height is not None else 0
        data, cells, height, col, next_active = [], [], measured_height or 20.0, 0, {}
        for tc in tr.findall(qn('w:tc')):
            tcpr = tc.find(qn('w:tcPr'))
            span = tcpr.find(qn('w:gridSpan')) if tcpr is not None else None
            span = safe_int(span.get(qn('w:val'), '1'), default=1) if span is not None else 1
            merge = tcpr.find(qn('w:vMerge')) if tcpr is not None else None
            continuing = merge is not None and merge.get(qn('w:val'), 'continue') != 'restart'
            meta = {'col': col, 'colspan': span, 'rowspan': 1, 'hidden': False}
            if continuing and col in active and active[col]['colspan'] == span:
                active[col]['rowspan'] += 1
                next_active[col] = active[col]
                meta['hidden'] = True
            elif merge is not None:
                next_active[col] = meta
            parts = []
            for p in tc.findall(qn('w:p')):
                info = parse_paragraph(p, is_table_cell=True)
                if info.get('content'):
                    parts.append(f'<div style="{paragraph_css(info)}">{info["content"]}</div>')
            html = ''.join(parts)
            data.append(html)
            cells.append(meta)
            chars = len(re.sub('<[^>]+>', '', html))
            width = sum(widths[col:col+span]) if widths else 150.0
            line_count = max(1, len(parts) + html.count('<br/>'), int(chars / max(12, width / 5.5)) + 1)
            if not measured_height:
                height = max(height, line_count * 14.0 + 8.0)
            col += span
        active = next_active
        rows.append(data)
        geometry.append(cells)
        heights.append(height)
    indent = props.find(qn('w:tblInd')) if props is not None else None
    cell_margins = props.find(qn('w:tblCellMar')) if props is not None else None
    padding = {}
    if cell_margins is not None:
        for edge in ('top', 'bottom', 'left', 'right'):
            item = cell_margins.find(qn('w:' + edge))
            if item is not None:
                padding[edge] = safe_float(item.get(qn('w:w'), '0')) / 20.0
    return {
        'type': 'table',
        'data': rows,
        'cell_props': geometry,
        'row_heights': heights,
        'height': sum(heights) + 12.0,
        'has_borders': has_borders,
        'col_widths': widths,
        'indent_left_pt': safe_float(indent.get(qn('w:w'), '0')) / 20.0 if indent is not None else 0.0,
        'cell_padding_pt': padding,
    }


def table_chunks(block, available_height):
    """Never break a vertical merge or discard geometry when paginating."""
    rows = block['data']
    props = block.get('cell_props', [[] for _ in rows])
    heights = block.get('row_heights', [26.0 for _ in rows])
    start, end, height = 0, 0, 12.0
    while end < len(rows):
        stop = end + 1
        cursor = end
        while cursor < stop:
            stop = min(len(rows), max(stop, max(
                (cursor + c.get('rowspan', 1) for c in props[cursor] if not c.get('hidden')), default=stop)))
            cursor += 1
        group_height = sum(heights[end:stop])
        if end > start and height + group_height > available_height:
            yield dict(block, data=rows[start:end], cell_props=props[start:end],
                       row_heights=heights[start:end], height=height)
            start, height = end, 12.0
        height += group_height
        end = stop
    if end > start:
        yield dict(block, data=rows[start:end], cell_props=props[start:end],
                   row_heights=heights[start:end], height=height)
