# trimui-chiaki-ng — trạng thái dự án v0.3.27-beta1

> Cập nhật: 2026-10-02. Đây là hồ sơ kỹ thuật tổng hợp; trạng thái thao tác cho
> session tiếp theo nằm trong `docs/NEW_SESSION_HANDOFF.md`.

> **Quyết định phạm vi:** PS4 là nền tảng duy trì chính thức. PS5 đã đóng sau
> `v0.4.0-beta2`; không phát triển thêm pair, stream, PSN login/Account-ID,
> H265 hoặc giao thức PS5. Beta PS5 chỉ được giữ làm lịch sử thử nghiệm.

> **Bluetooth gamepad (2026-10-02):** `v0.3.27-beta1` là beta thử nghiệm, **không
> phải latest**. Chi tiết kỹ thuật ở `docs/BLUETOOTH_GAMEPAD.md`.

## 1. Release hiện tại

| Mục | Giá trị |
|---|---|
| Bluetooth beta | `v0.3.27-beta1` (pre-release, không phải latest) |
| PS4 recommended | `v0.3.20` |
| Archived PS5 beta | `v0.4.0-beta2` |
| OTA files | 136 |
| ZIP entries | 139 |
| ZIP SHA-256 | `0df44f77dfe792fbb41f0c5d33b40d604693157b77826226bde5435d89ac0fc6` |
| Unittest | 128/128 đạt |
| Go test | đạt |
| Native SHA-256 | `194f41786223dafe1c02ba330797b60450f62abe71f24a80ff442f71e10e39d3` |
| CA SHA-256 | `f66dff1bdf8f96060b8177976f8b7d9254bc89bc4db933d769f7384d28480bc9` |

`v0.3.26-beta1` sửa chế độ tay cầm Bluetooth trên Brick Pro Stock OS: bảng điều
khiển HIDP viết lại đúng đặc tả, bảng ánh xạ nút tách khỏi giả định `key - 304`,
thêm màn hình THỬ NÚT, và bốn lỗi dùng hằng ngày đã sửa. Người dùng PS4 không bị
ảnh hưởng nếu không dùng tay cầm.

Manifest không chứa `settings.json`, secrets, log hoặc marker runtime. ZIP cài
mới có `settings.json` mặc định với `device_id` rỗng nhưng không có
`secrets.json` hay dữ liệu máy thật.

## 2. Ma trận nền tảng

| Nền tảng | UI/app | TLS/OTA | Pair/stream | Ghi chú |
|---|---:|---:|---:|---|
| Smart Pro S/TG5050 | Đã xác nhận | Đã dùng OTA | Đã stream PS4 thật | Baseline chính |
| Spruce OS | Đã xác nhận | Không thay đổi | Stream tốt ở `v0.3.14` | Issue `#35`, model `sun55iw3` |
| Brick Pro Stock OS | Đã xác nhận | Đã OTA đến `v0.3.16` | Đã stream PS4 thật | Issue `#39`, video/audio/input đạt |
| PS4 Pro 9.00/GoldHEN | — | — | Pair/session pre-10 đạt | Không cần PSN |
| PS5/H265 | — | — | Đã đóng sau beta | Không hỗ trợ và không phát triển thêm |

Một release chung đã được xác nhận trên máy thật. `sun50iw10` dùng dependency
closure riêng trong `libs/brick-stock`; `sun55iw3` không nhận path này và tiếp
tục dùng library hệ thống. Không cần tách release ở trạng thái hiện tại.

## 3. Kiến trúc runtime

### Python UI

- `files/app.py`: bootstrap, logger, identity, uploader pending và engine.
- `files/rh/engine.py`: SDL window/render loop, screen/modal stack.
- `files/rh/screens/home.py`: scan, chọn host, update và start stream.
- `files/rh/screens/guide.py`: hướng dẫn 8 bước, điều hướng D-pad/A/B.
- `files/rh/screens/pair.py`: nhập PIN, registration và lưu khóa.
- `files/rh/screens/settings.py`: cấu hình, xóa log và lưu settings.
- `files/rh/screens/bluetooth.py`: màn hình tay cầm Bluetooth của Brick Pro.
- `files/rh/screens/button_test.py`: màn hình THỬ NÚT, ghi `bluetooth-map.json`.
- `files/rh/gamepad_map.py`: đọc/ghi bảng ánh xạ nút và đọc evdev node.
- `files/rh/bluetooth_gamepad.py`: quản lý tiến trình backend, không chặn SDL.
- `files/rh/state.py`: state runtime và lưu `settings.json` atomically.

