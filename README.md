# trimui-chiaki-ng

Ứng dụng PS4 / PS5 Remote Play cho máy TrimUI Smart Pro S (firmware Linux 1.1.1).

**Trạng thái**: v0.2.8 - giao diện SDL, quét PS4/PS5 trong LAN, GitHub Release,
OTA theo manifest và tự gửi crash log đã sẵn sàng để thử trên máy thật. Luồng
stream video thực tế chưa được triển khai; mục tiêu của v0.3.0 là H264/H265
720p30.

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

## Cài đặt từ GitHub Releases

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
tại hoặc lần khởi động tiếp theo nếu mạng đang mất. Trước khi gửi, app lọc token,
password, khóa đăng ký, PSN ID, địa chỉ IP nội bộ và địa chỉ MAC. Fingerprint
được lưu cục bộ để cùng một crash không tạo Issue lặp lại. Có thể tắt bằng mục
**Tự gửi log lỗi** trong **Cài đặt**.

## File log

App ghi log rolling vào hai file nằm ngay trong thư mục `Apps/Chiaki/`:

- `Chiaki-loi.txt` - chỉ warning + error, xoay vòng tối đa 3 file backup 256 KB
- `Chiaki-debug.log` - toàn bộ info + debug, xoay vòng 1 file backup 512 KB

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
- Nên **tắt Bluetooth** trước khi stream để tránh nhiễu Wi-Fi (khuyến cáo của hãng).
- Bitrate mặc định `8000` kbps; nếu thấy giật thì giảm xuống `6000`.
- Phiên bản stream video thật sẽ đến ở v0.3.0 (FFmpeg subprocess + SDL renderer).

## Giấy phép

`AGPL-3.0` (copy từ chiaki-ng upstream). Khi phát hành binary phải kèm source.
