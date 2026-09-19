# trimui-chiaki-ng

Ứng dụng PS4 / PS5 Remote Play cho máy TrimUI Smart Pro S (firmware Linux 1.1.1).

**Trạng thái**: v0.2.0 - đã chạy được trên máy thật, quét máy PS4/PS5 qua LAN, hỗ trợ auto-update từ GitHub. Phiên bản v0.3.0 sẽ thêm luồng stream video thật với codec H264 / H265.

## Cấu hình phần cứng mục tiêu

- **SoC**: Allwinner A523 8 nhân Cortex-A55 @ 2.0GHz
- **GPU**: ARM Mali-G57 MC1 @ 744MHz
- **RAM**: 1GB LPDDR4
- **Màn hình**: IPS 4.96 inch 1280×720 (native 720p, không tốn scaler)
- **Wi-Fi**: 802.11 a/b/g/n/ac/ax băng tần kép
- **Firmware**: TrimUI Linux custom 1.1.1 (TG5050 Smart Pro S)

## Cấu hình video đề xuất (mục tiêu v0.3.0)

- Độ phân giải: `720p` (native, không tốn scaler)
- FPS: `30`
- Bitrate: `8000` kbps (giảm xuống `6000` nếu thấy giật)
- Codec: H264 (PS4), H265 (PS5)

## Cài đặt vào thẻ nhớ

1. Copy toàn bộ thư mục `files/` vào thẻ theo đường dẫn `/mnt/SDCARD/Apps/Chiaki/`.
2. Thêm một file `icon.png` (256×256 PNG, nền trong suốt) vào cùng thư mục.
3. Trong máy Smart Pro S, vào menu **Apps** → **Chiaki-ng**.
4. Lần đầu khởi động, ứng dụng sẽ:
   - Kiểm tra Python 3 và thư viện SDL2
   - Tự quét máy PS4/PS5 qua Wi-Fi
   - Tự kiểm tra bản cập nhật mới trên GitHub (có thể tắt trong **Cài đặt**)

## Tự cập nhật (OTA)

Mỗi lần khởi động, nếu `settings.auto_update = true`, ứng dụng sẽ gọi `manifest.json` tại `https://raw.githubusercontent.com/nlkcodenew/trimui-chiaki-ng/main/manifest.json`. Nếu có bản mới, popup sẽ hiện ra cho phép bạn chọn:

- **CÀI NGAY**: tải từng file, kiểm tra `sha256`, ghi đè vào chỗ thật bằng `os.replace` (an toàn khi máy tắt đột ngột).
- **ĐỂ SAU**: đóng popup, lần sau sẽ hỏi lại.
- **BỎ QUA**: ghi phiên bản vào `settings.json.skipped_versions`, không hỏi nữa.

`settings.json` trên máy không bao giờ bị ghi đè, để bảo toàn cấu hình người dùng.

## File log

App ghi log rolling vào hai file nằm ngay trong thư mục `Apps/Chiaki/`:

- `Chiaki-loi.txt` - chỉ warning + error, xoay vòng tối đa 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ info + debug, xoay vòng 1 file backup 512 KB

Định dạng mỗi dòng:

```
[2026-09-19 11:30:00.123] [INFO ] [MainThread  ] [trimui-chiaki-ng] home: bat dau scan...
```

Để bật log debug chi tiết, mở `settings.json` đổi `"enable_logging": false` thành `true`. Sau đó gửi hai file log này cho dev khi cần hỗ trợ.

## Cấu trúc repo

```
tools/
  make_release.py       # Build manifest.json với sha256 mới khi push tag
files/
  app.py                # Điểm vào chương trình
  config.json           # Manifest cho TrimUI launcher
  launch.sh             # Script khởi động (tìm python3, đặt env, ghi log)
  settings.json         # Cấu hình người dùng
  rh/
    engine.py           # Engine SDL2 (window, renderer, font, input)
    chiaki.py           # Wrapper discovery / wakeup / chiaki.conf
    updater.py          # Bộ cập nhật OTA
    logger.py           # Logger rolling 2 file
    modals/update.py    # Popup cập nhật OTA
    screens/            # Giao diện (home, settings)
    state.py            # Trạng thái runtime
    version.py          # Hằng số APP_VERSION
.github/workflows/
  release.yml           # Auto build manifest khi push tag v*
manifest.json           # (chỉ tool tạo ra) danh sách sha256 + version
```

## Build bản phát hành

Đẩy tag phiên bản mới:

```
git tag v0.3.0
git push origin v0.3.0
```

GitHub Action chạy `tools/make_release.py` → cập nhật `manifest.json` → commit ngược vào `main`. Mọi máy đang chạy bản cũ sẽ tự popup cập nhật trong vòng 30 giây khi người dùng mở ứng dụng.

## Lưu ý quan trọng

- Cần Python 3.10 trở lên. Firmware TrimUI Linux 1.1.1 đã có sẵn.
- Cần SDL2 + SDL2_ttf. Có sẵn trong `/usr/lib64` của firmware.
- Nên **tắt Bluetooth** trước khi stream để tránh nhiễu Wi-Fi (khuyến cáo của hãng).
- Bitrate mặc định `8000` kbps; nếu thấy giật thì giảm xuống `6000`.
- Phiên bản stream video thật sẽ đến ở v0.3.0 (FFmpeg subprocess + SDL renderer).

## Giấy phép

`AGPL-3.0` (copy từ chiaki-ng upstream). Khi phát hành binary phải kèm source.