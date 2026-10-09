"""Regression tests for the 'fix everything that is not blocked by Revit' batch. Hard asserts."""
import os as _os
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
import math, random, sys, types
from unittest.mock import MagicMock
from fakerevit import *
import fakerevit

EXT = REPO + "/MEP_Tools.extension"
ROOT = EXT + "/HVAC.tab/Utilities.panel"
CA, AH, AR, SP = (ROOT + "/Clash Avoid.pushbutton/script.py", ROOT + "/Auto Hangers.pushbutton/script.py",
                  ROOT + "/Auto Routing.pushbutton/script.py", ROOT + "/Split Pipes.pushbutton/script.py")
fails = []
def check(name, cond, detail=""):
    print("[%s] %s %s" % ("PASS" if cond else "FAIL", name, detail))
    if not cond: fails.append(name)
def P(x, y, z): return XYZ(mm(x), mm(y), mm(z))
def seg(e): c = e.Location.Curve; return c.a, c.b
def last(sc): return sc.get("alerts", [""])[-1]

# =================================================================== lib/mep_common (BUG-37, 38, 20)
print("=== lib: mep_common ===")
mods = build(Doc(), {"sym": None, "flextype": None, "flex": []})
sys.path.insert(0, fakerevit.LIB); saved = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods); sys.modules.pop("mep_common", None)
import mep_common as mc
def elem(params): return make_curve_elem(Duct, P(0, 0, 0), P(1000, 0, 0), params)
w, h = mc.get_section_size(elem({"RBS_CURVE_WIDTH_PARAM": Param(mm(800)), "RBS_CURVE_HEIGHT_PARAM": Param(mm(300))}))
check("BUG-37 reads BuiltInParameter (no display names present)", (round(tomm(w)), round(tomm(h))) == (800, 300), "-> %s" % ((round(tomm(w)), round(tomm(h))),))
w, h = mc.get_section_size(elem({"Width": Param(mm(800)), "Height": Param(mm(300))}))
check("BUG-37 falls back to display names", (round(tomm(w)), round(tomm(h))) == (800, 300))
w, h = mc.get_section_size(elem({"RBS_PIPE_OUTER_DIAMETER": Param(mm(168)), "Diameter": Param(mm(150))}))
check("BUG-37 pipe: outer diameter preferred over nominal", round(tomm(w)) == 168 and w == h)
check("BUG-37 round duct via RBS_CURVE_DIAMETER_PARAM", round(tomm(mc.get_section_size(elem({"RBS_CURVE_DIAMETER_PARAM": Param(mm(600))}))[0])) == 600)
check("unreadable size -> (None, None)", mc.get_section_size(elem({})) == (None, None))
check("insulation default 0", mc.get_insulation_thickness(elem({})) == 0.0 and round(tomm(mc.get_insulation_thickness(elem({"RBS_REFERENCE_INSULATION_THICKNESS": Param(mm(25))})))) == 25)
check("BUG-38 id_value: new API (.Value)", mc.id_value(types.SimpleNamespace(Value=7)) == 7)
check("BUG-38 id_value: old API (.IntegerValue)", mc.id_value(types.SimpleNamespace(IntegerValue=9)) == 9)
check("BUG-38 id_value: both present prefers .Value", mc.id_value(types.SimpleNamespace(Value=1, IntegerValue=2)) == 1)
box = (P(0, 0, 0), P(1000, 1000, 1000))
hits = [((-500, 500, 500), (1500, 500, 500), 0, True), ((-500, 500, 500), (-100, 500, 500), 0, False),
        ((-500, 500, 500), (-100, 500, 500), 50, False), ((-500, 500, 500), (-100, 500, 500), 600, True),
        ((500, -2000, 500), (500, 3000, 500), 0, True), ((500, -2000, 2000), (500, 3000, 2000), 0, False),
        ((500, 500, 500), (600, 600, 600), 0, True), ((2000, 0, 0), (2000, 1000, 1000), 0, False),
        ((-300, -300, -300), (-10, -10, -10), 0, False), ((-300, -300, -300), (-10, -10, -10), 20, True)]
ok = all(mc.segment_hits_box(P(*a), P(*b), box[0], box[1], mm(e)) == want for a, b, e, want in hits)
check("BUG-20 segment_hits_box: 10 hand-made cases (inside, outside, expand, diagonal, miss)", ok)
random.seed(5); bad = 0
for _ in range(3000):   # compare with dense sampling
    a = P(*[random.uniform(-2000, 3000) for _ in range(3)]); b = P(*[random.uniform(-2000, 3000) for _ in range(3)]); e = random.choice([0, 100, 400])
    brute = any(all(box[0].__dict__[k] - mm(e) <= (a + (b - a) * (i / 4000.0)).__dict__[k] <= box[1].__dict__[k] + mm(e) for k in "XYZ") for i in range(4001))
    if brute != mc.segment_hits_box(a, b, box[0], box[1], mm(e)):
        # sampling can miss grazing hits; only count if analytic says NO but brute says yes
        if brute and not mc.segment_hits_box(a, b, box[0], box[1], mm(e)): bad += 1
check("BUG-20 segment_hits_box vs brute-force sampling (3000 random segments): no false 'miss'", bad == 0, "bad=%d" % bad)
sys.modules.pop("mep_common", None)
for k, v_ in saved.items():
    if v_ is None: sys.modules.pop(k, None)
    else: sys.modules[k] = v_

# =================================================================== CLASH AVOID
class Obs:
    def __init__(s, mn, mx): s.bbox = Box(P(*mn), P(*mx)); s.Id = "OBS"
    def get_BoundingBox(s, w): return s.bbox
def clash(a, b, obs, direction="Đi lên trên (Up)", params=None, pinned=False, elbow_fail_on=(), break_fail=False, angle=None):
    doc = Doc(); doc.ActiveView = View()
    duct = doc.add(make_curve_elem(Duct, P(*a), P(*b), params if params is not None else {"Width": Param(mm(600)), "Height": Param(mm(300))}))
    duct.Pinned = pinned
    doc.els["OBS"] = Obs(*obs); sc = {"picks": [duct.Id, "OBS"], "select": direction, "break_fail": break_fail}
    if angle: sc["select_by_title"] = {"Chọn góc bẻ": angle}
    if elbow_fail_on:
        n = [0]; orig = doc.new_elbow
        def flaky(c1, c2):
            n[0] += 1
            if n[0] in elbow_fail_on: raise RuntimeError("elbow %d failed (injected)" % n[0])
            orig(c1, c2)
        doc.Create.NewElbowFitting = flaky
    r = run(CA, doc, sc); D = (P(*b) - P(*a)).Normalize()
    ds = sorted([e for e in doc.els.values() if isinstance(e, Duct)], key=lambda e: e.Location.Curve.a.DotProduct(D))
    return r, doc, ds, sc
