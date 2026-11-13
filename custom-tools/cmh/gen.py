#!/usr/bin/env python3
"""Generates the Vice Custom CMH (Columbus TRACON) facility configuration and
scenario groups into custom-resources/ of the colef12/vice fork.

  custom-resources/configurations/ZID/CMH.json   facility config (replaces stock stub)
  custom-resources/scenarios/cmh.json            "Columbus Area"
  custom-resources/scenarios/day.json            "Dayton Area"
  custom-resources/scenarios/cmhcombined.json    "CMH Combined"

Sources: FAA CIFP in vice (STARs/approaches), vice's scraped real-world routes,
vice's ZID STARS video maps. Sector layout and altitudes are approximations.
"""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from cifp import fix

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'custom-resources')

# ---------------------------------------------------------------- helpers

def dms(lat, lon):
    def f(v, pos, neg, w):
        h = pos if v >= 0 else neg
        v = abs(v)
        d = int(v); m = int((v - d) * 60); s = ((v - d) * 60 - m) * 60
        return f"{h}{d:0{w}d}.{m:02d}.{s:06.3f}"
    return f(lat, 'N', 'S', 3) + ',' + f(lon, 'E', 'W', 3)

def pt(name):
    return fix[name]

def along(a, b, frac):
    a, b = pt(a) if isinstance(a, str) else a, pt(b) if isinstance(b, str) else b
    return (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)

def nm(a, b):
    a, b = pt(a) if isinstance(a, str) else a, pt(b) if isinstance(b, str) else b
    dlat = (a[0] - b[0]) * 60
    dlon = (a[1] - b[1]) * 60 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dlat, dlon)

def toward(a, b, dist_nm):
    """Point dist_nm from a toward b."""
    return along(a, b, dist_nm / nm(a, b))

def al(*codes, fleet=None):
    out = []
    for c in codes:
        o = {"icao": c}
        if fleet: o["fleet"] = fleet
        out.append(o)
    return out

def arr_airlines(apt, pairs):
    """pairs: list of (icao, origin[, fleet])"""
    res = []
    for p in pairs:
        o = {"icao": p[0], "airport": p[1]}
        if len(p) > 2: o["fleet"] = p[2]
        res.append(o)
    return {apt: res}

# ---------------------------------------------------------------- facility config

CONTROL_POSITIONS = {
    # Columbus (area 1). 1E/1W/1L/1M/1U/1X keep their stock ids: stock IND
    # and CVG scenarios hand off to 11U and 11L.
    "1N": {"callsign": "CMH_N_APP", "frequency": 125950, "radio_name": "Columbus Approach"},
    "1P": {"callsign": "CMH_P_APP", "frequency": 120200, "radio_name": "Columbus Approach"},
    "1S": {"callsign": "CMH_S_APP", "frequency": 134000, "radio_name": "Columbus Approach"},
    "1F": {"callsign": "CMH_F_APP", "frequency": 118200, "radio_name": "Columbus Approach"},
    "1L": {"callsign": "CMH_L_APP", "frequency": 132300, "radio_name": "Columbus Approach"},
    "1E": {"callsign": "CMH_E_TWR", "frequency": 132700, "radio_name": "Columbus Tower"},
    "1W": {"callsign": "CMH_W_TWR", "frequency": 127525, "radio_name": "Columbus Tower"},
    # Dayton sectors of Columbus TRACON
    "1X": {"callsign": "DAY_X_APP", "frequency": 118850, "radio_name": "Columbus Approach"},
    "1U": {"callsign": "DAY_U_APP", "frequency": 134450, "radio_name": "Columbus Approach"},
    "1M": {"callsign": "DAY_M_APP", "frequency": 120925, "radio_name": "Columbus Approach"},
}

LISTED = {
    "1N": "Columbus North: DUBLN1/CBUSS2 arrivals, North/East departures (CMH 28R/10L), OSU",
    "1P": "Columbus East: CLPRR4 arrivals",
    "1S": "Columbus South: JAKTZ2/SCRLT3 arrivals, South/West departures (CMH 28L/10R)",
    "1F": "Columbus Final",
    "1L": "Rickenbacker: LCK, TZR",
    "1X": "Dayton Final",
    "1M": "Dayton East/North: DANEI3 and ROD arrivals",
    "1U": "Dayton South/West: HICKS and west arrivals, DAY departures",
}

