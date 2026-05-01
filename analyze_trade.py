#!/usr/bin/env python
"""Anno 117 save trade analyzer. Reads data.xml and lists routes belonging to the human."""
import sys, re, struct, os, argparse
from xml.etree import ElementTree as ET
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

HUMAN_PID_HEX = '29000000'
HUMAN_PID = 41

def i32(h):
    try: return int.from_bytes(bytes.fromhex(h),'little',signed=True)
    except: return None
def utf16(h):
    try: return bytes.fromhex(h).decode('utf-16-le').rstrip('\x00')
    except: return h

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xml-dir', required=True)
    args = ap.parse_args()

    with open(os.path.join(args.xml_dir,'data.xml'),'r',encoding='utf-8',errors='replace') as f:
        text = f.read()

    # Find all RouteMap entries (route id -> data) — each is a <None>ID</None><None>data</None> pair
    m = re.search(r'<SessionTradeRouteManager>(.*?)</SessionTradeRouteManager>', text, re.S)
    if not m:
        print('No SessionTradeRouteManager.'); return
    block = m.group(1)
    rm = re.search(r'<RouteMap>(.*?)</RouteMap>', block, re.S)
    if not rm:
        print('No RouteMap.'); return
    wrapped = '<root>' + rm.group(1) + '</root>'
    root = ET.fromstring(wrapped)
    kids = list(root)
    print(f'RouteMap top-level <None> elements: {len(kids)}  (paired -> {len(kids)//2} routes)')

    routes = []
    for i in range(0, len(kids)-1, 2):
        rec = {}
        # kids[i] is the route ID (as hex)
        rec['key_hex'] = (kids[i].text or '').strip()
        rec['key'] = i32(rec['key_hex'])
        data = kids[i+1]
        rec['ID']        = data.findtext('ID')
        rec['Name_hex']  = data.findtext('Name')
        rec['Name']      = utf16(rec['Name_hex']) if rec['Name_hex'] else ''
        rec['Owner_hex'] = data.findtext('Owner')
        rec['Owner']     = i32(rec['Owner_hex']) if rec['Owner_hex'] else None
        rec['Ships_hex'] = data.findtext('Ships')
        rec['stations']  = []
        for st in data.findall('.//Stations/None'):
            s = {
                'StationID': st.findtext('StationID'),
                'AreaID':    st.findtext('AreaID'),
                'TradeRouteID': st.findtext('TradeRouteID'),
                'RouteOwner': st.findtext('RouteOwner'),
                'AreaOwner': st.findtext('AreaOwner'),
                'AreaOwner_int': i32(st.findtext('AreaOwner') or ''),
                'HasTradeRights': st.findtext('HasTradeRights'),
            }
            rec['stations'].append(s)
        routes.append(rec)

    # Filter to routes that touch at least one human-owned area
    human_routes = []
    for r in routes:
        owners = {s['AreaOwner_int'] for s in r['stations'] if s['AreaOwner_int'] is not None}
        if HUMAN_PID in owners:
            human_routes.append(r)

    print(f'\nTotal routes in save: {len(routes)}')
    print(f'Routes touching human islands: {len(human_routes)}')

    # Distribution of route Owner values (sanity check on what "Owner" means)
    owners = Counter(r['Owner'] for r in routes)
    print(f'\nRoute "Owner" field distribution:')
    for k,v in owners.most_common():
        print(f'  Owner={k}  count={v}')

    # All AreaOwner participant IDs we see
    all_owners = Counter()
    for r in routes:
        for s in r['stations']:
            if s['AreaOwner_int'] is not None:
                all_owners[s['AreaOwner_int']] += 1
    print(f'\nAreaOwner participant distribution across all stations:')
    for k,v in all_owners.most_common():
        print(f'  AreaOwner={k}  count={v}')

    # Print human routes
    print(f'\n=== HUMAN TRADE ROUTES (touch human islands) ===')
    for r in human_routes:
        print(f'\n  Route #{r["key"]}: "{r["Name"]}"  Owner={r["Owner"]}  Stations={len(r["stations"])}')
        for s in r['stations']:
            mark = '★' if s['AreaOwner_int'] == HUMAN_PID else ' '
            print(f'    {mark} StationID={i32(s["StationID"] or "")} AreaID={s["AreaID"]} AreaOwner={s["AreaOwner_int"]} HasRights={s["HasTradeRights"]}')

if __name__ == '__main__':
    main()
