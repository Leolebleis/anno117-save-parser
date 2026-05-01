#!/usr/bin/env python
"""Authoritative building counter v2.

Approach: each placed object has an <ID>16-hex-chars</ID> where bytes 4-5 encode the AreaID.
We know which AreaIDs the human owns (from trade-route analysis). For each placed
object whose ID's AreaID matches a human-owned area, take its <guid>/<GUID> and count.
"""
import sys, re, json, os, argparse
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')

def i32(h):
    try: return int.from_bytes(bytes.fromhex(h),'little',signed=True)
    except: return None

# EDIT THESE for your save. AreaIDs are 4-hex-char identifiers shown alongside
# stations in `analyze_trade.py` output. Take all `AreaOwner=<your-pid>` station
# AreaIDs from your own trade routes (Owner=<your-pid>). Latium/Albion grouping
# is just for the per-region breakdown — the empire total is the union.
LATIUM_AREAS = {'C127', 'C122', '4121', '8123'}
ALBION_AREAS = {'0321', '4321', 'C322', '8324'}
HUMAN_AREAS = LATIUM_AREAS | ALBION_AREAS

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xml-dir', required=True)
    ap.add_argument('--guid-map', required=True)
    args = ap.parse_args()
    gm = json.load(open(args.guid_map, encoding='utf-8'))
    gm = {int(k): v for k, v in gm.items()}

    by_area = defaultdict(Counter)  # area -> guid -> count

    # Parse each session blob
    for blob_idx, region in [(0, 'Latium'), (1, 'Albion')]:
        path = os.path.join(args.xml_dir, f'session_blob_{blob_idx}.xml')
        if not os.path.exists(path):
            print(f'SKIP {path}'); continue
        print(f'Reading {path}...')
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()

        # An object record is a <None>...</None> block containing both:
        #   <guid>HEX</guid> (or <GUID>HEX</GUID>)  and
        #   <ID>16-hex-chars</ID>
        # Strategy: find every <ID>16-hex</ID>, look BACKWARD up to 1500 chars for the
        # nearest <guid>/<GUID>, decode AreaID from the ID.
        id_re = re.compile(r'<ID>([0-9A-Fa-f]{16})</ID>')
        guid_re = re.compile(r'<(?:guid|GUID)>([0-9A-Fa-f]{8})</(?:guid|GUID)>', re.IGNORECASE)

        n_records = 0
        n_human = 0
        for m in id_re.finditer(text):
            id_hex = m.group(1).upper()
            area = id_hex[8:12]  # bytes 4-5 (chars 8-11) = AreaID display
            if area not in HUMAN_AREAS:
                continue
            # backward search
            window = text[max(0, m.start()-800):m.start()]
            last_g = None
            for g in guid_re.finditer(window):
                last_g = g.group(1)
            if last_g:
                guid_int = i32(last_g)
                by_area[area][guid_int] += 1
                n_human += 1
            n_records += 1
        print(f'  scanned IDs: {sum(1 for _ in id_re.finditer(text))}, human-area objects with guid: {n_human}')

    # Aggregate empire-wide
    empire = Counter()
    for area, c in by_area.items():
        empire.update(c)

    by_tpl = defaultdict(list)
    unknown_count = 0
    for guid, n in empire.items():
        info = gm.get(guid)
        if info is None:
            unknown_count += 1
            continue
        by_tpl[info['template']].append((n, guid, info['name']))

    print(f'\n\n=== EMPIRE TOTAL: {sum(empire.values()):,} placed objects across {len(by_area)} areas ===\n')
    interesting = ['ResidenceBuilding','Production','Production Field','Production Area',
        'Production Marsh','Production Marsh Pasture','Production Marsh Area',
        'SlotFactoryBuilding7','PublicServiceBuilding','MiniInstitutionBuilding',
        'MonumentEventBuilding','RecruitmentBuilding','HarborDepot','HarborWarehouse',
        'TradeBuilding','OrnamentalBuilding','ProductionModuleSilo']
    seen = set()
    for tpl in interesting:
        if tpl in by_tpl:
            print(f'\n--- {tpl} ---')
            for n, guid, name in sorted(by_tpl[tpl], key=lambda x: -x[0]):
                print(f'  {n:>4}  ({guid:>7})  {name}')
            seen.add(tpl)

    # Per-region breakdown (just residences)
    print('\n\n=== Residences per region ===')
    for region, areas in [('LATIUM', LATIUM_AREAS), ('ALBION', ALBION_AREAS)]:
        print(f'\n{region}:')
        for area in sorted(areas):
            counts = by_area.get(area, Counter())
            total_in_area = sum(counts.values())
            res_in_area = {g:n for g,n in counts.items() if gm.get(g,{}).get('template')=='ResidenceBuilding'}
            res_total = sum(res_in_area.values())
            print(f'  Area {area}: {total_in_area} total objects, {res_total} residences')
            for g, n in sorted(res_in_area.items(), key=lambda x: -x[1]):
                print(f'    {n:>3}  {gm[g]["name"]}')

if __name__ == '__main__':
    main()