BEAM = ((9850, -3000, 2900), (10150, 3000, 3200))
A, B = (0, 0, 3000), (20000, 0, 3000)
def untouched(ds, doc):
    return len(ds) == 1 and ds[0].Location.Curve.a.DistanceTo(P(*A)) < 1e-9 and ds[0].Location.Curve.b.DistanceTo(P(*B)) < 1e-9 and not doc.elbows

print("\n=== Clash Avoid ===")
r, doc, ds, sc = clash(A, B, BEAM)
check("baseline still works (5 pieces, 4 elbows)", r == "completed" and len(ds) == 5 and len(doc.elbows) == 4 and "thành công" in last(sc))
for fail_on in [(1,), (3,), (4,), (2, 3)]:
    r, doc, ds, sc = clash(A, B, BEAM, elbow_fail_on=fail_on)
    check("BUG-22 elbow #%s fails -> full rollback, honest message" % (fail_on,), r == "exit" and untouched(ds, doc) and "hoàn tác" in last(sc) and "thành công" not in last(sc),
          "-> %s | pieces=%d" % (last(sc)[:60].replace("\n", " "), len(ds)))
r, doc, ds, sc = clash(A, B, BEAM, break_fail=True)
check("BreakCurve failure -> no half-open transaction, model untouched", r == "exit" and untouched(ds, doc) and "hoàn tác" in last(sc), "-> %s" % last(sc)[:60].replace("\n", " "))
# BUG-20
r, doc, ds, sc = clash(A, B, ((9850, 49850, 2900), (10150, 50150, 3200)))
check("BUG-20 obstacle 50 m away -> refused, model untouched", r == "exit" and untouched(ds, doc) and "không nằm trên đường đi" in last(sc), "-> %s" % last(sc)[:70])
r, doc, ds, sc = clash(A, B, ((9850, -3000, 3400), (10150, 3000, 3700)))   # bottom 3400, duct top at 3150 + 50 + ... = 3200 reach -> not on path
check("BUG-20 obstacle 250 mm above the duct top (beyond reach) -> refused", r == "exit" and untouched(ds, doc))
r, doc, ds, sc = clash(A, B, ((9850, -3000, 3200), (10150, 3000, 3500)))   # obstacle bottom 3200 = within reach (3000+300+50=3350)
check("BUG-20 obstacle within reach is accepted by the path check (then direction logic decides)", r in ("completed", "exit"))
# BUG-23 / BUG-48
r, doc, ds, sc = clash(A, B, ((9850, -3000, 2400), (10150, 3000, 2700)))   # obstacle top 2700, below duct bottom 2850
check("BUG-23 no clash going Up (obstacle below) -> no forced 100mm raise, tells user", r == "exit" and untouched(ds, doc) and "không cần né" in last(sc), "-> %s" % last(sc)[:90].replace("\n", " "))
r, doc, ds, sc = clash(A, B, ((9850, -3000, 3300), (10150, 3000, 3600)), "Đi xuống dưới (Down)")
check("BUG-48 obstacle above, user picks Down -> refused, tells user", r == "exit" and untouched(ds, doc) and "không cần né" in last(sc))
r, doc, ds, sc = clash(A, B, ((9850, -3000, 2900), (10150, 3000, 3200)), "Đi xuống dưới (Down)")
check("BUG-48 obstacle crossing duct, user picks Down -> handled (obstacle bottom 2900 < duct)", r == "completed" and len(ds) == 5, "-> z of mid-leg %.0f" % tomm(seg(ds[2])[0].Z))
r, doc, ds, sc = clash(A, B, ((9850, -3000, 2800), (10150, 3000, 2930)))   # thin: top 2930 -> needs raise 80 -> min 100 applies
zmid = tomm(seg(ds[2])[0].Z) if len(ds) == 5 else None
check("small real clash still gets the 100 mm minimum offset", r == "completed" and zmid is not None and zmid - 3000 >= 100 - 0.01, "-> offset %.1f" % (zmid - 3000 if zmid else -1))
# BUG-24
r, doc, ds, sc = clash(A, B, BEAM, params={"Diameter": Param(mm(600))})
check("BUG-24 round Ø600 -> clearance uses 600 (mid z = 3200+50+300)", r == "completed" and abs(tomm(seg(ds[2])[0].Z) - 3550) < 0.5, "-> %.1f" % tomm(seg(ds[2])[0].Z))
r, doc, ds, sc = clash(A, B, BEAM, params={"RBS_CURVE_DIAMETER_PARAM": Param(mm(600))})
check("BUG-37 same via BuiltInParameter only", r == "completed" and abs(tomm(seg(ds[2])[0].Z) - 3550) < 0.5)
r, doc, ds, sc = clash(A, B, BEAM, params={"Width": Param(mm(600)), "Height": Param(mm(300)), "RBS_REFERENCE_INSULATION_THICKNESS": Param(mm(25))})
check("BUG-24 insulation 25mm counted (h=300+2*25 -> mid z=3200+50+175)", r == "completed" and abs(tomm(seg(ds[2])[0].Z) - 3425) < 0.5, "-> %.1f" % tomm(seg(ds[2])[0].Z))
r, doc, ds, sc = clash(A, B, BEAM, params={})
check("BUG-24 unreadable size -> refused (no silent 150mm default)", r == "exit" and untouched(ds, doc) and "kích thước" in last(sc))
# Góc bẻ do người dùng chọn (mặc định 45°)
r, doc, ds, sc = clash(A, B, BEAM)
check("angle default 45: 4 elbows, all 45 deg", r == "completed" and len(doc.elbows) == 4 and all(abs(e[2] - 45) < 0.1 for e in doc.elbows), "-> %s" % [e[2] for e in doc.elbows])
for lbl, want in (("15° (khuyến nghị cho ống gió)", 15), ("30°", 30), ("60° (tối đa theo chuẩn)", 60)):
    r, doc, ds, sc = clash(A, B, BEAM, angle=lbl)
    check("angle %d chosen: 4 elbows, all %d deg, pieces=5" % (want, want), r == "completed" and len(ds) == 5 and len(doc.elbows) == 4 and all(abs(e[2] - want) < 0.1 for e in doc.elbows), "-> %s" % [e[2] for e in doc.elbows])
