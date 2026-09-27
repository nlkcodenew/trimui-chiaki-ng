# trimui-chiaki-ng — trạng thái dự án v0.3.21

> Cập nhật: 2026-09-25. Đây là hồ sơ kỹ thuật tổng hợp; trạng thái thao tác cho
> session tiếp theo nằm trong `docs/NEW_SESSION_HANDOFF.md`.

## 1. Release hiện tại

`v0.3.21` là hotfix quản lý nguồn: menu không còn giữ `/tmp/stay_alive`, marker
chỉ tồn tại khi native stream chạy và menu tự đóng sau 15 phút không thao tác.

| Mục | Giá trị |
|---|---|
| Latest stable | `v0.3.22` |
| Wake prerelease | `v0.3.23-beta12` |
| Tag | `v0.3.21` |
| Feature commit | release commit |
| OTA files | 126 |
| ZIP entries | 129 |
| ZIP SHA-256 | `dd24c2ea2a61ea06020d75babe9c5d66705a4288f0067499be818f25b90fac22` |
| Unittest | 86/86 đạt |
| Native SHA-256 | `a8d6bfdb846a501ed9525c378a4f2f9c0c4d64a88aadeb098e1093d4b0378d7d` |
| CA SHA-256 | `f66dff1bdf8f96060b8177976f8b7d9254bc89bc4db933d769f7384d28480bc9` |

GitHub Release có ba asset:

- `manifest.json`.
- `trimui-chiaki-ng-v0.3.21.zip`.
- `trimui-chiaki-ng-v0.3.21.zip.sha256`.

GitHub Actions đã hoàn tất thành công. Ba asset công khai tải qua
Release `v0.3.21` có 126 file OTA, 129 entry ZIP và SHA-256 ở bảng trên.

Manifest không chứa `settings.json`, secrets, log hoặc marker runtime. Từ
`v0.3.22-beta5`, ZIP cũng không chứa `settings.json`, `paired_hosts.json` hoặc
`chiaki.conf`; app tự tạo settings ở lần chạy đầu và cài đè giữ nguyên dữ liệu.

## 2. Ma trận nền tảng

| Nền tảng | UI/app | TLS/OTA | Pair/stream | Ghi chú |
|---|---:|---:|---:|---|
| Smart Pro S/TG5050 | Đã xác nhận | Đã dùng OTA | Đã stream PS4 thật | Baseline chính |
| Spruce OS | Đã xác nhận | Không thay đổi | Stream tốt ở `v0.3.14` | Issue `#35`, model `sun55iw3` |
| Brick Pro Stock OS | Đã xác nhận | Đã OTA đến `v0.3.16` | Đã stream PS4 thật | Issue `#39`, video/audio/input đạt |
| PS4 Pro 9.00/GoldHEN | — | — | Pair/session pre-10 đạt | Không cần PSN |
| PS5/H265 | — | — | Đã vô hiệu hóa từ `v0.3.22-beta8` | Ngoài phạm vi phát triển |

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
- `files/rh/state.py`: state runtime và lưu `settings.json` atomically.

### Remote Play

- `files/rh/chiaki.py`: discovery, registration wrapper, wakeup cũ và launcher.
- `files/rh/ps4_regist.py`: handshake registration PS4.
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
- `CHI-xxxx`: ID ngẫu nhiên của lần cài/thẻ, có thể đổi; chỉ dùng chẩn đoán phụ.
- `HW-xxxxxxxxxxxx`: SHA-256 pseudonym từ nguồn phần cứng ưu tiên, là mã chính.
- `APP-xxxxxxxxxxxx`: fallback nếu không có ID phần cứng.

Từ beta6, title Issue và tiêu đề app chỉ ghi `HW-...`/`APP-...`; model và
`CHI-...` vẫn nằm trong body nhưng không dùng để đối chiếu thiết bị.

Máy Brick Pro của người dùng đang thử có hardware ID ổn định
`HW-C3A2FEFAB3F5`. Các ID cài đặt `CHI-E545`, `CHI-E4DF`, `CHI-EC6F` đã xuất
hiện trên cùng thiết bị; beta4 từng ghi đè `settings.json` và làm mất pair.

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

- Chỉ quét PS4 tới destination port `987`; PS5 port `9302` bị vô hiệu hóa.
- Một source socket duy nhất bind `9303–9319` cho cả broadcast và unicast PS4.
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

> Điều tra đầy đủ và điểm dừng hiện tại nằm tại
> `docs/PS4_WAKEUP_INVESTIGATION.md`. Wakeup đang tạm dừng theo yêu cầu người
> dùng; không tự triển khai beta13 từ các giả thuyết bên dưới.

Lịch sử:

- `v0.3.7`: host paired offline và WAKEUP.
- `v0.3.8`: packet khớp upstream, source port đúng, timeout diagnostic.
- `v0.3.9`: broadcast LAN và retry hai vòng.
- Issue `#26–#30`: console vẫn không phản hồi trong môi trường thật.
- `v0.3.10`: tắt WAKEUP/offline host trong UI, trở lại bật PS4 bằng tay.

Beta `v0.3.22-beta6` giữ ZIP đúng `Apps/Chiaki/`, gửi SRCH broadcast và unicast
tới IP PS4 đã pair, đồng thời report `discovery_ps4_standby_not_found` một lần
mỗi phiên nếu Rest Mode vẫn không phản hồi. App phục hồi host đã pair dưới trạng
thái `offline`; khi người dùng bấm **A**, WAKEUP được gửi ngay tới IP đã lưu rồi
polling `ready` trên cùng UDP socket trong tối đa 25 giây. Beta không tự wake khi
scan và không thay đổi WoWLAN của TrimUI. Beta5 còn loại dữ liệu người dùng khỏi
ZIP, log `system-version → target` và trạng thái có/không Account-ID mà không ghi
giá trị.
Issue diagnostics `#29–#31` cho thấy `80108b03` sau khi mất pair; cần đóng/mở
lại **Add Device** để tạo PIN mới thay vì retry PIN cũ. Nhánh ổn định `v0.3.21`
giữ nguyên.

