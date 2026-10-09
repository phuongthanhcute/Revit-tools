"""Stub harness: runs the pyRevit scripts outside Revit.
Models only what matters for P0: DB has NO `.UI` (like real Autodesk.Revit.DB),
System.Collections.Generic.List exists, Autodesk.Revit.Exceptions exists.
This is MY model of the API, not real Revit."""
import os as _os
REPO = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), ".."))
import sys, types, math, runpy
from unittest.mock import MagicMock

ROOT = REPO
sys.path.insert(0, ROOT + "/MEP_Tools.extension/lib")
NEW = ROOT + "/MEP_Tools.extension/HVAC.tab/Utilities.panel"

class XYZ:
    def __init__(s, x=0, y=0, z=0): s.X, s.Y, s.Z = x, y, z
    def __add__(s, o): return XYZ(s.X + o.X, s.Y + o.Y, s.Z + o.Z)
    def __sub__(s, o): return XYZ(s.X - o.X, s.Y - o.Y, s.Z - o.Z)
    def __mul__(s, k): return XYZ(s.X * k, s.Y * k, s.Z * k)
    def __neg__(s): return XYZ(-s.X, -s.Y, -s.Z)
    def __truediv__(s, k): return XYZ(s.X / k, s.Y / k, s.Z / k)
    def Normalize(s): n = s.DistanceTo(XYZ()); return s / n
    def DistanceTo(s, o): return math.sqrt((s.X-o.X)**2 + (s.Y-o.Y)**2 + (s.Z-o.Z)**2)
    def DotProduct(s, o): return s.X*o.X + s.Y*o.Y + s.Z*o.Z
XYZ.BasisZ = XYZ(0, 0, 1)

class OperationCanceledException(Exception): pass
class ExitScript(SystemExit): pass
class Pipe: pass
class Duct: pass
class View3D: pass
class LocationCurve: pass

def build(scenario):
    calls = {"alerts": [], "placed": 0}
    DB = MagicMock(name="DB")
    del DB.UI                                  # real DB has no .UI -> AttributeError
    DB.XYZ = XYZ
    DB.Plumbing.Pipe, DB.Mechanical.Duct = Pipe, Duct
    DB.View3D, DB.LocationCurve = View3D, LocationCurve
    DB.MEPCurve = (Pipe, Duct)
    DB.ReferenceIntersector.return_value.FindNearest.return_value = types.SimpleNamespace(Proximity=3.0)   # tia trúng sàn cách 3 ft
    DB.Line.CreateBound = lambda a, b: MagicMock()
    # --- UI module (Autodesk.Revit.UI) ---
    UI = types.SimpleNamespace(Selection=types.SimpleNamespace(
        ISelectionFilter=object, ObjectType=types.SimpleNamespace(Element="Element")))
    # --- forms / script ---
    def alert(msg, **k):
        calls["alerts"].append(msg)
        if k.get("exitscript"): raise ExitScript()
    class TemplateListItem:
        def __init__(s, item): s.item = item
    sym = MagicMock(name="FamilySymbol"); sym.IsActive = True
    forms = types.SimpleNamespace(
        alert=alert, TemplateListItem=TemplateListItem,
        SelectFromList=types.SimpleNamespace(show=lambda opts, **k: (sym if k.get("title") == "Chọn Family Giá Đỡ" else list(opts)[0]) if scenario != "clash" else ("Đi lên trên (Up)" if k.get("title") == "Chọn hướng né va chạm" else list(opts)[0])),
        ask_for_string=lambda **k: k["default"])
    def sexit(): raise ExitScript()
    script = types.SimpleNamespace(exit=sexit)
    # --- revit doc/selection ---
    pipe = Pipe()
    lc = LocationCurve(); curve = MagicMock(); curve.Length = 10.0
    curve.GetEndPoint = lambda i: XYZ(0, 0, 0) if i == 0 else XYZ(10, 0, 0)
    lc.Curve = curve; pipe.Location = lc
    prm = MagicMock(); prm.AsDouble = lambda: 0.5; prm.IsReadOnly = False
    pipe.LookupParameter = lambda n: prm
    pipe.get_Parameter = lambda bip: None
    pipe.Pinned = False
    doc = MagicMock(); view = View3D(); view.Id = MagicMock(); doc.ActiveView = view
    def newfi(*a, **k): calls["placed"] += 1; return MagicMock()
    doc.Create.NewFamilyInstance = newfi
    class Tx:
        def __init__(s, *a, **k): pass
        def __enter__(s): return s
        def __exit__(s, *e): return False
    uidoc = MagicMock()
    if scenario == "clash_cancel":
        uidoc.Selection.PickObjects.side_effect = OperationCanceledException()
    elif scenario == "clash_bug":
        uidoc.Selection.PickObjects.side_effect = RuntimeError("real bug")
    revit = types.SimpleNamespace(doc=doc, uidoc=uidoc, Transaction=Tx,
                                  get_selection=lambda: types.SimpleNamespace(elements=[pipe]))
    pyrevit = types.ModuleType("pyrevit")
    pyrevit.revit, pyrevit.DB, pyrevit.UI, pyrevit.forms, pyrevit.script = revit, DB, UI, forms, script
    sysm = types.ModuleType("System"); coll = types.ModuleType("System.Collections")
    gen = types.ModuleType("System.Collections.Generic"); gen.List = type("List", (list,), {"__class_getitem__": classmethod(lambda c, i: c),
                                         "Add": lambda s, x: s.append(x)})
    adsk = types.ModuleType("Autodesk"); rv = types.ModuleType("Autodesk.Revit")
    exc = types.ModuleType("Autodesk.Revit.Exceptions"); exc.OperationCanceledException = OperationCanceledException
    mods = {"pyrevit": pyrevit, "System": sysm, "System.Collections": coll, "System.Collections.Generic": gen,
            "Autodesk": adsk, "Autodesk.Revit": rv, "Autodesk.Revit.Exceptions": exc}
    return mods, calls

def run(path, scenario):
    mods, calls = build(scenario)
    saved = {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    try:
        runpy.run_path(path, run_name="__main__"); return "completed", calls
    except ExitScript: return "script.exit()/alert-exit", calls
    except BaseException as e: return "%s: %s" % (type(e).__name__, e), calls
    finally:
        for k, v in saved.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v

fails = 0
def check(name, got, cond):
    global fails
    ok = cond(got); fails += (not ok)
    print("[%s] %s -> %s" % ("PASS" if ok else "FAIL", name, got))

print("--- extension (fixed) ---")
CA = NEW + "/Clash Avoid.pushbutton/script.py"
AH = NEW + "/Auto Hangers.pushbutton/script.py"
r, _ = run(CA, "clash_cancel")
check("BUG-01/06 Clash: ESC -> clean exit", r, lambda g: g == "script.exit()/alert-exit")
r, _ = run(CA, "clash_bug")
check("BUG-06 Clash: non-cancel error is NOT swallowed", r, lambda g: g.startswith("RuntimeError"))
r, c = run(AH, "hangers")
check("BUG-03/04/05 Hangers: runs to completion", r, lambda g: g == "completed")
check("BUG-05 Hangers: hangers actually placed (10ft pipe, 2000mm)", c["placed"], lambda n: n >= 2)
print("\nFAILED CHECKS:", fails)
sys.exit(1 if fails else 0)
