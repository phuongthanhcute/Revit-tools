# -*- coding: utf-8 -*-
__title__ = "Auto Hangers\n(Smart)"
__doc__ = """Tự động rải giá đỡ có tính năng Bắn tia (Raytrace) tìm trần bê tông.

Cách dùng:
1. Mở khung nhìn 3D (3D View). (Bắt buộc để thuật toán bắn tia hoạt động).
2. Chọn các đường ống cần rải giá đỡ (ống đứng sẽ được bỏ qua).
3. Chạy tool.
4. Chọn loại Family giá đỡ và nhập tham số.
5. Tool chèn giá đỡ, né phụ kiện (nếu còn dư nhịp), bỏ qua vị trí đã có giá đỡ và kéo dài ty treo đụng sàn/dầm.
Báo cáo cuối cho biết giá nào chưa tính được ty treo và vì sao."""

from pyrevit import revit, DB, forms
from pyrevit import script
from System.Collections.Generic import List
import math
from mep_common import (mm_to_ft, ft_to_mm, get_section_size, get_insulation_thickness, get_nominal_diameter,
                        ask_positive_number, confirm_over_limit, confirm_under_limit, is_end_free,
                        SPAN_PRESETS, span_from_rows)

doc = revit.doc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
# Khoảng cách giá đỡ tới mối nối/phụ kiện: ống gió >= 200mm (DW-02.02 chú thích 2, HD mục 6.1.3.15);
# ống nước 100~300mm (HD mục 4.1.3.12, 4.2.3.4) nên lấy cận dưới 100mm.
# Các giá trị dưới đây chỉ là MẶC ĐỊNH của ô nhập; người dùng có thể đổi khi chạy tool.
DUCT_FITTING_CLEARANCE_MM = 200  # mặc định: giá đỡ ống gió cách phụ kiện / tay nhánh (tê, cổ trích)
PIPE_FITTING_CLEARANCE_MM = 100  # mặc định: như trên, cho ống nước
EQUIPMENT_CLEARANCE_MM = 300     # mặc định (tự chọn, chuẩn không nêu số): giá đỡ cách thiết bị / miệng gió. HD 6.1.3.15: không đặt giá trùng cửa gió
END_SUPPORT_OFFSET_MM = 250      # [FIX_CỨNG]: giá cuối tuyến ống gió cách đầu ống tự do (chuẩn: <= 300mm, DW-02.02)
MIN_REASONABLE_SPACING_MM = 200  # [FIX_CỨNG]: nhịp tuỳ biến < 200mm thì hỏi xác nhận (thường là nhập nhầm đơn vị)
END_SUPPORT_MAX_MM = 300         # [FIX_CỨNG]: giá gần nhất cách đầu ống tự do quá 300mm thì bổ sung giá cuối tuyến
CUSTOM_SPAN_LABEL = "Tuỳ biến - nhập một nhịp chung cho nhóm này"
ROD_END_OPTIONS = [
    "Đỉnh ống (kể cả bảo ôn) - ty chỉ tới đỉnh ống (mặc định)",
    "Tâm ống",
    "Đáy ống (kể cả bảo ôn) - ty tới thanh đỡ dưới đáy ống (DW-02.03)",
]
DUCT_MAX_SPACING_MM = 2500       # [FIX_CỨNG]: nhịp giá đỡ ống gió cứng tối đa nếu thiết kế không nêu (DW-02.02 chú thích 1)
NUDGE_STEP_MM = 150          # [FIX_CỨNG]: mỗi lần dịch giá đỡ để né phụ kiện
EXISTING_HANGER_TOL_MM = 100 # [FIX_CỨNG]: có giá cùng loại trong bán kính 100mm thì coi là đã tồn tại
MIN_HORIZONTAL_COMPONENT = 0.5  # [FIX_CỨNG]: thành phần nằm ngang của tuyến ống < 0.5 (dốc > 60 độ) = ống đứng, bỏ qua
WIDTH_PARAM_NAMES = ["Width", "Rộng", "Đường kính", "Diameter"]  # tên tham số bề rộng của family giá đỡ


