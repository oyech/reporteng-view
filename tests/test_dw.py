import io
import os
import unittest
from datetime import date
from unittest.mock import Mock, patch

from openpyxl import load_workbook
from app import app, fetch_reports, normalize_report


def dw_row():
    return dict(id='dw1', title='Tower B', created_at='2026-09-10T09:00:00Z',
                created_date='2026-09-10T09:00:00Z', pic='Teknisi DW',
                report_items=[dict(job='Perbaikan shower', location='B-01',
                                   status='ProgressStatus.done',
                                   imagePaths=['https://example.com/dw.jpg'])])


class DWTests(unittest.TestCase):
    def test_postgres_fractional_timestamp_on_python39(self):
        row = dw_row()
        row['created_at'] = '2026-09-10T09:46:18.74061+00:00'
        self.assertEqual(normalize_report(row)[0]['tanggal'], '2026-09-10T16:46:18.740610+07:00')

    def setUp(self):
        self.env = patch.dict(os.environ, {
            'DW_SUPABASE_URL': 'https://dw.example', 'DW_SUPABASE_KEY': 'dw-anon',
            'DW_SUPABASE_TABLE': 'daily_reports', 'SUPABASE_URL': 'https://eng.example',
            'SUPABASE_KEY': 'eng-key', 'SUPABASE_TABLE': 'report_eng'})
        self.env.start()
        self.addCleanup(self.env.stop)
        identity = patch('auth.get_identity', return_value={'token': 'eng-user-token', 'email': 'test@example.com'})
        identity.start()
        self.addCleanup(identity.stop)
        self.client = app.test_client()

    def responses(self, get):
        get.side_effect = [Mock(status_code=200, ok=True, json=lambda: [dw_row()]),
                           Mock(status_code=200, ok=True, json=lambda: [])]

    @patch('app.requests.get')
    def test_dw_isolation_mapping_pagination_and_period(self, get):
        self.responses(get)
        rows = fetch_reports(date(2026, 9, 10), date(2026, 9, 10), 'eng-user-token', source='dw')
        args = get.call_args_list[0]
        self.assertEqual(args.args[0], 'https://dw.example/rest/v1/daily_reports')
        self.assertEqual(args.kwargs['headers']['Authorization'], 'Bearer dw-anon')
        self.assertEqual(args.kwargs['headers']['apikey'], 'dw-anon')
        self.assertIn(('created_at', 'gte.2026-09-09T17:00:00+00:00'), args.kwargs['params'])
        self.assertIn(('created_at', 'lt.2026-09-10T17:00:00+00:00'), args.kwargs['params'])
        self.assertIn(('offset', '1'), get.call_args_list[1].kwargs['params'])
        self.assertEqual(rows[0]['area_kerja'], 'Tower B')
        self.assertEqual(rows[0]['unit_area'], 'B-01')
        self.assertEqual(rows[0]['status'], 'done')
        self.assertEqual(rows[0]['foto'], ['https://example.com/dw.jpg'])

    @patch('app.requests.get')
    def test_engineering_keeps_its_credentials(self, get):
        get.return_value = Mock(status_code=200, ok=True, json=lambda: [])
        fetch_reports(None, None, 'eng-user-token')
        self.assertEqual(get.call_args.args[0], 'https://eng.example/rest/v1/report_eng')
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bearer eng-user-token')
        self.assertEqual(get.call_args.kwargs['headers']['apikey'], 'eng-key')

    @patch('app.requests.get')
    def test_filter_and_export_use_dw(self, get):
        self.responses(get)
        result = self.client.get('/api/dw/reports?q=shower&area_kerja=Tower+B')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['total'], 1)
        self.responses(get)
        result = self.client.get('/laporan-dw/export?q=shower')
        self.assertEqual(result.status_code, 200)
        self.assertIn('laporan_dw_', result.headers['Content-Disposition'])
        book = load_workbook(io.BytesIO(result.data))
        self.assertEqual(book.active.title, 'Laporan DW')
        self.assertEqual(book.active['D2'].value, 'Perbaikan shower')
        self.assertEqual(book.active['G2'].hyperlink.target, 'https://example.com/dw.jpg')
        self.assertEqual(get.call_args.args[0], 'https://dw.example/rest/v1/daily_reports')

    def test_page_and_login(self):
        dw = self.client.get('/laporan-dw')
        self.assertEqual(dw.status_code, 200)
        self.assertIn(b'<h1>Laporan DW<span>', dw.data)
        self.assertIn(b'data-reports-url="/api/dw/reports"', dw.data)
        self.assertNotIn(b'dw-anon', dw.data)
        eng = self.client.get('/')
        self.assertIn(b'data-reports-url="/api/reports"', eng.data)
        self.assertIn(b'<h1>Laporan Pekerjaan Engineering<span>', eng.data)
        with patch('auth.get_identity', return_value=None):
            self.assertEqual(self.client.get('/laporan-dw').status_code, 302)
            self.assertEqual(self.client.get('/api/dw/reports').status_code, 401)
            self.assertEqual(self.client.get('/laporan-dw/export').status_code, 401)

    @patch('app.requests.get')
    def test_configuration_and_access_errors(self, get):
        with patch.dict(os.environ, {'DW_SUPABASE_TABLE': ''}):
            result = self.client.get('/api/dw/reports')
            self.assertEqual(result.status_code, 503)
            self.assertIn('DW_SUPABASE_TABLE', result.json['error'])
            get.assert_not_called()
        get.return_value = Mock(status_code=403)
        result = self.client.get('/api/dw/reports')
        self.assertEqual(result.status_code, 403)
        self.assertIn('Supabase DW', result.json['error'])