VIDEO_MAPS = [
    "Columbus RWY 28s", "Columbus RWY 10s", "CMH 3 NM MVA", "CMH Class C/D",
    "Dayton RWY 18/24s", "Dayton RWY 6s",
    "CMH TRACON Boundary", "CMH 5 NM MVA",
    "Columbus ILS RWY 28 Fixes", "Columbus ILS RWY 10 Fixes",
    "Dayton ILS RWY 18/24 Fixes", "DAY ILS 6L Fixes",
    "CMH Primary RVM", "CMH Secondary RVM",
    "ZID CMH CLPRR STAR", "ZID CMH DUBLN STAR", "ZID CMH JAKTZ STAR", "ZID CMH SCRLT STAR",
    "ZID DAY DANEI STAR", "ZID DAY KEKEE STAR",
    "CMH RNAV Y RWY 28L", "CMH RNAV Y RWY 28R", "CMH RNAV Y RWY 10L", "CMH RNAV Y RWY 10R",
    "LCK RNAV RWY 23L", "LCK RNAV RWY 5L", "OSU RNAV RWY 27L", "OSU RNAV RWY 9R",
    "TZR RNAV RWY 22", "TZR RNAV RWY 4",
    "DAY RNAV Y RWY 24R", "DAY RNAV Y RWY 6L",
    "FFO RNAV RWY 23L", "FFO RNAV RWY 5L", "MGY RNAV RWY 2/20",
    "CMH Cab", "DAY Cab", "LCK Cab",
]

CMH_IN = {"DUBLN1": "1N", "CBUSS2": "1N", "CLPRR4": "1P", "JAKTZ2": "1S", "SCRLT3": "1S"}
DAY_IN = {"DANEI3": "1M", "DAY.N": "1M", "DAY.S": "1U", "DAY.W": "1U"}

def cmh_deps(flow):
    if flow == "W":
        return {"KCMH/28R": "1N", "KCMH/28L": "1S", "KLCK": "1L", "KOSU": "1N"}
    return {"KCMH/10L": "1N", "KCMH/10R": "1S", "KLCK": "1L", "KOSU": "1N"}

def day_deps(flow):
    if flow == "SW":
        return {"KDAY/24L": "1U", "KDAY/18": "1U"}
    return {"KDAY/6R": "1M", "KDAY/36": "1U"}

CMH_CONS = {"1N": ["1P", "1S", "1F", "1L"]}
DAY_CONS = {"1X": ["1U", "1M"]}
ALL_CONS = {"1N": ["1P", "1S", "1F", "1L", "1X"], "1X": ["1U", "1M"]}

def conf(inb, deps, cons, listed):
    return {"inbound_assignments": inb, "departure_assignments": deps,
            "default_consolidation": cons, "listed_positions": listed}

CMH_LISTED = {k: LISTED[k] for k in ["1N", "1P", "1S", "1F", "1L"]}
DAY_LISTED = {k: LISTED[k] for k in ["1X", "1M", "1U"]}

CONFIGURATIONS = {
    "CW": conf(CMH_IN, cmh_deps("W"), CMH_CONS, CMH_LISTED),
    "CE": conf(CMH_IN, cmh_deps("E"), CMH_CONS, CMH_LISTED),
    "DS": conf(DAY_IN, day_deps("SW"), DAY_CONS, DAY_LISTED),
    "DN": conf(DAY_IN, day_deps("NE"), DAY_CONS, DAY_LISTED),
    "XW": conf({**CMH_IN, **DAY_IN}, {**cmh_deps("W"), **day_deps("SW")}, ALL_CONS, LISTED),
    "XE": conf({**CMH_IN, **DAY_IN}, {**cmh_deps("E"), **day_deps("NE")}, ALL_CONS, LISTED),
}

SCRATCHPADS = {"RDBUV": "RDB", "OWEBO": "OWB", "POBSE": "POB", "PKACZ": "PKA",
               "TRIVO": "TRI", "WIPOT": "WIP", "WAMBO": "WAM", "ROD": "ROD"}

facility = {
    "control_positions": CONTROL_POSITIONS,
    "facility_adaptations": {
        "center": "KCMH",
        "range": 50,
        "max_distance": 150,
        "video_map_file": "videomaps/ZID-stars.mappack",
        "lists": {"ssa": {"system_altimeter": "KCMH", "altimeters": ["KCMH", "KDAY", "KLCK"]}},
        "radar_sites": {
            "CMH": {"char": "C", "position": "39.9973,-82.8853", "elevation": 815,
                    "primary_range": 60, "secondary_range": 120, "silence_angle": 30, "slope_angle": 0.175},
            "DAY": {"char": "D", "position": "39.9002,-84.2245", "elevation": 1009,
                    "primary_range": 60, "secondary_range": 120, "silence_angle": 30, "slope_angle": 0.175},
        },
        "scratchpads": SCRATCHPADS,
        "datablocks": {"display_rnav_symbol": True, "allow_long_scratchpad": True},
        "untracked_position_symbol_overrides": {"beacon_codes": "1200", "symbol": "V"},
        "areas": {"1": {"video_maps": VIDEO_MAPS}},
        "configurations": CONFIGURATIONS,
    },
    "handoff_ids": [
        {"id": "CLE", "prefix": "2"},
        {"id": "CVG", "prefix": "6"},
        {"id": "FWA", "prefix": "4"},
        {"id": "IND", "prefix": "5"},
        {"id": "TOL", "prefix": "3"},
        {"id": "ZAU", "prefix": "G"},
        {"id": "ZID", "prefix": "C"},
        {"id": "ZOB", "prefix": "O"},
    ],
}

