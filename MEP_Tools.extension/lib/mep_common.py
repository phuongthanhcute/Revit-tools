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
