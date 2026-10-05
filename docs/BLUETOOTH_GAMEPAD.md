# Brick Pro Bluetooth Gamepad — hồ sơ kỹ thuật

> Cập nhật: 2026-10-03. Áp dụng cho `v0.3.29-beta1`.

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

> **Cảnh báo: mục này sai và đã bị bác bỏ.** Bảng dưới đây suy ra từ dòng
> `B: KEY=` mà driver khai báo, và nó dự đoán sai ba mã: `316` (MENU) và `317`
> (L3) đều **có thật** trên máy, còn `305`/`304` của A/B bị đảo. Xem mục 4d
> cho số đo thật. Giữ lại để thấy sai ở đâu; không dùng làm nguồn ánh xạ.

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
| A / B | 304 / 305 | **305 / 304** | **đảo, xem mục 4d** |
| X / Y | 307 / 308 | **308 / 307** | **đảo, xem mục 4d** |
| L1 / R1 | 310 / 311 | có | đúng |
| SELECT / START | 314 / 315 | có | đúng |
| L2 / R2 analog | axis 2 / 5, range 0..255 | có | đúng, **không có mã phím** |
| 2 joystick | axis 0/1 và 3/4, range ±32767 | có | đúng |
| D-pad | axis 16/17 (hat) | có | đúng |
| L3 | 317 (BTN_THUMBL) | **có** | bitmap sai, xem mục 4d |
| R3 | 318 (BTN_THUMBR) | có | đúng |
| MENU | 316 (BTN_MODE) | **có** | bitmap sai, xem mục 4d |
| 5 phím còn lại | — | 60, 63, 114, 115, 172 | chưa gán |

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

## 4d. Kết quả ghi thô trên máy thật (2026-10-03)

`BrickButtons.log` từ lần test đầu tiên **sạch hoàn toàn**: 18 lần bấm, mỗi
nút một mã riêng, không mã nào trùng, và **không dòng nào có trường `codes=`**
(tức firmware không phát mã thừa).

```
001 +3.30s   keys=305      <- A
002 +6.04s   keys=304      <- B
003 +7.44s   keys=308      <- X
004 +8.96s   keys=307      <- Y
005 +11.81s  keys=310      <- L1
006 +12.83s  keys=311      <- R1
007 +27.73s  keys=317      <- L3
008 +29.03s  keys=318      <- R3
009 +37.45s  keys=314      <- SELECT
010 +38.84s  keys=315      <- START
```

### Bản đồ thật, đã đưa vào mặc định

| Nút | Mã | Mặc định cũ | |
|---|---|---|---|
| A | **305** | 304 | **đảo** |
| B | **304** | 305 | **đảo** |
| X | **308** | 307 | **đảo** |
| Y | **307** | 308 | **đảo** |
| L1 / R1 | 310 / 311 | 310 / 311 | đúng |
| L3 / R3 | **317** / 318 | 317 / 318 | L3 có thật |
| SELECT / START | 314 / 315 | 314 / 315 | đúng |

Người dùng đã xác nhận trực tiếp: bấm A ra 305, bấm B ra 304. Đây là hành vi
của firmware Stock OS, giữ nguyên.

### Đính chính: bản giải mã bitmap ở mục 2 là sai

Mục 2 kết luận `317` (BTN_THUMBL) không tồn tại và không có `316` (BTN_MODE),
dựa trên dòng `B: KEY=`. Máy thật báo **cả hai**. Bản giải mã
`input_seq_print_bitmap()` của kernel 4.9 đã đọc sai số word.

Hậu quả trực tiếp: `v0.3.29-beta1` dùng quy tắc "mọi mã ngoài `0x130..0x140`
là phím thoát" để tránh đoán mã MENU. Nhưng **316 nằm trong khoảng đó**, nên
quy tắc ấy chặn đúng nút thoát — giữ MENU không thoát màn hình.

Mã `B: KEY=` không nên là nguồn duy nhất. Nó là khả năng mà driver khai báo, còn
`BrickButtons.log` là việc thật đã xảy ra. Khi hai nguồn lệch nhau, tin việc
thật.

