import os, json, uuid, urllib.request
import datetime as dt
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
import astronomy

DATA = "/data"; PHOTOS = os.path.join(DATA, "photos"); ROOMS_FILE = os.path.join(DATA, "rooms.json")
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
    return {"type": "Eclissi Solare", "body": "sun", "kind": kname(e.kind),
            "obscuration": round((e.obscuration or 0)*100, 1),
            "peak_utc": e.peak.time.Utc().replace(tzinfo=dt.timezone.utc).isoformat(),
            "azimuth": round(az, 1), "compass": compass16(az), "altitude": round(e.peak.altitude, 1),
            "visible": e.peak.altitude > 0}

def next_lunar(obs):
    e = astronomy.SearchLunarEclipse(astronomy.Time.Now())
    az, alt = horiz(astronomy.Body.Moon, e.peak, obs)
    return {"type": "Eclissi Lunare", "body": "moon", "kind": kname(e.kind),
            "obscuration": round((getattr(e, "obscuration", 0) or 0)*100, 1),
            "peak_utc": e.peak.Utc().replace(tzinfo=dt.timezone.utc).isoformat(),
            "azimuth": round(az, 1), "compass": compass16(az), "altitude": round(alt, 1),
            "visible": alt > 0}

def load_rooms():
    try: return json.load(open(ROOMS_FILE))
    except Exception: return []
def save_rooms(r): json.dump(r, open(ROOMS_FILE, "w"), indent=2)

@app.get("/api/config")
def api_config(): return get_location()

@app.get("/api/eclipse")
def api_eclipse():
    loc = get_location()
    if loc["latitude"] is None: raise HTTPException(400, "Coordinate casa non impostate in HA")
    obs = astronomy.Observer(loc["latitude"], loc["longitude"], loc["elevation"])
    out = {"location": loc, "solar": None, "lunar": None}
    for k, fn in (("solar", next_solar), ("lunar", next_lunar)):
        try: out[k] = fn(obs)
        except Exception as ex: out[k] = {"error": str(ex)}
    return out

@app.get("/api/rooms")
def api_rooms(): return load_rooms()

@app.post("/api/rooms")
async def api_add_room(name: str = Form(...), azimuth: float = Form(...),
                       alt_min: float = Form(0.0), photo_fov: float = Form(66.0),
                       file: UploadFile = File(None)):
    rooms = load_rooms(); rid = uuid.uuid4().hex[:8]
    photo = None
    if file is not None:
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"): ext = ".jpg"
        photo = f"{rid}{ext}"
        with open(os.path.join(PHOTOS, photo), "wb") as f: f.write(await file.read())
    rooms.append({"id": rid, "name": name, "azimuth": round(float(azimuth) % 360, 1),
                  "alt_min": float(alt_min), "photo": photo,
                  "photo_az": round(float(azimuth) % 360, 1), "photo_fov": float(photo_fov)})
    save_rooms(rooms); return {"id": rid}

@app.delete("/api/rooms/{rid}")
def api_del_room(rid: str):
    save_rooms([r for r in load_rooms() if r["id"] != rid]); return {"ok": True}

@app.get("/photos/{fn}")
def get_photo(fn: str):
    p = os.path.join(PHOTOS, os.path.basename(fn))
    if not os.path.exists(p): raise HTTPException(404, "not found")
    return FileResponse(p)

@app.get("/", response_class=HTMLResponse)
def index(): return HTML

