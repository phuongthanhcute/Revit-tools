# -*- coding: utf-8 -*-
__title__ = "Auto\nRouting"
__doc__ = """Đấu nối tự động ống mềm (Flex Duct) từ Miệng gió / Hộp gió vào Ống chính.

Cách dùng:
1. Chọn các Miệng gió / Hộp gió cần đấu nối (family có connector gió còn trống).
2. Chạy tool; chọn loại ống mềm, có bảo ôn hay không, chiều dài tối đa (mặc định 2000 mm).
3. Tool tự động tìm Ống gió cứng (Duct) gần nhất (điểm tap luôn cách đầu ống một khoảng an toàn).
4. Tạo cổ trích (Tap) và vẽ ống mềm (Flex Duct) nối vào connector; đường kính ống mềm lấy theo connector.
Mỗi miệng gió được xử lý độc lập: miệng gió nào lỗi sẽ được hoàn tác sạch, không để lại ống mềm dở dang."""

from pyrevit import revit, DB, forms, script
from System.Collections.Generic import List
from mep_common import mm_to_ft, ft_to_mm, ask_positive_number, confirm_over_limit, get_section_size, read_length_param, is_pinned

doc = revit.doc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
TAP_END_CLEARANCE_MM = 200  # [FIX_CỨNG]: điểm tap cách đầu ống tối thiểu 200mm (chỗ cho cổ trích / phụ kiện)
FLEX_MAX_LENGTH_MM = 2000   # [FIX_CỨNG]: ống gió mềm <= 2m (DW-01.01 chú thích 3, HD mục 6.1.3.1)
FLEX_LENGTH_FACTOR = 1.2    # [FIX_CỨNG]: ống mềm phải uốn cong nên dài hơn khoảng cách thẳng ~20%
DEFAULT_INSULATION_MM = 25  # mặc định của ô nhập bề dày bảo ôn ống mềm
RECT_ELBOW_FACTOR = 8.0     # [FIX_CỨNG]: chân rẽ ống chữ nhật cách cút >= 8W (HD 6.1.3.22.7, DW-02.01)
ROUND_ELBOW_FACTOR = 6.0    # [FIX_CỨNG]: chân rẽ ống tròn cách cút >= 6D (HD 6.1.3.22.8)
TAP_COLLAR_GAP_MM = 100     # [ĐỀ XUẤT]: hai cổ trích cạnh nhau trên cùng một ống cách nhau (mép - mép) >= 100mm
DEFAULT_TAP_DIA_MM = 200    # đường kính giả định của cổ trích khi connector không tròn / không đọc được
NO_INSULATION = "Không bảo ôn (mặc định)"
WITH_INSULATION = "Có bảo ôn"


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


def end_has_elbow(duct, connector):
    """Đầu ống `connector` của `duct` có đang nối với một cút (Elbow) không. Không đọc được -> False."""
    try:
        for ref in connector.AllRefs:
            owner = ref.Owner
            if owner.Id == duct.Id:
                continue
            if isinstance(owner, DB.FamilyInstance) and owner.MEPModel.PartType == DB.PartType.Elbow:
                return True
    except Exception:
        pass
    return False


def elbow_distance_required(duct):
    """Khoảng cách tối thiểu từ chân rẽ tới cút: 8W (ống chữ nhật) hoặc 6D (ống tròn). None nếu không đọc được kích thước."""
    w, _ = get_section_size(duct)
    if not w:
        return None
    is_round = read_length_param(duct, ("RBS_CURVE_DIAMETER_PARAM",), ()) is not None
    return w * (ROUND_ELBOW_FACTOR if is_round else RECT_ELBOW_FACTOR)


def connector_diameter_ft(conn):
    """Đường kính (feet) của connector tròn; không đọc được thì dùng giá trị giả định."""
    try:
        if conn.Shape == DB.ConnectorProfileType.Round:
            return conn.Radius * 2.0
    except Exception:
        pass
    return mm_to_ft(DEFAULT_TAP_DIA_MM)


