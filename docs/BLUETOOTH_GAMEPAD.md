# Brick Pro Bluetooth Gamepad — hồ sơ kỹ thuật

> Cập nhật: 2026-10-02. Áp dụng cho `v0.3.27-beta1`.

Tài liệu này ghi lại kết quả rà soát app sau khi người dùng chạy thử `v0.3.25-beta1`
trên Brick Pro Stock OS và ghép với **iPhone** (`D8:DE:3A:21:25:E6`).

## 1. Kết quả chạy thử thực tế

Bluetooth **đã kết nối thành công**, hai lần, dữ liệu từ `/mnt/SDCARD/Apps/Chiaki/BrickBluetooth.log`:

```
15:48:10  Stage: radio_switch      bluetoothd -nd (nplugin=input) khởi động
15:48:11  Stage: waiting
15:48:53  Accepted HID PSM 17 from D8:DE:3A:21:25:E6
15:48:53  Accepted HID PSM 19 from D8:DE:3A:21:25:E6
15:48:53  Stage: connected         (+42.676s)
15:49:11  Stage: restoring         Bluetooth gamepad stopped cleanly
```

iOS hiện `TrimUI Brick Pro Gamepad — Đã kết nối`. Phiên thứ hai chỉ mất **9.234s**
vì iPhone tự kết nối lại (đã ghép từ phiên một). Độ trễ 42.7s ở phiên đầu là thời gian
người dùng tự tìm và bấm thiết bị trong Cài đặt — không phải lỗi app.

Điều chưa xác nhận được trong môi trường máy tính: hành vi nút bấm thực tế trên máy.

## 2. Mã phím thật của thiết bị

Dòng `B: KEY=` trong `/proc/bus/input/devices` phải được giải mã đúng theo
`input_seq_print_bitmap()` của kernel 4.9 (`drivers/input/input.c`):

- Mỗi word 64-bit in bằng `%lx` (bỏ số 0 ở đầu, giữ số 0 bên trong).
- Word bằng 0 **trước** word cao nhất bị bỏ qua (`skip_empty`).
- Sau khi đã in, các word 0 tiếp theo vẫn in ra là `0`.
- `KEY_MAX` = 767 → 12 word.

Áp dụng cho `7cdb000000000000 0 100000000000 c000000000000 1800000000000000`:

| Word | Phạm vi bit | Mã phím Linux |
|---|---|---|
| w4 | 256–319 | 304, 305, 307, 308, 310, 311, 314, 315, 318, 319, 320 |
| w2 | 128–191 | 172 |
| w1 | 64–127 | 114, 115 |
| w0 | 0–63 | 60, 63 |

Tập đầy đủ, đúng thứ tự:

```
60, 63, 114, 115, 172, 304, 305, 307, 308, 310, 311, 314, 315, 318, 319, 320
```

### Hệ quả

| Ý nghĩa | Mã mong đợi | Thực tế | Kết luận |
|---|---|---|---|
| A / B | 304 / 305 | có | đúng |
| X / Y | 307 / 308 | có | đúng |
| L1 / R1 | 310 / 311 | có | đúng |
| SELECT / START | 314 / 315 | có | đúng |
| L2 / R2 analog | axis 2 / 5, range 0..255 | có | đúng |
| 2 joystick | axis 0/1 và 3/4, range ±32767 | có | đúng |
| D-pad | axis 16/17 (hat) | có | đúng |
| **L3** | **317 (BTN_THUMBL)** | **không có** | **chưa từng hoạt động** |
| R3 | 318 (BTN_THUMBR) | có | đúng |
| 8 phím còn lại | — | 60, 63, 114, 115, 172, 319, 320 | chưa gán |

`padState.report()` cũ dùng `1 << (key - 304)`, tức giả định mã phím tăng đơn điệu
với bit HID. Với tập mã thật ở trên, các nút chưa gán rơi vào bit trùng hoặc bit
trên 15 và **bị cắt âm thầm**.

## 3. Bảng điều khiển HIDP sai hoàn toàn

Đối chiếu `include/net/bluetooth/hidp.h` (kernel 4.9) cho thấy bảng mã giao dịch
trong `hid.go` cũ không khớp đặc tả:

| Mã cũ | Được hiểu là | Đúng theo HIDP |
|---|---|---|
| `0x10` | SET_REPORT | `HIDP_TRANS_HID_CONTROL` |
| `0x20` | — | `HIDP_TRANS_SET_PROTOCOL` |
| `0x40` | GET_REPORT | `HIDP_TRANS_GET_REPORT` ✓ |
| `0x50` | — | `HIDP_TRANS_SET_REPORT` |
| `0x60` | GET_PROTOCOL | `HIDP_TRANS_GET_PROTOCOL` ✓ |
| `0x70` | (giả định sai) | `HIDP_TRANS_SET_PROTOCOL` |

