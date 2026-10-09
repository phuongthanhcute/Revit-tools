# -*- coding: utf-8 -*-
__title__ = "Clash\nAvoidance"
__doc__ = """Tự động tạo U-Shape (Offset) để bẻ lượn ống tránh chướng ngại vật.

Cách dùng:
1. Chạy tool.
2. Click chọn các Ống (Duct/Pipe) bị vướng, bấm Finish.
3. Click chọn các Chướng ngại vật (Dầm, Ống nước, Tường...), bấm Finish.
4. Chọn hướng né (Lên/Xuống) và góc bẻ (mặc định 45°; có thể chọn 15°/30°/60°).
5. Với mỗi ống, tool tìm các vật cản nằm trên đường đi, tự tính độ cao và bề rộng vùng né từ BoundingBox,
   cắt ống và sinh 4 lơi (Elbow) + 3 đoạn ống cho từng chỗ né. Các vật cản quá gần nhau được gộp thành một chỗ né chung.
Mỗi chỗ né là một bước độc lập: chỗ nào không tạo được lơi thì hoàn tác riêng chỗ đó và báo rõ lý do,
các chỗ khác vẫn được làm. Cuối cùng cảnh báo nếu việc bẻ làm hai ống khác nhau có thể va chạm nhau."""

from pyrevit import revit, DB, UI, forms
from pyrevit import script
from Autodesk.Revit.Exceptions import OperationCanceledException
from System.Collections.Generic import List
import math
from mep_common import (mm_to_ft, ft_to_mm, get_connector_closest_to, get_section_size, get_insulation_thickness,
                        segment_hits_box, is_pinned, segments_min_distance)

doc = revit.doc
uidoc = revit.uidoc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
SAFE_CLEARANCE_MM = 50            # [FIX_CỨNG]: 50mm hở an toàn từ mặt ngoài (kể cả bảo ôn) tới vật cản (quy ước công ty)
MIN_OFFSET_MM = 100               # [FIX_CỨNG]: 100mm độ lệch tối thiểu khi THẬT SỰ cần né (nhỏ hơn thì elbow vô nghĩa)
SIDE_CLEARANCE_MM = 100           # [FIX_CỨNG]: 100mm hở ngang (50mm mỗi bên) của đoạn giữa quanh vật cản
MIN_END_MM = 10                   # [FIX_CỨNG]: điểm cắt cách đầu ống tối thiểu 10mm
MIN_STRAIGHT_BETWEEN_MM = 300     # [ĐỀ XUẤT]: hai chỗ né liền kề phải cách nhau >= 300mm ống thẳng, nếu không thì gộp thành một chỗ né chung
MIN_HORIZONTAL_COMPONENT = 0.5    # [FIX_CỨNG]: độ dốc > 60 độ coi là ống đứng (riser)
ANGLE_CHOICES = [("45° (mặc định)", 45), ("15° (khuyến nghị cho ống gió)", 15), ("30°", 30), ("60° (tối đa theo chuẩn)", 60)]


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


class DuctInfo(object):
    """Hình học và kích thước của một ống được chọn (đọc một lần)."""
    pass


def read_duct(elem):
    """Trả về (DuctInfo, None) hoặc (None, lý do từ chối)."""
    if is_pinned(elem):
        return None, "Ống đã chọn đang bị Pin. Hãy Unpin trước khi chạy tool."
    curve = elem.Location.Curve
    info = DuctInfo()
    info.elem, info.curve = elem, curve
    info.start, info.end = curve.GetEndPoint(0), curve.GetEndPoint(1)
    info.length = curve.Length
    info.dir = (info.end - info.start).Normalize()
    info.horiz = math.sqrt(info.dir.X ** 2 + info.dir.Y ** 2)   # = cos(độ dốc của ống)
    if info.horiz < MIN_HORIZONTAL_COMPONENT:
        return None, "Ống đang chọn là ống đứng hoặc dốc quá 60°. Tool chỉ né được ống nằm ngang hoặc dốc nhẹ."
    # Kích thước ngoài (BuiltInParameter, không phụ thuộc ngôn ngữ Revit) + bề dày cách nhiệt
    info.w, info.h = get_section_size(elem)
    if not info.h:
        return None, "Không đọc được kích thước tiết diện của ống đã chọn nên không tính được khe hở. Hãy kiểm tra ống (Width/Height hoặc Diameter)."
    info.ins = get_insulation_thickness(elem)
    info.height_total = info.h + 2 * info.ins    # chiều cao tiết diện ngoài, kể cả cách nhiệt hai phía
    info.reach = max(info.w, info.h) / 2.0 + info.ins + mm_to_ft(SAFE_CLEARANCE_MM)
    info.radius = max(info.w, info.h) / 2.0 + info.ins   # bán kính bao quanh, dùng kiểm tra va chạm giữa các ống
    return info, None


