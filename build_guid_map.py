#!/usr/bin/env python
"""Build a GUID -> {name, template} map from the game's assets.xml."""
import sys, json, os, argparse
from xml.etree.ElementTree import iterparse

sys.stdout.reconfigure(encoding='utf-8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--assets', required=True, help='Path to assets.xml')
    ap.add_argument('--out', required=True, help='Output JSON path')
    args = ap.parse_args()

    out = {}
    n = 0
    cur_template = None
    cur_guid = None
    cur_name = None
    cur_id = None
    in_standard = False

    # Stream parse to keep memory bounded
    for ev, elem in iterparse(args.assets, events=('start','end')):
        if ev == 'start':
            if elem.tag == 'Standard':
                in_standard = True
            elif elem.tag == 'Asset':
                cur_template = None
                cur_guid = None
                cur_name = None
                cur_id = None
        else:  # end
            if elem.tag == 'Template':
                cur_template = (elem.text or '').strip()
            elif elem.tag == 'GUID' and in_standard:
                try:
                    cur_guid = int((elem.text or '').strip())
                except ValueError:
                    pass
            elif elem.tag == 'Name' and in_standard:
                cur_name = (elem.text or '').strip()
            elif elem.tag == 'ID' and in_standard:
                cur_id = (elem.text or '').strip()
            elif elem.tag == 'Standard':
                in_standard = False
            elif elem.tag == 'Asset':
                if cur_guid is not None:
                    out[cur_guid] = {
                        'name': cur_name or '',
                        'id': cur_id or '',
                        'template': cur_template or ''
                    }
                    n += 1
                    if n % 5000 == 0:
                        print(f'  parsed {n} assets...')
                elem.clear()  # free memory

    print(f'\nTotal assets: {n}')
    print(f'Distinct GUIDs: {len(out)}')

    # Stats by template
    from collections import Counter
    tpl_counts = Counter(v['template'] for v in out.values())
    print('\nTop 30 templates:')
    for t, c in tpl_counts.most_common(30):
        print(f'  {c:>5}  {t}')

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'\nWrote {args.out}')

if __name__ == '__main__':
    main()
