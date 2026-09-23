# Cài đặt trimui-chiaki-ng vào TrimUI Smart Pro S

## Yêu cầu

- Smart Pro S chạy firmware Linux custom 1.1.1 (TG5050), đã có sẵn:
  - Python 3.10+
  - `libSDL2.so`, `libSDL2_ttf.so` (ở `/usr/lib64` hoặc `/usr/lib`)
  - `libopus.so`, `libcurl.so` (ở `/usr/lib`)
- Thẻ nhớ micro SD format FAT32 hoặc exFAT
- Quyền ghi vào thư mục `Apps/` trên thẻ

## Cài bản GitHub Release

**Nếu máy đang có v0.2.0/v0.2.1 lỗi `ModuleNotFoundError: No module named
'sdl2'`, hãy xoá thư mục cũ trước khi cài.**

1. Tải `trimui-chiaki-ng-vX.Y.Z.zip` tại
   `https://github.com/nlkcodenew/trimui-chiaki-ng/releases/latest`.
   Không tải mục **Source code** do GitHub tự tạo.

2. Tháo thẻ khỏi máy và cắm vào PC. Nếu đang dùng bản v0.2.0/v0.2.1, xoá
   thư mục `Apps/Chiaki/` cũ.

3. Giải nén ZIP vào thư mục gốc của thẻ. Không tạo thêm một lớp thư mục mang
   tên file ZIP.

   Nội dung cuối cùng phải có:
   ```
   Apps/Chiaki/
     app.py
     config.json
     launch.sh
     bin/chiaki-stream   (ELF AArch64 bắt buộc)
     settings.json
     rh/                  (engine.py, chiaki.py, updater.py, ...)
     vendor/
       sdl2/              (50 file .py - bắt buộc có)
   ```

4. Lắp thẻ lại vào máy, vào **Apps** → **Chiaki-ng**.

## Thử stream PS4 LAN

Luồng này đã được xác nhận thành công trên Smart Pro S thật với PS4 Pro firmware
9.00 GoldHEN và `v0.3.2`: có hình PS4 trên máy cầm tay và chơi được qua LAN.
`v0.3.7` thêm đánh thức PS4 đã ghép nối từ Rest Mode ngay trong danh sách máy.
`v0.3.6` sửa mapping A/B/X/Y của native stream; bản này giữ nguyên pair/session.
`v0.3.5` giữ nguyên pair/session đã chạy tốt, sửa hộp xóa log bị nháy/tự đóng,
đồng thời kế thừa quản lý log an toàn và tổ hợp thoát stream của v0.3.4.
Ứng dụng không cần PSN.

1. Đặt PS4 và Smart Pro S cùng Wi-Fi/LAN 5 GHz.
2. Với PS4 firmware 9.00 GoldHEN, không cần và không được đăng nhập PSN. Sau khi
   cập nhật từ v0.3.1, bấm **Y** và nhập PIN lại đúng một lần để tạo khóa pre-10.
3. Muốn bật PS4 không cần tay cầm: bật `Stay Connected to the Internet`,
   `Enable Turning On PS4 from Network` và auto-login, rồi đưa PS4 vào Rest Mode.
   Mở app và quét; chọn host `[offline]`, bấm **A – ĐÁNH THỨC**, chờ thông báo
   sẵn sàng rồi bấm A lần nữa. Nếu PS4 đã bật, chọn máy và bấm A như trước.
   PS4 đã tắt hoàn toàn vẫn cần nút nguồn hoặc tay cầm thật để bật.
4. Bắt đầu bằng profile đã xác nhận tốt `720p`, 30 FPS, 4000 kbps. Nếu cần giảm
   tải, dùng `540p`, 30 FPS, 4000 kbps. Chỉ thử profile khác để so sánh; không
   dùng 15000 kbps làm cấu hình thường xuyên vì test thực tế cho thấy
   FEC/lost/IDR tăng mạnh.
5. Giữ **START + SELECT** khoảng 1,2 giây để thoát stream về menu app.
   Dòng hướng dẫn màu xanh luôn hiện trên màn hình chính. Không cần tắt PS4.
6. Sau khi thoát bình thường, app tự tạo Issue `native_stream_quality` khi token
   đã được cấu hình. Issue có thống kê 5 giây gồm `fps`, `rendered`, `lost`, `fec`
   và renderer. Nếu chưa có token, chép cả `Chiaki-debug.log` và
   `Chiaki-loi.txt`. Dòng `native stream preflight` sẽ liệt kê thư viện thiếu.

