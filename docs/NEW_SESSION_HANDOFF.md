# Bàn giao session mới — trimui-chiaki-ng v0.3.7

> Cập nhật: 2026-09-23. Đây là tài liệu cần đọc đầu tiên khi tiếp tục dự án.

## 1. Mục tiêu hiện tại

Kiểm thử hiệu năng Remote Play PS4 qua LAN trên TrimUI Smart Pro S TG5050.
`v0.3.2` là mốc stream thật ổn định về chức năng; `v0.3.3` tối ưu I/O/render.
`v0.3.4` quản lý log an toàn và sửa đường thoát stream START+SELECT trên TrimUI.
`v0.3.5` sửa hộp xóa log bị nháy rồi tự đóng do nhận lại nút A đang giữ.
Kiểm thử thật v0.3.5 đã có thêm hai phiên quan trọng: 540p60/15000 bị
packet loss/FEC và IDR nặng; 720p30/4000 chạy ổn định. `v0.3.6` sửa mapping
A/B/X/Y ở native SDL GameController và đã được xác nhận đúng trên máy thật.
`v0.3.7` thêm host paired offline và nút đánh thức PS4 từ Rest Mode.

## 2. Repo và bản phát hành

- Repo: `https://github.com/nlkcodenew/trimui-chiaki-ng`
- Thư mục làm việc: `E:\Trimiu Brick Pro\Project APPS\chiaki-ng`
- Nhánh: `main`
- Mốc ổn định đã xác nhận trên máy thật: `v0.3.2` (`9605d83`)
- Bản stream/mapping đã kiểm thử máy thật: `v0.3.6`
- Release: `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/tag/v0.3.7`
- `manifest.json` phải trả về đúng `0.3.7`, có
  `bin/chiaki-stream` và không có `settings.json`.

## 3. Phần cứng kiểm thử

- Máy cầm tay: TrimUI Smart Pro S, TG5050, Linux firmware 1.1.1.
- SoC: Allwinner A523, 8 nhân Cortex-A55, Mali-G57 MC1, RAM 1 GB.
- Màn hình: 1280×720.
- Máy đích: PS4 Pro tên `PS4-896`, firmware 9.00 + GoldHEN.
- IP LAN đã dùng khi thử: `192.168.1.45`.
- PSN bị khóa chủ động; ghép nối chỉ dùng PIN hiển thị bởi PS4.

Không ghi hoặc dán PIN, `regist_key`, `rp_key`, Account-ID hay token GitHub vào
tài liệu, Issue hoặc chat. Các khóa thật chỉ được giữ trên thẻ nhớ của người dùng.

## 4. Những gì đã xác nhận trên máy thật

- Giao diện tiếng Việt có dấu hoạt động.
- Nút A thay đổi cài đặt, nút B thoát menu và dòng `QUAY LẠI` hoạt động từ
  `v0.2.10`.
- OTA từ menu ứng dụng hoạt động.
- Quét LAN tìm thấy `PS4-896` tại `192.168.1.45` từ `v0.2.11`.
- Ghép nối PS4 thật thành công: PS4 tự đóng màn hình nhập PIN và app lưu khóa
  hợp lệ từ `v0.3.0-beta.1`.
- Ngày 2026-09-23, `v0.3.2` đã stream thành công trên Smart Pro S thật: màn hình
  PS4 xuất hiện, input hoạt động và người dùng đã chơi game qua LAN.
- Trải nghiệm ban đầu khá ổn nhưng drop FPS xảy ra khá nhiều. Đây là ưu tiên kế
  tiếp; pair, session pre-10 và hiển thị hình không còn là blocker.
- `secrets.json` đã được cấu hình và uploader đã tự tạo GitHub Issue `#1`, `#2`.
  Mục tiêu tự gửi log không cần người dùng đính kèm file thủ công đã đạt.

## 5. Luồng stream native

1. `files/rh/screens/home.py` gọi `prepare_stream_launch()`.
2. `files/rh/chiaki.py` đọc credential của đúng host, kiểm tra RP key 16 byte,
   tạo file phiên tạm quyền `0600` và `/tmp/launch_game.sh`.
3. Python/SDL menu thoát với lý do `stream_launch` để giải phóng màn hình.
4. `files/launch.sh` chạy `files/bin/chiaki-stream`, gom stdout/stderr vào log.
5. Native helper xóa file phiên ngay sau khi đọc, khởi tạo `chiaki_session`,
   giải mã video bằng FFmpeg, phát hình/âm thanh và gửi input.
6. Khi native kết thúc, launcher mở lại menu ứng dụng.

Cấu hình mặc định:

- PS4 H264, 1280×720, 30 FPS.
- Bitrate mặc định 8000 kbps; menu có 3000/4000 để thử đường truyền yếu.
- Độ phân giải có 360p/540p/720p/1080p; 1080p được scale về màn 720p.
- Âm thanh Opus qua SDL queued audio.
- Giữ `START + SELECT` khoảng 1,2 giây để kết thúc stream.
- Màn hình chính luôn hiển thị tổ hợp này. Không cần tắt hoặc rest mode PS4.