def box_union(boxes):
    mn = DB.XYZ(min(b[0].X for b in boxes), min(b[0].Y for b in boxes), min(b[0].Z for b in boxes))
    mx = DB.XYZ(max(b[1].X for b in boxes), max(b[1].Y for b in boxes), max(b[1].Z for b in boxes))
    return (mn, mx)


def compute_bump(info, box, going_up, rad_angle):
    """
    Tính 4 điểm gãy của chỗ né vật cản `box` = (min, max) cho ống `info`. Chưa kiểm tra biên đầu ống.
    Trả về (plan, None) hoặc (None, lý do không cần né).
    """
    D = info.dir
    bmin, bmax = box
    obs_center = (bmin + bmax) / 2.0

    # Vùng né tính trên MẶT BẰNG vì dầm/cột là lăng trụ thẳng đứng. E_h = bề rộng thật của BoundingBox chiếu lên
    # phương nằm ngang của ống (4 đỉnh mặt bằng, không dùng đường chéo).
    Dh = DB.XYZ(D.X, D.Y, 0) / info.horiz
    corner_proj_h = [DB.XYZ(x, y, 0).DotProduct(Dh) for x in (bmin.X, bmax.X) for y in (bmin.Y, bmax.Y)]
    E_h = max(corner_proj_h) - min(corner_proj_h)

    # Điểm đường tâm ống nằm đúng "dưới" tâm vật cản theo mặt bằng (không dùng curve.Project của tâm 3D: với ống dốc,
    # tâm vật cản lệch cao sẽ làm điểm chiếu trượt dọc ống).
    t_clash = (obs_center - info.start).DotProduct(Dh) / info.horiz
    pt_clash = info.start + D * t_clash

    # L_gap đo DỌC ỐNG, đoạn giữa phủ trọn E_h trên mặt bằng + 50mm mỗi bên
    L_gap = (E_h + mm_to_ft(SIDE_CLEARANCE_MM)) / info.horiz

    # Độ lệch thẳng đứng H. Ống dốc thì đoạn giữa song song với ống nên cao độ thay đổi dọc vùng né: tính tại đầu bất lợi nhất.
    slope_ft = (L_gap / 2.0) * abs(D.Z)
    safe_ft = mm_to_ft(SAFE_CLEARANCE_MM)
    if going_up:
        O_dir = DB.XYZ.BasisZ
        target_z = bmax.Z + safe_ft + (info.height_total / 2.0)
        H_required = target_z - (pt_clash.Z - slope_ft)
    else:
        O_dir = -DB.XYZ.BasisZ
        target_z = bmin.Z - safe_ft - (info.height_total / 2.0)
        H_required = (pt_clash.Z + slope_ft) - target_z
    if H_required <= 0:
        return None, "Ống đã nằm {} vật cản (kể cả khe hở an toàn) nên hướng \"{}\" không cần né. Nếu vật cản nằm ở phía còn lại của ống, hãy chạy lại và chọn hướng ngược lại.".format(
            "cao hơn đỉnh" if going_up else "thấp hơn đáy", "Đi lên trên (Up)" if going_up else "Đi xuống dưới (Down)")
    H = max(H_required, mm_to_ft(MIN_OFFSET_MM))

    # Phân tích độ lệch thẳng đứng O_dir*H thành thành phần dọc ống và vuông góc ống; mỗi chỗ bẻ đúng góc đã chọn SO VỚI PHƯƠNG ỐNG
    o_along = O_dir.DotProduct(D) * H
    h_perp = H * info.horiz
    L_horiz = h_perp / math.tan(rad_angle)

    pB_line = pt_clash - D * (L_gap / 2.0)
    pC_line = pt_clash + D * (L_gap / 2.0)
    plan = {
        # pA và pD LUÔN nằm trên đường tâm ống gốc (điều kiện để BreakCurve hợp lệ)
        "pA": pB_line + D * (o_along - L_horiz),
        "pD": pC_line + D * (o_along + L_horiz),
        "pB": pB_line + O_dir * H,
        "pC": pC_line + O_dir * H,
    }
    plan["tA"] = (plan["pA"] - info.start).DotProduct(D)   # vị trí dọc ống của chỗ cắt thứ nhất
    plan["tD"] = (plan["pD"] - info.start).DotProduct(D)   # vị trí dọc ống của chỗ cắt thứ hai
    return plan, None


