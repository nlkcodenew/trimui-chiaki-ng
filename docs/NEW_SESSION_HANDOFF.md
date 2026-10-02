# Bàn giao session mới — trimui-chiaki-ng v0.3.26-beta1

> Cập nhật: 2026-10-02. Đọc file này trước khi tiếp tục dự án.

> **Ghi chú thay thế 2026-09-26:** phần PS5 đã dừng phát triển sau
> `v0.4.0-beta2`. Nội dung PS5 cũ trong handoff này chỉ là lịch sử. PS4 là nền
> tảng duy trì chính thức; xem `docs/PS5_STATUS.md` và `docs/PROJECT_STATUS.md`.

> **Ghi chú 2026-10-02:** việc hiện tại là tay cầm Bluetooth của Brick Pro. Đọc
> `docs/BLUETOOTH_GAMEPAD.md` trước — mục 2 và 3 chứa hai lỗi gốc đã tìm ra.

## 0. Việc đang chờ người dùng

`v0.3.26-beta1` đã đẩy lên GitHub Release dưới dạng **pre-release, không phải
latest**. Người dùng sẽ tự tải ZIP, cài đè, rồi chạy màn hình THỬ NÚT.

Cần chờ: kết quả THỬ NÚT (mã phím thật của L3/R3 và 8 nút còn lại) và phản hồi
sau khi thử trong game. Nếu có lỗi, yêu cầu gửi `Apps/Chiaki/BrickBluetooth.log`.

## 1. Trạng thái ngắn gọn

- `v0.3.26-beta1` là beta tay cầm Bluetooth cho Brick Pro Stock OS. Đã tìm và sửa
  hai lỗi gốc: bảng điều khiển HIDP sai toàn bộ so với đặc tả, và bảng ánh xạ nút
  giả định `bit = key - 304` trong khi thiết bị báo mã phím không đều.
- Bluetooth đã kết nối thật với iPhone (`D8:DE:3A:21:25:E6`); phiên thứ hai 9.2s vì
  tự kết nối lại. Phiên đầu 42.7s là thời gian người dùng tìm thiết bị trong Cài đặt.
- 121/121 unittest và `go test` đều đạt; release verifier đạt.

- Repo: `https://github.com/nlkcodenew/trimui-chiaki-ng`.
- Workspace: `E:\Trimiu Brick Pro\Project APPS\chiaki-ng`.
- Nhánh: `main`.
- Release khuyến nghị: `v0.3.20` (không đổi).
- Beta đang thử: `v0.3.26-beta1` — cố ý **không** phải latest để OTA không tự đẩy.
- SHA-256 ZIP `v0.3.26-beta1`:
  `0df44f77dfe792fbb41f0c5d33b40d604693157b77826226bde5435d89ac0fc6`.
- Số file OTA/ZIP: 136/139; không có settings/secrets/log.
- Native `brick-pro-bt` SHA-256:
  `9fc52970bc64488cb454132f29fd023781ee21a8e56efbb251ab37e8214eac74`.

### Cách tạo và kiểm tra beta (không phải latest)

Beta được đẩy bằng tag có dấu `-`, ví dụ `v0.3.26-beta1`. Workflow
`.github/workflows/release.yml` tự đặt `prerelease: true` khi tag chứa `-`, nên
GitHub không tính nó là latest và OTA không tự tải về.

Lệnh build cục bộ:

```powershell
wsl -d Ubuntu -- bash -lc "cd '/mnt/e/Trimiu Brick Pro/Project APPS/chiaki-ng/bluetooth-native' && gofmt -l . && go vet ./... && go test ./... && CGO_ENABLED=0 GOOS=linux GOARCH=arm64 GOARM64=v8.0 go build -buildvcs=false -trimpath -ldflags='-s -w' -o ../files/bin/brick-pro-bt ."
python -m unittest discover -s tests
python tools\make_release.py
python tools\verify_release.py
```

Sau khi build native, phải cập nhật `files/docs/bluetooth-native-build.json`
(hash, size, version) trước khi đóng gói.

## 2. Mục tiêu và ràng buộc

Mục tiêu hiện tại là giữ một gói dùng chung cho:

- TrimUI Smart Pro S/TG5050 và Spruce OS.
- TrimUI Brick Pro Stock OS.

Các nguyên tắc không được phá vỡ:

1. Không tắt xác minh TLS certificate hoặc hostname.
2. Không đọc, in, commit hoặc đưa token/khóa ghép nối vào log/Issue/Release.
3. Không đưa `settings.json` vào OTA manifest; không ghi đè cấu hình người dùng.
4. Không thay native stream, pair/session pre-10 hoặc SDL/input nếu không có bằng
   chứng và kiểm thử máy thật.
