# trimui-chiaki-ng — Trạng thái dự án (đến v0.3.4)

> Tài liệu tổng hợp cho session mới. Cập nhật: 2026-09-23.
> v0.3.2 sửa đăng ký/session pre-10 cho PS4 Pro firmware 9.00 GoldHEN.
> **Mốc đã đạt trên máy thật:** stream có hình, nhận input và chơi được qua LAN.
> v0.3.3 giữ nguyên giao thức đã chạy tốt, giảm tải log/render, thêm báo cáo chất
> lượng 5 giây, bitrate 3000 kbps và lựa chọn 1080p để đo giới hạn máy thật.
> v0.3.4 thêm xóa/giới hạn log an toàn, retry Issue pending khi Thoát và fallback
> nút vật lý START/SELECT để trở về menu mà không cần tắt PS4.
>
> Bàn giao session mới và quy trình gửi log: `docs/NEW_SESSION_HANDOFF.md`.

## Stream native v0.3.4

- Binary `files/bin/chiaki-stream` là ELF AArch64 build bằng SDK TG5050 chính hãng.
- Session dùng khóa thật từ `paired_hosts.json`; khóa đi qua file tạm `0600`,
  được native xóa ngay khi đọc và không xuất hiện trong command line/log.
- Renderer nhận frame H264 từ `chiaki_ffmpeg_decoder`, chuyển về YUV420P khi
  cần và hiển thị bằng SDL texture đúng tỉ lệ trên màn 1280×720.
- Audio giải mã Opus và phát bằng SDL queued audio; input map A/B/X/Y, D-pad,
  analog, L/R, trigger, L3/R3, START/SELECT/PS; hỗ trợ rung đơn.
- Menu đóng SDL trước khi chạy native và tự mở lại khi stream kết thúc.
- Giữ START+SELECT 1,2 giây để thoát. Native stdout/stderr và `ldd` được ghi
  vào `Chiaki-debug.log`/`Chiaki-loi.txt`.
- Trace packet/frame native không còn bật theo `enable_logging`; mặc định chỉ ghi
  INFO/WARNING/ERROR, buffer stdout 64 KB và không `fflush` từng dòng.
- Renderer cache đích hiển thị, bỏ clear toàn màn hình khi frame phủ kín 1280×720
  và ghi tên renderer/accelerated/vsync để phát hiện fallback software.
- Mỗi 5 giây ghi `rendered`, `lost`, `fec`, FPS thực và số log bị lược; khi thoát
  bình thường launcher tự gửi Issue `native_stream_quality`.
- Cài đặt có thêm bitrate 3000 kbps và 1080p. 1080p được decode rồi scale về màn
  1280×720, chỉ dùng để thử sức decoder/GPU.
- Màn hình chính hiện rõ `giữ START + SELECT 1,2 giây để về menu`. Native nhận
  cả GameController và raw joystick button 8/9 cho riêng tổ hợp thoát, tránh lỗi
  mapping khiến người dùng trước đây phải tắt PS4 mới quay lại menu. Khi đủ tổ
  hợp, native nhả OPTIONS/SHARE khỏi input gửi sang PS4 để tránh tác dụng phụ.
- **Cài đặt → XÓA LOG CŨ** có xác nhận; không xóa nếu còn `.pending_crash` để
  bảo vệ report chưa gửi. Launcher cắt giữ phần cuối log native sau mỗi phiên.
- Khi chọn **THOÁT**, launcher retry report pending đồng bộ rồi mới đóng; nếu
  không có pending marker thì không tạo Issue mới không cần thiết.
- Đã xác nhận trên Smart Pro S thật ngày 2026-09-23: màn hình PS4 xuất hiện,
  điều khiển hoạt động và chơi game qua LAN được; cảm nhận ban đầu khá ổn.
- Chưa xong: xác nhận v0.3.4 trên máy thật, PS5/H265 và Internet/RUDP.

## 1. Mục tiêu

Viết app PS4/PS5 Remote Play cho TrimUI Smart Pro S (Allwinner A523 8xA55 2.0GHz, Mali-G57, 1GB RAM,
màn 1280x720, WiFi 6, firmware Linux 1.1.1 TG5050).
Mô hình hoạt động copy theo RetroHub: app Python + SDL nằm trong `Apps/Chiaki/` trên thẻ nhớ, chạy qua `launch.sh`.

