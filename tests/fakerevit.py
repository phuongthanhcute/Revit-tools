"""Minimal fake Revit kernel so the REAL script.py files can run on plain Python.
Geometry in feet (like Revit). Models only what the scripts touch.
It is MY model of the API (BreakCurve keeps original id for the start piece, etc.)."""
import os, sys, types, math, runpy
from unittest.mock import MagicMock

MM = 1 / 304.8
def mm(x): return x * MM
def tomm(x): return x / MM

class XYZ:
    def __init__(s, x=0.0, y=0.0, z=0.0): s.X, s.Y, s.Z = float(x), float(y), float(z)
    def __add__(s, o): return XYZ(s.X + o.X, s.Y + o.Y, s.Z + o.Z)
    def __sub__(s, o): return XYZ(s.X - o.X, s.Y - o.Y, s.Z - o.Z)
    def __mul__(s, k): return XYZ(s.X * k, s.Y * k, s.Z * k)
    def __neg__(s): return XYZ(-s.X, -s.Y, -s.Z)
    def __truediv__(s, k): return XYZ(s.X / k, s.Y / k, s.Z / k)
    def Normalize(s): return s / s.DistanceTo(XYZ())
    def DistanceTo(s, o): return math.sqrt((s.X-o.X)**2 + (s.Y-o.Y)**2 + (s.Z-o.Z)**2)
    def DotProduct(s, o): return s.X*o.X + s.Y*o.Y + s.Z*o.Z
    def t(s): return (round(tomm(s.X), 1), round(tomm(s.Y), 1), round(tomm(s.Z), 1))
XYZ.BasisZ = XYZ(0, 0, 1)

class IR:  # IntersectionResult
    def __init__(s, p, d, t): s.XYZPoint, s.Distance, s.Parameter = p, d, t
class Line:
    def __init__(s, a, b): s.a, s.b = a, b
    @staticmethod
    def CreateBound(a, b): return Line(a, b)
    @property
    def Length(s): return s.a.DistanceTo(s.b)
    def GetEndPoint(s, i): return s.a if i == 0 else s.b
    def Project(s, p):
        ab = s.b - s.a; t = (p - s.a).DotProduct(ab) / ab.DotProduct(ab)
        tc = max(0.0, min(1.0, t)); q = s.a + ab * tc
        return IR(q, p.DistanceTo(q), tc)

class OperationCanceledException(Exception): pass
class ExitScript(SystemExit): pass
class LocationCurve:
    def __init__(s, c): s.Curve = c
class Duct: pass
class Pipe: pass
class FlexDuct: pass
class FlexDuctType: pass
class DuctInsulationType: pass
class FamilyInstance: pass
class FamilySymbol: pass
class View3D: pass
class View: pass

class Conn:
    def __init__(s, owner, idx=None, pt=None): s.owner, s.idx, s._pt, s.IsConnected = owner, idx, pt, False; s.links = []; s.Domain = 'Hvac'
    @property
    def Origin(s): return s._pt if s.idx is None else s.owner.Location.Curve.GetEndPoint(s.idx)
    def ConnectTo(s, o): s.links.append(o); s.IsConnected = True
class CM:
    def __init__(s, conns): s.Connectors = conns

class Param:
    def __init__(s, v=0.0): s.v, s.IsReadOnly, s.sets = v, False, []
    def AsDouble(s): return s.v
    def Set(s, x): s.sets.append(x); s.v = x

def make_curve_elem(cls, a, b, params=None, eid=None):
    e = cls(); e.Location = LocationCurve(Line(a, b)); e.Id = eid
    e.ConnectorManager = CM([Conn(e, 0), Conn(e, 1)]); e._params = params or {}
    e.LookupParameter = lambda n, _e=e: _e._params.get(n)
    e.get_Parameter = lambda bip, _e=e: _e._params.get(bip)
    e.MEPSystem = None; e.LevelId = "L1"; e.Pinned = False
    return e

class Doc:
    def __init__(s):
        s.els, s._id = {}, 100
        s.elbows, s.unions, s.takeoffs, s.placed, s.rotated, s.deleted = [], [], [], [], [], []
        s.ActiveView = None
        s.Create = types.SimpleNamespace(NewElbowFitting=s.new_elbow, NewUnionFitting=s.new_union,
                                         NewTakeoffFitting=s.new_takeoff, NewFamilyInstance=s.new_fi)
    @staticmethod
    def _conns(e):
        if hasattr(e, "ConnectorManager"): return list(e.ConnectorManager.Connectors)
        if hasattr(e, "MEPModel"): return list(e.MEPModel.ConnectorManager.Connectors)
        return []
    def snapshot(s):
        return {"els": dict(s.els),
                "curves": {i: (e.Location.Curve.a, e.Location.Curve.b) for i, e in s.els.items() if isinstance(getattr(e, "Location", None), LocationCurve)},
                "conns": [(c, c.IsConnected, list(c.links)) for e in s.els.values() for c in s._conns(e)],
                "n": (len(s.elbows), len(s.unions), len(s.takeoffs), len(s.placed), len(s.rotated))}
    def restore(s, snap):
        s.els.clear(); s.els.update(snap["els"])
        for i, (a, b) in snap["curves"].items(): s.els[i].Location.Curve = Line(a, b)
        for c, ic, links in snap["conns"]: c.IsConnected, c.links = ic, links
        for lst, n in zip((s.elbows, s.unions, s.takeoffs, s.placed, s.rotated), snap["n"]): del lst[n:]
    def add(s, e):
        s._id += 1; e.Id = s._id; s.els[e.Id] = e; return e
    def GetElement(s, x): return s.els.get(getattr(x, "eid", x))
    def Delete(s, i): s.deleted.append(i); s.els.pop(i, None)
    def Regenerate(s): pass
    def GetDefaultElementTypeId(s, g): return "DEFAULT_SYSTEM"
    @staticmethod
    def _dir(e): c = e.Location.Curve; return (c.b - c.a).Normalize()
    def new_elbow(s, c1, c2):
        d1, d2 = s._dir(c1.owner), s._dir(c2.owner)
        ang = math.degrees(math.acos(max(-1, min(1, d1.DotProduct(d2)))))
        s.elbows.append((c1.Origin.t(), c2.Origin.t(), round(ang, 2), c1.Origin.DistanceTo(c2.Origin)))
    def new_union(s, c1, c2): s.unions.append((c1.Origin.t(), c2.Origin.t()))
    def new_takeoff(s, conn, duct): s.takeoffs.append((conn.Origin.t(), duct.Id))
    def new_fi(s, pt, sym, st):
        h = types.SimpleNamespace(pt=pt, Id=len(s.placed) + 1, Symbol=sym, bbox=Box(pt - XYZ(mm(50), mm(50), mm(50)), pt + XYZ(mm(50), mm(50), mm(50))),
                                  p={n: Param() for n in getattr(s, "hanger_params", ["Width", "Rod Length"])})
        h.LookupParameter = lambda n, _h=h: _h.p.get(n)
        s.placed.append(h); return h

def break_curve(doc, eid, pt):
    e = doc.els[eid]; c = e.Location.Curve
    ne = make_curve_elem(type(e), pt, c.b, dict(e._params)); doc.add(ne)
    e.Location.Curve = Line(c.a, pt); return ne.Id
def copy_elements(doc, ids, vec):
    out = []
    for i in list(ids):
        e = doc.els[i]; c = e.Location.Curve
        ne = make_curve_elem(type(e), c.a, c.b, dict(e._params)); doc.add(ne); out.append(ne.Id)
    return out

class Box:
    def __init__(s, mn, mx): s.Min, s.Max = mn, mx
class Outline:
    def __init__(s, mn, mx): s.mn, s.mx = mn, mx
class BBFilter:
    def __init__(s, o): s.o = o
class CatFilter:
    def __init__(s, c): s.c = c
class OrFilter:
    def __init__(s, *a): s.a = a
def _hit(o, bb):
    return all(o.mn.__dict__[k] <= bb.Max.__dict__[k] and o.mx.__dict__[k] >= bb.Min.__dict__[k] for k in "XYZ")
def _bbox_of(e):
    if hasattr(e, "bbox"): return e.bbox
    c = e.Location.Curve; a, b = c.a, c.b
    return Box(XYZ(min(a.X,b.X), min(a.Y,b.Y), min(a.Z,b.Z)), XYZ(max(a.X,b.X), max(a.Y,b.Y), max(a.Z,b.Z)))

