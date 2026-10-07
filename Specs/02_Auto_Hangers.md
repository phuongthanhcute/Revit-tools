# Specification: Tạo giá đỡ tự động & Thông minh (Auto Hangers/Supports v3.0)

## 1. Thông tin chung
- **Độ khó:** Khó (3/4) - Yêu cầu tính toán Vector, bắn tia (Raytrace) trong 3D và xử lý va chạm cơ bản.
- **Mục tiêu:** Rải giá đỡ dọc ống gió / ống nước với nhịp không vượt quá khoảng cách người dùng nhập, tự gán chiều dài ty treo tới sàn/dầm phía trên, và báo cáo rõ phần nào chưa làm được.

## 2. Đầu vào (Inputs)
- Các đường ống (Duct/Pipe) được chọn. Ống đứng (dốc > 60°) bị bỏ qua và được báo cáo.
- **Bắt buộc mở 3D View** (Raytrace cần 3D View).
- Cửa sổ UI:
  - Family giá đỡ (chọn trong danh sách đang load).
  - Tên tham số (instance) điều khiển "Chiều dài ty treo" (mặc định `Rod Length`).
  - Khoảng cách rải tối đa (mặc định 2000 mm; phải là số > 0).

## 3. Quy tắc rải (đã được kiểm chứng bằng test ngẫu nhiên)
Mỗi đoạn ống dài `L` đặt `k = max(1, ceil(L / spacing))` giá, giá thứ `i` nằm tại `(i + 0.5) · L / k`.
- Khoảng cách giữa hai giá trong cùng đoạn là `L / k ≤ spacing`.
- Khoảng cách giữa hai giá ở hai đoạn liền kề là `L₁/(2k₁) + L₂/(2k₂) ≤ spacing` (**chưa tính chiều dài phụ kiện nằm giữa hai đoạn**, xem mục 7).
- Ống ngắn hơn `spacing` vẫn có đúng 1 giá ở chính giữa; không bao giờ có hai giá sát nhau.

## 4. Luồng thuật toán
1. Lọc ống được chọn; bỏ qua ống đứng.
2. Đọc kích thước ống bằng `BuiltInParameter` (không phụ thuộc ngôn ngữ Revit; có fallback theo tên hiển thị) và bề dày cách nhiệt.
3. Với mỗi vị trí chia:
   - **Né phụ kiện:** nếu vị trí nằm trong ±150 mm của Fitting thì thử dịch ±150, ±300... mm, **nhưng không dịch quá phần nhịp còn dư** (`spacing − L/k`) để nhịp không vượt `spacing`, và luôn nằm trong đoạn ống. Không còn chỗ dịch thì giữ vị trí gốc và báo "còn sát phụ kiện".
   - **Bỏ qua nếu đã có** giá đỡ cùng loại trong bán kính 100 mm (chạy lại tool không nhân đôi giá).
4. Đặt giá (`NewFamilyInstance`), xoay vuông góc ống, gán bề rộng.
5. **Bắn tia** theo trục Z tìm Sàn/Dầm gần nhất. Chiều dài ty = khoảng cách − (nửa **chiều cao** ống + cách nhiệt). Chỉ ghi vào đúng tham số người dùng chỉ định.
6. Báo cáo: số giá đã đặt, số ty đã tính, số giá **chưa có ty** (không thấy sàn/dầm, hoặc không ghi được tham số), số giá bỏ qua vì đã tồn tại, ống đứng bỏ qua, giá còn sát phụ kiện.

## 5. Các Class/Method Revit API chính
- `ReferenceIntersector` / `FindReferenceTarget`: bắn tia.
- `FilteredElementCollector(doc)` + `BoundingBoxIntersectsFilter` (quick filter): quét phụ kiện và giá đã có quanh một điểm. Quét cả model, không giới hạn theo view.

## 6. Giới hạn đã biết (chưa xử lý, cần kiểm chứng trên Revit thật)
- **Model liên kết (Link):** Raytrace chưa bật tìm trong Revit Link; sàn/dầm nằm trong file Link sẽ không được thấy. Chỉ lọc Floors và Structural Framing.
- **Section Box / Visibility:** kết quả Raytrace phụ thuộc phạm vi hiển thị của 3D View.
- **Nhịp qua phụ kiện (mục 3):** hai giá ở hai đoạn kề nhau có thể cách nhau `spacing` + chiều dài phụ kiện.
- Ống dốc nhẹ: giá chỉ xoay quanh trục Z, độ dốc không ảnh hưởng hướng giá.
