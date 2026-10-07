# -*- coding: utf-8 -*-
__title__ = "Clash\nAvoidance"
__doc__ = """Tự động tạo U-Shape (Offset) để bẻ lượn ống tránh chướng ngại vật.

Cách dùng:
1. Chạy tool.
2. Click chọn Ống (Duct/Pipe) bị vướng.
3. Click chọn Chướng ngại vật (Dầm, Ống nước, Tường...).
4. Chọn hướng né: Lên hoặc Xuống.
5. Tool tự tính độ cao và bề rộng vùng né từ BoundingBox của vật cản, cắt ống, sinh 4 lơi (Elbow) 45° và 3 đoạn ống.
Nếu bất kỳ lơi nào không tạo được, toàn bộ thay đổi được hoàn tác (model giữ nguyên) và tool báo rõ lý do."""

from pyrevit import revit, DB, UI, forms
from pyrevit import script
from Autodesk.Revit.Exceptions import OperationCanceledException
from System.Collections.Generic import List
import math
from mep_common import (mm_to_ft, get_connector_closest_to, get_section_size, get_insulation_thickness,
                        segment_hits_box, is_pinned)

doc = revit.doc
uidoc = revit.uidoc


def create_elbow_at_pt(doc, id1, id2, pt):
    """Tạo elbow nối 2 ống tại pt. Trả về None nếu thành công, hoặc chuỗi mô tả lý do thất bại."""
    conn1 = get_connector_closest_to(doc.GetElement(id1), pt)
    conn2 = get_connector_closest_to(doc.GetElement(id2), pt)
    if not (conn1 and conn2):
        return "không tìm thấy connector"
    try:
        doc.Create.NewElbowFitting(conn1, conn2)
    except Exception as e:
        return str(e)
    return None


class CustomISelectionFilter(UI.Selection.ISelectionFilter):
    def __init__(self, class_type=None):
        self.class_type = class_type
    def AllowElement(self, e):
        if self.class_type == "MEPCurve":
            return isinstance(e, (DB.Mechanical.Duct, DB.Plumbing.Pipe))
        return True
    def AllowReference(self, ref, point):
        return True

# ==============================
# QUY TRÌNH CHẠY CHÍNH (MAIN)
# ==============================

try:
    # 1. Yêu cầu người dùng chọn đối tượng trên màn hình
    duct_ref = uidoc.Selection.PickObject(
        UI.Selection.ObjectType.Element,
        CustomISelectionFilter("MEPCurve"),
        "BƯỚC 1: Click chọn ỐNG (Duct/Pipe) bị vướng"
    )
    main_mep = doc.GetElement(duct_ref)
    
    obs_ref = uidoc.Selection.PickObject(
        UI.Selection.ObjectType.Element,
        CustomISelectionFilter(),
        "BƯỚC 2: Click chọn CHƯỚNG NGẠI VẬT (Dầm / Ống / Cột) để né"
    )
    obstacle = doc.GetElement(obs_ref)
    
except OperationCanceledException:
    # Người dùng bấm ESC hủy lệnh (các lỗi khác phải nổi lên để còn biết mà sửa)
    script.exit()

if is_pinned(main_mep):
    forms.alert("Ống đã chọn đang bị Pin. Hãy Unpin trước khi chạy tool.", exitscript=True)

# Không hỏi chiều cao/rộng nữa, script tự động tính bằng BoundingBox!
# Chỉ hỏi hướng né (Up/Down) vì đôi khi lên trần thì đụng sàn, xuống dưới thì đụng trần giả
direction_opt = forms.SelectFromList.show(["Đi lên trên (Up)", "Đi xuống dưới (Down)"], title="Chọn hướng né va chạm", button_name="Tiếp tục")
if not direction_opt: script.exit()

# Lấy BoundingBox chướng ngại vật
obs_bbox = obstacle.get_BoundingBox(None)
if not obs_bbox:
    forms.alert("Không lấy được BoundingBox của chướng ngại vật.", exitscript=True)
obs_center = (obs_bbox.Min + obs_bbox.Max) / 2.0

# Tính toán điểm giao cắt
curve = main_mep.Location.Curve
project_res = curve.Project(obs_center)
if not project_res:
    forms.alert("Chướng ngại vật nằm quá xa đường ống, không thể tính toán chiếu vuông góc.", exitscript=True)

# TỰ ĐỘNG TÍNH TOÁN (AUTOMATIC GEOMETRY RESOLUTION)
# 1. Kích thước ngoài của ống (đọc bằng BuiltInParameter, không phụ thuộc ngôn ngữ Revit) + bề dày cách nhiệt
duct_w_ft, duct_h_ft = get_section_size(main_mep)
if not duct_h_ft:
    forms.alert("Không đọc được kích thước tiết diện của ống đã chọn nên không tính được khe hở. Hãy kiểm tra ống (Width/Height hoặc Diameter).", exitscript=True)
insulation_ft = get_insulation_thickness(main_mep)
duct_height_ft = duct_h_ft + 2 * insulation_ft   # chiều cao tiết diện ngoài, kể cả cách nhiệt hai phía

