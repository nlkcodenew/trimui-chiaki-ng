# Cài đặt trimui-chiaki-ng trên TrimUI

Hướng dẫn này áp dụng cho `v0.4.0-beta2`, dùng chung cho TrimUI Smart Pro S/Spruce
OS và TrimUI Brick Pro Stock OS.

## Yêu cầu

- Máy TrimUI Linux có Python 3.10+.
- SDL2/SDL2_ttf, Opus và các thư viện hệ thống cần bởi native helper.
- Thẻ microSD FAT32 hoặc exFAT có quyền ghi vào `Apps/`.
- PS4/PS5 và máy TrimUI ở cùng LAN khi quét/ghép nối.

Native helper đi kèm là ELF64 AArch64. Smart Pro S/TG5050 với Spruce OS và Brick
Pro Stock OS đều đã được xác nhận stream PS4 thật có hình, âm thanh và input.

## Cài GitHub Release

1. Mở `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/tag/v0.4.0-beta2`.
2. Tải `trimui-chiaki-ng-v0.4.0-beta2.zip`. Không tải **Source code**.
3. Tháo thẻ an toàn khỏi máy, cắm vào PC và giải nén ZIP vào gốc thẻ.
4. Không tạo thêm lớp thư mục tên ZIP. Cấu trúc đúng:

   ```text
   Apps/Chiaki/
     app.py
     config.json
     launch.sh
     settings.json
     assets/
     bin/chiaki-stream
     certs/cacert.pem
     libs/brick-stock/
     rh/
     vendor/sdl2/
   ```

5. Eject thẻ an toàn, lắp lại và mở **Apps → Chiaki-ng**.

Nếu đang dùng bản rất cũ thiếu `vendor/sdl2`, nên xóa thư mục `Apps/Chiaki/` cũ
trước khi giải nén. Không xóa `settings.json`, `paired_hosts.json` hoặc
`secrets.json` của bản đang hoạt động nếu muốn giữ cấu hình, khóa ghép nối và
cấu hình developer cũ; hãy backup chúng trước khi cài sạch.

## Trường hợp Brick Pro trước v0.3.11

Nếu log có `CERTIFICATE_VERIFY_FAILED` và app cũ hơn `v0.3.11`, phải cài ZIP
`v0.3.11` hoặc mới hơn bằng tay một lần. Updater cũ phụ thuộc CA hệ thống của
Stock OS nên không thể tải chính bản vá CA.

## Runtime Brick Pro Stock OS

Issue `#36` và `#37` ở `v0.3.14` xác nhận registration/pair thành công, nhưng
native helper thoát `127` vì Stock OS không có `libjson-c.so.5`. `v0.3.15` thêm
dependency closure AArch64 tại `Apps/Chiaki/libs/brick-stock/` và chỉ thêm nó
làm fallback sau library Stock OS khi model là `sun50iw10`.

Smart Pro S/Spruce model `sun55iw3` không dùng bundle này và tiếp tục chạy với
library hệ thống đã được xác nhận. Brick `sun50iw10` và Spruce đều đã stream
thành công bằng cùng native binary, nên hiện không cần tách ZIP theo OS.

Issue `#38` cho thấy `v0.3.15` đã tìm được dependency closure, nhưng loader ưu
tiên `/usr/lib/libssl.so.1.1` và `/usr/lib/libcrypto.so.1.1` quá cũ, không export
`OPENSSL_1_1_1`. `v0.3.16` preload đúng hai file OpenSSL 1.1.1 đóng gói chỉ cho
native stream trên Brick. SDL/FFmpeg vẫn ưu tiên Stock OS; Spruce không preload.
Issue `#39` xác nhận bản sửa hoạt động: stream kết thúc `exit=0`, `8968` frame,
không mất frame và không có FEC failure.

Từ `v0.3.11`, app dùng thêm `certs/cacert.pem` nhưng vẫn giữ
`ssl.CERT_REQUIRED` và hostname verification. Không xóa CA bundle và không sửa
mã để dùng `CERT_NONE` hoặc unverified context.

## Cập nhật OTA

Mỗi lần vào màn hình chính, app kiểm tra manifest của GitHub Release mới nhất và
các URL dự phòng. Khi có version mới:

- **CÀI NGAY**: tải các file thay đổi, kiểm SHA-256, cài và restart.
- **ĐỂ SAU**: đóng popup; lần mở sau app hỏi lại.
- **BỎ QUA**: lưu version vào `skipped_versions`.

Từ `v0.3.14`, lỗi DNS/TLS/mạng của một nguồn không phải lỗi kết thúc nếu fallback
thành công. Trường hợp đó chỉ ghi `INFO`, không gửi Issue. Chỉ khi mọi nguồn đều
thất bại app mới ghi `WARNING`, hiển thị lỗi kiểm tra cập nhật và tạo report.

Updater không ghi đè `settings.json`, `secrets.json`, log hoặc marker runtime.
File tải về được ghi vào staging, kiểm hash, `fsync` và thay atomically;
`rh/version.py` được thay cuối. Không rút cáp hoặc tháo thẻ trong quá trình này.

## Ghép nối và stream PS4

Có thể chọn **Hướng dẫn sử dụng** trong menu chính để xem 8 bước ngay trên máy.
Tiêu đề chính hiển thị `ID: CHI-xxxx`; hãy gửi mã này khi cần tìm đúng Issue/log.

Luồng PS4 Pro firmware 9.00/GoldHEN đã được xác nhận trên Smart Pro S:

1. Bật PS4 bằng nút nguồn hoặc tay cầm và chờ auto-login.
2. Dùng LAN hoặc Wi-Fi 5 GHz; tắt Bluetooth nếu cần giảm nhiễu.
3. Mở app và quét. App chỉ hiện console đang phản hồi.
4. Nếu chưa có khóa pre-10, chọn console, bấm **Y**, mở màn hình PIN Remote Play
   trên PS4 và nhập đủ 8 số.
5. Quét lại, chọn console đã ghép và bấm **A**.
6. Giữ **START + SELECT** khoảng 1,2 giây để dừng stream và quay lại app.

Không cần PSN cho PS4 firmware 9.00 trong luồng này. Không đăng PIN, Account ID,
`regist_key` hoặc `rp_key` lên chat/Issue.

## Ghép nối thử nghiệm PS5

App chỉ hiện bước PSN Account-ID sau khi discovery nhận diện host là PS5; PS4
không đi qua bước này. Nhập chuỗi Base64 12 ký tự lấy từ **PSN Login** của
Chiaki-ng desktop chính chủ. Đây là `user_id` PSN được đổi thành 8 byte
little-endian rồi Base64, không phải PSN Online-ID hoặc PIN Remote Play. App tự
kiểm tra và lưu vào `settings.json`, không cần sửa file bằng tay.

Sau khi lưu Account-ID, app mới hiện bước nhập PIN Remote Play 8 số. Nếu pair
thất bại, chụp mã `PS5-*` và `CHI-*` ở màn PIN để gửi hỗ trợ; không chụp màn
Account-ID và không đăng Account-ID/PIN/khóa pair lên Issue.

Profile khuyến nghị:

- Baseline: `720p`, `30 FPS`, `4000 kbps`.
- Fallback: `540p`, `30 FPS`, `4000 kbps`.
- Từ `v0.3.17` khóa tối đa 720p; cấu hình 1080p cũ tự chạy ở 720p.
- Không ưu tiên `15000 kbps` hoặc 60 FPS trên các màn hình này.

Nếu PS4 báo Remote Play đang được dùng sau một lần thoát/kết nối lỗi, chờ khoảng
hai phút để console nhả lease rồi thử lại; không bấm kết nối liên tục.

## Tự gửi lỗi lên GitHub

Bản phát hành cho người thử không cần và không được chứa GitHub token. App gửi
log đã lọc tới HTTPS relay trong `reporting.json`; token chỉ nằm trong server
secret của relay và chỉ có quyền tạo Issue ở repo chẩn đoán private.

Người đóng gói app triển khai theo `deploy/issue-relay/README.md`, điền endpoint
`/report` trước khi build và đặt rate-limit phía Cloudflare. Người thử chỉ cần
Diagnostics tự động bật trong bản beta, không cần người dùng nhớ bật và không cần copy
`secrets.json`. App chỉ gửi log đã lọc tới relay HTTPS; OTA cũng bật chế độ này cho
các bản cài cũ để các lỗi thực tế được tạo thành GitHub Issue.

App và relay cùng lọc token, password, khóa ghép nối, PSN ID, IP nội bộ, MAC,
serial và chip ID trước khi gửi. Endpoint công khai vẫn cần giám sát abuse;
không dùng shared secret nhúng trong app vì người nhận có thể trích xuất nó.

Từ `v0.3.13`, report có:

- Model thiết bị, ví dụ `sun50iw10`.
- ID cài đặt/thẻ `CHI-xxxx`.
- ID phần cứng băm `HW-xxxxxxxxxxxx`.
- Version, loại lỗi, fingerprint và phần cuối log đã lọc.

ID `RH-xxxx` của RetroHub không phải serial phần cứng. Nếu không đọc được nguồn
phần cứng, app dùng fallback `APP-...` dựa trên ID cài đặt thay vì gửi raw ID.

Các lỗi được báo gồm thất bại OTA cuối cùng, lỗi lưu settings, socket discovery,
pair, chuẩn bị stream và crash. App không báo quét `0 host`, thao tác hủy, thoát
bình thường hoặc một nguồn OTA lỗi nhưng fallback thành công.

## Log cục bộ

Các file chính trong `Apps/Chiaki/`:

- `Chiaki-debug.log`: log đầy đủ, xoay vòng và giữ tail.
- `Chiaki-loi.txt`: stderr/cảnh báo/lỗi quan trọng.
- `.pending_crash`: các loại lỗi chưa gửi được.
- `.log_upload_state.json`: fingerprint và URL Issue gần nhất.

Để bắt đầu bài test sạch, chọn **Cài đặt → XÓA LOG CŨ → A → Có**. App từ chối
xóa nếu còn report pending. Khi chọn **THOÁT**, launcher thử gửi pending trước
khi đóng.

Một dòng chất lượng native có dạng:

```text
[native] quality: rendered=150 lost=0 fec=0 fps=30.0 suppressed=0 totals=...
```

- `fps` gần mức đặt và `fec/lost=0`: decode/render đang theo kịp.
- `fec` hoặc `lost` tăng: giảm bitrate, ưu tiên 5 GHz và tắt Bluetooth.
- `native stream preflight`: liệt kê thư viện hoặc điều kiện thiếu trước stream.
- `native runtime: brick-stock`: Brick đã chọn bundle riêng; Spruce phải ghi
  `native runtime: system`.
- `native OpenSSL: bundled 1.1.1`: Brick đã chọn đúng OpenSSL tương thích.

## An toàn thẻ nhớ

Không rút dây USB hoặc tháo thẻ khi máy/PC đang đọc ghi. exFAT không có journal;
ngắt giữa lúc I/O có thể tạo hai directory entry cùng tên. Nếu xảy ra:

1. Dừng mọi thao tác ghi.
2. Chạy `chkdsk <ổ>: /F` trên Windows.
3. Chỉ xóa/copy lại thư mục sau khi filesystem đã được sửa.

Updater dùng `fsync` để giảm rủi ro nhưng không thể chống việc ngắt vật lý khi
đang ghi.

## Gỡ lỗi nhanh

**Không thấy bản cập nhật:** kiểm tra `Chiaki-debug.log`. Một dòng
`source unavailable; trying fallback` ở mức INFO không phải lỗi nếu sau đó có
`OTA manifest ready`. Chỉ dòng `OTA manifest unavailable after ...` mới là thất
bại cuối cùng.

**`ModuleNotFoundError: No module named 'sdl2'`:** cài ZIP Release đầy đủ, không
dùng Source code và đảm bảo `Apps/Chiaki/vendor/sdl2/` tồn tại.

**`ImportError: PySDL2 not loaded`:** firmware thiếu hoặc không tìm thấy
`libSDL2.so`; cập nhật firmware hoặc kiểm tra library path của OS.

**App không khởi động:** từ `v0.3.20`, trước tiên kiểm tra
`Apps/Chiaki/Chiaki-loi.txt`. Launcher chỉ dùng thư mục log của OS, gốc thẻ hoặc
`/tmp` nếu thư mục app không ghi được; đồng thời kiểm tra quyền thực thi
`launch.sh` và Python 3.10+.

**Hai thư mục Chiaki cùng tên:** đây có thể là hỏng directory entry exFAT do
ngắt cáp khi I/O, không phải updater cố ý tạo thư mục thứ hai. Chạy `chkdsk` trước.
