# Đối chiếu code với tiêu chuẩn kỹ thuật gốc (bên Cơ điện)

Ngày đối chiếu: 2026-10-09 · Nguồn: thư mục `Docs_tieu_chuan/`

| Tài liệu | Phạm vi đã dùng |
|---|---|
| `DUCT-WORK.pdf` (Sigma, R0 2025/08, 15 trang bản vẽ) | DW-01 (ống gió, phụ kiện), DW-02 (bố trí, giá đỡ), DW-03 (quạt, xuyên tường) |
| `HD TRIEN KHAI BAN VE SHOP_202509.pdf` (SME-SDG-01, rev 01) | Mục 6.1 (ống gió), 4.x/6.x (giá đỡ ống nước, nước ngưng) |
| `ELECTRICAL-WORK.pdf` | **Không áp dụng**: bộ tool hiện chỉ có tab HVAC (không có tool cho ống luồn dây/thang máng cáp) |

**Nguyên tắc:** ô người dùng nhập (chiều dài cắt, khoảng cách giá đỡ, chiều dài ống mềm tối đa, tên tham số ty, hướng né, loại family) giữ nguyên. Khi giá trị nhập vượt giới hạn của chuẩn thì chỉ **hỏi xác nhận**, không tự sửa.

Ký hiệu: ✅ khớp · 🔧 đã sửa trong đợt này · ⚠️ chưa tuân thủ / cần quyết định · ❔ không kiểm chứng được bằng code

## 1. Split Ducts / Pipes

| Yêu cầu chuẩn | Code | |
|---|---|---|
| Chiều dài ống gió tiêu chuẩn **1120** (mối nối TDC) hoặc **1180** (nẹp C, bích V), DW-01.01 | Mặc định 1120, người dùng nhập được | ✅ (🔧 thêm gợi ý 1120/1180 vào ô nhập) |
| Chiều dài ống nước 6000 | Không có trong 3 tài liệu | ❔ giữ nguyên mặc định |
| Giá đỡ cách mối nối ống gió ≥ 200 mm (DW-02.02) | Tool cắt không kiểm tra giá đỡ sẵn có tại điểm cắt | ⚠️ nên chạy Split **trước** Auto Hangers |

## 2. Auto Hangers

| Yêu cầu chuẩn | Code | |
|---|---|---|
| Nhịp giá đỡ ống gió cứng ≤ 2.5 m, ống mềm ≤ 1 m (DW-02.02, HD 6.1.3.15) | Nhịp do người dùng nhập (mặc định 2000). Ống gió nhập > 2500 thì hỏi xác nhận | 🔧 |
| Giá đỡ cách mối nối ống gió ≥ 200 mm, cách phụ kiện chuyển hướng 200~300 mm | Clearance cũ 150 mm. Nay ống gió 200 mm, ống nước 100 mm (HD: 100~300 mm) | 🔧 |
| Ty treo nằm ngoài lớp bảo ôn (DW-02.03) | Bề rộng giá cũ = bề rộng ống, bỏ qua bảo ôn. Nay = rộng ống + 2 × bảo ôn | 🔧 |
| (Không phải chuẩn) nhịp giữa hai giá ≤ spacing | Bug có sẵn: hai giá kề dịch ngược chiều để né phụ kiện có thể vượt spacing (vd. ống 6334 mm, nhịp 2000 → 2033). Nay mỗi giá chỉ dịch ≤ nửa phần dư | 🔧 |
| Nhịp ống nước theo vật liệu/đường kính (PPR ≤ 1~2.5 m, UPVC ≤ 1~2.5 m, chữa cháy ≤ 4/6 m, nước ngưng ≤ 1~1.5 m) | Một nhịp chung cho cả ống nước và gió; không cảnh báo theo vật liệu | ⚠️ |
| Giá đỡ tại đầu cuối tuyến ống gió ≤ 300 mm kèm kẹp đỉnh | Không xét đầu tuyến; giá đặt giữa mỗi đoạn | ⚠️ |
| Không đặt giá trùng vị trí cửa gió; giá cho phụ kiện rộng ≥ 1000 mm; giá cố định cạnh dầm ≤ 5 × nhịp | Chưa xử lý | ⚠️ |
| Ống đứng: giá đỡ ưu tiên gắn sàn, 1.5~2 × nhịp ngang | Ống đứng (dốc > 60°) bị bỏ qua và báo cáo | ⚠️ ngoài phạm vi tool |
| Chiều dài ty tới giá treo (thanh đỡ nằm dưới đáy ống) | Ty = khoảng cách tới sàn − nửa cao ống − bảo ôn; điểm đặt family do family quy định | ❔ cần đối chiếu với family giá đỡ thực tế của dự án |

## 3. Auto Routing

