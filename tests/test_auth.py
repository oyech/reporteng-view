import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import auth
from app import app


def auth_user():
    return Mock(ok=True, status_code=200, json=lambda: {'id': 'member-id'})


def member_api(url, **kwargs):
    if url.endswith('/auth/v1/user'):
        return auth_user()
    return Mock(ok=True, status_code=200, json=lambda: [{'id': 'member-id'}])


def nonmember_api(url, **kwargs):
    if url.endswith('/auth/v1/user'):
        return auth_user()
    return Mock(ok=True, status_code=200, json=lambda: [])


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = app.config['AUTH_DB']
        app.config['AUTH_DB'] = str(Path(self.temp.name) / 'sessions.sqlite3')
        self.client = app.test_client()

    def tearDown(self):
        app.config['AUTH_DB'] = self.old_db
        self.temp.cleanup()

    def csrf(self):
        self.client.get('/login')
        with self.client.session_transaction() as session:
            return session['csrf']

    def signin(self):
        return self.client.post('/login', data={'csrf': self.csrf(), 'email': 'member@example.com', 'password': 'test-password'})

    @patch('auth.requests.get')
    def test_anonymous_cannot_read_or_export(self, get):
        self.assertEqual(self.client.get('/').status_code, 302)
        for path in ('/api/reports', '/export'):
            self.assertEqual(self.client.get(path).status_code, 401)
        get.assert_not_called()

    @patch('auth.requests.post')
    def test_csrf_rejected_before_login(self, post):
        self.assertEqual(self.client.post('/login', data={'email': 'x', 'password': 'x'}).status_code, 400)
        post.assert_not_called()
        self.assertEqual(self.client.post('/logout').status_code, 400)

    @patch('auth.requests.post')
    def test_invalid_password(self, post):
        post.return_value = Mock(ok=False, status_code=400)
        self.assertEqual(self.signin().status_code, 401)
        with self.client.session_transaction() as session:
            self.assertNotIn('sid', session)

    @patch('auth.requests.get')
    @patch('auth.requests.post')
    def test_nonmember_cannot_login(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'private-token', 'expires_in': 3600, 'refresh_token': 'private-refresh'})
        get.side_effect = nonmember_api
        self.assertEqual(self.signin().status_code, 403)
        with self.client.session_transaction() as session:
            self.assertNotIn('sid', session)

    @patch('auth.requests.get')
    @patch('auth.requests.post')
    def test_member_token_forwarded_and_logout_invalidates(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'private-token', 'expires_in': 3600, 'refresh_token': 'private-refresh'})
        member = Mock(ok=True, status_code=200, json=lambda: [{'id': 'member-id'}])
        get.side_effect = member_api
        result = self.signin()
        self.assertEqual(result.status_code, 302)
        self.assertNotIn('private-token', result.headers.get('Set-Cookie', ''))
        with self.client.session_transaction() as session:
            self.assertEqual(set(session), {'sid', 'csrf', '_permanent'})
            csrf = session['csrf']
        get.side_effect = [auth_user(), member, Mock(ok=True, status_code=200, json=lambda: [])]
        self.assertEqual(self.client.get('/api/reports').status_code, 200)
        self.assertEqual(get.call_args.kwargs['headers']['Authorization'], 'Bearer private-token')
        self.assertEqual(self.client.post('/logout', data={'csrf': csrf}).status_code, 302)
        self.assertEqual(self.client.get('/api/reports').status_code, 401)
        with app.app_context(), auth.connect() as db:
            self.assertEqual(db.execute('select count(*) from sessions').fetchone()[0], 0)

    @patch('auth.requests.get')
    @patch('auth.requests.post')
    def test_expired_session_and_removed_member(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'private-token', 'expires_in': 3600, 'refresh_token': 'private-refresh'})
        get.side_effect = member_api
        self.signin()
        with app.app_context(), auth.connect() as db:
            db.execute('update sessions set expires = ?', (time.time() - 1,))
        with patch('app.fetch_reports', return_value=[]):
            self.assertEqual(self.client.get('/export').status_code, 200)
        self.signin()
        get.side_effect = nonmember_api
        self.assertEqual(self.client.get('/export').status_code, 403)
        self.assertEqual(self.client.get('/api/reports').status_code, 403)


    @patch('auth.requests.get')
    def test_profile_query_is_scoped_to_verified_user(self, get):
        get.side_effect = member_api
        auth.check_member('test-token')
        self.assertTrue(get.call_args.args[0].endswith('/rest/v1/profiles'))
        self.assertEqual(get.call_args.kwargs['params']['id'], 'eq.member-id')

    @patch('auth.requests.get')
    def test_another_profile_cannot_grant_access(self, get):
        get.side_effect = [auth_user(), Mock(ok=True, status_code=200, json=lambda: [{'id': 'other-user'}])]
        with self.assertRaises(auth.AuthError) as error:
            auth.check_member('test-token')
        self.assertEqual(error.exception.status, 403)


