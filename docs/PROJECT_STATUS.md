# trimui-chiaki-ng — trạng thái dự án v0.3.14

> Cập nhật: 2026-09-24. Đây là hồ sơ kỹ thuật tổng hợp; trạng thái thao tác cho
> session tiếp theo nằm trong `docs/NEW_SESSION_HANDOFF.md`.

## 1. Release hiện tại

| Mục | Giá trị |
|---|---|
| Latest | `v0.3.14` |
| Commit/tag | `d09142a` |
| OTA files | 110 |
| ZIP entries | 113 |
| ZIP SHA-256 | `8ece098b41c494e83add3d6647b44383b53946e8dcc0cf27acd590a33e715bbd` |
| Unittest | 69/69 đạt |
| Native SHA-256 | `a8d6bfdb846a501ed9525c378a4f2f9c0c4d64a88aadeb098e1093d4b0378d7d` |
| CA SHA-256 | `f66dff1bdf8f96060b8177976f8b7d9254bc89bc4db933d769f7384d28480bc9` |

GitHub Release có ba asset:

- `manifest.json`.
- `trimui-chiaki-ng-v0.3.14.zip`.
- `trimui-chiaki-ng-v0.3.14.zip.sha256`.

Manifest không chứa `settings.json`, secrets, log hoặc marker runtime. ZIP cài
mới có `settings.json` mặc định với `device_id` rỗng nhưng không có
`secrets.json` hay dữ liệu máy thật.

## 2. Ma trận nền tảng

| Nền tảng | UI/app | TLS/OTA | Pair/stream | Ghi chú |
|---|---:|---:|---:|---|
| Smart Pro S/TG5050 | Đã xác nhận | Đã dùng OTA | Đã stream PS4 thật | Baseline chính |
| Spruce OS | Giữ tương thích | Không thay đổi | Chưa có log mới | Không sửa native trong chuỗi Brick Pro |
| Brick Pro Stock OS | Đã xác nhận | Đã OTA đến `v0.3.13` | Chưa xác nhận đầy đủ | `v0.3.14` chờ test OTA |
| PS4 Pro 9.00/GoldHEN | — | — | Pair/session pre-10 đạt | Không cần PSN |
| PS5/H265 | — | — | Chưa kiểm thử | Không tuyên bố hỗ trợ máy thật |

Hiện một release chung vẫn phù hợp. Chỉ tách release khi có bằng chứng native
binary, ABI hoặc library path khác nhau không thể xử lý an toàn trong launcher.

## 3. Kiến trúc runtime

### Python UI

- `files/app.py`: bootstrap, logger, identity, uploader pending và engine.
- `files/rh/engine.py`: SDL window/render loop, screen/modal stack.
- `files/rh/screens/home.py`: scan, chọn host, update và start stream.
- `files/rh/screens/pair.py`: nhập PIN, registration và lưu khóa.
- `files/rh/screens/settings.py`: cấu hình, xóa log và lưu settings.
- `files/rh/state.py`: state runtime và lưu `settings.json` atomically.

### Remote Play

- `files/rh/chiaki.py`: discovery, registration wrapper, wakeup cũ và launcher.
- `files/rh/ps4_regist.py`: handshake PS4/PS5 registration.
- `files/bin/chiaki-stream`: native AArch64 Remote Play helper.
- `files/launch.sh`: chọn Python, library path, crash marker và stream lifecycle.

### Network/release

- `files/rh/ssl_context.py`: TLS context dùng CA hệ thống + Mozilla bundle.
- `files/rh/updater.py`: manifest fallback, SHA-256, staging, apply và restart.
- `files/rh/log_uploader.py`: sanitize, pending queue, dedupe và GitHub Issue.
- `files/rh/device_identity.py`: model, install ID và hardware pseudonym.
- `tools/make_release.py`: manifest/ZIP deterministic.
- `tools/verify_release.py`: release build gate.

## 4. TLS và OTA

### Bảo mật

- Giữ `ssl.CERT_REQUIRED` và `check_hostname=True`.
- Không dùng `CERT_NONE`, `_create_unverified_context` hoặc tắt hostname check.
- CA bundle Mozilla đi kèm để bù CA store thiếu trên Brick Pro Stock OS.
- Updater và uploader dùng cùng helper verified context.

