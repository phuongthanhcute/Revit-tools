"""Chạy thử tool trong terminal trên Revit GIẢ (để xem luồng hỏi-đáp / thông báo, không thay được Revit thật).

    python3 tests/try_it.py

Trả lời các câu hỏi như khi dùng thật:
  - Ô nhập: Enter = nhận giá trị mặc định, gõ giá trị khác rồi Enter, 'q' = Cancel.
  - Danh sách chọn: gõ số thứ tự rồi Enter, 'q' = Cancel.
  - Hộp Yes/No: gõ y hoặc n.
Cảnh mẫu (ống, dầm, miệng gió...) được dựng sẵn, xem phần SCENE của từng tool.
"""
import os, sys, types, runpy
from unittest.mock import MagicMock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fakerevit as fr
from fakerevit import (Doc, Duct, Pipe, FamilyInstance, FlexDuct, Param, Box, Conn, CM, make_curve_elem,
                       XYZ, mm, tomm, ExitScript)

ROOT = os.path.join(fr.LIB, "..", "HVAC.tab", "Utilities.panel")
SCRIPT = {"clash": "Clash Avoid", "hangers": "Auto Hangers", "routing": "Auto Routing", "split": "Split Pipes"}


def P(x, y, z):
    return XYZ(mm(x), mm(y), mm(z))


def ask(prompt):
    try:
        return input(prompt)
    except EOFError:
        raise ExitScript()


# ---------------------------------------------------------------- UI giả (hộp thoại -> terminal)
def ui_alert(msg, title="", yes=False, no=False, exitscript=False, **k):
    print("\n+" + "-" * 70 + "+\n| [HỘP THOẠI] " + str(title or "pyRevit"))
    for line in str(msg).splitlines() or [""]:
        print("|  " + line)
    print("+" + "-" * 70 + "+")
    result = None
    if yes or no:
        result = ask("  Yes / No (y/n)? ").strip().lower().startswith("y")
    if exitscript:
        raise ExitScript()
    return result


def ui_ask_for_string(default="", prompt="", title="", **k):
    print("\n[Ô NHẬP] {}\n  {}".format(title, prompt.replace("\n", "\n  ")))
    text = ask("  (Enter = '{}', q = hủy) > ".format(default)).strip()
    if text.lower() == "q":
        return None
    return text or default


def ui_select(opts, title="", button_name="OK", sym=None, **k):
    opts = list(opts)
    if title == "Chọn Family Giá Đỡ":   # cảnh mẫu có sẵn 1 family giá đỡ
        print("\n[CHỌN] {} -> tự chọn 'Giá đỡ mẫu'".format(title))
        return sym
    print("\n[CHỌN] {}".format(title))
    for i, o in enumerate(opts, 1):
        print("  {}. {}".format(i, getattr(o, "name", o)))
    while True:
        text = ask("  Nhập số (q = hủy) > ").strip().lower()
        if text == "q":
            return None
        if text.isdigit() and 1 <= int(text) <= len(opts):
            o = opts[int(text) - 1]
            return getattr(o, "item", o)
        print("  Số không hợp lệ.")


def run_interactive(path, doc, scenario, sym=None):
    mods = fr.build(doc, scenario)
    py = mods["pyrevit"]
    py.forms.alert = ui_alert
    py.forms.ask_for_string = ui_ask_for_string
    py.forms.SelectFromList = types.SimpleNamespace(show=lambda opts, **k: ui_select(opts, sym=sym, **k))
    py.DB.Element.Name.GetValue = lambda it: getattr(it, "Name", "?")
    if fr.LIB not in sys.path:
        sys.path.insert(0, fr.LIB)
    sys.modules.pop("mep_common", None)
    saved = {k: sys.modules.get(k) for k in mods}
    sys.modules.update(mods)
    try:
        runpy.run_path(path, run_name="__main__")
        return "completed"
    except ExitScript:
        return "exit"
    except BaseException as e:
        return "LỖI {}: {}".format(type(e).__name__, e)
    finally:
        sys.modules.pop("mep_common", None)
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def tool_path(key):
    return os.path.join(ROOT, SCRIPT[key] + ".pushbutton", "script.py")


def pt(p):
    return "({:.0f}, {:.0f}, {:.0f})".format(tomm(p.X), tomm(p.Y), tomm(p.Z))


