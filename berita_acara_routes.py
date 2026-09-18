"""
Berita Acara routes and functionality
Integrates Berita Acara and BQ functionality into the main app
"""
from flask import render_template, request, jsonify, send_file, send_from_directory, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from xml.sax.saxutils import escape
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.utils import ImageReader, simpleSplit
import io

# Indonesian day names mapping
INDONESIAN_DAYS = {
    'Monday': 'Senin',
    'Tuesday': 'Selasa',
    'Wednesday': 'Rabu',
    'Thursday': 'Kamis',
    'Friday': 'Jumat',
    'Saturday': 'Sabtu',
    'Sunday': 'Minggu'
}

# Indonesian month names mapping
INDONESIAN_MONTHS = {
    'January': 'Januari',
    'February': 'Februari',
    'March': 'Maret',
    'April': 'April',
    'May': 'Mei',
    'June': 'Juni',
    'July': 'Juli',
    'August': 'Agustus',
    'September': 'September',
    'October': 'Oktober',
    'November': 'November',
    'December': 'Desember'
}

# Roman numerals for months
ROMAN_MONTHS = {
    1: 'I',
    2: 'II',
    3: 'III',
    4: 'IV',
    5: 'V',
    6: 'VI',
    7: 'VII',
    8: 'VIII',
    9: 'IX',
    10: 'X',
    11: 'XI',
    12: 'XII'
}

def format_indonesian_date(date):
    """Format date to Indonesian format"""
    english_day = date.strftime('%A')
    english_month = date.strftime('%B')
    
    indonesian_day = INDONESIAN_DAYS.get(english_day, english_day)
    indonesian_month = INDONESIAN_MONTHS.get(english_month, english_month)
    
    return f"{indonesian_day}, {date.day} {indonesian_month} {date.year}"

def format_indonesian_day_phrase(date):
    """Format a date phrase that matches the document style."""
    english_day = date.strftime('%A')
    english_month = date.strftime('%B')

    indonesian_day = INDONESIAN_DAYS.get(english_day, english_day)
    indonesian_month = INDONESIAN_MONTHS.get(english_month, english_month)

    return f"{indonesian_day} Tanggal {date.day} {indonesian_month} Tahun {date.year}"

def generate_berita_acara_number(nomor_input, tanggal):
    """Generate complete Berita Acara number from input number and date.
    
    Format: {nomor}/BAK-TAR/ENG/{bulan_romawi}/{tahun}
    Example: 067 -> 067/BAK-TAR/ENG/VIII/2026
    """
    try:
        # Pad the number with leading zeros if needed (3 digits)
        nomor_padded = str(nomor_input).zfill(3)
        
        # Get month in Roman numerals
        bulan_romawi = ROMAN_MONTHS.get(tanggal.month, str(tanggal.month))
        
        # Get year
        tahun = tanggal.year
        
        # Generate complete number
        nomor_lengkap = f"{nomor_padded}/BAK-TAR/ENG/{bulan_romawi}/{tahun}"
        
        return nomor_lengkap
    except Exception as e:
        # If there's any error, return the original input
        return str(nomor_input)

def safe_paragraph_text(value):
    return escape(value or "").replace("\n", "<br/>")

def wrap_paragraph(text, style, width):
    paragraph = Paragraph(safe_paragraph_text(text), style)
    _, height = paragraph.wrap(width, 1000)
    return paragraph, height

def draw_fitted_image(c, path, x, top_y, width, height):
    if not path or not os.path.exists(path):
        return False

    image = ImageReader(path)
    image_width, image_height = image.getSize()
    if not image_width or not image_height:
        return False

    scale = min(width / image_width, height / image_height)
    draw_width = image_width * scale
    draw_height = image_height * scale
    draw_x = x + (width - draw_width) / 2
    draw_y = top_y - height + (height - draw_height) / 2
    c.drawImage(image, draw_x, draw_y, width=draw_width, height=draw_height, mask='auto')
    return True

def draw_section_box(c, x, top_y, width, header_text, body_text, header_height, body_style):
    body_width = width - 0.2 * inch
    body_paragraph, body_height = wrap_paragraph(body_text, body_style, body_width)
    body_padding_top = 0.1 * inch
    body_padding_bottom = 0.1 * inch
    total_height = header_height + body_padding_top + body_height + body_padding_bottom

    c.setLineWidth(0.8)
    c.rect(x, top_y - total_height, width, total_height)
    c.line(x, top_y - header_height, x + width, top_y - header_height)
    c.setFont('Helvetica', 11.2)
    c.drawString(x + 0.08 * inch, top_y - 0.18 * inch, header_text)
    body_paragraph.drawOn(c, x + 0.1 * inch, top_y - header_height - body_padding_top - body_height)
    return top_y - total_height

