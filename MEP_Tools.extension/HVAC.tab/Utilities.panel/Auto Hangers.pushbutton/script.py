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
from mep_common import (mm_to_ft, get_section_size, get_insulation_thickness, ask_positive_number)

doc = revit.doc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
FITTING_CLEARANCE_MM = 150   # [FIX_CỨNG]: vùng quanh giá đỡ (±150mm) được coi là "dính phụ kiện"
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
    """Vị trí pt có nằm sát Fitting (Elbow, Tee, Cross, Transition) nào không. Quét toàn model (không chỉ view hiện hành)."""
    cat_filter = DB.LogicalOrFilter(
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_DuctFitting),
        DB.ElementCategoryFilter(DB.BuiltInCategory.OST_PipeFitting)
    )
    near = DB.FilteredElementCollector(doc) \
        .WherePasses(_box_filter(pt, clearance_ft)) \
        .WherePasses(cat_filter) \
        .ToElementIds()
    return len(near) > 0


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
    nhưng KHÔNG dịch quá `slack_ft` (phần nhịp còn dư), để khoảng cách giữa 2 giá không vượt spacing,
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
spacing_ft = mm_to_ft(ask_positive_number("2000", "Nhập khoảng cách giữa các giá đỡ (mm):", "Khoảng cách"))

rod_param_name = forms.ask_for_string(default="Rod Length", prompt="Nhập TÊN BIẾN điều khiển Chiều Dài Ty treo trong Family:", title="Tên Parameter")
if not rod_param_name:
    rod_param_name = "Rod Length"  # Mặc định

# Quy tắc rải: mỗi đoạn ống dài L đặt k = ceil(L / spacing) giá đỡ, giá thứ i nằm tại (i + 0.5) * L / k.
# - Khoảng cách giữa 2 giá trong 1 đoạn là L / k <= spacing.
# - Khoảng cách giữa 2 giá ở 2 đoạn liền kề = L1/(2*k1) + L2/(2*k2) <= spacing (chưa tính chiều dài phụ kiện nằm giữa).
# - Ống ngắn hơn spacing vẫn có đúng 1 giá ở chính giữa; không bao giờ có 2 giá sát nhau.

clearance_ft = mm_to_ft(FITTING_CLEARANCE_MM)
nudge_step_ft = mm_to_ft(NUDGE_STEP_MM)
existing_tol_ft = mm_to_ft(EXISTING_HANGER_TOL_MM)

stats = {"placed": 0, "rod_ok": 0, "no_slab": 0, "rod_param_missing": 0,
         "vertical": 0, "existing": 0, "fitting_unavoidable": 0, "size_unknown": 0}

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

        width_ft, height_ft = get_section_size(curve_elem)
        if not width_ft:
            stats["size_unknown"] += 1
            width_ft = height_ft = 0.0
        # Ty treo bắt đầu từ MÉP TRÊN của ống (nửa chiều cao, cộng cách nhiệt), không phải nửa bề rộng
        top_offset_ft = (height_ft / 2.0) + get_insulation_thickness(curve_elem)

        num_hangers = max(1, int(math.ceil(length / spacing_ft)))
        slack_ft = max(0.0, spacing_ft - length / num_hangers)  # phần nhịp còn dư, giới hạn mức dịch né phụ kiện

        for i in range(num_hangers):
            base_dist = (i + 0.5) * length / num_hangers

            dist, avoided = choose_distance(
                base_dist, length, slack_ft, nudge_step_ft,
                lambda d: is_point_near_fittings(start_pt + direction * d, clearance_ft))
            if not avoided:
                stats["fitting_unavoidable"] += 1
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
                set_parameter_if_exists(new_hanger, WIDTH_PARAM_NAMES, width_ft)

            # --- BẮN TIA (RAYTRACE) ---
            distance_to_slab = raytrace_to_slab(active_view, point_on_curve)
            if distance_to_slab is None:
                stats["no_slab"] += 1
            else:
                # CHỈ ghi vào đúng tham số người dùng chỉ định (không đoán tên khác, tránh ghi đè nhầm tham số của family)
                if set_parameter_if_exists(new_hanger, [rod_param_name], distance_to_slab - top_offset_ft):
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
if stats["rod_param_missing"]:
    report += "- CHƯA có ty treo (không ghi được tham số '{}': family không có tham số instance này, hoặc chỉ-đọc): {}\n".format(
        rod_param_name, stats["rod_param_missing"])
if stats["existing"]:
    report += "- Bỏ qua vì đã có giá đỡ cùng loại tại vị trí đó: {}\n".format(stats["existing"])
if stats["vertical"]:
    report += "- Ống đứng bỏ qua: {}\n".format(stats["vertical"])
if stats["fitting_unavoidable"]:
    report += "- Giá đỡ còn sát phụ kiện (không còn dư nhịp để dịch): {}\n".format(stats["fitting_unavoidable"])
if stats["size_unknown"]:
    report += "- Ống không đọc được kích thước (ty treo tính từ tâm ống): {}\n".format(stats["size_unknown"])

forms.alert(report, title="Kết Quả")
