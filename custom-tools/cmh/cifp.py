"""Minimal FAA CIFP (ARINC 424) reader for gen.py: fix positions and procedure legs."""
import re, math, collections
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
_CIFP = os.environ.get("CIFP_TXT") or os.path.join(_HERE, "..", "..", "resources", "FAACIFP18.zst")
if _CIFP.endswith(".zst"):
    # resources/FAACIFP18.zst is a git lfs file: run "git lfs pull --include resources/FAACIFP18.zst".
    import zstandard
    with open(_CIFP, "rb") as f:
        L = zstandard.ZstdDecompressor().stream_reader(f).read().decode("latin-1").splitlines()
else:
    L = open(_CIFP, errors="ignore").read().splitlines()
def ll(lat,lon):
    try:
        la=(int(lat[1:3])+int(lat[3:5])/60+int(lat[5:9])/360000)*(1 if lat[0]=='N' else -1)
        lo=(int(lon[1:4])+int(lon[4:6])/60+int(lon[6:10])/360000)*(1 if lon[0]=='E' else -1)
        return la,lo
    except: return None
fix={}
for l in L:
    if len(l)<60: continue
    if l.startswith('SUSAEA'):
        p=ll(l[32:41],l[41:51]); 
        if p: fix.setdefault(l[13:18].strip(),p)
    elif l.startswith('SUSAD'):
        p=ll(l[32:41],l[41:51])
        if p: fix.setdefault(l[13:17].strip(),p)
    elif l.startswith('SUSAP') and l[12]=='C':
        p=ll(l[32:41],l[41:51])
        if p: fix.setdefault(l[13:18].strip(),p)
    elif l.startswith('SUSAP') and l[12]=='A':
        p=ll(l[32:41],l[41:51])
        if p: fix.setdefault(l[6:10].strip(),p)
def dist(a,b):
    a=fix.get(a,a); b=fix.get(b,b)
    dlat=(a[0]-b[0])*60; dlon=(a[1]-b[1])*60*math.cos(math.radians((a[0]+b[0])/2))
    return math.hypot(dlat,dlon)
def brg(a,b):
    a=fix.get(a,a); b=fix.get(b,b)
    dlat=(b[0]-a[0]); dlon=(b[1]-a[1])*math.cos(math.radians((a[0]+b[0])/2))
    return (math.degrees(math.atan2(dlon,dlat))+360)%360
def proc(apt,typ,name):
    """legs grouped by transition: list of (fix, alt desc, alt1, alt2, speed, pathterm)"""
    out=collections.OrderedDict()
    for l in L:
        if l.startswith('SUSAP '+apt) and l[12]==typ and l[13:19].strip()==name:
            tr=l[20:25].strip() or '-'
            fx=l[29:34].strip(); pt=l[47:49]; ad=l[82]; a1=l[84:89].strip(); a2=l[89:94].strip(); sp=l[99:102].strip()
            out.setdefault((l[19],tr),[]).append((fx,pt,ad,a1,a2,sp))
    return out