def draw_two_column_section(c, x, top_y, width, header_text, left_label, left_value, right_label, right_value, label_style, value_style):
    section_title_h = 0.18 * inch
    box_top_gap = 0.05 * inch
    inner_pad = 0.10 * inch
    col_gap = 0.12 * inch
    col_width = (width - (inner_pad * 2) - col_gap) / 2

    # Remove manual line breaks and let paragraph wrap naturally
    left_value_clean = ' '.join(left_value.split()) if left_value else ''
    right_value_clean = ' '.join(right_value.split()) if right_value else ''

    # Create justified style for value columns
    justified_style = ParagraphStyle(
        'Justified',
        parent=value_style,
        alignment=TA_JUSTIFY
    )

    left_label_p, left_label_h = wrap_paragraph(left_label, label_style, col_width * 0.46)
    left_value_p, left_value_h = wrap_paragraph(left_value_clean, justified_style, col_width * 0.95)
    right_label_p, right_label_h = wrap_paragraph(right_label, label_style, col_width * 0.46)
    right_value_p, right_value_h = wrap_paragraph(right_value_clean, justified_style, col_width * 0.95)

    row1_h = max(left_label_h, right_label_h) + 0.06 * inch
    row2_h = max(left_value_h, right_value_h) + 0.10 * inch
    total_height = section_title_h + box_top_gap + row1_h + row2_h

    c.setFont('Helvetica-Bold', 11.2)
    c.drawString(x, top_y - 0.14 * inch, header_text)

    box_top = top_y - section_title_h - box_top_gap
    c.setLineWidth(0.8)
    c.rect(x, box_top - (row1_h + row2_h), width, row1_h + row2_h)
    c.line(x + inner_pad + col_width, box_top, x + inner_pad + col_width, box_top - (row1_h + row2_h))
    c.line(x, box_top - row1_h, x + width, box_top - row1_h)

    left_label_p.drawOn(c, x + inner_pad, box_top - 0.04 * inch - left_label_h)
    right_label_p.drawOn(c, x + inner_pad + col_width + col_gap, box_top - 0.04 * inch - right_label_h)
    left_value_p.drawOn(c, x + inner_pad, box_top - row1_h - 0.05 * inch - left_value_h)
    right_value_p.drawOn(c, x + inner_pad + col_width + col_gap, box_top - row1_h - 0.05 * inch - right_value_h)
    return top_y - total_height

def draw_numbered_items(c, x, top_y, width, items, style):
    cursor_y = top_y
    for idx, item in enumerate(items, 1):
        para = Paragraph(f'{idx}. {safe_paragraph_text(item)}', style)
        _, h = para.wrap(width, 200)
        para.drawOn(c, x, cursor_y - h)
        cursor_y -= h + 0.05 * inch
    return cursor_y

def draw_image_gallery(c, x, top_y, width, image_paths, date_text, caption_style, bottom_floor, page_height, top_margin):
    if not image_paths:
        return top_y

    image_gap = 0.04 * inch
    cursor_y = top_y

    # Fixed size for all photos - single row layout
    img_h = 1.7 * inch
    
    # Check if there's enough space for the row
    if cursor_y - img_h < bottom_floor:
        c.showPage()
        cursor_y = page_height - top_margin
    
    img_w = (width - (image_gap * (len(image_paths) - 1))) / len(image_paths)
    
    for i, img_path in enumerate(image_paths):
        img_x = x + i * (img_w + image_gap)
        draw_fitted_image(c, img_path, img_x, cursor_y, img_w, img_h)
    
    cursor_y -= img_h

    return cursor_y

def split_text_to_lines(text, font_name, font_size, width):
    lines = []
    for paragraph in (text or '').split('\n'):
        stripped = paragraph.strip()
        if not stripped:
            lines.append('')
            continue
        lines.extend(simpleSplit(stripped, font_name, font_size, width))
    return lines

def draw_paged_text_box(c, x, top_y, width, header_text, body_text, body_style, bottom_floor, page_height, top_margin):
    header_height = 0.24 * inch
    inner_pad = 0.10 * inch
    body_width = width - inner_pad * 2
    line_gap = 0.02 * inch
    lines = split_text_to_lines(body_text, body_style.fontName, body_style.fontSize, body_width)
    line_height = body_style.leading
    cursor_y = top_y
    idx = 0
    page_index = 0

    while idx < len(lines):
        if cursor_y < bottom_floor + header_height + 0.30 * inch:
            c.showPage()
            cursor_y = page_height - top_margin

        available_body_height = cursor_y - bottom_floor - header_height - 0.14 * inch
        max_lines = int(max(1, available_body_height / (line_height + line_gap)))
        page_lines = lines[idx: idx + max_lines]
        body_height = max(0, len(page_lines) * line_height + max(0, len(page_lines) - 1) * line_gap)
        total_height = header_height + 0.10 * inch + body_height + 0.10 * inch
        draw_header = header_text if page_index == 0 else f'{header_text} (lanjutan)'

        c.setLineWidth(0.8)
        c.rect(x, cursor_y - total_height, width, total_height)
        c.line(x, cursor_y - header_height, x + width, cursor_y - header_height)
        c.setFont('Helvetica-Bold', 11.2)
        c.drawString(x + 0.08 * inch, cursor_y - 0.18 * inch, draw_header)

        body_top = cursor_y - header_height - 0.10 * inch
        text_y = body_top
        for line in page_lines:
            if line:
                c.setFont(body_style.fontName, body_style.fontSize)
                c.drawString(x + inner_pad, text_y - line_height + 2, line)
            text_y -= line_height + line_gap

        cursor_y = cursor_y - total_height - 0.12 * inch
        idx += len(page_lines)
        page_index += 1

        if idx < len(lines):
            c.showPage()
            cursor_y = page_height - top_margin

    return cursor_y

def make_bq_price_cell(val, width, font_size=8.5, is_bold=False):
    if not val or val == 0:
        return ''
    t = Table([['Rp', f'{val:,.0f}']], colWidths=[16, width - 16 - 6])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold' if is_bold else 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t

