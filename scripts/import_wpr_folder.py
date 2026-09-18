import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyPDF2 import PdfReader, PdfWriter
from app import app, db, PdfUpload, PDF_FIELDS, parse_pdf_text, positioned_pdf_text


def extract_wpr(path):
    content = path.read_bytes()
    reader = PdfReader(io.BytesIO(content))
    pages = [(page, page.extract_text() or '') for page in reader.pages]
    worksheet = [(page, text) for page, text in pages if 'WORKSHEET PURCHASE REQUEST' in text.upper()]
    selected = worksheet[:1] if worksheet else pages[:1]
    plain = '\n'.join(text for _, text in selected)
    try:
        layout = '\n'.join(page.extract_text(extraction_mode='layout') or '' for page, _ in selected)
    except (TypeError, ValueError):
        layout = ''
    positioned = '\n'.join(positioned_pdf_text(page) for page, _ in selected)
    data = parse_pdf_text(layout)
    for alternative in (parse_pdf_text(plain), parse_pdf_text(positioned)):
        for field in PDF_FIELDS:
            if field != 'status' and not data.get(field):
                data[field] = alternative.get(field, '')
    return data, content


def compress_pdf(content):
    try:
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()
        for page in reader.pages:
            page.compress_content_streams()
            writer.add_page(page)
        output = io.BytesIO()
        writer.write(output)
        return output.getvalue() if output.tell() < len(content) else content
    except Exception:
        return content


def main(folder):
    added = updated = skipped = failed = 0
    with app.app_context():
        existing = {row.no_wpr.strip().upper(): row for row in PdfUpload.query.all()}
        for path in sorted(folder.glob('*.pdf')):
            try:
                data, content = extract_wpr(path)
                required = ('tanggal', 'no_wpr', 'deskripsi', 'type_budget')
                missing = [field for field in required if not data.get(field)]
                if missing:
                    print(f'SKIP {path.name}: missing {", ".join(missing)}')
                    skipped += 1
                    continue
                key = data['no_wpr'].strip().upper()
                row = existing.get(key)
                if row:
                    changed = False
                    for field in required:
                        if not getattr(row, field, None):
                            setattr(row, field, data[field]); changed = True
                    if not row.pdf_content:
                        row.pdf_filename = path.name
                        row.pdf_content = compress_pdf(content)
                        changed = True
                    updated += int(changed)
                    skipped += int(not changed)
                else:
                    row = PdfUpload(tanggal=data['tanggal'], no_wpr=data['no_wpr'],
                                    deskripsi=data['deskripsi'], type_budget=data['type_budget'],
                                    status='', keterangan='', pdf_filename=path.name,
                                    pdf_content=compress_pdf(content))
                    db.session.add(row)
                    existing[key] = row
                    added += 1
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                print(f'ERROR {path.name}: {exc}')
                failed += 1
        print(f'added={added} updated={updated} skipped={skipped} failed={failed} total={PdfUpload.query.count()}')


if __name__ == '__main__':
    main(Path(sys.argv[1] if len(sys.argv) > 1 else '/Volumes/DATA SHARING ENG/2026/WPR'))