## 2. Đã làm được

### Hạ tầng
- Repo: `https://github.com/nlkcodenew/trimui-chiaki-ng`, nhánh `main`
- Build release: `tools/make_release.py` quét `files/` -> `manifest.json` (sha256) + ZIP `App/Chiaki/...`
  với mode Unix đúng (0755 cho `.sh`), kèm file `.sha256`.
- Verify: `tools/verify_release.py` kiểm tra manifest/ZIP, cấm rò rỉ `secrets.json`, log runtime,
  chặn `settings.json` mặc định có `device_id`.
- CI: `.github/workflows/release.yml` (push tag `v*` -> checkout -> verify tag == `APP_VERSION` ->
  compileall -> make_release -> verify -> publish bằng `softprops/action-gh-release`).
- 38 unittest pass tại `tests/test_release_and_logs.py`.

### Ghép nối PS4 thật — v0.3.0-beta
- Xóa hoàn toàn `stub-rp-key-*`; chỉ báo thành công khi PS4 trả HTTP 200 và đủ `PS4-RegistKey`, `RP-Key`, `RP-KeyType`, MAC.
- Thực hiện đúng handshake upstream: UDP `SRC2`/`RES2` cổng 9295, TCP `/sie/ps4/rp/sess/rgst`, `RP-Version: 10.0`, HMAC-SHA256 và AES-128-CFB.
- Không kết nối dịch vụ PSN. PS4 firmware 9.00 dùng PIN LAN, Account-ID offline 8 byte bằng 0 và giao thức pre-10 (`/sce/rp/regist`, `RP-Version: 9.0`).
- Lưu riêng `psn_account_id`, `rp_key`, `rp_key_type`, `regist_key`, `server_mac`; tự vô hiệu dữ liệu giả của alpha.
- Sửa enum target theo đúng upstream (`800/900/1000/1000100`) và ưu tiên protocol header để PS4 không còn bị lưu thành PS5.
- Chưa hỗ trợ đăng ký PS5 trong beta; không tạo khóa giả khi người dùng thử PS5.
- Bản vá sau beta đầu tiên dùng AES-128-CFB thuần Python vì firmware máy thật không có executable `openssl`.

### OTA
- Fix lỗi vòng lặp RetroHub: `settings.json`, `secrets.json` không vào manifest/ZIP; `pending_files()`
  bỏ qua `settings.json`; `skipped_versions` chỉ chặn khi có version mới thực sự.
- Manifest dùng `release_tag: vX.Y.Z/files` và `base_url: .../vX.Y.Z/files` để tương thích updater cũ
  (ghép thẳng tag với path).
- Payload ưu tiên tag bất biến, fallback ghproxy/jsDelivr, kiểm SHA256.

### Sửa lỗi đã phát hiện trên máy thật
- v0.2.3: crash `SDL_GAMECONTROLLER_BUTTON_A` -> đổi sang enum số 0..14 (`files/rh/inputs.py`).
- v0.2.4: tiếng Việt không dấu -> chuyển toàn bộ VI sang có dấu (`files/rh/i18n.py`).
- v0.2.5: crash Cài đặt `language`/`current_lang` -> map key `current_lang` -> `language`.
- v0.2.6: popup Cập nhật nháy + không đóng + không tải được -> chuyển popup sang `edges`, close phải xóa
  `engine.active_modal`, sửa payload URL thiếu `/files/`, thêm log mạng chi tiết, tự restart sau cài.
- v0.2.7: A trong Cài đặt thoát ngay -> đổi A thành đổi giá trị + save, B thoát.
- v0.2.8: B vẫn save rồi mới thoát -> đổi B chỉ thoát (tồn tại ngắn), hiện version trên header.
- v0.2.9: Không thoát được Cài đặt khi kẹt -> thêm dòng cuối `QUAY LẠI →` (key `back`),
  mọi nút A/B/Trái/Phải tại dòng này đều pop về menu chính.
- v0.2.10: **Sửa tận gốc bug P0 "A và B đều chỉnh sửa"** (chi tiết ở mục 4.1).