def generate_bq_pdf_combined(bq):
    """Generate combined BQ PDF with 2 pages: Page 1 (Internal Cost Estimation) and Page 2 (Bill Of Quantity)"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    margin_x = 36  # 0.5 inch
    content_width = page_width - (margin_x * 2)

    styles = getSampleStyleSheet()
    desc_style = ParagraphStyle(
        'BQDescStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=10.5,
        alignment=TA_LEFT
    )

    green_color = colors.HexColor('#00B050')

    # PAGE 1: INTERNAL COST ESTIMATION & PAGE 2: BILL OF QUANTITY
    for page_num, title, is_ice in [(1, 'INTERNAL COST ESTIMATION', True), (2, 'BILL OF QUANTITY', False)]:
        if page_num > 1:
            c.showPage()

        y = page_height - 36  # Top margin

        # 1. Header: Logo & Title
        logo_path = 'static/img/logo_taman_anggrek.png'
        logo_w = 140
        logo_h = 28.8
        if os.path.exists(logo_path):
            c.drawImage(logo_path, page_width - margin_x - logo_w, y - logo_h, width=logo_w, height=logo_h, mask='auto')

        c.setFont('Helvetica-Bold', 14)
        c.drawString(margin_x, y - logo_h + 10, title)

        y -= (logo_h + 14)

        # 2. Project Info Box
        info_data = [
            [Paragraph('<b>Project</b>', desc_style), Paragraph(':', desc_style), Paragraph(escape(bq.project or ''), desc_style)],
            [Paragraph('<b>Kontraktor</b>', desc_style), Paragraph(':', desc_style), Paragraph(escape(bq.kontraktor or '-'), desc_style)],
            [Paragraph('<b>Location</b>', desc_style), Paragraph(':', desc_style), Paragraph(escape(bq.location or ''), desc_style)],
        ]
        info_table = Table(info_data, colWidths=[65, 10, content_width - 75])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BOX', (0, 0), (-1, -1), 0.7, colors.black),
        ]))
        _, info_h = info_table.wrap(content_width, 100)
        info_table.drawOn(c, margin_x, y - info_h)

        y -= (info_h + 12)

        # 3. Items Table
        col_widths = [30, 173.28, 25, 30, 65, 65, 67.5, 67.5]

        table_data = [
            ['NO', 'ITEM', 'QTY', '', 'UNIT PRICE', '', 'TOTAL PRICE', ''],
            ['', '', '', '', 'MATERIAL', 'LABOR', 'MATERIAL', 'LABOR']
        ]

        total_material = 0
        total_labor = 0

        for item in bq.items:
            qty_str = str(int(item.qty)) if item.qty == int(item.qty) else f'{item.qty:g}'
            tot_mat = item.qty * item.material_price
            tot_lab = item.qty * item.labor_price
            total_material += tot_mat
            total_labor += tot_lab

            desc_p = Paragraph(escape(item.item_description or ''), desc_style)

            if is_ice:
                row = [
                    str(item.item_no),
                    desc_p,
                    qty_str,
                    item.unit or '',
                    make_bq_price_cell(item.material_price, col_widths[4]),
                    make_bq_price_cell(item.labor_price, col_widths[5]),
                    make_bq_price_cell(tot_mat, col_widths[6]),
                    make_bq_price_cell(tot_lab, col_widths[7]),
                ]
            else:
                row = [
                    str(item.item_no),
                    desc_p,
                    qty_str,
                    item.unit or '',
                    '',
                    '',
                    '',
                    ''
                ]
            table_data.append(row)

        items_table = Table(table_data, colWidths=col_widths)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 1), green_color),
            ('TEXTCOLOR', (0, 0), (-1, 1), colors.white),
            ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 1), 8.5),
            ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),

            ('SPAN', (0, 0), (0, 1)),
            ('SPAN', (1, 0), (1, 1)),
            ('SPAN', (2, 0), (3, 1)),
            ('SPAN', (4, 0), (5, 0)),
            ('SPAN', (6, 0), (7, 0)),

            ('FONTNAME', (0, 2), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 2), (-1, -1), 8.5),
            ('ALIGN', (0, 2), (0, -1), 'CENTER'),
            ('ALIGN', (1, 2), (1, -1), 'LEFT'),
            ('ALIGN', (2, 2), (3, -1), 'CENTER'),
            ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),

            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]
        items_table.setStyle(TableStyle(t_style))
        _, t_h = items_table.wrap(content_width, 500)
        items_table.drawOn(c, margin_x, y - t_h)

        y -= (t_h + 14)

        # 4. Summary Table
        subtotal = total_material + total_labor
        ppn = subtotal * 0.11
        grand_total = subtotal + ppn

        summary_w = col_widths[4] + col_widths[5] + col_widths[6] + col_widths[7]
        summary_x = page_width - margin_x - summary_w

        if is_ice:
            sum_data = [
                ['Sub Total', 'Rp', f'{subtotal:,.0f}'],
                ['PPN 11%', 'Rp', f'{ppn:,.0f}'],
                ['Grand Total', 'Rp', f'{grand_total:,.0f}'],
            ]
        else:
            sum_data = [
                ['Sub Total', '', ''],
                ['PPN 11%', '', ''],
                ['Grand Total', '', ''],
            ]

        sum_table = Table(sum_data, colWidths=[summary_w - 120, 20, 100])
        sum_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        _, sum_h = sum_table.wrap(summary_w, 100)
        sum_table.drawOn(c, summary_x, y - sum_h)

        y -= (sum_h + 20)

        # 5. Signature Table
        sig_w = 375
        sig_x = margin_x + (content_width - sig_w) / 2
        col_w = sig_w / 3

        name_style = ParagraphStyle(
            'SigName',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=9.5,
            leading=11.5,
            alignment=TA_CENTER
        )
        title_style = ParagraphStyle(
            'SigTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=10.5,
            alignment=TA_CENTER
        )

        def make_sig_content(name, job_title):
            return [
                Spacer(1, 40),
                Paragraph(escape(name or ''), name_style),
                Paragraph(escape(job_title or ''), title_style)
            ]

        sig_data = [
            ['Dibuat Oleh', 'Menyetujui,', 'Mengetahui,'],
            [
                make_sig_content(bq.dibuat_oleh, 'Engineering Ast. Manager'),
                make_sig_content(bq.menyetujui, 'Property Manager'),
                make_sig_content(bq.mengetahui, 'GM Building Management'),
            ],
            ['Tanggal :', 'Tanggal :', 'Tanggal :']
        ]

        sig_table = Table(sig_data, colWidths=[col_w, col_w, col_w], rowHeights=[18, 65, 16])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),

            ('VALIGN', (0, 1), (-1, 1), 'BOTTOM'),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 4),

            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
            ('FONTSIZE', (0, 2), (-1, 2), 8),
            ('ALIGN', (0, 2), (-1, 2), 'LEFT'),
            ('VALIGN', (0, 2), (-1, 2), 'MIDDLE'),
            ('LEFTPADDING', (0, 2), (-1, 2), 3),

            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        _, sig_h = sig_table.wrap(sig_w, 150)
        
        # Check if signature table fits on current page
        if y - sig_h < 48:  # Bottom margin check
            c.showPage()
            y = page_height - 36  # Reset to top of new page
            
        sig_table.drawOn(c, sig_x, y - sig_h)

    c.save()
    buffer.seek(0)
    return buffer

def generate_pdf_content_v2(berita, upload_folder):
    """Generate a layout that follows the reference DOCX more closely."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    margin_x = 0.42 * inch
    top_margin = 0.36 * inch
    content_width = page_width - (margin_x * 2)
    y = page_height - top_margin
    bottom_floor = 0.48 * inch

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=21,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.6,
        leading=12.8,
        alignment=TA_LEFT,
        textColor=colors.black
    )
    body_style_compact = ParagraphStyle(
        'BodyCompact',
        parent=body_style,
        fontSize=9.5,
        leading=11.0
    )
    
    body_style_justified = ParagraphStyle(
        'BodyJustified',
        parent=body_style_compact,
        alignment=TA_JUSTIFY
    )
    caption_style = ParagraphStyle(
        'Caption',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.2,
        leading=9.2,
        alignment=TA_CENTER,
        textColor=colors.black
    )
    
    bold_name_style = ParagraphStyle(
        'BoldName',
        parent=body_style_compact,
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=11.0
    )

    logo_taman_path = next((path for path in [
        'static/img/logo_taman_anggrek.png',
        'static/img/logo_taman_anggrek.jpg',
        'static/img/logo_taman_anggrek.jpeg'
    ] if os.path.exists(path)), None)
    logo_asri_path = next((path for path in [
        'static/img/logo_asri.png',
        'static/img/logo_asri.jpg',
        'static/img/logo_asri.jpeg'
    ] if os.path.exists(path)), None)

    if logo_asri_path:
        draw_fitted_image(c, logo_asri_path, margin_x, y, 0.72 * inch, 0.72 * inch)
    if logo_taman_path:
        draw_fitted_image(c, logo_taman_path, page_width - margin_x - 1.95 * inch, y, 1.95 * inch, 0.72 * inch)

    c.setFont('Helvetica-Bold', 17)
    c.drawCentredString(page_width / 2, y - 0.20 * inch, 'PROPERTY MANAGEMENT')
    c.setFont('Helvetica-Bold', 13.5)
    c.drawCentredString(page_width / 2, y - 0.43 * inch, 'TAMAN ANGGREK RESIDENCES')

    line_y = y - 0.92 * inch
    c.setLineWidth(1)
    c.line(margin_x, line_y, page_width - margin_x, line_y)

    title_y = line_y - 0.28 * inch
    title_para = Paragraph('BERITA ACARA', title_style)
    _, title_h = title_para.wrap(content_width, 100)
    title_para.drawOn(c, margin_x, title_y - title_h)

    number_y = title_y - title_h - 0.06 * inch
    number_para = Paragraph(f'No.  {safe_paragraph_text(berita.nomor)}', subtitle_style)
    _, number_h = number_para.wrap(content_width, 100)
    number_para.drawOn(c, margin_x, number_y - number_h)

    info_y = number_y - number_h - 0.34 * inch
    info_text = (
        f'Pada hari ini {format_indonesian_day_phrase(berita.tanggal)} '
        f'jam {safe_paragraph_text(berita.waktu)} WIB'
    )
    info_para = Paragraph(info_text, body_style)
    _, info_h = info_para.wrap(content_width, 100)
    info_para.drawOn(c, margin_x, info_y - info_h)

    current_y = info_y - info_h - 0.05 * inch
    current_y = draw_two_column_section(
        c,
        margin_x,
        current_y,
        content_width,
        'Lokasi & Uraian Kejadian:',
        'Lokasi',
        berita.lokasi,
        'Uraian Kejadian',
        berita.deskripsi,
        body_style_compact,
        body_style_justified
    ) - 0.14 * inch

    analysis_texts = [t.strip() for t in (berita.analisa or '').split('\n') if t.strip()]
    analysis_header = 'Analisa Masalah / Kronologis:'
    analysis_height = 0.24 * inch + 0.10 * inch
    for text in analysis_texts:
        _, h = wrap_paragraph(text, body_style_justified, content_width - 0.2 * inch)
        analysis_height += h + 0.05 * inch

    c.setLineWidth(0.8)
    c.rect(margin_x, current_y - analysis_height, content_width, analysis_height)
    c.line(margin_x, current_y - 0.24 * inch, margin_x + content_width, current_y - 0.24 * inch)
    c.setFont('Helvetica-Bold', 11.2)
    c.drawString(margin_x + 0.08 * inch, current_y - 0.18 * inch, analysis_header)
    body_y = current_y - 0.24 * inch - 0.10 * inch
    for text in analysis_texts:
        para, h = wrap_paragraph(text, body_style_compact, content_width - 0.20 * inch)
        para.drawOn(c, margin_x + 0.10 * inch, body_y - h)
        body_y -= h + 0.05 * inch
    current_y = current_y - analysis_height - 0.14 * inch

    # Lampiran Foto section
    image_paths = []
    if berita.gambar_paths:
        for img_filename in berita.gambar_paths.split(','):
            img_path = os.path.join(upload_folder, img_filename.strip())
            if os.path.exists(img_path):
                image_paths.append(img_path)
    
    if image_paths:
        photo_header = 'Lampiran Foto:'
        
        # Calculate photo section height for single row layout (same pattern as Analisa Masalah)
        img_h = 1.7 * inch
        photo_height = 0.24 * inch + 0.10 * inch + img_h + 0.10 * inch  # header + padding + image + bottom padding
        
        # Check if photo section fits on current page
        if current_y - photo_height < bottom_floor:
            c.showPage()
            current_y = page_height - top_margin
        
        # Draw box exactly like Analisa Masalah section
        c.setLineWidth(0.8)
        c.rect(margin_x, current_y - photo_height, content_width, photo_height)
        c.line(margin_x, current_y - 0.24 * inch, margin_x + content_width, current_y - 0.24 * inch)
        c.setFont('Helvetica-Bold', 11.2)
        c.drawString(margin_x + 0.08 * inch, current_y - 0.18 * inch, photo_header)
        
        photo_y = current_y - 0.24 * inch - 0.10 * inch
        photo_y = draw_image_gallery(
            c,
            margin_x + 0.10 * inch,
            photo_y,
            content_width - 0.20 * inch,
            image_paths,
            format_indonesian_date(berita.tanggal),
            caption_style,
            bottom_floor,
            page_height,
            top_margin
        )
        
        current_y = current_y - photo_height - 0.14 * inch

    prevention_header = 'Tindakan Pencegahan / Solusi:'
    prevention_text = berita.solusi or ''
    # Add closing sentence
    closing_sentence = "Demikian Berita Acara ini dibuat untuk dipergunakan sebagaimana mestinya, atas perhatian dan kerja samanya diucapkan terima kasih."
    if prevention_text:
        prevention_text = prevention_text + "\n\n" + closing_sentence
    else:
        prevention_text = closing_sentence
    
    current_y = draw_paged_text_box(
        c,
        margin_x,
        current_y,
        content_width,
        prevention_header,
        prevention_text,
        body_style_justified,
        bottom_floor,
        page_height,
        top_margin
    )

    signature_data = [
        ['Dilaporkan oleh', 'Diperiksa oleh,', 'Diketahui oleh,', ''],
        [
            Paragraph('Paraf:<br/><br/><br/><br/><br/><br/>', body_style_compact),
            Paragraph('Paraf:<br/><br/><br/><br/><br/><br/>', body_style_compact),
            Paragraph('Paraf:<br/><br/><br/><br/><br/><br/>', body_style_compact),
            Paragraph('Paraf:<br/><br/><br/><br/><br/><br/>', body_style_compact),
        ],
        [
            Paragraph(f'Nama: <b>{safe_paragraph_text(berita.staff_engineering)}</b>', body_style_compact),
            Paragraph(f'Nama: <b>{safe_paragraph_text(berita.supervisor)}</b>', body_style_compact),
            Paragraph(f'Nama: <b>{safe_paragraph_text(berita.asst_manager)}</b>', body_style_compact),
            Paragraph(f'Nama: <b>{safe_paragraph_text(berita.property_manager)}</b>', body_style_compact),
        ],
        ['Engineering Staff', 'Supervisor', 'Engineering Asst. Manager', 'Property Manager'],
        ['Tanggal:', 'Tanggal:', 'Tanggal:', 'Tanggal:']
    ]
    signature_table = Table(signature_data, colWidths=[
        content_width * 0.25,
        content_width * 0.25,
        content_width * 0.25,
        content_width * 0.25
    ])
    signature_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('LEADING', (0, 0), (-1, -1), 11.5),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('SPAN', (2, 0), (3, 0)),
        ('ALIGN', (2, 0), (3, 0), 'CENTER'),
        ('ALIGN', (0, 2), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.8, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Bold header row
    ]))
    _, sig_h = signature_table.wrap(content_width, 320)
    sig_y = current_y - 0.02 * inch - sig_h
    if sig_y < bottom_floor:
        c.showPage()
        sig_y = page_height - top_margin - sig_h
    signature_table.drawOn(c, margin_x, sig_y)

    c.save()
    buffer.seek(0)
    return buffer