### Những gì log này sửa

1. **A/B và X/Y đảo.** Sửa `defaultMapping()` ở Go và `_default_buttons()` ở
   Python. Test `TestBuiltInTableMatchesTheMeasuredDevice` chốt lại.
2. **MENU = 316**, xác nhận bằng chính log (dòng 013, 014, 016, 017 đều là
   `keys=316` — đúng những lần người dùng giữ MENU).
3. **L2/R2 không có mã phím** — chúng là cảm biến analog (axis 2/5). Chúng có
   trong `DEFAULT_ORDER` nên mọi thứ lệch sau R1: log chỉ có **10** dòng cho
   **12** lần bấm. Đã bỏ khỏi danh sách, và `mapping.go` không gán mã cho
   chúng nữa (`duplicateButtons()` bỏ qua mã 0 để không báo trùng giả).
4. **Phím thoát đã xóa vẫn lọt vào log.** `_drop_exit_only_entry()` sửa
   `probe.reported`, còn màn hình giữ danh sách riêng `self.entries`. Nay
   `reported` là nguồn duy nhất.

### Về issue #67 và giả thuyết "firmware báo mã không ổn định"

`v0.3.29-beta1` xây cả bộ ghi thô lẫn giả định firmware phát nhiều mã cùng lúc
dựa trên log `Chiaki-debug.log` của issue #67. Log hôm nay **không có dòng nào**
có `codes=` — giả định đó không được chứng minh trên bản firmware của người
dùng.

Cách hiểu hợp lý hơn: log #67 ghi `asked=a` rồi `code=304`, rồi `code=305` cho
cùng một nút. Với bản đồ cũ (A=304), app hỏi A và nhận 305 — người dùng bấm
nhầm B, hoặc bấm A nhưng màn hình hỏi sai. Trường hợp `L3 → 316, 317` cũng
giải thích được: 316 là MENU, 317 là L3 thật.

Kết luận: giả thuyết nhiễu phải đặt lại thành câu hỏi mở. Hiện tại **không có
bằng chứng nào** cho thấy firmware phát mã thừa trên máy này.

### Log 18:32 cùng ngày và ba sửa trong `v0.3.31-beta1`

Log thứ hai vẫn ghi đúng từng nút riêng, nhưng có hai lỗi do app:

1. **Mất hai dòng đã ghi.** Log nhảy từ `008` sang `011`: khi người dùng giữ
   START+SELECT để thoát, `_drop_exit_only_entry()` lọc lại toàn bộ
   `probe.reported` và xóa cả hai dòng SELECT/START đã đóng trước đó. Bản sửa
   chỉ bỏ entry thoát đang mở trong đúng cử chỉ đó; các lần bấm độc lập cũ
   được giữ nguyên, nên số thứ tự không nhảy nữa.
2. **Một lần bấm hiện hai dòng giống hệt nhau.** Người dùng báo bấm A một lần
   nhưng màn hình hiện nội dung `001 ... keys=305` hai lần: một lần ở dòng
   "Vừa bấm", một lần ở dòng đầu bảng. Danh sách nay loại đúng dòng mới nhất
   đã in riêng, nên mỗi lần bấm chỉ còn một dòng.
3. **A không còn là nút lưu.** Người dùng đã yêu cầu bỏ việc "bấm A để lưu"
   từ trước. `HOLD_EXIT_SECONDS` nay là **2,0 giây**: giữ MENU 2 giây vừa lưu
   `BrickButtons.log` vừa thoát; START+SELECT giữ 2 giây là dự phòng.

### MENU thoát, không dùng A/B

- **Giữ MENU 2 s** → lưu log và thoát.
- **Giữ START + SELECT 2 s** → lưu log và thoát, dự phòng.

`_exit_gesture()` chỉ nhận MENU khi nó được giữ **một mình** (`keys ==
{316}`), và `START+SELECT` khi đúng hai phim đó. Có test cho trường hợp MENU
đi kèm nút khác: bấm A kèm mã 316 phải **không** thoát.

