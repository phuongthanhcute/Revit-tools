# Specification: Chia ống theo tiêu chuẩn (Split Ducts/Pipes)

## 1. Thông tin chung
- **Độ khó:** Dễ (1/4) - Phù hợp để làm quen với Revit API trong việc can thiệp vào Location và tạo Element mới.
- **Mục tiêu:** Tự động cắt các đoạn ống gió/ống nước dài thành các đoạn ngắn có chiều dài tiêu chuẩn (VD: ống gió 1.12m, ống thép 6m) để phục vụ bóc tách khối lượng và chế tạo.

## 2. Đầu vào (Inputs)
- Người dùng chọn các đường ống (Duct/Pipe) trên mặt bằng hoặc 3D.
- Cửa sổ UI nhập thông số:
  - Chiều dài tiêu chuẩn của ống gió (Mặc định: 1120 mm).
  - Chiều dài tiêu chuẩn của ống nước/thép (Mặc định: 6000 mm).
  - Tùy chọn: Loại fitting để nối (Union) giữa các đoạn cắt.

## 3. Đầu ra (Outputs)
- Các đường ống dài nguyên bản bị chia nhỏ thành các đoạn có chiều dài bằng chiều dài tiêu chuẩn (đoạn cuối cùng có thể ngắn hơn).
- Tự động chèn khớp nối (Union/Coupling) tại các vị trí cắt để đảm bảo hệ thống vẫn kết nối (Connected).

## 4. Luồng thuật toán (Workflow)
1. **Lọc đối tượng:** Lấy danh sách các Pipe/Duct từ lựa chọn của người dùng (`uidoc.Selection`).
2. **Kiểm tra chiều dài:** Nếu chiều dài hiện tại `<` chiều dài tiêu chuẩn -> Bỏ qua.
3. **Tính toán điểm cắt:** 
   - Lấy đường curve của ống (`LocationCurve`).
   - Dùng vòng lặp để tìm các điểm chia dọc theo curve dựa trên chiều dài tiêu chuẩn.
4. **Thực thi (Transaction):**
   - Rút ngắn ống hiện tại hoặc sử dụng chia Element.
   - Tạo các ống mới sao chép thuộc tính của ống cũ dọc theo các đoạn đã chia.
   - Chèn Union (Măng xông) bằng cách nối 2 connector tại điểm cắt sử dụng `doc.Create.NewUnionFitting()`.
5. Báo cáo kết quả: Hiển thị thông báo số lượng ống đã cắt.

## 5. Các Class/Method Revit API chính
- `Autodesk.Revit.DB.Plumbing.Pipe` / `Autodesk.Revit.DB.Mechanical.Duct`
- `Element.Location` -> `LocationCurve` -> `Curve`
- `PlumbingUtils.BreakCurve()` / `MechanicalUtils.BreakCurve()`
- `doc.Create.NewUnionFitting()`

## 6. Các trường hợp ngoại lệ cần lưu ý (Edge Cases)
- Ống có chứa các phụ kiện bọc (Insulation, Lining) -> Cần đảm bảo ống mới được tạo ra cũng kế thừa lớp bọc.
- Ống bị dốc (Sloped Pipe) -> Vẫn phải giữ nguyên độ dốc (Slope) ban đầu.
- Đoạn ống cuối cùng quá ngắn (nhỏ hơn khoảng hở của Union) -> Cần bỏ qua, không cắt điểm cuối nếu không đủ khoảng trống cho Fitting.

## 7. Trạng thái hiện tại và giới hạn đã biết (v2.0)
- Chỉ hỏi chiều dài cho loại ống có trong vùng chọn; nhập chữ, 0, số âm, `nan`, `inf` đều thoát gọn kèm thông báo (chấp nhận dấu phẩy thập phân).
- Ống bị Pin được bỏ qua và báo cáo.
- Báo cáo tách **số nhát cắt** và **số Union chèn thành công / không chèn được** (trước đây gộp làm một).
- Cắt từ đuôi về đầu: đoạn **đầu** giữ ElementId gốc, các đoạn sau nhận ElementId mới.
- **Chưa xử lý (cần dữ liệu từ Revit thật):**
  - Đoạn dư ở cuối có thể rất ngắn (mô phỏng: ~6% ống ngẫu nhiên cho đoạn < 100 mm, ví dụ 1151 mm thành `[1120, 31]`), và có thể dài hơn chuẩn tới 30 mm do ngưỡng 30 mm của điểm cắt. Union có lắp vừa các đoạn ngắn đó hay không chưa kiểm chứng.
  - Chưa kiểm tra fitting/tap nằm đúng vị trí cắt.
  - Việc ống mới có kế thừa lớp bọc (Insulation, Lining) hay không chưa kiểm chứng.