5. Không coi quét `0 host`, người dùng hủy hoặc fallback OTA thành công là lỗi.
6. Nếu các OS thật sự cần native binary/thư viện khác nhau, tách release theo OS
   thay vì sửa gói chung theo cách làm hỏng nền tảng đang hoạt động.

Không cần tách release: runtime Brick được cô lập theo model và cả Brick/Spruce
đều đã stream thật thành công bằng cùng native binary.

## 3. Brick Pro Stock OS — trạng thái máy thật

Log ngoài repo:

- `D:/Apps/Chiaki/Chiaki-debug.log`.
- `D:/Apps/Chiaki/Chiaki-loi.txt`.

Không đọc nội dung token trong `D:/Apps/Chiaki/secrets.json`. Chỉ kiểm tra tên,
tồn tại và metadata khi cần.

### Chuỗi cập nhật đã xác nhận

1. Bản trước `v0.3.11` không OTA được vì Stock OS thiếu CA phù hợp.
2. Người dùng cài ZIP `v0.3.11` thủ công một lần.
3. OTA `v0.3.11 → v0.3.12` thành công: manifest, ba file thay đổi, SHA-256 và
   restart đều đúng.
4. OTA `v0.3.12 → v0.3.13` thành công: 12 file được tải, kiểm hash, cài và
   restart đúng.
5. OTA lên `v0.3.14` đã thành công; Issue `#36`/`#37` được gửi đúng từ Brick.
6. OTA `v0.3.15 → v0.3.16` thành công; stream PS4 thật hoạt động đầy đủ.

### Pair và lỗi stream v0.3.14

- Pair không lỗi: log có `registration success`, `key_type=2`, target `1000`.
- Native helper thoát `127` trước session vì thiếu `libjson-c.so.5`.
- Loader chỉ báo dependency thiếu đầu tiên; closure từ SDK gồm 14 thư viện,
  khoảng 20 MB chưa nén và không thiếu SONAME ngoài glibc hệ thống.
- `v0.3.15` chỉ thêm `libs/brick-stock` làm fallback sau library Stock OS trên
  model `sun50iw10`, tránh override SDL/video/audio hệ thống của Brick.
- Spruce `sun55iw3` tiếp tục dùng runtime `system`; Issue `#35` xác nhận stream
  `v0.3.14` vẫn hoạt động tốt.

Issue `#38` ở `v0.3.15` tiến thêm một bước: loader đã tìm đủ thư viện nhưng lấy
`/usr/lib/libssl.so.1.1` và `libcrypto.so.1.1` của Stock OS. Hai file này có cùng
SONAME nhưng không export `OPENSSL_1_1_1`. Bundle SDK có đúng symbol đó.
`v0.3.16` dùng `LD_PRELOAD` với đường dẫn tuyệt đối tới đúng hai file bundle;
SDL/FFmpeg vẫn ưu tiên Stock OS và Spruce không nhận preload.

Issue `#39` xác nhận kết quả cuối trên Brick `sun50iw10`:

- Hình, âm thanh và input hoạt động khi chơi thực tế.
- Native stream kết thúc bình thường với exit `0`.
- `8968 rendered / 0 lost / 0 FEC`; phần lớn 29,4–30,2 FPS.
- `setterm: not found`, một H264 `no frame!` lúc khởi động và server shutdown
  khi kết thúc phiên là cảnh báo vô hại, không phải regression.

Trong lần lên `v0.3.13`, URL GitHub Release lỗi DNS lúc `10:38:46`:

```text
Name or service not known
```

Raw GitHub fallback bắt đầu ngay sau đó, tải manifest thành công, rồi toàn bộ OTA
hoàn tất. Đây là lỗi nguồn trung gian, không phải lỗi OTA kết thúc. `v0.3.14` sửa
cách ghi log:

- nguồn lỗi nhưng fallback thành công → `INFO`, không Issue;
- mọi nguồn thất bại → `WARNING`, trạng thái cuối và GitHub Issue.

### Định danh thiết bị

`v0.3.13` ghi nhận máy Brick Pro hiện tại:

- Model: `sun50iw10`.
- ID cài đặt/thẻ: `CHI-E545`.
- ID phần cứng băm: `HW-C3A2FEFAB3F5`.

`RH-5930` trong RetroHub là ID ngẫu nhiên của RetroHub, không phải serial máy.

`files/rh/device_identity.py` ưu tiên:

1. Device-tree/SoC serial hoặc `sunxi_chipid` hợp lệ.
2. Permanent/current Wi-Fi MAC.
3. `machine-id`.
4. Fallback `APP-...` từ ID cài đặt nếu không có nguồn phần cứng.

Chỉ pseudonym SHA-256 rút gọn được gửi. Uploader còn lọc raw MAC, serial,
`sunxi_chipid` và machine-id nếu chúng vô tình xuất hiện trong log.

### Sự cố hai thư mục Chiaki

Hai directory entry cùng tên là hỏng exFAT do rút cáp khi đang I/O, không phải
updater cố ý tạo thư mục. `chkdsk D: /F` đã sửa entry và đổi thư mục trùng thành
`CHIAKI-1`. Sau khi xóa bản cũ, copy sạch `v0.3.11` và OTA lại, lỗi không tái hiện.

Không rút cáp/thẻ trong khi máy hoặc Windows đang đọc ghi. `fsync` trong updater
chỉ giảm cửa sổ chưa flush, không thể chống ngắt vật lý.

## 4. TLS và OTA

Các file chính:

- `files/certs/cacert.pem` — Mozilla CA bundle đã kiểm checksum.
- `files/rh/ssl_context.py` — context dùng chung cho updater/uploader.
- `files/rh/updater.py` — manifest fallback, tải file, hash, staging, apply.
- `tools/make_release.py` — tạo manifest/ZIP tái lập giữa Windows và Linux.
- `tools/verify_release.py` — build gate và kiểm từng payload ZIP.

SHA-256 CA bundle:
`f66dff1bdf8f96060b8177976f8b7d9254bc89bc4db933d769f7384d28480bc9`.

TLS phải luôn giữ:

- `verify_mode == ssl.CERT_REQUIRED`.
- `check_hostname == True`.
- Không có `CERT_NONE`, `_create_unverified_context` hoặc
  `check_hostname = False` trong app/updater/uploader.

Thứ tự manifest mặc định:

1. GitHub Release `latest/download/manifest.json`.
2. Raw GitHub `main/manifest.json`.
3. Proxy phù hợp với cấu hình URL.

Quy tắc OTA:

- Chỉ popup khi remote version mới hơn `APP_VERSION`.
- Lệch hash trong cùng version không popup.
- `settings.json` bị loại ở build và runtime.
- Mọi file tải về phải khớp SHA-256.
- Staging file được flush/`fsync`; thư mục đích được `fsync` sau replace.
- `rh/version.py` được apply cuối cùng.
- Manifest release và fallback `main` phải có cùng payload hash.

## 5. GitHub Issue uploader

Từ `v0.3.17`, app chỉ dùng `issue_relay_url` từ:

- `Apps/Chiaki/reporting.json` trong release, hoặc
- biến môi trường `CHIAKI_ISSUE_RELAY_URL` khi phát triển.

Relay mẫu nằm ở `deploy/issue-relay/`. GitHub token chỉ là Cloudflare Worker
secret và trỏ tới repo private `nlkcodenew/trimui-chiaki-ng-diagnostics`.
Runtime không còn đường GitHub trực tiếp, không đọc token hoặc tên repo.
Worker đã deploy tại
`https://trimui-chiaki-issue-relay.issue-relay.workers.dev/report`. Worker
secret `GITHUB_TOKEN`, repo private, KV dedupe/rate-limit và E2E đều đã xác nhận;
Issue kiểm thử `#1` đã đóng, repo không còn Issue mở.

Không đọc file sai tên `secrets..json`; chỉ cảnh báo tên sai mà không log nội dung.

Issue title có dạng:

```text
[device-log][model][CHI-xxxx][HW-xxxxxxxxxxxx] vX.Y.Z reason fingerprint
```

Các lỗi có ý nghĩa được report:

- Manifest TLS/network thất bại sau khi hết fallback.
- Download/hash/staging/install/restart OTA thất bại.
- Exception của update modal.
- Socket discovery lỗi; không report kết quả bình thường `0 host`.
- Pair registration/screen/save lỗi.
- Pair PS5 bị chặn vì chưa hỗ trợ, với reason `pair_ps5_registration_unavailable`.
- Native helper thiếu hoặc chuẩn bị stream thất bại.
- Settings load/save/callback lỗi.
- Crash/exit code bất thường và chất lượng native stream.

Pending marker lưu tối đa nhiều reason khác nhau. Upload được khóa để tránh race;
fingerprint gồm reason nên hai lỗi khác loại trên cùng log vẫn tạo hai Issue,
trong khi retry cùng lỗi được dedupe.

## 6. Stream đã xác nhận