### Quy tắc manifest

- Ưu tiên GitHub Release latest, sau đó Raw GitHub và fallback phù hợp.
- Chỉ hiện update khi remote version mới hơn `APP_VERSION`.
- Hash drift cùng version không tạo popup lặp.
- `settings.json` bị loại ở build và `pending_files()`.
- Payload URL trỏ tag bất biến `vX.Y.Z/files`.

### Quy tắc lỗi v0.3.14

- Một source lỗi nhưng fallback thành công: log INFO, không report.
- Mọi source lỗi xác minh TLS: `tls_error` + `ota_manifest_tls_error`.
- Mọi source lỗi mạng/DNS/dữ liệu: `network_error` +
  `ota_manifest_network_error`.
- Lỗi hash/download/staging/install/restart có reason riêng.

### An toàn ghi file

- Tải vào `.update_staging`.
- Kiểm SHA-256 trước khi apply.
- Flush + `fsync` từng file staging.
- `os.replace` từng file và `fsync` thư mục đích.
- Apply `rh/version.py` cuối.
- Không thể bảo vệ khỏi rút cáp/thẻ vật lý trong lúc I/O.

## 5. GitHub Issue và quyền riêng tư

Uploader chỉ dùng fine-grained token trong `secrets.json` hoặc env. Token không
nằm trong Git, OTA manifest hoặc ZIP release.

Sanitizer lọc:

- GitHub token, password và secret.
- `regist_key`, `rp_key`, PSN Account ID/Online ID.
- Host name/address và private IP.
- MAC address, serial number, chip ID và machine-id.

Identity gửi lên Issue:

- Model đã làm sạch.
- `CHI-xxxx`: ID ngẫu nhiên lưu trong settings của bản cài/thẻ.
- `HW-xxxxxxxxxxxx`: SHA-256 pseudonym từ nguồn phần cứng ưu tiên.
- `APP-xxxxxxxxxxxx`: fallback nếu không có ID phần cứng.

Máy Brick Pro đang thử có `sun50iw10 / CHI-E545 / HW-C3A2FEFAB3F5`.

Không report:

- Scan bình thường trả `0 host`.
- User cancel/user exit.
- Source OTA trung gian lỗi nhưng fallback thành công.
- Cùng fingerprint/reason đã upload thành công.

Report:

- Crash/exit bất thường.
- Thất bại OTA cuối cùng.
- Settings load/save/callback lỗi.
- Discovery socket exception.
- Pair registration/screen/save lỗi.
- Native helper thiếu hoặc chuẩn bị stream lỗi.
- `native_stream_quality` sau phiên stream để theo dõi hiệu năng.

## 6. Pair, discovery và stream

### Discovery

- PS4 destination port `987`; PS5 destination port `9302`.
- Source socket bind `9303–9319`.
- SRCH packet dùng LF và byte NUL cuối, parser chấp nhận LF/CRLF.
- Chỉ host đang phản hồi xuất hiện trong UI từ `v0.3.10`.

### PS4 registration

- PS4 firmware 9.00 dùng LAN PIN và protocol pre-10.
- Không kết nối PSN.
- Chỉ báo thành công khi response có khóa thật cần thiết.
- `stub-rp-key-*` đã bị loại bỏ.
- Pair/session đã chạy thật từ `v0.3.0-beta.1` và stream từ `v0.3.2`.

### Input và thoát stream

- SDL GameController A/B/X/Y đã xác nhận đúng từ `v0.3.6`.
- Khi controller attached, JOY fallback không tạo double input.
- START+SELECT khoảng 1,2 giây dừng native stream và quay lại app.
- Có fallback physical button 8/9 cho firmware TrimUI.

### Chất lượng đã đo

- `720p30/4000` — Issue `#21`: khoảng `6565 rendered / 2 lost / 0 FEC`,
  FPS 29,8–30,0; đây là baseline.
- `540p60/15000` — Issue `#20`: khoảng
  `40798 rendered / 1357 lost / 295 FEC`; không khuyến nghị.