# ---------------------------------------------------------------- airports

def appr(ids):
    return {k: {"cifp_id": v} for k, v in ids.items()}

KCMH_APPROACHES = appr({
    "I0L": "I10L", "I0R": "I10R", "I8L": "I28L", "I8R": "I28R",
    "R0L": "RY10L", "R0R": "RY10R", "R8L": "RY28L", "R8R": "RY28R",
    "Z0L": "RZ10L", "Z0R": "RZ10R", "Z8L": "RZ28L", "Z8R": "RZ28R",
})
KLCK_APPROACHES = appr({"I5L": "I5L", "I3L": "I23L", "R5L": "R5L", "R5R": "R5R", "R3L": "R23L", "R3R": "R23R"})
KOSU_APPROACHES = appr({"I9R": "I9R", "R9R": "R9R", "R7L": "R27L"})
KDAY_APPROACHES = appr({
    "I4R": "I24R", "I4L": "I24L", "I6L": "I6L", "I18": "I18",
    "R4R": "RY24R", "Z4R": "RZ24R", "R6L": "RY6L", "Z6L": "RZ6L",
    "R4L": "R24L", "R6R": "R6R", "R18": "R18", "R36": "R36",
})

def dep_route(heading, alt=5000, opp=None):
    return {"cleared_altitude": alt, "waypoints": f"{opp}/h{heading:03d}"}

CMH_EXIT_CAT = {"RDBUV": "North", "OWEBO": "East", "POBSE": "South", "PKACZ": "West"}

KCMH_DEP_ROUTES = {
    # West flow: 28R (north runway) takes North/East gates, 28L South/West.
    "28R": {"RDBUV": dep_route(320, opp="KCMH-10L"), "OWEBO": dep_route(340, opp="KCMH-10L"),
            "PKACZ": dep_route(285, opp="KCMH-10L"), "POBSE": dep_route(240, opp="KCMH-10L")},
    "28L": {"POBSE": dep_route(230, opp="KCMH-10R"), "PKACZ": dep_route(270, opp="KCMH-10R"),
            "RDBUV": dep_route(310, opp="KCMH-10R"), "OWEBO": dep_route(320, opp="KCMH-10R")},
    # East flow: 10L (north) North/East, 10R South/West.
    "10L": {"RDBUV": dep_route(40, opp="KCMH-28R"), "OWEBO": dep_route(90, opp="KCMH-28R"),
            "PKACZ": dep_route(10, opp="KCMH-28R"), "POBSE": dep_route(140, opp="KCMH-28R")},
    "10R": {"POBSE": dep_route(150, opp="KCMH-28L"), "PKACZ": dep_route(190, opp="KCMH-28L"),
            "OWEBO": dep_route(120, opp="KCMH-28L"), "RDBUV": dep_route(60, opp="KCMH-28L")},
}

def dep(dest, exit, route, *airlines, fleet=None, alt=None):
    d = {"destination": dest, "exit": exit, "waypoints": route, "airlines": al(*airlines, fleet=fleet)}
    if alt: d["altitude"] = alt
    return d