def seg_text(e):
    c = e.Location.Curve
    return "{} -> {}".format(pt(c.a), pt(c.b))


# ---------------------------------------------------------------- các cảnh mẫu
def scene_clash():
    print("SCENE: 2 ống gió 600x300 dài 20 m song song (y=0 và y=900, cao độ z=3000); 3 dầm cao 300 (z 2900~3200), rộng 300, "
          "cắt ngang tại x=6000, x=10000 và x=10800 (hai dầm sau cách nhau 800 mm nên sẽ được gộp).")
    doc = Doc(); doc.ActiveView = fr.View()
    ducts = [doc.add(make_curve_elem(Duct, P(0, y, 3000), P(20000, y, 3000),
                                     {"Width": Param(mm(600)), "Height": Param(mm(300))})) for y in (0, 900)]
    ids = []
    for i, x in enumerate((6000, 10000, 10800)):
        class Obs:
            bbox = Box(P(x - 150, -3000, 2900), P(x + 150, 3000, 3200))
            def get_BoundingBox(self, w): return self.bbox
        o = Obs(); o.Id = "Dầm {}".format(i + 1); doc.els[o.Id] = o; ids.append(o.Id)
    print("(Bước chọn ống/vật cản được tự động: chọn cả 2 ống và cả 3 dầm.)")
    sc = {"pick_lists": [[d.Id for d in ducts], ids]}
    return doc, sc, None


def after_clash(doc, sc):
    ducts = [e for e in doc.els.values() if isinstance(e, Duct)]
    print("\nKẾT QUẢ MÔ HÌNH: {} đoạn ống, {} elbow".format(len(ducts), len(doc.elbows)))
    for y in (0, 900):
        row = sorted([d for d in ducts if abs(tomm(d.Location.Curve.a.Y) - y) < 1], key=lambda d: d.Location.Curve.a.X)
        print("  ống y={}: {} đoạn".format(y, len(row)))
        for i, d in enumerate(row, 1):
            print("    đoạn {}: {}".format(i, seg_text(d)))
    for el in doc.elbows:
        print("  elbow tại {} góc {}°".format(el[0], el[2]))


def scene_hangers():
    print("SCENE: ống gió 600x300 (bảo ôn 25) dài 6 m, ống nước Ø100 dài 6 m; sàn ở z=4000; có 1 phụ kiện tại x=3000 và 1 miệng gió tại x=1500.")
    doc = Doc(); v = fr.View3D(); v.Id = "V"; doc.ActiveView = v
    d = doc.add(make_curve_elem(Duct, P(0, 0, 3000), P(6000, 0, 3000),
                                {"Width": Param(mm(600)), "Height": Param(mm(300)), "RBS_REFERENCE_INSULATION_THICKNESS": Param(mm(25))}))
    p = doc.add(make_curve_elem(Pipe, P(0, 2000, 3000), P(6000, 2000, 3000), {"Diameter": Param(mm(100))}))
    d.ConnectorManager.Connectors[1].IsConnected = True   # đầu cuối nối vào thứ gì đó, đầu đầu tự do
    sym = MagicMock(); sym.IsActive = True
    sc = {"selection": [d, p], "slab_z": mm(4000),
          "fittings": [Box(P(2950, -300, 2800), P(3050, 300, 3200))],
          "equipment": [Box(P(1450, -200, 3300), P(1550, 200, 3500))]}
    return doc, sc, sym


def after_hangers(doc, sc):
    print("\nKẾT QUẢ MÔ HÌNH: {} giá đỡ".format(len(doc.placed)))
    for h in doc.placed:
        rod = h.p.get("Rod Length"); w = h.p.get("Width")
        print("  giá tại {}  Width={}  Rod Length={}".format(
            pt(h.pt), "{:.0f}".format(tomm(w.v)) if w.sets else "-", "{:.0f}".format(tomm(rod.v)) if rod.sets else "-"))