# Hàm phụ trợ
def get_angle_to_rotate(tangent_vector):
    # Lấy góc của vector tiếp tuyến so với trục X (tính trên mặt phẳng XY), cộng 90 độ để vuông góc ống
    return math.atan2(tangent_vector.Y, tangent_vector.X) + (math.pi / 2)


def set_parameter_if_exists(element, param_names, value):
    """Gán value cho tham số đầu tiên ghi được trong param_names. Trả về True nếu gán được."""
    for param_name in param_names:
        param = element.LookupParameter(param_name)
        if param and not param.IsReadOnly:
            try:
                param.Set(value)
                return True
            except Exception as e:
                print("Không gán được tham số '{}': {}".format(param_name, e))
    return False


def raytrace_to_slab(view3d, start_point):
    """Bắn tia từ start_point lên trên (trục Z). Trả về khoảng cách (feet) tới sàn/dầm gần nhất, hoặc None."""
    cat_filter = DB.LogicalOrFilter(
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_Floors),
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_StructuralFraming)
    )
    intersector = DB.ReferenceIntersector(cat_filter, DB.FindReferenceTarget.Face, view3d)
    intersector.FindSpatialElementFromBoundingBox = False
    ref_with_context = intersector.FindNearest(start_point, DB.XYZ.BasisZ)
    if ref_with_context:
        return ref_with_context.Proximity
    return None


def _box_filter(pt, half_ft):
    return DB.BoundingBoxIntersectsFilter(DB.Outline(
        DB.XYZ(pt.X - half_ft, pt.Y - half_ft, pt.Z - half_ft),
        DB.XYZ(pt.X + half_ft, pt.Y + half_ft, pt.Z + half_ft)))


def is_point_near_fittings(pt, clearance_ft):
    """Vị trí pt có nằm sát Fitting (Elbow, Tee, Cross, Transition, cổ trích) nào không. Quét toàn model (không chỉ view hiện hành)."""
    cat_filter = DB.LogicalOrFilter(
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_DuctFitting),
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_PipeFitting)
    )
    near = DB.FilteredElementCollector(doc) \
        .WherePasses(_box_filter(pt, clearance_ft)) \
        .WherePasses(cat_filter) \
        .ToElementIds()
    return len(near) > 0


def is_point_near_equipment(pt, clearance_ft):
    """Vị trí pt có nằm sát thiết bị cơ khí hoặc miệng gió không (không đặt giá trùng cửa gió)."""
    cat_filter = DB.LogicalOrFilter(
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_DuctTerminal),
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_MechanicalEquipment)
    )
    near = DB.FilteredElementCollector(doc) \
        .WherePasses(_box_filter(pt, clearance_ft)) \
        .WherePasses(cat_filter) \
        .ToElementIds()
    return len(near) > 0


def has_neighbor_duct_at(pt, elem, tol_ft):
    """Có ống gió KHÁC có đầu mút trùng pt không (đoạn ống kề nhau dù connector chưa nối, ví dụ Union bị lỗi khi Split)."""
    nearby = DB.FilteredElementCollector(doc) \
        .OfClass(DB.Mechanical.Duct) \
        .WherePasses(_box_filter(pt, tol_ft)) \
        .ToElements()
    for other in nearby:
        if other.Id == elem.Id or not isinstance(other.Location, DB.LocationCurve):
            continue
        oc = other.Location.Curve
        if oc.GetEndPoint(0).DistanceTo(pt) <= tol_ft or oc.GetEndPoint(1).DistanceTo(pt) <= tol_ft:
            return True
    return False


def group_key(elem):
    """Nhóm ống để chọn tiêu chuẩn nhịp: ống gió một nhóm; ống nước theo Pipe Type."""
    if isinstance(elem, DB.Mechanical.Duct):
        return "Ống gió"
    try:
        return "Ống nước - {}".format(elem.PipeType.Name)
    except Exception:
        return "Ống nước"


