#!/usr/bin/env python3
"""Generates the Vice Custom Chesapeake Area (PCT CHP) scenario group into
custom-resources/scenarios/bwi.json of the colef12/vice fork.

It starts from vice's stock resources/scenarios/bwi.json and
  - renames the four stock scenarios "CHP - BWI <flow> (Combined)";
  - adds one scenario per CHP sector per BWI flow in which only that sector
    is staffed (a scenario "default_consolidation" of just that position).
    The other CHP sectors are virtual: they feed the human through added
    inbound flows whose routes hand off at the sector boundaries, and
    Vice Custom removes what the human hands them (sim.absorbIntoVirtualSector).

Sector duties follow PCT 7110.65H Chapter 5 (Chesapeake Area); handoff
points are STAR fixes near the boundaries, which are approximations.
BWIFN has no West scenario: in a West operation BWIFS is the only final.

  python3 custom-tools/chp/gen.py [custom-resources dir]
"""
import copy, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..')
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'custom-resources')
stock = json.load(open(os.path.join(ROOT, 'resources', 'scenarios', 'bwi.json')))
g = copy.deepcopy(stock)
flows = g['inbound_flows']

OPS = ['North', 'East', 'South', 'West']
OPCODE = {'North': 'N', 'East': 'E', 'South': 'S', 'West': 'W'}
STOCK = {op: stock['scenarios']['CHP - BWI ' + op] for op in OPS}

# Approach and runway scratchpad (PCT 7110.65H Table 5-2-1) by runway.
APPR = {'33L': ('I3L', '33L'), '33R': ('I3R', '33R'), '15R': ('I5R', '15R'),
        '15L': ('I5L', '15L'), '10': ('I10', 'R10'), '28': ('I28', 'R28')}

# ---------------------------------------------------------------- helpers

def stock_arrival(flow, airport):
    for a in stock['inbound_flows'][flow]['arrivals']:
        if airport in a['airports']:
            return copy.deepcopy(a)
    raise KeyError((flow, airport))

def arrival(template_flow, airport, rwy=None, **kw):
    """A copy of the stock arrival for airport in template_flow, changed by kw.
    rwy, for KBWI, sets the expected approach and runway scratchpad."""
    a = stock_arrival(template_flow, airport)
    a['airports'] = [airport]
    a['airlines'] = {airport: a['airlines'][airport]}
    for k in ('assigned_altitude',):
        a.pop(k, None)
    if rwy:
        a['expect_approach'], a['scratchpad'] = APPR[rwy]
    for k, v in kw.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v
    return a

def add_flow(name, arrivals):
    flow = {'arrivals': arrivals}
    # The same flow serves several scenarios.
    assert flows.get(name, flow) == flow, name
    flows[name] = flow
    return name

# ---------------------------------------------------------------- feeder flows

# BELAY: ANTHM5 jets that virtual BUFFR descends via the STAR and hands over
# west of EAGLL (Table 5-10-1, BUFFR to BELAY).
add_flow('ANTHM5.BELAY', [
    arrival('ANTHM5', ap, spawn='BUBBI', initial_controller='1H', initial_altitude=16000,
            initial_speed=280, waypoint_actions={'SHEPH@.5': 'ho1B'})
    for ap in ('KBWI', 'KMTN')])

# WOOLY: DCA arrivals on the CLIPR/SKILS that BELAY gives WOOLY in trail at
# 10,000 toward BAL (Table 5-10-2, BELAY to WOOLY).
clipr = stock_arrival('CLIPR3', 'KDCA')
clipr['waypoint_actions'] = {'TROYZ': 'ho1B', 'CLIPR': 'ho1W', 'CAVDI': 'h187/delete', 'NAYES': 'h327/delete'}
clipr.pop('assigned_altitude', None)
add_flow('CLIPR3.WOOLY', [clipr])
skils = stock_arrival('SKILS5', 'KDCA')
assert skils['waypoints'].startswith('N039.51.19.701,W076.48.21.379 SHILO/ho SKILS/a12000 BAL')
skils['waypoints'] = skils['waypoints'].replace('SHILO/ho SKILS/a12000', 'SHILO/ho1B SKILS/a12000/ho1W')
skils.pop('assigned_altitude', None)
add_flow('SKILS5.WOOLY', [skils])

# ---------------------------------------------------------------- final flows

