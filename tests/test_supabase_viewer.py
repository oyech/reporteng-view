import os
import unittest
from unittest.mock import Mock, patch

import requests
from app import app
from supabase_viewer import ViewerError, fetch_table


class SupabaseViewerTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'TABLE_SUPABASE_URL': 'https://example.supabase.co',
                                     'TABLE_SUPABASE_KEY': 'test-anon-key', 'TABLE_SUPABASE_TABLES': ''})
        env.start()
        self.addCleanup(env.stop)

    def test_login_required(self):
        with patch('auth.get_identity', return_value=None), patch('supabase_viewer.requests.get') as get:
            self.assertEqual(app.test_client().get('/tabel-supabase').status_code, 302)
            get.assert_not_called()

    @patch('auth.get_identity', return_value={'email': 'test@example.com'})
    def test_render_pagination_and_escape(self, identity):
        response = Mock(ok=True, status_code=200, headers={'Content-Range': '50-50/101'})
        response.json.return_value = [{'id': 1, 'name': '<script>alert(1)</script>', 'meta': {'x': '<img>'}, 'enabled': False, 'empty': None}]
        with patch('supabase_viewer.requests.get', return_value=response) as get:
            result = app.test_client().get('/tabel-supabase?table=example&page=2')
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'Berikutnya', result.data)
            self.assertIn(b'51', result.data)
            self.assertNotIn(b'<script>alert(1)</script>', result.data)
            self.assertIn(b'&lt;script&gt;', result.data)
            self.assertIn(b'false', result.data)
            self.assertEqual(get.call_args.kwargs['params']['offset'], 50)
            self.assertNotIn(get.call_args.kwargs['headers']['apikey'].encode(), result.data)

    @patch('auth.get_identity', return_value={'email': 'test@example.com'})
    def test_empty_initial_page_and_invalid_input(self, identity):
        with patch('supabase_viewer.requests.get') as get:
            self.assertIn(b'Pilih tabel untuk mulai', app.test_client().get('/tabel-supabase').data)
            self.assertIn(b'Nama tabel harus', app.test_client().get('/tabel-supabase?table=../rpc/x').data)
            get.assert_not_called()

    def test_upstream_errors(self):
        for code in [401, 403, 404, 500]:
            with self.subTest(code=code), patch('supabase_viewer.requests.get', return_value=Mock(status_code=code, ok=False)):
                with self.assertRaises(ViewerError):
                    fetch_table('example', 1)
        with patch('supabase_viewer.requests.get', side_effect=requests.Timeout):
            with self.assertRaises(ViewerError):
                fetch_table('example', 1)

    @patch('auth.get_identity', return_value={'email': 'test@example.com'})
    def test_empty_and_invalid_page(self, identity):
        response = Mock(ok=True, status_code=200, headers={'Content-Range': '*/0'})
        response.json.return_value = []
        with patch('supabase_viewer.requests.get', return_value=response) as get:
            result = app.test_client().get('/tabel-supabase?table=example&page=invalid')
            self.assertIn(b'Tidak ada data', result.data)
            self.assertNotIn(b'Berikutnya', result.data)
            self.assertEqual(get.call_args.kwargs['params']['offset'], 0)

    @patch('auth.get_identity', return_value={'email': 'test@example.com'})
    def test_logsheet_items_selection_filters_and_values(self, identity):
        rows = [
            {'log_key': 'a', 'log_date': '2026-09-12', 'shift': '1',
             'payload': {'Petugas 1': 'Operator A', 'Shift': '1', 'Tanggal': '2026-09-12',
                         'GWT - Kapasitas': None, 'GWT - Kondisi': 'Baik',
                         'KWH - Meter': 0, 'Pompa - Aktif': False,
                         'Panel - Catatan': '<script>alert(1)</script>'}},
            {'log_key': 'b', 'log_date': '2026-09-11', 'shift': '2',
             'payload': {'STP - Blower': 'Auto'}},
        ]
        with patch('supabase_viewer.fetch_table', return_value=(rows, 2)):
            client = app.test_client()
            result = client.get('/tabel-supabase?table=logsheets')
            self.assertEqual(result.status_code, 200)
            self.assertIn(b'Item pemeriksaan', result.data)
            self.assertIn(b'Operator A', result.data)
            self.assertIn(b'Belum diisi', result.data)
            self.assertIn(b'&lt;script&gt;', result.data)
            self.assertNotIn(b'<script>alert(1)</script>', result.data)
            self.assertNotIn(b'Lihat rincian', result.data)
            filtered = client.get('/tabel-supabase?table=logsheets&group=GWT&filled=1')
            self.assertIn(b'Kondisi', filtered.data)
            self.assertNotIn(b'Kapasitas', filtered.data)
            selected = client.get('/tabel-supabase?table=logsheets&log=b&q=blower')
            self.assertIn(b'Auto', selected.data)
            self.assertNotIn(b'Operator A', selected.data)
            self.assertIn(b'Item tidak ditemukan', client.get('/tabel-supabase?table=logsheets&q=nonexistent').data)
        from supabase_viewer import logsheet_context
        context = logsheet_context(rows, {})
        self.assertEqual(context['item_count'], 5)
        self.assertEqual(context['filled_count'], 4)
        self.assertEqual(logsheet_context(rows, {'log': 'missing'})['selected_log'], rows[0])
        self.assertFalse(logsheet_context([{'payload': None}], {})['payload_valid'])