def systems_compatible(term_conn, duct):
    """Connector miệng gió và ống chính cùng loại hệ thống (cấp / hồi / thải...). Không biết một trong hai thì coi là khớp."""
    try:
        mep = duct.MEPSystem
        if mep is None:
            return True
        term_sys, duct_sys = term_conn.DuctSystemType, mep.SystemType
        undefined = DB.Mechanical.DuctSystemType.UndefinedSystemType
        if term_sys == undefined or duct_sys == undefined:
            return True
        return term_sys == duct_sys
    except Exception:
        return True


def find_tap_candidates(point, max_length_ft, term_conn, tap_dia_ft, used_taps, rejects):
    """
    Danh sách (khoảng cách, ống, điểm tap, cảnh báo cút) của các ống cứng quanh `point`, gần nhất trước.

    - Điểm tap là hình chiếu của point lên đường tâm ống, nhưng được kéo vào trong ống để luôn cách mỗi đầu
      ống >= TAP_END_CLEARANCE (ống ngắn hơn 2 lần khoảng này thì bị loại).
    - Đầu ống nối với cút: cố gắng cách cút >= 8W (chữ nhật) / 6D (tròn). Không đủ chỗ thì VẪN cho đặt (theo quyết định
      của kỹ sư) nhưng đánh dấu cảnh báo (phần tử thứ 4 = True).
    - Chỉ nhận ống mà ống mềm (khoảng cách thẳng x FLEX_LENGTH_FACTOR) không vượt max_length_ft.
    - Loại ống bị Pin, ống khác loại hệ thống với miệng gió, ống nhỏ hơn cổ trích; lý do được ghi vào `rejects` (set).
    - Hai cổ trích trên cùng một ống (cả những cổ trích đã tạo trong lần chạy này: `used_taps`) phải cách nhau đủ chỗ;
      điểm tap bị dịch dọc ống tới chỗ trống gần nhất, hết chỗ thì ống đó bị loại.
    Phần tử thứ 5 của kết quả là vị trí dọc ống (feet) của điểm tap.
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
        if is_pinned(duct):
            rejects.add("ống chính bị Pin (hãy Unpin)")
            continue
        if not systems_compatible(term_conn, duct):
            rejects.add("ống chính khác loại hệ thống với miệng gió (ví dụ cấp / hồi)")
            continue
        main_w, main_h = get_section_size(duct)
        if main_w and tap_dia_ft > max(main_w, main_h) + 1e-9:
            rejects.add("ống chính quá nhỏ cho cổ trích Ø{:.0f} mm".format(ft_to_mm(tap_dia_ft)))
            continue
        start = curve.GetEndPoint(0)
        direction = (curve.GetEndPoint(1) - start).Normalize()
        t = (curve.Project(point).XYZPoint - start).DotProduct(direction)

        # Khoảng cách tối thiểu tới mỗi đầu: 200mm, hoặc 8W/6D nếu đầu đó nối với cút
        lo = hi = clearance_ft
        required = elbow_distance_required(duct)
        elbow_ends = []
        if required:
            conns = list(duct.ConnectorManager.Connectors)
            for conn in conns:
                if end_has_elbow(duct, conn):
                    elbow_ends.append(conn.Origin.DistanceTo(start) < conn.Origin.DistanceTo(curve.GetEndPoint(1)))
        want_lo = max(clearance_ft, required) if (required and True in elbow_ends) else clearance_ft
        want_hi = max(clearance_ft, required) if (required and False in elbow_ends) else clearance_ft
        t_raw = t
        if want_lo + want_hi <= length:
            lo, hi = want_lo, want_hi
        t = max(lo, min(length - hi, t_raw))
        tap_pt = start + direction * t
        dist = point.DistanceTo(tap_pt)
        if dist > reach_ft and (lo, hi) != (clearance_ft, clearance_ft):
            # Vị trí đủ 8W/6D nằm quá xa (ống mềm vượt giới hạn): vẫn đặt ở vị trí gần nhất và cảnh báo
            lo = hi = clearance_ft
            t = max(lo, min(length - hi, t_raw))
            tap_pt = start + direction * t
            dist = point.DistanceTo(tap_pt)
        # Khoảng cách giữa các cổ trích trên cùng ống: nửa đường kính mỗi bên + khe hở
        used = used_taps.get(duct.Id, [])
        gap_ft = mm_to_ft(TAP_COLLAR_GAP_MM)
        def conflicts(tv):
            return any(abs(tv - tp) < (tap_dia_ft + dp) / 2.0 + gap_ft for tp, dp in used)
        if conflicts(t):
            step_ft, n, found = mm_to_ft(50), 1, None
            while found is None and n * step_ft <= length:
                for sign in (1, -1):
                    tv = t + sign * n * step_ft
                    if lo <= tv <= length - hi and not conflicts(tv):
                        found = tv
                        break
                n += 1
            if found is None:
                rejects.add("không còn chỗ trống trên ống để đặt thêm cổ trích (các cổ trích phải cách nhau đủ chỗ)")
                continue
            t = found
            tap_pt = start + direction * t
            dist = point.DistanceTo(tap_pt)
        warn = bool(required) and ((True in elbow_ends and t < required - 1e-9) or
                                   (False in elbow_ends and length - t < required - 1e-9))
        if dist <= reach_ft:
            candidates.append((dist, duct, tap_pt, warn, t))

    candidates.sort(key=lambda c: c[0])
    return candidates


def set_flex_diameter(flex_duct, term_conn):
    """Đặt đường kính ống mềm theo connector tròn của miệng gió / hộp gió. Trả về True nếu đặt được."""
    try:
        if term_conn.Shape != DB.ConnectorProfileType.Round:
            return False
        param = flex_duct.get_Parameter(DB.BuiltInParameter.RBS_CURVE_DIAMETER_PARAM)
        if param is None or param.IsReadOnly:
            return False
        param.Set(term_conn.Radius * 2.0)
        return True
    except Exception:
        return False


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

# 1. Lấy danh sách điểm đấu nối từ selection: miệng gió, hộp gió... bất kỳ family nào có connector gió còn trống
#    (ống mềm nối vào connector Duct Diameter có sẵn trên family)
selection = revit.get_selection()
terminals = [elem for elem in selection.elements if get_unconnected_connector(elem) is not None]

if not terminals:
    forms.alert("Vui lòng chọn ít nhất một Miệng Gió / Hộp gió (family có connector gió còn trống) trước khi chạy.", exitscript=True)

# 2. Nhập khoảng cách tối đa cho phép
max_length_mm = ask_positive_number(str(FLEX_MAX_LENGTH_MM), "Chiều dài Ống mềm tối đa cho phép (mm):", "Auto Routing")
confirm_over_limit(max_length_mm, FLEX_MAX_LENGTH_MM, "Chiều dài ống mềm",
                   "DW-01.01: ống gió mềm <= 2000 mm, độ võng <= 50 mm/m")
max_length_ft = mm_to_ft(max_length_mm)

# 3. Chọn loại Flex Duct (chỉ hỏi khi dự án có nhiều hơn một loại). Kích thước ống mềm lấy theo connector miệng gió.
class _NamedOption(forms.TemplateListItem):
    @property
    def name(self):
        return DB.Element.Name.GetValue(self.item)


flex_types = list(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.FlexDuctType).ToElements())
if not flex_types:
    forms.alert("Không tìm thấy loại Flex Duct nào trong dự án!", exitscript=True)
if len(flex_types) > 1:
    chosen_flex = forms.SelectFromList.show([_NamedOption(t) for t in flex_types], title="Chọn loại Flex Duct", button_name="Chọn")
    if not chosen_flex:
        script.exit()
    flex_type_id = chosen_flex.Id
else:
    flex_type_id = flex_types[0].Id

# 3b. Bảo ôn ống mềm (tuỳ chọn)
insulation_type_id = None
insulation_ft = 0.0
insulation_choice = forms.SelectFromList.show([NO_INSULATION, WITH_INSULATION], title="Ống mềm có bảo ôn không?", button_name="Chọn")
if not insulation_choice:
    script.exit()
if insulation_choice == WITH_INSULATION:
    ins_types = list(DB.FilteredElementCollector(doc).OfClass(DB.Mechanical.DuctInsulationType).ToElements())
    if not ins_types:
        forms.alert("Không tìm thấy loại bảo ôn ống gió (Duct Insulation Type) nào trong dự án!", exitscript=True)
    if len(ins_types) > 1:
        chosen_ins = forms.SelectFromList.show([_NamedOption(t) for t in ins_types], title="Chọn loại bảo ôn", button_name="Chọn")
        if not chosen_ins:
            script.exit()
        insulation_type_id = chosen_ins.Id
    else:
        insulation_type_id = ins_types[0].Id
    insulation_ft = mm_to_ft(ask_positive_number(str(DEFAULT_INSULATION_MM), "Bề dày bảo ôn ống mềm (mm):", "Bề dày bảo ôn"))

connected_count = 0
failures = []           # (id miệng gió, lý do)
default_system_count = 0
used_taps = {}          # id ống chính -> [(vị trí dọc ống, đường kính cổ trích)] đã tạo trong lần chạy này
elbow_warn_count = 0    # chân rẽ không đủ 8W / 6D tới cút (vẫn đặt)
size_unset_count = 0    # không đặt được đường kính ống mềm theo connector (dùng kích thước mặc định của loại ống)

# 4. Thực thi việc kết nối
with revit.Transaction("Auto Routing Flex Duct"):
    for terminal in terminals:
        term_conn = get_unconnected_connector(terminal)
        if not term_conn:
            failures.append((terminal.Id, "không có connector gió nào còn trống"))
            continue

        tap_dia_ft = connector_diameter_ft(term_conn)
        rejects = set()
        candidates = find_tap_candidates(term_conn.Origin, max_length_ft, term_conn, tap_dia_ft, used_taps, rejects)
        if not candidates:
            why = "không có ống chính nào đủ gần (<= {:.0f} mm sau khi tính hệ số uốn) hoặc ống quá ngắn để đặt cổ trích".format(max_length_mm)
            if rejects:
                why += "; ống ở gần nhưng bị loại: " + "; ".join(sorted(rejects))
            failures.append((terminal.Id, why))
            continue

        _, closest_duct, tap_pt, elbow_warn, tap_t = candidates[0]

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
            size_ok = set_flex_diameter(flex_duct, term_conn)
            if insulation_type_id is not None:
                DB.Mechanical.DuctInsulation.Create(doc, flex_duct.Id, insulation_type_id, insulation_ft)

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
            used_taps.setdefault(closest_duct.Id, []).append((tap_t, tap_dia_ft))
            if elbow_warn:
                elbow_warn_count += 1
            if not size_ok:
                size_unset_count += 1
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
if elbow_warn_count:
    report += "\n- CHÚ Ý: {} cổ trích cách cút gần hơn 8W (ống chữ nhật) / 6D (ống tròn) vì ống chính không đủ chỗ hoặc vị trí đủ chuẩn quá xa miệng gió (HD 6.1.3). Đã vẫn đặt theo yêu cầu, hãy kiểm tra.".format(elbow_warn_count)
if size_unset_count:
    report += "\n- CHÚ Ý: {} ống mềm chưa đặt được đường kính theo connector (connector không tròn hoặc tham số chỉ-đọc), đang dùng kích thước mặc định của loại ống.".format(size_unset_count)
if failures:
    report += "\n\nLý do (mỗi dòng 1 miệng gió, đầy đủ trong cửa sổ Output):"
    for term_id, reason in failures[:8]:
        report += "\n  • {}: {}".format(term_id, reason)
    if len(failures) > 8:
        report += "\n  ... và {} miệng gió khác".format(len(failures) - 8)
forms.alert(report, title="Kết Quả")
