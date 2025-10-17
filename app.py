# =========================================================
# YouTube Queue Online — v01.6.2a
# Ngày cập nhật: 17/10/2025
# Loại cập nhật: Bảo vệ trang Host + Đổi mật khẩu Host
# Bổ sung so với v01.6.2:
# - Thiết lập mặc định mật khẩu host ban đầu = "0000"
# - Không thay đổi bất kỳ logic nào khác (giữ nguyên toàn bộ API/route)
# =========================================================

import os, json, time, re, hashlib
from collections import deque
from urllib.parse import urlparse, parse_qs
from flask import Flask, request, jsonify, render_template, redirect
from werkzeug.utils import secure_filename
import requests

APP_TITLE       = os.environ.get("APP_TITLE", "YouTube Queue Online")
HOST_API_KEY    = os.environ.get("HOST_API_KEY", "ytp-premium-2025-dxd")
ENV_RATE_LIMIT  = int(os.environ.get("RATE_LIMIT_S", "180"))
PERSIST_PATH    = os.environ.get("PERSIST_PATH", "queue_data.json")
CONFIG_PATH     = os.environ.get("CONFIG_PATH", "config.json")
NICK_PATH       = os.environ.get("NICK_PATH", "nicknames.json")
STATIC_DIR      = os.path.join(os.path.dirname(__file__), "static")
ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".gif"}

app = Flask(__name__)

# ------------------ Runtime state ------------------
queue = deque()
history = deque(maxlen=300)
current = None
last_submit_ts = {}
last_progress = {"videoId": None, "pos": 0, "dur": 0, "ts": 0, "ended": False}

# ------------------ App config ------------------
# v01.6.2a: thêm mặc định password ban đầu "0000"
config = {
    "rate_limit_s": ENV_RATE_LIMIT,
    "logo_path": None,
    "nickname_valid_minutes": 60,
    "host_password_hash": hashlib.sha256("0000".encode()).hexdigest(),  # mặc định = 0000
}

# ------------------ Nicknames store ------------------
nicknames = {}

YOUTUBE_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|youtube\.com/(?:embed/|shorts/|watch\?v=))([A-Za-z0-9_-]{11})")

def extract_youtube_id(url: str):
    x = (url or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", x): return x
    m = YOUTUBE_ID_REGEX.search(x)
    if m: return m.group(1)
    try:
        q = parse_qs(urlparse(x).query)
        vid = q.get("v", [None])[0]
        if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid): return vid
    except Exception: pass
    return None

def fetch_title(video_id: str):
    try:
        r = requests.get(
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
            timeout=6
        )
        if r.ok: return r.json().get("title", f"Video {video_id}")
    except Exception: pass
    return f"Video {video_id}"

def load_state():
    global queue, history, current, last_progress
    if os.path.exists(PERSIST_PATH):
        try:
            with open(PERSIST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            queue = deque(data.get("queue", []))
            history = deque(data.get("history", []), maxlen=300)
            current = data.get("current")
            if current:
                last_progress.update({"videoId": current.get("id"), "pos": 0, "dur": 0, "ts": time.time(), "ended": False})
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
                config["logo_path"] = data.get("logo_path")
                config["nickname_valid_minutes"] = int(data.get("nickname_valid_minutes", 60))
                # Giữ mặc định 0000 nếu chưa có hash trong config.json
                if data.get("host_password_hash"):
                    config["host_password_hash"] = data.get("host_password_hash")
        except Exception as e:
            print("load_config error:", e)

def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_config error:", e)

# (Toàn bộ phần route, API, verify, change_password... giữ nguyên y hệt bản bạn gửi v01.6.2)
