# MEP Automation Toolkit for Revit 🚀

Bộ công cụ tự động hóa dành cho Kỹ sư Cơ Điện (MEP) và BIM Coordinator, viết bằng Python chạy trên nền tảng **pyRevit**. Bộ công cụ giúp giảm các thao tác lặp đi lặp lại (chia ống theo chuẩn, rải giá đỡ, đấu nối miệng gió, bẻ lượn ống né dầm) để bạn tập trung vào thiết kế.

> **Trạng thái:** các thuật toán đã được kiểm tra bằng mô hình Revit giả (mô phỏng hình học, test ngẫu nhiên, mutation test). **Chưa được kiểm chứng trên Revit thật.** Hãy thử trên một bản sao của model trước khi dùng cho dự án thật, và xem mục "Giới hạn đã biết".

---

## 🛠 Các tính năng (Scripts)

### 1. Split Ducts / Pipes (Chia Ống Tiêu Chuẩn)
- **Công dụng:** Cắt ống gió / ống nước dài thành các khúc theo chiều dài chuẩn (VD: 1.12m hoặc 6m) và chèn măng xông (Union).
- **Cách làm:** cắt từ đuôi về đầu; đoạn **đầu** giữ ElementId gốc, các đoạn sau nhận ElementId mới.
- **An toàn:** chỉ hỏi chiều dài cho loại ống đang chọn; từ chối giá trị không hợp lệ; bỏ qua ống bị Pin; báo cáo tách **số nhát cắt** và **số Union chèn được**.

### 2. Smart Auto Hangers (Rải Giá Đỡ)
- **Công dụng:** Rải giá đỡ dọc tuyến ống, xoay vuông góc ống, gán bề rộng và chiều dài ty treo tới sàn/dầm phía trên.
- **Quy tắc rải:** mỗi đoạn ống dài `L` đặt `ceil(L / spacing)` giá, đều nhau và căn giữa. Nhịp giữa hai giá không vượt `spacing`, và **ống ngắn hơn `spacing` vẫn có đúng 1 giá** ở giữa.
- **Raytrace:** bắn tia lên trục Z (cần 3D View) tìm Sàn/Dầm, ty = khoảng cách − (nửa **chiều cao** ống + cách nhiệt). Chỉ ghi vào đúng tham số bạn chỉ định.
- **Né phụ kiện:** chỉ dịch giá trong phần nhịp còn dư, không bao giờ làm nhịp vượt `spacing` hay đẩy giá ra ngoài ống.
- **An toàn:** chạy lại không nhân đôi giá; bỏ qua ống đứng; báo cáo rõ giá nào **chưa có ty** và vì sao.

### 3. Auto Routing (Đấu Nối Miệng Gió)
- **Công dụng:** Chọn hàng chục miệng gió, tool tìm ống chính gần nhất, đặt cổ trích (Takeoff) và vẽ ống mềm (Flex Duct) nối vào.
- **Tìm ống:** dùng BoundingBox quanh miệng gió để Revit chỉ trả về các ống ở gần (quét toàn model, không phụ thuộc view). Điểm tap luôn cách đầu ống ≥ 200 mm; chiều dài ống mềm được tính kèm hệ số uốn 1.2.
- **An toàn:** chỉ dùng connector **gió**; mỗi miệng gió là một SubTransaction nên lỗi ở miệng gió nào thì hoàn tác sạch miệng gió đó, không để lại ống mềm dở dang; báo lý do thất bại cho từng miệng gió.

