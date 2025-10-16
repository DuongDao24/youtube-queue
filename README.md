# YouTube Queue Online — v08.2 (Root Ready, Render-ready)

**New in v08.2**
- Host login (Admin/0000) with session, changeable via HOST_API_KEY
- Resume video after host reload (seek to last progress)
- Countdown 10 seconds before auto-next
- Settings input fix (no more reset while typing)
- Nickname required to submit
- Hide user IP on / (user), still visible on /host
- Removed Reload button

**Endpoints**
- `/` user page
- `/host` host page (login required)

**Deploy to Render**
- Build: `pip install -r requirements.txt`
- Start: `gunicorn -w 1 -k gevent -b 0.0.0.0:$PORT app:app`
- Env: `APP_TITLE`, `HOST_API_KEY`, `RATE_LIMIT_S`, `PYTHON_VERSION=3.11.9`