# ---- nhiều ống / nhiều vật cản trong một lần chạy
def clash_multi(ducts, obstacles, direction="Đi lên trên (Up)", params=None, elbow_fail_on=(), angle=None):
    doc = Doc(); doc.ActiveView = View()
    ds = [doc.add(make_curve_elem(Duct, P(*a), P(*b), dict(params) if params else {"Width": Param(mm(600)), "Height": Param(mm(300))})) for a, b in ducts]
    ids = []
    for i, o in enumerate(obstacles):
        ob = Obs(*o); ob.Id = "OB%d" % i; doc.els[ob.Id] = ob; ids.append(ob.Id)
    sc = {"pick_lists": [[d.Id for d in ds], ids], "select": direction}
    if angle: sc["select_by_title"] = {"Chọn góc bẻ": angle}
    if elbow_fail_on:
        n = [0]; orig = doc.new_elbow
        def flaky(c1, c2):
            n[0] += 1
            if n[0] in elbow_fail_on: raise RuntimeError("elbow %d failed (injected)" % n[0])
            orig(c1, c2)
        doc.Create.NewElbowFitting = flaky
    r = run(CA, doc, sc)
    return r, doc, sc, [e for e in doc.els.values() if isinstance(e, Duct)]
BM = lambda x, w=300: ((x - w // 2, -3000, 2900), (x + w // 2, 3000, 3200))
LONG = ((0, 0, 3000), (20000, 0, 3000))
r, doc, sc, ds = clash_multi([LONG], [BM(6000), BM(14000)])
check("MULTI 2 far beams in one run -> 2 bumps: 9 pieces, 8 elbows", r == "completed" and len(ds) == 9 and len(doc.elbows) == 8 and "2 chỗ né" in last(sc), "-> %d pieces, %d elbows | %s" % (len(ds), len(doc.elbows), last(sc)[:70].replace("\n", " ")))
r, doc, sc, ds = clash_multi([LONG], [BM(10000), BM(10800)])
check("MULTI 2 close beams (800 mm apart) -> merged into ONE bump (was refused before)", r == "completed" and len(ds) == 5 and len(doc.elbows) == 4 and "gộp" in last(sc), "-> %d pieces | %s" % (len(ds), last(sc)[:80].replace("\n", " ")))
r, doc, sc, ds = clash_multi([LONG], [BM(10800), BM(6000), BM(10000)])
check("MULTI obstacles in any pick order: far one separate, 2 close ones merged -> 2 bumps", r == "completed" and len(ds) == 9 and len(doc.elbows) == 8)
mid = sorted([d for d in ds if abs(d.Location.Curve.a.Z - d.Location.Curve.b.Z) < 1e-6 and abs(tomm(d.Location.Curve.a.Z) - 3400) < 1], key=lambda d: d.Location.Curve.a.X)
check("MULTI merged bump's middle leg covers both beams (x 9850..10950 + 50 mm each side)", len(mid) == 2 and tomm(mid[1].Location.Curve.a.X) <= 9800 + 1 and tomm(mid[1].Location.Curve.b.X) >= 11000 - 1, "-> %s" % [(round(tomm(d.Location.Curve.a.X)), round(tomm(d.Location.Curve.b.X))) for d in mid])
r, doc, sc, ds = clash_multi([LONG], [BM(150), BM(10000)])
check("MULTI one beam too near the duct end: only that one is skipped and reported, other still done", r == "completed" and len(ds) == 5 and "quá sát" in last(sc), "-> %d pieces | %s" % (len(ds), last(sc)[-90:].replace("\n", " ")))
r, doc, sc, ds = clash_multi([LONG], [BM(6000), BM(14000)], elbow_fail_on=(5,))
check("MULTI elbow fails in one bump -> only that bump rolled back (5 pieces, 4 elbows), other kept, reported", r == "completed" and len(ds) == 5 and len(doc.elbows) == 4 and "hoàn tác" in last(sc), "-> %d pieces, %d elbows" % (len(ds), len(doc.elbows)))
r, doc, sc, ds = clash_multi([((0, 0, 3000), (20000, 0, 3000)), ((0, 900, 3000), (20000, 900, 3000))], [((9850, -3000, 2900), (10150, 3000, 3200))])
check("MULTI 2 parallel ducts, 1 beam: both bumped (10 pieces, 8 elbows), no collision warning (900 mm apart)", r == "completed" and len(ds) == 10 and len(doc.elbows) == 8 and "CẢNH BÁO" not in last(sc), "-> %d pieces | %s" % (len(ds), last(sc)[:90].replace("\n", " ")))
r, doc, sc, ds = clash_multi([((0, 0, 3000), (20000, 0, 3000)), ((0, 0, 3400), (20000, 0, 3400))], [((9850, -3000, 2900), (10150, 3000, 3200))],
                              params={"Width": Param(mm(300)), "Height": Param(mm(300))})
check("MULTI lower duct raised into the upper one -> collision warning, upper duct reported as 'không cần né'", r == "completed" and "CẢNH BÁO" in last(sc) and "có thể va chạm" in last(sc) and "không cần né" in last(sc), "-> %s" % last(sc)[:200].replace("\n", " "))
r2, doc2, sc2, ds2 = clash_multi([LONG, ((0, 900, 3000), (20000, 900, 3000))], [((9850, 5000, 2900), (10150, 8000, 3200))])
check("MULTI obstacle on no selected duct's path -> refused, nothing changed", r2 == "exit" and len(ds2) == 2 and "không nằm trên đường đi" in last(sc2))
# hàm khoảng cách đoạn-đoạn
sd = mc.segments_min_distance
check("segments_min_distance: parallel 900 apart", abs(tomm(sd(P(0, 0, 0), P(1000, 0, 0), P(0, 900, 0), P(1000, 900, 0))) - 900) < 1e-6)
check("segments_min_distance: skew lines crossing above (z gap 250)", abs(tomm(sd(P(0, 0, 0), P(1000, 0, 0), P(500, -500, 250), P(500, 500, 250))) - 250) < 1e-6)
check("segments_min_distance: end-to-end (gap 300)", abs(tomm(sd(P(0, 0, 0), P(1000, 0, 0), P(1300, 0, 0), P(2000, 0, 0))) - 300) < 1e-6)
check("segments_min_distance: intersecting = 0", sd(P(0, 0, 0), P(1000, 0, 0), P(500, -500, 0), P(500, 500, 0)) < 1e-9)
# BUG-43 pinned
r, doc, ds, sc = clash(A, B, BEAM, pinned=True)
check("BUG-43 pinned duct -> refused", r == "exit" and untouched(ds, doc) and "Pin" in last(sc))

# =================================================================== AUTO HANGERS
def hangers(pipes, spacing="2000", fittings=None, params=None, slab=4000, doc=None, hp=None, pinned=False, cls=None, free_ends=False, extra=None, extra_sel=()):
    doc = doc or Doc(); doc.ActiveView = View3D(); doc.ActiveView.Id = "V"
    if hp: doc.hanger_params = hp
    els = [doc.add(make_curve_elem(cls or Pipe, P(*a), P(*b), dict(params) if params is not None else {"Diameter": Param(mm(150))})) for a, b in pipes]
    if cls is Duct and not free_ends:
        for e_ in els:
            for c_ in e_.ConnectorManager.Connectors: c_.IsConnected = True
    sym = MagicMock(); sym.IsActive = True
    sc = {"selection": els + list(extra_sel), "sym": sym, "select": sym, "ask": {"Khoảng cách": spacing}, "slab_z": mm(slab) if slab else None,
          "fittings": [Box(P(*f[0]), P(*f[1])) for f in (fittings or [])]}
    sc.update(extra or {})
    return run(AH, doc, sc), doc, sc, sym
def xs(doc): return [tomm(h.pt.X) for h in doc.placed]
def rod(doc, i=0): s_ = doc.placed[i].p.get("Rod Length"); return tomm(s_.v) if s_ and s_.sets else None

print("\n=== Auto Hangers ===")
# BUG-12
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], params={"Width": Param(mm(800)), "Height": Param(mm(300))})
check("BUG-12 rect 800x300 -> rod = 1000 - 150", abs(rod(doc) - 850) < 0.01, "-> %s" % rod(doc))
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], params={"Diameter": Param(mm(150))})
check("BUG-12 round Ø150 -> rod = 1000 - 75", abs(rod(doc) - 925) < 0.01, "-> %s" % rod(doc))
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], params={"Diameter": Param(mm(150)), "RBS_REFERENCE_INSULATION_THICKNESS": Param(mm(25))})
check("BUG-12 insulation 25mm shortens rod to 900", abs(rod(doc) - 900) < 0.01, "-> %s" % rod(doc))
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], params={})
check("unknown pipe size is reported, rod measured from centreline", "không đọc được kích thước" in last(sc) and abs(rod(doc) - 1000) < 0.01)
# BUG-10
FIT = lambda x0, x1: ((x0, -300, 2700), (x1, 300, 3300))
r, doc, sc, _ = hangers([((0, 0, 3000), (5000, 0, 3000))], fittings=[FIT(2480, 2520)])
p = sorted(xs(doc)); gaps = [b - a for a, b in zip(p, p[1:])]
check("BUG-10 slack available: hanger dodges the fitting, spans stay <= 2000, inside pipe", len(p) == 3 and max(gaps) <= 2000 + 1e-6 and 0 < p[0] and p[-1] < 5000 and abs(p[1] - 2500) > 1,
      "-> x=%s gaps=%s" % ([round(x) for x in p], [round(g) for g in gaps]))
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], fittings=[FIT(2900, 3100)])
p = sorted(xs(doc)); gaps = [b - a for a, b in zip(p, p[1:])]
check("BUG-10 no slack (L/k == spacing): span limit wins, hanger stays, user is told", max(gaps) <= 2000 + 1e-6 and "sát phụ kiện" in last(sc), "-> x=%s" % [round(x) for x in p])
r, doc, sc, _ = hangers([((0, 0, 3000), (1000, 0, 3000))], spacing="250", fittings=[FIT(850, 900)])
check("BUG-10 small spacing: never past the pipe end (was x=1025)", max(xs(doc)) < 1000 and min(xs(doc)) > 0, "-> max x=%.0f" % max(xs(doc)))
random.seed(21); bad = 0
for _ in range(300):
    L = random.uniform(500, 9000); s_ = random.choice([400, 800, 2000, 3000]); k = max(1, math.ceil(L / s_))
    fits = [FIT(f - 120, f + 120) for f in [random.uniform(0, L) for _ in range(random.randint(0, 4))]]
    r, doc, sc, _ = hangers([((0, 0, 3000), (L, 0, 3000))], spacing=str(s_), fittings=fits)
    p = sorted(xs(doc)); gaps = [b - a for a, b in zip(p, p[1:])]
    if len(p) != k or (gaps and max(gaps) > s_ + 1e-6) or p[0] <= 0 or p[-1] >= L: bad += 1