KCMH_DEPARTURES = [
    # North (RDBUV)
    dep("KDTW", "RDBUV", "RDBUV NOWZU EEEZI BONZZ BONZZ2", "DAL", "EDV", "SKW", alt=[15000, 17000]),
    dep("KEWR", "RDBUV", "RDBUV NOWZU WWSHR Q29 DORET J584 SLT FQM3", "UAL", "SKW"),
    dep("KLGA", "RDBUV", "RDBUV WWSHR SPYDY Q186 WEVEL ETG MIP4", "AAL", "DAL", "RPA", "SWA"),
    dep("KJFK", "RDBUV", "RDBUV NOWZU DJB JHW Q476 WLKES PUCKY1", "DAL", "EDV"),
    dep("CYYZ", "RDBUV", "RDBUV NOWZU JUSEP DJB QWERI NUBER6", "JZA", "ACA"),
    dep("KTEB", "RDBUV", "RDBUV NOWZU DJB JHW LVZ5", "EJA", "LXJ"),
    # East (OWEBO)
    dep("KBOS", "OWEBO", "OWEBO HLG WIGGZ Q190 PONCT JFUND2", "SWA", "DAL", "AAL"),
    dep("KBWI", "OWEBO", "OWEBO NUSMM ANTHM5", "SWA"),
    dep("KDCA", "OWEBO", "OWEBO AIR BUCKO FRDMM7", "AAL", "RPA", "DAL"),
    dep("KPHL", "OWEBO", "OWEBO HLG JST BOJID4", "AAL", "PDT"),
    dep("KIAD", "OWEBO", "OWEBO AIR MGW GIBBZ6", "UAL", "SKW"),
    # South (POBSE)
    dep("KATL", "POBSE", "POBSE OHIOS KTRYN ONDRE1", "DAL", "SWA", "EDV"),
    dep("KBNA", "POBSE", "POBSE OHIOS YOCKY CUTRR PASLY5", "SWA"),
    dep("KCLT", "POBSE", "POBSE OHIOS TAFTT PARQR6", "AAL", "PDT", "ENY"),
    dep("KMCO", "POBSE", "POBSE OHIOS HVQ Q147 BURGG IRQ WHYYT GRNCH5", "SWA", "FFT", "MXY"),
    dep("KTPA", "POBSE", "POBSE OHIOS IRQ WIGVO TEUFL BAAMF DADES2", "SWA", "MXY"),
    dep("KFLL", "POBSE", "POBSE OHIOS HVQ Q147 BURGG QUIWE Q93 FISHO Q93 GURGE Q93 PRMUS CUUDA3", "SWA", "NKS"),
    dep("KRSW", "POBSE", "POBSE OHIOS DOOGE IRQ CYNTA SHFTY6", "SWA", "MXY"),
    dep("KMIA", "POBSE", "POBSE OHIOS HVQ Q147 BURGG QUIWE Q93 FISHO Q93 GURGE Q93 DEBRL CSTAL3", "AAL"),
    # West (PKACZ)
    dep("KORD", "PKACZ", "PKACZ TARRY FWA WATSN4", "UAL", "AAL", "SKW", "ENY"),
    dep("KMDW", "PKACZ", "PKACZ TARRY ROD FWA PANGG7", "SWA"),
    dep("KMSP", "PKACZ", "PKACZ TARRY ROD FWA KAMMA KKILR4", "DAL", "SKW"),
    dep("KDEN", "PKACZ", "PKACZ TARRY ROD EDENS DSM OBH BRWRY LAWGR4", "UAL", "SWA", "FFT"),
    dep("KDFW", "PKACZ", "PKACZ TARRY PXV J131 LIT FEWWW SEEVR4", "AAL"),
    dep("KDAL", "PKACZ", "PKACZ TARRY DQN TTH FAM FSM CAMAL HIBIL3", "SWA"),
    dep("KAUS", "PKACZ", "PKACZ TARRY OWB JBR LIT TXK WINDU SEWZY6", "SWA"),
    dep("KHOU", "PKACZ", "PKACZ TARRY DQN HEVAN SIDAE Q29 HARES SWEUP WAPPL7", "SWA"),
    dep("KIAH", "PKACZ", "PKACZ TARRY CVG TIIDE Q31 UJM Q31 DHART SWEUP ZEEKK3", "UAL"),
    dep("KLAS", "PKACZ", "PKACZ TARRY CREEP J80 VHP AXC STJ TKO DANDD KD54U TAYLR MTJ DEANN TYEGR CHOWW4", "SWA"),
    dep("KPHX", "PKACZ", "PKACZ TARRY CREEP TTH DIRTT TYGER KK51E RASCL KK42Y KENTO ZUN EAGUL6", "SWA", "AAL"),
    dep("KSTL", "PKACZ", "PKACZ TARRY DQN VHP AARCH2", "SWA"),
]

KLCK_DEP_ROUTES = {
    "23L": {"POBSE": dep_route(200, opp="KLCK-5R"), "PKACZ": dep_route(250, opp="KLCK-5R")},
    "5R": {"POBSE": dep_route(110, opp="KLCK-23L"), "PKACZ": dep_route(320, opp="KLCK-23L")},
}
KLCK_DEPARTURES = [
    dep("KSFB", "POBSE", "POBSE OHIOS HVQ Q147 BURGG IRQ WHYYT GRNCH5", "AAY"),
    dep("KPIE", "POBSE", "POBSE OHIOS IRQ WIGVO TEUFL BAAMF DADES2", "AAY"),
    dep("KMEM", "PKACZ", "PKACZ TARRY PXV", "FDX"),
    dep("KSDF", "PKACZ", "PKACZ TARRY CVG", "UPS"),
]

