# trimui-chiaki-ng — Trạng thái dự án (đến v0.3.0-beta.1)

> Tài liệu tổng hợp cho session mới. Cập nhật: 2026-09-21.
> Phiên bản đang chuẩn bị phát hành: v0.3.0-beta.1. Bản này sửa lỗi máy thật không có executable `openssl` bằng AES thuần Python.

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
- 25 unittest pass tại `tests/test_release_and_logs.py`.

### Ghép nối PS4 thật — v0.3.0-beta
- Xóa hoàn toàn `stub-rp-key-*`; chỉ báo thành công khi PS4 trả HTTP 200 và đủ `PS4-RegistKey`, `RP-Key`, `RP-KeyType`, MAC.
- Thực hiện đúng handshake upstream: UDP `SRC2`/`RES2` cổng 9295, TCP `/sie/ps4/rp/sess/rgst`, `RP-Version: 10.0`, HMAC-SHA256 và AES-128-CFB.
- Không kết nối dịch vụ PSN. Trường Account-ID 8 byte vẫn là yêu cầu của giao thức PS4 firmware 8+; app dùng Account-ID đã cấu hình hoặc thử ID offline bằng 0.
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
- `files/rh/logger.py`: 2 file `Chiaki-loi.txt` (WARNING+) và `Chiaki-debug.log` (DEBUG khi `enable_logging`), xoay vòng.
- `files/launch.sh`: giữ log khi có `.pending_crash`, xuất `CHIAKI_STDERR_LOG`, tạo `.pending_crash` khi app exit != 0 và gọi uploader.

## 3. Tự động gửi log về GitHub — đã hoàn thiện về mã, chưa hoàn thiện về vận hành

**Mã đã xong:**
- `files/rh/log_uploader.py`: đọc `secrets.json` hoặc env `CHIAKI_GITHUB_TOKEN`, lọc token/PSN/IP/MAC,
  giới hạn 24KB/log, 60K body, fingerprint dedupe qua `.log_upload_state.json`, chỉ gửi khi có
  `.pending_crash`, retry ở lần khởi động sau, tạo Issue tiêu đề `[device-log] vX.Y.Z reason fingerprint`.
- `files/app.py` gọi `start_pending_upload("startup_retry")` và lazy import SDL sau logger.
- `files/launch.sh` gọi `python -m rh.log_uploader` khi crash.
- `files/secrets.example.json` mẫu, `.gitignore` loại trừ `secrets.json`.

**Tại sao chưa thấy Issue nào:**
- GitHub không cho tạo Issue ẩn danh. Máy bạn chưa có token nên log chỉ ghi
  `WARNING log upload pending: missing secrets.json github_token` (đã thấy trong mọi `Chiaki-loi.txt`).
- Chưa cấu hình token -> pipeline log hoạt động đúng nhưng bị gate ở bước lấy token.
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

### 4.4 P2 — Stream thật chưa làm
`files/rh/chiaki.py::init_session`/`run_stream` vẫn là stub (trả -1). Mục tiêu v0.3.0: FFmpeg + SDL renderer,
720p30, bitrate 6000-10000, PS4 H264 / PS5 H265. Cần quyết định test LAN trước hay làm codec ngay (xem mục 8).

### 4.5 P0 — Quét PS4/PS5 luôn trả 0 host — ĐÃ SỬA TRONG v0.2.11
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
- `tests/test_release_and_logs.py` — 20 tests
- `E:\Trimiu Brick Pro\Project APPS\repohubtool\files\rh\inputs.py` — tham chiếu chuẩn cho mapping nút


## 8. Khuyến nghị hướng đi (đã thảo luận với user)

Ưu tiên nên là: **test quét LAN với PS4 Pro trước (v0.2.11), rồi mới làm codec/stream**.

Lý do:
- Discovery là tầng đầu tiên của mọi thứ. Trước v0.2.11 nó sai cổng nên không thể test gì phía sau.
- Stream (init_session/run_stream) cần host_addr + regist_key + rp_key lấy từ bước quét/đăng ký. Nếu quét chưa thấy host thì làm codec cũng không có gì để nối tới.
- v0.2.11 đã sửa đúng protocol upstream, nên bước kế tiếp hợp lý là xác nhận máy TrimUI thấy được PS4 Pro trong LAN (0 -> >=1 host), xem đúng tên/state/addr trong log.

Sau khi quét OK, thứ tự đề xuất cho v0.3.0:
1. Đăng ký (regist): lấy `rp_key` / `regist_key` từ PS4/PS5 (upstream `lib/src/regist.c`) — cần PSN account-id + PIN.
2. Session init + handshake RUDP (`lib/src/session.c`, `remote/rudp.c`).
3. Bind codec H264 (PS4) / H265 (PS5): 2 hướng
   - a) FFmpeg subprocess decode -> frame -> SDL texture (dễ port, nặng hơn).
   - b) native lib (build aarch64 chiaki/ffmpeg) + ctypes/gRPC (nhẹ, khó port).
   Khuyến nghị bắt đầu bằng (a) để có hình ảnh trước, tối ưu (b) sau.
4. Audio Opus + input (đã có SDL controller map ở `files/rh/inputs.py`).

Lưu ý phần cứng: 1GB RAM, native 720p -> chốt 720p30, bitrate 6000-10000, tắt Bluetooth khi stream.