### Ghi log
- `files/rh/logger.py`: 2 file `Chiaki-loi.txt` (WARNING+) và `Chiaki-debug.log`
  (DEBUG khi `enable_logging`), xoay vòng; hỗ trợ xóa an toàn và cap log native.
- `files/launch.sh`: giữ log khi có `.pending_crash`, xuất `CHIAKI_STDERR_LOG`,
  gửi quality sau stream, retry pending khi Thoát và cap kích thước log.

## 3. Tự động gửi log về GitHub — ĐÃ XÁC NHẬN TRÊN MÁY THẬT

**Mã đã xong:**
- `files/rh/log_uploader.py`: đọc `secrets.json` hoặc env `CHIAKI_GITHUB_TOKEN`, lọc token/PSN/IP/MAC,
  giới hạn 24KB/log, 60K body, fingerprint dedupe qua `.log_upload_state.json`, chỉ gửi khi có
  `.pending_crash`, retry ở lần khởi động sau, tạo Issue tiêu đề `[device-log] vX.Y.Z reason fingerprint`.
- `files/app.py` gọi `start_pending_upload("startup_retry")` và lazy import SDL sau logger.
- `files/launch.sh` gọi `python -m rh.log_uploader` khi crash.
- `files/secrets.example.json` mẫu, `.gitignore` loại trừ `secrets.json`.

Người dùng đã cấu hình fine-grained token chỉ có quyền Issues cho repo này và
thiết bị đã tạo Issue `#1`, `#2`. Từ v0.3.4, nút xóa log bảo vệ marker pending;
launcher retry report khi người dùng chọn Thoát.
  Đây là thiết kế bảo mật, không phải bug.

**Để kích hoạt:**
- Tạo fine-grained PAT chỉ cho repo `nlkcodenew/trimui-chiaki-ng`, quyền `Issues: Read and write`,
  copy `secrets.example.json` thành `secrets.json` trên thẻ nhớ, điền `github_token`. Không commit file này.

## 4. Bug / việc còn dở

### 4.1 P0 — Cài đặt: cả A và B đều chỉnh sửa → ĐÃ SỬA TRONG v0.2.10

**Triệu chứng bạn báo:** ở màn CÀI ĐẶT, cả nút A và nút B đều làm thay đổi giá trị; B không thoát ra menu chính.

**Nguyên nhân gốc (không phải `settings.py` như giả định ở v0.2.7–v0.2.9):** nằm ở `files/rh/inputs.py`.

1. **Map nút GameController bị ngược.** SDL2 đặt tên nút theo layout Xbox
   (`BUTTON_A` = ô Nam/south, `BUTTON_B` = ô Đông/east), còn TrimUI Smart Pro S dùng layout kiểu Nintendo:
   nút **A vật lý ở ô Đông**, nút **B vật lý ở ô Nam**. Map cũ `0: "btn_a", 1: "btn_b"` khiến
   **nút B vật lý phát ra `btn_a`**. Vì `settings.py` check `btn_a` trước `btn_b`, bấm B bị hiểu là "đổi giá trị".
   -> Đã đảo `A<->B` và `X<->Y`, giống hệt cách `repohubtool/files/rh/inputs.py` xử lý
   (`SDL_CONTROLLER_BUTTON_B # Physical A (East)` -> `btn_a`).

2. **Sự kiện JOY* trùng với CONTROLLER.*** Khi SDL đã mở GameController, mỗi lần bấm nút sinh
   **cả** `SDL_CONTROLLERBUTTONDOWN` **và** `SDL_JOYBUTTONDOWN` cho cùng một hành động.
   `feed_event` trước đây xử lý cả hai, nên một nút bấm tạo 2 edge ngược nhau
   (ví dụ B vật lý: controller id 0 + joy id 0 -> `btn_b`, đồng thời profile trimui `btn_a: [1]`/joy
   bị ánh xạ chéo gây nhiễu). -> Đã bỏ qua `JOY*` khi `self.controller is not None`,
   đúng như `repohubtool` làm (`elif not has_controller and etype == sdl2.SDL_JOYBUTTONDOWN`).

