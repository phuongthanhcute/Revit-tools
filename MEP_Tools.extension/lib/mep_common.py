# -*- coding: utf-8 -*-
"""Hàm dùng chung cho các tool của HVAC.tab.

pyRevit tự thêm thư mục lib/ của extension vào sys.path, nên các script chỉ cần:
    from mep_common import mm_to_ft, ...
Các hàm import `pyrevit` bên trong thân hàm (không import ở đầu file) để file này không giữ tham chiếu
tới một phiên bản DB cũ khi chạy test ngoài Revit.
"""
import math


def mm_to_ft(mm):
    """mm -> feet (đơn vị nội bộ của Revit)."""
    return mm / 304.8


def ft_to_mm(ft):
    return ft * 304.8


def id_value(element_id):
    """ElementId -> int. Revit mới dùng .Value, Revit cũ dùng .IntegerValue (bị gỡ ở bản mới)."""
    if hasattr(element_id, "Value"):
        return int(element_id.Value)
    return int(element_id.IntegerValue)


def is_pinned(element):
    """Phần tử bị Pin thì không được sửa/cắt."""
    return bool(getattr(element, "Pinned", False))


# ---------------------------------------------------------------- tham số (không phụ thuộc ngôn ngữ Revit)
def read_length_param(element, builtin_names=(), display_names=()):
    """Đọc 1 tham số kiểu chiều dài (feet).

    Thử BuiltInParameter trước (không phụ thuộc ngôn ngữ giao diện Revit), sau đó mới thử tên hiển thị.
    builtin_names là TÊN (chuỗi) của BuiltInParameter, để bản Revit không có tham số đó không gây lỗi.
    Trả về None nếu không tìm thấy giá trị.
    """
    from pyrevit import DB
    for name in builtin_names:
        bip = getattr(DB.BuiltInParameter, name, None)
        if bip is None:
            continue
        param = element.get_Parameter(bip)
        if param is not None and getattr(param, "HasValue", True):
            return param.AsDouble()
    for name in display_names:
        param = element.LookupParameter(name)
        if param is not None and getattr(param, "HasValue", True):
            return param.AsDouble()
    return None


def get_section_size(element):
    """(rộng, cao) của tiết diện NGOÀI của ống gió / ống nước, tính bằng feet. Chưa cộng cách nhiệt.

    Ống gió chữ nhật: (Width, Height). Ống tròn: (đường kính, đường kính). Không đọc được: (None, None).
    """
    width = read_length_param(element, ("RBS_CURVE_WIDTH_PARAM",), ("Width",))
    height = read_length_param(element, ("RBS_CURVE_HEIGHT_PARAM",), ("Height",))
    if width and height:
        return width, height
    diameter = read_length_param(
        element,
        ("RBS_PIPE_OUTER_DIAMETER", "RBS_CURVE_DIAMETER_PARAM"),
        ("Outside Diameter", "Diameter"))
    if diameter:
        return diameter, diameter
    return None, None


def get_insulation_thickness(element):
    """Bề dày cách nhiệt (feet) của ống; 0 nếu không có / không đọc được."""
    value = read_length_param(element, ("RBS_REFERENCE_INSULATION_THICKNESS",), ())
    return value or 0.0


def get_nominal_diameter(element):
    """Đường kính danh nghĩa (feet) của ống nước; None nếu không đọc được."""
    return read_length_param(element, ("RBS_PIPE_DIAMETER_PARAM",), ("Nominal Diameter", "Diameter"))


def is_end_free(element, pt):
    """Đầu ống gần pt nhất có chưa nối với gì không (đầu/cuối tuyến thật sự). Không đọc được connector -> False."""
    try:
        best, best_d = None, float("inf")
        for conn in element.ConnectorManager.Connectors:
            d = conn.Origin.DistanceTo(pt)
            if d < best_d:
                best, best_d = conn, d
        return best is not None and not best.IsConnected
    except Exception:
        return False


# ---------------------------------------------------------------- nhịp giá đỡ theo tiêu chuẩn (HD triển khai bản vẽ SHOP)
# Mỗi bảng: (nhãn, [(đường kính tối đa mm hoặc None, nhịp mm), ...], cơ sở đường kính "od" (ngoài) | "dn" (danh nghĩa)).
# Chỉ là nhịp MẶC ĐỊNH khi thiết kế không nêu rõ; người dùng luôn có lựa chọn "Tuỳ biến".
SPAN_PRESETS = [
    ("Ống gió cứng (<= 2500, DW-02.02)", [(None, 2500)], "od"),
    ("PPR cấp nước (HD 4.1.3): D20~32=1000, D40~63=1500, D75~110=2000, D125~160=2500",
     [(32, 1000), (63, 1500), (110, 2000), (160, 2500)], "od"),
    ("UPVC thoát nước (HD 4.2.3): D21~42=1000, D48~60=1500, D75~140=2000, D160~200=2500",
     [(42, 1000), (60, 1500), (140, 2000), (200, 2500)], "od"),
    ("UPVC nước ngưng (HD 6.3.3): D21~42=1000, D48~60=1500",
     [(42, 1000), (60, 1500)], "od"),
    ("Chữa cháy (HD 5.1.3): <=DN50=4000, >DN50=6000", [(50, 4000), (None, 6000)], "dn"),
    ("Ống gas đồng (HD 6.2.3): 1500", [(None, 1500)], "od"),
]


def span_from_rows(rows, diameter_mm):
    """Nhịp (mm) theo bảng. Không biết đường kính -> lấy nhịp nhỏ nhất (an toàn). Lớn hơn bảng -> lấy dòng cuối."""
    if diameter_mm is None:
        return min(span for _, span in rows)
    for max_d, span in rows:
        if max_d is None or diameter_mm <= max_d + 0.5:
            return span
    return rows[-1][1]


