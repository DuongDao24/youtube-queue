import os, json, time, re
from collections import deque
from urllib.parse import urlparse, parse_qs
from flask import Flask, render_template_string, request, jsonify
from werkzeug.utils import secure_filename
import requests

APP_TITLE     = os.environ.get("APP_TITLE", "YouTube Queue Online")
SECRET_KEY    = os.environ.get("SECRET_KEY", "change-this-secret")
HOST_API_KEY  = os.environ.get("HOST_API_KEY", "ytq-premium-2025-dxd")
ENV_RATE_LIMIT  = int(os.environ.get("RATE_LIMIT_S", "180"))
PERSIST_PATH  = os.environ.get("PERSIST_PATH", "queue_data.json")
CONFIG_PATH   = os.environ.get("CONFIG_PATH", "config.json")
STATIC_DIR    = os.path.join(os.path.dirname(__file__), "static")

ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".gif"}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SECRET_KEY"] = SECRET_KEY

# State
queue = deque()
last_submit_ts = {}
current = None
history = deque(maxlen=200)
last_progress = {"videoId": None, "pos": 0, "dur": 0, "ts": 0, "ended": False}

config = {"rate_limit_s": ENV_RATE_LIMIT, "logo_path": None}

def load_config():
    global config
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config["rate_limit_s"] = int(data.get("rate_limit_s", ENV_RATE_LIMIT))
                config["logo_path"] = data.get("logo_path")
        except Exception as e:
            print("load_config:", e)

def save_config():
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_config:", e)

def get_rate_limit_s():
    return int(config.get("rate_limit_s") or ENV_RATE_LIMIT)

def get_logo_url():
    if config.get("logo_path"):
        return f"/{config['logo_path']}?t={int(time.time())}"
    return None

YOUTUBE_ID_REGEX = re.compile(r"(?:v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})")