KOSU_DEP_ROUTES = {
    "27L": {"RDBUV": dep_route(300, opp="KOSU-9R"), "POBSE": dep_route(240, opp="KOSU-9R"),
            "PKACZ": dep_route(270, opp="KOSU-9R"), "OWEBO": dep_route(330, opp="KOSU-9R")},
    "9R": {"RDBUV": dep_route(30, opp="KOSU-27L"), "POBSE": dep_route(150, opp="KOSU-27L"),
           "PKACZ": dep_route(330, opp="KOSU-27L"), "OWEBO": dep_route(90, opp="KOSU-27L")},
}
KOSU_DEPARTURES = [
    dep("KTEB", "RDBUV", "RDBUV NOWZU DJB JHW LVZ5", "EJA", "LXJ"),
    dep("KPBI", "POBSE", "POBSE OHIOS HVQ Q147 BURGG IRQ", "EJA"),
    dep("KMDW", "PKACZ", "PKACZ TARRY ROD FWA PANGG7", "EJA"),
]

DAY_EXIT_CAT = {"TRIVO": "South", "WIPOT": "East", "WAMBO": "West", "ROD": "North"}
KDAY_DEP_ROUTES = {
    "24L": {"WAMBO": dep_route(260, opp="KDAY-6R"), "ROD": dep_route(300, opp="KDAY-6R"),
            "TRIVO": dep_route(220, opp="KDAY-6R"), "WIPOT": dep_route(300, opp="KDAY-6R")},
    "18": {"TRIVO": dep_route(200, opp="KDAY-36"), "WIPOT": dep_route(150, opp="KDAY-36"),
           "WAMBO": dep_route(230, opp="KDAY-36"), "ROD": dep_route(270, opp="KDAY-36")},
    "6R": {"ROD": dep_route(30, opp="KDAY-24L"), "WIPOT": dep_route(90, opp="KDAY-24L"),
           "TRIVO": dep_route(120, opp="KDAY-24L"), "WAMBO": dep_route(330, opp="KDAY-24L")},
    "36": {"WAMBO": dep_route(320, opp="KDAY-18"), "ROD": dep_route(10, opp="KDAY-18"),
           "TRIVO": dep_route(270, opp="KDAY-18"), "WIPOT": dep_route(60, opp="KDAY-18")},
}
KDAY_DEPARTURES = [
    dep("KATL", "TRIVO", "TRIVO CVG IIU HITMN NEWBB IHAVE MTHEW CHPPR1", "DAL", "EDV"),
    dep("KCLT", "TRIVO", "TRIVO CVG FLM TAFTT PARQR6", "AAL", "PDT"),
    dep("KDFW", "TRIVO", "TRIVO CVG PXV J131 LIT MEEOW FEWWW SEEVR4", "AAL", "ENY"),
    dep("KDCA", "WIPOT", "WIPOT FLYIR APE J30 BUCKO FRDMM7", "AAL", "RPA"),
    dep("KIAD", "WIPOT", "WIPOT FLYIR APE AIR MGW GIBBZ6", "UAL", "SKW"),
    dep("KPHL", "WIPOT", "WIPOT FLYIR APE JST BOJID4", "AAL", "PDT"),
    dep("KDEN", "WAMBO", "WAMBO VHP AXC HYS J24 OATHE CLASH5", "UAL"),
    dep("KORD", "ROD", "ROD FWA WATSN4", "UAL", "AAL", "SKW", "ENY", alt=[16000, 22000]),
]

def vfr(rate, fleet="lightGA"):
    return {"vfr": {"random_routes": {"rate": rate, "fleet": fleet}}}

def airports_cmh():
    return {
        "KCMH": {"approaches": KCMH_APPROACHES, "departure_routes": KCMH_DEP_ROUTES,
                 "departures": KCMH_DEPARTURES, "exit_categories": CMH_EXIT_CAT,
                 "omit_arrival_scratchpad": True, "tower_list": 1},
        "KLCK": {"approaches": KLCK_APPROACHES, "departure_routes": KLCK_DEP_ROUTES,
                 "departures": KLCK_DEPARTURES, "exit_categories": {"POBSE": "South", "PKACZ": "West"},
                 "hold_for_release": True, "tower_list": 2, **vfr(0.6)},
        "KOSU": {"approaches": KOSU_APPROACHES, "departure_routes": KOSU_DEP_ROUTES,
                 "departures": KOSU_DEPARTURES, "exit_categories": CMH_EXIT_CAT,
                 "hold_for_release": True, "tower_list": 3, **vfr(3.0)},
        "KTZR": vfr(2.0),
        "KLHQ": vfr(1.2),
        "KDLZ": vfr(1.0),
        "KMRT": vfr(0.6),
        "KVTA": vfr(0.8),
        "KUYF": vfr(0.4),
        "KMNN": vfr(0.5),
    }

