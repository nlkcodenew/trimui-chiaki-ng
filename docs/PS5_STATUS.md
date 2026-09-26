# Trạng thái hỗ trợ PS5

## Quyết định

Phần PS5 của `trimui-chiaki-ng` đã dừng phát triển sau `v0.4.0-beta2`. Dự án
không tuyên bố hỗ trợ pair hoặc stream PS5 và không có kế hoạch phát hành thêm
bản sửa riêng cho PS5. PS4 là nền tảng duy trì chính thức.

## Lý do kỹ thuật và trải nghiệm

Theo luồng của upstream Chiaki-ng, PS5 cần đăng nhập PSN để lấy `user_id`, đổi
thành PSN Account-ID 8 byte little-endian rồi Base64 trước khi pair. Giá trị này
không phải PSN Online-ID và không thể thay thế bằng PIN Remote Play 8 số.

Chiaki-ng desktop có luồng PSN Login để hỗ trợ bước này. Trên TrimUI, việc thêm
đăng nhập PSN an toàn, nhập liệu bằng tay cầm, xử lý token/tài khoản và tiếp tục
debug giao thức/H265 tạo trải nghiệm quá phức tạp so với mục tiêu của dự án.

## Chính sách từ đây

- `v0.4.0-beta2` được giữ làm bản thử nghiệm lịch sử, không phải bản PS5 ổn định.
- Không phát triển thêm PSN Login, Account-ID, pair, H265 hoặc stream PS5.
- Issue PS5 mới có thể được giữ làm tham khảo nhưng không có cam kết xử lý.
- Không đưa Account-ID, PIN, token hoặc khóa pair lên Issue công khai.
- Các thay đổi tiếp theo tập trung vào độ ổn định và tương thích PS4.

Người dùng PS4 nên dùng bản ổn định `v0.3.20`. Quyết định đóng PS5 không thay
đổi luồng pair/session PS4 pre-10 đã được xác nhận trên máy thật.
