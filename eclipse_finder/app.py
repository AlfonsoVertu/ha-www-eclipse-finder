import os, json, uuid, urllib.request
import datetime as dt
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import uvicorn
import astronomy

DATA = "/data"; PHOTOS = os.path.join(DATA, "photos"); MODELS = os.path.join(DATA, "models"); PLAN_FILE = os.path.join(DATA, "plan.json")
os.makedirs(PHOTOS, exist_ok=True); os.makedirs(MODELS, exist_ok=True)
VENDOR = "/vendor"  # libreria model-viewer inclusa nell'immagine (offline)
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

@app.post("/api/model")
async def api_model(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".glb",".gltf"): ext=".glb"
    fn = uuid.uuid4().hex[:12]+ext
    with open(os.path.join(MODELS, fn),"wb") as f: f.write(await file.read())
    return {"model": fn}

@app.get("/models/{fn}")
def get_model(fn: str):
    p = os.path.join(MODELS, os.path.basename(fn))
    if not os.path.exists(p): raise HTTPException(404,"not found")
    return FileResponse(p)

@app.get("/vendor/{fn}")
def get_vendor(fn: str):
    if not fn.endswith(".js"): raise HTTPException(404,"not found")
    p = os.path.join(VENDOR, os.path.basename(fn))
    if not os.path.exists(p): raise HTTPException(404,"libreria non inclusa nel build")
    return FileResponse(p, media_type="text/javascript")

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
model-viewer{--poster-color:transparent}
</style>
<script type="module" src="vendor/model-viewer.min.js"></script>
</head><body>
<h1>🌒 Eclipse Finder</h1>
<div id="loc" class="mut">Carico…</div>
<h2>Prossima eclissi</h2>
<div id="eclipse" class="grid"></div>

<h2>Planimetria di casa</h2>
<div class="card">
  <div class="row" style="justify-content:space-between">
    <div class="row">
      <button onclick="startAddRoom()">➕ Stanza</button>
      <button class="sec" onclick="startDrawRoom()">✏️ Disegna</button>
      <button class="sec" id="addWinBtn" onclick="startAddWindow()">🪟 Finestra</button>
      <button class="sec" id="addDoorBtn" onclick="startAddDoor()">🚪 Porta</button>
      <button class="sec" onclick="startAddFurn()">🛋️ Mobile</button>
      <button class="sec" onclick="openHouse3D()">🏠 Casa 3D</button>
      <button class="sec" onclick="toggleExport()">⬇️ Esporta</button>
    </div>
    <span class="mut" id="mode"></span>
  </div>
  <div class="legend" style="margin:8px 0">
    <span>🏠 interna</span><span>🌿 balcone</span><span>☀️ terrazzo</span><span>🌳 giardino</span>
    <span>·</span><span>🪟 finestra</span><span>👁️ vista</span><span>🛋️ mobile</span>
    <span>·</span><span class="mut">Porte:</span>
    <span><span class="dot" style="background:var(--d-int)"></span>int</span>
    <span><span class="dot" style="background:var(--d-bal)"></span>balc</span>
    <span><span class="dot" style="background:var(--d-est)"></span>est</span>
    <span><span class="dot" style="background:var(--d-main)"></span>princ</span>
  </div>
  <div id="roomPicker" class="row" style="display:none;margin:6px 0">
    <span class="mut">Tipo stanza:</span>
    <button class="sec" onclick="pickRoom('interna')">🏠 interna</button>
    <button class="sec" onclick="pickRoom('balcone')">🌿 balcone</button>
    <button class="sec" onclick="pickRoom('terrazzo')">☀️ terrazzo</button>
    <button class="sec" onclick="pickRoom('giardino')">🌳 giardino</button>
  </div>
  <div id="drawBtns" class="row" style="display:none;margin:6px 0">
    <span class="mut">Disegno stanza — tocca i vertici:</span>
    <button onclick="finishDraw()">✔️ Chiudi forma</button>
    <button class="sec" onclick="undoDraw()">↶ Annulla punto</button>
    <button class="sec" onclick="cancelDraw()">✖️ Esci</button>
  </div>
  <div id="doorPicker" class="row" style="display:none;margin:6px 0">
    <span class="mut">Tipo porta:</span>
    <button class="sec" onclick="pickDoor('interna')">🚪 interna</button>
    <button class="sec" onclick="pickDoor('balcone')">🌿 balcone</button>
    <button class="sec" onclick="pickDoor('esterna')">🚶 esterna</button>
    <button class="sec" onclick="pickDoor('principale')">🏠 principale</button>
  </div>
  <div id="furnPicker" class="row" style="display:none;margin:6px 0"></div>
  <div id="exportPicker" class="row" style="display:none;margin:6px 0">
    <span class="mut">Esporta planimetria 2D:</span>
    <button class="sec" onclick="exportPNG()">🖼️ PNG</button>
    <button class="sec" onclick="exportSVG()">▦ SVG</button>
    <span class="mut">· il 3D (.glb) si esporta dalla vista 🏠 Casa 3D</span>
  </div>
  <div id="planwrap"><svg id="plan" width="100%" viewBox="0 0 1000 640" style="display:block"></svg></div>
  <div id="sel" class="mut" style="margin-top:8px">Tocca una stanza per selezionarla. Trascina per spostare, maniglia ◢ per ridimensionare. Stanze disegnate: trascina i vertici ◆. Usa ✏️ Disegna per forme non rettangolari.</div>
</div>

<div id="roomPanel"></div>
<div id="furnPanel"></div>

<!-- MODAL: nuovo template mobile -->
<div id="tplModal" class="modal"><div class="modalcard">
  <b>Nuovo template mobile</b>
  <div class="mut" style="margin:8px 0">Nome e dimensioni dei lati (unità del piano). Lo costruisci una volta e poi lo piazzi quante volte vuoi.</div>
  <input id="tplName" placeholder="Es. Scrivania / Armadio 3 ante" style="width:100%">
  <div class="row" style="margin-top:8px"><input id="tplW" type="number" min="10" placeholder="larghezza" style="flex:1"><input id="tplH" type="number" min="10" placeholder="profondità" style="flex:1"></div>
  <div class="row" style="margin-top:8px"><label class="sec" style="padding:9px;border:1px solid var(--bd);border-radius:8px;cursor:pointer">🧊 Modello 3D (.glb) opz.<input id="tplModel" type="file" accept=".glb,.gltf,model/gltf-binary" style="display:none" onchange="tplModelPick(this)"></label><span id="tplModelName" class="mut"></span></div>
  <div class="mut" style="margin-top:4px">Esporta da Blender in glTF 2.0 (.glb), senza compressione Draco per il 3D offline.</div>
  <div class="row" style="justify-content:flex-end;margin-top:10px"><button class="sec" onclick="closeTpl()">Annulla</button><button onclick="saveTpl()">💾 Salva template</button></div>
</div></div>