Hệ quả: Set Protocol và Set Report từng bị trả `0x03` (STALL). Loại lỗi này giải
thích hiện tượng "ghép nối được nhưng vào game thì nút không phản ứng" trên một số
máy. Đặc biệt đáng chú ý: log chạy thử **không có dòng `HID control:` nào**, nghĩa là
iOS trong phiên đó chưa từng gửi giao dịch control — nên framing cũ thực tế **chưa
từng được kiểm chứng** bởi host thật.

Đã viết lại theo đúng đặc tả:

- `0x10` HID_CONTROL: 3 suspend, 4 exit suspend, 5 virtual cable unplug, 1/2 reset.
- `0x50` SET_REPORT: bắt buộc trả handshake thành công cho output/feature.
- `0x40` GET_REPORT: chỉ nhận input report; sai report ID trả `0x02`, sai tham số `0x04`.
- `0x60` GET_PROTOCOL: trả handshake + `0x01` (report mode).
- `0x70` SET_PROTOCOL: không trả lời, host đọc trạng thái qua interrupt report kế.
- Không giao dịch nào trả stall trần. Test quét cả 256 header để giữ điều này.

## 4. Thay đổi của v0.3.26-beta1

### Backend Go (`bluetooth-native/`)

| File | Thay đổi |
|---|---|
| `mapping.go` | Mới. Bảng ánh nhãn→mã phím, nạp `bluetooth-map.json`, `usedKeys()`, `unmappedKeys()` |
| `hid.go` | Dùng bảng ánh xạ thay vì `key - 304`; viết lại HIDP; `hatValue()` tách D-pad khỏi joystick |
| `main_linux.go` | `check()` không còn exit 1 vì `HID_BUSY`/`BLUETOOTH_OFF`; cờ `--map-file` |
| `radio_linux.go` | Marker lưu cả trạng thái powered; `powerOnAdapter()`; `disablePowerSaving()` |
| `bluez.go` | `powerOnAdapter()`, `trustDevice()`; bật `Discoverable` sớm hơn |
| `server_linux.go` | `noteUnmappedKeys()`; tái gửi report khi Set Protocol/reset; report trung tính khi kết nối và khi đóng |
| `version` | `0.3.0-stock` → `0.3.1-stock` |

### Python

| File | Thay đổi |
|---|---|
| `rh/gamepad_map.py` | Mới. Đọc/ghi `bluetooth-map.json`, tìm evdev node, `PadReader` đọc không chặn |
| `rh/screens/button_test.py` | Mới. Màn hình THỬ NÚT |
| `rh/bluetooth_gamepad.py` | 143 khi dừng chủ động không còn là lỗi; xoay vòng log; `map_present()` |
| `rh/screens/bluetooth.py` | Thêm hành động X → THỬ NÚT; chừa chỗ cho dòng mới |
| `rh/i18n.py` | 18 khoá mới vi/en; hướng dẫn bỏ chữ "Android" |
| `launch.sh` | Shim `setterm` khi firmware thiếu, tự xoá khi thoát |
| `bluetooth-session.sh` | Xoay vòng `BrickBluetooth.log` ở 512 KB |

### Ỹ tưởng lấy từ Padpod

Đã đọc Padpod 2026.10.02 (`Padpod-2026.10.02-stockOS`) và lấy các ý tưởng sau.
Padpod là **PolyForm-Noncommercial**, nên chỉ lấy ý tưởng và tự viết lại bằng code của
dự án, không sao chép mã nguồn.

| Ý tưởng | Thực hiện |
|---|---|
| `echo 1 > /tmp/stay_awake` + `/tmp/stay_alive` | `launch.sh` đã có sẵn; giữ nguyên |
| Tắt power-saving chip BT trong phiên | `disablePowerSaving()` — `pkt_type DM1`, `power_save off`, `sc_only off` |
| `Device1.Trusted = true` | `trustDevice()` khi nhận kênh HID từ thiết bị đã paired |
| Lệnh `restore` từ marker `/tmp` | Đã có `--recover`; nay bật lại adapter sau khi khôi phục |
| Màn hình bấm từng nút ngay trên máy | Màn hình THỬ NÚT |
| Chọn profile máy chủ (PC/Xbox/PS4) | **Chưa làm** — cần descriptor DS4/Xbox đúng, xem mục 6 |

## 4b. Lỗi màn hình THỬ NÚT (phát hiện 2026-10-02)

Người dùng chạy `v0.3.26-beta1` và báo: ấn nút A theo hướng dẫn thì **3 nút sáng
đồng loạt**. Log `Chiaki-debug.log` cho thấy:

```
20:01:12.423 button test: bo qua a
20:01:12.423 button test: b -> 305 (truoc 305)
20:01:12.460 button test: x -> 305 (truoc 307)
20:01:12.497 button test: y -> 305 (truoc 308)
```

Ba bước liên tiếp trong 74 ms, cùng một mã `305`. Bản đồ lưu được
`x=305, y=305, r1=310, l3=310, select=318, start=318` — nhiều nút dùng chung mã.

### Hai nguyên nhân

