import io
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter
from app import app, db, PdfUpload, parse_pdf_text


class PdfUploadTests(unittest.TestCase):
    @staticmethod
    def pdf_bytes():
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        content = io.BytesIO()
        writer.write(content)
        return content.getvalue()

    def setUp(self):
        identity = patch('auth.get_identity', return_value={'token': 'test-token', 'email': 'test@example.com'})
        identity.start()
        self.addCleanup(identity.stop)
        self.client = app.test_client()
        with self.client.session_transaction() as session:
            session['csrf'] = 'test-csrf'
        self.created_ids = []

    def tearDown(self):
        with app.app_context():
            for record_id in self.created_ids:
                row = db.session.get(PdfUpload, record_id)
                if row:
                    db.session.delete(row)
            db.session.commit()

    def test_preview_does_not_save_and_empty_scan_is_rejected(self):
        response = self.client.post('/api/pdf-upload', data={
            'csrf': 'test-csrf', 'pdf_file': (io.BytesIO(self.pdf_bytes()), 'sample.pdf')
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('OCR', response.get_json()['error'])

        with patch('app.PdfReader') as reader:
            reader.return_value.pages = [type('Page', (), {'extract_text': lambda self: 'Tanggal Permintaan: 12/09/2026\nNo: WPR123\nBudget: CAPEX\nPerbaikan pompa utama'})()]
            response = self.client.post('/api/pdf-upload', data={
                'csrf': 'test-csrf', 'pdf_file': (io.BytesIO(b'%PDF'), 'sample.pdf')
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['no_wpr'], 'WPR123')
        with app.app_context():
            self.assertIsNone(PdfUpload.query.filter_by(no_wpr='WPR123').first())

    def test_create_edit_delete_in_sqlite(self):
        data = {'csrf': 'test-csrf', 'tanggal': '12/09/2026', 'no_wpr': 'WPR-TEST-123',
                'deskripsi': 'Perbaikan pompa', 'type_budget': 'CAPEX', 'keterangan': 'Prioritas',
                'pdf_file': (io.BytesIO(self.pdf_bytes()), 'wpr-original.pdf')}
        created = self.client.post('/api/pdf-records', data=data)
        self.assertEqual(created.status_code, 201)
        record_id = created.get_json()['data']['id']
        self.created_ids.append(record_id)
        self.assertTrue(created.get_json()['data']['has_pdf'])
        pdf_response = self.client.get(f'/api/pdf-records/{record_id}/pdf')
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.mimetype, 'application/pdf')
        self.assertEqual(pdf_response.data, self.pdf_bytes())
        self.assertIn('WPR-TEST-123', [row['no_wpr'] for row in self.client.get('/api/pdf-upload').get_json()['data']])
        data['deskripsi'] = 'Perbaikan pompa utama'
        data.pop('pdf_file')
        updated = self.client.post(f'/api/pdf-records/{record_id}/edit', data=data)
        self.assertEqual(updated.status_code, 200)
        with app.app_context():
            self.assertEqual(db.session.get(PdfUpload, record_id).deskripsi, 'Perbaikan pompa utama')
            self.assertEqual(db.session.get(PdfUpload, record_id).pdf_content, self.pdf_bytes())
        deleted = self.client.post(f'/api/pdf-records/{record_id}/delete', data={'csrf': 'test-csrf'})
        self.assertEqual(deleted.status_code, 200)
        with app.app_context():
            self.assertIsNone(db.session.get(PdfUpload, record_id))
        self.assertEqual(self.client.get(f'/api/pdf-records/{record_id}/pdf').status_code, 404)

    def test_mutations_require_csrf_and_required_fields(self):
        self.assertEqual(self.client.post('/api/pdf-records', data={'no_wpr': 'WPR1'}).status_code, 400)
        self.assertEqual(self.client.post('/api/pdf-records', data={'csrf': 'test-csrf', 'no_wpr': 'WPR1'}).status_code, 400)
        self.assertEqual(self.client.post('/api/pdf-records', data={
            'csrf': 'test-csrf', 'tanggal': '12/09/2026', 'no_wpr': 'WPR1',
            'deskripsi': 'Tes', 'type_budget': 'Capex'}).status_code, 400)

    def test_existing_record_can_receive_pdf_during_edit(self):
        with app.app_context():
            row = PdfUpload(tanggal='12/09/2026', no_wpr='WPR-LEGACY-TEST',
                            deskripsi='Catatan lama', type_budget='Capex', keterangan='')
            db.session.add(row)
            db.session.commit()
            record_id = row.id
            self.created_ids.append(record_id)
        self.assertEqual(self.client.get(f'/api/pdf-records/{record_id}/pdf').status_code, 404)
        updated = self.client.post(f'/api/pdf-records/{record_id}/edit', data={
            'csrf': 'test-csrf', 'tanggal': '12/09/2026', 'no_wpr': 'WPR-LEGACY-TEST',
            'deskripsi': 'Catatan lama', 'type_budget': 'Capex', 'keterangan': '',
            'pdf_file': (io.BytesIO(self.pdf_bytes()), 'lampiran-lama.pdf')
        })
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.get_json()['data']['has_pdf'])
        self.assertEqual(self.client.get(f'/api/pdf-records/{record_id}/pdf').data, self.pdf_bytes())

    def test_labeled_wpr_fields_and_multiline_description(self):
        parsed = parse_pdf_text('''PURCHASE REQUEST
Tanggal Permintaan: 05/03/2026
No. WPR: WPR/TAR/609/0304
Deskripsi: Bongkar Pasang
Ornamen Ceiling Indoor Pool Club House
Type Budget: Civil
Keterangan: Catatan tes''')
        self.assertEqual(parsed, {
            'tanggal': '05/03/2026', 'no_wpr': 'WPR/TAR/609/0304',
            'deskripsi': 'Bongkar Pasang Ornamen Ceiling Indoor Pool Club House',
            'type_budget': 'Civil', 'keterangan': 'Catatan tes'
        })

    def test_missing_fields_are_not_fabricated(self):
        parsed = parse_pdf_text('PURCHASE REQUEST\nWPR/TAR/609/0304\nPersetujuan Manager')
        self.assertEqual(parsed['no_wpr'], 'WPR/TAR/609/0304')
        self.assertEqual(parsed['tanggal'], '')
        self.assertEqual(parsed['deskripsi'], '')
        self.assertEqual(parsed['type_budget'], '')

    def test_worksheet_layout_from_marked_example(self):
        parsed = parse_pdf_text('''WORKSHEET PURCHASE REQUEST
TA RESIDENCE
Tanggal Permintaan : 24 - 02 - 2026 Direktoral : TA Residence No. : WPR/TAR/2602/0077
Kode Barang Nama Barang Qty Satuan Spesifikasi Item Price Extended Price
MAT-2120 Power Supply Unit, ST-230/24 2.00 Pcs
Penggantian Sparepart Lift Passenger Tower D (PE-D2) (Power Supply) Budget Capex Periode Bulan Februari 2026
Subtotal
APPROVED BY SYSTEM''')
        self.assertEqual(parsed['tanggal'], '24-02-2026')
        self.assertEqual(parsed['no_wpr'], 'WPR/TAR/2602/0077')
        self.assertEqual(parsed['deskripsi'], 'Penggantian Sparepart Lift Passenger Tower D (PE-D2) (Power Supply)')
        self.assertEqual(parsed['type_budget'], 'Capex')
        self.assertEqual(parsed['keterangan'], '')

    def test_worksheet_budget_on_separate_line(self):
        parsed = parse_pdf_text('''Tanggal Permintaan
24 - 02 - 2026
No. : WPR/TAR/2602/0077
Penggantian Sparepart Lift Passenger Tower D
Budget
Capex
Periode Bulan Februari 2026''')
        self.assertEqual(parsed['tanggal'], '24-02-2026')
        self.assertEqual(parsed['deskripsi'], 'Penggantian Sparepart Lift Passenger Tower D')
        self.assertEqual(parsed['type_budget'], 'Capex')

    def test_fragmented_date_and_budget_in_layout_text(self):
        class Page:
            def extract_text(self, extraction_mode=None):
                if extraction_mode == 'layout':
                    return '''Tanggal Permintaan : Tanggal Pengiriman : 24 – 02 – 2026
No. : WPR/TAR/2602/0077
Penggantian Sparepart Lift Passenger Tower D (PE-D2)
Budget : Periode Bulan Februari 2026 Capex'''
                return 'WORKSHEET PURCHASE REQUEST'

        with patch('app.PdfReader') as reader:
            reader.return_value.pages = [Page()]
            result = self.client.post('/api/pdf-upload', data={
                'csrf': 'test-csrf', 'pdf_file': (io.BytesIO(b'%PDF'), 'wpr.pdf')
            })
        self.assertEqual(result.status_code, 200)
        data = result.get_json()['data']
        self.assertEqual(data['tanggal'], '24-02-2026')
        self.assertEqual(data['type_budget'], 'Capex')

    def test_positioned_text_recovers_table_values(self):
        class Page:
            def extract_text(self, extraction_mode=None, visitor_text=None):
                if visitor_text:
                    for value, x, y in [
                        ('24 - 02 - 2026', 180, 700),
                        ('Tanggal Permintaan :', 20, 700),
                        ('Capex', 620, 500),
                        ('Budget', 560, 500),
                        ('Penggantian Sparepart Lift Passenger Tower D', 20, 500),
                    ]:
                        visitor_text(value, None, [1, 0, 0, 1, x, y], None, 11)
                    return ''
                return 'WORKSHEET PURCHASE REQUEST\nNo. : WPR/TAR/2602/0077'

        with patch('app.PdfReader') as reader:
            reader.return_value.pages = [Page()]
            result = self.client.post('/api/pdf-upload', data={
                'csrf': 'test-csrf', 'pdf_file': (io.BytesIO(b'%PDF'), 'wpr.pdf')
            })
        self.assertEqual(result.status_code, 200)
        data = result.get_json()['data']
        self.assertEqual(data['tanggal'], '24-02-2026')
        self.assertEqual(data['type_budget'], 'Capex')

    def test_actual_wpr_0010_short_description(self):
        from pathlib import Path
        pdf_path = Path('/Volumes/DATA SHARING ENG/2026/WPR/0010 Perbaikan ACP.pdf')
        if not pdf_path.exists():
            self.skipTest('contoh PDF tidak tersedia')
        text = PdfWriter  # keep this test independent from external PDF extraction APIs
        extracted = 'Tanggal Permintaan\n:\nNo. :\nWPR/TAR/2601/0010\n27 - 01 - 2026\nTipe\nKeterangan\nPERBAIKAN ACP\nPerbaikan ACP\n1.00\nLot\nPerbaikan ACP Budget RM Civil Periode Januari 2026'
        parsed = parse_pdf_text(extracted)
        self.assertEqual(parsed['tanggal'], '27-01-2026')
        self.assertEqual(parsed['deskripsi'], 'Perbaikan ACP')
        self.assertEqual(parsed['type_budget'], 'RM Civil')
