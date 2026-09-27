# Bàn giao session — v0.3.22 và beta10

## Stable

- Worktree: `E:\Trimiu Brick Pro\Project APPS\chiaki-ng-v0.3.21`
- Branch: `release/v0.3.22`
- Mục tiêu: tag/release stable `v0.3.22` và đặt thành GitHub latest.
- Stable chỉ có luồng PS4 đang bật; không có wake/offline host.
- Header: `CHIAKI-NG v0.3.22 | HW-xxxxxxxxxxxx`.
- Issue title chỉ dùng `HW-...`; `CHI-...` nằm trong body như metadata phụ.
- ZIP/OTA loại toàn bộ settings, pair data, secrets và log.

## Pair lần đầu

- Người dùng nhập PIN 8 số.
- `regist_key` và `rp_key` do PS4 tự trả về; app tự kiểm tra và lưu.
- Cài đè/OTA giữ pair.
- Xóa sạch thư mục app làm mất pair; settings mặc định được tạo lại nhưng người
  dùng phải pair lại bằng PIN.

## Beta wake

- Worktree: `E:\Trimiu Brick Pro\Project APPS\chiaki-ng-wake-beta`
- Hiện tại: `v0.3.22-beta9`.
- Thiết bị test: Brick Pro `sun50iw10`, mã chính `HW-C3A2FEFAB3F5`.
- Beta9 đã gửi DDP WAKEUP qua unicast + directed broadcast và retry trên cùng
  socket, nhưng PS4 không trả SRCH/`620 Standby`/`200 OK`.
- Beta10 phải giữ tách biệt stable và tăng chẩn đoán trạng thái LAN/ARP; không
  log IP, MAC, key, Account ID hoặc serial thô.
- DNS chặn Internet không trực tiếp chặn DDP LAN. GoldHEN/payload, network
  blocker hoặc NIC Rest Mode không hoạt động vẫn là khả năng cần kiểm tra.

## Quy tắc an toàn

- Không sửa hoặc thay native binary nếu chưa có regression được chứng minh.
- Không tắt TLS verification.
- Không retag release đã công bố.
- Chỉ xóa beta9 sau khi beta10 và asset công khai đã được xác minh.