def hanger_exists_near(pt, symbol_id, tol_ft):
    """Đã có giá đỡ cùng loại quanh pt chưa (để chạy lại tool không nhân đôi giá)."""
    nearby = DB.FilteredElementCollector(doc) \
        .OfClass(DB.FamilyInstance) \
        .WherePasses(_box_filter(pt, tol_ft)) \
        .ToElements()
    for inst in nearby:
        if inst.Symbol.Id == symbol_id:
            return True
    return False


def choose_distance(base_dist, length, slack_ft, step_ft, is_blocked):
    """
    Chọn vị trí giá đỡ dọc ống. Nếu vị trí gốc bị phụ kiện chặn thì thử dịch ±step, ±2*step, ...
    nhưng KHÔNG dịch quá `slack_ft` (một nửa phần nhịp còn dư), để khoảng cách giữa 2 giá không vượt spacing,
    và luôn nằm trong đoạn ống. Trả về (khoảng cách, né được hay không).
    """
    if not is_blocked(base_dist):
        return base_dist, True
    n = 1
    while n * step_ft <= slack_ft + 1e-9:
        for sign in (1, -1):
            d = base_dist + sign * n * step_ft
            if 0 < d < length and not is_blocked(d):
                return d, True
        n += 1
    return base_dist, False


# ==============================
# QUY TRÌNH CHẠY CHÍNH (MAIN)
# ==============================

# Raytrace yêu cầu 3D View
active_view = doc.ActiveView
if not isinstance(active_view, DB.View3D):
    forms.alert("Tính năng Bắn Tia (Raytrace) yêu cầu bạn phải mở khung nhìn 3D View trước khi chạy tool.", exitscript=True)

# 1. Lọc lấy các đối tượng người dùng đang chọn
selection = revit.get_selection()
mep_curves = []

for elem in selection.elements:
    if isinstance(elem, (DB.Plumbing.Pipe, DB.Mechanical.Duct)):
        mep_curves.append(elem)

ignored_count = len(selection.elements) - len(mep_curves)   # ống mềm, phụ kiện... (tool chưa hỗ trợ)

if not mep_curves:
    forms.alert("Vui lòng chọn ít nhất một Ống Gió (Duct) hoặc Ống Nước (Pipe).", exitscript=True)

# 2. Chọn Family Giá Đỡ
hanger_category_filters = [
    DB.BuiltInCategory.OST_PipeAccessory,
    DB.BuiltInCategory.OST_DuctAccessory,
    DB.BuiltInCategory.OST_GenericModel,
    DB.BuiltInCategory.OST_MechanicalEquipment
]

filter_list = List[DB.ElementFilter]()
for cat in hanger_category_filters:
    filter_list.Add(DB.ElementCategoryFilter(cat))
multi_cat_filter = DB.LogicalOrFilter(filter_list)

hanger_symbols = DB.FilteredElementCollector(doc) \
    .WherePasses(multi_cat_filter) \
    .OfClass(DB.FamilySymbol) \
    .ToElements()


class SymbolOption(forms.TemplateListItem):
    @property
    def name(self):
        return "{} - {}".format(self.item.FamilyName, DB.Element.Name.GetValue(self.item))


symbol_options = [SymbolOption(sym) for sym in hanger_symbols]
selected_symbol = forms.SelectFromList.show(
    symbol_options,
    title="Chọn Family Giá Đỡ",
    button_name="Chọn"
)

if not selected_symbol:
    script.exit()

# SelectFromList.show trả về đối tượng gốc (FamilySymbol) đã unwrap khỏi TemplateListItem
hanger_symbol = selected_symbol

if not hanger_symbol.IsActive:
    with revit.Transaction("Activate Hanger Symbol"):
        hanger_symbol.Activate()
        doc.Regenerate()

# 3. Form nhập tham số
# 3a. Nhịp giá đỡ: mỗi NHÓM ống (ống gió / mỗi Pipe Type) chọn một tiêu chuẩn nhịp riêng, hoặc "Tuỳ biến" (một nhịp chung)
groups = {}
for e in mep_curves:
    groups.setdefault(group_key(e), []).append(e)