Stream thật đã xác nhận trên Smart Pro S/Spruce và Brick Pro Stock OS với PS4
Pro firmware 9.00/GoldHEN:

- Có hình, âm thanh và input qua LAN.
- Pair bằng PIN LAN, protocol pre-10, không dùng PSN.
- Mapping A/B/X/Y đã xác nhận đúng từ `v0.3.6`.
- Giữ START+SELECT khoảng 1,2 giây để thoát stream về app.
- Brick `v0.3.16` đạt `8968/0/0` rendered/lost/FEC trong Issue `#39`.

Profile ưu tiên:

- `720p30/4000`: Issue `#21`, khoảng `6565/2/0` rendered/lost/FEC, FPS ổn định
  29,8–30,0.
- `540p30/4000`: fallback tải thấp.
- Không ưu tiên `540p60/15000`: Issue `#20` có khoảng
  `40798/1357/295`, nhiều FEC/IDR/decoder warning.

PS4 đôi khi giữ lease Remote Play khoảng hai phút sau khi client đã shutdown.
Không pair lại hoặc bấm kết nối liên tục; chờ rồi thử lại.

WAKEUP đã thử unicast/broadcast ở `v0.3.7–v0.3.9` nhưng console trong môi trường
hiện tại không phản hồi. Từ `v0.3.10`, UI trở lại luồng bật PS4 bằng tay rồi quét.
Không tiếp tục sửa WAKEUP nếu không có môi trường mới chứng minh console có thể
được đánh thức.

Native binary hiện tại không thay đổi trong các bản vá Brick Pro. SHA-256:
`a8d6bfdb846a501ed9525c378a4f2f9c0c4d64a88aadeb098e1093d4b0378d7d`.

## 7. Trạng thái kết thúc session

- Không còn lỗi phát hành hoặc kiểm thử máy thật đang chờ xử lý.
- `v0.3.20` là latest; native/runtime giữ nguyên từ bản đã xác nhận trên Brick.
- Tiếp tục dùng `720p30/4000` trên Smart Pro S và `540p30/3000` trên Brick.
- Không thay native binary, pair/session hoặc SDL mapping nếu không có Issue mới.
- Release public có đủ ba asset; checksum, 126 OTA files và 129 ZIP entries đã
  đối chiếu từ asset tải lại, không chỉ từ build cục bộ.
- HTTPS relay production hoạt động; app không chứa GitHub token hoặc tên repo
  chẩn đoán private.

## 8. Lệnh kiểm tra

```powershell
Set-Location 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng'
git status --short
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

Kiểm tra an toàn bổ sung:

```powershell
rg -n "CERT_NONE|check_hostname\s*=\s*False|_create_unverified_context" files/rh files/app.py tests tools
git hash-object files/bin/chiaki-stream
git rev-parse HEAD:files/bin/chiaki-stream
git hash-object files/settings.json
git rev-parse HEAD:files/settings.json
```

Trước commit/release, xác nhận không stage:

- `files/secrets.json` hoặc `files/secrets..json`.
- `files/settings.json` có dữ liệu máy thật.
- `Chiaki-debug.log`, `Chiaki-loi.txt`, `.pending_crash`.
- `dist/` hoặc khóa ghép nối.

## 9. Quy trình phát hành

1. Tăng `APP_VERSION` và release note.
2. Chạy compile, toàn bộ unittest, build và verifier.
3. Kiểm manifest có CA/native, không có settings/secrets/log.
4. Commit/push `main`.
5. Tạo annotated tag đúng version và push tag.
6. Chờ GitHub Actions tạo ba asset.
7. Tải lại ZIP/checksum/manifest, đối chiếu SHA-256 và kiểm `latest`.
8. Không retag một release đã công bố; nếu payload app đổi, tăng version mới.

## 10. Prompt tiếp tục gợi ý

```text
Tiếp tục repo E:\Trimiu Brick Pro\Project APPS\chiaki-ng.
Đọc docs/NEW_SESSION_HANDOFF.md và docs/PROJECT_STATUS.md trước.
Latest/release hiện tại là v0.3.20. Bản này khóa tối đa 720p, dùng HTTPS relay
không token client, có hướng dẫn 8 bước và hiện CHI-xxxx cạnh version. Brick
sun50iw10 đã stream thật thành công; Issue #39 đạt 8968/0/0
rendered/lost/FEC và exit 0. Spruce sun55iw3 vẫn dùng runtime system. Không tắt
TLS, không đọc/tiết lộ token và không sửa native/pair/input nếu không có Issue
mới chứng minh regression.
```
