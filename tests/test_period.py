import unittest
from datetime import datetime
from unittest.mock import patch
from test_app import envelope, response
from app import app


class PeriodRegressionTests(unittest.TestCase):
    def setUp(self):
        identity = patch('auth.get_identity', return_value={'token': 'test-token', 'email': 'test@example.com'})
        identity.start()
        self.addCleanup(identity.stop)
        self.client = app.test_client()

    @patch('app.requests.get')
    def test_september_2_through_7_includes_last_day_and_all_pages(self, get):
        timestamps = ['2026-09-01T23:59:59+00:00', '2026-09-02T00:00:00+00:00',
                      '2026-09-05T18:30:00+00:00', '2026-09-07T23:59:59+00:00',
                      '2026-09-08T00:00:00+00:00']
        source = [dict(envelope(), id=str(i), created_date=value) for i, value in enumerate(timestamps)]

        def server(*args, **kwargs):
            params = kwargs['params']
            bounds = [value for key, value in params if key == 'created_date']
            self.assertEqual(bounds, ['gte.2026-09-02T00:00:00+00:00', 'lt.2026-09-08T00:00:00+00:00'])
            start, end = [datetime.fromisoformat(value.split('.', 1)[1]) for value in bounds]
            selected = [row for row in reversed(source) if start <= datetime.fromisoformat(row['created_date']) < end]
            offset = int(dict(params)['offset'])
            return response(selected[offset:offset + 1])

        get.side_effect = server
        result = self.client.get('/api/reports?start=2026-09-02&end=2026-09-07')
        self.assertEqual(result.status_code, 200)
        rows = result.get_json()['rows']
        self.assertEqual({row['id'] for row in rows}, {'1', '2', '3'})
        self.assertEqual(len(rows), 6)
        self.assertEqual(get.call_count, 4)


if __name__ == '__main__':
    unittest.main()