## 4f. May that Android (Oppo Reno5, 2026-10-03) và ba sửa `v0.3.33-beta1`

Nối Android thành công, tester PS mode type 1 nhận đủ nút. Đây là bằng chứng
quyết định: **đường truyền + report HID của mình đúng**, iPhone không nhận chỉ
vì nó kén chuẩn (xem mục 6: cần profile DS4/Xbox riêng).

Ba lỗi ánh xạ lộ ra trên Android, đều do bit HID đi theo **tên** nút trong khi
tester đặt tên theo **vị trí** chuẩn (bit0=Cross/dưới, bit1=Circle/phải,
bit3=Square/trái, bit4=Triangle/trên):

1. **A/B và X/Y ngược vị trí.** Brick Pro dùng layout kiểu Nintendo (A ở
   Đông/phải, B ở Nam/dưới — `inputs.go` đã ghi rõ và phải đảo A↔B, X↔Y).
   Trước đây A(305)→bit0 nên hiện Cross, B(304)→bit1 nên hiện Circle; X→bit3
   hiện Square, Y→bit4 hiện Triangle. Nay bit đi theo vị trí: B→0, A→1, Y→3,
   X→4 (`hidButtons` trong `mapping.go`). Test
   `TestFaceButtonsFollowPhysicalPosition` chốt lại.
2. **Nút PS trống.** MENU (316) chưa bao giờ được gửi đi. Nay gửi ở **bit 12**
   (giả thiết cần máy thật xác nhận: bấm MENU mà nút PS sáng thì đúng).
3. **B dừng phiên.** B là nút test trên điện thoại mà bấm vào dừng luôn phiên
   Bluetooth. Nay B khi đang chạy bị bỏ qua; dừng bằng **giữ MENU 2 giây**
   (guard native đã đọc trực tiếp evdev, hạ từ 3s xuống 2s cho cùng một mốc).
   `quit` (phím Q/SDL_QUIT, không phải nút tay cầm) giữ làm lối thoát khẩn cấp.

PS mode type 2 của tester xáo nút lung tung — bỏ qua, chỉ dùng type 1.

## 4g. Profile nút (`v0.3.34-beta1`): ghi rõ và chọn được

Profile đã đo trên Android được ghi thành bảng, không còn nằm ngầm trong code.
Menu `TAY CẦM BLUETOOTH` có mục chọn (Trái/Phải khi chưa kết nối), lưu vào
`settings.json` (`gamepad_profile`), backend nhận qua `--profile`:

| Profile | Bit nút mặt | Khi nào dùng |
|---|---|---|
| `ps` (mặc định) | B→0, A→1, Y→3, X→4 (theo vị trí) | Tester PS-mode, game — đã đo trên Oppo Reno5 |
| `labels` | A→0, B→1, X→3, Y→4 (theo tên vỏ) | Công cụ đặt tên theo thứ tự label; cách cũ trước v0.3.33 |
| `ds4` (thử nghiệm, từ `v0.3.37-beta1`) | DS4 thật: B→cross, A→circle, Y→square, X→triangle, MENU→PS; stick 0–255; cò analog | iPhone — cần máy thật kiểm chứng |

Các bit còn lại giống nhau ở cả hai profile: L1→6, R1→7, L2→8, R2→9,
Select→10, Start→11, PS(MENU)→12, L3→13, R3→14. Tên lạ rơi về `ps`.

## 4h. iOS: tại sao chưa nhận, và làm DS4/Xbox ra sao (sau stable)

Triệu chứng trên iPhone: ghép nối Bluetooth thành công (PSM 17/19, `HID
connected`, phiên giữ hàng phút không lỗi) nhưng không app nào thấy controller.
Nguyên nhân: iOS chỉ sinh controller cho loại nó biết sẵn (MFi, Xbox Wireless,
DualShock/DualSense). Gamepad HID generic ghép nối được nhưng không bao giờ
thành `GCController`. Android nhận generic nên cùng một bản chạy tốt trên
Oppo Reno5 — đối chứng này loại trừ lỗi đường truyền/report.