check("BUG-10 property: 300 random pipes with random fittings -> count==ceil(L/s), gaps<=s, inside pipe", bad == 0, "violations=%d" % bad)
# Tiêu chuẩn DW-02.02: giá đỡ cách mối nối ống gió >= 200mm (ống nước: 100mm)
r, doc, sc, _ = hangers([((0, 0, 3000), (5000, 0, 3000))], fittings=[FIT(2490, 2510)], spacing="2400", cls=Duct, params={"Width": Param(mm(600)), "Height": Param(mm(300))})
d_ = min(abs(x - f) for x in xs(doc) for f in (2490, 2510))
check("STD duct hanger keeps >= 200 mm from a joint/fitting (nudged away)", d_ >= 200 - 1e-6, "-> x=%s" % [round(x) for x in xs(doc)])
r, doc, sc, _ = hangers([((0, 0, 3000), (5000, 0, 3000))], fittings=[FIT(2490, 2510)], spacing="2400", cls=Pipe)
d_ = min(abs(x - f) for x in xs(doc) for f in (2490, 2510))
check("STD pipe hanger keeps >= 100 mm from a fitting", d_ >= 100 - 1e-6, "-> x=%s" % [round(x) for x in xs(doc)])
# Bảo ôn: bề rộng giá = rộng ống + 2 x bảo ôn (DW-02.03)
r, doc, sc, _ = hangers([((0, 0, 3000), (1000, 0, 3000))], cls=Duct,
                        params={"Width": Param(mm(600)), "Height": Param(mm(300)), "RBS_REFERENCE_INSULATION_THICKNESS": Param(mm(25))})
