# GitHub Issue relay

Relay này nhận log đã lọc từ app, lọc lại phía server và tạo Issue bằng token
chỉ lưu trong Cloudflare Worker secret. App và gói Release không chứa GitHub
token.

## Triển khai

1. Tạo fine-grained GitHub token chỉ cấp **Issues: Read and write** cho đúng repo.
2. Cài Wrangler, đăng nhập và tạo KV:

   ```sh
   npm install --global wrangler
   wrangler login
   wrangler kv namespace create REPORTS
   ```

3. Copy `wrangler.toml.example` thành `wrangler.toml`, điền KV namespace ID.
4. Lưu token dưới dạng Worker secret và deploy:

   ```sh
   wrangler secret put GITHUB_TOKEN
   wrangler deploy
   ```

5. Điền URL HTTPS kết thúc bằng `/report` vào `files/reporting.json`, ví dụ:

   ```json
   {
    "issue_relay_url": "https://trimui-chiaki-issue-relay.issue-relay.workers.dev/report"
   }
   ```

6. Worker tự giới hạn 10 request mỗi 10 phút cho mỗi IP băm. Có thể thêm WAF
   rate-limit phía Cloudflare làm lớp bảo vệ ngoài và điều chỉnh khi nhiều người
   dùng chung một NAT.
7. Thông báo rõ dữ liệu gửi đi; người thử chủ động bật **Tự động gửi lỗi lên
   GitHub** trong app. Cài mới mặc định tắt báo cáo.

## Mô hình an toàn

- `GITHUB_TOKEN` chỉ nằm trong Worker secret, không nằm trong source, URL, app,
  manifest, ZIP hay log.
- Client không gửi header xác thực. Không thêm “shared secret” vào app: người có
  file app luôn có thể trích xuất secret đó, nên nó không bảo vệ endpoint.
- Relay giới hạn kích thước, kiểm schema/fingerprint/title, lọc lại token, key,
  IP riêng, MAC/serial, rate-limit theo IP băm và chống trùng bằng KV 30 ngày.
- Relay chỉ trả trạng thái nhận, không trả URL hoặc tên repo private cho client.
- Endpoint vẫn là endpoint công khai và có thể bị gọi ngoài app. Rate-limit ở
  Cloudflare, quyền token tối thiểu và giám sát abuse là các lớp bảo vệ bắt buộc.
- Nếu nghi token lộ, revoke/rotate token trong GitHub rồi chạy lại
  `wrangler secret put GITHUB_TOKEN`; không cần phát hành lại app.

Không commit `wrangler.toml` nếu sau này thêm cấu hình riêng tư. File hiện chỉ
cần tên repo private và KV ID, nhưng giữ config triển khai cục bộ giúp tránh vô
tình thêm secret vào Git ở lần chỉnh sửa sau.

## Deployment hiện tại

- Worker: `trimui-chiaki-issue-relay`.
- Endpoint: `https://trimui-chiaki-issue-relay.issue-relay.workers.dev/report`.
- Repo nhận log: `nlkcodenew/trimui-chiaki-ng-diagnostics` (private).
- KV dedupe/rate-limit: `REPORTS`.
- E2E ngày 2026-09-25: tạo Issue `#1`, dedupe đạt; Issue kiểm thử đã đóng.