def scene_routing():
    print("SCENE: ống chính 600x300 dài 6 m ở z=3000, đầu x=0 nối cút; 3 miệng gió tròn Ø200 ở z=2600 (x=500, 3000, 5500); "
          "2 loại ống mềm; 1 loại bảo ôn.")
    doc = Doc(); doc.ActiveView = fr.View(); doc.ActiveView.Id = "V"
    main = doc.add(make_curve_elem(Duct, P(0, 0, 3000), P(6000, 0, 3000), {"Width": Param(mm(600)), "Height": Param(mm(300))}))
    elb = FamilyInstance(); elb.Id = "ELB"; elb.MEPModel = types.SimpleNamespace(PartType="Elbow")
    main.ConnectorManager.Connectors[0].AllRefs = [types.SimpleNamespace(Owner=elb)]
    terms = []
    for i, x in enumerate((500, 3000, 5500)):
        t = FamilyInstance(); t.Id = "Miệng gió {}".format(i + 1)
        t.Category = types.SimpleNamespace(Id=types.SimpleNamespace(IntegerValue=7))
        c = Conn(t, pt=P(x, 300, 2600)); c.Domain = "Hvac"; c.Shape = "Round"; c.Radius = mm(100)
        t.MEPModel = types.SimpleNamespace(ConnectorManager=CM([c])); doc.els[t.Id] = t; terms.append(t)
    sc = {"selection": terms, "flex": [],
          "flextypes": [types.SimpleNamespace(Id="F1", Name="Flex Duct - Round"), types.SimpleNamespace(Id="F2", Name="Flex Duct - Insulated")],
          "instypes": [types.SimpleNamespace(Id="I1", Name="Glass wool")]}
    return doc, sc, None


def after_routing(doc, sc):
    flexes = sc["flex"]
    print("\nKẾT QUẢ MÔ HÌNH: {} ống mềm, {} cổ trích, bảo ôn: {}".format(len(flexes), len(doc.takeoffs), len(sc.get("insulated", []))))
    for tk in doc.takeoffs:
        print("  cổ trích tại {}".format(tk[0]))
    for f in flexes:
        dia = f._params.get("RBS_CURVE_DIAMETER_PARAM")
        print("  ống mềm đường kính: {}".format("{:.0f} mm".format(tomm(dia.v)) if dia and dia.sets else "mặc định (không gán)"))


def scene_split():
    print("SCENE: ống gió dài 5000 mm và ống nước dài 13000 mm (cả hai chọn cùng lúc).")
    doc = Doc(); doc.ActiveView = fr.View()
    d = doc.add(make_curve_elem(Duct, P(0, 0, 3000), P(5000, 0, 3000)))
    p = doc.add(make_curve_elem(Pipe, P(0, 2000, 3000), P(13000, 2000, 3000)))
    return doc, {"selection": [d, p]}, None


def after_split(doc, sc):
    els = sorted(doc.els.values(), key=lambda e: (type(e).__name__, e.Location.Curve.a.X))
    print("\nKẾT QUẢ MÔ HÌNH: {} đoạn ống, {} Union".format(len(els), len(doc.unions)))
    for e in els:
        c = e.Location.Curve
        print("  {} dài {:.0f} mm: {}".format("Ống gió" if isinstance(e, Duct) else "Ống nước", tomm(c.Length), seg_text(e)))


TOOLS = [("clash", "Clash Avoidance - bẻ ống né vật cản", scene_clash, after_clash),
         ("hangers", "Auto Hangers - rải giá đỡ", scene_hangers, after_hangers),
         ("routing", "Auto Routing - ống mềm vào miệng gió", scene_routing, after_routing),
         ("split", "Split Ducts/Pipes - chia ống", scene_split, after_split)]


def main():
    while True:
        print("\n=== CHẠY THỬ TRÊN REVIT GIẢ ===")
        for i, (_, label, _, _) in enumerate(TOOLS, 1):
            print("  {}. {}".format(i, label))
        text = ask("Chọn tool (q = thoát) > ").strip().lower()
        if text == "q":
            return
        if not (text.isdigit() and 1 <= int(text) <= len(TOOLS)):
            continue
        key, label, scene, after = TOOLS[int(text) - 1]
        print("\n--- {} ---".format(label))
        doc, sc, sym = scene()
        if sym is not None:
            sc["sym"], sc["select"] = sym, sym
        print("\n(bấm nút trên ribbon...)")
        result = run_interactive(tool_path(key), doc, sc, sym)
        print("\n[tool kết thúc: {}]".format(result))
        if result == "completed":
            after(doc, sc)


if __name__ == "__main__":
    main()
