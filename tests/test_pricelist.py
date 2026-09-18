import unittest
from unittest.mock import patch

from app import app
from pricelist_catalog import format_price, pricelist_catalog, search_pricelist


class PricelistTests(unittest.TestCase):
    def test_source_values_and_context(self):
        data = pricelist_catalog()
        self.assertEqual(len(data['entries']), 299)
        self.assertEqual(len(data['rates']), 25)
        self.assertEqual(len({r['category'] for r in data['entries']}), 11)
        by_row = {r['row']: r for r in data['entries']}
        self.assertEqual(by_row[10]['total'], 80000)
        self.assertEqual(by_row[35]['total'], 'By Approval')
        self.assertEqual(by_row[38]['parent'], '3.2 Kompressor AC 0,5PK  - 1PK')
        self.assertEqual((by_row[85]['total'], by_row[85]['rounded']), (200000, 20000))
        self.assertTrue(by_row[359]['free'])
        self.assertIsNone(by_row[359]['total'])
        self.assertEqual(next(r for r in data['rates'] if r['code'] == 'ELECTRONIC-A')['prices'], [40000, 450000, 50000])

    def test_search_filters_and_pages(self):
        result = search_pricelist('cleaning ac')
        self.assertEqual(result['total'], 4)
        self.assertEqual(search_pricelist('NGCG00-0008')['total'], 4)
        self.assertGreater(search_pricelist('HVAC-A')['total'], 0)
        category = pricelist_catalog()['entries'][0]['category']
        result = search_pricelist('jasa', category)
        self.assertGreater(result['total'], 0)
        self.assertTrue(all(r['category'] == category for r in result['rows']))
        self.assertEqual(search_pricelist(page=-1)['page'], 1)
        last = search_pricelist(page=99999)
        self.assertEqual(last['page'], last['pages'])
        self.assertEqual(search_pricelist('xyznoresults')['start'], 0)
        self.assertEqual(search_pricelist('HVAC-A', view='jasa')['total'], 1)

    def test_price_display_preserves_missing_zero_and_text(self):
        for value, expected in [(None, '—'), (0, 'Rp 0'), (80000, 'Rp 80.000'),
                                (8461.2, 'Rp 8.461,2'), ('By Approval', 'By Approval')]:
            self.assertEqual(format_price(value), expected)

    def test_login_and_rendering(self):
        with patch('auth.get_identity', return_value=None):
            self.assertEqual(app.test_client().get('/pricelist').status_code, 302)
        with patch('auth.get_identity', return_value={'email': 'test@example.com', 'token': 'test'}):
            client = app.test_client()
            for url in ['/pricelist', '/pricelist?view=jasa', '/pricelist?page=invalid', '/pricelist?page=9999']:
                result = client.get(url)
                self.assertEqual(result.status_code, 200)
                self.assertIn(b'Pricelist FLT.xlsx', result.data)
            result = client.get('/pricelist?q=cleaning+ac')
            self.assertIn(b'Rp 80.000', result.data)
            result = client.get('/pricelist', query_string={'q': '<script>alert(1)</script>'})
            self.assertNotIn(b'<script>alert(1)</script>', result.data)
            self.assertIn(b'Pekerjaan tidak ditemukan', result.data)
