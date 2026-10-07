# Checklist bug: MEP Automation Toolkit for Revit

Cập nhật: 2026-10-07 · Phạm vi: 4 tool trong `MEP_Tools.extension/HVAC.tab/Utilities.panel/` và `lib/mep_common.py`

## Tổng quan

| Mức | Tổng | ✅ Đã sửa | ◐ Sửa một phần | ⬜ Còn mở |
|---|---|---|---|---|
| 🔴 P0 (crash) | 6 | 6 | 0 | 0 |
| 🟠 P1 (sai kết quả / sai nghiệp vụ) | 36 | 26 | 0 | 10 |
| 🟡 P2 (chất lượng / bảo trì) | 10 | 6 | 2 | 2 |
| **Tổng** | **52** | **38** | **2** | **12** |

**Chú giải status:** ✅ đã sửa · ◐ sửa một phần · ⬜ còn mở.

**Cách đọc cột "Sau khi sửa":** ghi cách sửa và bằng chứng kiểm tra. Mọi kiểm tra chạy trên **mô hình Revit giả** (script `test_p0.py`, `test_fixes.py`, `test_batch.py`), **chưa chạy trên Revit thật**. Các điểm cần Revit thật được nêu ở cột "Lý do block".

**Cách đọc cột "Lý do block":** lý do bug chưa sửa được (hoặc chưa xác nhận được) vì phụ thuộc hành vi của Revit thật hoặc quyết định của người dùng.

## Bảng bug

