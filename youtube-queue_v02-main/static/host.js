
let HOST_KEY = localStorage.getItem("HOST_KEY") || "";
const qs = (s)=>document.querySelector(s);
const queueEl = qs("#queue");
const historyEl = qs("#history");
const countdown = qs("#countdown");
let player = null;
let currentId = null;
let tickTimer = null;

function headersAuth(){
  return HOST_KEY ? {"Content-Type":"application/json","X-Host-Key":HOST_KEY} : {"Content-Type":"application/json"};
}

function rQueue(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div class="flex-1">${it.title||it.id}</div>
    <button class="btn" data-id="${it.id}">Remove</button>
  </div>`;
}
function rHistory(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg">
    <div class="text-sm">${it.title||it.id}</div>
  </div>`;
}

window.onYouTubeIframeAPIReady = function(){
  player = new YT.Player('player', {
    videoId: '',
    playerVars: { 'autoplay': 1, 'controls': 1 },
    events: { 'onReady': onPlayerReady, 'onStateChange': onPlayerStateChange }
  });
}

function onPlayerReady(){
  refresh();
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(sendProgressTick, 1000);
}

function onPlayerStateChange(e){
  if (e.data === YT.PlayerState.ENDED){
    post('/api/progress', {ended:true, videoId: currentId, pos: player.getDuration(), dur: player.getDuration()})
      .then(()=> setTimeout(refresh, 800));
  }
}

async function post(path, body){
  const r = await fetch(path, {method:'POST', headers: headersAuth(), body: JSON.stringify(body||{})});
  return r.json().catch(()=>({}));
}

async function refresh(){
  const s = await (await fetch('/api/state')).json();
  queueEl.innerHTML = (s.queue||[]).map(rQueue).join("") || '<div class="small">Queue empty</div>';
  historyEl.innerHTML = (s.history||[]).slice(0,15).map(rHistory).join("") || '<div class="small">No history</div>';
  qs("#rate").value = (s.config && s.config.rate_limit_s) || 180;

  const cid = s.current && s.current.id;
  if (cid && cid !== currentId && player){
    currentId = cid;
    player.loadVideoById({videoId: cid, startSeconds: 0, suggestedQuality: 'large'});
  }
}

async function sendProgressTick(){
  if (!player || !HOST_KEY) return;
  try{
    const dur = Number(player.getDuration() || 0);
    const pos = Number(player.getCurrentTime() || 0);
    const vid = currentId;
    if (dur>0){
      const remain = Math.max(0, dur - pos);
      if (remain <= 3){
        countdown.classList.remove('hidden');
        countdown.textContent = Math.ceil(remain);
      } else {
        countdown.classList.add('hidden');
      }
    }
    await post('/api/progress', {videoId: vid, pos, dur, ended: false});
  }catch(e){}
}

// Controls
qs("#saveKey").onclick = ()=>{
  const v = qs("#key").value.trim();
  if(!v){ alert("Enter HOST_API_KEY"); return; }
  HOST_KEY = v; localStorage.setItem("HOST_KEY", HOST_KEY);
  alert("Saved.");
};
qs("#btnPlay").onclick = async()=>{ await post('/api/play', {}); await refresh(); };
qs("#btnNext").onclick = async()=>{ await post('/api/next', {}); await refresh(); };
qs("#btnPrev").onclick = async()=>{ await post('/api/prev', {}); await refresh(); };
qs("#btnClear").onclick = async()=>{ await post('/api/clear', {}); await refresh(); };
qs("#btnLogo").onclick = async()=>{
  const f = qs("#logo").files[0];
  if(!f){ alert("Choose file"); return; }
  const fd = new FormData(); fd.append("logo", f);
  const r = await fetch('/api/logo', {method:'POST', headers: HOST_KEY? {"X-Host-Key": HOST_KEY} : {}, body: fd});
  if (r.status===401){ alert("Wrong HOST_API_KEY"); return; }
  alert("Logo uploaded"); setTimeout(()=>location.reload(), 500);
};
qs("#btnSaveCfg").onclick = async()=>{
  const v = parseInt(qs("#rate").value||"180", 10);
  const r = await fetch('/api/config', {method:'POST', headers: headersAuth(), body: JSON.stringify({rate_limit_s: v})});
  if (r.status===401){ alert("Wrong HOST_API_KEY"); return; }
  alert("Saved."); refresh();
};
queueEl.addEventListener('click', async (e)=>{
  if (e.target.tagName === "BUTTON" && e.target.dataset.id){
    await post('/api/remove', {id: e.target.dataset.id}); refresh();
  }
});

// bootstrap: if API is already loaded
if (window.YT && window.YT.Player){ window.onYouTubeIframeAPIReady(); }

// Auto refresh queue/now-playing every 2s so host sees new user submissions
refresh();                    // load ngay khi mở trang
setInterval(refresh, 2000);   // poll mỗi 2 giây

qs("#btnReload").onclick = refresh;