<!-- MODAL: casa in 3D -->
<div id="house3dModal" class="modal"><div class="modalcard" style="max-width:960px;width:96vw">
  <div class="row" style="justify-content:space-between;flex-wrap:nowrap">
    <b>🏠 Casa in 3D</b>
    <div class="row"><span class="mut">Muri</span><input id="h3h" type="range" min="150" max="400" value="250" oninput="setH3Height(this.value)" style="width:100px"><button class="sec" onclick="exportGLB()">⬇️ .glb</button><button class="sec" onclick="closeHouse3D()">✖️ Chiudi</button></div>
  </div>
  <div id="house3dBox" style="margin-top:8px;height:72vh;background:#0b0f14;border-radius:8px;overflow:hidden"></div>
  <div id="house3dInfo" class="mut" style="margin-top:6px"></div>
</div></div>

<!-- MODAL: vista 3D a schermo intero -->
<div id="modelModal" class="modal"><div class="modalcard" style="max-width:680px">
  <div class="row" style="justify-content:space-between"><b>🧊 Vista 3D</b><button class="sec" onclick="closeModel3D()">✖️ Chiudi</button></div>
  <div id="model3dBox" style="margin-top:8px"></div>
</div></div>

<!-- MODAL: aggiungi finestra -->
<div id="winModal" class="modal"><div class="modalcard">
  <b id="winTitle">Nuova finestra</b>
  <div class="step on" data-s="1"><div class="mut" style="margin:8px 0">In quale stanza?</div>
    <select id="wRoom" style="width:100%" onchange="updateWinLabels()"></select>
    <div class="row" style="margin-top:8px"><input id="wRoomNew" placeholder="…oppure crea nuova stanza (interna)" style="flex:1" oninput="updateWinLabels()"></div>
    <div class="row" style="justify-content:flex-end;margin-top:10px"><button class="sec" onclick="closeWin()">Annulla</button><button onclick="winStep(2)">Avanti →</button></div>
  </div>
  <div class="step" data-s="2"><div class="mut" style="margin:8px 0" id="wNameLbl">Nome finestra</div>
    <input id="wName" placeholder="Es. Finestra grande / Portafinestra" style="width:100%">
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(1)">←</button><button onclick="winStep(3)">Avanti →</button></div>
  </div>
  <div class="step" data-s="3"><div class="mut" style="margin:8px 0" id="wDirLbl">Direzione (punta verso la finestra)</div>
    <div class="mut" style="margin:-4px 0 8px">Tieni il telefono come per fotografare la vista: catturo direzione <b>e</b> inclinazione.</div>
    <div class="livehdg" id="wLive">—°</div><div class="mut" style="text-align:center" id="wLivec"></div>
    <div class="mut" style="text-align:center">inclinazione (centro foto): <b id="wLiveAlt">—°</b></div>
    <div class="row" style="margin-top:8px"><button class="sec" onclick="enableCompass()">🧭 Bussola</button><button onclick="lockHeading()">🔒 Blocca mira</button></div>
    <div class="mut" style="text-align:center;margin:8px 0">— oppure a mano —</div>
    <div class="row"><input id="wDeg" type="number" min="0" max="360" placeholder="direzione 0–360 (N0 E90 S180 O270)" style="flex:1"></div>
    <div class="row" style="margin-top:6px"><input id="wAlt" type="number" min="-80" max="80" placeholder="altezza centro (° opz, 0=orizzonte)" style="flex:1"><button class="sec" onclick="useManual()">Usa</button></div>
    <div id="wcerr" class="mut"></div>
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(2)">←</button><button id="wS3" disabled onclick="winStep(4)">Avanti →</button></div>
  </div>
  <div class="step" data-s="4"><div class="mut" style="margin:8px 0">Foto della vista (opzionale)</div>
    <label class="sec" style="padding:10px;border:1px solid var(--bd);border-radius:8px;cursor:pointer;display:inline-block">📷 Scatta/scegli<input id="wPhoto" type="file" accept="image/*" capture="environment" style="display:none" onchange="wPhotoPick(this)"></label>
    <span id="wPname" class="mut"></span><div id="wPrev"></div>
    <div class="row" style="margin-top:8px"><span class="mut">Campo visivo orizz.:</span><input id="wFov" type="number" min="20" max="140" value="66" style="width:80px"><span class="mut">°</span></div>
    <div id="wFovHint" class="mut" style="margin-top:4px"></div>
    <div class="row" style="justify-content:space-between;margin-top:10px"><button class="sec" onclick="winStep(3)">←</button><button id="wSave" onclick="saveWindow()">💾 Salva finestra</button></div>
  </div>
</div></div>

<script>
const $=s=>document.querySelector(s);
let ECL=null, PLAN={rooms:[]}, LIVE=null, LOCKED=null, WPHOTO=null, LIVEPITCH=null, LOCKEDALT=null, TPLMODEL=null;
let MODE=null; // 'door:<type>' | 'draw' | 'furn:<tpl>' | placement
let SEL=null;  // selected room id
let SELF=null; // selected furniture id
let DRAWPTS=[]; // vertici della stanza in disegno
const DEFAULT_TEMPLATES=[
  {id:'t_arm',name:'Armadio',w:110,h:55},
  {id:'t_single',name:'Letto singolo',w:90,h:200},
  {id:'t_double',name:'Letto matrimoniale',w:160,h:200},
];
const DCOL={interna:'var(--d-int)',balcone:'var(--d-bal)',esterna:'var(--d-est)',principale:'var(--d-main)'};
const ROOM_EMO={interna:'🏠',balcone:'🌿',terrazzo:'☀️',giardino:'🌳'};
function isExt(r){return r&&r.kind==='esterna'}
function roomEmo(r){return ROOM_EMO[r.subtype]||(isExt(r)?'🌿':'🏠')}
function viewIcon(r){return isExt(r)?'👁️':'🪟'}
function viewNoun(r){return isExt(r)?'punto di osservazione':'finestra'}
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
  if(!PLAN.templates)PLAN.templates=DEFAULT_TEMPLATES.slice();
  if(!PLAN.furniture)PLAN.furniture=[];
  PLAN.rooms.forEach(clampRoom); savePlan(); // recupera stanze finite fuori dal piano
  render();
}