Tối ưu v0.3.3:

- Tắt TRACE packet/frame mặc định; chỉ bật bằng `CHIAKI_NATIVE_VERBOSE=1`.
- Buffer stdout, chỉ flush lỗi và báo cáo chất lượng 5 giây.
- Cache destination SDL và bỏ clear thừa khi hình phủ kín màn.
- Ghi renderer/accelerated/vsync, FPS thực, lost frame và FEC failure.
- Tự gửi `native_stream_quality` cả khi phiên stream thoát bình thường.

Quản lý log/thoát stream v0.3.4:

- Native đọc thêm raw joystick button 8/9 cho START/SELECT khi SDL cũng mở
  GameController; raw event chỉ dùng phát hiện tổ hợp thoát, không gửi input đôi.
  Khi đủ tổ hợp, OPTIONS/SHARE được nhả khỏi state gửi PS4 để tránh tác dụng phụ.
- **Cài đặt → XÓA LOG CŨ** xóa log/backup sau xác nhận nhưng từ chối nếu còn
  `.pending_crash` để không mất report chưa gửi.
- Launcher cap log sau stream và khi đóng app. Khi chọn **THOÁT**, pending report
  được retry ngay; không có pending thì không tạo Issue mới.
- v0.3.5: `InfoModal`, `ConfirmModal`, `StreamLoadingModal` chỉ xử lý `edges`;
  Confirm tự đóng trước callback để hộp kết quả không bị đóng bởi A đang giữ.

## 6. Binary và build

- Binary phát hành: `files/bin/chiaki-stream`.
- Kiến trúc: ELF64 AArch64 PIE, interpreter `/lib/ld-linux-aarch64.so.1`.
- SHA-256 binary v0.3.4: `d9ad23bc35a1cb78dbf6958718f79099996225bc30f2bf3f6b20490b12952f37`.
- Build bằng SDK TG5050 chính hãng, GCC 10.3.1, glibc 2.33.
- ABI phụ thuộc đã đối chiếu với SDK: SDL2 2.32, FFmpeg 6
  (`libavcodec.so.60`, `libavutil.so.58`, `libswscale.so.7`), Opus,
  OpenSSL 1.1, json-c, libevent và nghttp2.
- Source native: `native/chiaki-stream.c`.
- Script build tái lập: `native/build-tg5050.sh`.
- Upstream chiaki-ng đã dùng commit
  `a9a2805884cfa83865fdfcc09ca3ddfcd628aa42`.

## 7. Trạng thái kiểm thử trong sandbox

- `python -m unittest discover -s tests -v`: 47/47 test đạt.
- `python -m compileall -q files tools native`: đạt.
- `bash -n files/launch.sh`: đạt.
- `bash -n native/build-tg5050.sh`: đạt.
- `python tools/make_release.py`: đạt.
- `python tools/verify_release.py`: đạt.
- ZIP có quyền `0755` cho `App/Chiaki/bin/chiaki-stream`.
- Máy thật xác nhận modal xóa log, START+SELECT, stream/input và uploader hoạt
  động. Pair/session pre-10 không thay đổi; `v0.3.6` chỉ sửa mapping native.

### Kết quả Issue v0.3.5 và phiên test mới nhất

- `#4`: 540p30/4000, totals `5304/0/0`, chủ yếu 29–30 FPS.
- `#5`: 540p60/6000, totals `8142/20/0`, chủ yếu 57–60 FPS; FEC=0 nhưng decoder
  đôi lúc đầy, nên drop nhỏ nằm ở decode/render.
- `#6`: 720p30/4000, phiên riêng khoảng `2731/0/0`, chủ yếu gần 30 FPS.
- `#15`: 720p60, totals `4897/343/47`, trung bình khoảng 51,5 FPS; network/FEC
  và decode backlog cùng góp phần.
- `#17`: 1080p30, totals `1672/391/88`, trung bình khoảng 19,6 FPS; decode/render
  không theo kịp ngay cả khi một số cửa sổ FEC=0, sau đó FEC/IDR làm nặng thêm.
- `#18` là phiên 540p60/15000 trước đó: totals `2838/202/50`, trung bình khoảng
  47,2 FPS; bitrate cao làm tăng FEC.
- `#19` là lần bắt đầu phiên 540p60/15000 bị PS4 reset Ctrl và thoát 11, không
  dùng để đánh giá chất lượng hình.
- `#20` là phiên chất lượng 540p60/15000 hợp lệ: khoảng `40798 rendered / 1357
  lost / 295 FEC` (dòng native cuối khoảng `40863 rendered / 1359 lost`), FPS
  quan sát dao động khoảng 29,7–60 và trung bình tail khoảng 48,4. Có nhiều cảnh
  báo FEC, IDR và decoder buffer; 15000 kbps không phù hợp dù chỉ 540p.
