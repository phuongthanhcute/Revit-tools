# -*- coding: utf-8 -*-
__title__ = "Auto\nRouting"
__doc__ = """Đấu nối tự động ống mềm (Flex Duct) từ Miệng gió vào Ống chính.

Cách dùng:
1. Chọn các Miệng gió (Air Terminals) cần đấu nối.
2. Chạy tool.
3. Tool tự động tìm Ống gió cứng (Duct) gần nhất (điểm tap luôn cách đầu ống một khoảng an toàn).
4. Tạo cổ trích (Tap) và vẽ ống mềm (Flex Duct) nối vào miệng gió.
Mỗi miệng gió được xử lý độc lập: miệng gió nào lỗi sẽ được hoàn tác sạch, không để lại ống mềm dở dang."""

from pyrevit import revit, DB, forms
from System.Collections.Generic import List
from mep_common import mm_to_ft, id_value, ask_positive_number

doc = revit.doc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
TAP_END_CLEARANCE_MM = 200  # [FIX_CỨNG]: điểm tap cách đầu ống tối thiểu 200mm (chỗ cho cổ trích / phụ kiện)
FLEX_LENGTH_FACTOR = 1.2    # [FIX_CỨNG]: ống mềm phải uốn cong nên dài hơn khoảng cách thẳng ~20%


def get_unconnected_connector(element):
    """Connector GIÓ (HVAC) đầu tiên chưa được kết nối của element (bỏ qua connector điện, v.v.)."""
    if not isinstance(element, DB.FamilyInstance):
        return None
    mep_model = element.MEPModel
    if mep_model is None or mep_model.ConnectorManager is None:
        return None
    for conn in mep_model.ConnectorManager.Connectors:
        if not conn.IsConnected and conn.Domain == DB.Domain.DomainHvac:
            return conn
    return None


def find_tap_candidates(point, max_length_ft):
    """
    Danh sách (khoảng cách, ống, điểm tap) của các ống cứng quanh `point`, gần nhất trước.

    - Điểm tap là hình chiếu của point lên đường tâm ống, nhưng được kéo vào trong ống để luôn cách mỗi đầu
      ống >= TAP_END_CLEARANCE (ống ngắn hơn 2 lần khoảng này thì bị loại).
    - Chỉ nhận ống mà ống mềm (khoảng cách thẳng x FLEX_LENGTH_FACTOR) không vượt max_length_ft.
    """
    clearance_ft = mm_to_ft(TAP_END_CLEARANCE_MM)
    reach_ft = max_length_ft / FLEX_LENGTH_FACTOR

    # Hộp bao quanh point bán kính reach_ft: Revit chỉ trả về các ống nằm gần (quét toàn model, không phụ thuộc view)
    min_pt = DB.XYZ(point.X - reach_ft, point.Y - reach_ft, point.Z - reach_ft)
    max_pt = DB.XYZ(point.X + reach_ft, point.Y + reach_ft, point.Z + reach_ft)
    nearby_ducts = DB.FilteredElementCollector(doc) \
        .OfClass(DB.Mechanical.Duct) \
        .WherePasses(DB.BoundingBoxIntersectsFilter(DB.Outline(min_pt, max_pt))) \
        .ToElements()

    candidates = []
    for duct in nearby_ducts:
        loc_curve = duct.Location
        if not isinstance(loc_curve, DB.LocationCurve):
            continue
        curve = loc_curve.Curve
        length = curve.Length
        if length < 2 * clearance_ft:
            continue
        start = curve.GetEndPoint(0)
        direction = (curve.GetEndPoint(1) - start).Normalize()
        t = (curve.Project(point).XYZPoint - start).DotProduct(direction)
        t = max(clearance_ft, min(length - clearance_ft, t))
        tap_pt = start + direction * t
        dist = point.DistanceTo(tap_pt)
        if dist <= reach_ft:
            candidates.append((dist, duct, tap_pt))

    candidates.sort(key=lambda c: c[0])
    return candidates


def get_system_type_id(duct):
    """Lấy System Type ID từ ống gió cứng"""
    if duct.MEPSystem:
        return duct.MEPSystem.GetTypeId()
    param = duct.get_Parameter(DB.BuiltInParameter.RBS_DUCT_SYSTEM_TYPE_PARAM)
    if param and param.AsElementId() != DB.ElementId.InvalidElementId:
        return param.AsElementId()
    return None


# ==============================
# QUY TRÌNH CHẠY CHÍNH (MAIN)
# ==============================