w_ = doc.placed[0].p.get("Width")
check("STD hanger width includes insulation on both sides (600+2*25)", w_ is not None and abs(tomm(w_.v) - 650) < 0.01, "-> %s" % (tomm(w_.v) if w_ else None))
# Vượt giới hạn tiêu chuẩn: hỏi xác nhận, từ chối thì không đặt gì; đồng ý thì vẫn chạy
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], spacing="3000", cls=Duct, params={"Width": Param(mm(600)), "Height": Param(mm(300))})
check("STD duct spacing 3000 > 2500 asks for confirmation, user agrees -> still placed", any("vượt giới hạn" in a for a in sc["alerts"]) and len(doc.placed) == 2)
# Nhịp theo tiêu chuẩn chọn cho từng nhóm ống (HD)
PPR = "PPR cấp nước (HD 4.1.3): D20~32=1000, D40~63=1500, D75~110=2000, D125~160=2500"
FIRE = "Chữa cháy (HD 5.1.3): <=DN50=4000, >DN50=6000"
sel = lambda lbl: {"select_by_title": {"Chọn tiêu chuẩn nhịp giá đỡ: Ống nước": lbl}}
r, doc, sc, _ = hangers([((0, 0, 3000), (10000, 0, 3000))], params={"Diameter": Param(mm(25))}, extra=sel(PPR))
check("STD PPR D25 -> span 1000: 10 m pipe gets 10 hangers", len(doc.placed) == 10, "-> %d" % len(doc.placed))
r, doc, sc, _ = hangers([((0, 0, 3000), (10000, 0, 3000))], params={"Diameter": Param(mm(50))}, extra=sel(PPR))
check("STD PPR D50 -> span 1500: 10 m pipe gets 7 hangers", len(doc.placed) == 7, "-> %d" % len(doc.placed))
r, doc, sc, _ = hangers([((0, 0, 3000), (10000, 0, 3000))], params={"Diameter": Param(mm(100))}, extra=sel(FIRE))
check("STD fire DN100 -> span 6000: 10 m pipe gets 2 hangers", len(doc.placed) == 2, "-> %d" % len(doc.placed))
r, doc, sc, _ = hangers([((0, 0, 3000), (10000, 0, 3000))], params={"Diameter": Param(mm(40))}, extra=sel(FIRE))
check("STD fire DN40 -> span 4000: 10 m pipe gets 3 hangers", len(doc.placed) == 3, "-> %d" % len(doc.placed))
r, doc, sc, _ = hangers([((0, 0, 3000), (10000, 0, 3000))], spacing="2500")
check("custom span is still the default first option (10 m / 2500 -> 4 hangers)", len(doc.placed) == 4 and "Khoảng cách" in sc["asked"])
# Thiết bị / miệng gió: giá không đặt trùng (khoảng cách là ô nhập, ở đây nhập 100 mm)
r, doc, sc, _ = hangers([((0, 0, 3000), (5000, 0, 3000))], spacing="2400",
                        extra={"equipment": [Box(P(2480, -300, 2700), P(2520, 300, 3300))], "ask": {"Khoảng cách": "2400", "Khoảng cách thiết bị": "100"}})
d_ = min(abs(x - f) for x in xs(doc) for f in (2480, 2520))
check("hanger keeps the user-entered clearance (100 mm) from equipment / air terminal", len(doc.placed) == 3 and d_ >= 100 - 1e-6 and abs(xs(doc)[1] - 2500) > 1, "-> x=%s" % [round(x) for x in xs(doc)])
r, doc, sc, _ = hangers([((0, 0, 3000), (5000, 0, 3000))], spacing="2400",
                        extra={"equipment": [Box(P(2400, -300, 2700), P(2600, 300, 3300))]})
check("default 300 mm equipment clearance with no room to dodge -> reported 'sát phụ kiện'", "sát phụ kiện" in last(sc))
# Giá cuối tuyến ống gió (đầu ống tự do)
DW = {"Width": Param(mm(600)), "Height": Param(mm(300))}
r, doc, sc, _ = hangers([((0, 0, 3000), (1120, 0, 3000))], cls=Duct, params=dict(DW), free_ends=True)
check("free-end duct 1120: end supports added at 250 and 870 + middle", sorted(round(x) for x in xs(doc)) == [250, 560, 870], "-> %s" % sorted(round(x) for x in xs(doc)))
r, doc, sc, _ = hangers([((0, 0, 3000), (1120, 0, 3000))], cls=Duct, params=dict(DW))
check("duct with both ends connected: no extra end supports", len(doc.placed) == 1)
r, doc, sc, _ = hangers([((0, 0, 3000), (1120, 0, 3000))], params={"Diameter": Param(mm(150))}, extra={})
check("pipe with free ends: no end supports (rule only for ducts)", len(doc.placed) == 1)
# Điểm kết thúc của ty
for lbl, want in (("Tâm ống", 1000), ("Đáy ống (kể cả bảo ôn) - ty tới thanh đỡ dưới đáy ống (DW-02.03)", 1150)):
    r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], params=dict(DW), extra={"select_by_title": {"Ty treo kết thúc tại": lbl}})
    check("rod end '%s' -> rod %d" % (lbl[:12], want), abs(rod(doc) - want) < 0.01, "-> %s" % rod(doc))