### Bluetooth gamepad (Brick Pro Stock OS)

- `bluetooth-native/` → `files/bin/brick-pro-bt`: backend Go tĩnh AArch64, không cần
  dbus-python/GLib. Chạy `--check` (tiền kiểm) hoặc `--run` (phiên).
- `files/bluetooth-session.sh`: supervisor, giữ nút START+SELECT và bảo vệ app cha.
- Backend tự thay bluetoothd khi PSM 17/19 bị chiếm, ghi marker trong run dir và
  trả lại dịch vụ Stock OS khi thoát bất kể đường nào.
- Bảng ánh xạ nút đọc từ `bluetooth-map.json` nếu có, không thì dùng mặc định.
- Chi tiết: `docs/BLUETOOTH_GAMEPAD.md`.

### Remote Play

- `files/rh/chiaki.py`: discovery, registration wrapper, wakeup cũ và launcher.
- `files/rh/ps4_regist.py`: handshake PS4/PS5 registration.
- `files/bin/chiaki-stream`: native AArch64 Remote Play helper.
- `files/libs/brick-stock`: 14 shared libraries AArch64, chỉ cho `sun50iw10`.
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

Từ `v0.3.17`, app chỉ dùng HTTPS relay trong `reporting.json`. Fine-grained
token chỉ nằm trong Cloudflare Worker secret, giới hạn quyền tạo Issue ở repo
chẩn đoán private; token không nằm trong app, URL, Git, OTA hoặc ZIP. Runtime
không còn code đọc token, `secrets.json` hoặc tên repo nhận log.
Từ `v0.3.19`, diagnostics luôn bật cho cài mới và tự migrate cấu hình cũ;
Settings không còn công tắc tắt để tránh người thử quên bật trong giai đoạn beta.

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
- Brick Stock OS `540p30/3000` — Issue `#39`: `8968 rendered / 0 lost / 0 FEC`,
  phần lớn 29,4–30,2 FPS, native exit `0`; hình, âm thanh và input hoạt động.