# 1. Lấy danh sách miệng gió từ selection
selection = revit.get_selection()
terminals = []

for elem in selection.elements:
    if elem.Category and id_value(elem.Category.Id) == int(DB.BuiltInCategory.OST_DuctTerminal):
        terminals.append(elem)

if not terminals:
    forms.alert("Vui lòng chọn ít nhất một Miệng Gió (Air Terminal) trước khi chạy.", exitscript=True)

# 2. Nhập khoảng cách tối đa cho phép
max_length_mm = ask_positive_number("3000", "Chiều dài Ống mềm tối đa cho phép (mm):", "Auto Routing")
max_length_ft = mm_to_ft(max_length_mm)

# 3. Lấy loại Flex Duct mặc định trong dự án
flex_types = DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType).ToElements()
if not flex_types:
    forms.alert("Không tìm thấy loại Flex Duct nào trong dự án!", exitscript=True)
flex_type_id = flex_types[0].Id

connected_count = 0
failures = []           # (id miệng gió, lý do)
default_system_count = 0

# 4. Thực thi việc kết nối
with revit.Transaction("Auto Routing Flex Duct"):
    for terminal in terminals:
        term_conn = get_unconnected_connector(terminal)
        if not term_conn:
            failures.append((terminal.Id, "không có connector gió nào còn trống"))
            continue

        candidates = find_tap_candidates(term_conn.Origin, max_length_ft)
        if not candidates:
            failures.append((terminal.Id, "không có ống chính nào đủ gần (<= {:.0f} mm sau khi tính hệ số uốn) hoặc ống quá ngắn để đặt cổ trích".format(max_length_mm)))
            continue

        _, closest_duct, tap_pt = candidates[0]

        sys_type_id = get_system_type_id(closest_duct)
        used_default_system = False
        if not sys_type_id:
            # Ống chính chưa có System: dùng System Type mặc định của dự án (CÓ THỂ SAI hệ thống -> báo cáo để kiểm tra)
            sys_type_id = doc.GetDefaultElementTypeId(DB.ElementTypeGroup.DuctSystemType)
            used_default_system = True

        pts = List[DB.XYZ]()
        pts.Add(tap_pt)
        pts.Add(term_conn.Origin)

        # Mỗi miệng gió là 1 SubTransaction: lỗi ở bước nào thì hoàn tác sạch, không để lại ống mềm mồ côi
        sub = DB.SubTransaction(doc)
        sub.Start()
        try:
            flex_duct = DB.Mechanical.FlexDuct.Create(doc, sys_type_id, flex_type_id, closest_duct.LevelId, pts)

            flex_conn_tap = None
            flex_conn_term = None
            for f_conn in flex_duct.ConnectorManager.Connectors:
                if f_conn.Origin.DistanceTo(tap_pt) < f_conn.Origin.DistanceTo(term_conn.Origin):
                    flex_conn_tap = f_conn
                else:
                    flex_conn_term = f_conn
            if flex_conn_tap is None or flex_conn_term is None:
                raise RuntimeError("không xác định được 2 đầu của ống mềm vừa tạo")

            # Bước 1: Nối đầu Flex Duct vào Miệng gió
            flex_conn_term.ConnectTo(term_conn)
            # Bước 2: Nối đầu còn lại vào Ống cứng bằng cổ trích (Takeoff/Tap)
            doc.Create.NewTakeoffFitting(flex_conn_tap, closest_duct)

            sub.Commit()
            connected_count += 1
            if used_default_system:
                default_system_count += 1
        except Exception as e:
            sub.RollBack()
            failures.append((terminal.Id, "lỗi Revit: {} (đã hoàn tác)".format(e)))

# 5. Báo cáo
for term_id, reason in failures:
    print("Miệng gió ID {}: {}".format(term_id, reason))

report = "Đấu nối hoàn tất!\n\n- Thành công: {}\n- Thất bại / Bỏ qua: {}".format(connected_count, len(failures))
if default_system_count:
    report += "\n- CHÚ Ý: {} đấu nối dùng System Type mặc định vì ống chính chưa thuộc hệ thống nào, hãy kiểm tra lại.".format(default_system_count)
if failures:
    report += "\n\nLý do (mỗi dòng 1 miệng gió, đầy đủ trong cửa sổ Output):"
    for term_id, reason in failures[:8]:
        report += "\n  • {}: {}".format(term_id, reason)
    if len(failures) > 8:
        report += "\n  ... và {} miệng gió khác".format(len(failures) - 8)
forms.alert(report, title="Kết Quả")