def airports_day():
    return {
        "KDAY": {"approaches": KDAY_APPROACHES, "departure_routes": KDAY_DEP_ROUTES,
                 "departures": KDAY_DEPARTURES, "exit_categories": DAY_EXIT_CAT,
                 "omit_arrival_scratchpad": True, "tower_list": 1},
        "KMGY": vfr(2.0),
        "I19": vfr(1.2),
        "I73": vfr(0.8),
        "KSGH": vfr(0.8),
        "KVES": vfr(0.4),
        "KHAO": vfr(0.8),
        "KAXV": vfr(0.4),
    }

# ---------------------------------------------------------------- arrivals

def star_arr(star, spawn, init_ctrl, alt, airlines, airports, speed=280, rnav=True, cleared=None):
    a = {"star": star, "spawn": spawn, "initial_controller": init_ctrl,
         "initial_altitude": alt, "initial_speed": speed, "is_rnav": rnav,
         "expect_approach": None, "airports": airports, "airlines": airlines,
         "flight_strip_route": f"/. {spawn.split('@')[0]}.{star}"}
    if cleared: a["cleared_altitude"] = cleared
    return a

def merge(*dicts):
    out = {}
    for d in dicts:
        for k, v in d.items():
            out.setdefault(k, []).extend(v)
    return out

LCK = "KLCK"
OSU = "KOSU"

def cmh_flows():
    return {
        "DUBLN1": {"arrivals": [
            star_arr("DUBLN1", "CHDRS@0.0", "O03", 13000,
                     merge(arr_airlines("KCMH", [("UAL", "KORD"), ("AAL", "KORD"), ("SKW", "KORD"), ("ENY", "KORD"),
                                                 ("SWA", "KMDW"), ("DAL", "KMSP"), ("UAL", "KDEN"), ("SWA", "KDEN"),
                                                 ("FFT", "KDEN")]),
                           arr_airlines(OSU, [("EJA", "KMDW")])),
                     ["KCMH", OSU]),
            star_arr("DUBLN1", "FBC@0.4", "O03", 11000,
                     arr_airlines("KCMH", [("DAL", "KDTW"), ("EDV", "KDTW"), ("SKW", "KDTW")]), ["KCMH"]),
            star_arr("DUBLN1", "CYRAH@0.0", "C32", 13000,
                     arr_airlines("KCMH", [("SWA", "KSTL"), ("SWA", "KLAS"), ("SWA", "KPHX"), ("AAL", "KPHX")]),
                     ["KCMH"]),
        ]},
        "CBUSS2": {"arrivals": [
            star_arr("CBUSS2", "WAAHU@0.0", "O04", 13000,
                     arr_airlines("KCMH", [("ACA", "CYYZ"), ("JZA", "CYYZ")]), ["KCMH"]),
        ]},
        "CLPRR4": {"arrivals": [
            star_arr("CLPRR4", "MEYRR@0.3", "O20", 17000,
                     merge(arr_airlines("KCMH", [("AAL", "KLGA"), ("DAL", "KLGA"), ("RPA", "KLGA"), ("SWA", "KLGA"),
                                                 ("UAL", "KEWR"), ("DAL", "KJFK"), ("SWA", "KBOS"), ("AAL", "KBOS"),
                                                 ("AAL", "KPHL"), ("PDT", "KPHL")]),
                           arr_airlines(OSU, [("EJA", "KTEB"), ("LXJ", "KTEB")])),
                     ["KCMH", OSU]),
            star_arr("CLPRR4", "ZANDR@0.4", "O20", 14000,
                     arr_airlines("KCMH", [("EJA", "KTEB"), ("LXJ", "KTEB")]), ["KCMH"]),
        ]},
        "SCRLT3": {"arrivals": [
            star_arr("SCRLT3", "HACKS@0.7", "C24", 16000,
                     arr_airlines("KCMH", [("AAL", "KDCA"), ("RPA", "KDCA"), ("SWA", "KBWI"), ("UAL", "KIAD"),
                                           ("SKW", "KIAD")]), ["KCMH"]),
            star_arr("SCRLT3", "ZEDNO@0.2", "C24", 15000,
                     merge(arr_airlines("KCMH", [("DAL", "KATL"), ("SWA", "KATL"), ("AAL", "KCLT"), ("PDT", "KCLT"),
                                                 ("SWA", "KMCO"), ("FFT", "KMCO"), ("MXY", "KTPA"), ("SWA", "KTPA"),
                                                 ("SWA", "KFLL"), ("NKS", "KFLL"), ("AAL", "KMIA"), ("SWA", "KRSW")]),
                           arr_airlines(LCK, [("AAY", "KSFB"), ("AAY", "KPIE"), ("AAY", "KPGD")])),
                     ["KCMH", LCK]),
        ]},
        "JAKTZ2": {"arrivals": [
            star_arr("JAKTZ2", "PODGY@0.2", "C30", 17000,
                     merge(arr_airlines("KCMH", [("SWA", "KBNA"), ("SWA", "KHOU"), ("AAL", "KDFW"), ("SWA", "KDAL"),
                                                 ("SWA", "KAUS"), ("UAL", "KIAH")]),
                           arr_airlines(LCK, [("FDX", "KMEM"), ("UPS", "KSDF")])),
                     ["KCMH", LCK]),
        ]},
    }