def trish_final(sector, airport, rwy=None):
    """TRISH5 from BELAY: NUGGY and DRRES streams, handed off short of TRISH."""
    tag = rwy or airport[1:]
    nuggy = arrival('TRISH5.NUGGY.N', airport, rwy, spawn='TROYZ', initial_controller='1B',
                    initial_altitude=12000, initial_speed=280,
                    waypoint_actions={'FREEE@.5': 'ho' + sector})
    drres = arrival('TRISH5.DRRES.N', airport, rwy, spawn='DRRES', initial_controller='1B',
                    initial_altitude=10000, initial_speed=250,
                    waypoint_actions={'RAUKY@.5': 'ho' + sector})
    return add_flow(f'TRISH5.{tag}.{sector}', [nuggy, drres])

def anthm_final(sector, airport, rwy=None):
    """ANTHM5 from BELAY (via BUFFR), handed off at ANTHM."""
    tag = rwy or airport[1:]
    a = arrival('ANTHM5', airport, rwy, spawn='EAGLL', initial_controller='1B',
                initial_altitude=12000, initial_speed=250,
                waypoint_actions={'ANTHM': 'ho' + sector})
    return add_flow(f'ANTHM5.{tag}.{sector}', [a])

def miidy_final(sector, rwy):
    """MIIDY4 from PALEO, descending via the STAR, handed off at TRUTH."""
    a = arrival('DEALE3/MIIDY4', 'KBWI', rwy, spawn='BILIT', initial_controller='1P',
                initial_altitude=11000, initial_speed=250,
                waypoint_actions={'TRUTH': 'ho' + sector})
    return add_flow(f'MIIDY4.{rwy}.{sector}', [a])

def t495_mtn(sector):
    """KMTN arrivals off T495 from PALEO: direct JUGMO, at 4,000 (Table 5-11-1)."""
    a = stock_arrival('T495.GRACO.N', 'KMTN')
    a['waypoints'] = f'TUNDR GRACO/d4000/ho{sector} JUGMO'
    a['initial_controller'] = '1P'
    a['initial_altitude'] = 6000
    return add_flow(f'T495.MTN.{sector}', [a])

# ---------------------------------------------------------------- scenarios

def scenario(op, position, rates, departures, extra_runways=(), description=None):
    base = STOCK[op]
    s = {'configuration': 'CHP',
         'default_consolidation': {position: []},
         'arrival_runways': copy.deepcopy(base['arrival_runways']),
         'departure_runways': departures,
         'inbound_rates': rates,
         'wind': copy.deepcopy(base['wind'])}
    for ap, rwy in extra_runways:
        s['arrival_runways'].append({'airport': ap, 'runway': rwy})
    if description:
        s['description'] = description
    return s

def bwi_deps(op, rate):
    return [{'airport': 'KBWI', 'runway': '28' if op in ('North', 'West') else '15R', 'rate': rate}]

def dca_deps(op, category, rate):
    return [{'airport': 'KDCA', 'runway': '1' if op in ('North', 'West') else '19',
             'category': category, 'rate': rate}]

scen = {}
for op in OPS:
    c = OPCODE[op]
    t495 = 'T495.GRACO.N' if op in ('North', 'West') else 'T495.GRACO.S'

    # BUFFR (1H): ANTHM5 arrivals, IAD northwest departures, DCA HORTO4
    # departures, ARLFT2 via LUNDY. Arrivals go to BELAY.
    scen[f'CHP - BUFFR - BWI {op}'] = scenario(op, '1H',
        {'ANTHM5': {'KBWI': 12, 'KMTN': 1}, 'JERES2/MCRAY2': {'overflights': 10},
         'ARLFT2.LUNDY': {'overflights': 2}},
        bwi_deps(op, 10) + dca_deps(op, 'North', 9),
        description='BUFFR (1H) only. ANTHM5 to BELAY; IAD/DCA northwest departures to ZDC.')

    # WOOLY (1W): BWI FOXHL/LINSE/TERPZ departures, CLIPR/SKILS DCA arrivals from BELAY.
    scen[f'CHP - WOOLY - BWI {op}'] = scenario(op, '1W',
        {'CLIPR3.WOOLY': {'KDCA': 10}, 'SKILS5.WOOLY': {'KDCA': 4}},
        bwi_deps(op, 22),
        description='WOOLY (1W) only. BWI west departures; CLIPR/SKILS DCA arrivals from BELAY to Mount Vernon.')

    # BELAY (1B): TRISH5 arrivals, ANTHM5 from BUFFR, CLIPR/SKILS DCA arrivals.
    scen[f'CHP - BELAY - BWI {op}'] = scenario(op, '1B',
        {f'TRISH5.NUGGY.{c}': {'KBWI': 8, 'KMTN': 1}, f'TRISH5.DRRES.{c}': {'KBWI': 3},
         'ANTHM5.BELAY': {'KBWI': 10, 'KMTN': 1}, 'CLIPR3': {'KDCA': 10}, 'SKILS5': {'KDCA': 4}},
        bwi_deps(op, 10),
        description='BELAY (1B) only. TRISH5 and ANTHM5 (from BUFFR) to the BWI finals; CLIPR/SKILS to WOOLY.')

    # GRACO (1G): BWI DUKPN/CONLE departures, DCA DOCTR (DQO) departures.
    scen[f'CHP - GRACO - BWI {op}'] = scenario(op, '1G',
        {}, bwi_deps(op, 24) + dca_deps(op, 'DQO', 6),
        description='GRACO (1G) only. BWI DUKPN/CONLE and DCA DOCTR departures.')

    # PALEO (1P): MIIDY4 BWI and DEALE3 DCA arrivals, T495 satellites, ARLFT2 via COLIN.
    scen[f'CHP - PALEO - BWI {op}'] = scenario(op, '1P',
        {'DEALE3/MIIDY4': {'KBWI': 8, 'KDCA': 10}, t495: {'KESN': 3, 'KMTN': 2},
         'ARLFT2.COLIN': {'overflights': 2}},
        bwi_deps(op, 10),
        description='PALEO (1P) only. MIIDY4 to the BWI finals, DEALE3 to Mount Vernon, ESN/MTN satellites.')

