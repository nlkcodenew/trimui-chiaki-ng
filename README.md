# trimui-chiaki-ng

Ứng dụng Remote Play PS4 qua LAN cho các máy TrimUI chạy Linux.

## Phiên bản ổn định

**Bản đang phát triển: `v0.3.25-beta1`**

Phạm vi hiện tại:

- TrimUI Smart Pro S/TG5050 và Spruce OS.
- TrimUI Brick Pro Stock OS (`sun50iw10`).
- Chế độ biến Brick Pro thành tay cầm Bluetooth Classic HID cho Android, gồm
  D-pad, hai joystick analog, L2/R2 analog và L3/R3.
- PS4 firmware 9.00/GoldHEN qua LAN, không cần đăng nhập PSN.
- H264 tối đa 720p, âm thanh Opus và input SDL GameController.
- Chỉ kết nối console đang bật và phản hồi discovery trong cùng LAN.
- Chưa hỗ trợ đánh thức PS4 từ Rest Mode trong bản ổn định.

> **PS5 không được hỗ trợ.** Các tag beta cũ chỉ được giữ để tham khảo kỹ thuật;
> không tải Source code của chúng như một gói cài đặt.

`v0.3.25-beta1` thêm mục **TAY CẦM BLUETOOTH** dành riêng cho Brick Pro Stock
OS. Backend ARM64 static được viết lại từ prototype NextUI: giữ D-pad độc lập,
truyền đủ hai joystick thật của Brick Pro, tự dò dịch vụ BlueZ stock và khôi
phục dịch vụ khi thoát. Radio và ghép nối thật vẫn cần xác nhận trực tiếp trên
Brick Pro.

`v0.3.24` thêm logo khởi động NLK kiểu Netflix (2.2 giây, bấm phím
bất kỳ để bỏ qua, tắt được trong Cài đặt) và giữ đường PS4-only ổn định
của `v0.3.23`, bao gồm giảm báo cáo giả
dương tính: phiên stream thành công chỉ tạo Issue khi mất frame từ 1%, có ít
nhất 10 lỗi FEC hoặc FPS thấp kéo dài. Kiểm tra OTA khi thiết bị chỉ đang
offline vẫn hiển thị lỗi trong app nhưng không tạo Issue; lỗi TLS và manifest
không hợp lệ vẫn được báo cáo.

## Cài đặt