def register_berita_acara_routes(app, db, upload_folder='uploads'):
    """Register all Berita Acara and BQ routes with the Flask app"""
    
    # Create upload folder if it doesn't exist
    os.makedirs(upload_folder, exist_ok=True)
    
    # Import models
    from berita_acara_models import create_models
    BeritaAcara, BQ, BQItem = create_models(db)

    # Berita Acara Routes
    @app.route('/berita_acara')
    def berita_acara_list():
        berita_list = BeritaAcara.query.order_by(BeritaAcara.created_at.desc()).all()
        return render_template('berita_acara_list.html', berita_list=berita_list)

    @app.route('/berita_acara/api/list')
    def berita_acara_api_list():
        """Return berita acara list as JSON for auto-refresh polling."""
        berita_list = BeritaAcara.query.order_by(BeritaAcara.created_at.desc()).all()
        data = [{
            'id': b.id,
            'nomor': b.nomor,
            'tanggal': b.tanggal.strftime('%d/%m/%Y'),
            'lokasi': b.lokasi,
            'deskripsi': b.deskripsi,
            'created_at': b.created_at.isoformat() if b.created_at else ''
        } for b in berita_list]
        return jsonify({'success': True, 'data': data, 'count': len(data), 'max_id': data[0]['id'] if data else 0})

    @app.route('/berita_acara/api/changes')
    def berita_acara_api_changes():
        """Check for changes since given timestamp/id (lightweight poll)."""
        try:
            since_id = int(request.args.get('since_id', 0))
        except (TypeError, ValueError):
            since_id = 0

        new_items = BeritaAcara.query.filter(BeritaAcara.id > since_id) \
            .order_by(BeritaAcara.id.asc()).all()
        total = BeritaAcara.query.count()

        return jsonify({
            'success': True,
            'has_new': len(new_items) > 0,
            'new_count': len(new_items),
            'total': total,
            'max_id': new_items[-1].id if new_items else since_id
        })

    @app.route('/berita_acara/new')
    def berita_acara_new():
        return render_template('berita_acara_form.html')

    @app.route('/berita_acara/<int:id>/edit')
    def berita_acara_edit(id):
        berita = BeritaAcara.query.get_or_404(id)
        return render_template('berita_acara_form.html', berita=berita, edit_mode=True)

    @app.route('/berita_acara/<int:id>/view')
    def berita_acara_detail_view(id):
        berita = BeritaAcara.query.get_or_404(id)
        return render_template('berita_acara_detail.html', berita=berita)

    @app.route('/berita_acara/create', methods=['POST'])
    def berita_acara_create():
        try:
            # Handle multiple file uploads
            gambar_paths = []
            if 'gambar' in request.files:
                files = request.files.getlist('gambar')
                for i, file in enumerate(files):
                    if file and file.filename and file.filename.strip():
                        secure_name = secure_filename(file.filename)
                        filename = f"gambar_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}_{secure_name}"
                        file.save(os.path.join(upload_folder, filename))
                        gambar_paths.append(filename)
            
            # Convert list to comma-separated string for storage
            gambar_paths_str = ','.join(gambar_paths) if gambar_paths else None

            # Parse date
            tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date()

            # Generate complete nomor if not already in complete format
            nomor_input = request.form['nomor']
            if '/BAK-TAR/ENG/' not in nomor_input:
                nomor_lengkap = generate_berita_acara_number(nomor_input, tanggal)
            else:
                nomor_lengkap = nomor_input

            berita = BeritaAcara(
                nomor=nomor_lengkap,
                tanggal=tanggal,
                waktu=request.form['waktu'],
                lokasi=request.form['lokasi'],
                deskripsi=request.form['deskripsi'],
                analisa=request.form['analisa'],
                solusi=request.form['solusi'],
                staff_engineering=request.form['staff_engineering'],
                supervisor=request.form['supervisor'],
                asst_manager=request.form['asst_manager'],
                property_manager=request.form['property_manager'],
                gambar_paths=gambar_paths_str
            )
            db.session.add(berita)
            db.session.commit()
            return redirect('/berita_acara')
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/berita_acara/<int:id>/update', methods=['POST'])
    def berita_acara_update(id):
        try:
            berita = BeritaAcara.query.get_or_404(id)
            
            # Handle file uploads - keep existing images if no new files uploaded
            gambar_paths = []
            if 'gambar' in request.files:
                files = request.files.getlist('gambar')
                # Check if any new files were uploaded
                has_new_files = any(file and file.filename for file in files)
                
                if has_new_files:
                    # Delete old images
                    if berita.gambar_paths:
                        try:
                            old_image_paths = berita.gambar_paths.split(',')
                            for img_filename in old_image_paths:
                                img_path = os.path.join(upload_folder, img_filename.strip())
                                if os.path.exists(img_path):
                                    os.remove(img_path)
                        except:
                            pass
                    
                    # Upload new images
                    for i, file in enumerate(files):
                        if file and file.filename and file.filename.strip():
                            secure_name = secure_filename(file.filename)
                            filename = f"gambar_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}_{secure_name}"
                            file.save(os.path.join(upload_folder, filename))
                            gambar_paths.append(filename)
                    
                    gambar_paths_str = ','.join(gambar_paths) if gambar_paths else None
                else:
                    # Keep existing images
                    gambar_paths_str = berita.gambar_paths
            else:
                # Keep existing images
                gambar_paths_str = berita.gambar_paths

            # Parse date
            tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date()

            # Generate complete nomor if not already in complete format
            nomor_input = request.form['nomor']
            if '/BAK-TAR/ENG/' not in nomor_input:
                nomor_lengkap = generate_berita_acara_number(nomor_input, tanggal)
            else:
                nomor_lengkap = nomor_input

            # Update fields
            berita.nomor = nomor_lengkap
            berita.tanggal = tanggal
            berita.waktu = request.form['waktu']
            berita.lokasi = request.form['lokasi']
            berita.deskripsi = request.form['deskripsi']
            berita.analisa = request.form['analisa']
            berita.solusi = request.form['solusi']
            berita.staff_engineering = request.form['staff_engineering']
            berita.supervisor = request.form['supervisor']
            berita.asst_manager = request.form['asst_manager']
            berita.property_manager = request.form['property_manager']
            berita.gambar_paths = gambar_paths_str
            
            db.session.commit()
            return redirect('/berita_acara')
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/berita_acara/generate_nomor', methods=['POST'])
    def generate_nomor():
        """Generate complete Berita Acara number based on input number and date"""
        try:
            nomor_input = request.form.get('nomor', '')
            tanggal_str = request.form.get('tanggal', '')
            
            if not nomor_input or not tanggal_str:
                return jsonify({'success': False, 'error': 'Nomor dan tanggal diperlukan'})
            
            tanggal = datetime.strptime(tanggal_str, '%Y-%m-%d').date()
            
            # Generate complete number
            nomor_lengkap = generate_berita_acara_number(nomor_input, tanggal)
            
            return jsonify({'success': True, 'nomor_lengkap': nomor_lengkap})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/berita_acara/preview', methods=['POST'])
    def preview_pdf():
        try:
            # Handle multiple file uploads for preview (temp files)
            gambar_paths = []
            if 'gambar' in request.files:
                files = request.files.getlist('gambar')
                for i, file in enumerate(files):
                    if file and file.filename and file.filename.strip():
                        secure_name = secure_filename(file.filename)
                        filename = f"temp_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}_{secure_name}"
                        file.save(os.path.join(upload_folder, filename))
                        gambar_paths.append(filename)
            
            # Convert list to comma-separated string
            gambar_paths_str = ','.join(gambar_paths) if gambar_paths else None

            # Parse date
            tanggal = datetime.strptime(request.form['tanggal'], '%Y-%m-%d').date()

            # Generate complete nomor if not already in complete format
            nomor_input = request.form['nomor']
            if '/BAK-TAR/ENG/' not in nomor_input:
                nomor_lengkap = generate_berita_acara_number(nomor_input, tanggal)
            else:
                nomor_lengkap = nomor_input

            # Create temporary BeritaAcara object for preview
            class TempBeritaAcara:
                def __init__(self):
                    self.nomor = nomor_lengkap
                    self.tanggal = tanggal
                    self.waktu = request.form['waktu']
                    self.lokasi = request.form['lokasi']
                    self.deskripsi = request.form['deskripsi']
                    self.analisa = request.form['analisa']
                    self.solusi = request.form['solusi']
                    self.staff_engineering = request.form['staff_engineering']
                    self.supervisor = request.form['supervisor']
                    self.asst_manager = request.form['asst_manager']
                    self.property_manager = request.form['property_manager']
                    self.gambar_paths = gambar_paths_str

            temp_berita = TempBeritaAcara()
            
            # Generate PDF using the same logic
            buffer = generate_pdf_content_v2(temp_berita, upload_folder)
            
            return send_file(buffer, as_attachment=False, mimetype='application/pdf')
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/berita_acara/<int:id>/pdf')
    def generate_pdf(id):
        berita = BeritaAcara.query.get_or_404(id)
        buffer = generate_pdf_content_v2(berita, upload_folder)
        
        return send_file(buffer, as_attachment=True, 
                         download_name=f'Berita_Acara_{berita.nomor}.pdf',
                         mimetype='application/pdf')

    @app.route('/berita_acara/<int:id>/view_pdf')
    def view_pdf(id):
        berita = BeritaAcara.query.get_or_404(id)
        buffer = generate_pdf_content_v2(berita, upload_folder)
        return send_file(buffer, as_attachment=False, mimetype='application/pdf')

    @app.route('/berita_acara/<int:id>/detail')
    def berita_acara_detail_api(id):
        berita = BeritaAcara.query.get_or_404(id)
        gambar_list = []
        if berita.gambar_paths:
            gambar_list = [img.strip() for img in berita.gambar_paths.split(',') if img.strip()]
        
        return jsonify({
            'success': True,
            'data': {
                'id': berita.id,
                'nomor': berita.nomor,
                'tanggal': berita.tanggal.strftime('%d/%m/%Y'),
                'tanggal_phrase': format_indonesian_day_phrase(berita.tanggal),
                'waktu': berita.waktu,
                'lokasi': berita.lokasi,
                'deskripsi': berita.deskripsi,
                'analisa': berita.analisa,
                'solusi': berita.solusi,
                'staff_engineering': berita.staff_engineering,
                'supervisor': berita.supervisor,
                'asst_manager': berita.asst_manager,
                'property_manager': berita.property_manager,
                'gambar_paths': gambar_list,
                'created_at': berita.created_at.strftime('%d/%m/%Y %H:%M') if berita.created_at else ''
            }
        })

    @app.route('/berita_acara/<int:id>/delete', methods=['POST'])
    def berita_acara_delete(id):
        berita = BeritaAcara.query.get_or_404(id)
        
        # Delete all images if exist
        if berita.gambar_paths:
            try:
                image_paths = berita.gambar_paths.split(',')
                for img_filename in image_paths:
                    img_path = os.path.join(upload_folder, img_filename.strip())
                    if os.path.exists(img_path):
                        os.remove(img_path)
            except:
                pass
        
        db.session.delete(berita)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(upload_folder, filename)

    # BQ Routes
    @app.route('/bq')
    def bq_list():
        bq_list = BQ.query.order_by(BQ.created_at.desc()).all()
        return render_template('bq_list.html', bq_list=bq_list)

    @app.route('/bq/new')
    def bq_new():
        return render_template('bq_form.html')

    @app.route('/bq/<int:id>/edit')
    def bq_edit(id):
        bq = BQ.query.get_or_404(id)
        return render_template('bq_form.html', bq=bq, edit_mode=True)

    @app.route('/bq/<int:id>/view')
    def bq_detail_view(id):
        bq = BQ.query.get_or_404(id)
        return render_template('bq_detail.html', bq=bq)

    @app.route('/bq/create', methods=['POST'])
    def bq_create():
        try:
            # Create BQ record
            bq = BQ(
                nomor=request.form['nomor'],
                project=request.form['project'],
                kontraktor=request.form['kontraktor'],
                location=request.form['location'],
                dibuat_oleh=request.form['dibuat_oleh'],
                menyetujui=request.form['menyetujui'],
                mengetahui=request.form['mengetahui']
            )
            db.session.add(bq)
            db.session.commit()
            
            # Add items
            item_nos = request.form.getlist('item_no[]')
            item_descriptions = request.form.getlist('item_description[]')
            item_qtys = request.form.getlist('item_qty[]')
            item_units = request.form.getlist('item_unit[]')
            item_material_prices = request.form.getlist('item_material_price[]')
            item_labor_prices = request.form.getlist('item_labor_price[]')
            
            for i in range(len(item_nos)):
                if item_descriptions[i]:  # Only add if description is provided
                    item = BQItem(
                        bq_id=bq.id,
                        item_no=item_nos[i],
                        item_description=item_descriptions[i],
                        qty=float(item_qtys[i]) if item_qtys[i] else 0,
                        unit=item_units[i],
                        material_price=float(item_material_prices[i]) if item_material_prices[i] else 0,
                        labor_price=float(item_labor_prices[i]) if item_labor_prices[i] else 0
                    )
                    db.session.add(item)
            
            db.session.commit()
            
            # Generate combined PDF with 2 pages
            buffer_combined = generate_bq_pdf_combined(bq)
            
            # Save PDF
            pdf_dir = 'bq_pdfs'
            os.makedirs(pdf_dir, exist_ok=True)
            
            pdf_filename = f"BQ_{bq.nomor.replace('/', '_')}.pdf"
            
            with open(os.path.join(pdf_dir, pdf_filename), 'wb') as f:
                f.write(buffer_combined.getvalue())
            
            return jsonify({'success': True, 'id': bq.id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/bq/<int:id>/update', methods=['POST'])
    def bq_update(id):
        try:
            bq = BQ.query.get_or_404(id)
            
            # Update BQ fields
            bq.nomor = request.form['nomor']
            bq.project = request.form['project']
            bq.kontraktor = request.form['kontraktor']
            bq.location = request.form['location']
            bq.dibuat_oleh = request.form['dibuat_oleh']
            bq.menyetujui = request.form['menyetujui']
            bq.mengetahui = request.form['mengetahui']
            
            # Delete existing items
            BQItem.query.filter_by(bq_id=bq.id).delete()
            
            # Add new items
            item_nos = request.form.getlist('item_no[]')
            item_descriptions = request.form.getlist('item_description[]')
            item_qtys = request.form.getlist('item_qty[]')
            item_units = request.form.getlist('item_unit[]')
            item_material_prices = request.form.getlist('item_material_price[]')
            item_labor_prices = request.form.getlist('item_labor_price[]')
            
            for i in range(len(item_nos)):
                if item_descriptions[i]:  # Only add if description is provided
                    item = BQItem(
                        bq_id=bq.id,
                        item_no=item_nos[i],
                        item_description=item_descriptions[i],
                        qty=float(item_qtys[i]) if item_qtys[i] else 0,
                        unit=item_units[i],
                        material_price=float(item_material_prices[i]) if item_material_prices[i] else 0,
                        labor_price=float(item_labor_prices[i]) if item_labor_prices[i] else 0
                    )
                    db.session.add(item)
            
            db.session.commit()
            
            # Generate combined PDF with 2 pages
            buffer_combined = generate_bq_pdf_combined(bq)
            
            # Save PDF
            pdf_dir = 'bq_pdfs'
            os.makedirs(pdf_dir, exist_ok=True)
            
            pdf_filename = f"BQ_{bq.nomor.replace('/', '_')}.pdf"
            
            with open(os.path.join(pdf_dir, pdf_filename), 'wb') as f:
                f.write(buffer_combined.getvalue())
            
            return jsonify({'success': True, 'id': bq.id})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/bq/preview', methods=['POST'])
    def bq_preview():
        try:
            # Create temporary BQ object for preview
            class TempBQ:
                def __init__(self):
                    self.nomor = request.form['nomor']
                    self.project = request.form['project']
                    self.kontraktor = request.form['kontraktor']
                    self.location = request.form['location']
                    self.dibuat_oleh = request.form['dibuat_oleh']
                    self.menyetujui = request.form['menyetujui']
                    self.mengetahui = request.form['mengetahui']
                    self.items = []
            
            temp_bq = TempBQ()
            
            # Add items
            item_nos = request.form.getlist('item_no[]')
            item_descriptions = request.form.getlist('item_description[]')
            item_qtys = request.form.getlist('item_qty[]')
            item_units = request.form.getlist('item_unit[]')
            item_material_prices = request.form.getlist('item_material_price[]')
            item_labor_prices = request.form.getlist('item_labor_price[]')
            
            for i in range(len(item_nos)):
                if item_descriptions[i]:
                    class TempItem:
                        def __init__(self, item_no, item_description, qty, unit, material_price, labor_price):
                            self.item_no = item_no
                            self.item_description = item_description
                            self.qty = qty
                            self.unit = unit
                            self.material_price = material_price
                            self.labor_price = labor_price
                    
                    item = TempItem(
                        item_nos[i],
                        item_descriptions[i],
                        float(item_qtys[i]) if item_qtys[i] else 0,
                        item_units[i],
                        float(item_material_prices[i]) if item_material_prices[i] else 0,
                        float(item_labor_prices[i]) if item_labor_prices[i] else 0
                    )
                    temp_bq.items.append(item)
            
            # Generate combined PDF with 2 pages
            buffer = generate_bq_pdf_combined(temp_bq)
            
            return send_file(buffer, as_attachment=False, mimetype='application/pdf')
            
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/bq/<int:id>/pdf')
    def generate_bq_pdf_with_cost(id):
        bq = BQ.query.get_or_404(id)
        buffer = generate_bq_pdf_combined(bq)
        
        return send_file(buffer, as_attachment=True, 
                         download_name=f'BQ_{bq.nomor.replace("/", "_")}.pdf',
                         mimetype='application/pdf')

    @app.route('/bq/<int:id>/view_pdf')
    def view_bq_pdf(id):
        bq = BQ.query.get_or_404(id)
        buffer = generate_bq_pdf_combined(bq)
        return send_file(buffer, as_attachment=False, mimetype='application/pdf')

    @app.route('/bq/<int:id>/detail')
    def bq_detail_api(id):
        bq = BQ.query.get_or_404(id)
        items_data = []
        for item in bq.items:
            tot_mat = item.qty * (item.material_price or 0)
            tot_lab = item.qty * (item.labor_price or 0)
            tot_item = tot_mat + tot_lab
            items_data.append({
                'item_no': item.item_no,
                'item_description': item.item_description,
                'qty': item.qty,
                'unit': item.unit,
                'material_price': item.material_price or 0,
                'labor_price': item.labor_price or 0,
                'total_material': tot_mat,
                'total_labor': tot_lab,
                'total_price': tot_item
            })
        
        return jsonify({
            'success': True,
            'data': {
                'id': bq.id,
                'nomor': bq.nomor,
                'project': bq.project,
                'kontraktor': bq.kontraktor,
                'location': bq.location,
                'dibuat_oleh': bq.dibuat_oleh,
                'menyetujui': bq.menyetujui,
                'mengetahui': bq.mengetahui,
                'created_at': bq.created_at.strftime('%d/%m/%Y %H:%M') if bq.created_at else '',
                'items': items_data,
                'subtotal': bq.subtotal,
                'ppn': bq.ppn,
                'grand_total': bq.grand_total
            }
        })

    @app.route('/bq/<int:id>/delete', methods=['POST'])
    def bq_delete(id):
        bq = BQ.query.get_or_404(id)
        db.session.delete(bq)
        db.session.commit()
        return jsonify({'success': True})