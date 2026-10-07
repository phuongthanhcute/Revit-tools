"""Regression tests for the two fixed clusters. Hard asserts; exit code 1 on any failure."""
import os as _os
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
import math, random, sys
from unittest.mock import MagicMock
from fakerevit import *

ROOT = REPO + "/MEP_Tools.extension/HVAC.tab/Utilities.panel"
import os
CA, AH, SP = (os.environ.get("MUT_CA") or ROOT + "/Clash Avoid.pushbutton/script.py", ROOT + "/Auto Hangers.pushbutton/script.py", ROOT + "/Split Pipes.pushbutton/script.py")
fails = []
def check(name, cond, detail=""):
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond: fails.append(name)
def P(x, y, z): return XYZ(mm(x), mm(y), mm(z))
def seg(e): c = e.Location.Curve; return c.a, c.b

# ---------------------------------------------------------------- HANGERS (BUG-07/08/09)
def hangers(pipes, spacing="2000", fittings=None):
    doc = Doc(); doc.ActiveView = View3D(); doc.ActiveView.Id = "V"
    els = [doc.add(make_curve_elem(Pipe, P(*a), P(*b), {"Diameter": Param(mm(150))})) for a, b in pipes]
    sym = MagicMock(); sym.IsActive = True
    sc = {"selection": els, "sym": sym, "select": sym, "ask": {"Khoảng cách": spacing}, "slab_z": mm(4000),
          "fittings": [Box(P(*f[0]), P(*f[1])) for f in (fittings or [])]}
    return run(AH, doc, sc), doc, sc
def xs_of(doc): return [tomm(h.pt.X) for h in doc.placed]

print("=== Auto Hangers ===")
exp = {500: [250], 1120: [560], 1999: [999.5], 2000: [1000], 2001: [500.25, 1500.75], 3000: [750, 2250], 6000: [1000, 3000, 5000]}
for L, want in exp.items():
    r, doc, sc = hangers([((0, 0, 3000), (L, 0, 3000))]); got = xs_of(doc)
    check("L=%d" % L, r == "completed" and len(got) == len(want) and all(abs(a - b) < 0.01 for a, b in zip(got, want)), "-> %s" % [round(x, 2) for x in got])
# BUG-08 chain: pieces of 1120 now get a hanger each
r, doc, sc = hangers([((i * 1120, 0, 3000), ((i + 1) * 1120, 0, 3000)) for i in range(4)])
check("BUG-08 four 1120 pieces -> 4 hangers", len(doc.placed) == 4, "-> x=%s" % [round(x) for x in xs_of(doc)])
# property: bound inside a segment and across a joint, count == ceil(L/s)
random.seed(3); bad = 0; N = 400
for _ in range(N):
    L1, L2 = random.uniform(100, 12000), random.uniform(100, 12000); s = random.choice([500, 1000, 2000, 3000])
    r, doc, sc = hangers([((0, 0, 3000), (L1, 0, 3000)), ((L1, 0, 3000), (L1 + L2, 0, 3000))], spacing=str(s))
    xs = xs_of(doc); k1 = max(1, math.ceil(L1 / s - 1e-9)); k2 = max(1, math.ceil(L2 / s - 1e-9))
    if len(xs) != k1 + k2: bad += 1; continue
    gaps = [b - a for a, b in zip(xs, xs[1:])]
    if max(gaps) > s + 1e-6 or min(gaps) < 1e-6: bad += 1
    if not (0 < xs[0] and xs[-1] < L1 + L2): bad += 1
check("property: %d random 2-pipe runs (count==ceil(L/s), every gap<=s incl. across joint, none coincident)" % N, bad == 0, "violations=%d" % bad)
# nudge test (BUG-10) is a different cluster -> expected to remain
r, doc, sc = hangers([((0, 0, 3000), (6000, 0, 3000))], fittings=[((2900, -200, 2800), (3100, 200, 3200))])
print("[info] BUG-10 (not in this cluster) still present: hanger x=%s" % [round(x) for x in xs_of(doc)])

# ---------------------------------------------------------------- CLASH AVOID (BUG-16/17/18)
class Obs:
    def __init__(s, mn, mx): s.bbox = Box(P(*mn), P(*mx)); s.Id = "OBS"
    def get_BoundingBox(s, w): return s.bbox