# Dayton arrivals that don't fly a STAR in the CIFP
DAY_FIXES = {
    "_DAYS_HO": dms(*along("HICKS", "FIITZ", 0.35)),
    "_DAYN_SP": dms(*toward("ROD", "FWA", 25)),
    "_DAYN_HO": dms(*toward("ROD", "FWA", 15)),
    "_DAYW_SP": dms(*toward("KDAY", "SHB", 42)),
    "_DAYW_HO": dms(*toward("KDAY", "SHB", 32)),
    "_DAYW_FN": dms(*toward("KDAY", "SHB", 18)),
}

def manual_arr(waypoints, init_ctrl, alt, airlines, airports, strip, speed=270, assigned=None):
    a = {"waypoints": waypoints, "initial_controller": init_ctrl, "initial_altitude": alt,
         "initial_speed": speed, "expect_approach": None, "airports": airports,
         "airlines": airlines, "flight_strip_route": strip}
    if assigned: a["assigned_altitude"] = assigned
    return a

def day_flows():
    return {
        "DANEI3": {"arrivals": [
            star_arr("DANEI3", "COOJO@0.3", "C88", 11000,
                     arr_airlines("KDAY", [("AAL", "KDCA"), ("RPA", "KDCA"), ("UAL", "KIAD"), ("SKW", "KIAD"),
                                           ("AAL", "KPHL"), ("PDT", "KPHL")]),
                     ["KDAY"], rnav=False, cleared=10000),
        ]},
        "DAY.S": {"arrivals": [
            manual_arr("HICKS _DAYS_HO/ho FIITZ/a5000/h010", "C31", 11000,
                       arr_airlines("KDAY", [("DAL", "KATL"), ("EDV", "KATL"), ("AAL", "KCLT"), ("PDT", "KCLT"),
                                             ("AAL", "KDFW"), ("ENY", "KDFW")]),
                       ["KDAY"], "/. HICKS FIITZ", assigned=7000),
        ]},
        "DAY.N": {"arrivals": [
            manual_arr("_DAYN_SP _DAYN_HO/ho ROD/a5000/h200", "C32", 11000,
                       arr_airlines("KDAY", [("UAL", "KORD"), ("AAL", "KORD"), ("SKW", "KORD"), ("ENY", "KORD")]),
                       ["KDAY"], "/. FWA ROD", assigned=7000),
        ]},
        "DAY.W": {"arrivals": [
            manual_arr("_DAYW_SP _DAYW_HO/ho _DAYW_FN/a5000/h090", "C88", 11000,
                       arr_airlines("KDAY", [("UAL", "KDEN"), ("AAY", "KLAS")]),
                       ["KDAY"], "/. SHB", assigned=7000),
        ]},
    }

# ---------------------------------------------------------------- scenarios

def scen(desc, config, center, rng, arrivals, departures, inbound, wind, maps):
    return {"description": desc, "configuration": config, "center": center, "range": rng,
            "arrival_runways": [{"airport": a, "runway": r} for a, r in arrivals],
            "departure_runways": [dict(airport=a, runway=r, rate=rate, **({"category": c} if c else {}))
                                  for a, r, rate, c in departures],
            "inbound_rates": inbound, "wind": {"direction": wind}, "default_maps": maps}

CMH_RATES = {"DUBLN1": {"KCMH": 7, "KOSU": 0.5}, "CBUSS2": {"KCMH": 2}, "CLPRR4": {"KCMH": 5, "KOSU": 0.5},
             "SCRLT3": {"KCMH": 5, "KLCK": 1}, "JAKTZ2": {"KCMH": 4, "KLCK": 1}}
DAY_RATES = {"DANEI3": {"KDAY": 3}, "DAY.S": {"KDAY": 3}, "DAY.N": {"KDAY": 2}, "DAY.W": {"KDAY": 1}}

def cmh_west():
    return dict(arr=[("KCMH", "28L"), ("KCMH", "28R"), ("KLCK", "23L"), ("KOSU", "27L")],
                dep=[("KCMH", "28R", 5, "North"), ("KCMH", "28R", 4, "East"),
                     ("KCMH", "28L", 5, "South"), ("KCMH", "28L", 4, "West"),
                     ("KLCK", "23L", 1, None), ("KOSU", "27L", 1, None)])

