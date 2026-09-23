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
- Tag/Release đã phát hành và xác nhận trên máy thật: `v0.3.2`
- Release: `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/tag/v0.3.2`
- `manifest.json` trả về đúng `0.3.2`, có
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

- `python -m unittest discover -s tests -v`: 28/28 test đạt.
- `python -m compileall -q files tools native`: đạt.
- `bash -n files/launch.sh`: đạt.
- `bash -n native/build-tg5050.sh`: đạt.
- `python tools/make_release.py`: đạt.
- `python tools/verify_release.py`: đạt.
- ZIP có quyền `0755` cho `App/Chiaki/bin/chiaki-stream`.
- Sandbox không đo được hiệu năng thực tế; kết quả máy thật xác nhận stream và
  input hoạt động, còn drop FPS cần phân tích bằng Issue log tự động.

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
2. Giữ nguyên mốc ổn định `v0.3.2`; không sửa lại pair/session nếu không có bằng chứng.
3. Đọc GitHub Issue log của phiên stream thực tế và định lượng drop FPS.
4. Xác định bottleneck network/decode/convert/render trước khi thay thông số.
5. So sánh cấu hình 720p30 8000 kbps với 6000 kbps trên cùng điều kiện Wi-Fi.
6. Sửa tối thiểu đúng nguyên nhân, tăng version, chạy test/build/verify, push
   `main`, tạo tag và xác minh GitHub Release/manifest latest trước khi yêu cầu
   người dùng OTA.

## 10. Các phần chưa xác nhận

- Nguyên nhân chính xác của drop FPS thường xuyên ở 720p30.
- Bitrate tối ưu cho Wi-Fi và RAM 1 GB của Smart Pro S.
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
stream thành công PS4 Pro firmware 9.00 GoldHEN trên Smart Pro S: có hình, input
và chơi được qua LAN, không PSN. Uploader GitHub Issue cũng đã hoạt động. Nhiệm
vụ hiện tại là đọc Issue log, định lượng và tối ưu drop FPS thường xuyên mà không
làm hỏng mốc pair/session pre-10 đang chạy tốt.
Không tiết lộ hoặc ghi log PIN, regist_key, rp_key, Account-ID hay token.
```