- `v0.3.17` bỏ 1080p khỏi UI và cap cấu hình cũ về 720p.
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
| `v0.3.15` | Runtime AArch64 biệt lập cho Brick Pro Stock OS |
| `v0.3.16` | Preload OpenSSL 1.1.1 tương thích chỉ cho Brick stream |
| `v0.3.17` | Khóa 720p; chuyển báo cáo lỗi sang HTTPS relay không token client |
| `v0.3.18` | Hướng dẫn trong app; hiện `CHI-xxxx` cạnh version để tra Issue |
| `v0.3.19` | Luôn bật diagnostics; report cả lần thử pair PS5 chưa hỗ trợ |
| `v0.3.20` | Giữ log launcher trong app và bắt lỗi bootstrap trước khi đọc settings |
| `v0.3.25-beta1` | Tay cầm Bluetooth Classic HID cho Brick Pro Stock OS (hướng A) |
| `v0.3.26-beta1` | HIDP đúng đặc tả; bảng ánh xạ nút + màn hình THỬ NÚT; bỏ 4 lỗi dùng hằng ngày |
| `v0.3.27-beta1` | Một lần bấm chỉ gán một nút; chặn bản đồ trùng mã; sửa SDP record; bỏ hciconfig không hỗ trợ |
| `v0.3.30-beta1` | Đưa bản đồ đã đo bằng máy thật vào mặc định Go + Python; MENU=316; bỏ L2/R2 khỏi danh sách nút |
| `v0.3.31-beta1` | Giữ SELECT/START cũ khi giữ START+SELECT để thoát; mỗi lần bấm chỉ hiện một dòng; giữ MENU 2s để lưu log và thoát |
| `v0.3.32-beta1` | Kênh cập nhật beta riêng cho OTA (mặc định stable); sửa so sánh `beta10 > beta9` để beta mới luôn được đề nghị |
| `v0.3.33-beta1` | Nút mặt theo vị trí (B/A/Y/X, do layout Nintendo); MENU gửi nút PS (bit 12); dừng phiên bằng giữ MENU 2s thay phím B |
| `v0.3.34-beta1` | Mục chọn profile nút trong menu Bluetooth (ps/labels, lưu settings, backend nhận `--profile`) |
| `v0.3.35-beta1` | Giao diện mới: 2 theme tối/sáng (Cài đặt), chip footer đo theo chữ, chọn hàng kiểu accent-bar, ellipsis/wrap dùng chung, hết chữ tràn/chồng |
| `v0.3.36-beta1` | Tiêu đề hiện mã HW thay CHI; menu lùi xuống lộ hết dòng hướng dẫn remote; dòng thoát Bluetooth xuống 2 dòng, hết cắt dở |
| `v0.3.36` | **Stable**: chốt dãy beta tay cầm + UI. Đã kiểm trên Android (nút PS, MENU 2s, OTA beta). iOS chưa nhận gamepad generic — làm profile DS4/Xbox riêng sau stable |
| `v0.3.37-beta1` | Profile `ds4` thử nghiệm cho iPhone: descriptor 442 byte đã đối chiếu kernel, report 0x11 + CRC32, trả lời feature 0x02/0x05/0x06/0x09/0x12, tên adapter "Wireless Controller". Cần iPhone thật kiểm chứng |
| `v0.3.38-beta1` | iPhone nối rồi im lặng (0 giao dịch control) = thiếu nhận diện: profile `ds4` thêm bản ghi PnP VID 054C/PID 09CC và đổi tên adapter qua `hciconfig` (D-Bus từ chối trên máy này). Report giữ nguyên vì chưa có bằng chứng sai |
| `v0.3.39-beta1` | iPhone đã hỏi feature `0xA3` (firmware info) nhưng bị từ chối + `0x02` đã trả lời: nay trả lời `0xA3` đủ 48 byte + CRC. Tên cũ trên iPhone là do cache từ lần pair trước — phải Quên thiết bị rồi ghép lại |
| `v0.3.40-beta1` | Chơi game iPhone rớt link đều 1.5–3 phút/lần ở cự ly 20cm, phía mình không lỗi: gửi lại report mỗi 4s như DS4 thật (loại trừ link chết vì im lặng), và mỗi lần mất kênh ghi rõ lý do (peer đóng / lỗi đọc / lỗi gửi) để vòng sau biết bên nào cắt |
| `v0.3.40` | **Stable**: profile DualShock 4 cho iOS đã kiểm chứng trên iPhone; bỏ nhãn thử nghiệm và thêm menu INFO với QR ủng hộ tác giả |
| `v0.3.41-beta1` | Tiêu đề theo tên máy thật (Brick Pro/Smart Pro S, lạ thì "TrimUI"), bỏ chữ PS5 thừa ở subtitle |
| `v0.3.42-beta1` | Tắt luồng PS5 bằng cờ `PS5_ENABLED=False`: không quét cổng 9302, pair/guide/wakeup/stream từ chối PS5, code và test PS5 giữ nguyên để bật lại sau |
| `v0.3.43-beta1` | Quản lý sóng theo đề xuất người dùng: tắt Wi-Fi khi mở tay cầm (mở lại đúng trạng thái cũ khi dừng mọi kiểu), tắt discovery ngay khi đã nối. Crash tự phục hồi qua trap/recovery, reboot càng sạch (Stock OS tự dựng Wi-Fi/BT) |
| `v0.3.44-beta1` | SSH vào máy tìm ra `ifconfig up` không xin lại IP (udhcpc không tự renew) nên SSH chết sau phiên: restore giờ up + `wpa_cli reassociate` + `killall -USR1 udhcpc` + đợi IP thật, ghi kết quả vào log. Tunnel-loop tự nối lại khi có mạng |
| `v0.3.45-beta1` | Rớt GRID là tắc tạm bị cắt oan: tắc thì shedding báo cũ + giữ link, chỉ cắt khi tắc liền quá 15s. Nhãn profile ghi rõ máy (Android/iPhone), ba profile không gộp được vì khác protocol |
| iPhone vòng 3 (2026-10-05) | **Hiện DUALSHOCK 4 + đủ nút trên `v0.3.39-beta1`**: MENU tới nơi (tester mở games.apple.com), PS=bit12 xác nhận. Theo dõi: Brick tự reboot 1 lần, pair lần 1 thất bại lần 2 xong |

## 10. Kiểm thử và build gate

Lệnh chuẩn:

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

128 unittest của source hiện tại bao phủ:

- TLS context và CA fallback.
- OTA version/fallback/hash/settings exclusion.
- Uploader sanitize/dedupe/pending concurrency/identity và HTTPS relay.
- Reproducible release bytes trên Windows/Linux.
- Discovery packet/ports/parser.
- Registration crypto và target validation.
- Input mapping, settings/modal edges và home flow.
- Native launcher không đưa khóa vào script.
- Brick `sun50iw10` chọn runtime riêng; Spruce `sun55iw3` giữ runtime hệ thống.
- Màn hình THỬ NÚT: một lần bấm chỉ gán một nút, A/B không còn là phím điều
  hướng khi đang thử chúng, giữ phím không nuốt bước sau, từ chối lưu bản đồ trùng mã.
- Bản đồ nạp vào cũng bị từ chối nếu có hai nút chung mã phím.
- Dừng chủ động không báo lỗi backend, mã lỗi thật vẫn báo.

Ngoài ra `bluetooth-native` có `go test` riêng, gồm:

- Report trung tính, hai joystick độc lập, trigger analog, deadzone.
- Bảng điều khiển ghi đè được (đổi cả nút lẫn axis).
- Quét cả 256 header HIDP: không giao dịch nào trả stall trần.
- Session control: suspend, resume, unplug, reset.
- SDP record phải là XML đúng; test parse bằng `encoding/xml`.
- Bản đồ có hai nút chung mã thì bị báo tên, không dùng.

> Test Python **không được** để `files/` thật trên `sys.path`. `rh.paths` suy ra
> `APP_DIR` từ vị trí module, nên import `rh` từ thư mục nguồn sẽ ghi `device_id`
> thật vào `files/settings.json`. Mọi lớp test phải copy `files/` sang thư mục tạm
> rồi import từ đó.

Verifier kiểm:

- Tag/version/base URL.
- CA checksum, ELF64 AArch64 và checksum cố định của 14 thư viện Brick.
- Manifest source hash và từng payload trong ZIP.
- ZIP/sidecar SHA-256.
- File bắt buộc và file cấm.
- `settings.json` mặc định không có generated device ID.
- `reporting.json` dùng HTTPS không credential/query và source không chứa token.

## 11. Trạng thái chốt

1. Smart Pro S/Spruce và Brick Pro Stock OS đều đã stream PS4 thật thành công.
2. Giữ một release chung với runtime Brick cô lập theo model; chưa cần tách OS.
3. Giữ baseline Smart Pro S `720p30/4000`; Brick đã ổn ở `540p30/3000`.
4. Không sửa pair/native/input nếu không có Issue mới chứng minh regression.
5. `setterm: not found` đã được chặn bằng shim trong `launch.sh`; H264 `no frame!`
   lúc khởi động và server shutdown khi kết thúc phiên vẫn là cảnh báo vô hại.
6. `v0.4.0-beta2` là bản PS5 cuối để lưu lịch sử thử nghiệm. PS4/native giữ
   nguyên từ binary đã được xác nhận hoạt động; không mở thêm roadmap PS5.
7. `v0.3.27-beta1` là beta tay cầm Bluetooth, cố ý **không** đánh dấu latest để OTA
   không tự đẩy lên thiết bị đang dùng ổn định.
8. `test_relay_is_the_only_upload_transport` chạy thi thoang (khoảng 1/8 lần
   chạy cả suite) báo fail nhưng chạy riêng luôn đạt. Đây là test flaky có sẵn
   từ trước, không liên quan tay cầm Bluetooth; `log_uploader.py` và
   `test_release_and_logs.py` không thay đổi. Khi build nên chạy suite vài lần
   để phân biệt lỗi thật với lỗi này.
9. Bản đồ nút đã **đo trên máy thật** bằng `BrickButtons.log` (2026-10-03) và đưa
   vào mặc định Go + Python. Phát hiện: **A/B và X/Y đảo** (A=305, B=304,
   X=308, Y=307), **L3=317 và MENU=316 đều có thật**, **L2/R2 là analog không có
   mã phím**. Bản giải mã bitmap `B: KEY=` ở `docs/BLUETOOTH_GAMEPAD.md` mục 2 là
   **sai** — đã đánh dấu cảnh báo, không dùng làm nguồn ánh xạ nữa.
10. Giả thuyết "firmware báo mã phim không ổn định" (issue #67) **chưa được chứng
    minh**: log ghi thô không có dòng nào chứa `codes=`, tức không mã thừa nào được
    phát. Chỉ nên coi là câu hỏi mở.
11. Profile máy chủ PC/Xbox/PS4 (như Padpod) chưa làm: cần descriptor DS4 và Xbox
    Wireless chính xác, không được đoán.
