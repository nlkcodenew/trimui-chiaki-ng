# trimui-chiaki-ng — trạng thái dự án v0.3.22

> Cập nhật: 2026-09-27.

## Release ổn định

`v0.3.22` là bản PS4-only, kế thừa toàn bộ sửa lỗi nguồn của `v0.3.21`:

- Menu không giữ `/tmp/stay_alive`; marker chỉ tồn tại trong phiên stream.
- Menu tự thoát sau 15 phút không thao tác.
- Discovery chỉ dùng một socket UDP và broadcast giao thức PS4 tới cổng `987`.
- UI chỉ hiện PS4 đang trả trạng thái `ready`.
- Không có API, nút, host offline hoặc luồng WAKEUP trong stable.
- Tiêu đề app và Issue dùng mã `HW-xxxxxxxxxxxx` ổn định.
- ZIP/OTA không chứa dữ liệu người dùng hoặc khóa pair.

Native helper và runtime Brick giữ nguyên từ bản stream thật đã xác nhận để tránh
regression video/audio/input.

## Nền tảng

| Nền tảng | Trạng thái |
|---|---|
| Smart Pro S/TG5050 | Stream PS4 thật có hình, âm thanh và input |
| Spruce OS `sun55iw3` | Dùng library hệ thống, đã stream thật |
| Brick Pro Stock OS `sun50iw10` | Dùng `libs/brick-stock`, đã stream thật |
| PS4 Pro 9.00/GoldHEN | Pair PIN LAN và session pre-10 hoạt động |

Profile ưu tiên: `720p30/4000`; Brick có thể dùng `540p30/3000` để giảm tải.
App khóa tối đa 720p.

## Pair và dữ liệu

Người dùng chỉ nhập PIN 8 số. PS4 trả registration key, RP key, key type và MAC;
app kiểm tra rồi lưu atomically vào:

- `settings.json`
- `paired_hosts.json`

Cài đè hoặc OTA giữ hai file này. Xóa cả `Apps/Chiaki/` làm mất khóa và bắt buộc
pair lại; lần chạy mới chỉ tự tạo settings mặc định và `CHI-xxxx` mới.

`HW-...` là định danh chính trong UI/Issue. `CHI-...` chỉ là ID lần cài và có thể
đổi khi mất settings.

## Chẩn đoán

- HTTPS relay không để GitHub token trên client.
- TLS luôn xác minh certificate và hostname.
- Uploader lọc khóa pair, PSN ID, IP, MAC, serial và chip ID thô.
- Kết quả discovery bình thường `0 host` không tạo Issue.
- App không sửa cấu hình Wi-Fi/WoWLAN của hệ điều hành.

## Wake thử nghiệm

Wake PS4 Rest Mode không nằm trong stable `v0.3.22`. Beta9 đã gửi đúng DDP
WAKEUP bằng unicast và directed broadcast nhưng Brick Pro không nhận bất kỳ phản
hồi SRCH nào từ PS4 đang nghỉ. Beta10 phải tiếp tục ở worktree/branch beta riêng,
không merge thử nghiệm này vào stable nếu chưa xác nhận trên máy thật.

DNS chặn Internet/Sony không trực tiếp chặn UDP LAN cổng `987`. Tuy nhiên firmware
hack, payload/network blocker hoặc trạng thái Rest Mode có thể làm NIC/DDP service
không còn hoạt động. Bằng chứng quan trọng nhất hiện tại là PS4 không phát
`HTTP/1.1 620 Standby`, không phải định dạng WAKEUP sai.

## Kiểm thử release

```powershell
python -m compileall -q files tools tests
python -m unittest discover -s tests -v
python tools/make_release.py
python tools/verify_release.py
git diff --check
```

Trước khi tag, xác nhận ZIP không có `settings.json`, `paired_hosts.json`,
`chiaki.conf`, secrets, log hoặc khóa thật.