- 1080p chỉ là bài test tải vì màn mục tiêu 1280×720.
- Measured bitrate trong log là MBit/s video nhận được, không phải throughput
  tối đa của Wi-Fi.

PS4 có thể giữ Remote Play lease khoảng hai phút sau khi client shutdown. Chờ
trước khi kết nối lại để tránh nhiều Issue `already in use`.

## 7. WAKEUP

Lịch sử:

- `v0.3.7`: host paired offline và WAKEUP.
- `v0.3.8`: packet khớp upstream, source port đúng, timeout diagnostic.
- `v0.3.9`: broadcast LAN và retry hai vòng.
- Issue `#26–#30`: console vẫn không phản hồi trong môi trường thật.
- `v0.3.10`: tắt WAKEUP/offline host trong UI, trở lại bật PS4 bằng tay.

Không tiếp tục sửa packet nếu không có môi trường mạng/console khác chứng minh
WAKEUP có thể hoạt động.

## 8. Brick Pro và exFAT

### Kết quả đã xác nhận

- Cài tay `v0.3.11` sửa CA/TLS.
- OTA `v0.3.11 → v0.3.12` thành công.
- OTA `v0.3.12 → v0.3.13` thành công qua Raw fallback sau lỗi DNS Release URL.
- App `v0.3.13` log đúng identity máy.
- Không có pending marker/Issue cho source lỗi trung gian.

### Duplicate directory

Hai thư mục `Chiaki` cùng tên là hỏng directory entry exFAT sau rút cáp khi I/O.
`chkdsk D: /F` sửa filesystem và đổi entry trùng thành `CHIAKI-1`. Cài sạch rồi
OTA lại không tái hiện. Đây không được coi là updater tự tạo thư mục.

## 9. Lịch sử release rút gọn

| Version | Thay đổi chính |
|---|---|
| `v0.2.10` | Sửa A/B trong settings và UI cơ bản |
| `v0.2.11` | Sửa discovery destination ports |
| `v0.3.0-beta.1` | Pair PS4 thật bằng PIN/pre-10 |
| `v0.3.2` | Stream PS4 thật hoạt động |
| `v0.3.3` | Giảm tải I/O/render và quality metrics |
| `v0.3.4` | Quản lý log và START+SELECT |
| `v0.3.5` | Sửa modal nhận lại nút đang giữ |
| `v0.3.6` | Sửa mapping A/B/X/Y native |
| `v0.3.7–v0.3.9` | Thử WAKEUP unicast/broadcast |
| `v0.3.10` | Tắt WAKEUP, giữ active-host flow |
| `v0.3.11` | CA/TLS verified cho Brick Pro |
| `v0.3.12` | Không popup update cùng version |
| `v0.3.13` | Device-specific runtime/OTA Issues và fsync |
| `v0.3.14` | Không cảnh báo giả khi fallback OTA thành công |

## 10. Kiểm thử và build gate

Lệnh chuẩn:

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

69 unittest bao phủ:

- TLS context và CA fallback.
- OTA version/fallback/hash/settings exclusion.
- Uploader sanitize/dedupe/pending concurrency/identity.
- Reproducible release bytes trên Windows/Linux.
- Discovery packet/ports/parser.
- Registration crypto và target validation.
- Input mapping, settings/modal edges và home flow.
- Native launcher không đưa khóa vào script.

Verifier kiểm:

- Tag/version/base URL.
- CA checksum và ELF64 AArch64.
- Manifest source hash và từng payload trong ZIP.
- ZIP/sidecar SHA-256.
- File bắt buộc và file cấm.
- `settings.json` mặc định không có generated device ID.

## 11. Việc tiếp theo

1. Test OTA Brick Pro `v0.3.13 → v0.3.14`.
2. Xác nhận lỗi source trung gian chỉ ở debug log mức INFO và không vào
   `Chiaki-loi.txt` khi fallback thành công.
3. Xác nhận một Issue lỗi thật từ Brick Pro có model/`CHI`/`HW` và không lộ raw
   identifier hoặc secret.
4. Test native stream/input/audio trên Brick Pro.
5. Giữ baseline Smart Pro S `720p30/4000`; không sửa pair/native nếu không có
   log chứng minh regression.
