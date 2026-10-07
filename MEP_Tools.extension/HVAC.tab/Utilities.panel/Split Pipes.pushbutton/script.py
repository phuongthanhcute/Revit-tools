# -*- coding: utf-8 -*-
__title__ = "Split\nDucts/Pipes"
__doc__ = """Chia đường ống dài thành các đoạn tiêu chuẩn.
Hỗ trợ:
- Ống gió (Duct): Mặc định 1120mm
- Ống nước/thép (Pipe): Mặc định 6000mm

Cách dùng:
1. Chọn các đường ống cần chia.
2. Chạy tool và nhập chiều dài cắt (chỉ hỏi loại ống có trong vùng chọn).
3. Tool sẽ tự động cắt và chèn măng xông (Union).
Ống bị Pin sẽ được bỏ qua."""

from pyrevit import revit, DB, forms
import math
from mep_common import mm_to_ft, get_connector_closest_to, ask_positive_number, is_pinned

doc = revit.doc

# ==============================
# THAM SỐ CẤU HÌNH
# ==============================
LENGTH_TOLERANCE = 1.01   # [FIX_CỨNG]: ống dài <= 1.01 x chiều dài chuẩn thì không cắt (tránh cắt ống gần bằng chuẩn)
MIN_TAIL_FT = 0.1         # [FIX_CỨNG]: 0.1 feet (~30mm) khoảng cách tối thiểu từ nhát cắt đến mép cuối ống


def split_mep_curve(element, split_length_ft):
    """
    Cắt 1 đường ống thành các đoạn dài split_length_ft (đoạn dư nằm ở cuối ống).
    Trả về (số nhát cắt, số Union chèn được, số Union thất bại).
    """
    loc_curve = element.Location
    if not isinstance(loc_curve, DB.LocationCurve):
        return 0, 0, 0

    curve = loc_curve.Curve
    length_ft = curve.Length

    if length_ft <= split_length_ft * LENGTH_TOLERANCE:
        return 0, 0, 0

    num_cuts = int(math.floor(length_ft / split_length_ft))

    start_pt = curve.GetEndPoint(0)
    end_pt = curve.GetEndPoint(1)
    direction = (end_pt - start_pt).Normalize()

    cut_points = []
    for i in range(1, num_cuts + 1):
        cut_pt = start_pt + direction * (i * split_length_ft)
        if cut_pt.DistanceTo(end_pt) > MIN_TAIL_FT:
            cut_points.append(cut_pt)

    # MẸO REVIT API: cắt từ XA về GẦN (End -> Start). BreakCurve giữ ElementId gốc cho đoạn (Start -> điểm cắt)
    # và tạo ElementId mới cho đoạn (điểm cắt -> End), nên `element` luôn là đoạn đầu chứa các điểm cắt còn lại.
    cut_points.reverse()

    cuts_made = unions_made = unions_failed = 0

    for pt in cut_points:
        try:
            new_id = None
            if isinstance(element, DB.Plumbing.Pipe):
                new_id = DB.Plumbing.PlumbingUtils.BreakCurve(doc, element.Id, pt)
            elif isinstance(element, DB.Mechanical.Duct):
                new_id = DB.Mechanical.MechanicalUtils.BreakCurve(doc, element.Id, pt)

            if new_id:
                cuts_made += 1
                new_elem = doc.GetElement(new_id)
                conn1 = get_connector_closest_to(element, pt)
                conn2 = get_connector_closest_to(new_elem, pt)

                if conn1 and conn2 and not conn1.IsConnected and not conn2.IsConnected:
                    try:
                        doc.Create.NewUnionFitting(conn1, conn2)
                        unions_made += 1
                    except Exception as e:
                        unions_failed += 1
                        print("Cảnh báo: Không thể tạo Union Fitting tại tọa độ {}. Lỗi: {}".format(pt, e))
                else:
                    # connector đã nối sẵn (Revit tự nối) hoặc không tìm thấy: không cần / không thể chèn Union
                    unions_failed += 1
        except Exception as e:
            print("Lỗi khi cắt ống: {}".format(e))

    return cuts_made, unions_made, unions_failed


# ==============================
# QUY TRÌNH CHẠY CHÍNH (MAIN)
# ==============================

selection = revit.get_selection()
ducts, pipes = [], []
for elem in selection.elements:
    if isinstance(elem, DB.Mechanical.Duct):
        ducts.append(elem)
    elif isinstance(elem, DB.Plumbing.Pipe):
        pipes.append(elem)

if not ducts and not pipes:
    forms.alert("Vui lòng chọn ít nhất một Ống Gió (Duct) hoặc Ống Nước (Pipe) trên bản vẽ trước khi chạy.", exitscript=True)

# Chỉ hỏi chiều dài cho loại ống thực sự có trong vùng chọn
duct_len_ft = pipe_len_ft = None
if ducts:
    duct_len_ft = mm_to_ft(ask_positive_number("1120", "Nhập chiều dài tiêu chuẩn cắt ỐNG GIÓ (mm):", "Chia Ống Gió"))
if pipes:
    pipe_len_ft = mm_to_ft(ask_positive_number("6000", "Nhập chiều dài tiêu chuẩn cắt ỐNG NƯỚC (mm):", "Chia Ống Nước"))

total_cuts = total_unions = total_union_failed = skipped_pinned = 0

with revit.Transaction("Chia Ống Tiêu Chuẩn (Split MEP Curves)"):
    for elem, length_ft in [(e, duct_len_ft) for e in ducts] + [(e, pipe_len_ft) for e in pipes]:
        if is_pinned(elem):
            skipped_pinned += 1
            continue
        cuts, unions, failed = split_mep_curve(elem, length_ft)
        total_cuts += cuts
        total_unions += unions
        total_union_failed += failed

# Báo cáo kết quả (số liệu thật, không gộp "cắt" với "chèn Union")
report = "Thao tác hoàn tất!\n\n"
report += "- Số nhát cắt: {}\n".format(total_cuts)
report += "- Số Union chèn thành công: {}\n".format(total_unions)
if total_union_failed:
    report += "- Số vị trí KHÔNG chèn được Union: {} (xem cửa sổ Output)\n".format(total_union_failed)
if skipped_pinned:
    report += "- Ống bị Pin nên bỏ qua: {}\n".format(skipped_pinned)
forms.alert(report, title="Kết Quả")
