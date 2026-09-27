# Điều tra PS4 Wakeup — chốt tại v0.3.23-beta12

> Cập nhật: 2026-09-27. Công việc wakeup đang **tạm dừng theo yêu cầu người
> dùng**. Tài liệu này ghi lại bằng chứng và các khoảng trống cần kiểm chứng;
> không phải kế hoạch tự động triển khai beta13.

## 1. Phạm vi và trạng thái phát hành

- Release ổn định vẫn là `v0.3.22`; stream PS4 đang online đã được xác nhận trên
  Brick Pro Stock OS và Smart Pro S/Spruce.
- Beta wake mới nhất là prerelease `v0.3.23-beta12`. Không đưa beta12 thành
  latest và không thay đổi stable trong quá trình điều tra.
- PS5 đã bị vô hiệu hóa khỏi discovery, UI, pair, wake và stream. Điều tra này
  chỉ áp dụng cho PS4 LAN.
- Thiết bị thử beta11/beta12 là Brick Pro, model `sun50iw10`. Issue dùng mã
  `HW-...`; không ghi IP, MAC, RP key hoặc Account-ID vào tài liệu.

## 2. Điều kiện máy thật đã kiểm tra

Người dùng đã thực hiện phép thử kiểm soát trước beta11:

1. Tắt hẳn PS4 để mất trạng thái GoldHEN/jailbreak.
2. Khởi động lại nhưng không chạy exploit.
3. Rút SSD box/ổ USB ngoài.
4. Xác nhận tùy chọn cho phép bật PS4 từ mạng vẫn bật.
5. Đưa PS4 về Rest Mode và chờ đèn vàng ổn định.
6. Giữ DNS chặn Sony/Internet để tránh cập nhật firmware.

Vì vậy GoldHEN và ổ ngoài không giải thích đầy đủ lỗi wake hiện tại. DNS chặn
Internet không trực tiếp chặn UDP nội bộ cổng `987`, nhưng chưa có phép thử A/B
với DNS bình thường nên không tuyên bố nó hoàn toàn không liên quan đến mọi hành
vi Rest Mode của firmware.

Ở một số beta cũ, PS4 từng chuyển sang đèn vàng nhấp nháy và ổ ngoài được cấp
điện sau lệnh wake nhưng không lên đèn trắng. Đây là bằng chứng PS4 đã có phản
ứng trong những lần đó, không phải bằng chứng mọi packet ở mọi lần thử đều tới
console.

## 3. Bằng chứng diagnostic mới nhất

### Issue #58 — beta11

- Scan ban đầu không thấy PS4 Rest Mode.
- DDP WAKEUP unicast 135 byte được gửi từ cổng nguồn `9303`.
- Sau khoảng 25,2 giây, probe thứ 26 nhận phản hồi `620 Standby`.
- PS4 tiếp tục trả `620 Standby` đến hết 120 giây và không bao giờ trả `200
  Ready`.
- Beta11 chủ ý chỉ gửi một WAKEUP, nên không có packet wake tiếp theo khi đã thấy
  `620`.

Kết luận giới hạn: trong lần thử này, đường UDP hai chiều TrimUI ↔ PS4 hoạt động
và PS4 vẫn ở Standby. Không thể chỉ từ `sendto()` kết luận packet wake đã được
firmware chấp nhận, nhưng phản hồi `620` chứng minh console đã trả lời SRCH sau
lệnh ban đầu.

### Issue #59 — beta12 discovery

- Scan gửi SRCH broadcast và unicast tới host đã pair từ cổng nguồn `9303`.
- Sau khoảng ba giây, kết quả vẫn là `0 host(s)`.
- App phục hồi host đã pair dưới trạng thái `offline` để người dùng có thể thử
  wake thủ công.

### Issue #60 — beta12 wake

