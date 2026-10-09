# Specification: Xử lý va chạm (Clash Avoidance v3.0)

## 1. Thông tin chung
- **Độ khó:** Rất Khó (4/4) - Giao cắt hình học 3D, lượng giác không gian, kiểm soát điểm biên và nhân bản đối tượng.
- **Mục tiêu:** Tạo hệ ống bù (U-shape / Offset) gồm 4 lơi và 3 đoạn ống để vòng qua chướng ngại vật, dựa trên kích thước thật của chướng ngại vật. Tất cả trong một Transaction: lỗi thì hoàn tác toàn bộ.

## 2. Đầu vào (Inputs)
- Click chọn **một hoặc nhiều** ống (Duct/Pipe) không bị Pin, bấm Finish.
- Click chọn **một hoặc nhiều** chướng ngại vật (Dầm, Cột, Ống cứu hỏa...), bấm Finish.
- Chọn hướng né: Lên hoặc Xuống.
- Chọn góc bẻ: **45° (mặc định)**, hoặc 15° / 30° / 60° (áp dụng cho cả ống gió và ống nước; DW-01.04: Z loại 1 ≤ 15°, loại 2 ≤ 60°, HD 6.1.3 "nên ≤ 15°"). Góc nhỏ cần nhiều chỗ dọc ống hơn; không đủ chỗ thì tool báo và hoàn tác.
- Chiều cao nâng và bề rộng vùng né được tự tính. Khe hở an toàn 50 mm tính từ mặt ngoài lớp bảo ôn (quy ước công ty).

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
   Nhờ vậy cả bốn chỗ bẻ đều đúng góc đã chọn (mặc định 45°) **so với phương ống**, kể cả ống dốc.
5. **Kiểm tra biên:** `pA` và `pD` phải nằm trong chiều dài ống gốc, cách mép ≥ 10 mm. Đây là phép so sánh một chiều theo tham số dọc ống (tích vô hướng với `D`).
6. **Thực thi trong 1 Transaction:** `BreakCurve` tại `pA`, `pD` → copy đoạn giữa 3 lần → xóa đoạn gốc → đặt lại đường tâm → 4 lần `NewElbowFitting`. Thiếu bất kỳ lơi nào thì `RollBack`.

## 4b. Nhiều vật cản / nhiều ống (đề xuất, chưa có quyết định của kỹ sư)
- Với mỗi ống, tool lấy các vật cản **nằm trên đường đi** của ống và tính chỗ né riêng cho từng vật cản.
- Hai chỗ né có đoạn ống thẳng giữa chúng **< 300 mm** (`MIN_STRAIGHT_BETWEEN_MM`, tự đề xuất) thì **gộp**: dùng hộp bao chung của các vật cản và tính lại thành một chỗ né rộng. Xa hơn thì né riêng từng cái.
- Thực thi **từ cuối ống về đầu** (đoạn đầu luôn giữ ElementId gốc nên các chỗ né phía trước vẫn nằm trên chính phần tử này).
- Một Transaction chung, mỗi chỗ né là một `SubTransaction`: chỗ nào lỗi (thiếu elbow, quá sát đầu ống...) thì hoàn tác riêng chỗ đó và báo lý do; các chỗ khác vẫn được làm. Không chỗ nào làm được thì thoát với toàn bộ lý do.
- Nhiều ống: mỗi ống tính độc lập (cao độ né theo kích thước từng ống). Sau khi bẻ, tool **cảnh báo** nếu hai ống được chọn vốn không chạm nhau nhưng sau khi bẻ khoảng cách giữa hai đường tâm nhỏ hơn tổng bán kính (kể cả bảo ôn). Chưa tự bẻ đồng bộ cao độ các ống song song.

## 5. Kết quả đã được kiểm chứng (mô hình Revit giả, 300 ca ngẫu nhiên)
Ống dốc ±40°, hướng bất kỳ trong mặt bằng, vật cản bất kỳ, Lên/Xuống: luôn đủ 5 đoạn nối liền, 4 góc đúng góc đã chọn (45°; đã thêm test 15°/30°/60°), đoạn giữa song song ống, phủ vật cản + 50 mm mỗi bên và đủ độ hở thẳng đứng.

## 6. Giới hạn đã biết (chưa xử lý, cần kiểm chứng trên Revit thật)
- **Nhiều ống:** chưa kiểm tra va chạm của các ống được bẻ với ống/vật khác ngoài danh sách đã chọn; chưa bẻ đồng bộ ống song song.
- **Chiều dài tối thiểu của elbow:** vùng né nay sát vật cản (đoạn giữa có thể chỉ ~400 mm với dầm hẹp), elbow có thể không đủ chỗ đặt. Khi đó tool hoàn tác và báo lỗi, chứ không để lại ống hở.
- **Bán kính cong:** cua của elbow có thể "ăn" vào khe hở 50 mm (ước tính ~21 mm với ống 300 mm, ~60 mm với ống 600 mm nếu bán kính tâm = 1.5×).
- **Dữ liệu kế thừa khi nhân bản:** kích thước và System được kế thừa từ ống gốc; việc Insulation/Lining có được copy theo hay không **chưa kiểm chứng**. Tap, accessory, hanger gắn vào đoạn bị xóa sẽ mất theo.
- Hình dạng lơi 45° của ống gió chữ nhật phụ thuộc Routing Preferences của loại ống.