- `#21` là phiên chất lượng 720p30/4000 hợp lệ: `6565 rendered / 2 lost / 0 FEC`
  (native cuối `6654 rendered / 2 lost`), renderer GLES2 accelerated, các cửa sổ
  ổn định đạt khoảng 29,8–30,0 FPS. Đây là profile ưu tiên dùng hằng ngày.

Mọi phiên có hình đều ghi `renderer=opengles2 accelerated=1 vsync=1`. Dòng
`measured bitrate`, nếu có, là **MBit/s** của video nhận được chứ không phải MB/s
hay phép đo throughput tối đa của Wi-Fi. Issue v0.3.5 không cung cấp measured
bitrate đủ để suy ra giới hạn Wi-Fi.

Sau START+SELECT, Issue `#7` có session request thành công rồi Ctrl bị reset;
`#8`–`#14` thử lại liên tục báo Remote Play đang được dùng. Khoảng hai phút sau
`#15` kết nối lại. Shutdown trước đó đã gửi Disconnect và dừng Ctrl/Takion sạch,
nên giữ nguyên pair/session và chờ khoảng hai phút trước khi đổi profile.

## 8. Log cho session tiếp theo

Ưu tiên đọc Issue do thiết bị tự tạo trong repo. Uploader đã được xác nhận hoạt
động end-to-end ngày 2026-09-23. Chỉ khi Issue không xuất hiện mới cần lấy tay:

```text
Apps/Chiaki/Chiaki-debug.log
Apps/Chiaki/Chiaki-loi.txt
```

Nếu có file xoay vòng, gửi thêm:

```text
Apps/Chiaki/Chiaki-debug.log.1
Apps/Chiaki/Chiaki-loi.txt.1
```

Không sửa, chép lại bằng tay hoặc dán riêng vài dòng; cần file nguyên bản để giữ
thứ tự thời gian. App đã lọc khóa đăng ký khỏi log. Không gửi `settings.json`,
`paired_hosts.json` hoặc `secrets.json`.

Các marker quan trọng cần tìm:

```text
native stream prepared
native stream preflight
Remote Play connected
first video frame
audio ready
renderer=
quality: rendered=
session quit
native stream exit=
native stream failed
```

Hai file hiện có trong repo làm việc chỉ là log sandbox tạo launcher, không phải
log từ Smart Pro S và không dùng để chẩn đoán stream:

```text
[2026-09-21 21:46:04.471] ... native stream prepared: host=192.168.1.45 profile=1280x720@30fps 8000kbps
```

## 9. Việc session mới cần làm ngay

1. Đọc file này và `docs/PROJECT_STATUS.md`.
2. Giữ nguyên pair/session pre-10 của mốc `v0.3.2` nếu không có bằng chứng lỗi.
3. Dùng `720p30/4000` làm profile ưu tiên đã được xác nhận; `540p30/4000` là
   fallback tải thấp.
4. Chờ khoảng hai phút sau START+SELECT trước khi bắt đầu phiên kế tiếp.
5. Nếu FEC=0 mà codec buffer vẫn đầy/FPS thấp, tối ưu decode/render. Nếu FEC
   tăng, giảm bitrate và xử lý Wi-Fi trước; không thử 1080p/15000 lúc này.

## 10. Các phần chưa xác nhận

- Xác nhận WAKEUP của `v0.3.7` từ Rest Mode trên máy thật.
- Tối ưu decoder/render để 720p60 ổn định hơn.
- Bitrate tối ưu cho Wi-Fi và RAM 1 GB của Smart Pro S.
- Khả năng chạy 1080p30/1080p60 trên A523.
- PS5/H265.
- Remote Play qua Internet/RUDP.

## 11. Lệnh kiểm tra nhanh

```powershell
Set-Location 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng'
git status --short
git log -3 --oneline --decorate
python -m compileall -q files tools native
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
```

Không commit log runtime, `settings.json` của người dùng, khóa ghép nối,
`secrets.json`, thư mục `dist/` hoặc `__pycache__/`.

## 12. Nội dung có thể dán vào session mới

```text
Tiếp tục dự án trimui-chiaki-ng tại
E:\Trimiu Brick Pro\Project APPS\chiaki-ng.

Đọc docs/NEW_SESSION_HANDOFF.md và docs/PROJECT_STATUS.md trước. Mốc v0.3.2 đã
stream thành công PS4 Pro firmware 9.00 GoldHEN trên Smart Pro S, không PSN.
v0.3.5 đã xác nhận modal xóa log và START+SELECT hoạt động. Issue #20 cho thấy
540p60/15000 gây FEC/lost/IDR nặng, còn #21 xác nhận 720p30/4000 ổn định. Chờ
khoảng hai phút sau khi
thoát trước khi reconnect vì PS4 giữ lease tạm. Không sửa pair/session pre-10.
Không tiết lộ hoặc ghi log PIN, regist_key, rp_key, Account-ID hay token.
```