# Finals. North: BWIFS 33L, BWIFN 33R + MTN. West: BWIFS alone (28/33L + MTN).
# South: BWIFS 15R, BWIFN 15L + MTN. East: BWIFS 10, BWIFN 15L + MTN.
fs_rwy = {'North': '33L', 'South': '15R', 'East': '10'}
for op in ('North', 'South', 'East'):
    r = fs_rwy[op]
    ravnn = 'RAVNN9.' + r
    scen[f'CHP - BWIFS - BWI {op}'] = scenario(op, '1S',
        {trish_final('1S', 'KBWI', r): {'KBWI': 12},
         ravnn: {'KBWI': 10},
         **({anthm_final('1S', 'KBWI', r): {'KBWI': 8}} if op != 'North' else {})},
        bwi_deps(op, 10),
        description=f'BWIFS (1S) only. Runway {r}: TRISH5/ANTHM5 from BELAY, RAVNN9 from Mount Vernon.')

    nr = '33R' if op == 'North' else '15L'
    rates = {miidy_final('1N', nr): {'KBWI': 8},
             t495_mtn('1N'): {'KMTN': 3},
             trish_final('1N', 'KMTN'): {'KMTN': 2}}
    if op == 'North':
        rates[anthm_final('1N', 'KBWI', '33R')] = {'KBWI': 8}
        rates[anthm_final('1N', 'KMTN')] = {'KMTN': 2}
    scen[f'CHP - BWIFN - BWI {op}'] = scenario(op, '1N', rates, bwi_deps(op, 10),
        extra_runways=() if op == 'North' else (('KBWI', '15L'),),
        description=f'BWIFN (1N) only. Runway {nr}: MIIDY4 from PALEO' +
                    (', ANTHM5 from BELAY' if op == 'North' else '') + '; MTN satellite arrivals.')

# West: BWIFS works both runways and MTN (5-9-3 b).
scen['CHP - BWIFS - BWI West'] = scenario('West', '1S',
    {trish_final('1S', 'KBWI', '28'): {'KBWI': 10},
     anthm_final('1S', 'KBWI', '33L'): {'KBWI': 8},
     miidy_final('1S', '28'): {'KBWI': 6},
     'RAVNN9.28': {'KBWI': 8},
     t495_mtn('1S'): {'KMTN': 3}},
    bwi_deps('West', 10),
    description='BWIFS (1S) only; West operation has no BWIFN. Runways 28 and 33L plus MTN.')

# ---------------------------------------------------------------- assemble

scenarios = {}
for op in OPS:
    scenarios[f'CHP - BWI {op} (Combined)'] = stock['scenarios'][f'CHP - BWI {op}']
for name in sorted(scen):
    scenarios[name] = scen[name]
g['scenarios'] = scenarios
g['default_scenario'] = stock['default_scenario'] + ' (Combined)'
assert g['default_scenario'] in scenarios

path = os.path.join(OUT, 'scenarios', 'bwi.json')
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, 'w') as f:
    json.dump(g, f, indent=2)
    f.write('\n')
print('wrote', path, len(scenarios), 'scenarios')