**1. Chặn trùng không bao giờ chạy.** `consumed` được khởi tạo bằng
`set(DEFAULT_BUTTONS.values())` nên chứa **int**, nhưng phép kiểm tra lại là
`if key in self.consumed` với `key = "key305"` — **string**. Một string không bao
giờ nằm trong tập int, nên điều kiện luôn đúng và `_accept` chạy mọi khung hình
mà phím còn giữ. Một lần bấm vậy điền dần bước sau, bước sau nữa.

**2. A và B vừa là nút cần thử vừa là phím điều hướng.** `handle_input` dùng SDL
edge `btn_a` để "bỏ qua". Người dùng ấn A đúng theo yêu cầu thì bị hiểu thành bỏ
qua chính bước đó — dòng `bo qua a` ngay trước khi `b -> 305`.

Ngoài ra bản đồ sai đã lưu vẫn được backend dùng tiếp: `loadMapping` chỉ bỏ mã
ngoài phạm vi, không kiểm tra trùng.

### Cách sửa

- `consumed` so sánh bằng **int** (`if code in self.consumed`).
- Thêm cổng `wait_release`: sau khi gán phải thả hết phím mới gán tiếp.
- A/B **không** dùng làm phím điều hướng khi đang thử. Điều hướng dùng D-pad:
  `ABS_HAT0Y` lên = bỏ qua, xuống = lùi; giữ `ABS_HAT0X` 1.5 s = thoát không lưu.
- Bỏ cơ chế "giữ phím để bỏ qua": lần bấm đầu tiên đã bị gán nên không bao giờ
  kịp chạy ngưỡng giữ. Xóa hẳn thay vì giữ mã chết.
- `duplicate_buttons()` trong Python và Go: từ chối lưu và từ chối nạp bản đồ
  có hai nút chung mã, kèm cảnh báo tên rõ các nút bị trùng.
- Màn hình hiện dòng `Đang giữ: <mã>` và mã phím dưới từng nút, để đọc trực
  tiếp trên máy mà không cần app ngoài.

### Thêm lỗi phát hiện cùng lúc

`BrickBluetooth.log` cho thấy BlueZ báo:

```
bluetoothd[25089]: Unable to parse record for TrimUI Brick Pro Gamepad
```

Nguyên nhân: attribute `0x000d` trong SDP record thiếu một `</sequence>`.
Test `TestServiceRecordIsWellFormedXML` bắt được ngay.

`disablePowerSaving()` cũng phải bỏ: `hciconfig` của Stock OS không có
`pkt_type`, `power_save`, `sc_only`, và mỗi lần gọi đều in ra `hci0 ... DOWN`.
Chỉ giữ lại `rfkill unblock`.

## 5. Cách dùng màn hình THỬ NÚT

Bản đồ ánh xạ nằm ở `bluetooth-map.json` trong thư mục app, backend nạp bằng
cờ `--map-file`. Xóa file để trở về mặc định.

1. Cài ZIP beta đè lên bản cũ.
2. `TAY CẦM BLUETOOTH` → bấm **X**.
3. App lần lượt hỏi: A, B, X, Y, L1, R1, L3, R3, SELECT, START.
4. **Ấn đúng một nút rồi thả hẳn.** Dòng `Đang giữ: <mã>` cho biết kernel
   báo gì; đợi mất chữ "Nha het nut roi moi an buoc sau" mới sang bước kế.
5. D-pad lên = bỏ qua, D-pad xuống = lùi, giữ D-pad trái/phải 1.5 s = thoát.
6. Xong 10 bước thì **A** lưu, **B** làm lại.

Mã phim đã thuộc về nút khác không bao giờ được gán trùng; mã ngoài
`0x130..0x140` bị bỏ qua, vì đó không phải mã nút gamepad. Nếu còn trùng, app
**không lưu** và báo rõ tên các nút bị trùng.

Sau khi lưu, quay lại và bấm **A** để bắt đầu phiên Bluetooth. Backend in ra
`Button map: <path> (version 1, N override(s))` và
`WARNING: several buttons share one key code: ...` nếu bản đồ còn trùng.

## 6. Việc chưa làm

- **Profile máy chủ PC/Xbox/PS4.** Padpod dùng descriptor DS4 và Xbox Wireless thật.
  Cần bản mô tả chính xác từ `hid-sony.c` / `hid-playstation.c` / dump của xpadneo;
  không nên đoán, vì sai descriptor sẽ hỏng luôn đường đang chạy tốt.
- **Rumble.** Brick Pro không có motor rung; backend không khai báo Output Report.
- **Xác nhận nút trên máy thật.** Mọi khẳng định về nút ở trên đến từ bitmap `B: KEY=`
  trong log, chưa phải từ thử bấm.
- **`stay_awake` khi đang stream.** Chỉ giữ `stay_alive`; chưa thử idle timer dài.

## 7. Tham chiếu

- `include/net/bluetooth/hidp.h` và `net/bluetooth/hidp/core.c` — đặc tả HIDP.
- `drivers/input/input.c` — `input_seq_print_bitmap()`.
- `files/docs/bluetooth-native-build.json` — hash binary, dependency, cờ build.
- `files/docs/BLUETOOTH_THIRD_PARTY_NOTICES.txt` — giấy phép Go runtime và dependency.