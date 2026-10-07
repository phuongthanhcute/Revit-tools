# Specification: Xử lý va chạm (Clash Avoidance v3.0)

## 1. Thông tin chung
- **Độ khó:** Rất Khó (4/4) - Giao cắt hình học 3D, lượng giác không gian, kiểm soát điểm biên và nhân bản đối tượng.
- **Mục tiêu:** Tạo hệ ống bù (U-shape / Offset) gồm 4 lơi 45° và 3 đoạn ống để vòng qua chướng ngại vật, dựa trên kích thước thật của chướng ngại vật. Tất cả trong một Transaction: lỗi thì hoàn tác toàn bộ.

## 2. Đầu vào (Inputs)
- Click chọn 1 ống (Duct/Pipe) không bị Pin.
- Click chọn chướng ngại vật (Dầm, Cột, Ống cứu hỏa...).
- Chọn hướng né: Lên hoặc Xuống.
- Chiều cao nâng, bề rộng vùng né và góc lơi được tự tính (góc cố định 45° so với phương ống).

## 3. Điều kiện tool sẽ TỪ CHỐI (model giữ nguyên)
- Ống đứng hoặc dốc quá 60°.
- Không đọc được kích thước tiết diện ống.
- Vật cản không nằm trên đường đi của ống (đường tâm nới ra nửa kích thước lớn nhất của ống + cách nhiệt + 50 mm).
- Ống đã nằm sẵn ở phía được chọn so với vật cản (không cần né theo hướng đó). Tool báo để người dùng chọn hướng ngược lại, không ép nâng/hạ "cho có".
- Điểm cắt rơi ra ngoài ống hoặc cách mép < 10 mm.
- Bất kỳ lơi nào không tạo được, hoặc `BreakCurve`/copy lỗi: **hoàn tác toàn bộ** và báo lý do.

## 4. Luồng thuật toán
1. **Kích thước ống:** đọc bằng `BuiltInParameter` (fallback tên hiển thị), cộng cách nhiệt hai phía.
2. **Vùng né theo mặt bằng** (dầm/cột là lăng trụ thẳng đứng):
   - `E_h` = bề rộng của BoundingBox chiếu lên phương nằm ngang của ống (chiếu 4 đỉnh mặt bằng, không dùng đường chéo).
   - `pt_clash` = điểm trên đường tâm ống nằm đúng dưới tâm hộp theo mặt bằng.
   - `L_gap = (E_h + 100 mm) / cos(độ dốc)`, đo dọc theo ống: phủ trọn vật cản + 50 mm mỗi bên.
3. **Độ lệch thẳng đứng `H`:** `H_required` = chênh lệch giữa cao độ cần đạt (đỉnh/đáy vật cản ± 50 mm ± nửa chiều cao ống) và cao độ ống **tại đầu bất lợi nhất của vùng né** (ống dốc thì đoạn giữa song song với ống nên cao độ thay đổi dọc vùng né). `H = max(H_required, 100 mm)` khi `H_required > 0`.
4. **Bốn điểm gãy:** phân tích `H` thành thành phần dọc ống `o_along` và vuông góc ống `h_perp = H·cos(độ dốc)`.
   `pA = B_line + D·(o_along − h_perp)`, `pD = C_line + D·(o_along + h_perp)` (luôn nằm trên đường tâm ống gốc, điều kiện của `BreakCurve`), `pB = B_line + O·H`, `pC = C_line + O·H`.
   Nhờ vậy cả bốn chỗ bẻ đều đúng 45° **so với phương ống**, kể cả ống dốc.
5. **Kiểm tra biên:** `pA` và `pD` phải nằm trong chiều dài ống gốc, cách mép ≥ 10 mm. Đây là phép so sánh một chiều theo tham số dọc ống (tích vô hướng với `D`).
6. **Thực thi trong 1 Transaction:** `BreakCurve` tại `pA`, `pD` → copy đoạn giữa 3 lần → xóa đoạn gốc → đặt lại đường tâm → 4 lần `NewElbowFitting`. Thiếu bất kỳ lơi nào thì `RollBack`.

## 5. Kết quả đã được kiểm chứng (mô hình Revit giả, 300 ca ngẫu nhiên)
Ống dốc ±40°, hướng bất kỳ trong mặt bằng, vật cản bất kỳ, Lên/Xuống: luôn đủ 5 đoạn nối liền, 4 góc 45°, đoạn giữa song song ống, phủ vật cản + 50 mm mỗi bên và đủ độ hở thẳng đứng.

## 6. Giới hạn đã biết (chưa xử lý, cần kiểm chứng trên Revit thật)
- **Chiều dài tối thiểu của elbow:** vùng né nay sát vật cản (đoạn giữa có thể chỉ ~400 mm với dầm hẹp), elbow có thể không đủ chỗ đặt. Khi đó tool hoàn tác và báo lỗi, chứ không để lại ống hở.
- **Bán kính cong:** cua của elbow có thể "ăn" vào khe hở 50 mm (ước tính ~21 mm với ống 300 mm, ~60 mm với ống 600 mm nếu bán kính tâm = 1.5×).
- **Dữ liệu kế thừa khi nhân bản:** kích thước và System được kế thừa từ ống gốc; việc Insulation/Lining có được copy theo hay không **chưa kiểm chứng**. Tap, accessory, hanger gắn vào đoạn bị xóa sẽ mất theo.
- Hình dạng lơi 45° của ống gió chữ nhật phụ thuộc Routing Preferences của loại ống.
