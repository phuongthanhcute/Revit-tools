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
  - **Nhịp giá đỡ, chọn riêng cho từng nhóm ống** (ống gió; mỗi Pipe Type một nhóm): "Tuỳ biến" (nhập một nhịp chung, mặc định 2000 mm, phải > 0; ống gió nhập > 2500 mm thì hỏi xác nhận) hoặc bảng theo HD: ống gió cứng 2500; PPR (D20~32=1000, D40~63=1500, D75~110=2000, D125~160=2500); UPVC thoát nước (D21~42=1000, D48~60=1500, D75~140=2000, D160~200=2500); UPVC nước ngưng (D21~42=1000, D48~60=1500); chữa cháy (≤DN50=4000, >DN50=6000); gas đồng 1500. Bảng tra theo đường kính ngoài, riêng chữa cháy theo DN; không đọc được đường kính thì lấy nhịp nhỏ nhất.
  - Khoảng cách giá đỡ tới phụ kiện / tay nhánh (tê, cổ trích): mặc định ống gió 200 mm (hỏi xác nhận nếu < 200, DW-02.02), ống nước 100 mm.
  - Khoảng cách tới thiết bị / miệng gió: mặc định 300 mm (**tự chọn, chuẩn không nêu số**; HD 6.1.3.15 chỉ cấm đặt giá trùng cửa gió).
  - Ty treo kết thúc tại: đỉnh ống (mặc định) / tâm ống / đáy ống (thanh đỡ dưới đáy, DW-02.03).

## 3. Quy tắc rải (đã được kiểm chứng bằng test ngẫu nhiên)
Mỗi đoạn ống dài `L` đặt `k = max(1, ceil(L / spacing))` giá, giá thứ `i` nằm tại `(i + 0.5) · L / k`.
- Khoảng cách giữa hai giá trong cùng đoạn là `L / k ≤ spacing`.
- Khoảng cách giữa hai giá ở hai đoạn liền kề là `L₁/(2k₁) + L₂/(2k₂) ≤ spacing` (**chưa tính chiều dài phụ kiện nằm giữa hai đoạn**, xem mục 7).
- Ống ngắn hơn `spacing` vẫn có đúng 1 giá ở chính giữa; không bao giờ có hai giá sát nhau.

## 4. Luồng thuật toán
1. Lọc ống được chọn; bỏ qua ống đứng.
2. Đọc kích thước ống bằng `BuiltInParameter` (không phụ thuộc ngôn ngữ Revit; có fallback theo tên hiển thị) và bề dày cách nhiệt.
3. Với mỗi vị trí chia:
   - **Né phụ kiện:** nếu vị trí nằm trong vùng clearance của Fitting (**ống gió ±200 mm**, ống nước ±100 mm, theo DW-02.02 và HD mục 6.1.3 / 4.1.3) thì thử dịch ±150, ±300... mm, **nhưng mỗi giá không dịch quá NỬA phần nhịp còn dư** (`(spacing − L/k) / 2`; hai giá kề nhau có thể dịch ngược chiều nên tổng nhịp vẫn ≤ `spacing`) để nhịp không vượt `spacing`, và luôn nằm trong đoạn ống. Không còn chỗ dịch thì giữ vị trí gốc và báo "còn sát phụ kiện".
   - **Bỏ qua nếu đã có** giá đỡ cùng loại trong bán kính 100 mm (chạy lại tool không nhân đôi giá).
4. Đặt giá (`NewFamilyInstance`), xoay vuông góc ống, gán bề rộng.
5. **Bắn tia** theo trục Z tìm Sàn/Dầm gần nhất. Chiều dài ty = khoảng cách − (nửa **chiều cao** ống + cách nhiệt). Bề rộng giá = bề rộng ống + 2 × bề dày cách nhiệt (ty nằm ngoài lớp bảo ôn, DW-02.03). Chỉ ghi vào đúng tham số người dùng chỉ định.
5b. **Giá cuối tuyến ống gió:** nếu một đầu ống gió là đầu **tự do** (connector chưa nối) và giá gần nhất cách đầu đó > 300 mm thì bổ sung 1 giá cách đầu ống 250 mm (DW-02.02: ≤ 300 mm). Đầu nối thiết bị không xét.
5c. **Các trường hợp biên đã xử lý:** chiều dài ty ≤ 0 (sàn/dầm sát hoặc thấp hơn điểm kết thúc ty) thì không ghi vào family và báo riêng; nhịp tuỳ biến < 200 mm thì hỏi xác nhận (thường nhập nhầm đơn vị); đầu ống có ống khác trùng đầu mút (Union lỗi khi Split) không bị coi là "đầu tự do"; phần tử không phải ống cứng (ống mềm, phụ kiện) được đếm và báo là bị bỏ qua.
6. Báo cáo: số giá đã đặt, số ty đã tính, số giá **chưa có ty** (không thấy sàn/dầm, hoặc không ghi được tham số), số giá bỏ qua vì đã tồn tại, ống đứng bỏ qua, giá còn sát phụ kiện.

## 5. Các Class/Method Revit API chính
- `ReferenceIntersector` / `FindReferenceTarget`: bắn tia.
- `FilteredElementCollector(doc)` + `BoundingBoxIntersectsFilter` (quick filter): quét phụ kiện và giá đã có quanh một điểm. Quét cả model, không giới hạn theo view.

## 6. Giới hạn đã biết (chưa xử lý, cần kiểm chứng trên Revit thật)
- **Model liên kết (Link):** Raytrace chưa bật tìm trong Revit Link; sàn/dầm nằm trong file Link sẽ không được thấy. Chỉ lọc Floors và Structural Framing.
- **Section Box / Visibility:** kết quả Raytrace phụ thuộc phạm vi hiển thị của 3D View.
- **Nhịp qua phụ kiện (mục 3):** hai giá ở hai đoạn kề nhau có thể cách nhau `spacing` + chiều dài phụ kiện.
- Ống dốc nhẹ: giá chỉ xoay quanh trục Z, độ dốc không ảnh hưởng hướng giá.