def build(doc, scenario):
    """scenario: dict with keys used by the individual tests"""
    DB = MagicMock(name="DB"); del DB.UI
    DB.XYZ, DB.Line, DB.Outline, DB.BoundingBoxIntersectsFilter = XYZ, Line, Outline, BBFilter
    DB.ElementCategoryFilter, DB.LogicalOrFilter = CatFilter, OrFilter
    class _BIP:
        def __getattr__(self, n): return n
    DB.BuiltInParameter = _BIP()
    DB.Domain = types.SimpleNamespace(DomainHvac="Hvac")
    class Tx:
        def __init__(s, d, name=None): s.d, s.snap, s.state = d, None, "new"
        def Start(s): s.snap = s.d.snapshot(); s.state = "started"
        def Commit(s): s.state = "committed"
        def RollBack(s): s.d.restore(s.snap); s.state = "rolled back"
    DB.Transaction = lambda d, name=None: Tx(d, name)
    DB.SubTransaction = lambda d: Tx(d)
    DB.LocationCurve, DB.MEPCurve, DB.View3D, DB.FamilyInstance, DB.FamilySymbol = LocationCurve, (Duct, Pipe), View3D, FamilyInstance, FamilySymbol
    DB.Mechanical.Duct, DB.Plumbing.Pipe = Duct, Pipe
    DB.Mechanical.FlexDuctType = FlexDuctType
    DB.Mechanical.DuctInsulationType = DuctInsulationType
    DB.ConnectorProfileType = types.SimpleNamespace(Round="Round")
    DB.PartType = types.SimpleNamespace(Elbow="Elbow")
    DB.Mechanical.DuctInsulation = types.SimpleNamespace(Create=lambda d, i, t, th: scenario.setdefault("insulated", []).append((i, t, th)))
    def _break(d, i, p):
        if scenario.get("break_fail"): raise RuntimeError("BreakCurve failed (injected)")
        return break_curve(doc, i, p)
    DB.Mechanical.MechanicalUtils.BreakCurve = _break
    DB.Plumbing.PlumbingUtils.BreakCurve = lambda d, i, p: break_curve(doc, i, p)
    DB.ElementTransformUtils.CopyElements = lambda d, ids, v: copy_elements(doc, ids, v)
    DB.ElementTransformUtils.RotateElement = lambda d, i, ax, a: doc.rotated.append(a)
    DB.BuiltInCategory.OST_DuctTerminal = 7
    DB.BuiltInCategory.OST_MechanicalEquipment = 8
    DB.ElementId.InvalidElementId = "INVALID"
    class Coll:
        def __init__(s, d, vid=None): s.cls, s.f = None, []
        def OfClass(s, c): s.cls = c; return s
        def WherePasses(s, f): s.f.append(f); return s
        def _bb(s): return [f.o for f in s.f if isinstance(f, BBFilter)]
        def ToElements(s):
            if s.cls is FlexDuctType: return scenario.get("flextypes") or [scenario["flextype"]]
            if s.cls is DuctInsulationType: return scenario.get("instypes", [])
            if s.cls is FamilySymbol: return [scenario["sym"]]
            if s.cls is FamilyInstance:
                return [h for h in doc.placed if all(_hit(o, h.bbox) for o in s._bb())]
            if s.cls is Duct:
                return [e for e in doc.els.values() if isinstance(e, Duct) and all(_hit(o, _bbox_of(e)) for o in s._bb())]
            return []
        def _cats(s):
            out = []
            for f in s.f:
                for x in (getattr(f, "a", None) or [f]):
                    if isinstance(x, CatFilter): out.append(x.c)
            return out
        def ToElementIds(s):
            key = "equipment" if any(c in (7, 8) for c in s._cats()) else "fittings"
            return [1 for fb in scenario.get(key, []) if all(_hit(o, fb) for o in s._bb())]
    DB.FilteredElementCollector = Coll
    # raytrace
    class RI:
        def __init__(s, *a): pass
        def FindNearest(s, pt, d):
            z = scenario.get("slab_z");
            return None if z is None else types.SimpleNamespace(Proximity=z - pt.Z)
    DB.ReferenceIntersector = RI
    def flex_create(d, sysid, typeid, lvl, pts):
        pts = list(pts); f = FlexDuct(); doc.add(f)
        f.ConnectorManager = CM([Conn(f, pt=pts[0]), Conn(f, pt=pts[-1])]); f.sysid = sysid; f._params = {}; f.get_Parameter = lambda bip, _f=f: _f._params.setdefault(bip, Param()); scenario["flex"].append(f); return f
    DB.Mechanical.FlexDuct.Create = flex_create
    DB.Mechanical.FlexDuct = types.SimpleNamespace(Create=flex_create)
    UI = types.SimpleNamespace(Selection=types.SimpleNamespace(
        ISelectionFilter=object, ObjectType=types.SimpleNamespace(Element="Element")))
    alerts = scenario.setdefault("alerts", [])
    def alert(msg, **k):
        alerts.append(msg)
        if k.get("exitscript"): raise ExitScript()
        return scenario.get("confirm", True) if k.get("yes") else None
    class TLI:
        def __init__(s, item): s.item = item
    answers = scenario.get("ask", {})
    def _select(opts, k):
        t = k.get("title"); scenario.setdefault("selects_asked", []).append(t)
        if t in scenario.get("select_by_title", {}): return scenario["select_by_title"][t]
        if t in ("Chọn Family Giá Đỡ", "Chọn hướng né va chạm"): return scenario.get("select")
        o = list(opts)[0] if list(opts) else None
        return getattr(o, "item", o)
    forms = types.SimpleNamespace(alert=alert, TemplateListItem=TLI,
        SelectFromList=types.SimpleNamespace(show=lambda opts, **k: _select(opts, k)),
        ask_for_string=lambda **k: (scenario.setdefault('asked', []).append(k.get('title')), answers.get(k.get('title'), k['default']))[1])
    def sexit(): raise ExitScript()
    class RvTx:
        def __init__(s, *a, **k): s.snap = None
        def __enter__(s): s.snap = doc.snapshot(); return s
        def __exit__(s, et, ev, tb):
            if et is not None: doc.restore(s.snap)
            return False
    uidoc = MagicMock()
    picks = iter(scenario.get("picks", []))
    uidoc.Selection.PickObject = lambda *a, **k: types.SimpleNamespace(eid=next(picks))
    pick_lists = iter(scenario.get("pick_lists", []))   # mỗi lần PickObjects trả một danh sách id; không có thì lấy 1 id từ picks
    def pick_objects(*a, **k):
        try: ids = next(pick_lists)
        except StopIteration: ids = [next(picks)]
        return [types.SimpleNamespace(eid=i) for i in ids]
    uidoc.Selection.PickObjects = pick_objects
    revit = types.SimpleNamespace(doc=doc, uidoc=uidoc, Transaction=RvTx,
                                  get_selection=lambda: types.SimpleNamespace(elements=scenario.get("selection", [])))
    pyrevit = types.ModuleType("pyrevit")
    pyrevit.revit, pyrevit.DB, pyrevit.UI, pyrevit.forms = revit, DB, UI, forms
    pyrevit.script = types.SimpleNamespace(exit=sexit)
    gen = types.ModuleType("System.Collections.Generic")
    gen.List = type("List", (list,), {"__class_getitem__": classmethod(lambda c, i: c), "Add": lambda s, x: s.append(x)})
    exc = types.ModuleType("Autodesk.Revit.Exceptions"); exc.OperationCanceledException = OperationCanceledException
    return {"pyrevit": pyrevit, "System": types.ModuleType("System"), "System.Collections": types.ModuleType("System.Collections"),
            "System.Collections.Generic": gen, "Autodesk": types.ModuleType("Autodesk"), "Autodesk.Revit": types.ModuleType("Autodesk.Revit"),
            "Autodesk.Revit.Exceptions": exc}

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'MEP_Tools.extension', 'lib'))
def run(path, doc, scenario):
    if LIB not in sys.path: sys.path.insert(0, LIB)
    sys.modules.pop('mep_common', None)
    mods = build(doc, scenario); saved = {k: sys.modules.get(k) for k in mods}; sys.modules.update(mods)
    try:
        runpy.run_path(path, run_name="__main__"); return "completed"
    except ExitScript: return "exit"
    except BaseException as e: return "%s: %s" % (type(e).__name__, e)
    finally:
        sys.modules.pop('mep_common', None)
        for k, v in saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
