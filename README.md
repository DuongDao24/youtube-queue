# YouTube Queue Online — v09 (package) / **internal app version: v01.6**

- Host phát bằng YouTube IFrame API (không cần extension)
- Auto-next + Countdown 3-2-1 (góc phải dưới)
- User: submit + queue + now playing + history + progress sync
- Host: Play/Next/Prev/Remove/Clear + Upload logo + Save settings
- Polling 2s, chạy ổn Render Free

## Quan trọng
- **HOST_API_KEY mặc định**: `0000` (có thể đổi trong biến môi trường Render)
- **RATE_LIMIT_S mặc định**: `180`
- File lưu **state**: `queue_data.json`, config: `config.json` (tạo tự động)

## Deploy nhanh (Render)
1. Tạo dịch vụ Web mới (Python).
2. Kéo thả/Push repo này.
3. Kiểm tra `render.yaml` hoặc đặt Env:
   - `HOST_API_KEY=0000`
   - `RATE_LIMIT_S=180`
4. Mở `/host`, nhập HOST_API_KEY và **Save key** để điều khiển.

## Ghi chú phát hành
- Gói v09, mã nguồn **v01.6** (ghi version trong đầu file, README và CSS).
- Fix tràn chữ (ellipsis), giảm alert spam 401, UX submit rõ ràng.
