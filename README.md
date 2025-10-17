# YouTube Queue Online — v01.6.1

- HOST_API_KEY chính thức: `ytp-premium-2025-dxd` (auto inject xuống host.html)
- Route người dùng: `/user` (`templates/user.html`)
- Route host điều khiển: `/host` (`templates/host.html`)
- `/api/config` & `/api/logo` cập nhật tức thì (không reload)
- Auto-next; Prev/Start/Next/Clear/Remove hoạt động
- UI giữ nguyên (chỉ sửa chức năng)

## Cấu trúc
```
.
├── app.py
├── Procfile
├── render.yaml
├── requirements.txt
├── README.md
├── /templates/
│   ├── host.html
│   └── user.html
└── /static/
    ├── host.js
    ├── app.js
    └── style.css
```

## Chạy local
```bash
pip install -r requirements.txt
set HOST_API_KEY=ytp-premium-2025-dxd
python app.py
# Mở http://localhost:5000/user và http://localhost:5000/host
```

## Deploy Render
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --workers=2 --threads=4 --timeout=120`
- Env:
  - `HOST_API_KEY=ytp-premium-2025-dxd`
  - `RATE_LIMIT_S=180`
