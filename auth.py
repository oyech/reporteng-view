"""Server-side Supabase sessions with rotating refresh tokens. Browser cookies contain only a random ID."""
from contextlib import contextmanager
import hashlib
import math
import os
import secrets
import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import requests
from flask import current_app, session


class AuthError(Exception):
    def __init__(self, message, status=401):
        super().__init__(message)
        self.status = status


@contextmanager
def connect():
    path = Path(current_app.config['AUTH_DB'])
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Pre-create with private permissions before sqlite opens the file.
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd)
    db = sqlite3.connect(path, timeout=65)
    db.row_factory = sqlite3.Row
    # Serialize schema migration across workers; preserve all existing sessions.
    db.execute('BEGIN IMMEDIATE')
    db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, token TEXT NOT NULL, email TEXT NOT NULL, expires REAL NOT NULL)')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(sessions)')}
    if 'refresh_token' not in columns:
        db.execute('ALTER TABLE sessions ADD COLUMN refresh_token TEXT')
    db.commit()
    try:
        with db:
            yield db
    finally:
        db.close()


def digest(sid):
    return hashlib.sha256(sid.encode()).hexdigest()


def api_headers(token=None):
    headers = {'apikey': os.getenv('SUPABASE_KEY', ''), 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    return headers


def base_url():
    return os.getenv('SUPABASE_URL', '').rstrip('/')


def check_member(token):
    try:
        user_response = requests.get(base_url() + '/auth/v1/user', headers=api_headers(token), timeout=(10, 20))
        if user_response.status_code == 401:
            raise AuthError('Sesi berakhir. Silakan login kembali.')
        if not user_response.ok:
            raise AuthError('Identitas pengguna belum dapat diverifikasi.', 503)
        user_id = user_response.json().get('id')
        if not isinstance(user_id, str) or not user_id:
            raise ValueError()
        response = requests.get(base_url() + '/rest/v1/profiles',
                                headers=api_headers(token),
                                params={'select': 'id', 'id': 'eq.' + user_id, 'limit': '1'}, timeout=(10, 20))
        if response.status_code == 401:
            raise AuthError('Sesi berakhir. Silakan login kembali.')
        if not response.ok:
            raise AuthError('Profil belum dapat dibaca. Periksa izin SELECT dan policy profiles di Supabase.', 503)
        members = response.json()
        if not isinstance(members, list):
            raise ValueError()
        if not any(isinstance(member, dict) and member.get('id') == user_id for member in members):
            raise AuthError('Profil akun ini belum tersedia atau belum dapat dibaca di tabel profiles. Hubungi pengelola.', 403)
    except (requests.RequestException, ValueError):
        raise AuthError('Tidak dapat memeriksa akses tim. Silakan coba kembali.', 503)


def login_user(email, password):
    try:
        response = requests.post(base_url() + '/auth/v1/token', params={'grant_type': 'password'},
                                 headers=api_headers(), json={'email': email, 'password': password}, timeout=(10, 20))
        if response.status_code == 429:
            raise AuthError('Terlalu banyak percobaan login. Tunggu sebentar lalu coba lagi.', 429)
        if not response.ok:
            raise AuthError('Login gagal. Periksa email, password, dan konfirmasi akun Supabase.')
        payload = response.json()
        token, refresh_token, expires = token_values(payload)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise AuthError('Layanan login tidak tersedia. Silakan coba lagi.', 503)
    check_member(token)
    logout_user()
    sid = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute('INSERT INTO sessions (id, token, email, expires, refresh_token) VALUES (?, ?, ?, ?, ?)',
                   (digest(sid), token, email, expires, refresh_token))
    session['sid'] = sid
    session['csrf'] = secrets.token_urlsafe(32)
    session.permanent = True  # Make session permanent


def token_values(payload):
    token, refresh_token = payload['access_token'], payload['refresh_token']
    lifetime = float(payload['expires_in'])
    if not all(isinstance(value, str) and value for value in (token, refresh_token)) or not math.isfinite(lifetime) or lifetime <= 0:
        raise ValueError('Invalid token response')
    return token, refresh_token, time.time() + lifetime


def session_identity(sid, rejected_token=None):
    with connect() as db:
        # One refresh at a time, including across processes and browser tabs.
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT token, email, expires, refresh_token FROM sessions WHERE id = ?', (digest(sid),)).fetchone()
        if not row:
            return None
        token = row['token']
        needs_refresh = row['expires'] <= time.time() + 60 or rejected_token == token
        if row['refresh_token'] and needs_refresh:
            try:
                response = requests.post(base_url() + '/auth/v1/token',
                                         params={'grant_type': 'refresh_token'}, headers=api_headers(),
                                         json={'refresh_token': row['refresh_token']}, timeout=(10, 20))
                if response.status_code in (400, 401, 403):
                    raise AuthError('Sesi tidak dapat diperpanjang oleh Supabase. Silakan masuk kembali.')
                if not response.ok:
                    raise AuthError('Pembaruan sesi sementara gagal. Silakan coba lagi.', 503)
                token, refresh_token, expires = token_values(response.json())
            except (requests.RequestException, ValueError, KeyError, TypeError):
                raise AuthError('Pembaruan sesi sementara gagal. Silakan coba lagi.', 503)
            db.execute('UPDATE sessions SET token = ?, refresh_token = ?, expires = ? WHERE id = ?',
                       (token, refresh_token, expires, digest(sid)))
        return {'token': token, 'email': row['email']}


def get_identity():
    sid = session.get('sid')
    if not sid:
        return None
    identity = session_identity(sid)
    if not identity:
        return None
    try:
        check_member(identity['token'])
    except AuthError as error:
        if error.status != 401:
            raise
        renewed = session_identity(sid, rejected_token=identity['token'])
        if not renewed or renewed['token'] == identity['token']:
            raise
        check_member(renewed['token'])
        identity = renewed
    session.permanent = True
    return identity


def logout_user():
    sid = session.get('sid')
    if sid:
        with connect() as db:
            db.execute('DELETE FROM sessions WHERE id = ?', (digest(sid),))
    session.clear()
