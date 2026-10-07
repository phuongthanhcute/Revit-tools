# Tests

Các test chạy **ngoài Revit**, trên một "Revit giả" (`fakerevit.py`) có nhân hình học tối thiểu: `Line.Project`, `BreakCurve`, `CopyElements`, tạo elbow/union/takeoff, Transaction và SubTransaction có hoàn tác thật.

> ⚠️ Đây là mô hình do người viết dựng theo hiểu biết về Revit API. Test qua nghĩa là **logic của code đúng trong mô hình đó**, không chứng minh hành vi trên Revit thật. Các điểm cần Revit thật được liệt kê trong `checklist.md`.

## Chạy

Chỉ cần Python 3 (thư viện chuẩn). Chạy từ bất kỳ thư mục nào:

```bash
python tests/test_p0.py      # lỗi crash P0 (import thiếu, API không tồn tại, nuốt lỗi)
python tests/test_fixes.py   # Auto Hangers (quy tắc rải) và Clash Avoid (ống dốc, vùng né), có phép thử ngẫu nhiên
python tests/test_batch.py   # toàn bộ các bản sửa còn lại, gồm cả lib/mep_common.py
```

Mỗi file thoát với mã 1 nếu có kiểm tra thất bại.

Lint (tùy chọn): `pip install pyflakes` rồi `python -m pyflakes MEP_Tools.extension`.

## Ghi chú

- Script trong `MEP_Tools.extension` là IronPython/CPython của pyRevit và import `pyrevit`, `Autodesk.*`, `System.*`; test thay các module này bằng stub nên không cần cài pyRevit.
- Phép thử ngẫu nhiên dùng seed cố định nên kết quả lặp lại được.
