// ==========================================================
// YouTube Queue Online — v01.6.1
// Ngày cập nhật: 17/10/2025
// Loại cập nhật: Nickname bắt buộc trước khi submit
// - UI nickname (get/set) với hiệu lực theo phút từ host
// - Queue/History hiển thị "by nickname" (không lộ IP)
// =========================================================

const qEl = document.getElementById('queue');
const hEl = document.getElementById('history');
const playing = document.getElementById('playing');
const pbar = document.getElementById('pbar');
const msgEl = document.getElementById('msg');
const btnAdd = document.getElementById('btnAdd');

const nickForm = document.getElementById('nickForm');
const nickInput = document.getElementById('nickInput');
const nickMsg = document.getElementById('nickMsg');
const nickInfo = document.getElementById('nickInfo');

let nicknameOK = false;

function rowQueue(it, idx){
  const name = it.by_name ? it.by_name : "-";
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="font-medium">${it.title||it.id}</div>
      <div class="small">#${idx+1} • by ${name}</div>
    </div>
  </div>`;
}
function rowHistory(it){
  const name = it.by_name ? it.by_name : "-";
  return `<div class="item neu-item">
    <img class="thumb" src="https://i.ytimg.com/vi/${it.id}/default.jpg" alt="thumb">
    <div class="flex-1">
      <div class="text-sm">${it.title||it.id}</div>
      <div class="small">by ${name}</div>
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

async function loadState(){
  try{
    const s = await (await fetch('/api/state')).json();
    renderState(s);
  }catch(e){}
}

// ---- Nickname flow ----
async function checkNickname() {
  try {
    const r = await fetch('/api/nickname');
    const d = await r.json();
    if (d.ok) {
      nicknameOK = !!d.valid;
      if (d.valid) {
        nickInfo.textContent = `Welcome, ${d.name}! (expires in ${d.remain_mins} mins)`;
        if (nickForm) nickForm.style.display = "none";
      } else {
        nickInfo.textContent = `Please set your nickname (valid for ${d.limit_mins} mins).`;
        if (nickForm) nickForm.style.display = "flex";
      }
    }
  } catch (e) {}
}

if (nickForm) {
  nickForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const name = (nickInput.value || '').trim();
    if (!name) return;
    nickMsg.textContent = 'Saving...';
    try{
      const r = await fetch('/api/nickname', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name })});
      const d = await r.json().catch(()=>({}));
      if (!r.ok || !d.ok) {
        nickMsg.textContent = d.error || 'Cannot save nickname.';
      } else {
        nickMsg.textContent = 'Saved!';
        await checkNickname();
      }
    }catch(err){
      nickMsg.textContent = 'Network error.';
    }
  });
}

// ---- Add video ----
document.getElementById('addForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const url = document.getElementById('url').value.trim();
  if(!url){ return; }
  if (!nicknameOK) {
    msgEl.textContent = 'Please set your nickname first.';
    return;
  }
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
      await loadState();
    }
  }catch(err){ msgEl.textContent = 'Network error. Please try again.'; }
  finally{ btnAdd.disabled = false; }
});

setInterval(loadState, 2000);
(async ()=>{ await checkNickname(); await loadState(); })();