HTML = r"""<!doctype html><html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Eclipse Finder</title><style>
:root{--bg:#0d1117;--card:#161b22;--bd:#30363d;--fg:#e6edf3;--mut:#8b949e;--acc:#f0a500;--ok:#3fb950;--bad:#f85149}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--fg);padding:14px;max-width:840px;margin:auto}
h1{font-size:1.4rem;margin:.2rem 0 .8rem}h2{font-size:1.05rem;margin:1.1rem 0 .5rem;color:var(--acc)}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px;margin-bottom:12px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.badge{padding:2px 8px;border-radius:20px;font-size:.75rem;font-weight:600}
.ok{background:rgba(63,185,80,.15);color:var(--ok)}.bad{background:rgba(248,81,73,.15);color:var(--bad)}
.mut{color:var(--mut);font-size:.85rem}small{color:var(--mut)}
button{background:var(--acc);color:#111;border:0;border-radius:8px;padding:10px 14px;font-weight:700;cursor:pointer;font-size:.9rem}
button:disabled{opacity:.4}button.sec{background:transparent;color:var(--fg);border:1px solid var(--bd)}
input{background:#0d1117;border:1px solid var(--bd);color:var(--fg);border-radius:8px;padding:10px;font-size:.95rem;width:100%}
.big{font-size:1.6rem;font-weight:800}.dir{font-size:2.2rem;font-weight:800;color:var(--acc)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:560px){.grid{grid-template-columns:1fr}}
.viewwrap{position:relative;display:inline-block;max-width:100%;margin-top:8px}
.viewwrap img{max-width:100%;border-radius:8px;display:block}
.sun{position:absolute;width:46px;height:46px;transform:translate(-50%,-50%);pointer-events:none;filter:drop-shadow(0 0 6px rgba(0,0,0,.6))}
.step{display:none}.step.on{display:block}
.livehdg{font-size:2.6rem;font-weight:800;color:var(--acc);text-align:center}
.rose{display:block;margin:0 auto}
.cardrow{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}
</style></head><body>
<h1>🌒 Eclipse Finder</h1>
<div id="loc" class="mut">Carico…</div>
<h2>Prossima eclissi</h2>
<div id="eclipse" class="grid"></div>

<h2>Le mie finestre / balconi</h2>
<button id="startWiz">➕ Aggiungi finestra (guidato)</button>

<div id="wiz" class="card" style="display:none;margin-top:10px">
  <!-- STEP 1 -->
  <div class="step on" data-step="1">
    <b>1 · Che finestra è?</b>
    <div style="margin-top:8px"><input id="wname" placeholder="Es. Balcone soggiorno"></div>
    <div class="row" style="margin-top:10px;justify-content:flex-end"><button class="sec" onclick="wizCancel()">Annulla</button><button onclick="wizGo(2)">Avanti →</button></div>
  </div>
  <!-- STEP 2 -->
  <div class="step" data-step="2">
    <b>2 · Punta il telefono verso la finestra</b>
    <div class="livehdg" id="live">—°</div>
    <div class="mut" style="text-align:center" id="livec">tocca "Attiva bussola" e muovi il telefono a "8" per calibrare</div>
    <div class="row" style="margin-top:10px"><button class="sec" onclick="enableCompass()">🧭 Attiva bussola</button>
      <button id="lockBtn" onclick="lockHeading()">🔒 Blocca direzione</button></div>
    <div id="cerr" class="mut"></div>
    <div class="mut" style="text-align:center;margin:10px 0 6px">— oppure inserisci i gradi a mano (PC/senza bussola) —</div>
    <div class="row"><input id="manualDeg" type="number" min="0" max="360" step="1" placeholder="0–360 (es. 126 = SE)" style="flex:1;min-width:120px">
      <button class="sec" onclick="useManual()">Usa questi gradi</button></div>
    <div class="row" style="margin-top:12px;justify-content:space-between"><button class="sec" onclick="wizGo(1)">← Indietro</button><button id="s2next" disabled onclick="wizGo(3)">Avanti →</button></div>
  </div>
  <!-- STEP 3 -->
  <div class="step" data-step="3">
    <b>3 · Scatta una foto della vista</b>
    <div class="mut">Punta nella stessa direzione (${'${}'}) e scatta.</div>
    <div style="margin-top:8px"><label class="sec" style="padding:12px;border:1px solid var(--bd);border-radius:8px;cursor:pointer;display:inline-block">📷 Scatta / scegli foto
      <input id="wphoto" type="file" accept="image/*" capture="environment" style="display:none" onchange="photoPicked(this)"></label>
      <span id="pname" class="mut"></span></div>
    <div id="ppreview"></div>
    <div class="row" style="margin-top:10px;justify-content:space-between"><button class="sec" onclick="wizGo(2)">← Indietro</button><button id="saveBtn" onclick="wizSave()">💾 Salva finestra</button></div>
  </div>
</div>

<div id="rooms" style="margin-top:12px"></div>

<script>
const $=s=>document.querySelector(s);
let ECL=null, LIVE=null, LOCKED=null, PHOTOFILE=null;
function fmtLocal(iso){try{return new Date(iso).toLocaleString('it-IT',{dateStyle:'medium',timeStyle:'short'})}catch(e){return iso}}
function angdiff(a,b){return ((a-b+540)%360)-180}
function compass16(az){const d=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"];return d[Math.round((az%360)/22.5)%16]}
function polar(cx,cy,r,az){const a=(az-90)*Math.PI/180;return [cx+r*Math.cos(a), cy+r*Math.sin(a)]}

async function loadEclipse(){
  const d=await (await fetch('api/eclipse')).json();
  if(d.detail){$('#loc').innerHTML='<span class="bad">'+d.detail+'</span>';return}
  ECL=d; $('#loc').innerHTML='📍 '+d.location.location_name+' — '+d.location.latitude.toFixed(4)+', '+d.location.longitude.toFixed(4);
  const box=$('#eclipse');box.innerHTML='';
  for(const key of ['solar','lunar']){const e=d[key];const c=document.createElement('div');c.className='card';
    if(!e||e.error){c.innerHTML='<b>'+(key=='solar'?'Solare':'Lunare')+'</b><div class="mut">'+(e?e.error:'n/d')+'</div>';box.appendChild(c);continue}
    c.innerHTML=`<div class="row" style="justify-content:space-between"><b>${e.type}</b><span class="badge ${e.visible?'ok':'bad'}">${e.visible?'Visibile':'Non visibile'}</span></div>
      <div style="margin:6px 0"><span class="badge" style="background:rgba(240,165,0,.15);color:var(--acc)">${e.kind}</span> <span class="mut">· oscur. ${e.obscuration}%</span></div>
      <div class="big">${fmtLocal(e.peak_utc)}</div>
      <div class="row" style="margin-top:6px"><div><div class="dir">${e.compass}</div><small>az ${e.azimuth}°</small></div>
      <div style="margin-left:auto;text-align:right"><div class="big">${e.altitude}°</div><small>altezza</small></div></div>`;
    box.appendChild(c);}
  renderRooms();
}

// ---- Wizard ----
$('#startWiz').onclick=()=>{$('#wiz').style.display='block';$('#startWiz').style.display='none';wizGo(1);$('#wname').value='';LOCKED=null;PHOTOFILE=null;$('#s2next').disabled=true;$('#pname').textContent='';$('#ppreview').innerHTML='';};
function wizCancel(){$('#wiz').style.display='none';$('#startWiz').style.display='inline-block';}
function wizGo(n){
  if(n>=2 && !$('#wname').value.trim()){alert('Scrivi un nome');return}
  document.querySelectorAll('.step').forEach(s=>s.classList.toggle('on', +s.dataset.step===n));
  if(n===3){document.querySelector('[data-step="3"] .mut').textContent='Punta nella stessa direzione ('+(LOCKED!=null?compass16(LOCKED)+' '+LOCKED+'°':'')+') e scatta.';}
}
function orient(ev){let h=null;
  if(ev.webkitCompassHeading!=null)h=ev.webkitCompassHeading;
  else if(ev.absolute&&ev.alpha!=null)h=(360-ev.alpha)%360;
  if(h!=null){LIVE=Math.round(h);$('#live').textContent=LIVE+'°';$('#livec').textContent=compass16(LIVE);}}
async function enableCompass(){$('#cerr').textContent='';try{
  if(typeof DeviceOrientationEvent!=='undefined'&&DeviceOrientationEvent.requestPermission){const p=await DeviceOrientationEvent.requestPermission();if(p!=='granted'){$('#cerr').innerHTML='<span class="bad">Permesso negato</span>';return}}
  window.addEventListener('deviceorientationabsolute',orient,true);window.addEventListener('deviceorientation',orient,true);
  $('#livec').textContent='muovi a "8" per calibrare…';
}catch(e){$('#cerr').innerHTML='<span class="bad">Bussola non disponibile (serve HTTPS)</span>'}}
function lockHeading(){if(LIVE==null){alert('Prima attiva la bussola');return}LOCKED=LIVE;$('#live').textContent=LOCKED+'° 🔒';$('#livec').textContent='Direzione bloccata: '+compass16(LOCKED);$('#s2next').disabled=false;}
function useManual(){let v=parseFloat($('#manualDeg').value);if(isNaN(v)){alert('Inserisci i gradi (0-360)');return}LOCKED=((v%360)+360)%360;$('#live').textContent=LOCKED+'° ✍️';$('#livec').textContent=compass16(LOCKED)+' (manuale)';$('#s2next').disabled=false;}
function photoPicked(inp){if(!inp.files[0])return;PHOTOFILE=inp.files[0];$('#pname').textContent='✓ '+PHOTOFILE.name;
  const u=URL.createObjectURL(PHOTOFILE);$('#ppreview').innerHTML='<div class="viewwrap"><img src="'+u+'"></div>';}
async function wizSave(){
  const name=$('#wname').value.trim();if(!name||LOCKED==null){alert('Manca nome o direzione');return}
  const fd=new FormData();fd.append('name',name);fd.append('azimuth',LOCKED);
  if(PHOTOFILE)fd.append('file',PHOTOFILE);
  $('#saveBtn').disabled=true;
  await fetch('api/rooms',{method:'POST',body:fd});
  $('#saveBtn').disabled=false;wizCancel();renderRooms();
}

// ---- Render finestre: mappa bussola + foto con eclissi ----
function bestEclipseFor(r){let t=null,bd=1e9;for(const k of['solar','lunar']){const e=ECL&&ECL[k];if(!e||!e.visible)continue;const dh=Math.abs(angdiff(e.azimuth,r.azimuth));if(dh<bd){bd=dh;t=e;}}return t;}
function roseSVG(r,ecl){
  const S=150,cx=75,cy=75,R=62,fov=r.photo_fov||66;
  const [wx,wy]=polar(cx,cy,R,r.azimuth);
  const a1=(r.azimuth-fov/2-90)*Math.PI/180,a2=(r.azimuth+fov/2-90)*Math.PI/180;
  const wedge=`M${cx},${cy} L${cx+R*Math.cos(a1)},${cy+R*Math.sin(a1)} A${R},${R} 0 0 1 ${cx+R*Math.cos(a2)},${cy+R*Math.sin(a2)} Z`;
  let sun='';let inview=false;
  if(ecl){const [sx,sy]=polar(cx,cy,R-10,ecl.azimuth);const dh=angdiff(ecl.azimuth,r.azimuth);inview=Math.abs(dh)<=fov/2;
    sun=`<circle cx="${sx}" cy="${sy}" r="9" fill="${ecl.body=='sun'?'#ffd24a':'#cfd8e3'}" stroke="#f0a500" stroke-width="1.5"/>`;}
  const lbl=(t,az)=>{const[x,y]=polar(cx,cy,R+9,az);return`<text x="${x}" y="${y}" fill="#8b949e" font-size="10" text-anchor="middle" dominant-baseline="middle">${t}</text>`};
  return `<svg class="rose" width="${S}" height="${S}" viewBox="0 0 ${S} ${S}">
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="#30363d"/>
    <path d="${wedge}" fill="rgba(240,165,0,.18)" stroke="rgba(240,165,0,.5)"/>
    <line x1="${cx}" y1="${cy}" x2="${wx}" y2="${wy}" stroke="#f0a500" stroke-width="2"/>
    ${lbl('N',0)}${lbl('E',90)}${lbl('S',180)}${lbl('O',270)}${sun}
    <circle cx="${cx}" cy="${cy}" r="3" fill="#e6edf3"/></svg>
    <div class="mut" style="text-align:center">${inview?'<span class="badge ok">eclissi in questo affaccio</span>':'eclissi fuori affaccio'}</div>`;
}
async function renderRooms(){
  const rooms=await (await fetch('api/rooms')).json();const box=$('#rooms');box.innerHTML='';
  if(!rooms.length){box.innerHTML='<div class="mut">Nessuna finestra. Usa "Aggiungi finestra".</div>';return}
  for(const r of rooms){const ecl=bestEclipseFor(r);const c=document.createElement('div');c.className='card';
    c.innerHTML=`<div class="row" style="justify-content:space-between"><b>${r.name}</b><span class="mut">${compass16(r.azimuth)} · ${r.azimuth}°</span></div>
      <div class="cardrow" style="margin-top:8px">
        <div>${roseSVG(r,ecl)}</div>
        <div style="flex:1;min-width:200px"><div id="view_${r.id}"></div></div>
      </div>
      <div class="row" style="margin-top:8px"><button class="sec" onclick="delRoom('${r.id}')">🗑️ Elimina</button></div>`;
    box.appendChild(c);
    const v=document.getElementById('view_'+r.id);
    if(r.photo){v.innerHTML=`<div class="viewwrap"><img src="photos/${r.photo}?v=${Date.now()}" onload="placeSun('${r.id}',this,${r.azimuth},${r.photo_az},${r.photo_fov})"><div id="sun_${r.id}" class="sun" style="display:none">${sunSVG()}</div></div><small id="hint_${r.id}"></small>`;}
    else{v.innerHTML='<span class="mut">Nessuna foto per questa finestra.</span>';}
  }
}
function sunSVG(){return `<svg viewBox="0 0 46 46"><circle cx="23" cy="23" r="19" fill="#ffd24a" stroke="#f0a500" stroke-width="2"/><circle cx="31" cy="18" r="17" fill="rgba(13,17,23,.82)"/></svg>`}
window.placeSun=(rid,img,az,paz,fov)=>{
  const ecl=bestEclipseFor({azimuth:az});const sun=document.getElementById('sun_'+rid),hint=document.getElementById('hint_'+rid);
  if(!ecl){hint.textContent='Nessuna eclissi visibile da qui.';return}
  const center=(paz!=null?paz:az);const dh=angdiff(ecl.azimuth,center);
  if(Math.abs(dh)>fov/2){sun.style.display='none';hint.textContent=`Fuori inquadratura: ruota verso ${ecl.compass} (${dh>0?'destra':'sinistra'}).`;return}
  const fovV=fov*(img.clientHeight/img.clientWidth),centerAlt=15;
  const x=0.5+dh/fov,y=Math.max(0,Math.min(1,0.5-(ecl.altitude-centerAlt)/fovV));
  sun.style.left=(x*100)+'%';sun.style.top=(y*100)+'%';sun.style.display='block';
  hint.textContent=`${ecl.type} · ${ecl.compass} ${ecl.azimuth}° · alt ${ecl.altitude}° (posizione stimata)`;
};
window.delRoom=async(rid)=>{if(confirm('Eliminare?')){await fetch('api/rooms/'+rid,{method:'DELETE'});renderRooms();}};
loadEclipse();
</script></body></html>"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8099)
