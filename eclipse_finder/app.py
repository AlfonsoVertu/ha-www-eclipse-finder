import os, json, uuid, urllib.request
import datetime as dt
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import uvicorn
import astronomy

DATA = "/data"; PHOTOS = os.path.join(DATA, "photos"); PLAN_FILE = os.path.join(DATA, "plan.json")
os.makedirs(PHOTOS, exist_ok=True)
app = FastAPI()

def ha_config():
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    try:
        req = urllib.request.Request("http://supervisor/core/api/config", headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception:
        return {}

def get_location():
    c = ha_config()
    return {"latitude": c.get("latitude"), "longitude": c.get("longitude"),
            "elevation": c.get("elevation") or 0, "time_zone": c.get("time_zone") or "UTC",
            "location_name": c.get("location_name") or "Casa"}

def horiz(body, t, obs):
    eq = astronomy.Equator(body, t, obs, True, True)
    h = astronomy.Horizon(t, obs, eq.ra, eq.dec, astronomy.Refraction.Normal)
    return h.azimuth, h.altitude

def kname(k): return str(k).split(".")[-1]
def compass16(az):
    d = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"]
    return d[int((az % 360)/22.5 + 0.5) % 16]

def next_solar(obs):
    e = astronomy.SearchLocalSolarEclipse(astronomy.Time.Now(), obs)
    az, _ = horiz(astronomy.Body.Sun, e.peak.time, obs)
    return {"type":"Eclissi Solare","body":"sun","kind":kname(e.kind),
            "obscuration":round((e.obscuration or 0)*100,1),
            "peak_utc":e.peak.time.Utc().replace(tzinfo=dt.timezone.utc).isoformat(),
            "azimuth":round(az,1),"compass":compass16(az),"altitude":round(e.peak.altitude,1),
            "visible":e.peak.altitude>0}

def next_lunar(obs):
    e = astronomy.SearchLunarEclipse(astronomy.Time.Now())
    az, alt = horiz(astronomy.Body.Moon, e.peak, obs)
    return {"type":"Eclissi Lunare","body":"moon","kind":kname(e.kind),
            "obscuration":round((getattr(e,"obscuration",0) or 0)*100,1),
            "peak_utc":e.peak.Utc().replace(tzinfo=dt.timezone.utc).isoformat(),
            "azimuth":round(az,1),"compass":compass16(az),"altitude":round(alt,1),
            "visible":alt>0}

def load_plan():
    try: return json.load(open(PLAN_FILE))
    except Exception: return {"rooms": []}
def save_plan(p): json.dump(p, open(PLAN_FILE,"w"), indent=2)

@app.get("/api/config")
def api_config(): return get_location()

@app.get("/api/eclipse")
def api_eclipse():
    loc = get_location()
    if loc["latitude"] is None: raise HTTPException(400,"Coordinate casa non impostate in HA")
    obs = astronomy.Observer(loc["latitude"], loc["longitude"], loc["elevation"])
    out = {"location":loc,"solar":None,"lunar":None}
    for k,fn in (("solar",next_solar),("lunar",next_lunar)):
        try: out[k]=fn(obs)
        except Exception as ex: out[k]={"error":str(ex)}
    return out

@app.get("/api/plan")
def api_get_plan(): return load_plan()

@app.post("/api/plan")
async def api_save_plan(req: Request):
    body = await req.json()
    if not isinstance(body, dict) or "rooms" not in body: raise HTTPException(400,"formato non valido")
    save_plan(body); return {"ok": True}

@app.post("/api/photo")
async def api_photo(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".jpg",".jpeg",".png",".webp"): ext=".jpg"
    fn = uuid.uuid4().hex[:12]+ext
    with open(os.path.join(PHOTOS, fn),"wb") as f: f.write(await file.read())
    return {"photo": fn}

@app.get("/photos/{fn}")
def get_photo(fn: str):
    p = os.path.join(PHOTOS, os.path.basename(fn))
    if not os.path.exists(p): raise HTTPException(404,"not found")
    return FileResponse(p)

@app.get("/", response_class=HTMLResponse)
def index(): return HTML

HTML = r"""<!doctype html><html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Eclipse Finder</title><style>
:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#f0a500;--ok:#3fb950;--bad:#f85149;
--d-int:#58a6ff;--d-bal:#3fb950;--d-est:#d29922;--d-main:#f85149}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--fg);padding:12px;max-width:960px;margin:auto}
h1{font-size:1.35rem;margin:.2rem 0 .6rem}h2{font-size:1rem;margin:1rem 0 .5rem;color:var(--acc)}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:12px;margin-bottom:10px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.badge{padding:2px 8px;border-radius:20px;font-size:.72rem;font-weight:600}
.ok{background:rgba(63,185,80,.15);color:var(--ok)}.bad{background:rgba(248,81,73,.15);color:var(--bad)}
.mut{color:var(--mut);font-size:.85rem}small{color:var(--mut)}
button{background:var(--acc);color:#111;border:0;border-radius:8px;padding:9px 12px;font-weight:700;cursor:pointer;font-size:.85rem}
button.sec{background:transparent;color:var(--fg);border:1px solid var(--bd)}button:disabled{opacity:.4}
input,select{background:#0d1117;border:1px solid var(--bd);color:var(--fg);border-radius:8px;padding:9px;font-size:.9rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:560px){.grid{grid-template-columns:1fr}}
.big{font-size:1.4rem;font-weight:800}.dir{font-size:1.9rem;font-weight:800;color:var(--acc)}
#planwrap{position:relative;background:#0b0f14;border:1px solid var(--bd);border-radius:10px;overflow:hidden;touch-action:none}
svg text{user-select:none}
.viewwrap{position:relative;display:inline-block;max-width:100%;margin-top:8px}
.viewwrap img{max-width:100%;border-radius:8px;display:block}
.sun{position:absolute;width:42px;height:42px;transform:translate(-50%,-50%);pointer-events:none;filter:drop-shadow(0 0 6px #000)}
.step{display:none}.step.on{display:block}
.livehdg{font-size:2.2rem;font-weight:800;color:var(--acc);text-align:center}
.legend span{display:inline-flex;align-items:center;gap:4px;margin-right:10px;font-size:.78rem}
.dot{width:11px;height:11px;border-radius:3px;display:inline-block}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.6);display:none;align-items:center;justify-content:center;padding:14px;z-index:9}
.modal.on{display:flex}.modalcard{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px;max-width:460px;width:100%;max-height:90vh;overflow:auto}
</style></head><body>
<h1>🌒 Eclipse Finder</h1>
<div id="loc" class="mut">Carico…</div>
<h2>Prossima eclissi</h2>
<div id="eclipse" class="grid"></div>

<h2>Planimetria di casa</h2>
<div class="card">
  <div class="row" style="justify-content:space-between">
    <div class="row">
      <button onclick="addRoom()">➕ Stanza</button>
      <button class="sec" id="addWinBtn" onclick="startAddWindow()">🪟 Finestra</button>
      <button class="sec" id="addDoorBtn" onclick="startAddDoor()">🚪 Porta</button>
    </div>
    <span class="mut" id="mode"></span>
  </div>
  <div class="legend" style="margin:8px 0">
    <span><span class="dot" style="background:var(--d-int)"></span>interna</span>
    <span><span class="dot" style="background:var(--d-bal)"></span>balcone</span>
    <span><span class="dot" style="background:var(--d-est)"></span>esterna</span>
    <span><span class="dot" style="background:var(--d-main)"></span>principale</span>
    <span>🪟 finestra</span>
  </div>
  <div id="planwrap"><svg id="plan" width="100%" viewBox="0 0 1000 640" style="display:block"></svg></div>
  <div id="sel" class="mut" style="margin-top:8px">Tocca una stanza per selezionarla. Trascina per spostare, usa la maniglia ◢ per ridimensionare.</div>
</div>

<div id="roomPanel"></div>

<!-- MODAL: aggiungi finestra -->
<div id="winModal" class="modal"><div class="modalcard">
  <b>Nuova finestra</b>
  <div class="step on" data-s="1"><div class="mut" style="margin:8px 0">In quale stanza?</div>
    <select id="wRoom" style="width:100%"></select>
    <div class="row" style="margin-top:8px"><input id="wRoomNew" placeholder="…oppure crea nuova stanza" style="flex:1"></div>
    <div class="row" style="justify-content:flex-end;margin-top:10px"><button class="sec" onclick="closeWin()">Annulla</button><button onclick="winStep(2)">Avanti →</button></div>
  </div>
  <div class="step" data-s="2"><div class="mut" style="margin:8px 0">Nome finestra</div>
    <input id="wName" placeholder="Es. Finestra grande / Portafinestra" style="width:100%">
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(1)">←</button><button onclick="winStep(3)">Avanti →</button></div>
  </div>
  <div class="step" data-s="3"><div class="mut" style="margin:8px 0">Direzione (punta verso la finestra)</div>
    <div class="livehdg" id="wLive">—°</div><div class="mut" style="text-align:center" id="wLivec"></div>
    <div class="row" style="margin-top:8px"><button class="sec" onclick="enableCompass()">🧭 Bussola</button><button onclick="lockHeading()">🔒 Blocca</button></div>
    <div class="mut" style="text-align:center;margin:8px 0">— oppure gradi a mano —</div>
    <div class="row"><input id="wDeg" type="number" min="0" max="360" placeholder="0–360 (N0 E90 S180 O270)" style="flex:1"><button class="sec" onclick="useManual()">Usa</button></div>
    <div id="wcerr" class="mut"></div>
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(2)">←</button><button id="wS3" disabled onclick="winStep(4)">Avanti →</button></div>
  </div>
  <div class="step" data-s="4"><div class="mut" style="margin:8px 0">Foto della vista (opzionale)</div>
    <label class="sec" style="padding:10px;border:1px solid var(--bd);border-radius:8px;cursor:pointer;display:inline-block">📷 Scatta/scegli<input id="wPhoto" type="file" accept="image/*" capture="environment" style="display:none" onchange="wPhotoPick(this)"></label>
    <span id="wPname" class="mut"></span><div id="wPrev"></div>
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(3)">←</button><button id="wSave" onclick="saveWindow()">💾 Salva finestra</button></div>
  </div>
</div></div>

<script>
const $=s=>document.querySelector(s);
let ECL=null, PLAN={rooms:[]}, LIVE=null, LOCKED=null, WPHOTO=null;
let MODE=null; // 'door:<type>' | 'window' placement
let SEL=null;  // selected room id
const DCOL={interna:'var(--d-int)',balcone:'var(--d-bal)',esterna:'var(--d-est)',principale:'var(--d-main)'};
function fmtLocal(iso){try{return new Date(iso).toLocaleString('it-IT',{dateStyle:'medium',timeStyle:'short'})}catch(e){return iso}}
function angdiff(a,b){return ((a-b+540)%360)-180}
function compass16(az){const d=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"];return d[Math.round((az%360)/22.5)%16]}
function polar(cx,cy,r,az){const a=(az-90)*Math.PI/180;return [cx+r*Math.cos(a),cy+r*Math.sin(a)]}
function uid(){return Math.random().toString(36).slice(2,9)}

let saveT=null;
function savePlan(){clearTimeout(saveT);saveT=setTimeout(()=>fetch('api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(PLAN)}),400)}

async function boot(){
  const d=await (await fetch('api/eclipse')).json();
  if(d.detail){$('#loc').innerHTML='<span class="bad">'+d.detail+'</span>'}else{ECL=d;
    $('#loc').innerHTML='📍 '+d.location.location_name+' — '+d.location.latitude.toFixed(4)+', '+d.location.longitude.toFixed(4);
    const box=$('#eclipse');box.innerHTML='';
    for(const k of['solar','lunar']){const e=d[k];const c=document.createElement('div');c.className='card';
      if(!e||e.error){c.innerHTML='<b>'+(k=='solar'?'Solare':'Lunare')+'</b><div class="mut">'+(e?e.error:'n/d')+'</div>';box.appendChild(c);continue}
      c.innerHTML=`<div class="row" style="justify-content:space-between"><b>${e.type}</b><span class="badge ${e.visible?'ok':'bad'}">${e.visible?'Visibile':'No'}</span></div>
      <div style="margin:4px 0"><span class="badge" style="background:rgba(240,165,0,.15);color:var(--acc)">${e.kind}</span> <span class="mut">· ${e.obscuration}%</span></div>
      <div class="big">${fmtLocal(e.peak_utc)}</div>
      <div class="row" style="margin-top:4px"><div><div class="dir">${e.compass}</div><small>az ${e.azimuth}°</small></div>
      <div style="margin-left:auto;text-align:right"><div class="big">${e.altitude}°</div><small>altezza</small></div></div>`;box.appendChild(c);}
  }
  PLAN=await (await fetch('api/plan')).json(); if(!PLAN.rooms)PLAN={rooms:[]};
  render();
}

// ---------- Planimetria ----------
const SVG=$('#plan');
function svgPt(evt){const r=SVG.getBoundingClientRect();const x=(evt.clientX-r.left)/r.width*1000;const y=(evt.clientY-r.top)/r.height*640;return {x,y}}
function eclArrow(){ // freccia direzione eclissi dal centro
  let e=null;for(const k of['solar','lunar']){if(ECL&&ECL[k]&&ECL[k].visible){e=ECL[k];break}}
  if(!e)return'';const [x,y]=polar(500,320,240,e.azimuth);
  return `<line x1="500" y1="320" x2="${x}" y2="${y}" stroke="${e.body=='sun'?'#ffd24a':'#cfd8e3'}" stroke-width="3" stroke-dasharray="8 6" marker-end="url(#arrow)"/>
   <circle cx="${x}" cy="${y}" r="12" fill="${e.body=='sun'?'#ffd24a':'#cfd8e3'}" stroke="#f0a500"/>
   <text x="${x}" y="${y-18}" fill="var(--acc)" font-size="16" text-anchor="middle">🌒 ${e.compass}</text>`;
}
function render(){
  let s=`<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#f0a500"/></marker></defs>`;
  // griglia
  for(let i=0;i<=1000;i+=50)s+=`<line x1="${i}" y1="0" x2="${i}" y2="640" stroke="#161b22"/>`;
  for(let i=0;i<=640;i+=50)s+=`<line x1="0" y1="${i}" x2="1000" y2="${i}" stroke="#161b22"/>`;
  // rosa dei venti (Nord)
  s+=`<g transform="translate(60,60)"><circle r="34" fill="none" stroke="#30363d"/><line x1="0" y1="0" x2="0" y2="-30" stroke="var(--acc)" stroke-width="2" marker-end="url(#arrow)"/><text x="0" y="-38" fill="var(--acc)" font-size="14" text-anchor="middle">N</text></g>`;
  // stanze
  for(const r of PLAN.rooms){
    const selcol=r.id===SEL?'var(--acc)':'#3b4552';
    s+=`<g data-room="${r.id}">
      <rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" rx="6" fill="rgba(88,166,255,.08)" stroke="${selcol}" stroke-width="${r.id===SEL?3:1.5}"/>
      <text x="${r.x+8}" y="${r.y+20}" fill="var(--fg)" font-size="15" font-weight="700">${escapeHtml(r.name||'Stanza')}</text>`;
    // porte
    for(const d of (r.doors||[])) s+=`<rect x="${d.x-7}" y="${d.y-7}" width="14" height="14" rx="3" fill="${DCOL[d.type]||'#888'}" stroke="#0b0f14"/>`;
    // finestre (marker + freccia azimut)
    for(const w of (r.windows||[])){const wx=w.x!=null?w.x:r.x+r.w/2, wy=w.y!=null?w.y:r.y+r.h/2;
      const [ax,ay]=polar(wx,wy,26,w.azimuth);
      const inview=eclInView(w);
      s+=`<line x1="${wx}" y1="${wy}" x2="${ax}" y2="${ay}" stroke="${inview?'#ffd24a':'#8b949e'}" stroke-width="2" marker-end="url(#arrow)"/>
       <circle cx="${wx}" cy="${wy}" r="6" fill="#e6edf3" stroke="${inview?'#f0a500':'#30363d'}" stroke-width="2"/>`;}
    // maniglia resize
    if(r.id===SEL)s+=`<rect data-resize="${r.id}" x="${r.x+r.w-9}" y="${r.y+r.h-9}" width="18" height="18" fill="var(--acc)" rx="3" style="cursor:nwse-resize"/>`;
    s+=`</g>`;
  }
  s+=eclArrow();
  SVG.innerHTML=s;
  renderRoomPanel();
}
function escapeHtml(t){return (t+'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function eclInView(w){for(const k of['solar','lunar']){const e=ECL&&ECL[k];if(!e||!e.visible)continue;if(Math.abs(angdiff(e.azimuth,w.azimuth))<=(w.photo_fov||66)/2)return e}return null}

// ---- interazione: drag / resize / place / select ----
let drag=null;
SVG.addEventListener('pointerdown',ev=>{
  const p=svgPt(ev);
  if(MODE){placeAt(p);return}
  const rz=ev.target.getAttribute&&ev.target.getAttribute('data-resize');
  if(rz){drag={id:rz,mode:'resize'};SVG.setPointerCapture(ev.pointerId);return}
  // trova stanza sotto il punto (dall'alto)
  let hit=null;for(let i=PLAN.rooms.length-1;i>=0;i--){const r=PLAN.rooms[i];if(p.x>=r.x&&p.x<=r.x+r.w&&p.y>=r.y&&p.y<=r.y+r.h){hit=r;break}}
  if(hit){SEL=hit.id;drag={id:hit.id,mode:'move',dx:p.x-hit.x,dy:p.y-hit.y};SVG.setPointerCapture(ev.pointerId);render();}
  else{SEL=null;render();}
});
SVG.addEventListener('pointermove',ev=>{if(!drag)return;const p=svgPt(ev);const r=PLAN.rooms.find(x=>x.id===drag.id);if(!r)return;
  if(drag.mode==='move'){r.x=Math.round(p.x-drag.dx);r.y=Math.round(p.y-drag.dy)}
  else{r.w=Math.max(60,Math.round(p.x-r.x));r.h=Math.max(50,Math.round(p.y-r.y))}
  render();});
SVG.addEventListener('pointerup',ev=>{if(drag){drag=null;savePlan()}});

function placeAt(p){
  const r=PLAN.rooms.find(x=>x.id===SEL);
  if(!r){setMode(null);alert('Seleziona prima una stanza');return}
  if(MODE.startsWith('door:')){r.doors=r.doors||[];r.doors.push({id:uid(),type:MODE.split(':')[1],x:Math.round(p.x),y:Math.round(p.y)});}
  setMode(null);render();savePlan();
}
function startAddDoor(){
  if(!SEL){alert('Seleziona prima una stanza');return}
  const t=prompt('Tipo porta: interna / balcone / esterna / principale','interna');
  if(!t)return;const tt=t.trim().toLowerCase();if(!DCOL[tt]){alert('Tipo non valido');return}
  setMode('door:'+tt);
}
function setMode(m){MODE=m;$('#mode').textContent=m?('Tocca sul piano per posizionare: '+m.replace('door:','porta ')):'';}

function addRoom(name){
  const r={id:uid(),name:name||('Stanza '+(PLAN.rooms.length+1)),x:120+PLAN.rooms.length*30,y:120+PLAN.rooms.length*24,w:220,h:160,windows:[],doors:[]};
  PLAN.rooms.push(r);SEL=r.id;render();savePlan();return r;
}

function renderRoomPanel(){
  const box=$('#roomPanel');const r=PLAN.rooms.find(x=>x.id===SEL);
  if(!r){box.innerHTML='';return}
  let wins='';
  for(const w of (r.windows||[])){const e=eclInView(w);
    wins+=`<div class="card" style="margin:6px 0">
      <div class="row" style="justify-content:space-between"><b>🪟 ${escapeHtml(w.name)}</b><span class="mut">${compass16(w.azimuth)} · ${w.azimuth}°</span></div>
      <div>${e?'<span class="badge ok">'+e.type.split(' ')[1]+' visibile da qui</span>':'<span class="mut">nessuna eclissi da questo affaccio</span>'}</div>
      <div id="v_${w.id}"></div>
      <div class="row" style="margin-top:6px"><button class="sec" onclick="delWin('${r.id}','${w.id}')">🗑️</button></div></div>`;
  }
  box.innerHTML=`<div class="card"><div class="row" style="justify-content:space-between">
      <input value="${escapeHtml(r.name)}" onchange="renRoom('${r.id}',this.value)" style="flex:1;min-width:140px">
      <button class="sec" onclick="delRoom('${r.id}')">🗑️ Stanza</button></div>
    <div class="mut" style="margin-top:6px">Porte: ${(r.doors||[]).map(d=>d.type).join(', ')||'nessuna'}</div>
    <div style="margin-top:6px">${wins||'<span class="mut">Nessuna finestra in questa stanza.</span>'}</div></div>`;
  for(const w of (r.windows||[])) if(w.photo) drawView(w);
}
function drawView(w){const el=document.getElementById('v_'+w.id);if(!el)return;
  el.innerHTML=`<div class="viewwrap"><img src="photos/${w.photo}?v=${Date.now()}" onload="placeSun('${w.id}',this)"><div id="sun_${w.id}" class="sun" style="display:none">${sunSVG()}</div></div><small id="hint_${w.id}"></small>`;}
function sunSVG(){return `<svg viewBox="0 0 42 42"><circle cx="21" cy="21" r="17" fill="#ffd24a" stroke="#f0a500" stroke-width="2"/><circle cx="28" cy="16" r="15" fill="rgba(13,17,23,.82)"/></svg>`}
window.placeSun=(wid,img)=>{let w=null;for(const r of PLAN.rooms){const f=(r.windows||[]).find(x=>x.id===wid);if(f){w=f;break}}
  const e=w&&eclInView(w);const sun=document.getElementById('sun_'+wid),hint=document.getElementById('hint_'+wid);
  if(!e){if(hint)hint.textContent='Nessuna eclissi visibile da qui.';return}
  const paz=w.photo_az!=null?w.photo_az:w.azimuth, fov=w.photo_fov||66, dh=angdiff(e.azimuth,paz);
  if(Math.abs(dh)>fov/2){sun.style.display='none';hint.textContent=`Fuori inquadratura: ruota verso ${e.compass}.`;return}
  const fovV=fov*(img.clientHeight/img.clientWidth), cAlt=(w.photo_alt!=null?w.photo_alt:15);
  const x=0.5+dh/fov, y=Math.max(0,Math.min(1,0.5-(e.altitude-cAlt)/fovV));
  sun.style.left=(x*100)+'%';sun.style.top=(y*100)+'%';sun.style.display='block';
  hint.textContent=`${e.type} · ${e.compass} ${e.azimuth}° · alt ${e.altitude}° (stimato)`;
};
window.renRoom=(id,v)=>{const r=PLAN.rooms.find(x=>x.id===id);if(r){r.name=v;render();savePlan()}};
window.delRoom=(id)=>{if(confirm('Eliminare la stanza?')){PLAN.rooms=PLAN.rooms.filter(x=>x.id!==id);SEL=null;render();savePlan()}};
window.delWin=(rid,wid)=>{const r=PLAN.rooms.find(x=>x.id===rid);if(r){r.windows=r.windows.filter(x=>x.id!==wid);render();savePlan()}};

// ---------- Wizard finestra ----------
function startAddWindow(){
  LOCKED=null;WPHOTO=null;$('#wS3').disabled=true;$('#wName').value='';$('#wDeg').value='';$('#wPname').textContent='';$('#wPrev').innerHTML='';$('#wLive').textContent='—°';$('#wLivec').textContent='';
  const sel=$('#wRoom');sel.innerHTML='';for(const r of PLAN.rooms){const o=document.createElement('option');o.value=r.id;o.textContent=r.name;sel.appendChild(o)}
  if(SEL)sel.value=SEL;$('#wRoomNew').value='';
  winStep(1);$('#winModal').classList.add('on');
}
function closeWin(){$('#winModal').classList.remove('on')}
function winStep(n){document.querySelectorAll('#winModal .step').forEach(s=>s.classList.toggle('on',+s.dataset.s===n));
  if(n===3)$('#wLivec').textContent=LOCKED!=null?compass16(LOCKED)+' '+LOCKED+'°':'';}
function orient(ev){let h=null;if(ev.webkitCompassHeading!=null)h=ev.webkitCompassHeading;else if(ev.absolute&&ev.alpha!=null)h=(360-ev.alpha)%360;
  if(h!=null){LIVE=Math.round(h);$('#wLive').textContent=LIVE+'°';$('#wLivec').textContent=compass16(LIVE)}}
async function enableCompass(){$('#wcerr').textContent='';try{
  if(typeof DeviceOrientationEvent!=='undefined'&&DeviceOrientationEvent.requestPermission){const p=await DeviceOrientationEvent.requestPermission();if(p!=='granted'){$('#wcerr').innerHTML='<span class="bad">Permesso negato</span>';return}}
  addEventListener('deviceorientationabsolute',orient,true);addEventListener('deviceorientation',orient,true);$('#wLivec').textContent='muovi a "8"…';
}catch(e){$('#wcerr').innerHTML='<span class="bad">Bussola solo su HTTPS</span>'}}
function lockHeading(){if(LIVE==null){alert('Attiva la bussola');return}LOCKED=LIVE;$('#wLive').textContent=LOCKED+'° 🔒';$('#wS3').disabled=false}
function useManual(){let v=parseFloat($('#wDeg').value);if(isNaN(v)){alert('Gradi 0-360');return}LOCKED=((v%360)+360)%360;$('#wLive').textContent=LOCKED+'° ✍️';$('#wLivec').textContent=compass16(LOCKED)+' (manuale)';$('#wS3').disabled=false}
function wPhotoPick(inp){if(!inp.files[0])return;WPHOTO=inp.files[0];$('#wPname').textContent='✓';$('#wPrev').innerHTML='<div class="viewwrap"><img src="'+URL.createObjectURL(WPHOTO)+'"></div>'}
async function saveWindow(){
  let roomId=$('#wRoom').value;const newName=$('#wRoomNew').value.trim();
  if(newName){const r=addRoom(newName);roomId=r.id}
  const room=PLAN.rooms.find(x=>x.id===roomId);
  if(!room){alert('Scegli o crea una stanza');return}
  if(!$('#wName').value.trim()||LOCKED==null){alert('Manca nome o direzione');return}
  let photo=null;if(WPHOTO){const fd=new FormData();fd.append('file',WPHOTO);photo=(await (await fetch('api/photo',{method:'POST',body:fd})).json()).photo}
  room.windows=room.windows||[];
  room.windows.push({id:uid(),name:$('#wName').value.trim(),azimuth:LOCKED,photo_az:LOCKED,photo:photo,photo_fov:66,alt_min:0,
    x:room.x+room.w/2,y:room.y+room.h/2});
  SEL=roomId;closeWin();render();savePlan();
}
boot();
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
