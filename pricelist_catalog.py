"""Searchable, read-only FLT price list with original source values."""
import json
from functools import lru_cache
from pathlib import Path
from item_catalog import searchable


@lru_cache(maxsize=1)
def pricelist_catalog():
    return json.loads((Path(__file__).parent / 'data' / 'pricelist.json').read_text(encoding='utf-8'))


def format_price(value):
    if value is None:
        return '—'
    if isinstance(value, (int, float)):
        number = f'{value:,.2f}'.rstrip('0').rstrip('.').replace(',', '_').replace('.', ',').replace('_', '.')
        return 'Rp ' + number
    return str(value)


def search_pricelist(query='', category='', page=1, view='detail', size=25):
    data = pricelist_catalog()
    rows = data['rates'] if view == 'jasa' else data['entries']
    categories = list(dict.fromkeys(row['category'] for row in rows))
    if category not in categories:
        category = ''
    terms = searchable(query).split()
    exact_code = any(str(row.get('code') or '').casefold() == query.casefold() for row in rows) if query else False
    found = [row for row in rows if (not category or row['category'] == category)
             and (not exact_code or str(row.get('code') or '').casefold() == query.casefold())
             and all(term in searchable(' '.join(str(row.get(field) or '') for field in
                 ('category', 'group', 'parent', 'name', 'code', 'service_type', 'type', 'note', 'examples')))
                     for term in terms)]
    pages = max(1, (len(found) + size - 1) // size)
    page = min(max(1, page), pages)
    start = (page - 1) * size
    return dict(rows=found[start:start + size], total=len(found), catalog_count=len(rows),
                categories=categories, category=category, page=page, pages=pages,
                start=start + 1 if found else 0, end=min(start + size, len(found)),
                period=data['period'], criteria_notes=data['criteria_notes'])
