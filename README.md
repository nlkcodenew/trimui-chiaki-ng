# trimui-chiaki-ng

Ứng dụng PS4/PS5 Remote Play cho các máy TrimUI chạy Linux, tập trung vào:

- TrimUI Smart Pro S/TG5050 và Spruce OS.
- TrimUI Brick Pro chạy Stock OS.
- PS4 Pro firmware 9.00/GoldHEN qua LAN, không cần đăng nhập PSN.

## Trạng thái hiện tại

**Release thử nghiệm mới nhất: `v0.4.0-beta2`.**

- `v0.3.11` đóng gói Mozilla CA bundle cho Brick Pro Stock OS. OTA và GitHub
  Issue uploader vẫn bắt buộc xác minh certificate và hostname.
- `v0.3.12` ngăn popup cập nhật lặp khi app và manifest đã cùng phiên bản.
- `v0.3.13` tự báo các lỗi OTA/runtime có ý nghĩa, thêm ID thiết bị riêng tư và
  `fsync` cho quá trình cập nhật trên thẻ exFAT.
- `v0.3.14` coi lỗi một nguồn manifest là lỗi trung gian nếu URL dự phòng tải
  thành công. Chỉ khi tất cả nguồn đều thất bại app mới ghi `WARNING` và gửi
  GitHub Issue.
- `v0.3.15` thêm runtime AArch64 biệt lập cho Brick Pro Stock OS sau khi Issue
  `#36`/`#37` cho thấy pair đã thành công nhưng loader thiếu `libjson-c.so.5`.
- `v0.3.16` sửa Issue `#38`: Stock OS có OpenSSL 1.1 cũ nhưng thiếu symbol
  `OPENSSL_1_1_1`; launcher Brick preload đúng OpenSSL 1.1.1 đã đóng gói.
- `v0.3.17` khóa profile tối đa 720p và chuyển báo cáo lỗi sang HTTPS relay;
  GitHub token chỉ nằm trong Worker secret, không còn trong app hoặc thẻ nhớ.
- `v0.3.18` thêm hướng dẫn sử dụng 8 bước ngay trong menu và hiển thị mã cài
  đặt `CHI-xxxx` cạnh version để đối chiếu đúng Issue khi hỗ trợ người dùng.

Brick Pro Stock OS đã OTA thành công đến `v0.3.16` và stream PS4 thật có hình,
âm thanh, input. Issue `#39` ghi nhận native exit `0`, tổng `8968` frame,
`lost=0`, `FEC=0`, phần lớn giữ 29,4–30,2 FPS ở profile 540p30/3000.

- `v0.3.19` luôn bật diagnostics và tự gửi Issue qua HTTPS relay; không còn phụ thuộc
  người dùng nhớ bật tùy chọn. Lỗi pair PS5 chưa được hỗ trợ cũng được ghi nhận riêng.
- `v0.3.20` luôn tạo `Apps/Chiaki/Chiaki-loi.txt` từ launcher và khởi tạo logger
  trước khi đọc settings, nên lỗi bootstrap trên Stock OS vẫn để lại log chẩn đoán.
- `v0.4.0-beta1` thêm đường pair/stream PS5 riêng bằng helper native upstream,
  giữ nguyên đường đăng ký Python pre-10 và H264 đã xác nhận trên PS4. Lỗi PS5
  được ghi theo stage `account_id`, `helper`, `input`, `start`, `network`,
  `protocol` hoặc `result` để đối chiếu Issue mà không ghi PIN hay khóa bí mật.
- `v0.4.0-beta2` thêm bước nhập PSN Account-ID trực tiếp bằng tay cầm chỉ khi
  app nhận diện PS5. Lỗi hiện mã `PS5-*` và `CHI-*` để người test chụp ảnh mà
  không phải chụp Account-ID, PIN hoặc khóa pair.
- Từ `v0.3.17`, UI không còn 1080p; cấu hình 1080p cũ hoặc giá trị không hợp lệ
đều bị cap về 720p. HTTPS relay đã được kiểm thử end-to-end với repo chẩn đoán
private và không làm thay đổi native stream/runtime đã xác nhận trên máy thật.