span_rules = {}   # key -> (rows, basis) hoặc nhịp cố định (mm)
for key in sorted(groups):
    is_duct = isinstance(groups[key][0], DB.Mechanical.Duct)
    presets = [p for p in SPAN_PRESETS if (p[0].startswith("Ống gió")) == is_duct]
    labels = [CUSTOM_SPAN_LABEL] + [p[0] for p in presets]
    choice = forms.SelectFromList.show(labels, title="Chọn tiêu chuẩn nhịp giá đỡ: {}".format(key), button_name="Chọn")
    if not choice:
        script.exit()
    if choice == CUSTOM_SPAN_LABEL:
        custom_mm = ask_positive_number("2000", "Nhập khoảng cách giữa các giá đỡ (mm) cho [{}]:".format(key), "Khoảng cách")
        confirm_under_limit(custom_mm, MIN_REASONABLE_SPACING_MM, "Khoảng cách giá đỡ",
                            "nhỏ bất thường, có thể sinh ra rất nhiều giá đỡ (nhập nhầm đơn vị?)")
        if is_duct:
            confirm_over_limit(custom_mm, DUCT_MAX_SPACING_MM, "Khoảng cách giá đỡ ống gió",
                               "DW-02.02: ống gió cứng <= 2.5 m nếu thiết kế không nêu rõ")
        span_rules[key] = custom_mm
    else:
        span_rules[key] = [(p[1], p[2]) for p in presets if p[0] == choice][0]

# 3b. Khoảng cách tới phụ kiện / tay nhánh, và tới thiết bị / miệng gió (tuỳ biến được)
duct_fit_mm = pipe_fit_mm = None
if any(isinstance(e, DB.Mechanical.Duct) for e in mep_curves):
    duct_fit_mm = ask_positive_number(str(DUCT_FITTING_CLEARANCE_MM), "Khoảng cách giá đỡ tới phụ kiện / tay nhánh - ỐNG GIÓ (mm):", "Khoảng cách phụ kiện (ống gió)")
    confirm_under_limit(duct_fit_mm, DUCT_FITTING_CLEARANCE_MM, "Khoảng cách giá đỡ tới mối nối ống gió", "DW-02.02: >= 200 mm")
if any(isinstance(e, DB.Plumbing.Pipe) for e in mep_curves):
    pipe_fit_mm = ask_positive_number(str(PIPE_FITTING_CLEARANCE_MM), "Khoảng cách giá đỡ tới phụ kiện / tay nhánh - ỐNG NƯỚC (mm):", "Khoảng cách phụ kiện (ống nước)")
equip_mm = ask_positive_number(str(EQUIPMENT_CLEARANCE_MM), "Khoảng cách giá đỡ tới thiết bị / miệng gió (mm):", "Khoảng cách thiết bị")

# 3c. Ty treo
rod_param_name = forms.ask_for_string(default="Rod Length", prompt="Nhập TÊN BIẾN điều khiển Chiều Dài Ty treo trong Family:", title="Tên Parameter")
if not rod_param_name:
    rod_param_name = "Rod Length"  # Mặc định
rod_end_opt = forms.SelectFromList.show(ROD_END_OPTIONS, title="Ty treo kết thúc tại", button_name="Chọn")
if not rod_end_opt:
    script.exit()
rod_end_index = ROD_END_OPTIONS.index(rod_end_opt)   # 0=đỉnh ống, 1=tâm ống, 2=đáy ống

# Quy tắc rải: mỗi đoạn ống dài L đặt k = ceil(L / spacing) giá đỡ, giá thứ i nằm tại (i + 0.5) * L / k.
# - Khoảng cách giữa 2 giá trong 1 đoạn là L / k <= spacing.
# - Khoảng cách giữa 2 giá ở 2 đoạn liền kề = L1/(2*k1) + L2/(2*k2) <= spacing (chưa tính chiều dài phụ kiện nằm giữa).
# - Ống ngắn hơn spacing vẫn có đúng 1 giá ở chính giữa; không bao giờ có 2 giá sát nhau.
# - Ống gió có đầu ống TỰ DO (cuối tuyến): bổ sung 1 giá cách đầu ống <= 300mm nếu giá gần nhất xa hơn.

