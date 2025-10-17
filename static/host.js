// ==========================================================
// YouTube Queue Online — v01.6
// Ngày cập nhật: 17/10/2025
// Mô tả thay đổi:
// ✅ Loại bỏ localStorage key (dùng HOST_KEY truyền từ server Flask)
// ✅ Fix lỗi Upload & Save settings không gửi header xác thực
// ✅ Giữ auto refresh 2s, thêm bảo vệ khi đang chỉnh input
// ✅ Giữ layout mới: Prev – Start – Next – Clear
// ==========================================================

const qs = (s) => document.querySelector(s);
const queueEl = qs("#queue");
const historyEl = qs("#history");
const countdown = qs("#countdown");
let player = null;
let currentId = null;
let tickTimer = null;
let editingRate = false; // chống ghi đè khi đang gõ số

// ==========================================================
// 🧩 Header xác thực — dùng HOST_KEY được truyền từ host.html
// ==========================================================
function headersAuth() {
  return HOST_KEY
    ? { "Content-Type": "application/json", "X-Host-Key": HOST_KEY }
    : { "Content-Type": "application/json" };
}

// ==========================================================
// 🧩 Hàm render từng mục trong queue / history
// ==========================================================
function rQueue(it) {
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">${it.title || it.id}</div>
    <button class="btn" data-id="${it.id}">Remove</button>
  </div>`;
}

function rHistory(it) {
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="text-sm">${it.title || it.id}</div>
  </div>`;
}

// ==========================================================
// 🎥 YouTube IFrame Player API callbacks
// ==========================================================
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

// ==========================================================
// 🌐 POST tiện ích (tự động parse JSON)
// ==========================================================
async function post(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: headersAuth(),
    body: JSON.stringify(body || {}),
  });
  return r.json().catch(() => ({}));
}

// ==========================================================
// 🔁 Refresh trạng thái host (polling 2s/lần)
// ==========================================================
async function refresh() {
  try {
    const s = await (await fetch("/api/state")).json();
    queueEl.innerHTML =
      (s.queue || []).map(rQueue).join("") ||
      '<div class="small">Queue empty</div>';
    historyEl.innerHTML =
      (s.history || []).slice(0, 15).map(rHistory).join("") ||
      '<div class="small">No history</div>';

    // Chỉ update khi không đang nhập số
    if (!editingRate) {
      qs("#rate").value = (s.config && s.config.rate_limit_s) || 180;
    }

    const cid = s.current && s.current.id;
    if (cid && cid !== currentId && player) {
      currentId = cid;
      player.loadVideoById({
        videoId: cid,
        startSeconds: 0,
        suggestedQuality: "large",
      });
    }
  } catch (e) {
    // ignore network errors
  }
}

// ==========================================================
// ⏱️ Gửi tiến trình phát video về server
// ==========================================================
async function sendProgressTick() {
  if (!player || !HOST_KEY) return;
  try {
    const dur = Number(player.getDuration() || 0);
    const pos = Number(player.getCurrentTime() || 0);
    const vid = currentId;
    if (dur > 0) {
      const remain = Math.max(0, dur - pos);
      if (remain <= 3) {
        countdown.classList.remove("hidden");
        countdown.textContent = Math.ceil(remain);
      } else {
        countdown.classList.add("hidden");
      }
    }
    await post("/api/progress", { videoId: vid, pos, dur, ended: false });
  } catch (e) {}
}

// ==========================================================
// 🎛️ Các nút điều khiển host
// ==========================================================
qs("#btnPlay").onclick = async () => {
  await post("/api/play", {});
  await refresh();
};
qs("#btnNext").onclick = async () => {
  await post("/api/next", {});
  await refresh();
};
qs("#btnPrev").onclick = async () => {
  await post("/api/prev", {});
  await refresh();
};
qs("#btnClear").onclick = async () => {
  await post("/api/clear", {});
  await refresh();
};

// ==========================================================
// ⚙️ Upload logo + Lưu cấu hình submit limit
// ==========================================================
qs("#btnLogo").onclick = async () => {
  const f = qs("#logo").files[0];
  if (!f) {
    alert("Please choose a logo file first.");
    return;
  }
  const fd = new FormData();
  fd.append("logo", f);
  const r = await fetch("/api/logo", {
    method: "POST",
    headers: HOST_KEY ? { "X-Host-Key": HOST_KEY } : {},
    body: fd,
  });
  const d = await r.json().catch(() => ({}));
  if (r.ok && d.ok) {
    alert("✅ Logo uploaded successfully!");
    setTimeout(() => location.reload(), 800);
  } else {
    alert("❌ Upload failed: " + (d.error || "Unknown error"));
  }
};

qs("#btnSaveCfg").onclick = async () => {
  const v = parseInt(qs("#rate").value || "180", 10);
  const r = await fetch("/api/config", {
    method: "POST",
    headers: headersAuth(),
    body: JSON.stringify({ rate_limit_s: v }),
  });
  const d = await r.json().catch(() => ({}));
  if (r.ok && d.ok) {
    alert(`✅ Saved! New limit: ${v}s`);
    await refresh();
  } else {
    alert("❌ Save failed: " + (d.error || "Unknown error"));
  }
};

// ==========================================================
// 🧠 Các sự kiện input (chống bị auto refresh khi đang gõ)
// ==========================================================
const rateInput = qs("#rate");
if (rateInput) {
  rateInput.addEventListener("input", () => {
    editingRate = true;
  });
  rateInput.addEventListener("blur", () => {
    editingRate = false;
  });
}

// ==========================================================
// 🚀 Bootstrap
// ==========================================================
if (window.YT && window.YT.Player) {
  window.onYouTubeIframeAPIReady();
}
refresh();
setInterval(refresh, 2000);