// ---------- Planimetria ----------
const SVG=$('#plan');
function clampRoom(r){
  if(r.poly&&r.poly.length){r.poly=r.poly.map(pt=>[Math.max(0,Math.min(1000,Math.round(pt[0]))),Math.max(0,Math.min(640,Math.round(pt[1])))]);return}
  r.w=Math.max(60,Math.min(1000,r.w));r.h=Math.max(50,Math.min(640,r.h));r.x=Math.max(0,Math.min(1000-r.w,Math.round(r.x)));r.y=Math.max(0,Math.min(640-r.h,Math.round(r.y)));
}
function roomBBox(r){if(r.poly&&r.poly.length){const xs=r.poly.map(p=>p[0]),ys=r.poly.map(p=>p[1]);const x=Math.min(...xs),y=Math.min(...ys);return{x,y,w:Math.max(...xs)-x,h:Math.max(...ys)-y}}return{x:r.x,y:r.y,w:r.w,h:r.h}}
function roomCenter(r){const b=roomBBox(r);return{x:Math.round(b.x+b.w/2),y:Math.round(b.y+b.h/2)}}
function pointInRoom(r,p){
  if(r.poly&&r.poly.length>=3){let inside=false,q=r.poly;for(let i=0,j=q.length-1;i<q.length;j=i++){const xi=q[i][0],yi=q[i][1],xj=q[j][0],yj=q[j][1];if(((yi>p.y)!==(yj>p.y))&&(p.x<(xj-xi)*(p.y-yi)/(yj-yi)+xi))inside=!inside}return inside}
  return p.x>=r.x&&p.x<=r.x+r.w&&p.y>=r.y&&p.y<=r.y+r.h;
}
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
    const selcol=r.id===SEL?'var(--acc)':'#3b4552';const ext=isExt(r);
    const fill=ext?'rgba(63,185,80,.09)':'rgba(88,166,255,.08)';
    const dash=ext?' stroke-dasharray="8 5"':'';const b=roomBBox(r);const sw=r.id===SEL?3:1.5;
    s+=`<g data-room="${r.id}">`;
    if(r.poly&&r.poly.length>=3){const pts=r.poly.map(p=>p[0]+','+p[1]).join(' ');
      s+=`<polygon points="${pts}" fill="${fill}" stroke="${selcol}" stroke-width="${sw}"${dash}/>`;}
    else s+=`<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="6" fill="${fill}" stroke="${selcol}" stroke-width="${sw}"${dash}/>`;
    s+=`<text x="${b.x+8}" y="${b.y+20}" fill="var(--fg)" font-size="15" font-weight="700">${roomEmo(r)} ${escapeHtml(r.name||'Stanza')}</text>`;
    // porte
    for(const d of (r.doors||[])) s+=`<rect x="${d.x-7}" y="${d.y-7}" width="14" height="14" rx="3" fill="${DCOL[d.type]||'#888'}" stroke="#0b0f14"/>`;
    // finestre / punti di osservazione (marker + freccia azimut)
    const c=roomCenter(r);
    for(const w of (r.windows||[])){const wx=w.x!=null?w.x:c.x, wy=w.y!=null?w.y:c.y;
      const [ax,ay]=polar(wx,wy,26,w.azimuth);
      const inview=eclInView(w);
      s+=`<line x1="${wx}" y1="${wy}" x2="${ax}" y2="${ay}" stroke="${inview?'#ffd24a':'#8b949e'}" stroke-width="2" marker-end="url(#arrow)"/>`;
      if(ext)s+=`<rect x="${wx-6}" y="${wy-6}" width="12" height="12" transform="rotate(45 ${wx} ${wy})" fill="#3fb950" stroke="${inview?'#f0a500':'#0b0f14'}" stroke-width="2"/>`;
      else s+=`<circle cx="${wx}" cy="${wy}" r="6" fill="#e6edf3" stroke="${inview?'#f0a500':'#30363d'}" stroke-width="2"/>`;}
    // maniglie: vertici (poligono) o resize (rettangolo)
    if(r.id===SEL){
      if(r.poly&&r.poly.length)for(let vi=0;vi<r.poly.length;vi++){const v=r.poly[vi];
        s+=`<rect data-vert="${r.id}:${vi}" x="${v[0]-7}" y="${v[1]-7}" width="14" height="14" fill="var(--acc)" rx="3" transform="rotate(45 ${v[0]} ${v[1]})" style="cursor:move"/>`;}
      else s+=`<rect data-resize="${r.id}" x="${b.x+b.w-9}" y="${b.y+b.h-9}" width="18" height="18" fill="var(--acc)" rx="3" style="cursor:nwse-resize"/>`;
    }
    s+=`</g>`;
  }
  // mobili
  for(const f of (PLAN.furniture||[])){const sel=f.id===SELF;const stroke=sel?'var(--acc)':'#8b949e';
    s+=`<g transform="rotate(${f.rot||0} ${f.x} ${f.y})">
      <rect x="${f.x-f.w/2}" y="${f.y-f.h/2}" width="${f.w}" height="${f.h}" rx="4" fill="rgba(139,148,158,.20)" stroke="${stroke}" stroke-width="${sel?2.5:1.5}"/>
      <text x="${f.x}" y="${f.y}" fill="var(--fg)" font-size="12" text-anchor="middle" dominant-baseline="middle">${escapeHtml(f.name||'')}</text>`;
    if(sel){
      s+=`<rect data-furnrz="${f.id}" x="${f.x+f.w/2-7}" y="${f.y+f.h/2-7}" width="14" height="14" fill="var(--acc)" rx="2" style="cursor:nwse-resize"/>`;
      s+=`<line x1="${f.x}" y1="${f.y-f.h/2}" x2="${f.x}" y2="${f.y-f.h/2-22}" stroke="var(--acc)" stroke-width="1.5"/><circle data-furnrot="${f.id}" cx="${f.x}" cy="${f.y-f.h/2-22}" r="7" fill="var(--acc)" style="cursor:grab"/>`;
    }
    s+=`</g>`;
  }
  // forma in disegno
  if(MODE==='draw'&&DRAWPTS.length){const pts=DRAWPTS.map(p=>p[0]+','+p[1]).join(' ');
    s+=`<polyline points="${pts}" fill="rgba(240,165,0,.10)" stroke="var(--acc)" stroke-width="2" stroke-dasharray="6 4"/>`;
    for(const v of DRAWPTS)s+=`<circle cx="${v[0]}" cy="${v[1]}" r="5" fill="var(--acc)"/>`;}
  s+=eclArrow();
  SVG.innerHTML=s;
  renderRoomPanel();renderFurnPanel();
}
function clampFurn(f){f.x=Math.max(0,Math.min(1000,Math.round(f.x)));f.y=Math.max(0,Math.min(640,Math.round(f.y)));}
function furnHit(f,p){const a=-(f.rot||0)*Math.PI/180,dx=p.x-f.x,dy=p.y-f.y;const lx=dx*Math.cos(a)-dy*Math.sin(a),ly=dx*Math.sin(a)+dy*Math.cos(a);return Math.abs(lx)<=f.w/2&&Math.abs(ly)<=f.h/2;}
function escapeHtml(t){return (t+'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function eclInView(w){for(const k of['solar','lunar']){const e=ECL&&ECL[k];if(!e||!e.visible)continue;if(Math.abs(angdiff(e.azimuth,w.azimuth))<=(w.photo_fov||66)/2)return e}return null}

// ---- interazione: drag / resize / place / select ----
let drag=null;
SVG.addEventListener('pointerdown',ev=>{
  const p=svgPt(ev);
  if(MODE==='draw'){DRAWPTS.push([Math.round(p.x),Math.round(p.y)]);render();return}
  if(MODE){placeAt(p);return}
  const vt=ev.target.getAttribute&&ev.target.getAttribute('data-vert');
  if(vt){const a=vt.split(':');drag={mode:'vertmove',id:a[0],vi:+a[1]};SVG.setPointerCapture(ev.pointerId);return}
  const rz=ev.target.getAttribute&&ev.target.getAttribute('data-resize');
  if(rz){drag={id:rz,mode:'resize'};SVG.setPointerCapture(ev.pointerId);return}
  const fz=ev.target.getAttribute&&ev.target.getAttribute('data-furnrz');
  if(fz){SELF=fz;SEL=null;drag={mode:'furnresize',id:fz};SVG.setPointerCapture(ev.pointerId);render();return}
  const fr=ev.target.getAttribute&&ev.target.getAttribute('data-furnrot');
  if(fr){SELF=fr;SEL=null;drag={mode:'furnrot',id:fr};SVG.setPointerCapture(ev.pointerId);render();return}
  // hit-test finestre/porte (trascinabili) prima delle stanze
  for(const r of PLAN.rooms){const c=roomCenter(r);
    for(const w of (r.windows||[])){const wx=w.x!=null?w.x:c.x, wy=w.y!=null?w.y:c.y;
      if(Math.hypot(p.x-wx,p.y-wy)<14){SEL=r.id;SELF=null;drag={mode:'winmove',roomId:r.id,eid:w.id};SVG.setPointerCapture(ev.pointerId);render();return}}
    for(const d of (r.doors||[])){if(Math.hypot(p.x-d.x,p.y-d.y)<12){SEL=r.id;SELF=null;drag={mode:'doormove',roomId:r.id,eid:d.id};SVG.setPointerCapture(ev.pointerId);render();return}}
  }
  // mobili (sopra le stanze)
  for(let i=(PLAN.furniture||[]).length-1;i>=0;i--){const f=PLAN.furniture[i];if(furnHit(f,p)){SELF=f.id;SEL=null;drag={mode:'furnmove',id:f.id,dx:p.x-f.x,dy:p.y-f.y};SVG.setPointerCapture(ev.pointerId);render();return}}
  // trova stanza sotto il punto (dall'alto)
  let hit=null;for(let i=PLAN.rooms.length-1;i>=0;i--){if(pointInRoom(PLAN.rooms[i],p)){hit=PLAN.rooms[i];break}}
  if(hit){SEL=hit.id;SELF=null;
    if(hit.poly&&hit.poly.length)drag={id:hit.id,mode:'polymove',sx:p.x,sy:p.y,orig:hit.poly.map(v=>[v[0],v[1]])};
    else drag={id:hit.id,mode:'move',dx:p.x-hit.x,dy:p.y-hit.y};
    SVG.setPointerCapture(ev.pointerId);render();}
  else{SEL=null;SELF=null;render();}
});
SVG.addEventListener('pointermove',ev=>{if(!drag)return;const p=svgPt(ev);
  if(drag.mode==='winmove'){const r=PLAN.rooms.find(x=>x.id===drag.roomId);const w=r&&r.windows.find(x=>x.id===drag.eid);if(w){w.x=Math.round(p.x);w.y=Math.round(p.y);render()}return}
  if(drag.mode==='doormove'){const r=PLAN.rooms.find(x=>x.id===drag.roomId);const d=r&&r.doors.find(x=>x.id===drag.eid);if(d){d.x=Math.round(p.x);d.y=Math.round(p.y);render()}return}
  if(drag.mode==='vertmove'){const r=PLAN.rooms.find(x=>x.id===drag.id);if(r&&r.poly){r.poly[drag.vi]=[Math.round(p.x),Math.round(p.y)];clampRoom(r);render()}return}
  if(drag.mode==='polymove'){const r=PLAN.rooms.find(x=>x.id===drag.id);if(r&&r.poly){const dx=p.x-drag.sx,dy=p.y-drag.sy;r.poly=drag.orig.map(v=>[Math.round(v[0]+dx),Math.round(v[1]+dy)]);clampRoom(r);render()}return}
  if(drag.mode==='furnmove'){const f=PLAN.furniture.find(x=>x.id===drag.id);if(f){f.x=p.x-drag.dx;f.y=p.y-drag.dy;clampFurn(f);render()}return}
  if(drag.mode==='furnrot'){const f=PLAN.furniture.find(x=>x.id===drag.id);if(f){let ang=Math.atan2(p.y-f.y,p.x-f.x)*180/Math.PI+90;f.rot=Math.round(((ang%360)+360)%360);render()}return}
  if(drag.mode==='furnresize'){const f=PLAN.furniture.find(x=>x.id===drag.id);if(f){const a=-(f.rot||0)*Math.PI/180,dx=p.x-f.x,dy=p.y-f.y;const lx=Math.abs(dx*Math.cos(a)-dy*Math.sin(a)),ly=Math.abs(dx*Math.sin(a)+dy*Math.cos(a));f.w=Math.max(15,Math.round(lx*2));f.h=Math.max(15,Math.round(ly*2));render()}return}
  const r=PLAN.rooms.find(x=>x.id===drag.id);if(!r)return;
  if(drag.mode==='move'){r.x=Math.round(p.x-drag.dx);r.y=Math.round(p.y-drag.dy)}
  else if(drag.mode==='resize'){r.w=Math.max(60,Math.round(p.x-r.x));r.h=Math.max(50,Math.round(p.y-r.y))}
  clampRoom(r);render();});
SVG.addEventListener('pointerup',ev=>{if(drag){drag=null;savePlan()}});

function placeAt(p){
  if(MODE.startsWith('furn:')){const tid=MODE.split(':')[1];const t=(PLAN.templates||[]).find(x=>x.id===tid);
    PLAN.furniture=PLAN.furniture||[];const f={id:uid(),tpl:tid,name:t?t.name:'Mobile',w:t?t.w:80,h:t?t.h:80,rot:0,x:Math.round(p.x),y:Math.round(p.y)};
    clampFurn(f);PLAN.furniture.push(f);SELF=f.id;SEL=null;setMode(null);render();savePlan();return;}
  const r=PLAN.rooms.find(x=>x.id===SEL);
  if(!r){setMode(null);alert('Seleziona prima una stanza');return}
  if(MODE.startsWith('door:')){r.doors=r.doors||[];r.doors.push({id:uid(),type:MODE.split(':')[1],x:Math.round(p.x),y:Math.round(p.y)});}
  setMode(null);render();savePlan();
}
// ---- mobili: libreria template + istanze ----
function renderFurnPicker(){let h='<span class="mut">Mobile:</span>';
  for(const t of (PLAN.templates||[]))h+=`<button class="sec" onclick="pickFurn('${t.id}')">${escapeHtml(t.name)} <small>${t.w}×${t.h}${t.model?' 🧊':''}</small></button>`;
  h+='<button onclick="openTpl()">➕ Nuovo template</button>';$('#furnPicker').innerHTML=h;}
function startAddFurn(){setMode(null);renderFurnPicker();$('#furnPicker').style.display='flex';}
function pickFurn(id){$('#furnPicker').style.display='none';setMode('furn:'+id);}
function openTpl(){$('#furnPicker').style.display='none';$('#tplName').value='';$('#tplW').value='';$('#tplH').value='';TPLMODEL=null;$('#tplModel').value='';$('#tplModelName').textContent='';$('#tplModal').classList.add('on');}
function closeTpl(){$('#tplModal').classList.remove('on');}
function tplModelPick(inp){TPLMODEL=inp.files[0]||null;$('#tplModelName').textContent=TPLMODEL?('✓ '+TPLMODEL.name):'';}
async function uploadModel(file){const fd=new FormData();fd.append('file',file);return (await (await fetch('api/model',{method:'POST',body:fd})).json()).model;}
async function saveTpl(){const n=$('#tplName').value.trim();const w=parseInt($('#tplW').value),h=parseInt($('#tplH').value);
  if(!n||!(w>0)||!(h>0)){alert('Servono nome e dimensioni valide');return}
  let model=null;if(TPLMODEL){try{model=await uploadModel(TPLMODEL)}catch(e){alert('Upload modello fallito');return}}
  PLAN.templates=PLAN.templates||[];const t={id:uid(),name:n,w,h};if(model)t.model=model;PLAN.templates.push(t);
  savePlan();closeTpl();renderFurnPicker();$('#furnPicker').style.display='flex';}
async function addTplModel(tplId,inp){if(!inp.files[0])return;let m;try{m=await uploadModel(inp.files[0])}catch(e){alert('Upload fallito');return}
  const t=(PLAN.templates||[]).find(x=>x.id===tplId);if(t){t.model=m;savePlan();render()}}
window.delTplModel=(tplId)=>{const t=(PLAN.templates||[]).find(x=>x.id===tplId);if(t&&confirm('Rimuovere il modello 3D dal template?')){delete t.model;savePlan();render()}};
function openModel3D(fn){$('#model3dBox').innerHTML=`<model-viewer src="models/${fn}" camera-controls auto-rotate style="width:100%;height:70vh;background:#0b0f14;border-radius:8px"></model-viewer>`;$('#modelModal').classList.add('on');}
function closeModel3D(){$('#modelModal').classList.remove('on');$('#model3dBox').innerHTML='';}
function renderFurnPanel(){const box=$('#furnPanel');const f=(PLAN.furniture||[]).find(x=>x.id===SELF);if(!f){box.innerHTML='';return}
  const t=(PLAN.templates||[]).find(x=>x.id===f.tpl);const model=t&&t.model;
  let m3d='';
  if(model)m3d=`<div style="margin-top:8px"><model-viewer src="models/${model}" camera-controls auto-rotate disable-tap style="width:100%;height:200px;background:#0b0f14;border-radius:8px"></model-viewer>
      <div class="row" style="margin-top:6px"><button class="sec" onclick="openModel3D('${model}')">🧊 Vista 3D</button><button class="sec" onclick="delTplModel('${f.tpl}')">Rimuovi 3D</button></div></div>`;
  else if(t)m3d=`<div class="row" style="margin-top:8px"><label class="sec" style="padding:9px;border:1px solid var(--bd);border-radius:8px;cursor:pointer">🧊 Aggiungi modello 3D (.glb)<input type="file" accept=".glb,.gltf" style="display:none" onchange="addTplModel('${f.tpl}',this)"></label></div><div class="mut" style="margin-top:4px">si applica al template «${escapeHtml(t.name)}»</div>`;
  box.innerHTML=`<div class="card"><div class="row" style="justify-content:space-between"><b>🛋️ Mobile</b><button class="sec" onclick="delFurn('${f.id}')">🗑️</button></div>
    <div class="row" style="margin-top:8px"><span class="mut">Nome</span><input value="${escapeHtml(f.name||'')}" onchange="setFurn('${f.id}','name',this.value)" style="flex:1;min-width:120px"></div>
    <div class="row" style="margin-top:6px"><span class="mut">L</span><input type="number" value="${f.w}" onchange="setFurn('${f.id}','w',this.value)" style="width:76px"><span class="mut">P</span><input type="number" value="${f.h}" onchange="setFurn('${f.id}','h',this.value)" style="width:76px"><span class="mut">Rot°</span><input type="number" value="${f.rot||0}" onchange="setFurn('${f.id}','rot',this.value)" style="width:76px"></div>
    ${m3d}
    <div class="row" style="margin-top:8px"><button class="sec" onclick="furnToTpl('${f.id}')">⭐ Salva come template</button></div></div>`;}
window.setFurn=(id,k,v)=>{const f=PLAN.furniture.find(x=>x.id===id);if(!f)return;
  if(k==='name')f.name=v;else{let n=parseInt(v);if(!isNaN(n)){if(k==='rot')f.rot=((n%360)+360)%360;else f[k]=Math.max(10,n)}}
  render();savePlan();};
window.delFurn=(id)=>{PLAN.furniture=PLAN.furniture.filter(x=>x.id!==id);SELF=null;render();savePlan();};
window.furnToTpl=(id)=>{const f=PLAN.furniture.find(x=>x.id===id);if(!f)return;const n=prompt('Nome del template',f.name||'Mobile');if(!n)return;
  const src=(PLAN.templates||[]).find(x=>x.id===f.tpl);const nt={id:uid(),name:n.trim(),w:f.w,h:f.h};if(src&&src.model)nt.model=src.model;
  PLAN.templates=PLAN.templates||[];PLAN.templates.push(nt);savePlan();alert('Template salvato: '+n.trim());};
function startAddDoor(){
  if(!SEL){alert('Seleziona prima una stanza');return}
  $('#doorPicker').style.display='flex';
}
function pickDoor(t){$('#doorPicker').style.display='none';setMode('door:'+t);}
function setMode(m){MODE=m;
  let t='';if(m&&m.startsWith('furn:'))t='Tocca sul piano per posizionare il mobile';else if(m)t='Tocca sul piano per posizionare: '+m.replace('door:','porta ');
  $('#mode').textContent=t;
  if(!m){$('#doorPicker').style.display='none';$('#roomPicker').style.display='none';$('#drawBtns').style.display='none';$('#furnPicker').style.display='none'}}

// ---- disegno stanza poligonale ----
function startDrawRoom(){setMode(null);MODE='draw';DRAWPTS=[];SEL=null;$('#roomPicker').style.display='none';$('#doorPicker').style.display='none';$('#drawBtns').style.display='flex';$('#mode').textContent='Disegna: tocca i vertici, poi "Chiudi forma"';render();}
function undoDraw(){if(MODE==='draw'&&DRAWPTS.length){DRAWPTS.pop();render()}}
function cancelDraw(){MODE=null;DRAWPTS=[];$('#drawBtns').style.display='none';$('#mode').textContent='';render();}
function finishDraw(){if(DRAWPTS.length<3){alert('Servono almeno 3 vertici');return}
  const r={id:uid(),name:'Stanza '+(PLAN.rooms.length+1),kind:'interna',subtype:null,poly:DRAWPTS.slice(),windows:[],doors:[]};
  clampRoom(r);PLAN.rooms.push(r);SEL=r.id;MODE=null;DRAWPTS=[];$('#drawBtns').style.display='none';$('#mode').textContent='';render();savePlan();}

function startAddRoom(){setMode(null);$('#doorPicker').style.display='none';$('#roomPicker').style.display='flex';}
function pickRoom(t){$('#roomPicker').style.display='none';
  const kind=t==='interna'?'interna':'esterna';const sub=t==='interna'?null:t;
  addRoom(null,kind,sub);
}
function cap(s){return s?s.charAt(0).toUpperCase()+s.slice(1):s}
function addRoom(name,kind,sub){
  kind=kind||'interna';sub=sub||null;
  const def=name||(kind==='interna'?('Stanza '+(PLAN.rooms.length+1)):(cap(sub)+' '+(PLAN.rooms.length+1)));
  const r={id:uid(),name:def,kind:kind,subtype:sub,x:120+PLAN.rooms.length*30,y:120+PLAN.rooms.length*24,w:220,h:160,windows:[],doors:[]};
  PLAN.rooms.push(r);SEL=r.id;render();savePlan();return r;
}
window.setRoomKind=(id,v)=>{const r=PLAN.rooms.find(x=>x.id===id);if(!r)return;
  r.kind=v==='interna'?'interna':'esterna';r.subtype=v==='interna'?null:v;render();savePlan();};

function renderRoomPanel(){
  const box=$('#roomPanel');const r=PLAN.rooms.find(x=>x.id===SEL);
  const awb=$('#addWinBtn');
  if(!r){box.innerHTML='';if(awb){awb.innerHTML='🪟 Finestra'}return}
  if(awb)awb.innerHTML=viewIcon(r)+' '+(isExt(r)?'Vista':'Finestra');
  const kv=isExt(r)?(r.subtype||'balcone'):'interna';
  const opts=[['interna','🏠 interna'],['balcone','🌿 balcone'],['terrazzo','☀️ terrazzo'],['giardino','🌳 giardino']]
    .map(([v,l])=>`<option value="${v}"${v===kv?' selected':''}>${l}</option>`).join('');
  let wins='';
  for(const w of (r.windows||[])){const e=eclInView(w);
    wins+=`<div class="card" style="margin:6px 0">
      <div class="row" style="justify-content:space-between"><b>${viewIcon(r)} ${escapeHtml(w.name)}</b><span class="mut">${compass16(w.azimuth)} · ${w.azimuth}°</span></div>
      <div>${e?'<span class="badge ok">'+e.type.split(' ')[1]+' visibile da qui</span>':'<span class="mut">nessuna eclissi da questo affaccio</span>'}</div>
      <div id="v_${w.id}"></div>
      <div class="row" style="margin-top:6px"><button class="sec" onclick="delWin('${r.id}','${w.id}')">🗑️</button></div></div>`;
  }
  box.innerHTML=`<div class="card"><div class="row" style="justify-content:space-between">
      <input value="${escapeHtml(r.name)}" onchange="renRoom('${r.id}',this.value)" style="flex:1;min-width:140px">
      <button class="sec" onclick="delRoom('${r.id}')">🗑️ Stanza</button></div>
    <div class="row" style="margin-top:8px"><span class="mut">Tipo:</span>
      <select onchange="setRoomKind('${r.id}',this.value)">${opts}</select></div>
    <div class="mut" style="margin-top:6px">Porte: ${(r.doors||[]).map(d=>d.type).join(', ')||'nessuna'}</div>
    <div style="margin-top:6px">${wins||'<span class="mut">Nessun'+(isExt(r)?' punto di osservazione':'a finestra')+' in questa stanza.</span>'}</div></div>`;
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
  LOCKED=null;LOCKEDALT=null;LIVEPITCH=null;WPHOTO=null;$('#wS3').disabled=true;$('#wName').value='';$('#wDeg').value='';$('#wAlt').value='';$('#wPname').textContent='';$('#wPrev').innerHTML='';$('#wLive').textContent='—°';$('#wLivec').textContent='';$('#wLiveAlt').textContent='—°';$('#wFov').value=66;$('#wFovHint').textContent='';
  const sel=$('#wRoom');sel.innerHTML='';for(const r of PLAN.rooms){const o=document.createElement('option');o.value=r.id;o.textContent=r.name;sel.appendChild(o)}
  if(SEL)sel.value=SEL;$('#wRoomNew').value='';
  updateWinLabels();winStep(1);$('#winModal').classList.add('on');
}
function curWinRoom(){if($('#wRoomNew').value.trim())return{kind:'interna'};return PLAN.rooms.find(x=>x.id===$('#wRoom').value)||{kind:'interna'}}
function updateWinLabels(){const ext=curWinRoom().kind==='esterna';
  $('#winTitle').textContent=ext?'Nuovo punto di osservazione':'Nuova finestra';
  $('#wNameLbl').textContent=ext?'Nome del punto':'Nome finestra';
  $('#wName').placeholder=ext?'Es. Angolo balcone / Ringhiera SO':'Es. Finestra grande / Portafinestra';
  $('#wDirLbl').textContent=ext?'Direzione (punta verso la vista / orizzonte)':'Direzione (punta verso la finestra)';
  $('#wSave').textContent=ext?'💾 Salva punto':'💾 Salva finestra';
}
function closeWin(){$('#winModal').classList.remove('on')}
function winStep(n){document.querySelectorAll('#winModal .step').forEach(s=>s.classList.toggle('on',+s.dataset.s===n));
  if(n===3)$('#wLivec').textContent=LOCKED!=null?compass16(LOCKED)+' '+LOCKED+'°':'';}
// elevazione dell'asse fotocamera (−z del device) dal suolo, valida in qualsiasi orientamento (portrait/landscape)
function camAlt(beta,gamma){const b=beta*Math.PI/180,g=gamma*Math.PI/180;let z=-Math.cos(b)*Math.cos(g);z=Math.max(-1,Math.min(1,z));return Math.round(Math.asin(z)*180/Math.PI);}
function orient(ev){let h=null;if(ev.webkitCompassHeading!=null)h=ev.webkitCompassHeading;else if(ev.absolute&&ev.alpha!=null)h=(360-ev.alpha)%360;
  if(h!=null){LIVE=Math.round(h);$('#wLive').textContent=LIVE+'°';$('#wLivec').textContent=compass16(LIVE)}
  if(ev.beta!=null){const a=(ev.gamma!=null)?camAlt(ev.beta,ev.gamma):Math.round(ev.beta-90);LIVEPITCH=Math.max(-80,Math.min(80,a));const el=$('#wLiveAlt');if(el)el.textContent=LIVEPITCH+'°'}}
async function enableCompass(){$('#wcerr').textContent='';try{
  if(typeof DeviceOrientationEvent!=='undefined'&&DeviceOrientationEvent.requestPermission){const p=await DeviceOrientationEvent.requestPermission();if(p!=='granted'){$('#wcerr').innerHTML='<span class="bad">Permesso negato</span>';return}}
  addEventListener('deviceorientationabsolute',orient,true);addEventListener('deviceorientation',orient,true);$('#wLivec').textContent='muovi a "8"…';
}catch(e){$('#wcerr').innerHTML='<span class="bad">Bussola solo su HTTPS</span>'}}
function lockHeading(){if(LIVE==null){alert('Attiva la bussola');return}LOCKED=LIVE;LOCKEDALT=(LIVEPITCH!=null?LIVEPITCH:0);$('#wLive').textContent=LOCKED+'° 🔒';$('#wLivec').textContent=compass16(LOCKED)+' · centro '+LOCKEDALT+'°';$('#wS3').disabled=false}
function useManual(){let v=parseFloat($('#wDeg').value);if(isNaN(v)){alert('Inserisci la direzione 0-360');return}LOCKED=((v%360)+360)%360;let a=parseFloat($('#wAlt').value);LOCKEDALT=isNaN(a)?0:Math.max(-80,Math.min(80,a));$('#wLive').textContent=LOCKED+'° ✍️';$('#wLivec').textContent=compass16(LOCKED)+' (manuale) · centro '+LOCKEDALT+'°';$('#wS3').disabled=false}
function readF35(buf){try{
  const dv=new DataView(buf);if(dv.getUint16(0)!==0xFFD8)return null;
  let off=2;const len=dv.byteLength;
  while(off+4<=len){
    if(dv.getUint8(off)!==0xFF)return null;const marker=dv.getUint8(off+1);
    if(marker===0xDA)return null; // inizio dati immagine
    if(marker===0x01||(marker>=0xD0&&marker<=0xD9)){off+=2;continue}
    const size=dv.getUint16(off+2);
    if(marker===0xE1){const app1=off+4;
      if(app1+6<=len&&dv.getUint32(app1)===0x45786966){ // "Exif"
        const tiff=app1+6;const little=dv.getUint16(tiff)===0x4949;
        const rd16=o=>dv.getUint16(o,little),rd32=o=>dv.getUint32(o,little);
        const ifd0=tiff+rd32(tiff+4);
        const find=(ifd,tag)=>{const n=rd16(ifd);for(let i=0;i<n;i++){const e=ifd+2+i*12;if(rd16(e)===tag)return e}return -1};
        const ep=find(ifd0,0x8769);if(ep<0)return null;
        const exif=tiff+rd32(ep+8);const te=find(exif,0xA405);if(te<0)return null; // FocalLengthIn35mmFilm
        const val=rd16(te+2)===3?rd16(te+8):rd32(te+8);return(val>0&&val<300)?val:null;
      }}
    off+=2+size;
  }
  return null;
}catch(e){return null}}
function wPhotoPick(inp){if(!inp.files[0])return;WPHOTO=inp.files[0];$('#wPname').textContent='✓';
  const url=URL.createObjectURL(WPHOTO);$('#wPrev').innerHTML='<div class="viewwrap"><img src="'+url+'"></div>';
  const img=new Image();img.onload=()=>{const land=img.naturalWidth>=img.naturalHeight;
    (WPHOTO.arrayBuffer?WPHOTO.arrayBuffer():Promise.reject()).then(buf=>{const f35=readF35(buf);
      if(f35){const sw=land?36:24;const fov=Math.round(2*Math.atan(sw/(2*f35))*180/Math.PI);
        $('#wFov').value=fov;$('#wFovHint').innerHTML='<span class="mut">FOV stimato da EXIF ('+f35+'mm eq, '+(land?'orizz.':'vert.')+'): '+fov+'° — correggibile</span>';}
      else $('#wFovHint').innerHTML='<span class="mut">EXIF assente: valore tipico 66° (o correggi a mano)</span>';
    }).catch(()=>{$('#wFovHint').innerHTML='<span class="mut">EXIF non leggibile: usa 66° o correggi a mano</span>'});
  };img.src=url;}
async function saveWindow(){
  let roomId=$('#wRoom').value;const newName=$('#wRoomNew').value.trim();
  if(newName){const r=addRoom(newName);roomId=r.id}
  const room=PLAN.rooms.find(x=>x.id===roomId);
  if(!room){alert('Scegli o crea una stanza');return}
  if(!$('#wName').value.trim()||LOCKED==null){alert('Manca nome o direzione');return}
  let photo=null;if(WPHOTO){const fd=new FormData();fd.append('file',WPHOTO);photo=(await (await fetch('api/photo',{method:'POST',body:fd})).json()).photo}
  room.windows=room.windows||[];
  const c=roomCenter(room);const fov=Math.max(20,Math.min(140,parseFloat($('#wFov').value)||66));
  room.windows.push({id:uid(),name:$('#wName').value.trim(),azimuth:LOCKED,photo_az:LOCKED,photo:photo,photo_fov:fov,alt_min:0,
    photo_alt:(LOCKEDALT!=null?LOCKEDALT:0),x:c.x,y:c.y});
  SEL=roomId;closeWin();render();savePlan();
}
// ================= CASA IN 3D (three.js) =================
let THREEREADY=false, H3={}, HHEIGHT=250;
const CX3=500, CZ3=320, WT3=8, DW3=46, WW3=66, SILL3=90, WHEAD3=210; // costanti piano→3D
function loadScript(src){return new Promise((res,rej)=>{const s=document.createElement('script');s.src=src;s.onload=res;s.onerror=()=>rej(new Error(src));document.head.appendChild(s)})}
async function ensureThree(){if(THREEREADY)return;await loadScript('vendor/three.min.js');await loadScript('vendor/GLTFLoader.js');await loadScript('vendor/OrbitControls.js');await loadScript('vendor/GLTFExporter.js');THREEREADY=true;}
function roomPts(r){return (r.poly&&r.poly.length>=3)?r.poly:[[r.x,r.y],[r.x+r.w,r.y],[r.x+r.w,r.y+r.h],[r.x,r.y+r.h]];}
function projOnSeg(p,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],L2=dx*dx+dy*dy||1;let t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/L2;t=Math.max(0,Math.min(1,t));const px=a[0]+t*dx,py=a[1]+t*dy;return {d:t*Math.sqrt(L2),len:Math.sqrt(L2),dist:Math.hypot(p[0]-px,p[1]-py)};}
async function openHouse3D(){$('#house3dModal').classList.add('on');const box=$('#house3dBox');box.innerHTML='<div class="mut" style="padding:20px">Carico il motore 3D…</div>';
  try{await ensureThree()}catch(e){box.innerHTML='<span class="bad" style="padding:20px;display:block">Impossibile caricare il motore 3D (vendor mancante).</span>';return}
  buildHouse3D();}
function closeHouse3D(){H3.run=false;if(H3.animId)cancelAnimationFrame(H3.animId);if(H3.onResize)removeEventListener('resize',H3.onResize);if(H3.renderer){try{H3.renderer.dispose();H3.renderer.forceContextLoss&&H3.renderer.forceContextLoss()}catch(e){}}H3={};$('#house3dBox').innerHTML='';$('#house3dModal').classList.remove('on');}
window.setH3Height=(v)=>{HHEIGHT=+v;if(H3.run)buildHouse3D();};
function buildHouse3D(){
  H3.run=false;if(H3.animId)cancelAnimationFrame(H3.animId);
  const box=$('#house3dBox');box.innerHTML='';
  const W=box.clientWidth||800, Hh=box.clientHeight||500;
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x0b0f14);
  const grp=new THREE.Group();scene.add(grp);
  scene.add(new THREE.HemisphereLight(0xffffff,0x30363d,0.95));
  const dl=new THREE.DirectionalLight(0xffffff,0.7);dl.position.set(250,450,180);scene.add(dl);
  grp.add(new THREE.GridHelper(1200,24,0x223047,0x1a2130));
  const wallMat=new THREE.MeshStandardMaterial({color:0x9aa4b0,roughness:.95,metalness:0,side:THREE.DoubleSide});
  const H=HHEIGHT;
  function wallBox(p0,p1,y0,y1){const ax=p0[0]-CX3,az=p0[1]-CZ3,bx=p1[0]-CX3,bz=p1[1]-CZ3;const len=Math.hypot(bx-ax,bz-az);if(len<0.6||y1-y0<0.6)return;
    const m=new THREE.Mesh(new THREE.BoxGeometry(len,y1-y0,WT3),wallMat);m.position.set((ax+bx)/2,(y0+y1)/2,(az+bz)/2);m.rotation.y=-Math.atan2(bz-az,bx-ax);grp.add(m);}
  let nRooms=0,nWin=0,nDoor=0,nFurn=0;
  for(const r of (PLAN.rooms||[])){nRooms++;const pts=roomPts(r);const ext=isExt(r);
    // pavimento
    const shape=new THREE.Shape(pts.map(p=>new THREE.Vector2(p[0]-CX3,-(p[1]-CZ3))));
    const fgeo=new THREE.ShapeGeometry(shape);fgeo.rotateX(-Math.PI/2);
    grp.add(new THREE.Mesh(fgeo,new THREE.MeshStandardMaterial({color:ext?0x1c3b2a:0x18314f,roughness:1,side:THREE.DoubleSide})));
    // assegna aperture (porte/finestre) al lato più vicino
    const es=[];for(let i=0;i<pts.length;i++)es.push([pts[i],pts[(i+1)%pts.length]]);
    const byEdge=es.map(()=>[]);
    const cen=roomCenter(r);
    for(const d of (r.doors||[])){let bi=0,bd=1e9,bp=0,bl=0;es.forEach((e,i)=>{const pr=projOnSeg([d.x,d.y],e[0],e[1]);if(pr.dist<bd){bd=pr.dist;bi=i;bp=pr.d;bl=pr.len}});byEdge[bi].push({d:bp,len:bl,type:'door'});nDoor++;}
    for(const w of (r.windows||[])){const wx=w.x!=null?w.x:cen.x,wy=w.y!=null?w.y:cen.y;let bi=0,bd=1e9,bp=0,bl=0;es.forEach((e,i)=>{const pr=projOnSeg([wx,wy],e[0],e[1]);if(pr.dist<bd){bd=pr.dist;bi=i;bp=pr.d;bl=pr.len}});byEdge[bi].push({d:bp,len:bl,type:'window'});nWin++;}
    // muri con vani
    es.forEach((e,i)=>{const a=e[0],b=e[1];const L=Math.hypot(b[0]-a[0],b[1]-a[1]);if(L<1)return;const ux=(b[0]-a[0])/L,uy=(b[1]-a[1])/L;const pAt=dd=>[a[0]+ux*dd,a[1]+uy*dd];
      const ops=byEdge[i].slice().sort((x,y)=>x.d-y.d);let cur=0;
      for(const op of ops){const half=(op.type==='window'?WW3:DW3)/2;const s=op.d-half,e2=op.d+half;
        if(s>cur)wallBox(pAt(cur),pAt(Math.max(cur,s)),0,H);
        const q0=pAt(Math.max(0,s)),q1=pAt(Math.min(L,e2));
        if(op.type==='window'){wallBox(q0,q1,0,SILL3);wallBox(q0,q1,Math.min(WHEAD3,H),H);}
        cur=Math.max(cur,e2);}
      if(cur<L)wallBox(pAt(cur),pAt(L),0,H);
    });
  }
  // mobili con modello .glb (gli altri sono nascosti per scelta)
  const loader=new THREE.GLTFLoader();
  for(const f of (PLAN.furniture||[])){const t=(PLAN.templates||[]).find(x=>x.id===f.tpl);if(!t||!t.model)continue;nFurn++;
    loader.load('models/'+t.model,(gltf)=>{const obj=gltf.scene;const b=new THREE.Box3().setFromObject(obj);const sz=b.getSize(new THREE.Vector3());
      const sc=Math.min((f.w||t.w)/(sz.x||1),(f.h||t.h)/(sz.z||1));obj.scale.setScalar(sc);
      const b2=new THREE.Box3().setFromObject(obj);const c2=b2.getCenter(new THREE.Vector3());
      obj.position.x-=c2.x;obj.position.z-=c2.z;obj.position.y-=b2.min.y;
      const piv=new THREE.Group();piv.add(obj);piv.position.set(f.x-CX3,0,f.y-CZ3);piv.rotation.y=-(f.rot||0)*Math.PI/180;grp.add(piv);
    },undefined,(err)=>{console.warn('glb load fail',t.model,err)});
  }
  // camera + controlli
  const cam=new THREE.PerspectiveCamera(55,W/Hh,1,6000);cam.position.set(0,H*2.6,760);
  const rnd=new THREE.WebGLRenderer({antialias:true});rnd.setPixelRatio(Math.min(devicePixelRatio,2));rnd.setSize(W,Hh);box.appendChild(rnd.domElement);
  const ctrl=new THREE.OrbitControls(cam,rnd.domElement);ctrl.target.set(0,40,0);ctrl.enableDamping=true;ctrl.update();
  const onResize=()=>{const w2=box.clientWidth,h2=box.clientHeight;if(!w2||!h2)return;cam.aspect=w2/h2;cam.updateProjectionMatrix();rnd.setSize(w2,h2)};
  addEventListener('resize',onResize);
  $('#house3dInfo').textContent=`${nRooms} stanze · ${nWin} finestre · ${nDoor} porte · ${nFurn} mobili 3D`+((nFurn===0)?' (nessun mobile ha un modello .glb)':'');
  H3={run:true,renderer:rnd,controls:ctrl,onResize,scene,grp};
  (function loop(){if(!H3.run)return;H3.animId=requestAnimationFrame(loop);ctrl.update();rnd.render(scene,cam)})();
}
function exportGLB(){if(!H3.grp){alert('Apri prima la vista 3D');return}
  try{const ex=new THREE.GLTFExporter();ex.parse(H3.grp,(res)=>{downloadBlob(new Blob([res],{type:'model/gltf-binary'}),'casa.glb');},{binary:true});}
  catch(e){alert('Export 3D non riuscito');}
}

