"""Read-only, paginated access to the additional Supabase project."""
import os
import re

import requests

PAGE_SIZE = 50


class ViewerError(Exception):
    pass


def fetch_table(table, page):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', table):
        raise ViewerError('Nama tabel harus berupa huruf, angka, atau underscore, dan diawali huruf atau underscore.')
    url = os.getenv('TABLE_SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('TABLE_SUPABASE_KEY', '').strip()
    if not url or not key:
        raise ViewerError('Koneksi belum dikonfigurasi. Isi TABLE_SUPABASE_URL dan TABLE_SUPABASE_KEY di .env.')
    try:
        response = requests.get(
            url + '/rest/v1/' + table,
            headers={'apikey': key, 'Authorization': 'Bearer ' + key, 'Prefer': 'count=exact'},
            params={'select': '*', 'limit': PAGE_SIZE, 'offset': (page - 1) * PAGE_SIZE,
                    **({'order': 'log_date.desc,log_key.asc'} if table == 'logsheets' else {})},
            timeout=25,
        )
    except requests.RequestException:
        raise ViewerError('Tidak dapat menghubungi Supabase. Periksa koneksi lalu coba lagi.') from None
    if response.status_code in (401, 403):
        raise ViewerError('Akses ditolak Supabase. Periksa anon key dan izin SELECT/RLS untuk tabel ini.')
    if response.status_code == 404:
        raise ViewerError('Tabel tidak ditemukan. Periksa nama tabel dan pastikan tersedia melalui API Supabase.')
    if response.status_code == 416:
        return [], None
    if not response.ok:
        raise ViewerError('Supabase gagal memuat tabel (HTTP %s). Periksa nama tabel dan konfigurasi API.' % response.status_code)
    try:
        rows = response.json()
    except ValueError:
        raise ViewerError('Respons Supabase tidak valid. Silakan coba lagi.') from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ViewerError('Format data Supabase bukan kumpulan baris tabel.')
    raw_total = response.headers.get('Content-Range', '').rsplit('/', 1)[-1]
    total = int(raw_total) if raw_total.isdigit() else None
    return rows, total


def logsheet_context(rows, args):
    """Build readable inspection items for one log, preserving zero/false values."""
    selected_key = args.get('log', '')
    selected = next((row for row in rows if str(row.get('log_key')) == selected_key), None)
    if selected is None:
        selected = rows[0] if rows else None
    payload = selected.get('payload') if selected else None
    metadata = {'Tanggal', 'Shift', 'Petugas 1', 'Petugas 2', 'Petugas 3'}
    items = []
    if isinstance(payload, dict):
        for name, value in payload.items():
            if name in metadata:
                continue
            group, separator, label = name.partition(' - ')
            items.append({'group': group if separator else 'Umum',
                          'name': label if separator else name,
                          'value': value, 'full_name': name,
                          'filled': value is not None and value != ''})
    groups = sorted({item['group'] for item in items}, key=str.casefold)
    query = args.get('q', '').strip()[:200]
    group = args.get('group', '')
    filled_only = args.get('filled') == '1'
    visible = [item for item in items
               if (not group or item['group'] == group)
               and (not filled_only or item['filled'])
               and (not query or query.casefold() in item['full_name'].casefold())]
    visible.sort(key=lambda item: (item['group'].casefold(), item['name'].casefold()))
    return dict(selected_log=selected, log_items=visible, log_groups=groups,
                item_count=len(items), filled_count=sum(item['filled'] for item in items),
                log_query=query, log_group=group, filled_only=filled_only,
                payload_valid=isinstance(payload, dict),
                personnel=[payload[name] for name in ('Petugas 1', 'Petugas 2', 'Petugas 3')
                           if payload.get(name) is not None and payload.get(name) != '']
                if isinstance(payload, dict) else [])


def register_supabase_viewer(app):
    from flask import render_template, request

    @app.get('/tabel-supabase')
    def supabase_tables():
        tables = [name.strip() for name in os.getenv('TABLE_SUPABASE_TABLES', '').split(',') if name.strip()]
        table = request.args.get('table', tables[0] if tables else '').strip()
        try:
            page = max(1, min(int(request.args.get('page', '1')), 1000000))
        except ValueError:
            page = 1
        rows, total, error = [], None, None
        if table:
            try:
                rows, total = fetch_table(table, page)
            except ViewerError as exc:
                error = str(exc)
        columns = list(dict.fromkeys(column for row in rows for column in row))
        return render_template('supabase_tables.html', tables=tables, table=table,
                               page=page, rows=rows, total=total, columns=columns, error=error,
                               **logsheet_context(rows if table == 'logsheets' else [], request.args),
                               start=(page - 1) * PAGE_SIZE + 1 if rows else 0,
                               end=(page - 1) * PAGE_SIZE + len(rows) if rows else 0,
                               has_next=(page * PAGE_SIZE < total if total is not None else len(rows) == PAGE_SIZE))
