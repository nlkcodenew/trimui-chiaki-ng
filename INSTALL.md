# Cài đặt trimui-chiaki-ng vào TrimUI Smart Pro S

## Yêu cầu

- Smart Pro S chạy firmware Linux custom 1.1.1 (TG5050), đã có sẵn:
  - Python 3.10+
  - `libSDL2.so`, `libSDL2_ttf.so` (ở `/usr/lib64` hoặc `/usr/lib`)
  - `libopus.so`, `libcurl.so` (ở `/usr/lib`)
  - Lệnh `openssl` (dùng mã hóa khi ghép nối PS4)
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
     settings.json
     rh/                  (engine.py, chiaki.py, updater.py, ...)
     vendor/
       sdl2/              (50 file .py - bắt buộc có)
   ```

4. Lắp thẻ lại vào máy, vào **Apps** → **Chiaki-ng**.

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

## File log cục bộ

Khi app chạy, 2 file log nằm ngay trong `Apps/Chiaki/`:

- `Chiaki-loi.txt` - lỗi + cảnh báo, xoay vòng 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ hoạt động, xoay vòng 1 file backup 512 KB

Format mỗi dòng: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [Thread] module - message`

Để bật log debug, sửa `settings.json` đổi `"enable_logging": false` thành `true`.
Nếu không cấu hình tự gửi, copy hai file này để gửi thủ công.

## Gỡ lỗi nhanh

**Crash `ModuleNotFoundError: No module named 'sdl2'`**: bản cũ chưa bundle
pysdl2. Xoá `Apps/Chiaki/` rồi giải nén bản Release mới nhất vào gốc thẻ.

**Crash `ImportError: PySDL2 not loaded`**: firmware TrimUI thiếu `libSDL2.so`. Cập nhật firmware lên 1.0.4 trở lên (có sẵn libSDL2 2.30.8).

**App không khởi động, không log gì**: kiểm tra `/mnt/SDCARD/Chiaki-loi.txt` hoặc `Apps/Chiaki/Chiaki-loi.txt` có mới không. Nếu rỗng, kiểm tra quyền thực thi của `launch.sh`.