- WAKEUP ban đầu được `sendto()` đủ 135 byte từ cổng nguồn `9303`.
- App gửi 240 SRCH unicast, chu kỳ 500 ms, trong 120,2 giây.
- Không nhận được bất kỳ phản hồi hợp lệ nào: trạng thái cuối là `unknown`.
- `standby_seen=False`, `standby_wake_attempted=False` và
  `standby_wake_sent=False`.
- Do không nhận `620 Standby`, nhánh mới của beta12 gửi WAKEUP thứ hai **không
  hề được thực thi**. Beta12 vì vậy chưa kiểm thử được giả thuyết cốt lõi của nó.

Sự khác nhau giữa #58 và #60 cho thấy phản hồi Rest Mode không ổn định giữa hai
lần thử. Không được diễn giải #60 thành “PS4 từ chối WAKEUP thứ hai”, vì packet
thứ hai chưa tồn tại; cũng không được diễn giải `initial_sent=True` thành “PS4
đã nhận”, vì cờ này chỉ xác nhận kernel chấp nhận đủ số byte UDP.

## 4. Chiaki-ng desktop thực sự làm gì

Đối chiếu source upstream trong `gui/src/discoverymanager.cpp`,
`gui/src/qmlbackend.cpp`, `lib/src/discovery.c` và
`lib/src/discoveryservice.c` cho thấy:

1. `DiscoveryManager` chạy discovery service lâu dài, với `PING_MS=500`.
2. Desktop có service broadcast theo interface và các service unicast riêng cho
   manual host; mỗi service giữ socket và thread nhận phản hồi sống liên tục.
3. DDP WAKEUP dùng đúng `rp_regist_key` diễn giải như số hex, gửi unicast tới
   cổng PS4 `987`. Upstream không dùng magic packet WOL cho luồng này.
4. Khi discovery service IPv4 đang active, `DiscoveryManager::SendWakeup()` tái
   sử dụng socket của discovery service chính để gửi WAKEUP; nó không bắt buộc
   mở socket wake tạm.
5. Khi người dùng chọn một host đã discover ở trạng thái `Standby`, desktop gửi
   WAKEUP rồi tạo session kết nối ngay, thay vì đợi `Ready` mới bắt đầu session.
6. Trong `updateDiscoveryHosts()`, nếu host vẫn `Standby` trong lúc session đang
   `IsConnecting()`, desktop gọi `sendWakeup()` lại. Source hiện tại không có cờ
   one-shot ở nhánh này, nên WAKEUP có thể được gửi trên nhiều update Standby,
   không chỉ đúng một lần.

Do đó mô tả trước đây “beta12 mô phỏng Chiaki desktop” cần hiểu hẹp: beta12 chỉ
mô phỏng chu kỳ SRCH 500 ms và ý tưởng gửi wake sau khi thấy `620`. Nó **không**
mô phỏng đầy đủ vòng đời socket, broadcast theo interface, việc bắt đầu session
song song, hay khả năng gửi lại WAKEUP trên các update Standby liên tiếp.

## 5. TrimUI beta12 đang làm gì

- Scan UI là transaction khoảng ba giây, dùng một socket rồi đóng.
- Khi chọn host `offline`, app mở một socket mới, thường bind lại cổng `9303`.
- App gửi một WAKEUP unicast, sau đó chỉ gửi SRCH unicast tới IP đã lưu mỗi 500
  ms và chờ tối đa 120 giây trên socket đó.
- App chỉ gửi thêm đúng một WAKEUP nếu socket này nhận được phản hồi Standby đầu
  tiên.
- App chỉ khởi chạy native stream sau khi đã thấy `Ready`; không thử kết nối
  native song song trong lúc console còn Standby.
- App không dùng magic WOL, directed-broadcast wake hoặc retry theo timer trong
  beta11/beta12.

Packet SRCH/WAKEUP, protocol version PS4, cổng đích và cách đổi registration key
sang credential khớp source upstream ở mức format đã rà soát. Tuy nhiên chưa có
packet capture cùng lúc giữa desktop thành công và TrimUI thất bại để chứng minh
hai datagram giống hệt trên dây.