class SessionRefreshTests(unittest.TestCase):
    setUp = AuthTests.setUp
    tearDown = AuthTests.tearDown
    csrf = AuthTests.csrf
    signin = AuthTests.signin

    @patch('auth.requests.get', side_effect=member_api)
    @patch('auth.requests.post')
    def test_rotation_persists_and_is_not_repeated(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'old-token', 'refresh_token': 'old-refresh', 'expires_in': 3600})
        self.signin()
        with app.app_context(), auth.connect() as db:
            db.execute('UPDATE sessions SET expires = 0')
        post.reset_mock()
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'new-token', 'refresh_token': 'new-refresh', 'expires_in': 3600})
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/').status_code, 200)
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['params'], {'grant_type': 'refresh_token'})
        self.assertEqual(post.call_args.kwargs['json'], {'refresh_token': 'old-refresh'})
        with app.app_context(), auth.connect() as db:
            row = db.execute('SELECT token, refresh_token FROM sessions').fetchone()
            self.assertEqual(tuple(row), ('new-token', 'new-refresh'))
        with self.client.session_transaction() as cookie:
            self.assertEqual(set(cookie), {'sid', 'csrf', '_permanent'})

    @patch('auth.requests.get', side_effect=member_api)
    @patch('auth.requests.post')
    def test_refresh_failure_preserves_session_and_can_retry(self, post, get):
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'old-token', 'refresh_token': 'old-refresh', 'expires_in': 3600})
        self.signin()
        with self.client.session_transaction() as cookie:
            sid = cookie['sid']
        with app.app_context(), auth.connect() as db:
            db.execute('UPDATE sessions SET expires = 0')
        for status in (503, 429, 400):
            post.return_value = Mock(ok=False, status_code=status)
            self.assertEqual(self.client.get('/api/reports').status_code, 401 if status == 400 else 503)
            with self.client.session_transaction() as cookie:
                self.assertEqual(cookie['sid'], sid)
            with app.app_context(), auth.connect() as db:
                self.assertEqual(db.execute('SELECT refresh_token FROM sessions').fetchone()[0], 'old-refresh')
        post.return_value = Mock(ok=True, status_code=200, json=lambda: {'access_token': 'new-token', 'refresh_token': 'new-refresh', 'expires_in': 3600})
        self.assertEqual(self.client.get('/').status_code, 200)

    @patch('auth.requests.get', side_effect=member_api)
    @patch('auth.requests.post')
    def test_legacy_migration_preserves_active_user(self, post, get):
        import sqlite3
        with sqlite3.connect(app.config['AUTH_DB']) as db:
            db.execute('CREATE TABLE sessions (id TEXT PRIMARY KEY, token TEXT NOT NULL, email TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)', (auth.digest('legacy-id'), 'legacy-token', 'member@example.com', 0))
        with self.client.session_transaction() as cookie:
            cookie['sid'] = 'legacy-id'
            cookie['csrf'] = 'legacy-csrf'
        self.assertEqual(self.client.get('/').status_code, 200)
        post.assert_not_called()
        get.side_effect = [Mock(ok=False, status_code=401)]
        self.assertEqual(self.client.get('/api/reports').status_code, 401)
        with app.app_context(), auth.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0], 1)
        with self.client.session_transaction() as cookie:
            self.assertEqual(cookie['sid'], 'legacy-id')
