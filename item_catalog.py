"""Read-only catalog imported from the user's Kode Item.xlsx."""
import json
import re
from functools import lru_cache
from pathlib import Path


def searchable(value):
    return re.sub(r'[^\w]+', ' ', value.casefold()).strip()


@lru_cache(maxsize=1)
def catalog():
    raw = json.loads((Path(__file__).parent / 'data' / 'items.json').read_text(encoding='utf-8'))
    pairs = {}
    names = {}
    for row in raw['items']:
        satuan = row.get('satuan', '')
        key = (row['code'], row['name'], satuan)
        pairs[key] = pairs.get(key, 0) + 1
        names.setdefault(row['code'], set()).add(row['name'])
    items = [dict(code=code, name=name, satuan=satuan, occurrences=count,
                  variants=len(names[code]), search=searchable(code + ' ' + name + ' ' + satuan))
             for (code, name, satuan), count in pairs.items()]
    items.sort(key=lambda row: (row['name'].casefold(), row['code']))
    return items, len(raw['items']), len(names)


def search_items(query, page=1, size=25):
    items, source_count, code_count = catalog()
    terms = searchable(query).split()
    found = [row for row in items if all(term in row['search'] for term in terms)]
    if query.strip():
        exact = query.strip().casefold()
        found.sort(key=lambda row: (row['code'].casefold() != exact, row['name'].casefold(), row['code']))
    pages = max(1, (len(found) + size - 1) // size)
    page = min(max(page, 1), pages)
    start = (page - 1) * size
    return dict(items=found[start:start + size], total=len(found), page=page,
                pages=pages, start=start + 1 if found else 0,
                end=min(start + size, len(found)), source_count=source_count,
                code_count=code_count, catalog_count=len(items))
