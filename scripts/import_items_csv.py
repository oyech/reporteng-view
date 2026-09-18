import csv
import json
import sys
from pathlib import Path


def main(source, destination):
    with source.open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream, delimiter=';'))
    items = []
    for row in rows:
        code = (row.get('code') or '').strip()
        name = (row.get('name') or '').strip()
        satuan = (row.get('satuan') or '').strip()
        if code and name:
            items.append({'code': code, 'name': name, 'satuan': satuan})
    destination.write_text(
        json.dumps({'source': source.name, 'items': items}, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    print(f'Imported {len(items)} rows to {destination}')


if __name__ == '__main__':
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parents[1] / 'data' / 'items.json'
    main(source, destination)