def extract_youtube_id(s: str):
    x = (s or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", x): return x
    m = YOUTUBE_ID_REGEX.search(x)
    if m: return m.group(1)
    try:
        q = parse_qs(urlparse(x).query)
        if "v" in q:
            vid = q["v"][0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid): return vid
    except Exception:
        pass
    return None

def fetch_title(video_id: str):
    try:
        r = requests.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json", timeout=6)
        if r.ok: return r.json().get("title","")
    except Exception:
        pass
    return f"Video {video_id}"

def save_state():
    try:
        with open(PERSIST_PATH, "w", encoding="utf-8") as f:
            json.dump({"queue": list(queue), "current": current, "history": list(history)}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("save_state:", e)

def load_state():
    global queue, current, history
    if not os.path.exists(PERSIST_PATH): return
    try:
        with open(PERSIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        queue   = deque(data.get("queue", []))
        current = data.get("current")
        history = deque(data.get("history", []), maxlen=200)
    except Exception as e:
        print("load_state:", e)

def set_next_current():
    global current, queue, last_progress
    current = queue.popleft() if queue else None
    last_progress = {"videoId": current["id"] if current else None, "pos": 0, "dur": 0, "ts": time.time(), "ended": False}
    return current

# ---------- HTML (Tailwind via CDN) ----------
INDEX_HTML = """
<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ app_title }}</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 text-gray-900">
<div class="max-w-5xl mx-auto p-6 space-y-6">
  <div class="flex items-center gap-4">
    {% if logo_url %}<img src="{{ logo_url }}" class="h-10 w-auto rounded-md shadow-sm" alt="logo">{% else %}<div class="text-xl">Logo</div>{% endif %}
    <h1 class="text-3xl font-bold">{{ app_title }}</h1>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-2xl shadow p-5">
      <h2 class="font-semibold mb-2">Add YouTube video</h2>
      <p class="text-sm text-gray-600 mb-4">Paste a YouTube video (not playlist). Limit: <b>{{ rate_limit_s }}</b>s per IP.</p>
      <form id="addForm" class="space-y-3">
        <input id="url" type="text" placeholder="https://www.youtube.com/watch?v=..." class="w-full border rounded-xl px-3 py-2" required>
        <button class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl">Add to queue</button>
        <div id="msg" class="text-sm text-gray-600"></div>
      </form>
    </div>

    <div class="bg-white rounded-2xl shadow p-5">
      <h2 class="font-semibold mb-3">Now playing</h2>
      <div id="playing" class="flex items-center gap-4"></div>
      <div class="h-2 bg-gray-200 rounded-full overflow-hidden mt-3"><div id="pbar" class="h-full bg-blue-600" style="width:0%"></div></div>
    </div>
  </div>

  <div class="bg-white rounded-2xl shadow p-5">
    <h2 class="font-semibold mb-3">Queue</h2><div id="queue" class="space-y-3"></div>
  </div>

  <div class="bg-white rounded-2xl shadow p-5">
    <h2 class="font-semibold mb-3">History</h2><div id="history" class="space-y-3"></div>
  </div>
</div>
<script>
const qEl=document.getElementById('queue'), msgEl=document.getElementById('msg');
const pbar=document.getElementById('pbar'), playing=document.getElementById('playing');
const hEl=document.getElementById('history');

function renderQueue(items){
  qEl.innerHTML=''; if(!items||!items.length){ qEl.innerHTML='<div class="text-gray-500 text-sm">Empty.</div>'; return; }
  items.forEach((it,idx)=>{ const row=document.createElement('div'); row.className='flex items-center gap-4';
    row.innerHTML=`<img src="https://i.ytimg.com/vi/${it.id}/default.jpg" class="w-24 h-16 rounded-lg object-cover">
      <div class="flex-1"><div class="font-medium">${it.title||it.id}</div><div class="text-xs text-gray-500">#${idx+1} • by ${it.by}</div></div>`;
    qEl.appendChild(row);});
}
function renderHistory(items){
  hEl.innerHTML=''; if(!items||!items.length){ hEl.innerHTML='<div class="text-gray-500 text-sm">No history.</div>'; return; }
  items.slice(0,15).forEach((it)=>{ const row=document.createElement('div'); row.className='flex items-center gap-4';
    row.innerHTML=`<img src="https://i.ytimg.com/vi/${it.id}/default.jpg" class="w-20 h-14 rounded-lg object-cover">
      <div class="flex-1"><div class="text-sm">${it.title||it.id}</div><div class="text-xs text-gray-500">by ${it.by||'-'}</div></div>`;
    hEl.appendChild(row);});
}
function renderPlaying(item){
  playing.innerHTML=''; if(!item){ playing.innerHTML='<div class="text-gray-500 text-sm">No current.</div>'; return; }
  playing.innerHTML=`<img src="https://i.ytimg.com/vi/${item.id}/hqdefault.jpg" class="w-28 h-20 rounded-lg object-cover">
    <div><div class="font-semibold">${item.title||item.id}</div>
    <a target="_blank" href="https://www.youtube.com/watch?v=${item.id}" class="text-blue-600 text-sm">Open on YouTube</a></div>`;
}
async function load(){
  const s = await (await fetch('/api/state')).json();
  renderQueue(s.queue); renderPlaying(s.current); renderHistory(s.history||[]);
  const p=s.progress||{}; const pos=p.pos||0, dur=p.dur||0;
  pbar.style.width = dur>0? Math.min(100, Math.round(pos*100/dur))+'%' : '0%';
}
document.getElementById('addForm').addEventListener('submit', async e=>{
  e.preventDefault(); const url=document.getElementById('url').value.trim(); msgEl.textContent='Submitting...';
  try{ const r=await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
    const d=await r.json(); if(!r.ok) throw new Error(d.error||'Error'); msgEl.textContent='Added: '+(d.item.title||d.item.id);
    document.getElementById('url').value=''; load();
  }catch(err){ msgEl.textContent='Error: '+err.message; }
});
setInterval(load, 2000); load();
</script></body></html>
"""

HOST_HTML = """
<!doctype html><html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ app_title }} - Host</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-gray-50 text-gray-900">
<div class="max-w-6xl mx-auto p-6 space-y-6">
  <div class="flex items-center gap-4">
    {% if logo_url %}<img src="{{ logo_url }}" class="h-10 w-auto rounded-md shadow-sm" alt="logo">{% else %}<div class="text-xl">Logo</div>{% endif %}
    <h1 class="text-3xl font-bold">{{ app_title }} - Host</h1>
  </div>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <div class="bg-white rounded-2xl shadow p-5">
      <h2 class="font-semibold mb-3">Controls</h2>
      <div class="flex gap-2 mb-3">
        <input id="key" type="password" class="border rounded-xl px-3 py-2 w-64" placeholder="HOST_API_KEY">
        <button id="saveKey" class="bg-gray-800 text-white px-4 py-2 rounded-xl">Save key</button>
        <button id="btnNext" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl">Next</button>
        <button id="btnClear" class="bg-gray-200 px-4 py-2 rounded-xl">Clear</button>
      </div>
      <div id="current" class="mb-3"></div>
      <div id="queue" class="space-y-2"></div>
    </div>

    <div class="bg-white rounded-2xl shadow p-5">
      <h2 class="font-semibold mb-3">Settings</h2>
      <div class="space-y-4">
        <div><label class="text-sm text-gray-600">Submit limit (seconds)</label>
             <input id="rate" type="number" min="10" step="10" class="border rounded-xl px-3 py-2 w-48"></div>
        <div><label class="text-sm text-gray-600">Logo (png/jpg/gif)</label>
             <input id="logo" type="file" accept=".png,.jpg,.jpeg,.gif" class="block">
             <button id="btnLogo" class="mt-2 bg-gray-800 text-white px-4 py-2 rounded-xl">Upload logo</button></div>
      </div>
    </div>
  </div>

  <div class="bg-white rounded-2xl shadow p-5">
    <h2 class="font-semibold mb-3">Recent history</h2>
    <div id="history" class="space-y-2"></div>
  </div>
</div>
<script>
const qs=(s)=>document.querySelector(s);
let HOST_KEY = localStorage.getItem("HOST_KEY") || "";
function headersAuth(){ return HOST_KEY? {"Content-Type":"application/json","X-Host-Key":HOST_KEY} : {"Content-Type":"application/json"}; }

function renderState(s){
  const cur = s.current;
  qs("#current").innerHTML = cur ? `
    <div class="flex items-center gap-3">
      <img src="https://i.ytimg.com/vi/${cur.id}/hqdefault.jpg" class="w-28 h-20 rounded-lg object-cover">
      <div><div class="font-semibold">${cur.title||cur.id}</div>
      <a class="text-blue-600 text-sm" target="_blank" href="https://www.youtube.com/watch?v=${cur.id}">Open</a></div></div>` : '<div class="text-gray-500 text-sm">No current.</div>';

  const q = s.queue || []; const qEl = qs("#queue"); qEl.innerHTML="";
  if(!q.length){ qEl.innerHTML = '<div class="text-gray-500 text-sm">Queue empty.</div>'; }
  q.forEach(it=>{ const row=document.createElement("div"); row.className="flex items-center gap-3";
    row.innerHTML=`<img src="https://i.ytimg.com/vi/${it.id}/default.jpg" class="w-20 h-14 rounded-lg object-cover">
      <div class="flex-1">${it.title||it.id}</div><button data-id="${it.id}" class="bg-gray-200 px-3 py-1 rounded">Remove</button>`;
    qEl.appendChild(row); });
  qEl.onclick = async (e)=>{ if(e.target.tagName==="BUTTON"){ const vid=e.target.getAttribute("data-id");
      await fetch('/api/remove',{method:'POST',headers:headersAuth(),body:JSON.stringify({id:vid})}); await refresh(); } };

  const hEl = qs("#history"); hEl.innerHTML="";
  (s.history||[]).slice(0,15).forEach(it=>{ const row=document.createElement("div"); row.className="flex items-center gap-3";
    row.innerHTML=`<img src="https://i.ytimg.com/vi/${it.id}/default.jpg" class="w-20 h-14 rounded-lg object-cover">
      <div class="text-sm text-gray-700">${it.title||it.id}</div>`; hEl.appendChild(row); });
}

async function refresh(){
  const s = await (await fetch('/api/state')).json(); renderState(s);
  const cfg = await (await fetch('/api/config')).json(); qs("#rate").value = cfg.rate_limit_s || 180;
}
qs("#saveKey").onclick = ()=>{ const v=qs("#key").value.trim(); if(!v){alert("Enter HOST_API_KEY");return;}
  HOST_KEY=v; localStorage.setItem("HOST_KEY", HOST_KEY); alert("Saved."); };
qs("#btnNext").onclick = async()=>{ const r=await fetch('/api/next',{method:'POST',headers:headersAuth()});
  if(r.status===401){ alert("Wrong HOST_API_KEY"); return; } await refresh(); };
qs("#btnClear").onclick = async()=>{ const r=await fetch('/api/clear',{method:'POST',headers:headersAuth()});
  if(r.status===401){ alert("Wrong HOST_API_KEY"); return; } await refresh(); };
qs("#btnLogo").onclick = async()=>{ const file=qs("#logo").files[0]; if(!file){alert("No file selected.");return;}
  const fd=new FormData(); fd.append("logo", file);
  const r=await fetch('/api/logo',{method:'POST',headers:HOST_KEY?{"X-Host-Key":HOST_KEY}:{},body:fd});
  if(r.status===401){ alert("Wrong HOST_API_KEY"); return; }
  if(!r.ok){ alert("Upload failed"); return; }
  alert("Logo uploaded. Reloading..."); setTimeout(()=>location.reload(),500); };
setInterval(refresh, 2000); refresh();
</script></body></html>
"""

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template_string(INDEX_HTML, app_title=APP_TITLE, rate_limit_s=get_rate_limit_s(), logo_url=get_logo_url())

@app.route("/host")
def host():
    return render_template_string(HOST_HTML, app_title=APP_TITLE, logo_url=get_logo_url())

@app.route("/api/state")
def api_state():
    # auto-next nếu /api/progress đã đánh dấu ended
    global last_progress, history
    if last_progress.get("ended") and queue:
        if current: history.appendleft(current)
        set_next_current()
        save_state()
        last_progress["ended"] = False
    return jsonify({"current": current, "queue": list(queue), "history": list(history), "progress": last_progress})

@app.route("/api/add", methods=["POST"])
def api_add():
    global current
    data = request.get_json(force=True, silent=True) or {}
    url  = (data.get("url") or "").strip()
    user = request.remote_addr or "unknown"

    now = time.time()
    RATE_LIMIT_S = get_rate_limit_s()
    last = last_submit_ts.get(user, 0)
    remaining = RATE_LIMIT_S - int(now - last)
    if remaining > 0:
        return jsonify({"ok": False, "error": f"Please wait {remaining}s."}), 429

    vid = extract_youtube_id(url)
    if not vid: return jsonify({"ok": False, "error": "Paste a YouTube video link (not playlist)."}), 400

    item = {"id": vid, "title": fetch_title(vid), "by": user, "ts": int(now)}
    queue.append(item); last_submit_ts[user] = now

    if current is None:
        set_next_current()

    save_state()
    return jsonify({"ok": True, "item": item})

def _require_host_key():
    if request.headers.get("X-Host-Key") != HOST_API_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    return None

@app.route("/api/next", methods=["POST"])
def api_next():
    unauth = _require_host_key()
    if unauth: return unauth
    global history
    if current: history.appendleft(current)
    set_next_current()
    save_state()
    return jsonify({"ok": True, "current": current})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    unauth = _require_host_key()
    if unauth: return unauth
    queue.clear()
    save_state()
    return jsonify({"ok": True})

@app.route("/api/remove", methods=["POST"])
def api_remove():
    unauth = _require_host_key()
    if unauth: return unauth
    global queue
    data = request.get_json(force=True, silent=True) or {}
    vid = data.get("id")
    if not vid: return jsonify({"ok": False}), 400

    from collections import deque as dq
    newq, removed = dq(), False
    for it in list(queue):
        if not removed and it["id"] == vid:
            removed = True
            continue
        newq.append(it)

    queue = newq
    save_state()
    return jsonify({"ok": True, "removed": removed})

@app.route("/api/progress", methods=["POST"])
def api_progress():
    unauth = _require_host_key()
    if unauth: return unauth
    data = request.get_json(force=True, silent=True) or {}
    videoId  = data.get("videoId")
    pos      = float(data.get("pos", 0))
    dur      = float(data.get("dur", 0))
    ended    = bool(data.get("ended", False))
    ts       = time.time()

    global last_progress, history
    last_progress = {"videoId": videoId, "pos": pos, "dur": dur, "ts": ts, "ended": ended}
    if ended and queue:
        if current: history.appendleft(current)
        set_next_current()
        save_state()
        last_progress["ended"] = False
    return jsonify({"ok": True})

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({"rate_limit_s": get_rate_limit_s(), "logo_url": get_logo_url()})
    unauth = _require_host_key()
    if unauth: return unauth
    data = request.get_json(force=True, silent=True) or {}
    if "rate_limit_s" in data:
        try:
            val = int(data.get("rate_limit_s"))
            if val < 10: val = 10
            config["rate_limit_s"] = val
            save_config()
        except Exception:
            pass
    return jsonify({"ok": True, "rate_limit_s": get_rate_limit_s()})

@app.route("/api/logo", methods=["POST"])
def api_logo():
    unauth = _require_host_key()
    if unauth: return unauth
    if "logo" not in request.files:
        return jsonify({"ok": False, "error": "No file"}), 400
    f = request.files["logo"]
    if not f.filename:
        return jsonify({"ok": False, "error": "Empty filename"}), 400
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".png",".jpg",".jpeg",".gif"}:
        return jsonify({"ok": False, "error": "Invalid file type"}), 400
    # remove old logo files
    for old in os.listdir("static"):
        if old.startswith("logo"):
            try: os.remove(os.path.join("static", old))
            except Exception: pass
    save_name = f"logo{ext}"
    full_path = os.path.join("static", save_name)
    f.save(full_path)
    rel_path = f"static/{save_name}"
    config["logo_path"] = rel_path
    save_config()
    return jsonify({"ok": True, "logo_url": f"/{rel_path}" })

@app.route("/healthz")
def healthz(): return "ok"

def create_app():
    load_state(); load_config(); return app

if __name__ == "__main__":
    load_state(); load_config()
    port = int(os.environ.get("PORT","5000"))
    app.run(host="0.0.0.0", port=port)