## 6. Các vấn đề và giả thuyết còn mở

### Đã chứng minh

- Pair credential đủ dùng để remote PS4 khi máy đang online trên cả hai thiết bị
  thử; mất pair do cài sạch là vấn đề dữ liệu người dùng riêng, không phải lỗi
  wake protocol.
- Beta6 từng có lỗi gọi wrapper trước khi gửi packet; beta7 đã sửa và có test.
- Beta11 từng nhận `620 Standby`; đường phản hồi LAN có thể hoạt động.
- Beta12 không nhận `620`, nên không chạy nhánh WAKEUP xác nhận Standby.
- GoldHEN và SSD ngoài không phải điều kiện bắt buộc để tái hiện thất bại.
- `setterm: not found` không liên quan đến DDP wake.
- App không sửa `wowlan_triggers`; WoWLAN của TrimUI không phải cơ chế đánh thức
  PS4 trong các beta này.

### Chưa chứng minh

- Chưa có phép thử Chiaki-ng desktop trên đúng PS4, đúng LAN, đúng trạng thái DNS
  và cùng thời điểm để làm đối chứng thành công.
- Chưa có packet capture ở router/AP để biết datagram WAKEUP và SRCH nào thật sự
  rời TrimUI, tới PS4 và phản hồi quay về ở các lần #58/#60.
- Chưa biết khác biệt quyết định có phải socket discovery tồn tại lâu dài, địa
  chỉ broadcast theo interface, trạng thái ARP, retry theo từng `620`, hay việc
  session kết nối song song của desktop.
- Chưa biết vì sao PS4 trả `620` sau 25 giây ở beta11 nhưng im lặng toàn bộ ở
  beta12. Một lần thử mỗi beta không đủ tách biến trạng thái Rest Mode/LAN khỏi
  thay đổi phần mềm.
- Chưa chứng minh DNS chặn Sony hoàn toàn trung tính với firmware Rest Mode;
  chỉ có cơ sở rằng nó không chặn trực tiếp datagram LAN cổng `987`.
- Chưa chứng minh phản ứng đèn vàng nhấp nháy ở beta cũ là một boot bị kẹt do
  thiếu packet tiếp theo, session handshake, thiết bị USB hay trạng thái firmware.

## 7. Thứ tự kiểm chứng nếu tiếp tục ở session sau

Không sửa code trước khi người dùng chủ động tiếp tục. Khi tiếp tục, ưu tiên:

1. Dùng Chiaki-ng desktop làm control trên đúng PS4/LAN: ghi rõ phiên bản, trạng
   thái đèn, DNS, thời gian vào Rest Mode và kết quả wake.
2. Nếu desktop wake thành công, capture UDP `987` ở router/AP cho cả desktop và
   TrimUI; chỉ lưu metadata/packet đã che credential, IP và MAC khi đưa vào repo.
3. So sánh socket nguồn, đích unicast/broadcast, nhịp SRCH, số lần WAKEUP, thời
   điểm bắt đầu session và chuyển trạng thái `620 → 200`.
4. Lặp lại beta11/beta12 ít nhất ba lần với cùng quy trình Rest Mode để đo độ ổn
   định trước khi quy nguyên nhân cho thay đổi 1 giây → 500 ms.
5. Chỉ sau bằng chứng control/capture mới cân nhắc beta mới mô phỏng đầy đủ
   desktop: discovery service lâu dài, reuse socket, session kết nối song song và
   chính sách gửi lại trên Standby. Không quay lại magic WOL/broadcast mò mẫm.

## 8. Điểm dừng

- Không triển khai beta13 trong session này.
- Không sửa code wake, native stream, pair, input hoặc stable `v0.3.22`.
- Không xóa beta12: giữ prerelease và Issue #59/#60 làm mốc tái hiện.
- Session sau phải đọc tài liệu này trước `PROJECT_STATUS.md` và lịch sử beta.
