# ==========================================================
# YouTube Queue Online — v01.5.1
# Simplified Host (no HOST_API_KEY required)
# ==========================================================

import os, time, json
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# === Global Config ===
config = {
    "admin_user": os.getenv("HOST_USER", "Admin"),
    "admin_pass": os.getenv("HOST_PASS", "0000"),
    "rate_limit_s": int(os.getenv("RATE_LIMIT_S", "180")),
    "nick_change_hours": int(os.getenv("NICK_CHANGE_HOURS", "24")),
    "queue": [],
    "history": [],
    "names": {},
    "name_changed_at": {},
    "current": None,
    "progress": {},
    "logo_path": None,
}

# === Helpers ===
def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "0.0.0.0")

def persist():
    pass  # memory only (Render Free resets on restart)

# === Pages ===
@app.route("/")
def page_user():
    return render_template("user.html")

@app.route("/host")
def page_host():
    return render_template("host.html")

# === API endpoints ===

@app.route("/api/state")
def api_state():
    return jsonify({
        "config": {
            "rate_limit_s": config["rate_limit_s"],
            "nick_change_hours": config["nick_change_hours"],
        },
        "queue": config["queue"],
        "history": config["history"],
        "current": config["current"],
        "progress": config["progress"],
        "names": config["names"],
        "logo": config["logo_path"],
    })


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    u = data.get("username", "")
    p = data.get("password", "")
    if u == config["admin_user"] and p == config["admin_pass"]:
        return jsonify({"ok": True})
    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/api/admin/update_auth", methods=["POST"])
def api_update_auth():
    # Removed API key requirement for simplicity
    data = request.get_json(silent=True) or {}
    u = data.get("username")
    p = data.get("password")
    if u:
        config["admin_user"] = u
    if p:
        config["admin_pass"] = p
    return jsonify({"ok": True})


@app.route("/api/config", methods=["POST"])
def api_config():
    # Removed key authorization check (for free deployment ease)
    data = request.get_json(silent=True) or {}
    config["rate_limit_s"] = int(data.get("rate_limit_s", config["rate_limit_s"]))
    config["nick_change_hours"] = int(data.get("nick_change_hours", config["nick_change_hours"]))
    return jsonify({"ok": True})


@app.route("/api/logo", methods=["POST"])
def api_logo():
    # Removed host key requirement
    f = request.files.get("logo")
    if not f:
        return jsonify({"error": "No file"}), 400
    fn = "uploaded_logo." + f.filename.split(".")[-1]
    path = os.path.join("static", fn)
    f.save(path)
    config["logo_path"] = "/" + path
    return jsonify({"ok": True, "path": config["logo_path"]})


@app.route("/api/name", methods=["POST"])
def api_name():
    ip = client_ip()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    now = time.time()

    last_change = float(config["name_changed_at"].get(ip) or 0)
    if ip in config["names"] and now - last_change < config["nick_change_hours"] * 3600:
        remain = config["nick_change_hours"] * 3600 - (now - last_change)
        h = int(remain // 3600)
        m = int((remain % 3600) // 60)
        return jsonify({"error": f"Can change in {h}h{m:02d}m."}), 429

    if not name or len(name) > 24:
        return jsonify({"error": "Invalid name"}), 400

    config["names"][ip] = name
    config["name_changed_at"][ip] = now
    persist()
    return jsonify({"ok": True, "name": name})


# === Submit video ===
@app.route("/api/add", methods=["POST"])
def api_add():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip()
    ip = client_ip()

    # ✅ enforce nickname lock check
    saved_name = config["names"].get(ip)
    last_change = float(config["name_changed_at"].get(ip) or 0)
    now = time.time()
    lock_hours = int(config.get("nick_change_hours", 24))
    if saved_name and now - last_change < lock_hours * 3600:
        print(f"[nickname-lock] {ip} tried to change '{name}' -> kept '{saved_name}'")
        name = saved_name

    if not name:
        return jsonify({"error": "Nickname required"}), 400
    if not url.startswith("http"):
        return jsonify({"error": "Invalid URL"}), 400

    # enforce rate limit
    rate_limit = config["rate_limit_s"]
    if ip in config["progress"]:
        last_submit = config["progress"][ip].get("last_submit", 0)
        if time.time() - last_submit < rate_limit:
            remain = int(rate_limit - (time.time() - last_submit))
            return jsonify({"error": f"Wait {remain}s"}), 429

    vid = None
    if "youtube.com/watch" in url and "v=" in url:
        vid = url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0]
    if not vid:
        return jsonify({"error": "Invalid YouTube link"}), 400

    item = {
        "id": vid,
        "url": url,
        "by_ip": ip,
        "by_name": name,
        "title": None,
        "time": time.time(),
    }
    config["queue"].append(item)
    config["progress"][ip] = {"last_submit": time.time()}
    persist()
    return jsonify({"ok": True, "added": item})


@app.route("/api/next", methods=["POST"])
def api_next():
    if not config["queue"]:
        config["current"] = None
        return jsonify({"error": "Queue empty"}), 400
    if config["current"]:
        config["history"].insert(0, config["current"])
    config["current"] = config["queue"].pop(0)
    persist()
    return jsonify({"ok": True, "current": config["current"]})


@app.route("/api/prev", methods=["POST"])
def api_prev():
    if not config["history"]:
        return jsonify({"error": "No previous video"}), 400
    if config["current"]:
        config["queue"].insert(0, config["current"])
    config["current"] = config["history"].pop(0)
    persist()
    return jsonify({"ok": True, "current": config["current"]})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    config["queue"].clear()
    persist()
    return jsonify({"ok": True})


@app.route("/api/remove", methods=["POST"])
def api_remove():
    data = request.get_json(silent=True) or {}
    vid = data.get("id")
    config["queue"] = [v for v in config["queue"] if v.get("id") != vid]
    persist()
    return jsonify({"ok": True})


@app.route("/api/progress", methods=["POST"])
def api_progress():
    data = request.get_json(silent=True) or {}
    vid = data.get("videoId")
    pos = float(data.get("pos", 0))
    dur = float(data.get("dur", 0))
    ended = bool(data.get("ended", False))
    config["progress"]["pos"] = pos
    config["progress"]["dur"] = dur
    config["progress"]["ended"] = ended
    return jsonify({"ok": True})


@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)


# === Main ===
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
