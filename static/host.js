// === v01.5.1: fix skip first video (double /next protection) ===
let settingsDirty = { submitLimit:false, nickChange:false };
function markDirty(key){ settingsDirty[key] = true; }
function clearDirty(){ settingsDirty = { submitLimit:false, nickChange:false }; }

document.addEventListener('DOMContentLoaded', () => {
  const submitEl = document.querySelector('#submitLimit');
  const nickEl = document.querySelector('#nicknameChange');
  if(submitEl){ ['input','change'].forEach(ev=> submitEl.addEventListener(ev, ()=>markDirty('submitLimit')) ); }
  if(nickEl){ ['input','change'].forEach(ev=> nickEl.addEventListener(ev, ()=>markDirty('nickChange')) ); }

  const loginModal = document.querySelector('#hostLoginModal');
  if(loginModal){
    loginModal.addEventListener('keydown', (e)=>{
      if(e.key === 'Enter'){
        const btn = loginModal.querySelector('button.login-btn');
        if(btn){ btn.click(); }
      }
    });
  }
});

let isLoggedIn = false;
const qs = (s)=>document.querySelector(s);
const queueEl = qs("#queue");
const historyEl = qs("#history");
const countdown = qs("#countdown");
let player = null;
let currentId = null;
let tickTimer = null;
let pauseRefresh = false;

// --- countdown + skip controls ---
let countdownTimer = null;
let countdownActive = false;
let skipNextEnded = false;
let hasPlayedOnce = false; 
let hasAutoNexted = false; // ✅ new flag: prevent double next

function whoHost(it){ return (it.by_name ? `${it.by_name} (${it.by_ip||''})` : (it.by_ip||'')); }
function rQueue(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div class="flex-1">
      <div>${it.title||it.id}</div>
      <div class="small">by ${whoHost(it)}</div>
    </div>
    <button class="btn" data-id="${it.id}">Remove</button>
  </div>`;
}
function rHistory(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div>
      <div class="text-sm">${it.title||it.id}</div>
      <div class="small">by ${whoHost(it)}</div>
    </div>
  </div>`;
}

async function loginRequired(){
  const r = await fetch('/api/state');
  if (!isLoggedIn){
    qs("#loginModal").classList.remove("hidden");
  }
}

qs("#btnLogin").onclick = async ()=>{
  const u = qs("#loginUser").value.trim() || "Admin";
  const p = qs("#loginPass").value.trim() || "0000";
  const msg = qs("#loginMsg");
  msg.textContent = "Signing in...";
  const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
  const d = await r.json();
  if (r.ok && d.ok){
    isLoggedIn = true;
    qs("#loginModal").classList.add("hidden");
    await refresh(true);
  } else {
    msg.textContent = d.error || "Login failed";
  }
};

// --- YouTube Player setup ---
window.onYouTubeIframeAPIReady = function(){
  player = new YT.Player('player', {
    videoId: '',
    playerVars: { 'autoplay': 1, 'controls': 1 },
    events: { 'onReady': onPlayerReady, 'onStateChange': onPlayerStateChange }
  });
}

function onPlayerReady(){
  try {
    const data = player.getVideoData();
    if (data && data.video_id) currentId = data.video_id;
  } catch(e){}
  refresh(true);
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(sendProgressTick, 1000);
}

function startCountdownAndNext(){
  if(countdownActive) return;
  countdownActive = true;
  let sec = 10;
  countdown.classList.remove('hidden');
  countdown.textContent = sec;
  countdownTimer = setInterval(()=>{
    sec--;
    if(sec<=0){
      clearInterval(countdownTimer);
      countdown.classList.add('hidden');
      countdownActive = false;
      const remain = Math.max(0, player.getDuration() - player.getCurrentTime());
      // ✅ Only next once and only if video really ended
      if (remain <= 1.5 && !hasAutoNexted){
        hasAutoNexted = true;
        skipNextEnded = true;
        nextVideoFromStart();
        setTimeout(()=> hasAutoNexted = false, 4000);
      }
    }else{
      countdown.textContent = sec;
    }
  },1000);
}

function onPlayerStateChange(e){
  if (e.data === YT.PlayerState.PLAYING){
    hasPlayedOnce = true;
  }
  if (e.data === YT.PlayerState.ENDED){
    if (!hasPlayedOnce){ hasPlayedOnce = true; return; }
    if (skipNextEnded){ skipNextEnded = false; return; }
    // ✅ prevent duplicate next
    if (!hasAutoNexted){
      hasAutoNexted = true;
      nextVideoFromStart();
      setTimeout(()=> hasAutoNexted = false, 4000);
    }
  }
}