Native binary, pair/session pre-10 và mapping SDL của Smart Pro S/Spruce không
thay đổi. Model `sun55iw3` tiếp tục dùng library hệ thống; chỉ `sun50iw10` có
`libs/brick-stock` làm fallback sau library Stock OS. Cả hai nền tảng đã stream
thật với đường runtime riêng nên không cần tách release hiện tại. Chỉ xem xét
tách theo OS nếu một thay đổi tương lai tạo ra ABI/GPU không thể cô lập an toàn.

## Tính năng

- Quét PS4/PS5 đang hoạt động trong LAN.
- Ghép nối PS4 firmware 9.00 bằng PIN LAN và giao thức pre-10.
- Native Remote Play AArch64, H264, âm thanh Opus và input SDL GameController.
- OTA theo manifest bất biến, kiểm SHA-256 trước khi thay file.
- Mozilla CA bundle dùng chung cho OTA và uploader, không tắt TLS verification.
- Log xoay vòng, nút xóa log an toàn và retry báo cáo pending.
- Tự tạo GitHub Issue cho lỗi kết thúc thật sự và báo cáo chất lượng stream.
- ID Issue gồm model, mã cài đặt `CHI-xxxx` và mã phần cứng băm
  `HW-xxxxxxxxxxxx` để phân biệt nhiều máy mà không gửi serial/MAC thô.
- Menu **Hướng dẫn sử dụng** trình bày bật máy, auto-login, pair PIN, stream và
  thoát phiên; PS5 có hướng dẫn beta riêng và không đi qua mã pair PS4.

## Tương thích đã xác nhận

| Thành phần | Trạng thái |
|---|---|
| Smart Pro S/TG5050 | Stream PS4 thật có hình, âm thanh và input |
| Spruce OS | Stream tốt trên `sun55iw3`; tiếp tục dùng library hệ thống |
| Brick Pro Stock OS | `v0.3.16` stream PS4 thật có hình, âm thanh và input |
| PS4 Pro 9.00 GoldHEN | Pair PIN LAN và session pre-10 hoạt động |
| PS5/H265 | Beta pair/stream LAN riêng; chưa được xác nhận trên máy thật |
| WAKEUP PS4 Rest Mode | Đã thử thất bại trên môi trường hiện tại và tắt từ `v0.3.10` |

## Cài đặt

