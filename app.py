
import os, json, time, re
from collections import deque
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import requests

APP_TITLE      = os.environ.get("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY   = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")
ENV_RATE_LIMIT = int(os.environ.get("RATE_LIMIT_S", "180"))
PERSIST_PATH   = os.environ.get("PERSIST_PATH", "queue_data.json")
CONFIG_PATH    = os.environ.get("CONFIG_PATH", "config.json")
STATIC_DIR     = os.path.join(os.path.dirname(__file__), "static")
ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".gif"}

app = Flask(__name__)

queue = deque()
history = deque(maxlen=300)
current = None
last_submit_ts = {}
last_progress = {"videoId": None, "pos": 0, "dur": 0, "ts": 0, "ended": False}

config = {"rate_limit_s": ENV_RATE_LIMIT, "logo_path": None}

YOUTUBE_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|shorts/|watch\?v=))([A-Za-z0-9_-]{11})")

def extract_youtube_id(url: str):
    x = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", x):
        return x
    m = YOUTUBE_ID_REGEX.search(x)
    if m: return m.group(1)
    try:
        q = parse_qs(urlparse(x).query)
        vid = q.get("v", [None])[0]
        if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return vid
    except Exception:
        pass
    return None

def fetch_title(video_id: str):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=6)
        if r.ok: return r.json().get("title", f"Video {video_id}")
    except Exception:
        pass
    return f"Video {video_id}"

