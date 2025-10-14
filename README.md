# YouTube Queue Online — v07 (Render-ready, HTTP polling)
- Không dùng eventlet/socketio → chạy ổn định trên Render Free.
- User: trang `/` để submit video + xem queue/current/history (poll 2s).
- Host: trang `/host` (nhập HOST_API_KEY) để Next/Clear/Remove, đổi RATE_LIMIT_S, upload logo.
- Optional: `/api/progress` (host key) nếu bạn dùng extension để báo tiến độ/đã hết bài.