# ---------------------------------------------------------------- nhập liệu
def ask_positive_number(default, prompt, title):
    """Hỏi 1 số > 0. Hủy / nhập chữ / nhập 0 hoặc số âm đều thoát tool kèm thông báo (không crash)."""
    from pyrevit import forms, script
    text = forms.ask_for_string(default=default, prompt=prompt, title=title)
    if not text:
        script.exit()
    try:
        value = float(text.replace(",", "."))
    except ValueError:
        forms.alert("'{}' không phải là số hợp lệ.".format(text), exitscript=True)
    if not (value > 0) or math.isinf(value):
        forms.alert("Giá trị phải là số lớn hơn 0 (bạn nhập: {}).".format(text), exitscript=True)
    return value


def confirm_under_limit(value, limit, what, standard):
    """Như confirm_over_limit nhưng cho giá trị nhỏ hơn mức tối thiểu của tiêu chuẩn."""
    if value >= limit:
        return True
    from pyrevit import forms, script
    ok = forms.alert(
        "{} = {:.0f} mm nhỏ hơn mức tối thiểu của tiêu chuẩn ({:.0f} mm, {}).\n\nVẫn tiếp tục với giá trị đã nhập?".format(
            what, value, limit, standard),
        title="Dưới tiêu chuẩn", yes=True, no=True)
    if not ok:
        script.exit()
    return True


def confirm_over_limit(value, limit, what, standard):
    """Giá trị người dùng nhập vượt giới hạn của tiêu chuẩn thì hỏi xác nhận (vẫn cho phép nếu người dùng đồng ý).

    Chỉ cảnh báo, không tự sửa giá trị: người dùng/dự án có thể có yêu cầu riêng trong thiết kế.
    Trả về True nếu không vượt giới hạn hoặc người dùng chọn tiếp tục; ngược lại thoát tool.
    """
    if value <= limit:
        return True
    from pyrevit import forms, script
    ok = forms.alert(
        "{} = {:.0f} mm vượt giới hạn tiêu chuẩn ({:.0f} mm, {}).\n\nVẫn tiếp tục với giá trị đã nhập?".format(
            what, value, limit, standard),
        title="Vượt tiêu chuẩn", yes=True, no=True)
    if not ok:
        script.exit()
    return True


# ---------------------------------------------------------------- connector / hình học
def get_connector_closest_to(element, pt):
    """Connector của MEPCurve gần điểm pt nhất (dùng tìm 2 đầu vừa bị cắt)."""
    from pyrevit import DB
    if not isinstance(element, DB.MEPCurve):
        return None
    closest, best = None, float("inf")
    for conn in element.ConnectorManager.Connectors:
        dist = conn.Origin.DistanceTo(pt)
        if dist < best:
            best, closest = dist, conn
    return closest


def _xyz(p):
    return (p.X, p.Y, p.Z)


def segments_min_distance(p0, p1, q0, q1):
    """Khoảng cách ngắn nhất (feet) giữa hai đoạn thẳng p0-p1 và q0-q1 trong không gian 3D (Ericson, Real-Time Collision Detection)."""
    a, b, c, d = _xyz(p0), _xyz(p1), _xyz(q0), _xyz(q1)
    sub = lambda u, v: (u[0] - v[0], u[1] - v[1], u[2] - v[2])
    dot = lambda u, v: u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    d1, d2, r = sub(b, a), sub(d, c), sub(a, c)
    aa, ee, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    eps = 1e-12
    clamp = lambda x: max(0.0, min(1.0, x))
    if aa <= eps and ee <= eps:
        s_ = t_ = 0.0
    elif aa <= eps:
        s_, t_ = 0.0, clamp(f / ee)
    else:
        cc = dot(d1, r)
        if ee <= eps:
            t_, s_ = 0.0, clamp(-cc / aa)
        else:
            bb = dot(d1, d2)
            denom = aa * ee - bb * bb
            s_ = clamp((bb * f - cc * ee) / denom) if denom > eps else 0.0
            t_ = (bb * s_ + f) / ee
            if t_ < 0.0:
                t_, s_ = 0.0, clamp(-cc / aa)
            elif t_ > 1.0:
                t_, s_ = 1.0, clamp((bb - cc) / aa)
    c1 = (a[0] + d1[0] * s_, a[1] + d1[1] * s_, a[2] + d1[2] * s_)
    c2 = (c[0] + d2[0] * t_, c[1] + d2[1] * t_, c[2] + d2[2] * t_)
    diff = sub(c1, c2)
    return math.sqrt(dot(diff, diff))


def segment_hits_box(p0, p1, box_min, box_max, expand=0.0):
    """Đoạn thẳng p0-p1 có cắt hộp AABB [box_min, box_max] (nới ra mỗi phía `expand`) hay không.

    Dùng phương pháp "slab": cắt tham số t của đoạn thẳng với từng cặp mặt phẳng song song trục.
    """
    t_lo, t_hi = 0.0, 1.0
    for a0, a1, lo, hi in ((p0.X, p1.X, box_min.X, box_max.X),
                           (p0.Y, p1.Y, box_min.Y, box_max.Y),
                           (p0.Z, p1.Z, box_min.Z, box_max.Z)):
        lo -= expand
        hi += expand
        d = a1 - a0
        if abs(d) < 1e-12:
            if a0 < lo or a0 > hi:
                return False
            continue
        t1, t2 = (lo - a0) / d, (hi - a0) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_lo, t_hi = max(t_lo, t1), min(t_hi, t2)
        if t_lo > t_hi:
            return False
    return True