Hướng làm (workstream riêng, vài vòng beta, cần iPhone test từng vòng):

1. **Giả lập tay cầm thật theo profile**, dùng đúng chỗ profile hiện có
   (`--profile ds4` / `--profile xbox`): descriptor HID + layout report lấy
   từng byte từ nguồn công khai — `hid-sony.c` / `hid-playstation.c` của kernel
   (đã kiểm tra tải được) và dump xpadneo. Không chép code Padpod, không đoán.
2. DS4 qua Bluetooth dùng input report `0x11` kèm CRC32; iOS còn gửi feature
   GET_REPORT khi bắt tay — backend hiện trả lỗi các report lạ nên phải cài
   trả lời đúng (`controlResponse` trong `hid.go`).
3. SDP bổ sung PnP ID (VID/PID Sony/Microsoft) và tên "Wireless Controller" /
   "Xbox Wireless Controller" cho đúng loại giả lập.
4. Mỗi vòng chỉ tin kết quả trên iPhone thật: hiện controller, đủ nút, stick
   full range, không đứt phiên.

Rủi ro đã thấy trước: iOS có thể kiểm tra sâu hơn descriptor (hành vi bắt tay,
thứ tự query), nên vòng đầu có thể vẫn chưa hiện. Không đưa vào bản stable.

## 5. Cách dùng màn hình GHI NÚT

Bản đồ ánh xạ nằm ở `bluetooth-map.json` trong thư mục app, backend nạp bằng
cờ `--map-file`. Xóa file để trở về mặc định.

1. Cài ZIP beta đè lên bản cũ.
2. `TAY CẦM BLUETOOTH` → bấm **X**.
3. Bấm từng nút một lần theo thứ tự in trên màn hình (`1.A 2.B ... 10.START`).
   **L2/R2 không có mã phím** nên không cần bấm.
4. Giữ **MENU 2 giây** để lưu log và thoát (START + SELECT 2 giây là dự phòng).

Log ra `BrickButtons.log`:

```
## Brick Pro button press log
## keys=  first key code reported
## codes= extra codes in the same moment (repeats or noise)
## held=  how long the button was held
001 +1.20s   keys=305
002 +3.45s   keys=304 held=120ms
```

Backend in ra `Button map: <path> (version 1, N override(s))` và
`WARNING: several buttons share one key code: ...` nếu bản đồ còn trùng.

## 6. Việc chưa làm

- **Profile máy chủ PC/Xbox/PS4.** Padpod dùng descriptor DS4 và Xbox Wireless thật.
  Cần bản mô tả chính xác từ `hid-sony.c` / `hid-playstation.c` / dump của xpadneo;
  không nên đoán, vì sai descriptor sẽ hỏng luôn đường đang chạy tốt.
- **Rumble.** Brick Pro không có motor rung; backend không khai báo Output Report.
- **Xác nhận trên điện thoại.** Bản đồ ở mục 4d đã đo bằng log ghi thô trên máy
  thật, nhưng chưa xác nhận điện thoại hiển thị đúng sau khi sửa A/B và X/Y.
  Đó là bước kiểm chứng tiếp theo.
- **5 phím chưa gán (60, 63, 114, 115, 172).** Không biết là nút gì trên vỏ máy.
  Cần đoán nốt bằng cách bấm từng nút và xem mã ra, nếu quan tâm tới chúng.
- **`stay_awake` khi đang stream.** Chỉ giữ `stay_alive`; chưa thử idle timer dài.

## 7. Tham chiếu

- `include/net/bluetooth/hidp.h` và `net/bluetooth/hidp/core.c` — đặc tả HIDP.
- `drivers/input/input.c` — `input_seq_print_bitmap()`.
- `files/docs/bluetooth-native-build.json` — hash binary, dependency, cờ build.
- `files/docs/BLUETOOTH_THIRD_PARTY_NOTICES.txt` — giấy phép Go runtime và dependency.