nudge_step_ft = mm_to_ft(NUDGE_STEP_MM)
existing_tol_ft = mm_to_ft(EXISTING_HANGER_TOL_MM)
equip_ft = mm_to_ft(equip_mm)

stats = {"placed": 0, "rod_ok": 0, "no_slab": 0, "rod_param_missing": 0,
         "vertical": 0, "existing": 0, "fitting_unavoidable": 0, "size_unknown": 0, "end_support": 0,
         "rod_nonpositive": 0}

with revit.Transaction("Rải Giá Đỡ Thông Minh (Smart Auto Hangers)"):
    for curve_elem in mep_curves:
        loc_curve = curve_elem.Location
        if not isinstance(loc_curve, DB.LocationCurve):
            continue

        curve = loc_curve.Curve
        length = curve.Length
        if length <= 1e-9:
            continue

        start_pt = curve.GetEndPoint(0)
        end_pt = curve.GetEndPoint(1)
        direction = (end_pt - start_pt).Normalize()

        # Ống đứng: góc xoay và tia bắn lên trục Z đều vô nghĩa -> bỏ qua
        if math.sqrt(direction.X ** 2 + direction.Y ** 2) < MIN_HORIZONTAL_COMPONENT:
            stats["vertical"] += 1
            continue

        is_duct = isinstance(curve_elem, DB.Mechanical.Duct)
        clearance_ft = mm_to_ft(duct_fit_mm if is_duct else pipe_fit_mm)
        width_ft, height_ft = get_section_size(curve_elem)
        if not width_ft:
            stats["size_unknown"] += 1
            width_ft = height_ft = 0.0
        insulation_ft = get_insulation_thickness(curve_elem)
        half_outer_ft = (height_ft / 2.0) + insulation_ft
        # Ty kết thúc ở: đỉnh ống (+half_outer), tâm ống (0) hoặc đáy ống (-half_outer)
        top_offset_ft = (half_outer_ft, 0.0, -half_outer_ft)[rod_end_index]

        # Nhịp của ống này theo quy tắc nhóm
        rule = span_rules[group_key(curve_elem)]
        if isinstance(rule, list) or isinstance(rule, tuple):
            rows, basis = rule
            diameter_ft = get_nominal_diameter(curve_elem) if basis == "dn" else width_ft
            spacing_ft = mm_to_ft(span_from_rows(rows, ft_to_mm(diameter_ft) if diameter_ft else None))
        else:
            spacing_ft = mm_to_ft(rule)

        num_hangers = max(1, int(math.ceil(length / spacing_ft)))
        # Phần nhịp còn dư. Mỗi giá chỉ được dịch tối đa NỬA phần dư: hai giá liền kề có thể dịch ngược chiều nhau
        # nên tổng nhịp tăng tối đa = phần dư, và nhịp vẫn <= spacing (kể cả khi qua mối nối giữa hai đoạn ống).
        slack_ft = max(0.0, spacing_ft - length / num_hangers) / 2.0

        def is_blocked(d):
            pt = start_pt + direction * d
            return is_point_near_fittings(pt, clearance_ft) or is_point_near_equipment(pt, equip_ft)

        positions = []
        for i in range(num_hangers):
            base_dist = (i + 0.5) * length / num_hangers
            dist, avoided = choose_distance(base_dist, length, slack_ft, nudge_step_ft, is_blocked)
            if not avoided:
                stats["fitting_unavoidable"] += 1
            positions.append(dist)

        # Giá cuối tuyến ống gió (đầu ống tự do): cách đầu ống <= 300mm, kèm kẹp trên đỉnh (chi tiết ở family)
        if is_duct:
            offset_ft = mm_to_ft(END_SUPPORT_OFFSET_MM)
            max_ft = mm_to_ft(END_SUPPORT_MAX_MM)
            if length > 2 * offset_ft:
                neighbor_tol_ft = mm_to_ft(10)
                if is_end_free(curve_elem, start_pt) and min(positions) > max_ft \
                        and not has_neighbor_duct_at(start_pt, curve_elem, neighbor_tol_ft):
                    positions.append(offset_ft)
                    stats["end_support"] += 1
                if is_end_free(curve_elem, end_pt) and length - max(positions) > max_ft \
                        and not has_neighbor_duct_at(end_pt, curve_elem, neighbor_tol_ft):
                    positions.append(length - offset_ft)
                    stats["end_support"] += 1

        for dist in positions:
            point_on_curve = start_pt + (direction * dist)

            if hanger_exists_near(point_on_curve, hanger_symbol.Id, existing_tol_ft):
                stats["existing"] += 1
                continue

            new_hanger = doc.Create.NewFamilyInstance(
                point_on_curve,
                hanger_symbol,
                DB.Structure.StructuralType.NonStructural
            )

            angle = get_angle_to_rotate(direction)
            if angle != 0:
                axis = DB.Line.CreateBound(point_on_curve, point_on_curve + DB.XYZ.BasisZ)
                DB.ElementTransformUtils.RotateElement(doc, new_hanger.Id, axis, angle)

            if width_ft > 0:
                # Ống bảo ôn: ty treo nằm ngoài lớp bảo ôn (DW-02.03) nên bề rộng giá = bề rộng ống + bảo ôn hai bên
                set_parameter_if_exists(new_hanger, WIDTH_PARAM_NAMES, width_ft + 2 * insulation_ft)

            # --- BẮN TIA (RAYTRACE) ---
            distance_to_slab = raytrace_to_slab(active_view, point_on_curve)
            if distance_to_slab is None:
                stats["no_slab"] += 1
            else:
                rod_length_ft = distance_to_slab - top_offset_ft
                if rod_length_ft <= 0:
                    # Sàn/dầm sát hoặc thấp hơn điểm kết thúc ty: không ghi chiều dài âm/0 vào family
                    stats["rod_nonpositive"] += 1
                # CHỈ ghi vào đúng tham số người dùng chỉ định (không đoán tên khác, tránh ghi đè nhầm tham số của family)
                elif set_parameter_if_exists(new_hanger, [rod_param_name], rod_length_ft):
                    stats["rod_ok"] += 1
                else:
                    stats["rod_param_missing"] += 1

            stats["placed"] += 1