1. Tải `trimui-chiaki-ng-v0.4.0-beta2.zip` tại
   [GitHub Releases](https://github.com/nlkcodenew/trimui-chiaki-ng/releases/tag/v0.4.0-beta2).
   Không tải các gói **Source code** do GitHub tự tạo.
2. Giải nén ZIP trực tiếp vào gốc thẻ nhớ.
3. Kiểm tra tồn tại `Apps/Chiaki/launch.sh` và
   `Apps/Chiaki/bin/chiaki-stream`.
4. Bản PS5 beta còn cần `Apps/Chiaki/bin/chiaki-regist`.

## Thử nghiệm PS5

PS4 hack pair/stream được vì dự án có đường giao thức PS4 pre-10 hoàn chỉnh;
điều này không phụ thuộc trạng thái jailbreak. PS5 dùng endpoint, crypto, target
và H265 riêng nên dòng `v0.4.0-beta` cô lập đường PS5 thay vì thay thế mã PS4. Không
cần tách release “PS5 jailbreak/no-jailbreak”; khả năng kết nối phụ thuộc firmware,
cấu hình Remote Play, tài khoản và mạng của PS5, không phải tên release.

1. Giữ PS5 và TrimUI trong cùng LAN; bật Remote Play và để PS5 ở trạng thái ready.
2. Khi chọn pair một host được nhận diện là PS5, app hiện **Bước 1/2** để nhập
   PSN Account-ID Base64 12 ký tự bằng tay cầm. Giá trị này là `user_id` PSN
   được upstream Chiaki-ng đổi thành 8 byte little-endian rồi Base64; nó không
   phải PSN Online-ID, PIN hay mã 8 số. Có thể lấy bằng nút **PSN Login** trên
   Chiaki-ng desktop chính chủ rồi nhập chuỗi kết quả vào TrimUI. App tự lưu vào
   `settings.json`; PS4 không hiện và không dùng bước này.
3. Trong vòng test đầu, tắt mã đăng nhập console 4 số; đây không phải PIN Remote
   Play 8 số. Chọn profile 720p/30, SDR và không bật HDR.
4. Quét PS5, chọn pair, mở màn hình thêm thiết bị Remote Play trên PS5, nhập PIN
   8 số rồi bấm A. Helper đăng ký trực tiếp theo IP, không broadcast registration.
5. Nếu lỗi, chụp màn hình chứa mã `PS5-*` và ID `CHI-xxxx`, nhưng không chụp
   màn nhập Account-ID. App tự gửi log đã lọc với stage cụ thể; file cục bộ là
   `Apps/Chiaki/Chiaki-loi.txt` và `Apps/Chiaki/Chiaki-debug.log`.
4. Lắp thẻ vào máy và mở **Apps → Chiaki-ng**.
5. Chọn **Hướng dẫn sử dụng** trong menu nếu cần xem từng bước ngay trên máy.

Nếu Brick Pro Stock OS đang chạy bản trước `v0.3.11` và log có
`CERTIFICATE_VERIFY_FAILED`, phải cài ZIP `v0.3.11` hoặc mới hơn bằng tay một
lần. Updater cũ chưa có CA nên không thể tự tải chính bản vá CA.

Xem hướng dẫn đầy đủ tại `INSTALL.md`.

## Cập nhật OTA

App ưu tiên manifest của GitHub Release mới nhất, sau đó thử Raw GitHub và proxy
dự phòng. Quy tắc từ `v0.3.14`:

- Một nguồn lỗi nhưng nguồn sau thành công: ghi `INFO`, không tạo Issue.
- Tất cả nguồn lỗi TLS: trạng thái `tls_error`, ghi `WARNING`, tạo Issue
  `ota_manifest_tls_error`.
- Tất cả nguồn lỗi mạng/DNS/dữ liệu: ghi `WARNING`, tạo Issue
  `ota_manifest_network_error`.
- Chỉ hiện popup khi version server mới hơn app; lệch hash trong cùng version
  không tạo vòng lặp cập nhật.

OTA không đưa `settings.json`, `secrets.json`, log hoặc marker runtime vào
manifest. File staging được kiểm SHA-256, `fsync`, rồi thay atomically;
`rh/version.py` được áp dụng cuối để bản cập nhật gián đoạn có thể thử lại.

## Chạy stream PS4

1. Bật PS4 bằng nút nguồn hoặc tay cầm và chờ auto-login hoàn tất.
2. Đặt PS4 và TrimUI cùng mạng LAN/Wi-Fi 5 GHz.
3. Nếu chưa ghép nối đúng giao thức pre-10, chọn PS4, bấm **Y** và nhập PIN 8 số.
4. Quét lại, chọn host đã ghép và bấm **A** để stream.
5. Giữ **START + SELECT** khoảng 1,2 giây để dừng stream và trở lại app.

Profile ưu tiên đã xác nhận là `720p`, `30 FPS`, `4000 kbps`. Fallback tải thấp
là `540p`, `30 FPS`, `4000 kbps`. Từ `v0.3.17` chỉ cho chọn tối đa 720p;
cấu hình 1080p cũ cũng chạy ở 720p. Thử nghiệm máy thật cho thấy profile cao
hơn độ phân giải màn hình và bitrate cao làm giảm FPS, tăng FEC/lost/IDR.

Sau khi thoát stream, nên chờ khoảng hai phút trước khi kết nối lại. PS4 đôi khi
giữ lease Remote Play tạm thời dù client đã shutdown sạch.

## GitHub Issue tự động

GitHub không cho client ẩn danh tạo Issue. Bản chia sẻ gửi log đã lọc tới một
HTTPS relay; chỉ relay giữ fine-grained token trong server secret rồi tạo Issue
trong **repo chẩn đoán private**. Không đặt token chung trong app, URL, ZIP hoặc
thẻ nhớ của người thử vì mọi secret phía client đều có thể bị trích xuất.

1. Triển khai Worker theo `deploy/issue-relay/README.md`.
2. Cấp token chỉ có **Issues: Read and write** cho đúng repo private nhận log.
3. Điền endpoint `/report` vào `files/reporting.json` trước khi build release.
4. Đặt rate-limit cho endpoint và thông báo người thử về dữ liệu chẩn đoán.
5. Diagnostics được bật mặc định và không có công tắc tắt trong bản beta; app tự gửi
   log đã lọc qua relay để phát hiện lỗi thực tế. OTA cũng migrate bản cũ sang chế độ này.

Verifier từ chối release nếu relay không phải HTTPS sạch, thiếu config OTA hoặc
phát hiện token GitHub trong source đóng gói. App không còn đọc `secrets.json`,
GitHub token hoặc tên repo nhận log; client chỉ biết URL relay. Client và relay
đều lọc token, password, khóa ghép nối, PSN ID, IP nội bộ, MAC, serial, chip ID
và machine-id trước khi gửi.

Issue có dạng:

```text
[device-log][sun50iw10][CHI-E545][HW-C3A2FEFAB3F5] v0.3.19 reason fingerprint
```

- `CHI-...`: ID ngẫu nhiên của bản cài/thẻ nhớ.
- `HW-...`: pseudonym SHA-256 từ chip serial, permanent MAC hoặc machine-id;
  raw value không rời thiết bị.
- `RH-...` của RetroHub là ID riêng của RetroHub, không phải serial phần cứng.

Tiêu đề màn hình chính hiển thị `CHIAKI-NG vX.Y.Z | ID: CHI-xxxx`. Khi báo lỗi,
người dùng chỉ cần gửi mã `CHI-xxxx`; mã này trùng với mã trong title/body Issue.

Không gửi Issue cho trạng thái bình thường như quét `0 host`, người dùng hủy,
thoát bình thường hoặc một URL OTA lỗi nhưng fallback thành công. Khi mất mạng,
app giữ nhiều lý do pending và thử lại ở lần mở/thoát tiếp theo.

## Log cục bộ

- `Apps/Chiaki/Chiaki-debug.log`: toàn bộ hoạt động của app.
- `Apps/Chiaki/Chiaki-loi.txt`: stderr và cảnh báo/lỗi quan trọng.
- `.pending_crash`: các lý do chưa gửi được.
- `.log_upload_state.json`: fingerprint báo cáo đã gửi để chống trùng lặp.

Vào **Cài đặt → XÓA LOG CŨ → A → Có** để chuẩn bị bài test sạch. App không xóa
log khi còn report pending. `CHIAKI_NATIVE_VERBOSE=1` chỉ nên bật khi cần trace
native vì log dày có thể làm giảm FPS.

## An toàn dữ liệu thẻ nhớ

Không rút cáp USB hoặc tháo thẻ trong khi máy/Windows đang đọc ghi. exFAT không
có journal; ngắt giữa lúc I/O có thể tạo directory entry trùng tên. Updater có
`fsync` để giảm cửa sổ chưa flush nhưng không thể bảo vệ khỏi việc rút cáp vật
lý. Nếu thấy hai thư mục cùng tên, dừng ghi và chạy `chkdsk <ổ>: /F` trước khi
xóa hoặc chép lại dữ liệu.

## Phát triển và kiểm tra

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

Build gate kiểm tra version, CA bundle, ELF AArch64, từng checksum runtime Brick,
manifest/ZIP, từng SHA-256 payload, file cấm và tính tái lập LF giữa Windows và
Linux. Native binary hiện tại có SHA-256
`a8d6bfdb846a501ed9525c378a4f2f9c0c4d64a88aadeb098e1093d4b0378d7d`.

## Tài liệu

- `INSTALL.md`: cài đặt, OTA, stream và gỡ lỗi cho người dùng.
- `docs/NEW_SESSION_HANDOFF.md`: trạng thái chính xác để tiếp tục phát triển.
- `docs/PROJECT_STATUS.md`: ma trận tính năng, lịch sử và giới hạn đã biết.

## Giấy phép

Xem `LICENSE`.