def bounds_reason(info, plan):
    """Điểm cắt phải nằm trong ống (cách mép >= 10mm). Trả về chuỗi lý do hoặc None."""
    if plan["tA"] < mm_to_ft(MIN_END_MM) or plan["tD"] > info.length - mm_to_ft(MIN_END_MM):
        return "Vị trí va chạm nằm quá sát đầu/cuối của ống. Không đủ không gian chèn 4 phụ kiện (Elbow) để bẻ lượn. Vui lòng nối dài ống gốc hoặc né bằng tay."
    return None


def plan_groups(info, obstacle_boxes, going_up, rad_angle):
    """
    Nhóm các vật cản trên đường đi của ống thành các chỗ né. Hai chỗ né có khoảng ống thẳng giữa chúng
    < MIN_STRAIGHT_BETWEEN_MM thì gộp (hộp bao chung) và tính lại. Trả về (danh sách nhóm theo vị trí tăng dần, danh sách lý do bỏ qua).
    """
    gap_ft = mm_to_ft(MIN_STRAIGHT_BETWEEN_MM)
    items, skipped = [], []
    for ident, box in obstacle_boxes:
        plan, reason = compute_bump(info, box, going_up, rad_angle)
        if plan is None:
            skipped.append(reason)
        else:
            items.append({"boxes": [box], "box": box, "plan": plan, "ids": [ident]})
    items.sort(key=lambda g: g["plan"]["tA"])

    groups = []
    for item in items:
        groups.append(item)
        while len(groups) >= 2 and groups[-1]["plan"]["tA"] - groups[-2]["plan"]["tD"] < gap_ft:
            last = groups.pop()
            prev = groups.pop()
            boxes = prev["boxes"] + last["boxes"]
            union = box_union(boxes)
            plan, reason = compute_bump(info, union, going_up, rad_angle)
            if plan is None:   # không xảy ra (hộp bao chung luôn cao/thấp hơn từng hộp), giữ an toàn
                skipped.append(reason)
                groups.append(prev)
                continue
            groups.append({"boxes": boxes, "box": union, "plan": plan, "ids": prev["ids"] + last["ids"]})
    return groups, skipped


def execute_bump(head_elem, plan):
    """Cắt ống `head_elem` (đoạn đầu giữ ElementId gốc) tại pA, pD, dựng 3 đoạn + 4 elbow. Ném RuntimeError nếu lỗi."""
    if isinstance(head_elem, DB.Mechanical.Duct):
        id_mid_to_end = DB.Mechanical.MechanicalUtils.BreakCurve(doc, head_elem.Id, plan["pA"])
        id_end = DB.Mechanical.MechanicalUtils.BreakCurve(doc, id_mid_to_end, plan["pD"])
    else:
        id_mid_to_end = DB.Plumbing.PlumbingUtils.BreakCurve(doc, head_elem.Id, plan["pA"])
        id_end = DB.Plumbing.PlumbingUtils.BreakCurve(doc, id_mid_to_end, plan["pD"])
    id_start = head_elem.Id

    # Copy đoạn giữa thành 3 đoạn nhỏ để kế thừa thuộc tính (kích thước, system), rồi xóa đoạn giữa gốc
    new_ids = []
    for _ in range(3):
        copied = DB.ElementTransformUtils.CopyElements(doc, List[DB.ElementId]([id_mid_to_end]), DB.XYZ(0, 0, 0))
        new_ids.append(list(copied)[0])
    id_d1, id_d2, id_d3 = new_ids
    doc.Delete(id_mid_to_end)

    doc.GetElement(id_d1).Location.Curve = DB.Line.CreateBound(plan["pA"], plan["pB"])
    doc.GetElement(id_d2).Location.Curve = DB.Line.CreateBound(plan["pB"], plan["pC"])
    doc.GetElement(id_d3).Location.Curve = DB.Line.CreateBound(plan["pC"], plan["pD"])

    # Thiếu bất kỳ elbow nào là hỏng kết nối => ném lỗi để hoàn tác riêng chỗ này
    elbow_failures = []
    for label, id_a, id_b, pt in (("tại A", id_start, id_d1, plan["pA"]), ("tại B", id_d1, id_d2, plan["pB"]),
                                  ("tại C", id_d2, id_d3, plan["pC"]), ("tại D", id_d3, id_end, plan["pD"])):
        reason = create_elbow_at_pt(doc, id_a, id_b, pt)
        if reason:
            elbow_failures.append("{}: {}".format(label, reason))
    if elbow_failures:
        raise RuntimeError("không tạo được elbow ({})".format("; ".join(elbow_failures)))


