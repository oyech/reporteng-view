import unittest
from unittest.mock import patch
from app import app
from item_catalog import catalog, search_items


class ItemCatalogTests(unittest.TestCase):
    def test_source_and_deduplication(self):
        rows, source_count, codes = catalog()
        self.assertEqual((source_count, codes, len(rows)), (8486, 2337, 2356))
        self.assertEqual(sum(row['occurrences'] for row in rows), source_count)
        variants = search_items('SMGS99-0001')['items']
        self.assertEqual(len(variants), 2)
        self.assertTrue(all(row['variants'] == 2 for row in variants))

    def test_catalog_compatible_with_windows_encoding(self):
        import json
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / 'data' / 'items.json'
        windows = json.loads(path.read_text(encoding='cp1252'))
        utf8 = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(windows, utf8)
        self.assertTrue(any('Ø' in row['name'] for row in utf8['items']))

    def test_search_and_pagination(self):
        result = search_items('skf bearing')
        self.assertGreater(result['total'], 0)
        self.assertTrue(all('skf' in r['name'].lower() and 'bearing' in r['name'].lower() for r in result['items']))
        self.assertEqual(search_items('wmap00-0001')['items'][0]['code'], 'WMAP00-0001')
        self.assertEqual(search_items('no-such-engineering-material-xyz')['total'], 0)
        self.assertEqual(search_items('', -1)['page'], 1)
        end = search_items('', 999999)
        self.assertEqual(end['page'], end['pages'])

    def test_access_requires_login(self):
        with patch('auth.get_identity', return_value=None):
            response = app.test_client().get('/kode-item')
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.location)

    def test_render_search_and_escape(self):
        with patch('auth.get_identity', return_value={'email': 'test@example.com', 'token': 'test'}):
            client = app.test_client()
            response = client.get('/kode-item?q=WMAP00-0001')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'thermometer htc-1 h595 putih', response.data)
            self.assertIn(b'Salin kode', response.data)
            self.assertEqual(client.get('/kode-item?page=invalid').status_code, 200)
            response = client.get('/kode-item', query_string={'q': '<script>alert(1)</script>'})
            self.assertNotIn(b'<script>alert(1)</script>', response.data)
            self.assertIn(b'Barang tidak ditemukan', response.data)
