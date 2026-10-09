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
- **Quy tắc rải:** nhịp chọn theo từng nhóm ống (bảng theo HD hoặc tuỳ biến); mỗi đoạn ống dài `L` đặt `ceil(L / spacing)` giá, đều nhau và căn giữa. Nhịp giữa hai giá không vượt `spacing`, và **ống ngắn hơn `spacing` vẫn có đúng 1 giá** ở giữa.
- **Raytrace:** bắn tia lên trục Z (cần 3D View) tìm Sàn/Dầm, ty = khoảng cách − (nửa **chiều cao** ống + cách nhiệt). Chỉ ghi vào đúng tham số bạn chỉ định.
- **Né phụ kiện:** chỉ dịch giá trong phần nhịp còn dư, không bao giờ làm nhịp vượt `spacing` hay đẩy giá ra ngoài ống.
- **An toàn:** chạy lại không nhân đôi giá; bỏ qua ống đứng; báo cáo rõ giá nào **chưa có ty** và vì sao.

### 3. Auto Routing (Đấu Nối Miệng Gió)
- **Công dụng:** Chọn hàng chục miệng gió / hộp gió, tool tìm ống chính gần nhất, đặt cổ trích (Takeoff) và vẽ ống mềm (Flex Duct, đường kính theo connector, có/không bảo ôn) nối vào.
- **Tìm ống:** dùng BoundingBox quanh miệng gió để Revit chỉ trả về các ống ở gần (quét toàn model, không phụ thuộc view). Điểm tap luôn cách đầu ống ≥ 200 mm; chiều dài ống mềm được tính kèm hệ số uốn 1.2.
- **An toàn:** chỉ dùng connector **gió**; mỗi miệng gió là một SubTransaction nên lỗi ở miệng gió nào thì hoàn tác sạch miệng gió đó, không để lại ống mềm dở dang; báo lý do thất bại cho từng miệng gió.

### 4. Clash Avoidance (Xử Lý Va Chạm)
- **Công dụng:** Tạo hệ ống bù (U-shape / Offset: 4 lơi và 3 đoạn ống, góc mặc định 45°, chọn được 15°/30°/60°) bọc qua dầm, cột, ống cứu hỏa chọn được nhiều ống và nhiều vật cản một lần (vật cản đứng gần nhau tự gộp thành một chỗ né), chọn hướng Lên/Xuống.
- **Tự tính vùng né:** bề rộng vùng né lấy từ BoundingBox của vật cản chiếu lên phương ống (không dùng đường chéo), độ cao lấy từ đỉnh/đáy vật cản cộng khe hở an toàn, tính cả khi **ống dốc** (cả 4 chỗ bẻ vẫn đúng 45° so với phương ống).
- **Từ chối khi không hợp lệ:** ống đứng/dốc quá 60°, vật cản không nằm trên đường đi của ống, ống đã nằm sẵn ở phía được chọn (không cần né), không đọc được kích thước ống, ống bị Pin, hoặc điểm cắt sát đầu ống.
- **Một Transaction duy nhất:** thiếu bất kỳ lơi nào thì **hoàn tác toàn bộ**, không để lại ống hở và không báo "thành công" sai.
- **Nhân bản đoạn giữa:** tool cắt ống và copy đoạn giữa để các đoạn mới kế thừa kích thước và System của ống gốc (việc kế thừa Insulation chưa được kiểm chứng).

---

> 📐 Đối chiếu với tiêu chuẩn Cơ điện (`Docs_tieu_chuan/`): xem `Specs/00_Doi_chieu_tieu_chuan.md`.

## ⚠️ Giới hạn đã biết

Những điểm **chưa xử lý** hoặc **cần kiểm chứng trên Revit thật** (chi tiết trong `Specs/`):

