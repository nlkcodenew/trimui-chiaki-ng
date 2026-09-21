# Cài đặt trimui-chiaki-ng vào TrimUI Smart Pro S

## Yêu cầu

- Smart Pro S chạy firmware Linux custom 1.1.1 (TG5050), đã có sẵn:
  - Python 3.10+
  - `libSDL2.so`, `libSDL2_ttf.so` (ở `/usr/lib64` hoặc `/usr/lib`)
  - `libopus.so`, `libcurl.so` (ở `/usr/lib`)
- Thẻ nhớ micro SD format FAT32 hoặc exFAT
- Quyền ghi vào thư mục `Apps/` trên thẻ

## Lần đầu cài (v0.2.0 trở xuống → v0.2.2)

**Quan trọng: nếu máy đang chạy v0.2.0 hoặc v0.2.1 bị crash `ModuleNotFoundError: No module named 'sdl2'`, làm theo các bước sau.**

1. **Tắt app và xoá thư mục cũ**: trên máy Smart Pro S, mở **Settings** → **Apps** → **Chiaki-ng** → **Uninstall** (nếu có). Nếu không có, mở **File Manager** trên máy, vào `/mnt/SDCARD/Apps/Chiaki/` rồi xoá sạch thư mục `Chiaki`.

2. **Tháo thẻ nhớ** khỏi máy, cắm vào PC.

3. **Copy thư mục `files/` vào thẻ** ở đường dẫn `/mnt/SDCARD/Apps/Chiaki/`.

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

4. **Thêm file `icon.png`** (256×256 PNG, nền trong suốt) vào cùng thư mục.

5. **Lắp thẻ lại vào máy**, vào **Apps** → **Chiaki-ng**.

## Cập nhật OTA từ v0.2.2 trở đi

Sau khi cài v0.2.2 thành công, mỗi lần khởi động app sẽ tự động kiểm tra GitHub release mới. Nếu có bản mới (ví dụ v0.3.0), popup sẽ hiện ra để bạn chọn:

- **CÀI NGAY**: tải về ~30s, tự kiểm tra `sha256`, ghi đè vào chỗ thật, restart.
- **ĐỂ SAU**: đóng popup, lần sau mở app sẽ hỏi lại.
- **BỎ QUA**: ghi vào `skipped_versions`, không hỏi nữa cho bản đó.

## File log

Khi app chạy, 2 file log nằm ngay trong `Apps/Chiaki/`:

- `Chiaki-loi.txt` - lỗi + cảnh báo, xoay vòng 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ hoạt động, xoay vòng 1 file backup 512 KB

Format mỗi dòng: `[YYYY-MM-DD HH:MM:SS.mmm] [LEVEL] [Thread] module - message`

Để bật log debug, sửa `settings.json` đổi `"enable_logging": false` thành `true`. Khi gặp lỗi, copy 2 file log đó và gửi cho dev.

## Gỡ lỗi nhanh

**Crash `ModuleNotFoundError: No module named 'sdl2'`**: bản cũ (v0.2.0 / v0.2.1) chưa bundle pysdl2. Xoá `Apps/Chiaki/` rồi copy lại v0.2.2.

**Crash `ImportError: PySDL2 not loaded`**: firmware TrimUI thiếu `libSDL2.so`. Cập nhật firmware lên 1.0.4 trở lên (có sẵn libSDL2 2.30.8).

**App không khởi động, không log gì**: kiểm tra `/mnt/SDCARD/Chiaki-loi.txt` hoặc `Apps/Chiaki/Chiaki-loi.txt` có mới không. Nếu rỗng, kiểm tra quyền thực thi của `launch.sh`.