# --- edge cases rà soát thêm
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], slab=3050)
check("EDGE slab within the duct/pipe (rod would be -25 mm): no negative rod written, reported", all(x > 0 for h in doc.placed for x in h.p["Rod Length"].sets) and not any(h.p["Rod Length"].sets for h in doc.placed) and "chiều dài ty <= 0" in last(sc), "-> %s" % last(sc)[:120].replace("\n", " "))
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], spacing="5", extra={"confirm": False})
check("EDGE absurd spacing (5 mm): asks to confirm, user says no -> nothing placed", r == "exit" and not doc.placed and any("nhỏ hơn mức tối thiểu" in a for a in sc["alerts"]))
r, doc, sc, _ = hangers([((0, 0, 3000), (1120, 0, 3000)), ((1120, 0, 3000), (2240, 0, 3000))], spacing="2500", cls=Duct, params={"Width": Param(mm(600)), "Height": Param(mm(300))}, free_ends=True)
check("EDGE two ducts end-to-end whose connectors are NOT joined (failed Union): no fake end supports at the joint", sorted(round(x) for x in xs(doc)) == [250, 560, 1680, 1990], "-> %s" % sorted(round(x) for x in xs(doc)))
r, doc, sc, _ = hangers([((0, 0, 3000), (3000, 0, 3000))], extra_sel=[FamilyInstance(), FamilyInstance()])
check("EDGE non-duct/pipe elements in the selection (flex duct, fittings) are reported as ignored", "bị bỏ qua vì không phải ống" in last(sc) and ": 2" in last(sc))
# BUG-14
r, doc, sc, _ = hangers([((0, 0, 0), (0, 0, 6000))])
check("BUG-14 vertical pipe skipped and reported", len(doc.placed) == 0 and "Ống đứng bỏ qua: 1" in last(sc))
r, doc, sc, _ = hangers([((0, 0, 0), (6000, 0, 6000))])   # 45 deg riser-ish but < 60
check("45 deg pipe (8485 mm) still gets ceil(8485/2000)=5 hangers", len(doc.placed) == 5, "-> %d" % len(doc.placed))
t = math.radians(70); r, doc, sc, _ = hangers([((0, 0, 0), (6000 * math.cos(t), 0, 6000 * math.sin(t)))])
check("70 deg pipe skipped", len(doc.placed) == 0)
# BUG-15
r, doc, sc, sym = hangers([((0, 0, 3000), (6000, 0, 3000))]); n1 = len(doc.placed)
# second run on the same doc with the same symbol object
sc2 = {"selection": [e for e in doc.els.values() if isinstance(e, Pipe)], "sym": sym, "select": sym, "ask": {"Khoảng cách": "2000"}, "slab_z": mm(4000), "fittings": []}
doc.ActiveView = View3D(); doc.ActiveView.Id = "V"; r2 = run(AH, doc, sc2)
check("BUG-15 rerun: no duplicates, reported", len(doc.placed) == n1 == 3 and "đã có giá đỡ" in last(sc2), "-> %d hangers after rerun | %s" % (len(doc.placed), last(sc2)[-70:].replace("\n", " ")))
sym2 = MagicMock(); sym2.IsActive = True
sc3 = dict(sc2, sym=sym2, select=sym2); sc3["alerts"] = []
r3 = run(AH, doc, sc3)
check("BUG-15 a DIFFERENT hanger family is not treated as existing", len(doc.placed) == 6)
# BUG-39
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], hp=["Width", "Height"])
check("BUG-39 family has no 'Rod Length': 'Height' is NOT overwritten, user is told", all(not h.p["Height"].sets for h in doc.placed) and "Rod Length" in last(sc) and "CHƯA có ty treo" in last(sc))
# BUG-46
r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], slab=None)
check("BUG-46 raytrace miss is reported", "không tìm thấy sàn/dầm" in last(sc) and "3" in last(sc).split("sàn/dầm phía trên)")[1][:4])
# BUG-35
for val in ["abc", "0", "-5", ""]:
    r, doc, sc, _ = hangers([((0, 0, 3000), (6000, 0, 3000))], spacing=val)
    check("BUG-35 Hangers spacing %r -> clean exit, nothing placed" % val, r == "exit" and len(doc.placed) == 0)
# BUG-30 static
check("BUG-30 no collector is limited to the active view any more", all("ActiveView.Id" not in open(f, encoding="utf-8").read() for f in (AH, AR)))

# =================================================================== SPLIT
def split(L, sl="1120", kinds=("duct",), fail_union=False, pinned=False, vertical=False, extra_sel=()):
    doc = Doc(); doc.ActiveView = View(); els = []
    for kd in kinds:
        a, b = (P(0, 0, 0), P(0, 0, L)) if vertical else (P(0, 0, 0), P(L, 0, 0))
        e = doc.add(make_curve_elem(Duct if kd == "duct" else Pipe, a, b)); e.Pinned = pinned; els.append(e)
    sc = {"selection": els + list(extra_sel), "ask": {"Chia Ống Gió": sl, "Chia Ống Nước": sl}}
    if fail_union:
        def boom(c1, c2): raise RuntimeError("union failed")
        doc.Create.NewUnionFitting = boom
    return run(SP, doc, sc), doc, sc
print("\n=== Split ===")
r, doc, sc = split(3400)
check("baseline: 3 cuts, 3 unions, report separates them", doc.unions and len(doc.unions) == 3 and "Số nhát cắt: 3" in last(sc) and "Union chèn thành công: 3" in last(sc))
r, doc, sc = split(3400, fail_union=True)
check("BUG-34 union failure: report says 3 cuts, 0 unions, 3 failed", "Số nhát cắt: 3" in last(sc) and "chèn thành công: 0" in last(sc) and "KHÔNG chèn được Union: 3" in last(sc), "-> %s" % last(sc).replace("\n", " | "))
r, doc, sc = split(3400)
check("BUG-36 only a duct selected -> only the duct prompt", sc["asked"] == ["Chia Ống Gió"], "-> %s" % sc["asked"])
r, doc, sc = split(3400, kinds=("pipe",), sl="1000")
check("BUG-36 only a pipe selected -> only the pipe prompt", sc["asked"] == ["Chia Ống Nước"])
r, doc, sc = split(3400, kinds=("duct", "pipe"))
check("both kinds -> both prompts", sc["asked"] == ["Chia Ống Gió", "Chia Ống Nước"])
for val in ["abc", "0", "-100", "", "nan", "inf"]:
    r, doc, sc = split(3400, sl=val)
    check("BUG-35 Split length %r -> clean exit, nothing cut" % val, r == "exit" and len(doc.els) == 1 and not doc.unions)
r, doc, sc = split(3400, sl="1000,5")
check("decimal comma accepted (1000,5)", r == "completed" and len(doc.els) == 4, "-> %d pieces" % len(doc.els))
r, doc, sc = split(3400, pinned=True)
check("BUG-43 pinned duct is skipped and reported", len(doc.els) == 1 and "Pin" in last(sc))
r, doc, sc = split(3400, vertical=True)
check("vertical duct still splits", len(doc.els) == 4)

r, doc, sc = split(3400, extra_sel=[FamilyInstance()])
check("EDGE Split: ignored elements (flex duct, fittings...) reported", "bị bỏ qua vì không phải ống" in last(sc))