1. Mở trang [Releases](https://github.com/nlkcodenew/trimui-chiaki-ng/releases/latest).
2. Với bản thử này, tải `trimui-chiaki-ng-v0.3.25-beta1.zip`, không tải gói **Source code**.
3. Giải nén vào gốc thẻ nhớ để có `Apps/Chiaki/`.
4. Tháo thẻ an toàn, lắp vào TrimUI rồi mở **Chiaki-ng**.

### Cập nhật mà không mất pair

- **Cài đè** ZIP mới lên `Apps/Chiaki/` hoặc dùng OTA trong app.
- Không xóa thư mục `Apps/Chiaki/` trước khi cập nhật.
- ZIP và OTA không chứa/ghi đè `settings.json`, `paired_hosts.json`,
  `chiaki.conf`, log hoặc secrets.
- Có thể backup ba file dữ liệu trên trước khi thao tác với thẻ nhớ.

Nếu xóa sạch thư mục `Apps/Chiaki/`, app không thể phục hồi khóa pair đã bị xóa.
Lần chạy mới sẽ tự tạo `settings.json` mặc định và một ID cài đặt mới, nhưng bạn
phải pair lại PS4 bằng PIN. Mã `HW-...` vẫn ổn định theo thiết bị nếu hệ thống
còn cung cấp cùng nguồn phần cứng.

## Pair lần đầu

1. Kết nối TrimUI và PS4 vào cùng LAN hoặc Wi-Fi 5 GHz.
2. Trên PS4, bật **Settings → Remote Play Connection Settings → Enable Remote Play**.
3. Bật PS4 và chờ vào màn hình chính; bản stable chưa đánh thức Rest Mode.
4. Trong Chiaki-ng chọn **QUÉT MÁY PS4**.
5. Chọn PS4, bấm **Y** để mở màn hình pair.
6. Trên PS4 chọn **Add Device**, nhập PIN 8 số vào Chiaki-ng rồi bấm **A**.

Người dùng chỉ nhập PIN. Khi registration thành công, PS4 tự trả về
`regist_key`, `rp_key`, loại khóa và MAC; app kiểm tra rồi tự lưu atomically vào
`settings.json` và `paired_hosts.json`. Không nhập, sao chép hoặc đăng các khóa
này lên chat/Issue.

Nếu PS4 báo `HTTP 403 / 80108b03`, thoát màn **Add Device**, mở lại để lấy PIN
mới rồi pair một lần; không tiếp tục gửi lại PIN cũ.

## Sử dụng

- Bật PS4 bằng tay cầm hoặc nút nguồn trước khi quét.
- Chọn **QUÉT MÁY PS4**, chọn máy rồi bấm **A** để stream.
- Khi đang chơi, giữ **START + SELECT** khoảng 1,2 giây để trở lại app.
- Nếu kết nối lại báo phiên đang được dùng, chờ khoảng hai phút để PS4 nhả lease.
- Profile khuyến nghị: `720p30/4000` hoặc `540p30/3000` trên Brick Pro.

Menu **HƯỚNG DẪN SỬ DỤNG** trong app có 8 bước về chuẩn bị mạng, bật PS4,
quét, pair PIN, stream, thoát an toàn, cài đè và trường hợp phải pair lại.

### Dùng Brick Pro làm tay cầm Bluetooth

1. Chọn **TAY CẦM BLUETOOTH** trong menu Chiaki-ng.
2. Chờ kiểm tra input/BlueZ, sau đó bấm **A**.
3. Trên Android, dùng profile PlayStation; trên iOS, chọn profile DualShock 4
   rồi ghép với `Wireless Controller`.
4. Thử D-pad, ABXY, L/R, L2/R2, L3/R3 và cả hai joystick.
5. Giữ **MENU** 2 giây để dừng (START + SELECT 2 giây là dự phòng). B là nút test.

Log chẩn đoán được ghi ở `Apps/Chiaki/BrickBluetooth.log`. Chế độ này yêu cầu
Stock OS có BlueZ, system D-Bus và quyền đọc `/dev/input/event*`. Profile
DualShock 4 đã được kiểm chứng trên iPhone; app không giả lập XInput/Microsoft
Xbox protocol.

## Dữ liệu và chẩn đoán

Tiêu đề app có dạng:

```text
CHIAKI-NG v0.3.25-beta1 | HW-xxxxxxxxxxxx
```

Tiêu đề Issue chẩn đoán có dạng:

```text
[device-log][HW-xxxxxxxxxxxx] v0.3.25-beta1 reason fingerprint
```

- `HW-...` là pseudonym SHA-256 ổn định từ nguồn phần cứng khả dụng; dùng mã
  này để tìm đúng Issue của thiết bị.
- `CHI-...` là ID ngẫu nhiên của lần cài/thẻ nhớ, có thể đổi khi mất settings và
  chỉ còn là dữ liệu phụ trong body.
- App lọc token, khóa pair, PSN ID, IP, MAC, serial và chip ID thô trước khi gửi.
- Phiên stream thoát bình thường không tạo Issue nếu chất lượng vẫn trong ngưỡng;
  mất mạng OTA thông thường cũng chỉ được ghi log cục bộ.
- App không sửa `/etc/wifi/wpa_supplicant.conf` hay `wowlan_triggers`.

File log cục bộ:

- `Apps/Chiaki/Chiaki-debug.log`
- `Apps/Chiaki/Chiaki-loi.txt`

Chọn **Cài đặt → XÓA LOG CŨ** để chuẩn bị một bài test sạch. Nếu app không khởi
động, kiểm tra `Chiaki-loi.txt` trước.

## An toàn thẻ nhớ

Không rút cáp hoặc tháo thẻ khi đang ghi. exFAT không có journal; nếu Windows
hiện hai thư mục cùng tên hoặc báo lỗi filesystem, dừng ghi và chạy:

```powershell
chkdsk <ổ>: /F
```

## Kiểm thử release

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

Xem hướng dẫn chi tiết trong `INSTALL.md`.