def clash(a, b, obs, direction="Đi lên trên (Up)", h=300):
    doc = Doc(); doc.ActiveView = View()
    duct = doc.add(make_curve_elem(Duct, P(*a), P(*b), {"Width": Param(mm(600)), "Height": Param(mm(h))}))
    doc.els["OBS"] = Obs(*obs); sc = {"picks": [duct.Id, "OBS"], "select": direction}
    r = run(CA, doc, sc); D = (P(*b) - P(*a)).Normalize()
    ds = sorted([e for e in doc.els.values() if isinstance(e, Duct)], key=lambda e: e.Location.Curve.a.DotProduct(D))
    return r, doc, ds, sc

print("\n=== Clash Avoid ===")
T = ((9850, -3000, 2900), (10150, 3000, 3200))   # 300 wide beam crossing the duct
r, doc, ds, sc = clash((0, 0, 3000), (20000, 0, 3000), T)
span = tomm(seg(ds[3])[1].X - seg(ds[1])[0].X)
check("BUG-16 crossing beam: detour footprint = 400 + 2*400", abs(span - 1200) < 0.5, "-> %.1f mm (was 6907)" % span)
check("BUG-16 4 elbows, all 45 deg", len(doc.elbows) == 4 and all(abs(e[2] - 45) < 0.01 for e in doc.elbows), "-> %s" % [e[2] for e in doc.elbows])
r, doc, ds, sc = clash((0, 0, 3000), (20000, 0, 3000), ((1850, -3000, 2900), (2150, 3000, 3200)))
check("BUG-16 beam 2 m from duct start is now built", r == "completed" and len(ds) == 5, "-> run=%s pieces=%d first piece=%.0f mm" % (r, len(ds), tomm(ds[0].Location.Curve.Length) if ds else -1))
r, doc, ds, sc = clash((0, 0, 3000), (20000, 0, 3000), ((7000, -150, 2900), (13000, 150, 3200)))
margin = 7000 - tomm(seg(ds[1])[1].X)
check("beam along duct: margin to obstacle face = 50 mm exactly", abs(margin - 50) < 0.5, "-> %.2f mm (was 53.7)" % margin)

# BUG-17 sloped ducts: all four bends 45, clearance over the whole obstacle span
def route_z_at_x(ds, x_mm):
    """centerline z of the mid-leg (ds[2]) at horizontal position x"""
    a, b = seg(ds[2]); ax, bx = tomm(a.X), tomm(b.X); t = (x_mm - ax) / (bx - ax)
    return tomm(a.Z) + t * (tomm(b.Z) - tomm(a.Z))
for slope in [2.86, 5.71, 15, 30]:
    t = math.radians(slope); L = 20000; cx = 10000; zc = 3000 + cx * math.tan(t)
    for direction in ["Đi lên trên (Up)", "Đi xuống dưới (Down)"]:
        up = direction.startswith("Đi lên")
        obs = ((cx - 150, -3000, zc - 150 if up else zc - 300), (cx + 150, 3000, zc + 300 if up else zc + 150))
        r, doc, ds, sc = clash((0, 0, 3000), (L * math.cos(t), 0, 3000 + L * math.sin(t)), obs, direction)
        angles = [e[2] for e in doc.elbows]
        ok_ang = len(angles) == 4 and all(abs(a - 45) < 0.01 for a in angles)
        zs = [route_z_at_x(ds, x) for x in range(cx - 150, cx + 151, 10)]
        need = (obs[1][2] + 50 + 150) if up else (obs[0][2] - 50 - 150)
        ok_clear = (min(zs) >= need - 0.5) if up else (max(zs) <= need + 0.5)
        check("BUG-17 slope %.2f %-5s: bends 45, clearance over span" % (slope, "Up" if up else "Down"), r == "completed" and ok_ang and ok_clear,
              "-> angles=%s mid-leg z in span [%.0f..%.0f] need %s %.0f" % (sorted(set(angles)), min(zs), max(zs), ">=" if up else "<=", need))

# BUG-18 vertical / too steep -> refused, nothing changed
r, doc, ds, sc = clash((0, 0, 0), (0, 0, 10000), ((-300, -300, 4800), (300, 300, 5200)))
check("BUG-18 vertical duct refused, model untouched", r == "exit" and len(ds) == 1 and len(doc.elbows) == 0, "-> %s | %s" % (r, sc.get("alerts", [""])[-1][:60]))
t = math.radians(70); r, doc, ds, sc = clash((0, 0, 0), (10000 * math.cos(t), 0, 10000 * math.sin(t)), ((-300, -300, 4800), (300, 300, 5200)))
check("BUG-18 70 deg riser refused", r == "exit" and len(doc.elbows) == 0)
t = math.radians(55); r, doc, ds, sc = clash((0, 0, 0), (20000 * math.cos(t), 0, 20000 * math.sin(t)), ((6000, -300, 8500), (6600, 300, 9000)))
check("55 deg duct still handled (below 60 deg limit)", r == "completed" and len(doc.elbows) == 4 and all(abs(e[2] - 45) < 0.01 for e in doc.elbows), "-> %s %s" % (r, [e[2] for e in doc.elbows]))