safe_clearance_ft = mm_to_ft(50) # [FIX_CỨNG]: 50mm hở an toàn chiều dọc từ đỉnh dầm đến đáy ống

# 2. Phương tuyến ống. Ống đứng / quá dốc thì hình học "nâng lên - hạ xuống" bị suy biến nên từ chối.
start_pt = curve.GetEndPoint(0)
end_pt = curve.GetEndPoint(1)
D_dir = (end_pt - start_pt).Normalize()
horiz_comp = math.sqrt(D_dir.X ** 2 + D_dir.Y ** 2)  # = cos(độ dốc của ống)
if horiz_comp < 0.5: # [FIX_CỨNG]: độ dốc > 60 độ coi như ống đứng (riser)
    forms.alert("Ống đang chọn là ống đứng hoặc dốc quá 60°. Tool chỉ né được ống nằm ngang hoặc dốc nhẹ.", exitscript=True)

# Vật cản phải thật sự nằm trên đường đi của ống (đường tâm nới ra nửa kích thước lớn nhất của ống + khe hở an toàn)
reach_ft = max(duct_w_ft, duct_h_ft) / 2.0 + insulation_ft + safe_clearance_ft
if not segment_hits_box(start_pt, end_pt, obs_bbox.Min, obs_bbox.Max, reach_ft):
    forms.alert("Chướng ngại vật không nằm trên đường đi của ống đã chọn (cách đường tâm ống hơn {:.0f} mm), nên không có gì để né. Hãy kiểm tra lại đối tượng đã click.".format(reach_ft * 304.8), exitscript=True)

# 3. Vùng né, tính trên MẶT BẰNG vì dầm/cột là lăng trụ thẳng đứng.
# Dh = phương nằm ngang của ống. E_h = bề rộng thật của BoundingBox chiếu lên Dh (8 đỉnh, không dùng đường chéo).
Dh = DB.XYZ(D_dir.X, D_dir.Y, 0) / horiz_comp
bbox_corners = [DB.XYZ(x, y, 0)
                for x in (obs_bbox.Min.X, obs_bbox.Max.X)
                for y in (obs_bbox.Min.Y, obs_bbox.Max.Y)]
corner_proj_h = [c.DotProduct(Dh) for c in bbox_corners]
E_h = max(corner_proj_h) - min(corner_proj_h)

# Điểm đường tâm ống nằm đúng "dưới" tâm dầm theo mặt bằng. (Không dùng curve.Project của tâm 3D:
# với ống dốc, tâm dầm lệch cao so với ống sẽ làm điểm chiếu trượt dọc ống và vùng né lệch khỏi dầm.)
t_clash = (obs_center - start_pt).DotProduct(Dh) / horiz_comp
pt_clash = start_pt + D_dir * t_clash

# L_gap đo DỌC ỐNG, sao cho đoạn giữa phủ trọn E_h trên mặt bằng + 50mm mỗi bên
L_gap = (E_h + mm_to_ft(100)) / horiz_comp # [FIX_CỨNG]: 100mm hở an toàn chiều ngang (50mm mỗi bên)

# 4. Tính chiều cao H cần né (độ lệch THẲNG ĐỨNG của đoạn giữa so với đường tâm ống)
# Nếu ống dốc, đoạn giữa song song với ống nên cao độ thay đổi dọc vùng né: tính tại đầu thấp nhất của vùng né.
slope_ft = (L_gap / 2.0) * abs(D_dir.Z)
min_offset_ft = mm_to_ft(100) # [FIX_CỨNG]: 100mm độ lệch tối thiểu khi THẬT SỰ cần né (nhỏ hơn thì elbow vô nghĩa)
going_up = (direction_opt == "Đi lên trên (Up)")
if going_up:
    O_dir = DB.XYZ.BasisZ
    target_z = obs_bbox.Max.Z + safe_clearance_ft + (duct_height_ft / 2.0)
    H_required = target_z - (pt_clash.Z - slope_ft)
else:
    O_dir = -DB.XYZ.BasisZ
    target_z = obs_bbox.Min.Z - safe_clearance_ft - (duct_height_ft / 2.0)
    H_required = (pt_clash.Z + slope_ft) - target_z

# H_required <= 0: ống đã nằm sẵn ở phía đó của vật cản (kể cả khe hở), không có va chạm theo hướng này.
# Không ép nâng/hạ "cho có" mà báo để người dùng chọn lại hướng.
if H_required <= 0:
    forms.alert("Ống đã nằm {} vật cản (kể cả khe hở an toàn) nên hướng \"{}\" không cần né. Nếu vật cản nằm ở phía còn lại của ống, hãy chạy lại và chọn hướng ngược lại.".format(
        "cao hơn đỉnh" if going_up else "thấp hơn đáy", direction_opt), exitscript=True)
H = max(H_required, min_offset_ft)

# 5. Góc lơi (Cố định chuẩn 45 độ của ngành MEP) - đo so với PHƯƠNG ỐNG, kể cả khi ống dốc
angle_deg = 45 # [FIX_CỨNG]: 45 độ góc bẻ lơi tiêu chuẩn
rad_angle = math.radians(angle_deg)

