// YouTube Queue Online — v01.6 (user)
const qEl = document.getElementById('queue');
const hEl = document.getElementById('history');
const playing = document.getElementById('playing');
const pbar = document.getElementById('pbar');
const msgEl = document.getElementById('msg');
const btnAdd = document.getElementById('btnAdd');

function rowQueue(it, idx){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">#${idx+1} • by ${it.by}</div>
    </div>
  </div>`;
}
function rowHistory(it){
  return `<div class="item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="text-sm">${it.title||it.id}</div>
      <div class="small">by ${it.by||"-"}</div>
    </div>
  </div>`;
}
function renderState(s){
  document.getElementById('limit').textContent = (s.config&&s.config.rate_limit_s)||180;
  playing.innerHTML = s.current ? `<img class="thumb" src="https://i.ytimg.com/vi/${s.current.id}/hqdefault.jpg" alt="thumb">
      <div><div class="font-semibold">${s.current.title||s.current.id}</div>
      <a class="text-blue-600 text-sm" target="_blank" href="https://www.youtube.com/watch?v=${s.current.id}">Open on YouTube</a></div>`
    : '<div class="small">No current.</div>';
  const p = s.progress || {}; const pos = p.pos||0, dur = p.dur||0;
  pbar.style.width = dur>0 ? Math.min(100, Math.round(pos*100/dur))+'%' : '0%';
  qEl.innerHTML = (s.queue||[]).map((it,i)=>rowQueue(it,i)).join("") || '<div class="small">Empty</div>';
  hEl.innerHTML = (s.history||[]).slice(0,15).map(rowHistory).join("") || '<div class="small">No history</div>';
}
async function load(){
  try{
    const res = await fetch('/api/state');
    const s = await res.json();
    renderState(s);
  }catch(e){ /* ignore network errors for polling */ }
}
document.getElementById('addForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const url = document.getElementById('url').value.trim();
  if(!url){ return; }
  msgEl.textContent = 'Submitting...';
  btnAdd.disabled = true;
  try{
    const r = await fetch('/api/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
    const d = await r.json().catch(()=>({}));
    if(!r.ok){
      msgEl.textContent = d.error || 'Error adding video.';
    }else{
      msgEl.textContent = 'Added: ' + (d.item?.title||d.item?.id||'');
      document.getElementById('url').value='';
      load();
    }
  }catch(err){ msgEl.textContent = 'Network error. Please try again.'; }
  finally{ btnAdd.disabled = false; }
});
setInterval(load, 2000);
load();
