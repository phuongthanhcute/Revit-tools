# Câu hỏi cần kỹ sư Cơ điện xác nhận

Nguồn đối chiếu: `Docs_tieu_chuan/` (DUCT-WORK R0 2025/08, HD triển khai bản vẽ SHOP SME-SDG-01).
Cột "Trả lời" để trống cho kỹ sư điền; sau đó gửi lại để chỉnh code.

## A. Clash Avoid (bẻ ống né vật cản)

**1. Góc bẻ.** DW-01.04 cho Z loại 1 γ ≤ 15° và loại 2 γ ≤ 60°. HD 6.1.3 ghi "nên ≤ 15°". Tool đang bẻ cố định 45°.
- Khi né dầm/ống, dùng 45° có được chấp nhận không, hay bắt buộc ≤ 15°?
- Muốn cho người dùng chọn góc (15° / 30° / 45° / 60°) hay chỉ một góc cố định cho từng loại ống?

Trả lời:

**2. Ống nước.** Chuẩn chỉ nêu góc cho ống gió. Ống nước (nước lạnh, thoát nước, chữa cháy) có giới hạn góc khác không (ví dụ thoát nước chỉ dùng cút 45°)?

Trả lời:

**3. Khe hở an toàn.** Tool đang dùng 50 mm từ vật cản tới ống, nhưng con số này không có trong chuẩn. Quy ước của công ty là bao nhiêu (tính cả lớp bảo ôn)?

Trả lời:

**4. Đoạn thẳng giữa các cút.** DW-01.04 ghi ≥ 25 mm ở hai đầu Z. Giữa hai cút liên tiếp có yêu cầu đoạn thẳng tối thiểu nào khác không?

Trả lời:

## B. Auto Routing (đấu miệng gió bằng ống mềm)

**5. Chân rẽ so với cút (ống chữ nhật).** HD 6.1.3.7 ghi ≥ 8W từ phụ kiện rẽ nhánh tới điểm chuyển hướng, và ≥ 150 mm tới côn.
- Nếu ống chính ngắn hoặc sát cút không đủ 8W: bỏ qua ống đó, hay vẫn cho đặt và chỉ cảnh báo?
- 8W tính theo bề rộng ống chính hay ống nhánh?

Trả lời:

**6. Ống tròn.** HD ghi T thẳng cách điểm chuyển hướng ≥ 6D và cách T khác ≥ 6D; T thu ≥ 0.5D. Tool có nên áp dụng các khoảng này khi đặt cổ trích trên ống tròn không?

Trả lời:

**7. Hộp gió.** DW-01.04 vẽ hộp gió (H ≥ 250 mm, cổ hộp = cổ miệng gió + 10 mm), còn tool nối ống mềm thẳng vào miệng gió.
- Dự án nào cũng bắt buộc có hộp gió, hay chỉ một số loại miệng gió?
- Hộp gió có sẵn trong model hay tool phải tạo? Nếu có sẵn, ống mềm nên nối vào cổ hộp gió thay vì miệng gió?

Trả lời:

**8. Chiều dài ống mềm.** Chuẩn ghi ≤ 2 m, nhưng DW-02.03 vẽ khoảng cách treo ≤ 1500 mm và HD ghi giá đỡ ống mềm ≤ 1 m. Con số nào là chiều dài tối đa của ống mềm (2 m?) và con số nào là khoảng cách treo?

Trả lời:

**9. Kích thước và loại ống mềm.** Ống mềm lấy đường kính theo cổ miệng gió hay theo bảng thiết kế? Có loại ống mềm (có/không bảo ôn) quy định theo từng dự án không?

Trả lời:

## C. Auto Hangers (giá đỡ)

**10. Nhịp giá đỡ ống nước.** Chuẩn cho nhịp theo vật liệu và đường kính (PPR 1~2.5 m, UPVC 1~2.5 m, chữa cháy ≤ 4 m hoặc ≤ 6 m, nước ngưng 1~1.5 m, gas lạnh ≤ 1.5 m). Tool đang dùng một nhịp chung cho mọi ống.
- Muốn tool tự tra nhịp theo vật liệu và đường kính (cần biết xác định vật liệu bằng cách nào: tên Pipe Type hay tham số nào), hay giữ một nhịp do người dùng nhập và chỉ cảnh báo khi vượt chuẩn?
- Ống thép (nước lạnh, chiller, chữa cháy) chuẩn chưa nêu nhịp: lấy theo bảng nào?

Trả lời:

**11. Giá đỡ ở đầu cuối tuyến ống gió.** DW-02.02 ghi giá ở đầu cuối tuyến phải có kẹp trên đỉnh và cách điểm cuối ≤ 300 mm.
- "Đầu cuối tuyến" là đầu ống không nối tiếp gì (bịt đầu, nối vào thiết bị), hay cả chỗ nối vào cút/tê?
- Kẹp trên đỉnh có phải chi tiết riêng của family giá đỡ không?

Trả lời:

**12. Giá đỡ trùng cửa gió.** HD 6.1.3.15 ghi không đặt giá trùng vị trí cửa gió. Khoảng cách tối thiểu từ giá tới tâm cổ trích hoặc cửa gió là bao nhiêu mm?

Trả lời:

**13. Phụ kiện bề rộng ≥ 1000 mm.** Cần có giá riêng cho phụ kiện này. Bắt buộc 2 giá (hai đầu) hay chỉ 1?

Trả lời:

**14. Giá cố định cạnh dầm.** Chuẩn ghi giá cố định cho ống ngang cách ≤ 5 lần nhịp và ưu tiên cạnh dầm. Tool có cần tự chọn một số giá làm "giá cố định" không, hay việc này làm tay?

Trả lời:

**15. Ống đứng.** Tool đang bỏ qua ống dốc hơn 60°. Giá đỡ ống đứng (1.5~2 lần nhịp ngang, ưu tiên gắn sàn) có cần tool xử lý không, hay làm riêng?

Trả lời:

**16. Family giá đỡ.** Thanh đỡ nằm dưới đáy ống và ty treo nằm ngoài lớp bảo ôn (DW-02.03). Family giá đỡ chuẩn của công ty có điểm gốc ở tâm ống hay đáy ống, và tham số "chiều dài ty" tên là gì? Câu trả lời quyết định cách tool tính chiều dài ty.

Trả lời:

## D. Câu hỏi chung

**17. Thứ tự chạy tool.** Nên chạy Split → Hangers → Routing, hay thứ tự khác? Hangers nên chạy trước hay sau khi đã đấu miệng gió?

Trả lời:

**18. Ngoài phạm vi HVAC.** Có muốn mở rộng tool cho điện (ống luồn dây, thang máng cáp theo `ELECTRICAL-WORK.pdf`) không? Nếu có, ưu tiên khoảng cách giá đỡ thang máng (≤ 1.5 m ngang, ≤ 2 m đứng) hay cao độ/khoảng cách giữa các lớp?

Trả lời:
