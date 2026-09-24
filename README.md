# trimui-chiaki-ng

Ứng dụng PS4 / PS5 Remote Play cho TrimUI Smart Pro S/Spruce OS và TrimUI Brick
Pro Stock OS.

**Trạng thái**: v0.3.11 đóng gói Mozilla CA bundle và dùng chung TLS context có
xác minh cho OTA/GitHub Issue trên Brick Pro Stock OS. CA hệ thống vẫn được giữ,
`CERT_REQUIRED` và kiểm tra hostname không bị tắt, nên cùng artifact tiếp tục
dùng cho Smart Pro S/Spruce OS. Native stream, pair/session pre-10, SDL/input và
luồng quét máy đang bật của v0.3.10 không thay đổi.

**Nền tảng v0.3.4:** bổ sung quản lý log và sửa thao tác thoát stream trên
TrimUI. Màn hình chính luôn hiện hướng dẫn giữ `START + SELECT` 1,2 giây; native
nhận cả sự kiện GameController lẫn nút vật lý 8/9 để quay về menu mà không cần
tắt PS4. Pair/session pre-10 cho PS4 Pro firmware 9.00 GoldHEN được giữ nguyên;
ứng dụng không đăng nhập hoặc kết nối PSN.

**Mốc máy thật 2026-09-23:** sau khi OTA lên `v0.3.2` và ghép lại bằng PIN,
Smart Pro S đã hiển thị màn hình PS4, nhận điều khiển và chơi game qua LAN thành
công. Trải nghiệm ban đầu khá ổn nhưng còn drop FPS thường xuyên. Hệ thống tự gửi
log cũng đã tạo GitHub Issue thành công. Log cũ ghi measured video bitrate khoảng
2–3 MBit/s, RTT gần 1 giây và nhiều lỗi FEC. Đây không phải phép đo throughput
Wi-Fi; v0.3.3 giảm tải log và thêm profile bitrate thấp để tách nguyên nhân.

**Kết quả test mới nhất:** renderer là `opengles2 accelerated=1`. `#21` với
`720p30/4000` đạt `6565 rendered / 2 lost / 0 FEC` (native cuối `6654/2`) và
ổn định khoảng 29,8–30,0 FPS. Ngược lại `#20` với `540p60/15000` có khoảng
`40798 rendered / 1357 lost / 295 FEC`, nhiều cảnh báo FEC/IDR/decoder buffer;
không nên dùng bitrate 15000. Sau START+SELECT, nên chờ khoảng hai phút trước
khi kết nối lại vì PS4
có thể tạm báo Remote Play vẫn đang được dùng dù client đã shutdown sạch.

Tiếp tục dự án ở session khác: đọc `docs/NEW_SESSION_HANDOFF.md` trước. Tài liệu
này ghi chính xác release hiện tại, kiến trúc stream, trạng thái test và danh
sách GitHub Issue/log cần đọc trực tiếp từ thiết bị.

## Cấu hình phần cứng mục tiêu

- **SoC**: Allwinner A523 8 nhân Cortex-A55 @ 2.0GHz
- **GPU**: ARM Mali-G57 MC1 @ 744MHz
- **RAM**: 1GB LPDDR4
- **Màn hình**: IPS 4.96 inch 1280×720 (native 720p, không tốn scaler)
- **Wi-Fi**: 802.11 a/b/g/n/ac/ax băng tần kép
- **Firmware**: TrimUI Linux custom 1.1.1 (TG5050 Smart Pro S)

## Cấu hình stream và thứ tự thử

- Profile ưu tiên đã xác nhận: `720p`, `30 FPS`, `4000` kbps.
- Fallback tải thấp: `540p`, `30 FPS`, `4000` kbps.
- Bitrate mặc định cài đặt vẫn là `8000` kbps, nhưng không nên dùng làm baseline.
- Tùy chọn thử nghiệm: `1080p` ở 30/60 FPS. Màn hình máy chỉ 1280×720 nên 1080p
  dùng để đo sức giải mã/GPU, không làm tăng độ phân giải vật lý của màn hình.
- Codec: H264 cho PS4. H265/PS5 có trong helper nhưng chưa được kiểm thử.
- Thứ tự khuyến nghị: `720p30/4000`, rồi `540p30/4000` nếu cần giảm tải.
- Chỉ thử 60 FPS khi `fec/lost` gần 0; không ưu tiên 1080p hoặc 15000 kbps trên
  màn 720p.

## Chạy stream

1. Sau khi cập nhật từ v0.3.1, chọn PS4 và bấm **Y – GHÉP NỐI** để nhập PIN lại
   đúng một lần. Khóa cũ được tạo bằng giao thức 10.0 nên không dùng cho FW 9.00.
2. Bật PS4 bằng nút nguồn hoặc tay cầm thật và để auto-login hoàn tất.
3. Quét LAN. App chỉ hiện PS4 đang phản hồi; nếu chưa thấy, chờ máy khởi động
   xong rồi quét lại. Chọn PS4 và bấm **A – BẮT ĐẦU CHƠI**.
4. Nếu một lần kết nối thất bại rồi PS4 báo Remote Play đang được dùng, không
   bấm liên tục; chờ khoảng hai phút để PS4 nhả phiên rồi quét/kết nối lại.
5. Giữ **START + SELECT** khoảng 1,2 giây để dừng stream và trở lại menu.
   Không cần tắt, rest mode hoặc khởi động lại PS4.
6. Khi thoát stream bình thường, app tự gửi Issue `native_stream_quality` chứa
   FPS/rendered/lost/FEC nếu `secrets.json` đã được cấu hình. Nếu không có hình,
   app gửi log lỗi như trước; hai file cục bộ vẫn nằm trong
   `Apps/Chiaki/`. Log có kết quả `ldd`, handshake, frame và exit code nhưng
   không chứa PIN, `regist_key` hoặc `rp_key`.

## Cài đặt từ GitHub Releases

**Brick Pro đang ở v0.3.9/v0.3.10:** phải cài ZIP v0.3.11 thủ công lần đầu vì
updater cũ không có CA để tải chính bản vá CA. Sau khi v0.3.11 đã chạy, OTA và
GitHub Issue uploader dùng bundle CA đóng gói. Không cần tắt xác minh TLS.

1. Mở [trang Releases](https://github.com/nlkcodenew/trimui-chiaki-ng/releases/latest).
2. Tải `trimui-chiaki-ng-vX.Y.Z.zip` (không tải Source code ZIP của GitHub).
3. Giải nén ZIP trực tiếp vào **thư mục gốc của thẻ nhớ**. Kết quả phải có
   `Apps/Chiaki/launch.sh` và `Apps/Chiaki/app.py`.
4. Lắp thẻ vào Smart Pro S, vào **Apps** → **Chiaki-ng**.
5. Lần đầu khởi động, ứng dụng sẽ:
   - Kiểm tra Python 3 và thư viện SDL2
   - Tự quét máy PS4/PS5 qua Wi-Fi
   - Tự kiểm tra bản cập nhật mới trên GitHub (có thể tắt trong **Cài đặt**)

## Tự cập nhật (OTA)

Mỗi lần khởi động, nếu `auto_update = true`, ứng dụng ưu tiên đọc
`manifest.json` của GitHub Release mới nhất và dùng bản trên nhánh `main` làm
dự phòng. Nếu có bản mới, popup cho phép chọn:

- **CÀI NGAY**: tải từng file, kiểm tra `sha256`, ghi đè vào chỗ thật bằng `os.replace` (an toàn khi máy tắt đột ngột).
- **ĐỂ SAU**: đóng popup, lần sau sẽ hỏi lại.
- **BỎ QUA**: ghi phiên bản vào `settings.json.skipped_versions`, không hỏi nữa.

`settings.json` trên máy không bao giờ bị ghi đè, để bảo toàn cấu hình người dùng.
Payload OTA ưu tiên tải từ tag bất biến `vX.Y.Z` và luôn được kiểm tra SHA-256
trước khi cài.

## Tự gửi crash log lên GitHub

GitHub không hỗ trợ tạo Issue ẩn danh. Muốn app tự gửi log, tạo một
**fine-grained personal access token** chỉ cho repo
`nlkcodenew/trimui-chiaki-ng`, với quyền tối thiểu:

- Repository access: **Only select repositories** → `trimui-chiaki-ng`
- Repository permissions: **Issues: Read and write**
- Không cấp quyền Contents, Administration hoặc quyền tài khoản khác

Trên máy tính, copy `Apps/Chiaki/secrets.example.json` thành
`Apps/Chiaki/secrets.json`, điền token vào `github_token`, rồi lắp thẻ vào máy.
Không gửi token qua chat và không commit file này. `secrets.json` bị loại khỏi
Git, manifest OTA và ZIP Release.

Khi app thoát do lỗi, launcher tạo `.pending_crash` và gửi log trong lần hiện
tại hoặc lần khởi động tiếp theo nếu mạng đang mất. Từ v0.3.3, phiên stream thoát
bình thường cũng gửi báo cáo `native_stream_quality` để đo drop FPS từ xa. Trước
khi gửi, app lọc token, password, khóa đăng ký, PSN ID, địa chỉ IP nội bộ và địa
chỉ MAC. Fingerprint ngăn tạo Issue lặp lại. Có thể tắt trong **Cài đặt**.

## File log

App ghi log rolling vào hai file nằm ngay trong thư mục `Apps/Chiaki/`:

- `Chiaki-loi.txt` - chỉ warning + error, xoay vòng tối đa 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ info + debug, xoay vòng 1 file backup 512 KB

Từ v0.3.4, launcher còn cắt giữ phần cuối log sau mỗi phiên stream để log native
không tăng vô hạn. Trong **Cài đặt → XÓA LOG CŨ**, bấm A và xác nhận để xóa log
cùng backup trước một bài test mới. Nếu còn báo cáo chờ gửi GitHub, app từ chối
xóa để không làm mất bằng chứng. Khi chọn **THOÁT**, launcher retry báo cáo đang
chờ trước khi đóng; nó không tạo Issue mới nếu không có report pending.

Định dạng mỗi dòng:

```
[2026-09-19 11:30:00.123] [INFO ] [MainThread  ] [trimui-chiaki-ng] home: bat dau scan...
```

Để bật log debug chi tiết, mở `settings.json` đổi `"enable_logging": false` thành
`true`. Nếu chưa cấu hình token, vẫn có thể lấy hai file trên và gửi thủ công.

## Cấu trúc repo

```
tools/
  make_release.py       # Build manifest.json với sha256 mới khi push tag
files/
  app.py                # Điểm vào chương trình
  config.json           # Manifest cho TrimUI launcher
  launch.sh             # Script khởi động (tìm python3, đặt env, ghi log)
  settings.json         # Cấu hình người dùng
  bin/chiaki-stream     # ELF AArch64: session, H264, Opus, SDL input/render
  rh/
    engine.py           # Engine SDL2 (window, renderer, font, input)
    chiaki.py           # Wrapper discovery / wakeup / chiaki.conf
    updater.py          # Bộ cập nhật OTA
    logger.py           # Logger rolling 2 file
    modals/update.py    # Popup cập nhật OTA
    screens/            # Giao diện (home, settings)
    state.py            # Trạng thái runtime
    version.py          # Hằng số APP_VERSION
native/
  chiaki-stream.c       # Frontend native nhẹ cho RAM 1GB
  build-tg5050.sh       # Build tái lập bằng SDK TG5050 chính hãng
.github/workflows/
  release.yml           # Build ZIP + manifest và tạo GitHub Release khi push tag
manifest.json           # (chỉ tool tạo ra) danh sách sha256 + version
```

## Build bản phát hành

Đẩy tag phiên bản mới:

```
git tag v0.3.0
git push origin v0.3.0
```

Trước khi tag, chạy build và commit manifest:

```
python tools/make_release.py
python tools/verify_release.py
git add manifest.json
git commit -m "chore(release): prepare v0.3.0"
git push origin main
git tag v0.3.0
git push origin v0.3.0
```

GitHub Actions build lại, kiểm tra gói và tạo Release gồm ZIP cài đặt, file
SHA-256 và `manifest.json`. Máy cũ đọc manifest trên `main` để biết có version
mới; sau khi lên v0.2.3, app ưu tiên manifest của GitHub Releases.

## Lưu ý quan trọng

- Cần Python 3.10 trở lên. Firmware TrimUI Linux 1.1.1 đã có sẵn.
- Cần SDL2 + SDL2_ttf. Có sẵn trong `/usr/lib64` của firmware.
- Ghép nối PS4 dùng AES-128-CFB thuần Python, không cần `openssl` hay thư viện ngoài.
- Nên **tắt Bluetooth** trước khi stream để tránh nhiễu Wi-Fi (khuyến cáo của hãng).
- Khi đo drop FPS, thử `720p30/4000` trước; chỉ tăng bitrate nếu FEC/lost thấp.
- Native helper dùng ABI của SDK TG5050: SDL2 2.32, FFmpeg 6, Opus và OpenSSL 1.1.
- Stream hiện chỉ nhắm LAN; Internet/RUDP và PS5 cần kiểm thử sau.

## Giấy phép

`AGPL-3.0` (copy từ chiaki-ng upstream). Khi phát hành binary phải kèm source.