3. **Lớp phòng thủ trong `settings.py`:** `handle_input` giờ check `btn_b`/`quit` **trước** `btn_a`,
   nên dù hai edge đến cùng khung hình thì "thoát" vẫn thắng "đổi giá trị".
   Riêng dòng `back`: `B`/`quit` và `A`/`Left`/`Right` đều pop.

**Kiểm chứng:** thêm 3 test mới trong `tests/test_release_and_logs.py`:
- `test_gamecontroller_physical_b_maps_to_btn_b_not_btn_a` — B vật lý (id 0) phải ra `btn_b`.
- `test_joystick_events_ignored_when_controller_attached` — có controller thì JOY* bị bỏ qua, không sinh edge.
- `test_settings_integration_physical_buttons` — mô phỏng đúng chuỗi bấm máy thật: B vật lý chỉ pop (không save),
  A vật lý đổi giá trị + save.

Tổng 20/20 test pass; `make_release.py` + `verify_release.py` pass cho v0.2.10.

**Đã xác nhận trên máy thật (v0.2.10):** nút A đổi giá trị + lưu ngay, nút B thoát ra menu chính, dòng `QUAY LẠI` hoạt động. Bug P0 đã đóng.

### 4.2 P1 — Tiêu đề hiển thị version — ĐÃ XONG (v0.2.8)
`HomeScreen.get_header_title` trả `CHIAKI-NG vX.Y.Z`. Bạn thấy trên máy ở header rồi. Coi như đóng.

### 4.3 OTA — v0.2.10/v0.2.11 đã phát hành
`v0.2.9` và `v0.2.10` đã success trên Actions, `latest` hiện là `v0.2.10`. `v0.2.11` đang chuẩn bị phát hành
để sửa discovery. Máy đang ở `v0.2.10` đã xác nhận OTA `CẬP NHẬT -> CÀI NGAY` hoạt động.

### 4.4 P2 — Stream PS4 LAN đã triển khai; v0.3.4 đang kiểm thử
`HomeScreen` tạo phiên tạm bảo mật rồi thoát SDL menu; `launch.sh` chạy
`bin/chiaki-stream` và mở lại menu sau khi phiên kết thúc. Native helper dùng
`chiaki_session_*`, FFmpeg H264, SDL renderer/input/audio với cấu hình mặc định
720p30, 8000 kbps.

**Đã xác nhận thành công trên máy thật ngày 2026-09-23:** sau khi pair lại đúng
protocol pre-10, Smart Pro S hiển thị màn hình PS4 Pro GoldHEN 9.00, nhận input
và chơi game qua LAN được. Chất lượng ban đầu khá ổn nhưng drop FPS xảy ra khá
nhiều. P2 kết nối/stream cơ bản đã đóng; công việc tiếp theo là profiling và tune
decode/render/network để giảm drop FPS.

Issue `#2` cho thấy phiên kết nối thành công có `rendered=338`, `lost=21`, bitrate
mục tiêu 8000 kbps nhưng bitrate đo được chỉ khoảng 1,96–2,89 Mbps, RTT khoảng
946–988 ms, kèm nhiều FEC failure/missing unit/IDR request. Bằng chứng hiện tại
nghiêng mạnh về packet loss/độ trễ mạng; đồng thời `CHIAKI_LOG_ALL` và `fflush`
từng dòng xuống thẻ SD là tải phụ đáng kể. v0.3.3 xử lý phần tải log/render có thể
sửa trong app và bổ sung số đo để kiểm chứng phần mạng trên thiết bị.

### 4.5 P1 — Tự gửi log GitHub — ĐÃ XÁC NHẬN TRÊN MÁY THẬT
Người dùng đã cấu hình `Apps/Chiaki/secrets.json` bằng fine-grained token chỉ có
quyền Issues. App đã tự tạo Issue `#1` và `#2` trong repo, xác nhận marker crash,
lọc dữ liệu và retry startup hoạt động end-to-end. Không cần gửi hai file log bằng
tay trong các lần lỗi tiếp theo, trừ khi uploader mất token hoặc mất mạng kéo dài.

