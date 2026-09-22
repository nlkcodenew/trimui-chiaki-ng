# Bàn giao session mới — trimui-chiaki-ng v0.3.2

> Cập nhật: 2026-09-22. Đây là tài liệu cần đọc đầu tiên khi tiếp tục dự án.

## 1. Mục tiêu hiện tại

Kiểm thử và hoàn thiện Remote Play PS4 qua LAN trên TrimUI Smart Pro S TG5050.
Bản `v0.3.2` sửa toàn bộ luồng PS4 firmware 9.00 GoldHEN sang protocol pre-10:
pair PIN `/sce/rp/regist`, session `/sce/rp/session`, `RP-Version: 9.0`.

## 2. Repo và bản phát hành

- Repo: `https://github.com/nlkcodenew/trimui-chiaki-ng`
- Thư mục làm việc: `E:\Trimiu Brick Pro\Project APPS\chiaki-ng`
- Nhánh: `main`
- Commit hiện tại: `12a89c3`
- Tag/Release chuẩn bị phát hành: `v0.3.2`
- Release: `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/tag/v0.3.2`
- `manifest.json` phải trả về đúng `0.3.2`, có
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
- Chưa có kết quả kiểm thử stream `v0.3.2` trên thiết bị thật ở thời điểm bàn
  giao. Đây là bước đầu tiên của session kế tiếp.

## 5. Luồng stream v0.3.2

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
- Bitrate 8000 kbps; nếu drop thì thử 6000 kbps.
- Âm thanh Opus qua SDL queued audio.
- Giữ `START + SELECT` khoảng 1,2 giây để kết thúc stream.

## 6. Binary và build

- Binary phát hành: `files/bin/chiaki-stream`.
- Kiến trúc: ELF64 AArch64 PIE, interpreter `/lib/ld-linux-aarch64.so.1`.
- SHA-256 binary: `fe0d5ee63a3eba28f15a43f336f1844de930e63e1473c2d9226752de96d8ae1f`.
- Build bằng SDK TG5050 chính hãng, GCC 10.3.1, glibc 2.33.
- ABI phụ thuộc đã đối chiếu với SDK: SDL2 2.32, FFmpeg 6
  (`libavcodec.so.60`, `libavutil.so.58`, `libswscale.so.7`), Opus,
  OpenSSL 1.1, json-c, libevent và nghttp2.
- Source native: `native/chiaki-stream.c`.
- Script build tái lập: `native/build-tg5050.sh`.
- Upstream chiaki-ng đã dùng commit
  `a9a2805884cfa83865fdfcc09ca3ddfcd628aa42`.

## 7. Trạng thái kiểm thử trong sandbox

- `python -m unittest discover -s tests -v`: 27/27 test đạt.
- `python -m compileall -q files tools native`: đạt.
- `bash -n files/launch.sh`: đạt.
- `bash -n native/build-tg5050.sh`: đạt.
- `python tools/make_release.py`: đạt.
- `python tools/verify_release.py`: đạt.
- ZIP có quyền `0755` cho `App/Chiaki/bin/chiaki-stream`.
- Không thể xác nhận hình, âm thanh và độ trễ thật trong sandbox vì không có
  Smart Pro S/PS4.

## 8. Log cần gửi ở session mới

Sau khi thử bấm A để stream, tháo thẻ nhớ và đính kèm trực tiếp hai file sau
vào lời nhắn đầu tiên của session mới:

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
2. Người dùng cập nhật/cài `v0.3.2`, bật PS4 và ghép lại bằng PIN một lần.
3. Bấm A để bắt đầu chơi, chờ ít nhất 20–30 giây.
4. Ghi nhận PS4 có chuyển vào Remote Play hay không; có hình, âm, input hay
   màn hình đen/tự thoát.
5. Thử giữ `START + SELECT` 1,2 giây nếu stream mở được.
6. Đọc hai file log thiết bị được đính kèm, xác định lỗi đầu tiên thay vì đoán.
7. Sửa tối thiểu đúng nguyên nhân, tăng version, chạy test/build/verify, push
   `main`, tạo tag và xác minh GitHub Release/manifest latest trước khi yêu cầu
   người dùng OTA.

## 10. Các phần chưa xác nhận

- PS4 có nhận phiên và gửi frame thật cho binary `v0.3.2` hay không.
- Khả năng tương thích SDL video/audio/input thực tế trên firmware 1.1.1.
- Hiệu năng software decode 720p30 và bitrate phù hợp trên RAM 1 GB.
- PS5/H265.
- Remote Play qua Internet/RUDP.
- Tự tạo GitHub Issue chỉ hoạt động nếu người dùng tự cấu hình
  `Apps/Chiaki/secrets.json` với token Issues; không có token thì phải gửi log
  thủ công. Không yêu cầu người dùng chia sẻ token.

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

Đọc docs/NEW_SESSION_HANDOFF.md và docs/PROJECT_STATUS.md trước. Bản đang test
là v0.3.2. PS4 Pro firmware 9.00 GoldHEN dùng pair/session pre-10, không PSN;
nhiệm vụ hiện tại là đọc Issue log tự động hoặc log thiết bị, sửa
lỗi stream native PS4 LAN 720p30, kiểm thử, build và phát hành bản OTA mới.
Không tiết lộ hoặc ghi log PIN, regist_key, rp_key, Account-ID hay token.
```