// --- Helpers ---
async function post(path, body){
  const r = await fetch(path, {method:'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body||{})});
  return r.json().catch(()=>({}));
}

async function refresh(force=false){
  if (!isLoggedIn){ await loginRequired(); return; }
  const s = await (await fetch('/api/state')).json();
  queueEl.innerHTML = (s.queue||[]).map(rQueue).join("") || '<div class="small">Queue empty</div>';
  historyEl.innerHTML = (s.history||[]).slice(0,15).map(rHistory).join("") || '<div class="small">No history</div>';
  if (!pauseRefresh || force){
    qs("#rate").value = (s.config && s.config.rate_limit_s) || 180;
    qs("#nickHours").value = (s.config && s.config.nick_change_hours) || 24;
  }
  const cid = s.current && s.current.id;
  const prog = s.progress || {};
  if (!currentId && cid) currentId = cid;
  if (cid && player){
    const nowId = player.getVideoData().video_id;
    if ((cid !== currentId) || (force && nowId !== cid)){
      currentId = cid;
      const seek = Math.max(0, Math.floor((prog.pos||0)));
      player.loadVideoById({videoId: cid, startSeconds: seek, suggestedQuality: 'large'});
    }
  }
}

// --- send progress and manage countdown ---
async function sendProgressTick(){
  if (!player || !isLoggedIn) return;
  try{
    const dur = Number(player.getDuration() || 0);
    const pos = Number(player.getCurrentTime() || 0);
    const vid = currentId;
    if (dur>0){
      const remain = Math.max(0, dur - pos);
      if (remain <= 10 && !countdownActive && player.getPlayerState() === YT.PlayerState.PLAYING){
        startCountdownAndNext();
      }
      if (remain > 10){
        countdown.classList.add('hidden');
      }
    }
    await post('/api/progress', {videoId: vid, pos, dur, ended: false});
  }catch(e){}
}

// --- Playback controls ---
async function playCurrentFromStart(){
  const s = await (await fetch('/api/state')).json();
  const cid = s.current && s.current.id;
  if (cid){
    currentId = cid;
    player.loadVideoById({videoId: cid, startSeconds: 0, suggestedQuality: 'large'});
    await post('/api/play', {videoId: cid, pos: 0});
  } else {
    await post('/api/play', {});
  }
  await refresh(true);
}

async function nextVideoFromStart(){
  await post('/api/next', {});
  await refresh(true);
  if (currentId){
    player.loadVideoById({videoId: currentId, startSeconds: 0, suggestedQuality: 'large'});
  }
}

async function prevVideoFromStart(){
  await post('/api/prev', {});
  await refresh(true);
  if (currentId){
    player.loadVideoById({videoId: currentId, startSeconds: 0, suggestedQuality: 'large'});
  }
}

// --- Button bindings ---
qs("#btnPlay").onclick = playCurrentFromStart;
qs("#btnNext").onclick = nextVideoFromStart;
qs("#btnPrev").onclick = prevVideoFromStart;
qs("#btnClear").onclick = async()=>{ await post('/api/clear', {}); await refresh(true); };

["#rate","#nickHours"].forEach(sel=>{
  const el = qs(sel);
  el.addEventListener('focus', ()=> pauseRefresh = true);
  el.addEventListener('blur', ()=> { pauseRefresh = false; });
});

qs("#btnSaveCfg").onclick = async()=>{
  const v  = parseInt(qs("#rate").value||"180", 10);
  const nh = parseInt(qs("#nickHours").value||"24", 10);
  const r = await fetch('/api/config', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({rate_limit_s: v, nick_change_hours: nh})});
  if (!r.ok){ alert("Not authorized or error"); return; }
  await refresh(true);
};

qs("#btnLogo").onclick = async()=>{
  const f = qs("#logo").files[0];
  if(!f){ alert("Choose file"); return; }
  const fd = new FormData(); fd.append("logo", f);
  const r = await fetch('/api/logo', {method:'POST', body: fd});
  if (!r.ok){ alert("Not authorized or error"); return; }
  alert("Logo uploaded"); setTimeout(()=>location.reload(), 400);
};

qs("#btnSaveAuth").onclick = async()=>{
  const u = qs("#hostUser").value.trim();
  const p = qs("#hostPass").value.trim();
  const k = qs("#hostKey").value.trim();
  if (!k){ alert("Enter HOST_API_KEY to confirm."); return; }
  const r = await fetch('/api/admin/update_auth', {method:'POST', headers:{'Content-Type':'application/json','X-Host-Key':k}, body: JSON.stringify({username:u, password:p})});
  const d = await r.json().catch(()=>({}));
  if (!r.ok){ alert(d.error||"Unauthorized"); return; }
  alert("Saved. You can now login with new credentials.");
};

// --- Remove item (smooth, no player reload) ---
queueEl.addEventListener('click', async (e)=>{
  if (e.target.tagName === "BUTTON" && e.target.dataset.id){
    await fetch('/api/remove', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({id:e.target.dataset.id})
    });
    e.target.closest(".item").remove();
    if (!queueEl.querySelector(".item")) {
      queueEl.innerHTML = '<div class="small">Queue empty</div>';
    }
  }
});

if (window.YT && window.YT.Player){ window.onYouTubeIframeAPIReady(); }
refresh(true);
setInterval(()=>{ if(!pauseRefresh) refresh(false); }, 2000);

function __clearDirtyFlagsAfterSave(){ clearDirty(); }
