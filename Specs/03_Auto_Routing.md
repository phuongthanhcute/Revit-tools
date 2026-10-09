# Specification: Auto-Routing (Đấu nối tự động v2.0)

## 1. Thông tin chung
- **Độ khó:** Khó (3/4) - Cần tìm kiếm hình học không gian và khởi tạo kết nối MEP System.
- **Mục tiêu:** Vẽ ống mềm (Flex Duct) từ ống gió cứng vào các miệng gió (Air Terminal), mỗi miệng gió xử lý độc lập và hoàn tác sạch khi lỗi.

## 2. Đầu vào (Inputs)
- Danh sách miệng gió / hộp gió được chọn: **bất kỳ family nào có connector gió còn trống** (ống mềm nối vào connector Duct Diameter có sẵn trên family).
- Loại Flex Duct (chỉ hỏi khi dự án có nhiều hơn một loại).
- Có bảo ôn hay không (mặc định: không). Nếu có: chọn loại bảo ôn (nếu có nhiều loại) và nhập bề dày (mặc định 25 mm).
- Chiều dài tối đa của ống mềm (mm, phải > 0; mặc định 2000). Nhập > 2000 mm sẽ hỏi xác nhận (DW-01.01 chú thích 3 và HD mục 6.1.3: ống gió mềm ≤ 2 m); người dùng vẫn được phép tiếp tục.

## 3. Đầu ra (Outputs)
- Flex Duct nối connector gió của miệng gió với cổ trích (Takeoff) trên ống cứng.
- Báo cáo: số thành công, số thất bại **kèm lý do từng miệng gió**, và cảnh báo nếu phải dùng System Type mặc định.

## 4. Luồng thuật toán
1. Lấy từ selection các family có connector gió còn trống (không còn lọc theo Category).
2. Lấy connector **gió (Domain HVAC)** đầu tiên còn trống (bỏ qua connector điện).
3. Tìm ống cứng ứng viên: `FilteredElementCollector` + `BoundingBoxIntersectsFilter` quanh miệng gió, bán kính `max_length / 1.2`, **quét toàn model** (không giới hạn theo view).
   Đây là quick filter của Revit, giúp không phải xét mọi ống trong dự án; **không phải O(1)**.
4. **Điểm tap:** hình chiếu của connector lên đường tâm ống, rồi kéo vào trong để luôn cách mỗi đầu ống **≥ 200 mm** (ống ngắn hơn 400 mm bị loại). Đầu ống nối với **cút** thì cố gắng cách cút **≥ 8W** (ống chữ nhật) / **≥ 6D** (ống tròn). Không đủ chỗ thì **vẫn đặt** nhưng báo cảnh báo (quyết định của kỹ sư). Chọn ống có điểm tap gần nhất.
5. **Giới hạn chiều dài:** khoảng cách thẳng × **1.2** (ống mềm phải uốn cong) phải ≤ chiều dài tối đa.
6. Mỗi miệng gió trong một `SubTransaction`: `FlexDuct.Create` → đặt đường kính theo connector tròn → (tuỳ chọn) `DuctInsulation.Create` → nối đầu vào miệng gió → `NewTakeoffFitting` vào ống cứng. Lỗi bất kỳ bước nào thì `RollBack` miệng gió đó (không để lại ống mềm dở dang) và ghi lý do.

4b. **Các trường hợp biên đã xử lý:** hai cổ trích trên cùng một ống (kể cả vừa tạo trong lần chạy này) phải cách nhau (mép - mép) ≥ 100 mm, điểm tap được dịch tới chỗ trống gần nhất, hết chỗ thì miệng gió đó bị từ chối kèm lý do; bỏ qua ống chính khác loại hệ thống với connector miệng gió (cấp/hồi/thải; không biết một trong hai thì coi là khớp), ống chính nhỏ hơn đường kính cổ trích, và ống chính bị Pin. Lý do loại ống được ghi vào báo cáo.

## 5. Các Class/Method Revit API chính
- `BoundingBoxIntersectsFilter`, `Curve.Project(XYZ)`, `FlexDuct.Create`, `doc.Create.NewTakeoffFitting`, `SubTransaction`, `Connector.Domain`.

## 6. Giới hạn đã biết (chưa xử lý, cần kiểm chứng trên Revit thật)
- **Kích thước ống mềm** lấy theo connector **tròn**; connector chữ nhật hoặc tham số chỉ-đọc thì dùng kích thước mặc định của loại ống và tool báo trong kết quả.
- **Khoảng cách T/cổ trích** chỉ xét với cút ở đầu ống chính; chưa xét 6D giữa các T (ống tròn) hoặc 0.5D giữa các T thu.
- **Hướng đi ra của ống mềm** chưa theo hướng connector miệng gió: ống mềm là đoạn thẳng từ điểm tap tới miệng gió, nên miệng gió lệch ngang nhiều thì ống mềm đi chéo.
- **System Type:** nếu ống chính chưa thuộc hệ thống nào, tool dùng System Type mặc định của dự án (có thể sai hệ thống, tool có cảnh báo).
- **Chọn ống:** theo khoảng cách tâm ống gần nhất; chưa xét kích thước hay hệ thống của ống.
- Điểm tap chưa kiểm tra va chạm với phụ kiện/ống khác.