def polyline_points(info, done_plans):
    """Đường tâm ống sau khi bẻ: start -> (pA pB pC pD)... -> end."""
    pts = [info.start]
    for plan in sorted(done_plans, key=lambda p: p["tA"]):
        pts += [plan["pA"], plan["pB"], plan["pC"], plan["pD"]]
    pts.append(info.end)
    return pts


def min_polyline_distance(pts_a, pts_b):
    best = float("inf")
    for i in range(len(pts_a) - 1):
        for j in range(len(pts_b) - 1):
            best = min(best, segments_min_distance(pts_a[i], pts_a[i + 1], pts_b[j], pts_b[j + 1]))
    return best


# ==============================
# QUY TRÌNH CHẠY CHÍNH (MAIN)
# ==============================

try:
    # 1. Yêu cầu người dùng chọn các đối tượng trên màn hình (chọn xong bấm Finish)
    duct_refs = uidoc.Selection.PickObjects(
        UI.Selection.ObjectType.Element,
        CustomISelectionFilter("MEPCurve"),
        "BƯỚC 1: Chọn các ỐNG (Duct/Pipe) bị vướng, rồi bấm Finish"
    )
    obs_refs = uidoc.Selection.PickObjects(
        UI.Selection.ObjectType.Element,
        CustomISelectionFilter(),
        "BƯỚC 2: Chọn các CHƯỚNG NGẠI VẬT (Dầm / Ống / Cột) để né, rồi bấm Finish"
    )
except OperationCanceledException:
    # Người dùng bấm ESC hủy lệnh (các lỗi khác phải nổi lên để còn biết mà sửa)
    script.exit()

main_elems = [doc.GetElement(r) for r in duct_refs]
obstacles = [doc.GetElement(r) for r in obs_refs]
if not main_elems or not obstacles:
    forms.alert("Cần chọn ít nhất một ống và một chướng ngại vật.", exitscript=True)

# Chỉ hỏi hướng né (Up/Down) vì đôi khi lên trần thì đụng sàn, xuống dưới thì đụng trần giả
direction_opt = forms.SelectFromList.show(["Đi lên trên (Up)", "Đi xuống dưới (Down)"], title="Chọn hướng né va chạm", button_name="Tiếp tục")
if not direction_opt: script.exit()
going_up = (direction_opt == "Đi lên trên (Up)")

# Góc bẻ: mặc định 45°; cho chọn 15/30/60°. DW-01.04: Z ống gió loại 1 <= 15°, loại 2 <= 60°; HD 6.1.3 "nên <= 15°".
# Góc nhỏ cần nhiều chỗ hơn dọc ống (nếu không đủ chỗ tool sẽ báo và không sửa model ở chỗ đó).
angle_opt = forms.SelectFromList.show([label for label, _ in ANGLE_CHOICES], title="Chọn góc bẻ", button_name="Tiếp tục")
if not angle_opt: script.exit()
angle_deg = dict(ANGLE_CHOICES)[angle_opt]
rad_angle = math.radians(angle_deg)

# Hộp bao của từng vật cản
obstacle_boxes = []   # (id, (min, max))
messages = []         # lý do từ chối / bỏ qua (mỗi mục một ý)
multi_duct = len(main_elems) > 1
for ob in obstacles:
    bb = ob.get_BoundingBox(None)
    if not bb:
        messages.append("Không lấy được BoundingBox của chướng ngại vật {}.".format(ob.Id))
        continue
    obstacle_boxes.append((ob.Id, (bb.Min, bb.Max)))


def tag(elem, text):
    return "Ống {}: {}".format(elem.Id, text) if multi_duct else text


# 2. Đọc từng ống, xếp các vật cản nằm trên đường đi vào nhóm
infos_all = []   # mọi ống đọc được (kể cả ống không có chỗ nào để né), dùng kiểm tra va chạm giữa các ống
jobs = []        # (info, groups)
on_path_obstacles = set()
for elem in main_elems:
    info, reason = read_duct(elem)
    if info is None:
        messages.append(tag(elem, reason))
        continue
    infos_all.append(info)
    hit_boxes = []
    for ident, box in obstacle_boxes:
        if ident == elem.Id:
            continue
        if segment_hits_box(info.start, info.end, box[0], box[1], info.reach):
            hit_boxes.append((ident, box))
            on_path_obstacles.add(ident)
    if not hit_boxes:
        continue
    groups, skipped = plan_groups(info, hit_boxes, going_up, rad_angle)
    for reason in skipped:
        messages.append(tag(elem, reason))
    if groups:
        jobs.append((info, groups))

