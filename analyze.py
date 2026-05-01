#!/usr/bin/env python
"""Anno 117 save analyzer. Reads extracted XML files and reports human-player state."""
import sys, re, struct, os, argparse
from collections import Counter, defaultdict
from xml.etree import ElementTree as ET

sys.stdout.reconfigure(encoding='utf-8')

HUMAN_ID_HEX = '29000000'  # participant id 41

def i32(h):
    try: return int.from_bytes(bytes.fromhex(h), 'little', signed=True)
    except: return None
def u32(h):
    try: return int.from_bytes(bytes.fromhex(h), 'little', signed=False)
    except: return None
def i64(h):
    try: return int.from_bytes(bytes.fromhex(h), 'little', signed=True)
    except: return None
def f32(h):
    try: return struct.unpack('<f', bytes.fromhex(h))[0]
    except: return None
def utf16(h):
    try: return bytes.fromhex(h).decode('utf-16-le').rstrip('\x00')
    except: return None

def section_economy(text):
    m = re.search(r'<EconomyManager>(.*?)</EconomyManager>', text, re.S)
    return m.group(1) if m else ''

def parse_pairs(econ_xml):
    """EconomyManager has <Pair> blocks: ParticipantGUID + MetaEconomy."""
    out = []
    wrapped = '<root>' + econ_xml + '</root>'
    root = ET.fromstring(wrapped)
    for pair in root.iter('Pair'):
        pid = pair.findtext('ParticipantGUID')
        me = pair.find('MetaEconomy')
        if me is None: continue
        get = lambda t: me.findtext(t) or ''
        rec = {
            'pid_hex': pid,
            'pid': i32(pid),
            'population_f32':   f32(get('Population')),
            'money_f32':        f32(get('Money')),
            'happiness_f32':    f32(get('Happiness')),
            'health_f32':       f32(get('Health')),
            'fire_safety_f32':  f32(get('FireSafety')),
            'belief_f32':       f32(get('Belief')),
            'knowledge_f32':    f32(get('Knowledge')),
            'prestige_f32':     f32(get('Prestige')),
        }
        bought = me.find('BoughtSettlementRightsAndCosts')
        rec['settlements_bought'] = 0
        if bought is not None:
            rec['settlements_bought'] = sum(1 for n in bought if (n.text or '').strip() and len(n.text.strip()) <= 8)
        out.append(rec)
    return out

def find_human(participants):
    """Heuristic: human is the only one with multiple bought settlements AND positive economy."""
    candidates = [p for p in participants if p['settlements_bought'] >= 1]
    if len(candidates) == 1: return candidates[0]
    candidates.sort(key=lambda p: (p['settlements_bought'], p['money_f32'] or 0), reverse=True)
    return candidates[0] if candidates else participants[0]

def parse_money_manager(text, human_pid_hex):
    """Find the human's per-minute income/expense from MetaMoneyManager."""
    m = re.search(r'<MetaMoneyManager>(.*?)</MetaMoneyManager>', text, re.S)
    if not m: return None
    block = m.group(1)
    mp = re.search(r'<MoneyDataPerParticipant>(.*?)</MoneyDataPerParticipant>', block, re.S)
    if not mp: return None
    wrapped = '<root>' + mp.group(1) + '</root>'
    root = ET.fromstring(wrapped)
    kids = list(root)
    for i in range(0, len(kids)-1, 2):
        if kids[i].text and kids[i].text.strip().lower() == human_pid_hex.lower():
            data = kids[i+1]
            return {
                'income_per_min':  f32(data.findtext('TotalMoneyIncomePerMinute') or ''),
                'expense_per_min': f32(data.findtext('TotalMoneyOutgoingsPerMinute') or ''),
                'net_per_min':     f32(data.findtext('TotalAmountOfMoneyPerMinuteNew') or ''),
                'income_categories': parse_categories(data),
            }
    return None

def parse_categories(participant_data):
    """Decode per-source income/outgoings if available."""
    # MoneyByCategoryData typically has SourceData entries
    out = {'sources': [], 'sinks': []}
    for n in participant_data.iter('SourceData'):
        # SourceData entries have nested <None> keys + values; skip detail for now
        pass
    return out