### 4. Clash Avoidance (Xử Lý Va Chạm)
- **Công dụng:** Tạo hệ ống bù (U-shape / Offset: 4 lơi 45° và 3 đoạn ống) bọc qua dầm, cột, ống cứu hỏa chỉ với 2 cú click và chọn hướng Lên/Xuống.
- **Tự tính vùng né:** bề rộng vùng né lấy từ BoundingBox của vật cản chiếu lên phương ống (không dùng đường chéo), độ cao lấy từ đỉnh/đáy vật cản cộng khe hở an toàn, tính cả khi **ống dốc** (cả 4 chỗ bẻ vẫn đúng 45° so với phương ống).
- **Từ chối khi không hợp lệ:** ống đứng/dốc quá 60°, vật cản không nằm trên đường đi của ống, ống đã nằm sẵn ở phía được chọn (không cần né), không đọc được kích thước ống, ống bị Pin, hoặc điểm cắt sát đầu ống.
- **Một Transaction duy nhất:** thiếu bất kỳ lơi nào thì **hoàn tác toàn bộ**, không để lại ống hở và không báo "thành công" sai.
- **Nhân bản đoạn giữa:** tool cắt ống và copy đoạn giữa để các đoạn mới kế thừa kích thước và System của ống gốc (việc kế thừa Insulation chưa được kiểm chứng).

---

## ⚠️ Giới hạn đã biết

Những điểm **chưa xử lý** hoặc **cần kiểm chứng trên Revit thật** (chi tiết trong `Specs/`):

| Tool | Giới hạn |
|---|---|
| Split | Đoạn dư ở cuối có thể rất ngắn (< 100 mm) hoặc dài hơn chuẩn tới 30 mm; chưa kiểm tra fitting/tap tại vị trí cắt; Union có lắp vừa đoạn ngắn không chưa kiểm chứng. |
| Hangers | Raytrace chưa tìm trong model **Link** (sàn/dầm trong file liên kết sẽ không được thấy); nhịp qua phụ kiện có thể vượt `spacing` thêm chiều dài phụ kiện. |
| Routing | Chưa gán kích thước ống mềm theo miệng gió; ống mềm chưa đi ra theo hướng connector miệng gió; chọn ống chỉ theo khoảng cách tâm. |
| Clash | Vùng né nay sát vật cản nên elbow có thể không đủ chỗ (tool sẽ hoàn tác và báo lỗi); cua elbow có thể ăn vào khe hở 50 mm; chưa kiểm chứng việc copy có mang theo Insulation. |

---

## 📂 Cấu trúc thư mục

```text
📁 Revit-tools/
 ├── 📁 MEP_Tools.extension/      # <-- Dùng thư mục này để load vào pyRevit
 │    ├── 📁 lib/
 │    │    └── mep_common.py      # Hàm dùng chung (đọc tham số, nhập liệu, hình học...)
 │    └── 📁 HVAC.tab/
 │         └── 📁 Utilities.panel/
 │              ├── 📁 Split Pipes.pushbutton/
 │              ├── 📁 Auto Hangers.pushbutton/
 │              ├── 📁 Auto Routing.pushbutton/
 │              └── 📁 Clash Avoid.pushbutton/
 ├── 📁 Specs/                    # Tài liệu kỹ thuật (Algorithm Specifications)
 ├── 📁 tests/                    # Test chạy ngoài Revit (xem tests/README.md)
 ├── 📁 docs/                     # Ghi chú ý tưởng ban đầu
 ├── 📄 checklist.md              # Danh sách bug, trạng thái và việc cần xác nhận
 └── 📄 README.md
```

## ⚙️ Hướng dẫn Cài đặt (Installation)

1. Đảm bảo máy tính Windows của bạn đã cài đặt sẵn phần mềm [pyRevit](https://github.com/eirannejad/pyRevit).
2. Copy thư mục `MEP_Tools.extension` (**nguyên cả thư mục, gồm cả `lib/`**) vào máy tính (VD: `C:\BIM_Tools\MEP_Tools.extension`).
3. Mở phần mềm Revit. Trên thanh Ribbon, chọn Tab **pyRevit** $\rightarrow$ Bấm nút **Settings** (Biểu tượng bánh răng).
4. Vào thẻ **Custom Extension Directories**.
5. Bấm **Add Folder** và trỏ đường dẫn tới thư mục mẹ (VD: `C:\BIM_Tools\`).
6. Bấm **Save Settings and Reload**.
7. Một Tab mới tên là **HVAC** sẽ xuất hiện trên Revit cùng 4 công cụ nói trên.