| Tool | Giới hạn |
|---|---|
| Split | Đoạn dư ở cuối có thể rất ngắn (< 100 mm) hoặc dài hơn chuẩn tới 30 mm; chưa kiểm tra fitting/tap tại vị trí cắt; Union có lắp vừa đoạn ngắn không chưa kiểm chứng. |
| Hangers | Raytrace chưa tìm trong model **Link** (sàn/dầm trong file liên kết sẽ không được thấy); nhịp qua phụ kiện có thể vượt `spacing` thêm chiều dài phụ kiện. |
| Routing | Đường kính ống mềm chỉ gán được khi connector tròn; ống mềm chưa đi ra theo hướng connector miệng gió; chọn ống chỉ theo khoảng cách tâm. |
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
 ├── 📁 tests/                    # Test chạy ngoài Revit + try_it.py (chạy thử có hộp thoại)
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

---

## 📝 Lịch sử thay đổi

> Mọi thay đổi dưới đây mới được kiểm tra bằng mô hình Revit giả (`tests/`), **chưa chạy trên Revit thật**.

### v1.1.0 — 2026-10-09 · Đối chiếu tiêu chuẩn Cơ điện, né va chạm nhiều ống/nhiều vật cản
Đối chiếu với `Docs_tieu_chuan/` (DUCT-WORK R0 2025/08, SME-SDG-01), chi tiết trong `Specs/00_Doi_chieu_tieu_chuan.md`. Các ô người dùng nhập được giữ nguyên; giá trị vượt chuẩn chỉ hỏi xác nhận.

**Auto Hangers**
- Nhịp giá đỡ chọn riêng cho từng nhóm ống (ống gió, mỗi Pipe Type): bảng theo HD (PPR, UPVC, chữa cháy, nước ngưng, gas đồng) hoặc "Tuỳ biến".
- Giá đỡ cách phụ kiện/tay nhánh ≥ 200 mm (ống gió) hoặc 100 mm (ống nước), và cách thiết bị/miệng gió 300 mm; cả ba là ô nhập.
- Bổ sung giá cuối tuyến cho ống gió có đầu ống tự do (≤ 300 mm cách đầu ống).
- Ty treo kết thúc tại đỉnh / tâm / đáy ống; bề rộng giá cộng bảo ôn hai bên.
- Sửa: hai giá liền kề dịch ngược chiều làm nhịp vượt giá trị nhập; ghi chiều dài ty âm; nhập nhầm đơn vị (nhịp < 200 mm) không hỏi; đầu nối chưa liền connector (Union lỗi) bị coi là cuối tuyến.

**Auto Routing**
- Nhận mọi family có connector gió còn trống (kể cả hộp gió); đường kính ống mềm theo connector tròn.
- Chọn loại ống mềm; chọn có/không bảo ôn (loại và bề dày).
- Chiều dài ống mềm mặc định 2000 mm (DW-01.01), nhập hơn thì hỏi xác nhận.
- Cổ trích cách cút ≥ 8W (ống chữ nhật) / 6D (ống tròn): vẫn đặt khi không đủ chỗ nhưng cảnh báo.
- Cổ trích trên cùng ống phải cách nhau đủ chỗ; bỏ qua ống bị Pin, ống khác loại hệ thống, ống nhỏ hơn cổ trích.

**Clash Avoid**
- Chọn góc bẻ: 45° (mặc định), 15°, 30°, 60°.
- Chọn nhiều ống và nhiều vật cản một lần; vật cản đứng gần nhau được gộp thành một chỗ né (ngưỡng 300 mm là đề xuất, chờ kỹ sư xác nhận).
- Mỗi chỗ né hoàn tác riêng khi lỗi; cảnh báo nếu việc bẻ làm hai ống có thể va chạm nhau.

**Split Ducts/Pipes**: gợi ý 1120 (TDC) / 1180 (nẹp C, bích V) ở ô nhập; báo phần tử không phải ống cứng bị bỏ qua.

**Khác**: thêm `tests/try_it.py` (chạy thử có hộp thoại trong terminal trên Revit giả), `docs/cau_hoi_cho_ky_su_co_dien.md` (câu hỏi cần kỹ sư xác nhận).

### v1.0.0 — 2026-10-07 · Bản sửa lỗi nền
Sửa các lỗi crash và sai nghiệp vụ của 4 tool (38/52 mục trong `checklist.md` đã sửa), thêm bộ test trên Revit giả.