Issue `#32`, `#33`, `#36` đều là log beta4, cùng hardware ID
`HW-C3A2FEFAB3F5`. `#32` xác nhận pair thành công với Account-ID zero; `#36`
xác nhận Rest Mode trả `0 host` dù đã SRCH broadcast + unicast tới IP paired.
Beta6 vì vậy khôi phục host paired `offline` trong UI và gửi WAKEUP trực tiếp
trước khi có response `standby`, sau đó polling `ready` trên cùng socket.

Issue beta6 `#41/#42` ghi nhận
`_paired_credentials() takes 1 positional argument but 2 were given`. Đây là
lỗi wrapper Python xảy ra trước khi gửi WAKEUP, không phải PS4 từ chối packet.
Beta7 gọi đúng `_paired_credentials(addr)`, kiểm credential là PS4 và thêm test
tích hợp đọc `paired_hosts.json` thật rồi xác nhận packet đầu tiên là WAKEUP.

Issue `#58` của beta11 xác nhận một DDP WAKEUP được gửi, PS4 bắt đầu trả `620
Standby` sau khoảng 25 giây nhưng không chuyển sang `200 Ready`. Beta12 được tạo
để poll mỗi 500 ms và gửi thêm một WAKEUP sau phản hồi Standby đầu tiên.

Issue `#59/#60` của beta12 cho kết quả khác: scan vẫn `0 host`, WAKEUP ban đầu
được kernel chấp nhận đủ 135 byte nhưng 240 SRCH trong 120,2 giây không nhận bất
kỳ phản hồi nào. Vì `standby_seen=False`, WAKEUP thứ hai chưa từng được gửi;
beta12 chưa kiểm thử được giả thuyết chính của nó.

Rà soát desktop cho thấy beta12 mới mô phỏng một phần. Desktop giữ discovery
service/socket sống lâu, quét 500 ms, tái sử dụng socket discovery để wake, tạo
session kết nối ngay sau wake và có thể gọi wake lại trên nhiều update Standby
khi session còn connecting. App beta12 dùng transaction riêng, đợi Ready trước
khi stream và chỉ cho phép một WAKEUP bổ sung. Chưa có desktop control hoặc
packet capture trên cùng PS4/LAN, nên chưa biết khác biệt nào là nguyên nhân.

Không tiếp tục sửa packet hoặc phát hành beta mới nếu chưa đọc tài liệu điều tra
và chưa có phép thử đối chứng/capture giúp tách trạng thái console, LAN và code.

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
| `v0.3.21` | Chỉ giữ `stay_alive` khi stream; menu idle 15 phút tự đóng để tránh hao pin |
| `v0.3.22-beta6` | Wake host PS4 paired `offline`; title app/Issue dùng mã `HW-...` ổn định |
| `v0.3.22-beta7` | Sửa crash đọc credential khiến beta6 chưa gửi được packet WAKEUP |
| `v0.3.22-beta8` | Tắt PS5; discovery PS4 dùng một socket để tránh cạnh tranh UDP port nguồn |
| `v0.3.22-beta9` | Gửi WAKEUP unicast và directed broadcast của subnet để tránh phụ thuộc ARP |
| `v0.3.23-beta10` | Giữ DDP upstream, thêm WOL cổng 9/7 theo MAC pair và log trạng thái ARP đã ẩn dữ liệu |
| `v0.3.23-beta11` | Phép thử đối chứng: một DDP WAKEUP unicast chuẩn Chiaki, không WOL/broadcast/retry, chờ 120 giây |
| `v0.3.23-beta12` | Poll 500 ms như desktop; gửi thêm đúng một DDP WAKEUP khi lần đầu nhận 620 Standby |

Kết quả máy thật beta12: Issue `#60` không nhận `620`, nên mô tả trên là hành vi
dự kiến của code chứ chưa phải đường chạy đã được xác nhận trên console.

## 10. Kiểm thử và build gate

Lệnh chuẩn:

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

97 unittest của source hiện tại bao phủ:

- TLS context và CA fallback.
- OTA version/fallback/hash/settings exclusion.
- Uploader sanitize/dedupe/pending concurrency/identity và HTTPS relay.
- Reproducible release bytes trên Windows/Linux.
- Discovery packet/ports/parser.
- Registration crypto và target validation.
- Input mapping, settings/modal edges và home flow.
- Native launcher không đưa khóa vào script.
- Brick `sun50iw10` chọn runtime riêng; Spruce `sun55iw3` giữ runtime hệ thống.

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
5. `setterm: not found`, H264 `no frame!` lúc khởi động và server shutdown khi
   kết thúc phiên hiện là cảnh báo vô hại, không phải lỗi stream.
6. Từ `v0.3.22-beta8`, PS5 bị vô hiệu hóa ở discovery/UI/pair/wake/stream; giữ
   trường dữ liệu tương thích để cài đè không làm hỏng cấu hình cũ.
7. Điều tra wake dừng tại beta12. Stable không bị ảnh hưởng; không tạo beta13
   cho tới khi người dùng mở lại công việc và có đối chứng desktop/capture phù hợp.
