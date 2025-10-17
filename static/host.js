// ==========================================================
// YouTube Queue Online — v01.6.1
// Ngày cập nhật: 17/10/2025
// Loại cập nhật: Hiển thị "by nickname (IP)" + chỉnh nickLimit
// ==========================================================

const qs = (s) => document.querySelector(s);
const queueEl = qs("#queue");
const historyEl = qs("#history");
const countdown = qs("#countdown");
let player = null;
let currentId = null;
let tickTimer = null;
let editingRate = false;

function headersAuth() {
  return HOST_KEY
    ? { "Content-Type": "application/json", "X-Host-Key": HOST_KEY }
    : { "Content-Type": "application/json" };
}

function who(it) {
  const n = it.by_name || "-";
  const ip = it.by_ip ? ` (${it.by_ip})` : "";
  return `by ${n}${ip}`;
}
function rQueue(it) {
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">${who(it)}</div>
    </div>
    <button class="neu-btn remove-btn" data-id="${it.id}">Remove</button>
  </div>`;
}
function rHistory(it) {
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="text-sm">${it.title||it.id}</div>
    <div class="small ml-auto">${who(it)}</div>
  </div>`;
}

window.onYouTubeIframeAPIReady = function () {
  player = new YT.Player("player", {
    videoId: "",
    playerVars: { autoplay: 1, controls: 1 },
    events: { onReady: onPlayerReady, onStateChange: onPlayerStateChange },
  });
};

function onPlayerReady() {
  refresh();
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(sendProgressTick, 1000);
}

function onPlayerStateChange(e) {
  if (e.data === YT.PlayerState.ENDED) {
    post("/api/progress", {
      ended: true,
      videoId: currentId,
      pos: player.getDuration(),
      dur: player.getDuration(),
    }).then(() => setTimeout(refresh, 800));
  }
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: headersAuth(), body: JSON.stringify(body || {}) });
  return r.json().catch(() => ({}));
}

async function refresh() {
  try {
    const s = await (await fetch("/api/state")).json();
    queueEl.innerHTML = (s.queue||[]).map(rQueue).join("") || '<div class="small">Queue empty</div>';
    historyEl.innerHTML = (s.history||[]).slice(0,15).map(rHistory).join("") || '<div class="small">No history</div>';

    if (!editingRate) {
    const rateBox = qs("#rate");
    if (rateBox && document.activeElement !== rateBox) {
    rateBox.value = (s.config && s.config.rate_limit_s) || 180;
    }

    const nickBox = qs("#nickLimit");
    if (nickBox && document.activeElement !== nickBox) {
    nickBox.value = (s.config && s.config.nickname_valid_minutes) || 60;
    }
  }


    const cid = s.current && s.current.id;
    if (cid && cid !== currentId && player) {
      currentId = cid;
      player.loadVideoById({ videoId: cid, startSeconds: 0, suggestedQuality: "large" });
    }

    // bind remove buttons
    queueEl.querySelectorAll("[data-id]").forEach(btn => {
      btn.onclick = async () => { await post("/api/remove", { id: btn.dataset.id }); await refresh(); };
    });
  } catch (e) { }
}

async function sendProgressTick() {
  if (!player || !HOST_KEY) return;
  try {
    const dur = Number(player.getDuration() || 0);
    const pos = Number(player.getCurrentTime() || 0);
    const vid = currentId;
    if (dur > 0) {
      const remain = Math.max(0, dur - pos);
      if (remain <= 3) { countdown.classList.remove("hidden"); countdown.textContent = Math.ceil(remain); }
      else { countdown.classList.add("hidden"); }
    }
    await post("/api/progress", { videoId: vid, pos, dur, ended: false });
  } catch (e) { }
}

qs("#btnPlay").onclick = async () => { await post("/api/play", {}); await refresh(); };
qs("#btnNext").onclick = async () => { await post("/api/next", {}); await refresh(); };
qs("#btnPrev").onclick = async () => { await post("/api/prev", {}); await refresh(); };
qs("#btnClear").onclick = async () => { await post("/api/clear", {}); await refresh(); };

const btnLogo = qs("#btnLogo");
if (btnLogo) {
  btnLogo.onclick = async () => {
    const f = qs("#logo").files[0];
    if (!f) { alert("Please choose a logo file first."); return; }
    const fd = new FormData(); fd.append("logo", f);
    const r = await fetch("/api/logo", { method: "POST", headers: HOST_KEY ? { "X-Host-Key": HOST_KEY } : {}, body: fd });
    const d = await r.json().catch(() => ({}));
    if (r.ok && d.ok) { alert("✅ Logo uploaded successfully!"); setTimeout(() => location.reload(), 600); }
    else { alert("❌ Upload failed: " + (d.error || "Unknown error")); }
  };
}

const saveBtn = qs("#btnSaveCfg");
if (saveBtn) {
  saveBtn.onclick = async () => {
    const rateInput = qs("#rate");
    const nickInput = qs("#nickLimit");
    const rateVal = parseInt(rateInput.value || "180", 10);
    const nickVal = parseInt(nickInput.value || "60", 10);

    // feedback trước
    saveBtn.textContent = "Saving...";
    saveBtn.disabled = true;

    try {
      const r = await fetch("/api/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Host-Key": HOST_KEY,
        },
        body: JSON.stringify({
          rate_limit_s: rateVal,
          nickname_valid_minutes: nickVal,
        }),
      });

      const d = await r.json().catch(() => ({}));
      if (r.ok && d.ok) {
        alert(`✅ Settings saved!\nSubmit limit: ${d.rate_limit_s}s\nNickname valid: ${d.nickname_valid_minutes} mins`);
      } else {
        alert(`❌ Failed: ${d.error || "Unknown error"}`);
      }
    } catch (err) {
      alert("⚠️ Network or server error while saving settings.");
    } finally {
      saveBtn.textContent = "Save settings";
      saveBtn.disabled = false;
      await refresh(); // cập nhật lại giao diện
    }
  };
}

refresh();
setInterval(refresh, 2000);