| Yêu cầu chuẩn | Code | |
|---|---|---|
| Ống gió mềm ≤ **2 m**, độ võng ≤ 50 mm/m (DW-01.01, HD 6.1.3.1) | Mặc định cũ 3000 mm. Nay mặc định 2000; nhập > 2000 thì hỏi xác nhận | 🔧 |
| Chân rẽ chữ nhật cách điểm chuyển hướng ≥ **8W**, cách côn ≥ 150 mm (HD 6.1.3.7) | Chỉ giữ ≥ 200 mm cách đầu ống; không xét khoảng cách tới cút | ⚠️ cần đọc connector/fitting kề đầu ống |
| T ống tròn cách điểm chuyển hướng ≥ 6D, giữa hai T thẳng ≥ 6D (T thu: 0.5D) | Không xét | ⚠️ |
| Chân rẽ có L ≥ 150 mm, côn 45°~60° (DW-01.03) | Do `NewTakeoffFitting` của Revit quyết định | ❔ |
| Miệng gió gắn qua hộp gió cao ≥ 250 mm, cổ hộp = cổ miệng gió + 10 mm (DW-01.04) | Nối ống mềm trực tiếp vào miệng gió | ⚠️ phụ thuộc quy ước dự án |

## 4. Clash Avoid

| Yêu cầu chuẩn | Code | |
|---|---|---|
| Z/Offset ống gió: Loại 1 γ ≤ 15°, Loại 2 γ ≤ 60° (DW-01.04); HD 6.1.3 "nên ≤ 15°" | Cố định 45° (nằm trong Loại 2, nhưng vượt khuyến nghị 15°) | ⚠️ **cần quyết định**: giữ 45° hay cho chọn góc |
| Đoạn thẳng ≥ 25 mm hai đầu Z | Không kiểm tra riêng; nếu elbow không đủ chỗ thì Revit lỗi và tool hoàn tác | ❔ |
| Cút chữ nhật R ≥ 0.5W; tiết diện không thu hẹp | Do Routing Preferences của Revit | ❔ |
| Cao độ ống gió tính theo đáy ống BOD so với sàn hoàn thiện | Tool dùng cao độ tuyến tâm và đỉnh/đáy vật cản, khe hở 50 mm cố định | ❔ khe hở 50 mm không có trong chuẩn |

## 5. Quyết định của kỹ sư (2026-10-09) và trạng thái triển khai

| # | Quyết định | Trạng thái |
|---|---|---|
| 1-2 | Góc bẻ: mặc định 45°, cho chọn 15°/30°/60°, cả ống gió và ống nước | ✅ Clash Avoid |
| 3 | Khe hở 50 mm tính cả bảo ôn | ✅ giữ nguyên (đã tính từ mặt ngoài bảo ôn) |
| 4 | Đoạn giữa hai phụ kiện: miễn sinh ra và thi công được | ✅ Revit lỗi thì tool hoàn tác |
| 5-6 | Cổ trích gần cút: vẫn cho đặt, kèm cảnh báo; áp dụng 8W / 6D | ✅ Auto Routing (chỉ xét cút ở đầu ống chính; chưa xét giữa các T) |
| 7 | Hộp gió có sẵn, nối vào connector Duct Diameter của family | ✅ nhận mọi family có connector gió trống |
| 8-9 | Ống mềm tối đa 2 m, giá đỡ ≤ 1 m; đường kính theo connector; có/không bảo ôn | ✅ (giá đỡ ống mềm chưa có tool: tool Hangers chỉ nhận Duct cứng và Pipe) |
| 10 | Nhịp theo từng loại ống, có "Tuỳ biến"; tránh tay nhánh và thiết bị | ✅ Auto Hangers (khoảng cách tới tay nhánh/thiết bị là ô nhập; mặc định 200/100/300 mm do tôi chọn) |
| 10 | "Xem file pipe-work" | ⚠️ **file này chưa có trong `Docs_tieu_chuan/`**; đang dùng bảng nhịp trong HD. Cần file để đối chiếu thép/chiller |
| 11 | Đầu tuyến = nối máy, cuối tuyến = cuối ống | ✅ chỉ xử lý đầu ống **tự do**; đầu nối máy chưa có quy tắc riêng |
| 12 | Giá cách cửa gió: tự chọn theo chuẩn ngoài | ✅ mặc định 300 mm, tuỳ biến (cần kỹ sư xác nhận con số) |
| 13 | Phụ kiện ≥ 1000 mm: theo file (DW-02.02: "bố trí giá đỡ", không nói số giá) | ⬜ chưa làm: file không nêu 1 hay 2 giá |
| 14 | Giá cố định cạnh dầm: bán tự động | ⬜ chưa làm: cần thống nhất cách đánh dấu (tham số nào) |
| 15 | Ống đứng | ⬜ chưa trả lời |
| 16 | Family giá đỡ chỉ là ty: thêm lựa chọn xác định | ✅ chọn ty kết thúc ở đỉnh / tâm / đáy ống |
| 17 | Thứ tự Split → Hangers → Routing | ✅ ghi nhận |
| 18 | Điện: theo file ELECTRICAL-WORK | ⬜ tính năng mới, chưa làm |