# property test: random slope, random yaw in plan, random obstacle, Up/Down
random.seed(11); bad = []; N = 300
for i in range(N):
    slope = math.radians(random.uniform(-40, 40)); yaw = math.radians(random.uniform(0, 360)); L = 40000
    D = XYZ(math.cos(slope) * math.cos(yaw), math.cos(slope) * math.sin(yaw), math.sin(slope))
    a = XYZ(0, 0, mm(3000)); b = a + D * mm(L)
    c = a + D * mm(random.uniform(12000, 28000))
    w, d_, hh = random.uniform(200, 6000), random.uniform(200, 6000), random.uniform(200, 800)
    up = random.random() < 0.5; zc = c.Z + mm(random.uniform(-hh / 2, hh / 2))  # obstacle centre may sit above/below the duct axis (but the box still crosses it)
    mn = (tomm(c.X) - w / 2, tomm(c.Y) - d_ / 2, tomm(zc) + (-hh / 2)); mx = (tomm(c.X) + w / 2, tomm(c.Y) + d_ / 2, tomm(zc) + hh / 2)
    doc = Doc(); doc.ActiveView = View()
    duct = doc.add(make_curve_elem(Duct, a, b, {"Width": Param(mm(600)), "Height": Param(mm(300))})); doc.els["OBS"] = Obs(mn, mx)
    sc = {"picks": [duct.Id, "OBS"], "select": "Đi lên trên (Up)" if up else "Đi xuống dưới (Down)"}
    r = run(CA, doc, sc)
    ds = sorted([e for e in doc.els.values() if isinstance(e, Duct)], key=lambda e: e.Location.Curve.a.DotProduct(D))
    why = None
    if r != "completed" or len(ds) != 5: why = "run=%s pieces=%d" % (r, len(ds))
    elif len(doc.elbows) != 4 or any(abs(e[2] - 45) > 0.01 for e in doc.elbows): why = "angles %s" % [e[2] for e in doc.elbows]
    elif any(seg(ds[i])[1].DistanceTo(seg(ds[i + 1])[0]) > 1e-9 for i in range(4)): why = "not contiguous"
    else:
        # mid-leg must be parallel to D, cover every bbox corner projection with >=50mm margin, and clear the box vertically
        mb, mc = seg(ds[2]); dv = (mc - mb).Normalize()
        Dh = XYZ(D.X, D.Y, 0).Normalize()
        if dv.DotProduct(D) < 1 - 1e-9: why = "mid-leg not parallel to duct"
        else:
            cps = [XYZ(mm(x), mm(y), 0).DotProduct(Dh) for x in (mn[0], mx[0]) for y in (mn[1], mx[1])]
            lo, hi = mb.DotProduct(Dh), mc.DotProduct(Dh)
            if lo > min(cps) - mm(50) + 1e-6 or hi < max(cps) + mm(50) - 1e-6: why = "plan coverage: leg [%.0f,%.0f] vs obstacle [%.0f,%.0f] (+-50)" % (tomm(lo), tomm(hi), tomm(min(cps)), tomm(max(cps)))
            else:  # vertical clearance at every obstacle corner (plan position) along the mid-leg
                for x in (mn[0], mx[0]):
                    for y in (mn[1], mx[1]):
                        tt = (XYZ(mm(x), mm(y), 0).DotProduct(Dh) - lo) / (hi - lo)
                        zr = tomm(mb.Z + (mc.Z - mb.Z) * tt)
                        if up and zr < mx[2] + 50 + 150 - 0.5: why = "Up clearance %.1f < %.1f" % (zr, mx[2] + 200)
                        if (not up) and zr > mn[2] - 50 - 150 + 0.5: why = "Down clearance %.1f > %.1f" % (zr, mn[2] - 200)
    if why: bad.append((i, slope * 57.3, why))
check("property: %d random ducts (slope +-40, any yaw, any obstacle, Up/Down): 5 pieces, 4x45deg, contiguous, parallel mid-leg, covers obstacle+50mm, vertical clearance" % N, not bad, "violations=%d %s" % (len(bad), bad[:3]))

print("\nFAILED:", fails if fails else "none"); sys.exit(1 if fails else 0)