// ================= EXPORT 2D (PNG / SVG) =================
const EXPORT_VARS='--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#f0a500;--ok:#3fb950;--bad:#f85149;--d-int:#58a6ff;--d-bal:#3fb950;--d-est:#d29922;--d-main:#f85149';
function toggleExport(){const el=$('#exportPicker');el.style.display=el.style.display==='flex'?'none':'flex';}
function downloadBlob(blob,name){const u=URL.createObjectURL(blob);const a=document.createElement('a');a.href=u;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),3000);}
function planSVGString(){const clone=SVG.cloneNode(true);
  clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width','1000');clone.setAttribute('height','640');clone.removeAttribute('style');
  clone.setAttribute('style',EXPORT_VARS+';background:#0b0f14');
  return '<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(clone);}
function exportSVG(){downloadBlob(new Blob([planSVGString()],{type:'image/svg+xml'}),'planimetria.svg');}
function exportPNG(){const data=planSVGString();const img=new Image();
  img.onload=()=>{const c=document.createElement('canvas');c.width=2000;c.height=1280;const ctx=c.getContext('2d');ctx.fillStyle='#0b0f14';ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(img,0,0,c.width,c.height);
    c.toBlob(b=>{if(b)downloadBlob(b,'planimetria.png');else alert('PNG non riuscito')},'image/png');};
  img.onerror=()=>alert('PNG non riuscito');
  img.src='data:image/svg+xml;base64,'+btoa(unescape(encodeURIComponent(data)));}
boot();
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