## Cập nhật OTA

Mỗi lần khởi động app sẽ kiểm tra GitHub Release mới. Nếu có bản mới, popup
hiện ra để chọn:

- **CÀI NGAY**: tải về ~30s, tự kiểm tra `sha256`, ghi đè vào chỗ thật, restart.
- **ĐỂ SAU**: đóng popup, lần sau mở app sẽ hỏi lại.
- **BỎ QUA**: ghi vào `skipped_versions`, không hỏi nữa cho bản đó.

## Bật tự gửi crash log

GitHub yêu cầu xác thực khi tạo Issue. Tạo fine-grained token chỉ cấp quyền
**Issues: Read and write** cho riêng repo `nlkcodenew/trimui-chiaki-ng`.

1. Copy `Apps/Chiaki/secrets.example.json` thành `Apps/Chiaki/secrets.json`.
2. Điền token vào trường `github_token`.
3. Không gửi token cho người khác và không đăng nội dung file lên Issue/chat.

Token chỉ nằm trên thẻ nhớ; OTA và Release không đọc, ghi đè hoặc đóng gói file
này. Khi crash, log được lọc dữ liệu nhạy cảm rồi tạo GitHub Issue. Nếu mất mạng,
app giữ yêu cầu và thử lại ở lần mở sau.

Luồng này đã được xác nhận hoạt động trên máy thật ngày 2026-09-23: thiết bị đã
tự tạo Issue trong repo sau khi `secrets.json` được cấu hình đúng.

## File log cục bộ

Khi app chạy, 2 file log nằm ngay trong `Apps/Chiaki/`:

- `Chiaki-loi.txt` - lỗi + cảnh báo, xoay vòng 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ hoạt động, xoay vòng 1 file backup 512 KB

Native stream ghi handshake, trạng thái audio/video, số frame mất, FEC, FPS và
exit code vào hai file trên. Log packet/frame lặp lại bị tắt mặc định để tránh I/O
thẻ nhớ làm giảm FPS. PIN và khóa ghép nối không được ghi vào log.

App đã có xoay vòng log. Từ v0.3.4, launcher còn giới hạn lại kích thước sau mỗi
phiên native. Để có log sạch cho một bài test, vào **Cài đặt → XÓA LOG CŨ → A →
Có**. App không cho xóa nếu `.pending_crash` cho biết vẫn còn báo cáo chưa gửi.
Khi chọn **THOÁT**, launcher thử gửi lại report pending trước khi đóng ứng dụng.

Format mỗi dòng: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [Thread] module - message`

`enable_logging` chỉ điều khiển debug Python. Chỉ đặt biến môi trường
`CHIAKI_NATIVE_VERBOSE=1` khi thật sự cần trace native đầy đủ vì chế độ này có thể
làm giảm FPS. Nếu không cấu hình tự gửi, copy hai file để gửi thủ công.

## Đọc báo cáo chất lượng

Mỗi dòng `quality` bao phủ khoảng 5 giây:

```text
[native] quality: rendered=150 lost=0 fec=0 fps=30.0 suppressed=0 totals=...
```

- `fps` gần mức đặt và `fec/lost=0`: decode/render đang theo kịp.
- `fec` hoặc `lost` tăng: ưu tiên giảm bitrate, dùng Wi-Fi 5 GHz và tắt Bluetooth.
- 1080p vẫn được thu nhỏ về màn 1280×720; đây là bài test tải decoder/GPU.

## Gỡ lỗi nhanh

**Crash `ModuleNotFoundError: No module named 'sdl2'`**: bản cũ chưa bundle
pysdl2. Xoá `Apps/Chiaki/` rồi giải nén bản Release mới nhất vào gốc thẻ.

**Crash `ImportError: PySDL2 not loaded`**: firmware TrimUI thiếu `libSDL2.so`. Cập nhật firmware lên 1.0.4 trở lên (có sẵn libSDL2 2.30.8).

**App không khởi động, không log gì**: kiểm tra `/mnt/SDCARD/Chiaki-loi.txt` hoặc `Apps/Chiaki/Chiaki-loi.txt` có mới không. Nếu rỗng, kiểm tra quyền thực thi của `launch.sh`.
