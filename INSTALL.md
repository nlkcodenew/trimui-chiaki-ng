# Cài đặt trimui-chiaki-ng v0.3.22

Hướng dẫn này dành cho bản ổn định PS4-only trên TrimUI Smart Pro S/Spruce OS
và TrimUI Brick Pro Stock OS.

## 1. Tải đúng gói

1. Mở `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/latest`.
2. Tải `trimui-chiaki-ng-v0.3.22.zip`.
3. Không tải **Source code (zip/tar.gz)** vì các gói đó không phải bộ cài.
4. Có thể kiểm SHA-256 bằng file `.zip.sha256` đi kèm release.

## 2. Cài mới

1. Giải nén ZIP vào gốc thẻ nhớ.
2. Kiểm tra đường dẫn cuối là `Apps/Chiaki/launch.sh`.
3. Tháo thẻ an toàn khỏi máy tính, lắp vào TrimUI và mở **Chiaki-ng**.
4. Lần chạy đầu tự tạo `settings.json` mặc định và ID cài đặt `CHI-xxxx`.

## 3. Cập nhật và bảo toàn pair

Để nâng cấp, giải nén/copy **đè** `Apps/Chiaki/` hoặc dùng OTA trong app. Không
xóa thư mục cũ trước khi cập nhật.

ZIP và OTA cố ý không chứa hoặc ghi đè:

- `settings.json`
- `paired_hosts.json`
- `chiaki.conf`
- `secrets.json`
- log và marker runtime

Vì vậy cài đè giữ cấu hình và khóa pair hiện có. Nên backup ba file dữ liệu đầu
tiên trước khi sửa thẻ nhớ.

Nếu đã xóa sạch `Apps/Chiaki/`, các khóa pair cũng đã bị xóa. App chỉ có thể tạo
settings mới, không thể suy ra hoặc tải lại khóa bí mật cũ; cần pair lại bằng
PIN. Đây là hành vi an toàn dự kiến, không phải lỗi discovery.

## 4. Pair PS4 lần đầu hoặc sau khi xóa sạch

1. Đặt TrimUI và PS4 trong cùng mạng LAN/Wi-Fi.
2. Trên PS4 bật **Remote Play Connection Settings → Enable Remote Play**.
3. Bật PS4 bằng tay cầm/nút nguồn và chờ vào màn hình chính.
4. Trong app chọn **QUÉT MÁY PS4**.
5. Chọn máy, bấm **Y**.
6. Trên PS4 mở **Add Device**, nhập PIN 8 số vào app và bấm **A**.

Sau PIN, PS4 tự trả `regist_key` và `rp_key`; app xác thực kích thước/định dạng
rồi tự lưu bằng file tạm + `fsync` + rename. Người dùng không cần và không được
nhập khóa thủ công.

Nếu gặp `HTTP 403 / 80108b03`, đóng **Add Device**, mở lại để lấy PIN mới rồi
thử một lần. PIN cũ không nên được gửi lại liên tục.

## 5. Kết nối

1. Bật PS4 trước khi quét; `v0.3.22` chưa hỗ trợ đánh thức Rest Mode.
2. Chọn **QUÉT MÁY PS4**.
3. Chọn PS4 đã pair và bấm **A**.
4. Khi chơi, giữ **START + SELECT** khoảng 1,2 giây để trở lại app.

Nếu phiên cũ chưa được PS4 nhả, chờ khoảng hai phút rồi kết nối lại.

## 6. Profile khuyến nghị

- Smart Pro S/Spruce: `720p30/4000`.
- Brick Pro Stock OS: `540p30/3000` hoặc `720p30/4000` nếu mạng ổn định.
- App khóa tối đa 720p; cấu hình 1080p cũ tự được chuẩn hóa về 720p.

## 7. Mã thiết bị và log

Tiêu đề app hiển thị `CHIAKI-NG v0.3.22 | HW-xxxxxxxxxxxx`. Khi cần đối chiếu
Issue chẩn đoán, cung cấp mã `HW-...`; không dùng `CHI-...` làm mã chính vì ID
cài đặt có thể đổi sau khi mất settings.

Không đăng PIN, `regist_key`, `rp_key`, PSN Account ID, IP hoặc MAC lên Issue.
Uploader tự lọc các trường nhạy cảm trước khi gửi qua HTTPS relay.

Log cục bộ:

- `Apps/Chiaki/Chiaki-debug.log`
- `Apps/Chiaki/Chiaki-loi.txt`

## 8. Gỡ lỗi nhanh

**Không tìm thấy PS4:** xác nhận PS4 đang bật ở màn hình chính, Remote Play đã
bật, và hai thiết bị cùng subnet không bị AP/client isolation.

**App không khởi động:** kiểm tra `Chiaki-loi.txt`, Python 3.10+, quyền thực thi
`launch.sh`, và thư mục `vendor/sdl2/` từ ZIP release.

**Mất pair sau cài lại:** nếu đã xóa cả thư mục, pair lại bằng PIN. Nếu chỉ cài
đè mà vẫn mất, kiểm tra xem `settings.json`/`paired_hosts.json` có bị công cụ
copy bên ngoài xóa hay filesystem exFAT bị lỗi hay không.

**Hai thư mục cùng tên hoặc file biến mất:** dừng ghi thẻ và chạy
`chkdsk <ổ>: /F` trên Windows trước khi copy lại.

## 9. Quyền riêng tư

- App không chứa GitHub token.
- TLS luôn xác minh certificate và hostname bằng CA bundle đóng gói.
- App không thay đổi cấu hình WoWLAN của hệ điều hành.
- Gói release không chứa settings, khóa pair, secrets hoặc log từ máy phát triển.