# 4. Báo cáo
report = "Hoàn tất rải giá đỡ thông minh!\n\n"
report += "- Tổng số giá đỡ đã chèn: {}\n".format(stats["placed"])
report += "- Đã tự tính chiều dài ty treo: {}\n".format(stats["rod_ok"])
if stats["no_slab"]:
    report += "- CHƯA có ty treo (không tìm thấy sàn/dầm phía trên): {}\n".format(stats["no_slab"])
if stats["rod_nonpositive"]:
    report += "- CHƯA có ty treo (sàn/dầm sát hoặc thấp hơn điểm kết thúc ty, chiều dài ty <= 0): {}\n".format(stats["rod_nonpositive"])
if stats["rod_param_missing"]:
    report += "- CHƯA có ty treo (không ghi được tham số '{}': family không có tham số instance này, hoặc chỉ-đọc): {}\n".format(
        rod_param_name, stats["rod_param_missing"])
if stats["existing"]:
    report += "- Bỏ qua vì đã có giá đỡ cùng loại tại vị trí đó: {}\n".format(stats["existing"])
if stats["vertical"]:
    report += "- Ống đứng bỏ qua: {}\n".format(stats["vertical"])
if stats["fitting_unavoidable"]:
    report += "- Giá đỡ còn sát phụ kiện (không còn dư nhịp để dịch): {}\n".format(stats["fitting_unavoidable"])
if ignored_count:
    report += "- Phần tử bị bỏ qua vì không phải ống gió/ống nước cứng (ống mềm, phụ kiện...): {}\n".format(ignored_count)
if stats["end_support"]:
    report += "- Giá cuối tuyến ống gió (đầu ống tự do) đã bổ sung: {}\n".format(stats["end_support"])
if stats["size_unknown"]:
    report += "- Ống không đọc được kích thước (ty treo tính từ tâm ống): {}\n".format(stats["size_unknown"])

forms.alert(report, title="Kết Quả")