def load_state():
    global queue, history, current, last_progress
    if not os.path.exists(PERSIST_PATH): return
    try:
        with open(PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        queue = deque(data.get("queue", []))
        history = deque(data.get("history", []), maxlen=300)
        current = data.get("current")
        if current:
            last_progress = {"videoId": current.get("id"), "pos": 0, "dur": 0, "ts": time.time(), "ended": False}
    except Exception as e:
        print("load_state error:", e)

def save_state():
    try:
        with open(PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump({"queue": list(queue), "history": list(history), "current": current}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_state error:", e)

def load_config():
    global config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config["rate_limit_s"] = int(data.get("rate_limit_s", ENV_RATE_LIMIT))
                config["logo_path"]    = data.get("logo_path")
        except Exception as e:
            print("load_config error:", e)

def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_config error:", e)

def get_rate_limit_s():
    return int(config.get("rate_limit_s") or ENV_RATE_LIMIT)

def set_next_current():
    global current, last_progress
    current = queue.popleft() if queue else None
    last_progress = {"videoId": current["id"] if current else None, "pos": 0, "dur": 0, "ts": time.time(), "ended": False}
    save_state()
    return current

def get_logo_url():
    if config.get("logo_path"):
        return f"/{config['logo_path']}?t={int(time.time())}"
    return None

def require_host_key():
    if request.headers.get("X-Host-Key") != HOST_API_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

@app.route("/")
def page_index():
    return render_template("index.html", app_title=APP_TITLE, rate_limit_s=get_rate_limit_s(), logo_url=get_logo_url())

@app.route("/host")
def page_host():
    return render_template("host.html", app_title=APP_TITLE, logo_url=get_logo_url())

@app.route("/api/state")
def api_state():
    global last_progress
    if last_progress.get("ended") and queue:
        if current: history.appendleft(current)
        set_next_current()
        last_progress["ended"] = False
    return jsonify({
        "current": current,
        "queue": list(queue),
        "history": list(history),
        "progress": last_progress,
        "config": {"rate_limit_s": get_rate_limit_s(), "logo_url": get_logo_url()}
    })

@app.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json(silent=True) or {}
    url  = (data.get("url") or "").strip()
    ip   = request.remote_addr or "unknown"

    now = time.time()
    remain = get_rate_limit_s() - int(now - last_submit_ts.get(ip, 0))
    if remain > 0:
        return jsonify({"ok": False, "error": f"Please wait {remain}s."}), 429

    vid = extract_youtube_id(url)
    if not vid:
        return jsonify({"ok": False, "error": "Paste a YouTube video link (not playlist)."}), 400

    title = fetch_title(vid)
    item = {"id": vid, "title": title, "by": ip, "ts": int(now)}
    queue.append(item)
    last_submit_ts[ip] = now

    if not current:
        set_next_current()

    save_state()
    return jsonify({"ok": True, "item": item})

@app.route("/api/next", methods=["POST"])
def api_next():
    unauth = require_host_key()
    if unauth: return unauth
    if current: history.appendleft(current)
    set_next_current()
    return jsonify({"ok": True, "current": current})

@app.route("/api/prev", methods=["POST"])
def api_prev():
    unauth = require_host_key()
    if unauth: return unauth
    global current, queue
    if history:
        if current: queue.appendleft(current)
        current = history.popleft()
        save_state()
        return jsonify({"ok": True, "current": current})
    return jsonify({"ok": False, "error": "No previous"}), 400

@app.route("/api/play", methods=["POST"])
def api_play():
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    vid  = data.get("videoId")
    global current
    if vid:
        if current: history.appendleft(current)
        title = fetch_title(vid)
        current = {"id": vid, "title": title, "by": "host", "ts": int(time.time())}
        save_state()
    else:
        if not current:
            set_next_current()
    return jsonify({"ok": True, "current": current})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    unauth = require_host_key()
    if unauth: return unauth
    queue.clear()
    save_state()
    return jsonify({"ok": True})

@app.route("/api/remove", methods=["POST"])
def api_remove():
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    vid  = data.get("id")
    if not vid: return jsonify({"ok": False}), 400
    from collections import deque as dq
    global queue
    newq, removed = dq(), False
    for it in list(queue):
        if not removed and it["id"] == vid:
            removed = True
            continue
        newq.append(it)
    queue = newq
    save_state()
    return jsonify({"ok": True, "removed": removed})

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({"rate_limit_s": get_rate_limit_s(), "logo_url": get_logo_url()})
    unauth = require_host_key()
    if unauth: return unauth
    data = request.get_json(silent=True) or {}
    if "rate_limit_s" in data:
        try:
            v = int(data["rate_limit_s"])
            if v < 10: v = 10
            config["rate_limit_s"] = v
        except Exception:
            pass
    save_config()
    return jsonify({"ok": True, "rate_limit_s": get_rate_limit_s()})

@app.route("/api/logo", methods=["POST"])
def api_logo():
    unauth = require_host_key()
    if unauth: return unauth
    if "logo" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["logo"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    fn = secure_filename(f.filename)
    ext = os.path.splitext(fn)[1].lower()
    if ext not in {".png",".jpg",".jpeg",".gif"}:
        return jsonify({"ok": False, "error": "Invalid file type"}), 400
    try:
        for old in os.listdir(STATIC_DIR):
            if old.startswith("logo"):
                try: os.remove(os.path.join(STATIC_DIR, old))
                except Exception: pass
    except Exception:
        pass
    save_name = f"logo{ext}"
    full = os.path.join(STATIC_DIR, save_name)
    f.save(full)
    config["logo_path"] = f"static/{save_name}"
    save_config()
    return jsonify({"ok": True, "logo_url": f"/{config['logo_path']}"} )

@app.route("/api/progress", methods=["POST"])
def api_progress():
    unauth = require_host_key()
    if unauth: return unauth
    global last_progress
    data = request.get_json(silent=True) or {}
    pos   = float(data.get("pos", 0))
    dur   = float(data.get("dur", 0))
    ended = bool(data.get("ended", False))
    vid   = data.get("videoId")
    ts    = time.time()
    last_progress = {"videoId": vid, "pos": pos, "dur": dur, "ts": ts, "ended": ended}
    if ended:
        if current: history.appendleft(current)
        set_next_current()
        last_progress["ended"] = False
    return jsonify({"ok": True})

@app.route("/healthz")
def healthz():
    return "ok", 200

def boot():
    load_config()
    load_state()
boot()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")), debug=False)