### 4.6 P0 — Quét PS4/PS5 luôn trả 0 host — ĐÃ SỬA TRONG v0.2.11
**Triệu chứng:** dù PS4 Pro bật cùng WiFi, `QUÉT MÁY PS4/PS5` luôn báo `0 host` (log 3 lần đều 0).
**Nguyên nhân gốc (đối chiếu `E:\Trimiu Brick Pro\Project APPS\chiaki-ng-tmp\lib\include\chiaki\discovery.h`):**
`CHIAKI_DISCOVERY_PORT_PS4=987`, `PORT_PS5=9302` là cổng **đích** gửi SRCH; `9303-9319` chỉ là cổng **nguồn** để nhận phản hồi.
Code cũ gửi SRCH tới chính `9303-9308` (cổng nguồn) nên packet không bao giờ tới PS4/PS5.
**Đã sửa:** `files/rh/chiaki.py` gửi SRCH tới `987`/`9302` với socket nguồn bind `9303-9319`, packet `SRCH ...\n...\n\x00`
khớp `chiaki_discovery_packet_fmt`, parser chấp nhận `\r\n`/`\n` và mã `200`/`620`. Thêm 5 test trong
`tests/test_release_and_logs.py` (packet format, dest ports, parse ready/standby). 23/23 pass.
**Việc còn lại:** cập nhật lên `v0.2.11` rồi test lại `QUÉT MÁY PS4/PS5` với PS4 Pro trong cùng mạng
(tắt Bluetooth trên TrimUI để tránh nhiễu WiFi).

## 5. Cách cài / cập nhật

- **Lần đầu:** tải `trimui-chiaki-ng-vX.Y.Z.zip` từ Releases, giải nén trực tiếp vào gốc thẻ nhớ
  -> có `Apps/Chiaki/launch.sh`.
- **OTA:** trong app -> `CẬP NHẬT` -> `CÀI NGAY`. Từ v0.2.4 trở đi OTA dùng tag bất biến.
- **Log thủ công:** lấy `Apps/Chiaki/Chiaki-loi.txt` + `Chiaki-debug.log` trên thẻ gửi cho dev
  nếu chưa cấu hình token.

## 6. Lệnh nhanh cho session mới

```powershell
Set-Location 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng'
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py; python tools/verify_release.py
```

Phát hành tag mới (vd v0.2.11):

```powershell
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' fetch origin
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' add files tests tools README.md docs manifest.json
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' commit -m 'fix: discovery sends SRCH to ports 987/9302 in v0.2.11'
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' push origin main
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' tag -a v0.2.11 -m 'v0.2.11: fix PS4/PS5 discovery'
git -C 'E:\Trimiu Brick Pro\Project APPS\chiaki-ng' push origin v0.2.11
```

## 7. File quan trọng

- `files/rh/inputs.py` — **nguyên nhân gốc P0**: map nút GameController + gate JOY*
- `files/rh/screens/settings.py` — logic A đổi giá trị / B thoát, ưu tiên `btn_b` trước `btn_a`
- `files/rh/screens/home.py` — header version
- `files/rh/updater.py` — OTA + log mạng
- `files/rh/log_uploader.py` — auto Issue
- `tools/make_release.py` / `tools/verify_release.py` — build gate
- `tests/test_release_and_logs.py` — 38 tests
- `E:\Trimiu Brick Pro\Project APPS\repohubtool\files\rh\inputs.py` — tham chiếu chuẩn cho mapping nút


## 8. Bước kiểm thử v0.3.4

1. Nếu muốn bài test sạch, vào **Cài đặt → XÓA LOG CŨ → A → Có**.
2. Mỗi cấu hình chơi 1–2 phút rồi giữ START+SELECT 1,2 giây để về menu; không
   tắt PS4. Xác nhận app quay về menu và Issue chất lượng xuất hiện.
3. Thử lần lượt `720p30/4000`, `720p30/6000`, `720p60/6000`, `1080p30/6000`.
4. Chỉ thử 1080p60 hoặc 8000–15000 kbps khi `fec/lost` ở cấu hình trước gần 0.
5. So sánh `fps`, `fec`, `lost` và renderer; dùng Wi-Fi 5 GHz, tắt Bluetooth.

Lưu ý phần cứng: RAM 1 GB và màn 720p, nên 720p30 vẫn là cấu hình ưu tiên.