def cmh_east():
    return dict(arr=[("KCMH", "10R"), ("KCMH", "10L"), ("KLCK", "5R"), ("KOSU", "9R")],
                dep=[("KCMH", "10L", 5, "North"), ("KCMH", "10L", 4, "East"),
                     ("KCMH", "10R", 5, "South"), ("KCMH", "10R", 4, "West"),
                     ("KLCK", "5R", 1, None), ("KOSU", "9R", 1, None)])

def day_sw():
    return dict(arr=[("KDAY", "24R")],
                dep=[("KDAY", "24L", 3, "West"), ("KDAY", "24L", 2, "North"),
                     ("KDAY", "18", 3, "South"), ("KDAY", "18", 2, "East")])

def day_ne():
    return dict(arr=[("KDAY", "6L")],
                dep=[("KDAY", "6R", 2, "North"), ("KDAY", "6R", 2, "East"), ("KDAY", "6R", 3, "South"),
                     ("KDAY", "36", 3, "West")])

CMH_C, DAY_C, MID_C = "KCMH", "KDAY", "39.9496,-83.5558"

def write(path, obj):
    path = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
    print("wrote", path)

def main():
    write("configurations/ZID/CMH.json", facility)

    w, e = cmh_west(), cmh_east()
    write("scenarios/cmh.json", {
        "name": "Columbus Area", "tracon": "CMH",
        "default_scenario": "CMH - West Flow (28s)",
        "airports": airports_cmh(),
        "inbound_flows": cmh_flows(),
        "scenarios": {
            "CMH - West Flow (28s)": scen(
                "Columbus TRACON, CMH sectors combined on 1N. Land 28L/28R, depart 28R (North/East gates) "
                "and 28L (South/West gates). LCK 23L, OSU 27L satellites.",
                "CW", CMH_C, 40, w["arr"], w["dep"], CMH_RATES, "200-340",
                ["Columbus RWY 28s", "CMH 3 NM MVA", "CMH Class C/D"]),
            "CMH - East Flow (10s)": scen(
                "Columbus TRACON, CMH sectors combined on 1N. Land 10R/10L, depart 10L (North/East gates) "
                "and 10R (South/West gates). LCK 5R, OSU 9R satellites.",
                "CE", CMH_C, 40, e["arr"], e["dep"], CMH_RATES, "020-160",
                ["Columbus RWY 10s", "CMH 3 NM MVA", "CMH Class C/D"]),
        },
    })

    sw, ne = day_sw(), day_ne()
    write("scenarios/day.json", {
        "name": "Dayton Area", "tracon": "CMH",
        "default_scenario": "DAY - Southwest Flow (24s/18)",
        "fixes": DAY_FIXES,
        "airports": airports_day(),
        "inbound_flows": day_flows(),
        "scenarios": {
            "DAY - Southwest Flow (24s/18)": scen(
                "Dayton sectors of Columbus TRACON combined on 1X. Land 24R; depart 24L (West/North) and 18 "
                "(South/East).", "DS", DAY_C, 35, sw["arr"], sw["dep"], DAY_RATES, "170-300",
                ["Dayton RWY 18/24s", "CMH 3 NM MVA", "CMH Class C/D"]),
            "DAY - Northeast Flow (6s/36)": scen(
                "Dayton sectors of Columbus TRACON combined on 1X. Land 6L; depart 6R (North/East/South) and "
                "36 (West).", "DN", DAY_C, 35, ne["arr"], ne["dep"], DAY_RATES, "010-130",
                ["Dayton RWY 6s", "CMH 3 NM MVA", "CMH Class C/D"]),
        },
    })

    write("scenarios/cmhcombined.json", {
        "name": "CMH Combined", "tracon": "CMH",
        "default_scenario": "CMH Combined - West / DAY Southwest",
        "fixes": DAY_FIXES,
        "airports": {**airports_cmh(), **airports_day()},
        "inbound_flows": {**cmh_flows(), **day_flows()},
        "scenarios": {
            "CMH Combined - West / DAY Southwest": scen(
                "All of Columbus TRACON on 1N: CMH west flow (28s) and DAY southwest flow (24R/18).",
                "XW", MID_C, 55, w["arr"] + sw["arr"], w["dep"] + sw["dep"], {**CMH_RATES, **DAY_RATES},
                "200-300", ["Columbus RWY 28s", "Dayton RWY 18/24s", "CMH 3 NM MVA", "CMH Class C/D"]),
            "CMH Combined - East / DAY Northeast": scen(
                "All of Columbus TRACON on 1N: CMH east flow (10s) and DAY northeast flow (6L/36).",
                "XE", MID_C, 55, e["arr"] + ne["arr"], e["dep"] + ne["dep"], {**CMH_RATES, **DAY_RATES},
                "020-130", ["Columbus RWY 10s", "Dayton RWY 6s", "CMH 3 NM MVA", "CMH Class C/D"]),
        },
    })

if __name__ == "__main__":
    main()