# Phân tích độ lệch thẳng đứng O_dir*H thành: thành phần dọc ống (o_along) + thành phần vuông góc ống (h_perp)
o_along = O_dir.DotProduct(D_dir) * H
h_perp = H * horiz_comp
L_horiz = h_perp / math.tan(rad_angle)   # khoảng cách dọc ống để đoạn xiên lệch đúng h_perp với góc 45° so với ống

# Tính 4 điểm mấu chốt. pA và pD LUÔN nằm trên đường tâm ống gốc (điều kiện để BreakCurve hợp lệ).
pB_line = pt_clash - D_dir * (L_gap / 2.0)
pC_line = pt_clash + D_dir * (L_gap / 2.0)

pA = pB_line + D_dir * (o_along - L_horiz)
pD = pC_line + D_dir * (o_along + L_horiz)

pB = pB_line + O_dir * H
pC = pC_line + O_dir * H

# KIỂM TRA ĐIỀU KIỆN AN TOÀN TRƯỚC KHI CẮT (CRITICAL GEOMETRY CHECK)
# Đảm bảo pA phải nằm "sau" điểm bắt đầu và pD phải nằm "trước" điểm kết thúc của ống gốc.
vec_start_to_pA = pA - start_pt
dist_to_pA = vec_start_to_pA.DotProduct(D_dir)

vec_start_to_pD = pD - start_pt
dist_to_pD = vec_start_to_pD.DotProduct(D_dir)

# Nếu điểm cắt rớt ra ngoài biên của ống (hoặc quá sát mép < 10mm)
if dist_to_pA < mm_to_ft(10) or dist_to_pD > (curve.Length - mm_to_ft(10)):
    forms.alert("Vị trí va chạm nằm quá sát đầu/cuối của ống. Không đủ không gian chèn 4 phụ kiện (Elbow) để bẻ lượn. Vui lòng nối dài ống gốc hoặc né bằng tay.", exitscript=True)

# 6. Thực thi việc cắt ống và tạo lơi. Tất cả trong 1 Transaction: lỗi ở bất kỳ bước nào => RollBack, model giữ nguyên.
tx = DB.Transaction(doc, "Né Va Chạm (Clash Avoidance)")
tx.Start()
error_message = None
try:
    # Bước 6.1: Break ống gốc thành 3 đoạn
    if isinstance(main_mep, DB.Mechanical.Duct):
        id_mid_to_end = DB.Mechanical.MechanicalUtils.BreakCurve(doc, main_mep.Id, pA)
        id_end = DB.Mechanical.MechanicalUtils.BreakCurve(doc, id_mid_to_end, pD)
    else:
        id_mid_to_end = DB.Plumbing.PlumbingUtils.BreakCurve(doc, main_mep.Id, pA)
        id_end = DB.Plumbing.PlumbingUtils.BreakCurve(doc, id_mid_to_end, pD)
    id_start = main_mep.Id

    # Bước 6.2: Copy đoạn giữa thành 3 đoạn nhỏ để kế thừa thuộc tính (kích thước, system)
    zero_vec = DB.XYZ(0, 0, 0)
    new_ids = []
    for _ in range(3):
        copied = DB.ElementTransformUtils.CopyElements(doc, List[DB.ElementId]([id_mid_to_end]), zero_vec)
        new_ids.append(list(copied)[0])
    id_d1, id_d2, id_d3 = new_ids

    # Bước 6.3: Xóa đoạn giữa bị đâm xuyên (chính là id_mid_to_end gốc)
    doc.Delete(id_mid_to_end)

    # Bước 6.4: Thay đổi đường tâm (LocationCurve) cho 3 đoạn copy
    doc.GetElement(id_d1).Location.Curve = DB.Line.CreateBound(pA, pB)
    doc.GetElement(id_d2).Location.Curve = DB.Line.CreateBound(pB, pC)
    doc.GetElement(id_d3).Location.Curve = DB.Line.CreateBound(pC, pD)

    # Bước 6.5: Tạo 4 Elbow. Thiếu bất kỳ elbow nào là hỏng kết nối => hoàn tác toàn bộ.
    elbow_failures = []
    for label, id_a, id_b, pt in (("tại A", id_start, id_d1, pA), ("tại B", id_d1, id_d2, pB),
                                  ("tại C", id_d2, id_d3, pC), ("tại D", id_d3, id_end, pD)):
        reason = create_elbow_at_pt(doc, id_a, id_b, pt)
        if reason:
            elbow_failures.append("{}: {}".format(label, reason))
    if elbow_failures:
        raise RuntimeError("không tạo được elbow ({})".format("; ".join(elbow_failures)))

    tx.Commit()
except Exception as e:
    tx.RollBack()
    error_message = str(e)

if error_message:
    forms.alert("Không thể bẻ ống né vật cản. Lý do: {}\n\nMọi thay đổi đã được hoàn tác, model giữ nguyên.".format(error_message),
                title="Clash Avoidance", exitscript=True)

forms.alert("Đã bẻ ống lượn qua chướng ngại vật thành công!", title="Clash Avoidance")