# Vật cản không nằm trên đường đi của bất kỳ ống nào
for ident, _ in obstacle_boxes:
    if ident not in on_path_obstacles and infos_all:
        messages.append("Chướng ngại vật {} không nằm trên đường đi của ống đã chọn (cách đường tâm ống hơn {:.0f} mm), nên không có gì để né. Hãy kiểm tra lại đối tượng đã click.".format(
            ident, ft_to_mm(infos_all[0].reach)))

# 3. Thực thi. Một Transaction chung; mỗi chỗ né là một SubTransaction: lỗi thì hoàn tác riêng chỗ đó.
# Xử lý từ CUỐI ống về ĐẦU: đoạn đầu luôn giữ ElementId gốc nên các chỗ né phía trước vẫn nằm trên chính phần tử này.
done_count = 0
done_plans = {}   # id ống -> danh sách plan đã làm xong
tx = DB.Transaction(doc, "Né Va Chạm (Clash Avoidance)")
tx.Start()
try:
    for info, groups in jobs:
        for group in sorted(groups, key=lambda g: g["plan"]["tA"], reverse=True):
            plan = group["plan"]
            reason = bounds_reason(info, plan)
            if reason is None:
                sub = DB.SubTransaction(doc)
                sub.Start()
                try:
                    execute_bump(info.elem, plan)
                    sub.Commit()
                    done_count += 1
                    done_plans.setdefault(info.elem.Id, []).append(plan)
                    continue
                except Exception as e:
                    sub.RollBack()
                    reason = "Không thể bẻ ống né vật cản. Lý do: {} (đã hoàn tác riêng chỗ này, model giữ nguyên).".format(e)
            messages.append(tag(info.elem, reason))
    tx.Commit()
except Exception as e:
    tx.RollBack()
    forms.alert("Không thể bẻ ống né vật cản. Lý do: {}\n\nMọi thay đổi đã được hoàn tác, model giữ nguyên.".format(e),
                title="Clash Avoidance", exitscript=True)

if done_count == 0:
    forms.alert("\n\n".join(messages) if messages else "Không có gì để né.", title="Clash Avoidance", exitscript=True)

# 4. Cảnh báo va chạm GIỮA các ống đã chọn sau khi bẻ (chỉ cảnh báo cặp ống trước đó chưa chạm nhau)
warnings = []
for a in range(len(infos_all)):
    for b in range(a + 1, len(infos_all)):
        ia, ib = infos_all[a], infos_all[b]
        need = ia.radius + ib.radius
        before = min_polyline_distance([ia.start, ia.end], [ib.start, ib.end])
        after = min_polyline_distance(polyline_points(ia, done_plans.get(ia.elem.Id, [])),
                                      polyline_points(ib, done_plans.get(ib.elem.Id, [])))
        if before >= need and after < need:
            warnings.append("Ống {} và ống {} có thể va chạm nhau sau khi bẻ (khoảng cách giữa hai đường tâm {:.0f} mm < {:.0f} mm). Hãy kiểm tra hoặc bẻ đồng bộ.".format(
                ia.elem.Id, ib.elem.Id, ft_to_mm(after), ft_to_mm(need)))

report = "Đã bẻ ống lượn qua chướng ngại vật thành công! ({} chỗ né trên {} ống)".format(done_count, len(done_plans))
merged = sum(1 for _, groups in jobs for g in groups if len(g["ids"]) > 1)
if merged:
    report += "\n- {} chỗ né gộp từ nhiều vật cản đứng gần nhau (nếu né riêng thì khoảng ống thẳng giữa hai chỗ né < {} mm).".format(merged, MIN_STRAIGHT_BETWEEN_MM)
if messages:
    report += "\n\nKhông làm được / bỏ qua:\n" + "\n".join("  • " + m.split("\n")[0] for m in messages[:10])
    if len(messages) > 10:
        report += "\n  ... và {} mục khác".format(len(messages) - 10)
if warnings:
    report += "\n\nCẢNH BÁO:\n" + "\n".join("  • " + w for w in warnings)
forms.alert(report, title="Clash Avoidance")