| ID | Tên bug | Mô tả chi tiết | Status | Sau khi sửa | Lý do block |
|---|---|---|---|---|---|
| BUG-01 | `DB.UI` không tồn tại | Clash Avoid dòng 49, 66, 72 dùng `DB.UI.Selection...`. `ISelectionFilter` và `ObjectType` thuộc `Autodesk.Revit.UI`, không thuộc `DB`, nên script ném `AttributeError` ngay khi nạp. | ✅ Đã sửa | Import `UI` từ pyrevit, dùng `UI.Selection.*`. Bản cũ ném `AttributeError: UI`, bản mới chạy qua (test_p0). | |
| BUG-02 | Thiếu import `List` (Clash Avoid) | Dòng 176 trở đi dùng `List[...]` nhưng chưa import, gây `NameError` sau khi `BreakCurve` đã chạy, có thể để lại ống bị cắt dở. | ✅ Đã sửa | Thêm `from System.Collections.Generic import List`. `pyflakes` sạch; bản backup cũ trong `Scripts/` vẫn báo lỗi. | |
| BUG-03 | Thiếu import `List` (Auto Hangers) | Dòng 117 dùng `List` chưa import, tool chết trước khi hiện hộp chọn Family. | ✅ Đã sửa | Thêm import. Bản cũ ném `NameError`, bản mới chạy tới cuối (test_p0). | |
| BUG-04 | `CommandOption` không tồn tại | Khối `components` (code chết) gọi `forms.CommandSwitchWindow.CommandOption` không tồn tại, gây `AttributeError`. | ✅ Đã sửa | Xóa cả khối. | |
| BUG-05 | `selected_symbol.item` có thể sai | `SelectFromList` với `TemplateListItem` thường trả về đối tượng đã unwrap, nên `.item` có thể gây `AttributeError`. | ✅ Đã sửa (chưa xác nhận) | Đổi thành `hanger_symbol = selected_symbol`. Test chỉ chứng minh trong stub do tôi dựng theo giả định. | Cần thử trên pyRevit thật để xác nhận `show` trả về gì. Nếu trả `TemplateListItem` thì phải đổi lại `.item`. |
| BUG-06 | `except Exception` nuốt lỗi | Clash Avoid dòng 79 bắt mọi lỗi (kể cả `AttributeError` của BUG-01) rồi thoát im lặng, người dùng không thấy gì. | ✅ Đã sửa | Chỉ bắt `OperationCanceledException`. ESC thoát sạch, lỗi khác nổi lên đúng (test_p0). | |
| BUG-07 | Ống ngắn không có giá đỡ | Điều kiện `continue` loại ống `L ≤ spacing`, nên nhánh "1 giá ở trọng tâm" là code chết và README nói sai. Tái hiện: ống 500, 1120, 1999, 2000 mm đều 0 giá. | ✅ Đã sửa | Mỗi đoạn đặt `k = max(1, ceil(L/spacing))` giá, giá thứ `i` tại `(i+0.5)·L/k`. Ống 500, 1120, 1999, 2000 mm có đúng 1 giá ở giữa. | |
| BUG-08 | Split rồi Hangers cho 0 giá | Split cắt ống gió thành đoạn 1120 mm, Hangers mặc định 2000 mm nên mọi đoạn bị bỏ qua. Đây là luồng dùng phổ biến nhất. | ✅ Đã sửa | Mỗi đoạn 1120 mm có 1 giá (4 đoạn cho 4 giá, x = 560, 1680, 2800, 3920). | |
| BUG-09 | Hai giá gần như trùng nhau | Khi `L = spacing + ε`, hai giá cách nhau chỉ `ε` (ống 2001 mm: cách nhau 1 mm). | ✅ Đã sửa | Ống 2001 mm: hai giá cách nhau 1000,5 mm. Phép thử ngẫu nhiên 400 cặp ống: số giá đúng `ceil(L/s)`, mọi nhịp ≤ spacing kể cả qua mối nối, không có giá trùng. | |
| BUG-10 | Dịch né phụ kiện phá giới hạn nhịp | Dịch cố định +150 mm làm nhịp vượt spacing (2150 so với 2000). Spacing 250 mm: giá cuối nằm ở x = 1025 trên ống dài 1000 mm (ngoài ống). Không kiểm tra lại sau khi dịch. | ✅ Đã sửa | Thử dịch ±150, ±300... mm nhưng chỉ trong phần nhịp còn dư `(spacing − L/k)` và trong đoạn ống. Không còn chỗ dịch thì giữ vị trí gốc và báo "còn sát phụ kiện". Phép thử 300 ống ngẫu nhiên kèm fitting ngẫu nhiên: 0 vi phạm. | |
| BUG-11 | Nhịp qua phụ kiện lớn hơn spacing | Gap giữa hai giá ở hai đoạn kề nhau bằng đúng `spacing` chưa tính chiều dài phụ kiện nằm giữa. Tái hiện: hai ống 6000 mm cách nhau fitting 400 mm cho nhịp 2400 mm (giới hạn 2000). | ⬜ Còn mở | Chưa sửa. Đã ghi vào `Specs/02_Auto_Hangers.md` mục "Giới hạn đã biết". | Cần lấy chiều dài fitting thật (hình học hoặc connector của fitting) từ Revit, mô hình giả không dựng được. |
| BUG-12 | Ty treo sai cho ống chữ nhật | Code trừ nửa **bề rộng** thay vì nửa **chiều cao** (ống gió 800×300 cho ty 600 mm, đúng phải 850 mm). Ống tròn dùng đường kính danh nghĩa, chưa tính cách nhiệt. | ✅ Đã sửa | Trừ nửa chiều cao tiết diện ngoài cộng cách nhiệt. Ống 800×300: 850 mm. Ống tròn Ø150: 925 mm. Có cách nhiệt 25 mm: 900 mm. | |
| BUG-13 | Raytrace bỏ qua model liên kết | Script không bật `FindReferencesInRevitLinks`, và chỉ lọc Floors và Structural Framing, nên sàn/dầm nằm trong file Link không được thấy. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec và README. | Cần xác nhận trên Revit thật: `ReferenceIntersector` có thấy sàn trong Link không, và view phối cảnh có dùng được không. |
| BUG-14 | Giá đỡ trên ống đứng vô nghĩa | `atan2(0,0)+90°` làm mọi giá xoay 90°, và tia bắn dọc theo trục ống. | ✅ Đã sửa | Ống dốc > 60° bị bỏ qua và báo cáo "Ống đứng bỏ qua". Ống 45° vẫn có giá, ống 70° bị bỏ qua. | |
| BUG-15 | Chạy lại nhân đôi giá đỡ | Không kiểm tra giá đã tồn tại: chạy lần 2 làm 3 giá thành 6. | ✅ Đã sửa | Bỏ qua nếu đã có giá cùng loại trong bán kính 100 mm và báo cáo số giá bỏ qua. Family khác loại không bị coi là đã có. | |
| BUG-16 | `L_gap` dùng đường chéo bbox | Dầm rộng 300 mm cắt ngang ống cho vùng né 6907 mm thay vì ~1200 mm (dư 1427%). Dầm cách đầu ống 2 m bị từ chối dù né 1,2 m khả thi. | ✅ Đã sửa | `L_gap = (E_h + 100 mm)/cos(độ dốc)`, trong đó `E_h` là bề rộng bbox chiếu lên phương ống trên mặt bằng. Dầm 300 mm cho vùng né 1200 mm. Dầm cách đầu ống 2 m được xử lý (đoạn đầu 1400 mm). | |
| BUG-17 | Góc bẻ lệch và bất đối xứng trên ống dốc | Ống dốc 10%: hai elbow đầu bẻ 42,14° và hai elbow sau bẻ 47,86° (45° ∓ θ/2) thay vì 45°. | ✅ Đã sửa | Phân tích `H` thành thành phần dọc ống `o_along` và vuông góc ống `h_perp`; cả 4 elbow đúng 45° so với phương ống. Kiểm tra dốc 2,86°, 5,71°, 15°, 30° cả Lên và Xuống, cộng 300 ca ngẫu nhiên (dốc ±40°, mọi hướng trong mặt bằng). | |
| BUG-18 | Ống đứng làm hình học suy biến | Ống đứng cho 5 đoạn chồng lên nhau trên trục ống, có đoạn dài 0, không tạo độ lệch nào. | ✅ Đã sửa | Ống đứng hoặc dốc quá 60° bị từ chối bằng thông báo, model giữ nguyên. Ống 55° vẫn xử lý được. Ngưỡng 60° là hằng số do tôi chọn. | |
| BUG-19 | Cua elbow ăn khe hở 50 mm | Elbow có bán kính cong nên đường tâm tụt xuống tại mép vật cản. Ước tính giải tích (R = 1,5× kích thước): ống 300 mm tụt ~21 mm, ống 600 mm tụt ~60 mm (âm khe hở). Rủi ro tăng sau khi sửa BUG-16 vì vùng né nay sát vật cản. | ⬜ Còn mở | Chưa sửa. Hiện nếu elbow không tạo được thì tool hoàn tác và báo lỗi (BUG-22). | Cần bán kính cong thật của loại elbow trong Revit. Số liệu hiện tại chỉ là giải tích với giả định R = 1,5×. |
| BUG-20 | Không kiểm tra vật cản có cắt ống | Vật cản cách ống 50 m vẫn tạo đủ 5 đoạn và báo thành công. | ✅ Đã sửa | Kiểm tra đường tâm ống (nới nửa kích thước lớn nhất cộng cách nhiệt cộng 50 mm) có cắt bbox vật cản không (phương pháp slab). Không cắt thì từ chối, model giữ nguyên. Đối chiếu với brute-force 3000 đoạn ngẫu nhiên: không có lần "bỏ lọt". | |
| BUG-21 | Biên an toàn 10 mm quá nhỏ | Script chấp nhận đoạn đầu chỉ dài 15 mm trước elbow đầu tiên. | ⬜ Còn mở | Chưa sửa quy tắc 10 mm. Nếu elbow không đặt được thì tool hoàn tác và báo lỗi (BUG-22), nên không còn để lại ống hở. | Cần chiều dài tay elbow tối thiểu thật từ Revit để đặt biên đúng. Rủi ro tăng vì đoạn giữa nay ngắn hơn. |
| BUG-22 | Báo thành công giả khi elbow lỗi | Lỗi tạo elbow chỉ `print`, nhưng dialog "thành công" hiện vô điều kiện (trong kịch bản ống đứng chỉ 2/4 elbow được tạo). Ống hở vẫn được commit. | ✅ Đã sửa | Toàn bộ trong 1 `DB.Transaction`; thiếu bất kỳ elbow nào, hoặc `BreakCurve` lỗi, thì `RollBack`, báo lý do và model giữ nguyên. Kiểm tra bằng cách giả lập lỗi elbow thứ 1, 3, 4 và cặp 2+3: đều hoàn tác sạch. | |
| BUG-23 | Nâng tối thiểu 100 mm dù không va chạm | Vật cản thấp hơn ống, chọn "Lên": ống vẫn nâng 100 mm (z = 3100) dù không có va chạm. | ✅ Đã sửa | Tính `H_required`; nếu `≤ 0` thì báo "không cần né" và thoát. Mức tối thiểu 100 mm chỉ áp khi thật sự cần né. Va chạm nhỏ vẫn được xử lý (nâng 130 mm). | |
| BUG-24 | Chiều cao ống tròn sai | Không tìm thấy "Height" thì dùng mặc định 152,4 mm, nên ống tròn Ø600 bị ngắn 224 mm. Tên tham số phụ thuộc ngôn ngữ Revit. | ✅ Đã sửa | Đọc kích thước bằng `BuiltInParameter` (fallback tên hiển thị) và cộng cách nhiệt hai phía. Không đọc được kích thước thì từ chối thay vì đoán. Ống tròn Ø600 cho z = 3550 mm đúng; cách nhiệt 25 mm cho 3425 mm với ống 600×300. | |
| BUG-25 | Rủi ro mất dữ liệu khi nhân bản | Tool copy đoạn giữa 3 lần rồi xóa đoạn gốc. Insulation/lining có được copy theo không chưa biết. Tap, accessory, hanger gắn vào đoạn bị xóa sẽ mất theo. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 04. | Cần thí nghiệm trên Revit thật xem `CopyElements` có mang theo các phần tử phụ thuộc không. |
| BUG-26 | Kích thước flex không khớp miệng gió | Script không đọc hay gán kích thước nào cho ống mềm; `flex_types[0]` chọn tùy ý (có thể là loại chữ nhật). | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 03. | Cần hành vi thật của Revit khi gán kích thước cho `FlexDuct` và khi `ConnectTo` bị lệch size. Nên làm cùng BUG-47. |
| BUG-27 | Lỗi giữa chừng để lại flex mồ côi | Nếu `NewTakeoffFitting` lỗi sau khi flex đã tạo và nối vào miệng gió, flex vẫn nằm trong model nhưng bị tính là thất bại. | ✅ Đã sửa | Mỗi miệng gió là 1 `SubTransaction`; lỗi thì `RollBack` (flex bị xóa, connector miệng gió tự do trở lại). Các miệng gió khác vẫn được nối (3 miệng gió, #2 lỗi: 2 thành công, 1 thất bại). | |
| BUG-28 | Chọn nhầm connector | Lấy connector rảnh đầu tiên, không lọc domain nên có thể chọn connector điện của miệng gió. | ✅ Đã sửa | Chỉ chọn connector `Domain.DomainHvac`. Connector điện đứng trước vẫn nối đúng connector gió. Miệng gió chỉ có connector điện thì báo "không có connector gió nào còn trống". | |
| BUG-29 | Tap rơi vào đầu ống | `Curve.Project` kẹp về đầu mút: miệng gió cách đầu ống 600 mm vẫn tap ngay tại đầu ống (x = 5000) và báo "Thành công". Tap cách đầu ống 50 mm cũng được chấp nhận. | ✅ Đã sửa | Điểm tap được kéo vào trong để cách mỗi đầu ống ít nhất 200 mm (x = −500 cho 200, x = 5600 cho 4800); ống ngắn hơn 400 mm bị loại, tool thử ống khác. Con số 200 mm là hằng số do tôi chọn. | |
| BUG-30 | Tìm ống chỉ trong view hiện hành | Cả hai collector dùng `doc.ActiveView.Id`, nên ống/fitting bị ẩn, ngoài view range hoặc section box bị coi là không có. | ✅ Đã sửa | Bỏ giới hạn theo view ở Auto Routing và Auto Hangers (quét toàn model, vẫn dùng quick filter theo bbox). Test chỉ xác nhận trong code không còn `ActiveView.Id`; tác động hiệu năng trên model lớn chưa đo được. | |
| BUG-31 | Giới hạn độ dài dùng khoảng cách thẳng | Ống mềm phải uốn nên dài hơn khoảng cách thẳng, nhưng giới hạn so với khoảng cách thẳng. | ✅ Đã sửa | Dùng hệ số 1,2: khoảng cách thẳng 2600 mm (×1,2 = 3120 mm) bị từ chối với giới hạn 3000 mm; 2400 mm (×1,2 = 2880 mm) được chấp nhận. Hệ số 1,2 do tôi chọn. | |
| BUG-32 | Đoạn dài hơn tiêu chuẩn tới 30 mm | Ngưỡng 0,1 ft (30,48 mm) làm đoạn cuối có thể dài hơn chuẩn: 2% (8/400) ống ngẫu nhiên. Ống ≤ 1,01·s cũng không bị cắt. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 01. | Gộp với BUG-33: cần chiều dài tối thiểu của Union từ Revit để chọn thuật toán chia cân bằng. |
| BUG-33 | Đoạn đuôi quá ngắn | 6% (24/400) ống ngẫu nhiên cho đoạn nhỏ hơn 100 mm (ví dụ 1151 mm thành `[1120, 31]`). | ⬜ Còn mở | Chưa sửa. Đề xuất: khi phần dư nhỏ hơn `r_min` thì chia đều hai đoạn cuối (ví dụ `[1120, 590, 590]`). | Cần dữ liệu Union thật: chiều dài tối thiểu, và `BreakCurve` có tự nối hai đoạn không. |
| BUG-34 | Báo cáo số Union sai | `cuts_made` tăng cả khi Union thất bại, nhưng báo cáo ghi "đã cắt và chèn Union". | ✅ Đã sửa | Báo cáo tách riêng số nhát cắt, số Union chèn thành công và số vị trí không chèn được. Khi Union lỗi: "chèn thành công 0, KHÔNG chèn được 3". | |
| BUG-35 | Kiểm tra đầu vào chưa đủ | Split nhập 0 gây `ZeroDivisionError`, nhập số âm thì không làm gì; Hangers nhập chữ gây `ValueError`, nhập 0 gây `ZeroDivisionError`; Routing nhập chữ gây `ValueError`. | ✅ Đã sửa | Hàm chung `ask_positive_number` cho cả 3 tool: chữ, 0, số âm, `nan`, `inf`, rỗng đều thoát gọn kèm thông báo, không sửa gì model. Chấp nhận dấu phẩy thập phân (1000,5). | |
| BUG-36 | Luôn hỏi cả hai độ dài | Chỉ chọn ống gió vẫn bị hỏi độ dài ống nước. | ✅ Đã sửa | Chỉ hỏi cho loại ống có trong vùng chọn. | |
| BUG-39 | Fallback tên tham số ghi đè nhầm | Chiều dài ty có thể bị ghi vào tham số "Height", "L" hoặc "Chieu dai ty" khi family không có "Rod Length". | ✅ Đã sửa | Chỉ ghi vào đúng tham số người dùng chỉ định; thiếu thì báo trong báo cáo. Bỏ các tên fallback "W", "D" ở tham số bề rộng. | |
| BUG-46 | Raytrace trượt thì ty bỏ trống mà không báo | Không trúng sàn/dầm thì ty giữ nguyên và báo cáo không nhắc gì. | ✅ Đã sửa | Báo cáo liệt kê riêng: giá chưa có ty vì không thấy sàn/dầm, và vì không ghi được tham số. | |
| BUG-47 | Flex ngó lơ hướng connector miệng gió | Ống mềm là đoạn thẳng từ điểm tap tới miệng gió, bỏ qua hướng connector: miệng gió lệch ngang 1500 mm thì flex rời cổ miệng gió lệch 75° so với trục thẳng đứng. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 03. | Cần hành vi thật của `FlexDuct.Create` với điểm trung gian và hướng connector. Nên làm cùng BUG-26. |
| BUG-48 | Hướng Lên/Xuống không đối chiếu vật cản | Vật cản nằm trên ống mà chọn "Xuống": ống hạ 100 mm vô ích, không né được gì. | ✅ Đã sửa | Cùng cơ chế BUG-23: ống đã nằm sẵn ở phía đó thì báo "không cần né" và gợi ý chọn hướng ngược lại. Hướng Xuống hợp lệ vẫn chạy bình thường. | |
| BUG-50 | Không kiểm tra fitting hay tap tại điểm cắt | Split cắt tại điểm tính toán, không kiểm tra có fitting/tap nằm đúng vị trí đó không. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 01. | Cần biết Revit phản ứng thế nào khi `BreakCurve` trúng fitting hoặc tap (ném lỗi, hay cắt sai). |
| BUG-52 | Điểm tâm vùng né trượt và `L_gap` co lại khi ống dốc | Phát hiện khi sửa BUG-17, là lỗi có sẵn trong code cũ: `pt_clash` là hình chiếu 3D của tâm dầm nên trượt dọc ống khi tâm dầm lệch cao so với ống (dốc 30°, lệch 1000 mm là 500 mm); `L_gap` theo extent 3D thiếu độ phủ khi dốc lớn (dốc 40°, dầm 300 mm: phủ chỉ 252 mm < 300 mm). | ✅ Đã sửa | Tính trên mặt bằng: `pt_clash` nằm đúng dưới tâm hộp theo mặt bằng, `L_gap` đo dọc ống từ `E_h`. Mutation test cố ý đưa lại từng lỗi: bắt được 300/300 và 233/300 ca ngẫu nhiên. | |
| BUG-37 | `LookupParameter` phụ thuộc ngôn ngữ | Tên "Diameter/Width/Height/Outside Diameter" sẽ lỗi trên Revit không phải tiếng Anh. | ✅ Đã sửa | `read_length_param` thử `BuiltInParameter` trước rồi mới tên hiển thị; `get_section_size` ưu tiên đường kính ngoài của ống nước. Các tên `BuiltInParameter` (ví dụ `RBS_PIPE_OUTER_DIAMETER`, `RBS_REFERENCE_INSULATION_THICKNESS`) chưa xác nhận trên Revit thật; nếu thiếu thì rơi về tên hiển thị. | |
| BUG-38 | `ElementId.IntegerValue` bị deprecated | Auto Routing dòng 97 dùng `.IntegerValue`, bị loại bỏ ở các bản Revit mới. | ✅ Đã sửa | Hàm `id_value` dùng `.Value`, nếu không có thì dùng `.IntegerValue`. Kiểm tra cả hai kiểu ElementId. | |
| BUG-40 | `except:` trần nuốt lỗi | Auto Hangers dòng 36, 185 và Clash Avoid dòng 108 bắt mọi thứ kể cả `KeyboardInterrupt`. | ✅ Đã sửa | Loại bỏ; chỗ còn lại bắt `Exception` cụ thể và `print` lý do. | |
| BUG-41 | Code lặp giữa các tool | `mm_to_ft` có ở cả 4 file; `get_connector_closest_to` ở 2 file. | ✅ Đã sửa | Tách `MEP_Tools.extension/lib/mep_common.py` dùng chung (đọc tham số, nhập liệu, connector, hình học). Phải chép cả thư mục `lib/` khi cài (README đã ghi). | |
| BUG-42 | Docstring lạc hậu và biến chết | Docstring Clash Avoid còn nói "Nhập chiều cao cần nâng và bề rộng vùng né" trong khi code đã tự tính; `uidoc`, `math` thừa. | ✅ Đã sửa | Cập nhật docstring; xóa biến và import thừa. `pyflakes` sạch trên cả 5 file. | |
| BUG-43 | Giá trị cứng và thiếu kiểm tra phần tử khóa | Các hằng số 50, 100, 150 mm, 45°, 0,1 ft nằm rải rác; Pin, Group, workset không được xử lý. | ◐ Sửa một phần | Hằng số của Split, Hangers, Routing đã gom lên đầu file với tên rõ nghĩa (nhãn `[FIX_CỨNG]`). Ống bị Pin được bỏ qua và báo cáo ở Split, bị từ chối ở Clash Avoid. | Chưa làm: hằng số trong Clash Avoid vẫn rải rác; chưa xử lý Group và workset bị người khác mượn (cần môi trường có worksharing để kiểm chứng). |
| BUG-44 | README nói quá so với code | Các khẳng định sai: "O(1)", "bảo toàn 100% ID" (chỉ đúng đoạn đầu), "1 giá khi ống ngắn" (từng sai), "Dot Product kiểm duyệt biên", "kế thừa 100% dữ liệu BIM". | ✅ Đã sửa | Viết lại `README.md` và `Specs/01` đến `04` cho khớp code; thêm mục "Giới hạn đã biết" và dòng cảnh báo chưa kiểm chứng trên Revit thật. | |
| BUG-45 | Thiếu `bundle.yaml` và icon | Tool vẫn nạp được nhưng không có icon và tooltip chuẩn. | ⬜ Còn mở | Chưa làm. | Cần icon (file ảnh) do bạn cung cấp hoặc chỉ định kiểu icon. Không phụ thuộc Revit. |
| BUG-49 | Chọn ống chính chỉ theo khoảng cách tâm | Auto Routing chọn ống có tâm gần nhất, không xét kích thước hay hệ thống: ống nhỏ cách 400 mm được chọn thay vì ống lớn cách 700 mm. | ⬜ Còn mở | Chưa sửa. Đã ghi vào Spec 03. | Là quyết định thiết kế: bạn cần chọn tiêu chí ưu tiên (kích thước ống, cùng hệ thống, khoảng cách bề mặt...). |
| BUG-51 | Thư mục `Scripts/` còn bản cũ | `Scripts/` vẫn chứa phiên bản có bug P0 và các cụm đã sửa, dễ nạp nhầm. | ◐ Sửa một phần | Thêm `Scripts/DEPRECATED.md` nêu rõ các file lỗi thời và nguồn chính thức là `MEP_Tools.extension/`. Chưa xóa file nào. Thư mục `Scripts/` **không được đưa vào repo git này** (bản gốc vẫn nằm ở thư mục làm việc). | Dự án chưa nằm trong git nên xóa là không hoàn tác được; chờ bạn quyết định xóa hay giữ. |

## Việc cần làm trên Revit thật

Đây là các thí nghiệm ngắn sẽ gỡ block cho phần lớn bug còn mở.

| Cần xác nhận | Gỡ block cho |
|---|---|
| Chiều dài tay elbow 45° tối thiểu ở mỗi phía; bán kính cong thực của elbow | BUG-19, BUG-21 |
| `BreakCurve` có nối hai đoạn không; `NewUnionFitting` cần khoảng hở bao nhiêu và Union tối thiểu mấy mm | BUG-32, BUG-33 |
| `CopyElements` có mang theo Insulation, Lining và các phần tử phụ thuộc không | BUG-25 |
| Chiều dài fitting thật nằm giữa hai đoạn ống | BUG-11 |
| `ReferenceIntersector` có thấy sàn trong Link không; view phối cảnh có dùng được không | BUG-13 |
| Hành vi `FlexDuct.Create` (kích thước, điểm trung gian, hướng connector) | BUG-26, BUG-47 |
| `BreakCurve` khi điểm cắt trùng fitting hoặc tap | BUG-50 |
| `SelectFromList.show` trả về gì với `TemplateListItem`; tên các `BuiltInParameter` đã dùng có tồn tại | BUG-05, BUG-37 |

## Việc bạn cần xác nhận lại

Ba nhóm: **A** là quyết định cần bạn đưa ra, **B** là hành vi đã đổi có chủ ý cần bạn đồng ý, **C** là kịch bản thử nhanh trên Revit thật. Cột cuối để trống cho bạn điền.

### A. Quyết định cần bạn trả lời

| # | Việc cần xác nhận | Vì sao cần / bug liên quan | Mặc định hiện tại hoặc đề xuất | Câu trả lời của bạn |
|---|---|---|---|---|
| A1 | Phiên bản Revit mục tiêu (2023, 2024, 2025 hay 2026) và engine pyRevit (IronPython 2.7 hay CPython 3)? | Quyết định tên API và `BuiltInParameter` dùng được. BUG-38 và BUG-37. | Code viết tương thích cả hai (không dùng f-string; `id_value` hỗ trợ cả `.Value` lẫn `.IntegerValue`). | |
| A2 | Ngưỡng coi là ống đứng: dốc trên 60° có đúng không? | Clash Avoid từ chối ống dốc trên 60°, Auto Hangers bỏ qua ống dốc trên 60°. BUG-14, BUG-18. | Giữ 60°. Đổi nếu bạn có ống riser dốc 45° đến 60° cần xử lý. | |
| A3 | Khe hở an toàn của Clash Avoid: 50 mm theo chiều đứng, 100 mm theo chiều ngang (50 mm mỗi bên), nâng tối thiểu 100 mm. Có theo chuẩn công ty không? | BUG-16, BUG-19, BUG-23. | Giữ 50, 100, 100 mm. Khe hở 50 mm có thể bị cua elbow ăn mất một phần (xem BUG-19). | |
| A4 | Auto Routing: điểm tap cách đầu ống tối thiểu 200 mm, hệ số uốn ống mềm 1,2 có hợp lý không? | BUG-29, BUG-31. Cả hai là số tôi chọn, chưa có chuẩn nào. | Giữ 200 mm và 1,2. | |
| A5 | Auto Hangers: khoảng cách rải là **nhịp tối đa không được vượt** hay chỉ là khoảng cách mong muốn? | BUG-10. Hiện hiểu là tối đa: nếu không còn dư nhịp để dịch né phụ kiện thì giá **giữ nguyên chỗ sát phụ kiện** và được báo cáo. | Giữ cách hiểu "tối đa". Nếu bạn cho phép vượt nhịp để né phụ kiện, cần đổi logic. | |
| A6 | Auto Hangers: vùng "sát phụ kiện" ±150 mm, bước dịch 150 mm, bán kính nhận ra "đã có giá" 100 mm có hợp lý không? | BUG-10, BUG-15. Số do tôi chọn. | Giữ 150, 150, 100 mm. | |
| A7 | Split: bạn chấp nhận đoạn cuối ngắn (dưới 100 mm) hoặc dài hơn chuẩn tới 30 mm không? Nếu không, chiều dài tối thiểu `r_min` của đoạn cuối là bao nhiêu và có cho phép chia cân bằng hai đoạn cuối (ví dụ 1120, 590, 590, tức đoạn cuối không đúng chuẩn)? | BUG-32 và BUG-33, đang chờ quyết định này cộng dữ liệu Union từ Revit. | Chưa quyết. Đề xuất chia cân bằng với `r_min` khoảng 300 mm. | |
| A8 | Auto Routing: khi ống chính chưa thuộc hệ thống nào, tiếp tục dùng System Type mặc định kèm cảnh báo, hay từ chối? | Hiện dùng mặc định rồi cảnh báo, có thể sai hệ thống. | Giữ cảnh báo. Đổi sang từ chối nếu bạn muốn chặt hơn. | |
| A9 | BUG-49: tiêu chí chọn ống chính khi có nhiều ống gần miệng gió? | Hiện chọn theo khoảng cách tâm, không xét kích thước hay hệ thống. | Cần bạn chọn: kích thước lớn nhất, cùng hệ thống, hay khoảng cách bề mặt. | |
| A10 | BUG-51: xóa hay giữ thư mục `Scripts/`? | Chứa bản cũ còn bug. Xóa không hoàn tác được vì dự án chưa có git. | Giữ cùng `DEPRECATED.md`. | |
| A11 | Có muốn đưa dự án vào git không? | Hiện không có git nên mọi chỉnh sửa và xóa đều không hoàn tác được. | Nên khởi tạo git trước các thay đổi tiếp theo. | |
| A12 | BUG-45: icon cho 4 nút, bạn sẽ cung cấp hay muốn tôi tạo icon đơn giản? | Chưa có icon và `bundle.yaml`. | Chờ bạn. | |
| A13 | BUG-43: có cần xử lý Group và workset bị người khác mượn không? | Cần môi trường có worksharing để kiểm chứng. | Chưa làm; chỉ xử lý Pin. | |
| A14 | Chiều dài chuẩn mặc định 1120 mm (ống gió) và 6000 mm (ống nước), nhịp giá đỡ mặc định 2000 mm có đúng chuẩn công ty không? | Các số này nằm sẵn trong form nhập, không phải do tôi thêm. | Giữ nguyên. | |

### B. Hành vi đã đổi có chủ ý, cần bạn đồng ý

| # | Hành vi mới | Trước đây | Bug liên quan | Đồng ý? |
|---|---|---|---|---|
| B1 | Clash Avoid **hoàn tác toàn bộ** nếu bất kỳ elbow nào không tạo được, rồi báo lý do. | Vẫn commit ống bị hở và báo "thành công". | BUG-22 | |
| B2 | Clash Avoid **từ chối** khi không đọc được kích thước ống. | Đoán chiều cao 150 mm. | BUG-24 | |
| B3 | Clash Avoid báo "không cần né" thay vì ép nâng hoặc hạ 100 mm khi không có va chạm theo hướng đã chọn. | Luôn nâng hoặc hạ ít nhất 100 mm. | BUG-23, BUG-48 | |
| B4 | Clash Avoid từ chối khi vật cản **không nằm trên đường đi** của ống. | Vẫn tạo hệ ống né cho vật cản cách xa 50 m. | BUG-20 | |
| B5 | Vùng né của Clash Avoid nay **sát vật cản** (dầm hẹp 300 mm cho vùng né chỉ ~1200 mm, đoạn giữa ~400 mm). | Vùng né lớn quá mức (dầm cắt ngang cho 6907 mm). | BUG-16 | |
| B6 | Auto Hangers đặt giá tại `(i + 0.5)·L/k`, **vị trí giá thay đổi** (ví dụ ống 3000 mm: trước 1000 và 2000, nay 750 và 2250). Ống ngắn hơn nhịp có 1 giá ở giữa. | Margin cố định `spacing/2`, ống ngắn không có giá. | BUG-07, 08, 09 | |
| B7 | Auto Hangers chỉ ghi vào **đúng tham số ty bạn nhập**, và báo giá nào chưa có ty. | Đoán nhiều tên khác như "Height", "L". | BUG-39, BUG-46 | |
| B8 | Auto Hangers và Auto Routing **quét toàn model**, không giới hạn theo view. | Chỉ quét phần tử hiển thị trong view hiện hành. | BUG-30 | |
| B9 | Auto Routing xử lý từng miệng gió độc lập (SubTransaction), lỗi thì hoàn tác riêng miệng gió đó. | Lỗi giữa chừng để lại ống mềm dở dang. | BUG-27 | |
| B10 | Auto Routing chỉ dùng connector gió và **kéo điểm tap vào trong** (cách đầu ống tối thiểu 200 mm). | Lấy connector đầu tiên bất kể loại; tap có thể ngay đầu ống. | BUG-28, BUG-29 | |
| B11 | Split báo cáo "không chèn được Union" cả khi connector đã được Revit nối sẵn, nên số này có thể bao gồm trường hợp không cần Union. | Gộp chung "cắt và chèn Union". | BUG-34 | |
| B12 | Mọi tool từ chối độ dài nhập là chữ, 0, số âm, `nan`, `inf` hoặc rỗng, và chấp nhận dấu phẩy thập phân (1000,5). | Crash hoặc im lặng bỏ qua. | BUG-35 | |
| B13 | Tool phụ thuộc `lib/mep_common.py`: phải chép cả thư mục `lib/` khi cài. | Mỗi script chạy độc lập. | BUG-41 | |

### C. Kịch bản thử nhanh trên Revit thật

Mỗi kịch bản cho biết bạn cần quan sát gì. Ghi kết quả vào cột cuối (hoặc chụp màn hình rồi gửi lại cho tôi). Hãy chạy trên **bản sao** của model, và nhớ thử Ctrl+Z sau mỗi lần chạy để chắc mỗi tool hoàn tác được trong 1 bước.

**Auto Hangers** (mở 3D View; có ống gió, ống nước, sàn trong cùng file; family giá đỡ có tham số instance `Rod Length`)

| # | Thao tác | Kết quả mong đợi | Liên quan | Kết quả thực tế |
|---|---|---|---|---|
| H1 | Chạy tool, xem hộp chọn Family giá đỡ. | Danh sách hiện đủ và chọn xong không báo lỗi. | BUG-05 | |
| H2 | Chọn ống gió dài 1,12 m, spacing 2000 mm. | Đúng 1 giá ở chính giữa ống. | BUG-07, 08 | |
| H3 | Chọn ống dài 6 m, spacing 2000 mm. | Ba giá tại 1000, 3000, 5000 mm; mọi nhịp không quá 2000 mm. | BUG-09 | |
| H4 | Ống gió chữ nhật 800×300 có sàn phía trên. Đo tay chiều dài ty. | Ty bằng khoảng cách tới sàn trừ 150 mm (nửa chiều cao). | BUG-12, 37 | |
| H5 | Ống nước có cách nhiệt, đo ty. | Ty đã trừ cả bề dày cách nhiệt. | BUG-12, 37 | |
| H6 | Sàn nằm trong **file Link** (không nằm cùng file). | Báo "chưa có ty (không tìm thấy sàn/dầm)". Xác nhận đây là giới hạn thật. | BUG-13 | |
| H7 | Chạy lại tool lần 2 trên cùng ống. | Không có giá mới, báo "đã có giá đỡ". | BUG-15 | |
| H8 | Family không có tham số tên `Rod Length`. | Báo "không ghi được tham số", các tham số khác của family không bị đổi. | BUG-39 | |
| H9 | Ống đứng, và ống có fitting nằm sát vị trí giá. | Ống đứng bị bỏ qua và báo cáo; giá né fitting hoặc báo "còn sát phụ kiện". | BUG-10, 14 | |
| H10 | Model lớn (nhiều nghìn phần tử), chọn khoảng 50 ống. | Tool vẫn chạy trong thời gian chấp nhận được (ghi lại số giây). | BUG-30 | |

**Auto Routing** (mặt bằng trần có ống gió cứng và miệng gió; có Flex Duct type trong dự án)

| # | Thao tác | Kết quả mong đợi | Liên quan | Kết quả thực tế |
|---|---|---|---|---|
| R1 | Miệng gió cách ống chính khoảng 400 mm, chạy tool. | Có ống mềm và cổ trích (Takeoff); đầu ống mềm khớp connector miệng gió. | BUG-27 | |
| R2 | Xem kích thước ống mềm so với connector miệng gió. | Ghi lại có khớp không (BUG-26 chưa sửa). | BUG-26 | |
| R3 | Miệng gió gần đầu ống chính (cách đầu dưới 200 mm). | Điểm tap cách đầu ống ít nhất 200 mm. | BUG-29 | |
| R4 | Miệng gió quá xa (vượt giới hạn chiều dài). | Báo lý do cho miệng gió đó, không để lại ống mềm nào. | BUG-27, 31 | |
| R5 | Ống chính chưa thuộc hệ thống nào. | Có cảnh báo dùng System Type mặc định. | BUG-27 | |
| R6 | Miệng gió lệch ngang khoảng 1,5 m so với ống chính. | Ghi lại ống mềm có gập góc xấu ở cổ miệng gió không (BUG-47 chưa sửa). | BUG-47 | |
| R7 | Miệng gió có cả connector điện và connector gió. | Ống mềm nối vào connector **gió**. | BUG-28 | |
| R8 | Nhiều miệng gió, trong đó cố ý có 1 miệng gió lỗi. | Các miệng gió còn lại vẫn nối thành công; báo cáo nêu lý do miệng gió lỗi. | BUG-27 | |

**Clash Avoid** (ống gió và dầm trong cùng file)

| # | Thao tác | Kết quả mong đợi | Liên quan | Kết quả thực tế |
|---|---|---|---|---|
| C1 | Dầm ngang cắt ống gió ngang, chọn "Lên". | Cắt thành 5 đoạn với 4 elbow 45°; đoạn giữa nằm trên đỉnh dầm cộng 50 mm cộng nửa chiều cao ống. | BUG-16, 17 | |
| C2 | **Dầm hẹp** (khoảng 300 mm), vùng né rất sát vật cản. | Ghi lại elbow có tạo được không. Nếu không, tool phải **hoàn tác toàn bộ** và báo lý do. | BUG-19, 21, 22 | |
| C3 | Ống dốc nhẹ (khoảng 5%). | Cả 4 elbow đúng 45° so với phương ống. | BUG-17 | |
| C4 | Ống có cách nhiệt, xem sau khi chạy. | Ghi lại cách nhiệt có được copy sang các đoạn mới không. | BUG-25 | |
| C5 | Kiểm tra khe hở thực tế giữa ống và mép dầm sau khi chạy (ống lớn hoặc nhỏ). | Ghi lại khe hở đo được (mong đợi 50 mm, có thể ít hơn do cua elbow). | BUG-19 | |
| C6 | Chọn hướng ngược (vật cản thấp hơn ống mà chọn "Lên"). | Báo "không cần né", model không đổi. | BUG-23, 48 | |
| C7 | Chọn vật cản cách xa ống, ống đứng, ống bị Pin, ống không đọc được kích thước. | Mỗi trường hợp bị từ chối bằng thông báo rõ, model không đổi. | BUG-18, 20, 24, 43 | |

**Split Ducts/Pipes**

| # | Thao tác | Kết quả mong đợi | Liên quan | Kết quả thực tế |
|---|---|---|---|---|
| S1 | Ống gió 20 m, chia 1120 mm. | Đoạn đầu giữ ElementId gốc. Ghi lại số nhát cắt và số Union chèn được. | BUG-34 | |
| S2 | Ống có phần dư rất ngắn (ví dụ 3400 mm cho đoạn cuối 40 mm). | Ghi lại Union có lắp được vào đoạn ngắn đó không. | BUG-33 | |
| S3 | `BreakCurve` có tự nối hai đoạn mới không (xem connector `IsConnected` sau khi cắt). | Ghi lại để biết số "không chèn được Union" có chứa trường hợp đã nối sẵn không. | BUG-34 | |
| S4 | Ống có tap hoặc fitting nằm đúng vị trí cắt. | Ghi lại Revit phản ứng thế nào (ném lỗi, hay cắt sai). | BUG-50 | |
| S5 | Ống bị Pin; nhập chữ hoặc 0 vào ô độ dài. | Ống Pin được bỏ qua và báo cáo; nhập sai thì thoát gọn. | BUG-35, 43 | |
| S6 | Ống gió có cách nhiệt, xem sau khi cắt. | Ghi lại cách nhiệt có theo các đoạn mới không. | BUG-25 | |

## Cách chạy lại bộ kiểm tra

Chỉ cần Python 3, chạy từ bất kỳ thư mục nào (chi tiết trong `tests/README.md`):

```
python tests/test_p0.py       # 4 kiểm tra: crash P0
python tests/test_fixes.py    # 25 kiểm tra: Hangers và Clash cụm 1
python tests/test_batch.py    # 82 kiểm tra: toàn bộ đợt sửa 2
```

Kết quả tại thời điểm tạo repo: 111 kiểm tra đều qua, `pyflakes` sạch. Mô hình Revit giả (`tests/fakerevit.py`) là mô hình do người viết dựng, nên đây là bằng chứng về logic của code, không phải bằng chứng về hành vi của Revit.
