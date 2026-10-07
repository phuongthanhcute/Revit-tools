# Các thành phần có thể tối ưu bằng cách viết script điền vào pyRevit
## Tạo giá đỡ tự động (Auto Hangers/Supports): 
Ống gió và ống nước cần có giá đỡ (ty treo) treo lên trần bê tông, khoảng cách thường là 1.5m - 2m một cái. Kỹ sư phải copy-paste từng cái giá đỡ dọc theo đường ống rất vất vả. Một thuật toán chia khoảng cách (Divide Curve) có thể rải hàng nghìn giá đỡ trong nháy mắt.

## Chia ống theo tiêu chuẩn (Split Ducts/Pipes): 
Khi vẽ, kỹ sư thường kéo một đường ống dài 20m. Nhưng thực tế sản xuất, một đoạn tôn ống gió chỉ dài 1.12m, ống thép dài 6m. Script của bạn có thể tự động "cắt khúc" đường ống dài đó ra thành các đoạn chuẩn để xuất khối lượng cho nhà máy.

## Xử lý va chạm (Clash Avoidance): 
Khi ống gió đụng phải dầm bê tông hoặc ống chữa cháy, kỹ sư phải xóa đoạn ống đó đi, vẽ 4 cái lơi (Fitting góc 45 độ) để ống lượn xuống rồi lượn lên. Thuật toán có thể nhận diện điểm giao cắt và tự động bẻ ống (tạo offset).

## Auto-Routing (Đấu nối tự động): 
Tự động vẽ các đoạn ống mềm nối từ ống gió chính vào hàng chục miệng gió trên trần thạch cao.