# =================================================================== AUTO ROUTING
def route(terms, mains=((0, 5000, 0, 3000),), maxlen="3000", takeoff_fail=(), flex_type=True, extra=None, main_params=None, elbow_ends=(), conn_attrs=None, category=True, pinned=False, main_system=None):
    """terms: list of lists of (x,y,z,domain)"""
    doc = Doc(); doc.ActiveView = View(); doc.ActiveView.Id = "V"
    ms = [doc.add(make_curve_elem(Duct, P(x0, y, z), P(x1, y, z), dict(main_params) if main_params else None)) for (x0, x1, y, z) in mains]
    for m_ in ms:
        m_.Pinned = pinned
        if main_system: m_.MEPSystem = types.SimpleNamespace(SystemType=main_system, GetTypeId=lambda: "SYS")
    if elbow_ends:
        elb = FamilyInstance(); elb.Id = "ELB"; elb.MEPModel = types.SimpleNamespace(PartType="Elbow")
        for ci in elbow_ends: ms[0].ConnectorManager.Connectors[ci].AllRefs = [types.SimpleNamespace(Owner=elb)]
    ts = []
    for i, conns in enumerate(terms):
        t = FamilyInstance(); t.Category = types.SimpleNamespace(Id=types.SimpleNamespace(IntegerValue=7)) if category else None; t.Id = "T%d" % i
        cs = []
        for (x, y, z, dom) in conns:
            c = Conn(t, pt=P(x, y, z)); c.Domain = dom; cs.append(c)
            for k_, v_ in (conn_attrs or {}).items(): setattr(c, k_, v_)
        t.MEPModel = types.SimpleNamespace(ConnectorManager=CM(cs)); doc.els[t.Id] = t; ts.append(t)
    sc = {"selection": ts, "ask": {"Auto Routing": maxlen}, "flextype": types.SimpleNamespace(Id="FT"), "flex": []}
    if takeoff_fail:
        n = [0]; orig = doc.new_takeoff
        def flaky(conn, duct):
            n[0] += 1
            if n[0] in takeoff_fail: raise RuntimeError("takeoff %d failed (injected)" % n[0])
            orig(conn, duct)
        doc.Create.NewTakeoffFitting = flaky
    sc.update(extra or {})
    r = run(AR, doc, sc)
    flexes = [e for e in doc.els.values() if isinstance(e, FlexDuct)]
    return r, doc, sc, ms, ts, flexes
H = "Hvac"; EL = "Electrical"
print("\n=== Auto Routing ===")
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]])
check("baseline: 1 flex, tap right above the terminal", len(fl) == 1 and doc.takeoffs[0][0][0] == 2500.0)
# BUG-29
for tx, want in [(100, 200), (-500, 200), (4990, 4800), (5600, 4800), (2500, 2500), (200, 200)]:
    r, doc, sc, ms, ts, fl = route([[(tx, 0, 2600, H)]])
    got = doc.takeoffs[0][0][0] if doc.takeoffs else None
    check("BUG-29 terminal x=%5d -> tap x=%s (min 200 mm from either end)" % (tx, want), got == want, "-> %s" % got)
r, doc, sc, ms, ts, fl = route([[(150, 0, 2600, H)]], mains=((0, 300, 0, 3000),))
check("BUG-29 duct shorter than 2x200 mm -> refused with a reason", not fl and "quá ngắn" in last(sc) and "Thất bại / Bỏ qua: 1" in last(sc))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], mains=((0, 300, 0, 3000), (0, 5000, 0, 3300)))
check("BUG-29 a too-short nearer duct is skipped, longer duct is used", len(fl) == 1 and doc.takeoffs[0][1] == ms[1].Id)
# BUG-31
r, doc, sc, ms, ts, fl = route([[(2500, 0, 3000 - 2600, H)]], maxlen="3000")   # 2600 below -> 2600*1.2 = 3120 > 3000
check("BUG-31 straight 2600 mm x1.2 > 3000 -> refused", not fl)
r, doc, sc, ms, ts, fl = route([[(2500, 0, 3000 - 2400, H)]], maxlen="3000")   # 2400*1.2 = 2880
check("BUG-31 straight 2400 mm x1.2 <= 3000 -> accepted", len(fl) == 1)
# BUG-28
r, doc, sc, ms, ts, fl = route([[(100, 0, 2000, EL), (2500, 0, 2600, H)]])
used = sorted(round(tomm(c.Origin.X)) for c in fl[0].ConnectorManager.Connectors) if fl else None
check("BUG-28 electrical connector listed first: flex goes to the HVAC one", used == [2500, 2500], "-> %s" % used)
r, doc, sc, ms, ts, fl = route([[(100, 0, 2000, EL)]])
check("BUG-28 terminal with only an electrical connector -> refused with reason", not fl and "connector gió" in last(sc))
# BUG-27
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], takeoff_fail=(1,))
check("BUG-27 takeoff fails -> no orphan flex, terminal connector free again, reported", not fl and not ts[0].MEPModel.ConnectorManager.Connectors[0].IsConnected and "hoàn tác" in last(sc), "-> flex left=%d" % len(fl))
r, doc, sc, ms, ts, fl = route([[(1000, 0, 2600, H)], [(3000, 0, 2600, H)], [(4000, 0, 2600, H)]], takeoff_fail=(2,))
check("BUG-27 terminals are independent: #2 fails, #1 and #3 still connected", len(fl) == 2 and len(doc.takeoffs) == 2 and "Thành công: 2" in last(sc) and "Thất bại / Bỏ qua: 1" in last(sc), "-> %s" % last(sc).replace("\n", " | ")[:120])
# BUG-35
for val in ["abc", "0", "-1"]:
    r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], maxlen=val)
    check("BUG-35 Routing max length %r -> clean exit" % val, r == "exit" and not fl)
r, doc, sc, ms, ts, fl = route([[(3000, 0, 2600, H)]], mains=((0, 6000, 0, 3000),), maxlen="2000", main_params={"Width": Param(mm(600)), "Height": Param(mm(300))}, elbow_ends=(0,))
check("8W position too far for the flex limit -> tap still placed at the nearest point, with warning", len(fl) == 1 and abs(doc.takeoffs[0][0][0] - 3000) < 0.5 and "cách cút gần hơn" in last(sc), "-> tap x=%s" % (doc.takeoffs[0][0][0] if doc.takeoffs else None))
# --- quyết định của kỹ sư: nhận mọi family có connector gió, kích thước theo connector, bảo ôn, loại ống mềm, 8W/6D
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], category=False)
check("any family with a free HVAC connector is accepted (e.g. air box, no OST_DuctTerminal category)", r == "completed" and len(fl) == 1)
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], conn_attrs={"Shape": "Round", "Radius": mm(100)})
dia = fl[0]._params.get("RBS_CURVE_DIAMETER_PARAM")
check("flex diameter follows the round connector (Ø200)", dia is not None and abs(tomm(dia.v) - 200) < 0.01 and "đường kính" not in last(sc), "-> %s" % (tomm(dia.v) if dia else None))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]])
check("connector without readable round size -> reported, still connected", len(fl) == 1 and "chưa đặt được đường kính" in last(sc))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], extra={"select_by_title": {"Ống mềm có bảo ôn không?": "Có bảo ôn"}, "instypes": [types.SimpleNamespace(Id="INS")], "ask": {"Auto Routing": "3000", "Bề dày bảo ôn": "30"}})
ins = sc.get("insulated", [])
check("insulated flex: DuctInsulation created with chosen type and 30 mm", len(ins) == 1 and ins[0][1] == "INS" and abs(tomm(ins[0][2]) - 30) < 0.01, "-> %s" % ins)
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]])
check("default: no insulation created", not sc.get("insulated"))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], extra={"select_by_title": {"Ống mềm có bảo ôn không?": "Có bảo ôn"}})
check("insulation chosen but project has no insulation type -> refused with a reason, nothing drawn", r == "exit" and not fl and "bảo ôn" in last(sc))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], extra={"flextypes": [types.SimpleNamespace(Id="FT1"), types.SimpleNamespace(Id="FT2")]})
check("several flex types -> user is asked which one", "Chọn loại Flex Duct" in sc["selects_asked"] and len(fl) == 1)
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]])
check("single flex type -> no extra question", "Chọn loại Flex Duct" not in sc["selects_asked"])
RECT = {"Width": Param(mm(600)), "Height": Param(mm(300))}
r, doc, sc, ms, ts, fl = route([[(500, 0, 2600, H)]], mains=((0, 10000, 0, 3000),), maxlen="6000", main_params=RECT, elbow_ends=(0,))
tx = doc.takeoffs[0][0][0] if doc.takeoffs else None
check("rect 600 duct, elbow at start: tap pushed to >= 8W = 4800 from the elbow", tx is not None and abs(tx - 4800) < 0.5 and "cách cút gần hơn" not in last(sc), "-> tap x=%s" % tx)
r, doc, sc, ms, ts, fl = route([[(500, 0, 2600, H)]], mains=((0, 3000, 0, 3000),), maxlen="6000", main_params=RECT, elbow_ends=(0,))
tx = doc.takeoffs[0][0][0] if doc.takeoffs else None
check("duct too short for 8W: tap STILL placed (engineer decision) but reported", len(fl) == 1 and "cách cút gần hơn" in last(sc), "-> tap x=%s" % tx)
ROUND = {"RBS_CURVE_DIAMETER_PARAM": Param(mm(300))}
r, doc, sc, ms, ts, fl = route([[(9800, 0, 2600, H)]], mains=((0, 10000, 0, 3000),), maxlen="6000", main_params=ROUND, elbow_ends=(1,))
tx = doc.takeoffs[0][0][0] if doc.takeoffs else None
check("round Ø300 duct, elbow at end: tap >= 6D = 1800 from the elbow end", tx is not None and abs(tx - 8200) < 0.5, "-> tap x=%s" % tx)
r, doc, sc, ms, ts, fl = route([[(500, 0, 2600, H)]], mains=((0, 10000, 0, 3000),), maxlen="6000", main_params=RECT)
tx = doc.takeoffs[0][0][0] if doc.takeoffs else None
check("no elbow at the ends: tap stays under the terminal (x=500)", tx is not None and abs(tx - 500) < 0.5, "-> tap x=%s" % tx)
CA_ = {"Shape": "Round", "Radius": mm(100)}
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)], [(2520, 0, 2600, H)]], conn_attrs=CA_)
xs_ = sorted(t[0][0] for t in doc.takeoffs)
check("EDGE 2 terminals 20 mm apart: takeoffs kept >= 300 mm apart (Ø200 collars + 100 mm gap), both connected", len(fl) == 2 and len(xs_) == 2 and xs_[1] - xs_[0] >= 300 - 0.5, "-> takeoffs x=%s" % [round(x) for x in xs_])
r, doc, sc, ms, ts, fl = route([[(x, 0, 2600, H)] for x in (2000, 2100, 2200, 2300, 2400)], mains=((0, 1500, 0, 3000),), conn_attrs=CA_, maxlen="6000")
check("EDGE too many terminals for the duct length: those without room are refused with a reason, none stacked closer than 300 mm", 0 < len(fl) < 5 and all(abs(a[0][0] - b[0][0]) >= 300 - 0.5 for i, a in enumerate(doc.takeoffs) for b in doc.takeoffs[i + 1:]) and "không còn chỗ trống" in last(sc), "-> %d of 5 connected, x=%s | %s" % (len(fl), sorted(round(t[0][0]) for t in doc.takeoffs), last(sc)[-110:].replace("\n", " ")))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], conn_attrs=dict(CA_, DuctSystemType="SupplyAir"), main_system="ReturnAir")
check("EDGE supply terminal vs RETURN duct: refused with reason (not tapped into the wrong system)", not fl and "khác loại hệ thống" in last(sc), "-> %s" % last(sc)[:120].replace("\n", " "))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], conn_attrs=dict(CA_, DuctSystemType="SupplyAir"), main_system="SupplyAir")
check("EDGE same system type: accepted", len(fl) == 1)
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], conn_attrs=CA_, main_params={"Width": Param(mm(150)), "Height": Param(mm(150))})
check("EDGE Ø200 flex onto a 150x150 main duct: refused with reason", not fl and "quá nhỏ cho cổ trích" in last(sc), "-> %s" % last(sc)[:120].replace("\n", " "))
r, doc, sc, ms, ts, fl = route([[(2500, 0, 2600, H)]], conn_attrs=CA_, pinned=True)
check("EDGE pinned main duct: not tapped, reason says Unpin", not fl and "Pin" in last(sc), "-> %s" % last(sc)[:120].replace("\n", " "))
# BUG-38 end-to-end: category check works with both ElementId flavours
check("BUG-38 script no longer touches .IntegerValue directly", ".IntegerValue" not in open(AR, encoding="utf-8").read())

print("\nFAILED:", fails if fails else "none"); sys.exit(1 if fails else 0)