def parse_trade_routes(text):
    """Find SessionTradeRouteManager and parse routes."""
    m = re.search(r'<SessionTradeRouteManager>(.*?)</SessionTradeRouteManager>', text, re.S)
    if not m: return []
    block = m.group(1)
    # Each route is <None>{route data}</None> at TradeRoutes level
    tr = re.search(r'<TradeRoutes>(.*?)</TradeRoutes>', block, re.S)
    if not tr: return []
    wrapped = '<root>' + tr.group(1) + '</root>'
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError as e:
        return [{'_parse_error': str(e)}]
    routes = []
    for child in root:
        # each route block contains TradeRouteID, RouteOwner, Locations, etc.
        rec = {}
        for sub in child:
            rec[sub.tag] = sub.text
        rec['_subtags'] = sorted({sub.tag for sub in child})
        routes.append(rec)
    return routes

def parse_storage(text, human_pid_hex):
    """Find storage levels per island for the human."""
    # MetaStorageCount and goods storage are scattered; focus on a high-level grep
    # Look for <Goods> blocks paired with <ProductGUID>/<ProductAmount>
    pass  # not implemented in v1

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--xml-dir', required=True, help='Directory containing data.xml, header.xml')
    args = p.parse_args()

    data_path = os.path.join(args.xml_dir, 'data.xml')
    print(f'Reading {data_path}...')
    with open(data_path, 'r', encoding='utf-8', errors='replace') as f:
        data = f.read()
    print(f'  size: {len(data):,} chars\n')

    print('=== PARTICIPANTS (EconomyManager) ===')
    econ = section_economy(data)
    parts = parse_pairs(econ)
    for p_ in parts:
        marker = ''
        print(f'  pid={p_["pid"]} ({p_["pid_hex"]})  bought={p_["settlements_bought"]}  '
              f'pop={p_["population_f32"]:>10.0f}  money={p_["money_f32"]:>10.2f}  '
              f'happy={p_["happiness_f32"]:>7.1f}  belief={p_["belief_f32"]:>7.1f}')
    human = find_human(parts)
    print(f'\nHuman player: pid={human["pid"]} ({human["pid_hex"]})')

    print('\n=== HUMAN ECONOMY ===')
    print(f'  Population (cur):    {human["population_f32"]:>12,.0f}')
    print(f'  Money* (cur, f32):   {human["money_f32"]:>12,.2f}    (* may be income/min, not balance)')
    print(f'  Happiness:           {human["happiness_f32"]:>12,.1f}')
    print(f'  Health:              {human["health_f32"]:>12,.1f}')
    print(f'  FireSafety:          {human["fire_safety_f32"]:>12,.1f}')
    print(f'  Belief:              {human["belief_f32"]:>12,.1f}')
    print(f'  Knowledge:           {human["knowledge_f32"]:>12,.1f}')
    print(f'  Prestige:            {human["prestige_f32"]:>12,.1f}')

    money_mgr = parse_money_manager(data, human['pid_hex'])
    if money_mgr:
        print(f'  Income/min:    +{money_mgr["income_per_min"]:>10,.0f}')
        print(f'  Expense/min:   -{money_mgr["expense_per_min"]:>10,.0f}')
        print(f'  Net/min:       {money_mgr["net_per_min"]:>+11,.0f}')

    print('\n=== AvailableMoneyInt (per session/budget) ===')
    avail_pairs = []
    for m_ in re.finditer(r'<AvailableMoneyInt>([^<]+)</AvailableMoneyInt>', data):
        avail_pairs.append(i32(m_.group(1)))
    print(f'  values across all islands/budgets: {avail_pairs}')
    print(f'  total: {sum(avail_pairs):,}')

    print('\n=== TRADE ROUTES (high-level count) ===')
    # Quick count
    n_routes = len(re.findall(r'<TradeRouteID>', data))
    n_owner_human = sum(1 for m_ in re.finditer(rf'<RouteOwner>{HUMAN_ID_HEX}</RouteOwner>', data, re.IGNORECASE))
    print(f'  Total TradeRouteID tags: {n_routes}')
    print(f'  Routes owned by human:   {n_owner_human}')

    print('\n=== ISLAND NAMES ===')
    seen = set()
    for m_ in re.finditer(r'<CustomIslandName>([^<]+)</CustomIslandName>', data):
        s = utf16(m_.group(1))
        if s and s not in seen:
            seen.add(s)
            print(f'  "{s}"')
    # Also look in header
    hdr = open(os.path.join(args.xml_dir, 'header.xml'), encoding='utf-8', errors='replace').read()
    for m_ in re.finditer(r'<CustomIslandName>([^<]+)</CustomIslandName>', hdr):
        s = utf16(m_.group(1))
        if s and s not in seen:
            seen.add(s)
            print(f'  "{s}" (header)')

if __name__ == '__main__':
    main()
