
"use strict";
/* ===========================================================================
   MIRAI Mission Control — the console
   Talks only to its own origin. Every call goes through api(), which unwraps
   {ok:...} and raises the server's own message, so a failure is never silent.
   =========================================================================== */
const $  = (s, r=document) => r.querySelector(s);
const $$ = (s, r=document) => Array.from(r.querySelectorAll(s));
const esc = s => String(s==null?"":s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nf = n => (n==null||n==="")?"—":Number(n).toLocaleString();
const ago = t => { if(!t) return "—"; const s=Math.max(0,(Date.now()/1000)-Number(t));
  if(s<60)return Math.round(s)+"s ago"; if(s<3600)return Math.round(s/60)+"m ago";
  if(s<86400)return Math.round(s/3600)+"h ago"; return Math.round(s/86400)+"d ago"; };

let STATE = { settings:{}, agents:[], missions:[], health:null, greeting:null };
const I18N = {
  id: {
    "nav.cockpit":"Status","nav.agents":"Sepuluh kursi","nav.deploy":"Pasang agen","nav.city":"Kota agen",
    "nav.missions":"Misi","nav.chat":"Obrolan","nav.docs":"Dokumen","nav.schedule":"Jadwal",
    "nav.health":"Kesehatan","nav.files":"Berkas","nav.terminal":"Terminal","nav.voice":"Suara",
    "nav.hand":"Mode tangan","nav.integrations":"Integrasi","nav.settings":"Pengaturan",
    "grp.fleet":"Rumah","grp.work":"Jejak","grp.machine":"Mesin",
    "kpi.ready":"Agen siap","empty.agents":"belum ada persona di mesin ini","stat.sessions":"sesi hari ini",
    "lang.id":"ID","lang.en":"EN"
  },
  en: {
    "nav.cockpit":"Status","nav.agents":"Ten seats","nav.deploy":"Deploy agent","nav.city":"Agent City",
    "nav.missions":"Missions","nav.chat":"Chat","nav.docs":"Docs","nav.schedule":"Schedule",
    "nav.health":"Health","nav.files":"Files","nav.terminal":"Terminal","nav.voice":"Voice",
    "nav.hand":"Hand mode","nav.integrations":"Integrations","nav.settings":"Settings",
    "grp.fleet":"House","grp.work":"Trace","grp.machine":"Machine",
    "kpi.ready":"Agents ready","empty.agents":"no profiles on this machine yet","stat.sessions":"sessions today",
    "lang.id":"ID","lang.en":"EN"
  }
};
let LANG = localStorage.getItem("mirai.lang") || "id";
if(LANG!=="id" && LANG!=="en") LANG="id";
function t(k){ const pack=I18N[LANG]||I18N.id; return (pack[k]||I18N.en[k]||k); }
function setLang(next){
  LANG = next==="en" ? "en" : "id";
  localStorage.setItem("mirai.lang", LANG);
  document.documentElement.lang = LANG;
  location.reload();
}

function toast(msg, ok=true){
  const box=$("#toast"), el=document.createElement("div");
  el.className = ok?"":"bad"; el.textContent=msg; box.appendChild(el);
  setTimeout(()=>el.remove(), ok?4200:8000);
}

async function api(path, opts={}){
  const init = {headers:{"Content-Type":"application/json"}, ...opts};
  if(init.body && typeof init.body!=="string") init.body=JSON.stringify(init.body);
  const r = await fetch(path, init);
  let j=null; try{ j=await r.json(); }catch(e){ /* non-JSON: fall through */ }
  if(!j) throw new Error(`${path} → ${r.status} and no JSON body`);
  if(j.ok===false) throw new Error(j.error || `request failed (${r.status})`);
  return j;
}

/* ---------------------------------------------------------------------------
   Pages. One render function per surface; nav is built from this list, so a
   page that exists is reachable and a page that does not is not faked.
   --------------------------------------------------------------------------- */
const PAGES = [
  {id:"cockpit",   labelKey:"nav.cockpit",      glyph:"\u25c6", groupKey:"grp.fleet"},
  {id:"agents",    labelKey:"nav.agents",       glyph:"\u25cf", groupKey:"grp.fleet"},
  {id:"deploy",    labelKey:"nav.deploy",       glyph:"+",        groupKey:"grp.fleet", hidden:true},
  {id:"city",      labelKey:"nav.city",         glyph:"\u25a6", groupKey:"grp.fleet", hidden:true},
  {id:"missions",  labelKey:"nav.missions",     glyph:"\u25ce", groupKey:"grp.work", hidden:true},
  {id:"chat",      labelKey:"nav.chat",         glyph:"\u2709", groupKey:"grp.work"},
  {id:"docs",      labelKey:"nav.docs",         glyph:"\u25a4", groupKey:"grp.work", hidden:true},
  {id:"schedule",  labelKey:"nav.schedule",     glyph:"\u25f7", groupKey:"grp.work"},
  {id:"health",    labelKey:"nav.health",       glyph:"\u2318", groupKey:"grp.machine"},
  {id:"files",     labelKey:"nav.files",        glyph:"\u25a3", groupKey:"grp.machine"},
  {id:"terminal",  labelKey:"nav.terminal",     glyph:"\u25b7", groupKey:"grp.machine", hidden:true},
  {id:"voice",     labelKey:"nav.voice",        glyph:"\u25cd", groupKey:"grp.machine", hidden:true},
  {id:"hand",      labelKey:"nav.hand",         glyph:"\u2733", groupKey:"grp.machine", hidden:true},
  {id:"integrations", labelKey:"nav.integrations", glyph:"\u25c7", groupKey:"grp.machine"},
  {id:"settings",  labelKey:"nav.settings",     glyph:"\u2699", groupKey:"grp.machine"},
];

function buildShell(){
  const nav=$("#nav"); let last="";
  for(const p of PAGES){
    if(p.hidden) continue;
    const grp=t(p.groupKey||"grp.fleet");
    if(grp!==last){ const d=document.createElement("div"); d.className="sep"; d.textContent=grp; nav.appendChild(d); last=grp; }
    const b=document.createElement("button"); b.id="nav-"+p.id;
    b.innerHTML = `<span class="g" aria-hidden="true">${p.glyph||"\u00b7"}</span><span>${t(p.labelKey)}</span>`;
    b.onclick=()=>show(p.id); nav.appendChild(b);
  }
  const pages=$("#pages");
  for(const p of PAGES){
    const el=document.createElement("section");
    el.className="page"; el.id="page-"+p.id;
    el.innerHTML = `<div id="body-${p.id}"><p class="empty">${LANG==="en"?"loading…":"memuat…"}</p></div>`;
    pages.appendChild(el);
  }
}
let CURRENT=null;
function show(id){
  CURRENT=id;
  $$("#nav button").forEach(b=>b.classList.toggle("on", b.id==="nav-"+id));
  $$(".page").forEach(s=>s.classList.toggle("on", s.id==="page-"+id));
  const first=!RENDERED.has(id); RENDERED.add(id);
  const fn=RENDERERS[id];
  if(fn) fn({first});
}
const RENDERED=new Set();
const RENDERERS={};

/* Helpers shared by the pages. */
function body(id, html){ $("#body-"+id).innerHTML = html; }
function fail(id, err){
  body(id, `<div class="notice bad"><b>${esc(err.message||err)}</b>
    <div class="sub" style="margin-top:6px">Halaman ini butuh layanan MIRAI. Cek
    <code>/api/ping</code> dan log di ~/mirai/data/mission-control.err.log.</div></div>`);
}
const statusPill = s => {
  const k = /ready|done|delivered|running|live|ok/i.test(s)?"good"
          : /strain|review|paused|waiting|needs/i.test(s)?"warn" : "bad";
  return `<span class="pill ${k}">${esc(s||"—")}</span>`;
};

async function refreshHeader(){
  try{
    const [s,g] = await Promise.all([api("/api/settings"), api("/api/greeting").catch(()=>null)]);
    STATE.settings = s.settings||{}; STATE.greeting = g;
    const name = STATE.settings.display_name || STATE.settings.operator_name || "operator";
    const line = (g && (g.text||g.greeting)) || (LANG==='en' ? `MIRAI is up, ${name}.` : `MIRAI hidup, ${name}.`);
    $("#hello").innerHTML = `${esc(line)}`;
    $("#tzlabel").textContent = STATE.settings.timezone || "UTC";
  }catch(e){ $("#hello").innerHTML = `<span class="dot bad"></span> ${LANG==="en"?"backend unreachable":"layanan tidak terjangkau"}`; }
  tickClock();
}
function tickClock(){
  const tz = STATE.settings.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  try{
    $("#clock").textContent = new Intl.DateTimeFormat("en-GB",
      {timeZone:tz, hour:"2-digit", minute:"2-digit"}).format(new Date());
    $("#tzlabel").textContent = tz;
  }catch(e){ $("#clock").textContent = new Date().toTimeString().slice(0,5); }
}
setInterval(tickClock, 15000);

/* ----------------------------- Cockpit ----------------------------------- */
RENDERERS.cockpit = async () => {
  const id="cockpit";
  try{
    const [house, agents, health] = await Promise.all([
      api("/api/house"), api("/api/agents").catch(()=>({agents:[]})), api("/api/health").catch(()=>null)]);
    STATE.house=house; STATE.agents=agents.agents||[]; STATE.health=health;
    railFoot(agents);
    const w=house.wiki||{}, c=house.cron||{}, g=house.gateway||{}, seats=house.seats||[];
    const cronOk=(c.present||0)+" / "+(c.wanted||5);
    const wikiLine = w.exists
      ? (w.alive ? "detak "+ago(Date.now()/1000-(w.heartbeat_s||0)) : "folder ada, detak tidak segar")
      : "folder belum ada di jalur yang diharapkan";
    const seatMosaic = seats.map(s=>mosaicTile(s)).join("");
    const cronRows=(c.jobs||[]).map(j=>`<tr>
      <td class="mono">${esc(j.name)}</td><td class="sub">${esc(j.when)}</td>
      <td>${j.present?'<span class="pill good">ada</span>':'<span class="pill warn">tidak terlihat</span>'}</td>
    </tr>`).join("");
    const forbid=(c.forbidden_live||[]).length
      ? `<div class="notice bad">Job yang tidak boleh hidup: ${esc((c.forbidden_live||[]).join(", "))}</div>` : "";
    body(id, `
      <section class="hero">
        <div class="hero-inner">
          <div>
            <div class="kicker"><em>\u25c6</em> MIRAI · jendela Niumination</div>
            <h2>Rumah yang <span>ada.</span></h2>
            <p class="lede">Bukan demo armada pabrik. Sepuluh kursi adalah topik Telegram; kerja hidup di grup, bukan di tombol di sini. Gateway hanya lampu. Plugin paket tetap mati.</p>
            <div class="actions">
              <button class="btn pri" onclick="show('agents')">Lihat sepuluh kursi</button>
              <button class="btn" onclick="show('schedule')" style="background:oklch(0.97 0.012 75 / .06); border-color:oklch(0.97 0.012 75 / .18); color:var(--cream)">Jadwal cron</button>
            </div>
          </div>
          <div>
            <div class="kpis">
              <div class="kpi"><b>${g.up?"hidup":"mati"}</b><small>Gateway</small><span>${esc(g.note||"tidak di-restart dari sini")}</span></div>
              <div class="kpi"><b>${w.alive?"hidup":(w.exists?"sepi":"tidak ada")}</b><small>Wiki</small><span>${esc(w.path||"—")} · ${esc(wikiLine)}</span></div>
              <div class="kpi"><b>${esc(cronOk)}</b><small>Cron yang diizinkan</small><span>${(c.ticker&&c.ticker.running)?"ticker hidup":"ticker tidak terlihat"}</span></div>
            </div>
            <div class="kpis" style="margin-top:10px">
              <div class="kpi"><b>${seats.length}</b><small>Kursi topik</small><span>${esc((house.telegram&&house.telegram.title)||"grup")} · plugin ${esc((house.telegram&&house.telegram.plugin)||"off")}</span></div>
              <div class="kpi"><b>1</b><small>Profil Hermes</small><span>${esc(house.profile||"default")} — create-fleet dilarang</span></div>
              <div class="kpi"><b>${esc((house.telegram&&house.telegram.router)||"config.yaml")}</b><small>Router</small><span>bukan plugin MIRAI</span></div>
            </div>
          </div>
        </div>
      </section>
      <div class="ribbon" aria-hidden="true"><div class="track">
        ${seats.map(s=>`<b><em>◆</em> ${esc(s.code)} ${esc(s.name)} #${esc(s.thread_id)}</b>`).join("")}
      </div></div>
      <h3>Sepuluh kursi</h3>
      <div class="fleet-mosaic">${seatMosaic}</div>
      <h3>Lima cron (bukan tujuh)</h3>
      <div class="card"><table><thead><tr><th>Nama</th><th>Jadwal</th><th></th></tr></thead><tbody>
        ${cronRows}</tbody></table>${forbid}
        <p class="sub" style="margin-top:10px">Mail-sweep dan offsite tidak dipasang. Angka “tidak terlihat” jujur: jendela hanya membaca jobs.json Hermes, tidak membuat job.</p>
      </div>`);
  }catch(e){ fail(id,e); }
};
function railFoot(agents){
  const el = $("#rail-foot"); if(!el) return;
  const host = (agents.host && agents.host.hostname) || location.hostname || "127.0.0.1";
  const where = location.port ? host + ":" + location.port : host;
  el.innerHTML = `${LANG==='en'?'Bound to':'Terikat ke'} <b>${esc(where)}</b>
    <div style="margin-top:8px;display:flex;gap:6px">
      <button type="button" class="pill" onclick="setLang('id')" ${LANG==="id"?"style='outline:1px solid oklch(0.66 0.22 38)'":""}>${t("lang.id")}</button>
      <button type="button" class="pill" onclick="setLang('en')" ${LANG==="en"?"style='outline:1px solid oklch(0.66 0.22 38)'":""}>${t("lang.en")}</button>
    </div>`;
}

function MISSIONS_MODE(){ return STATE.missions.length? "board: "+(STATE.missions[0].mode||"—") : "no missions yet"; }
function reducedMotion(){
  return !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
}
function faceUrl(a){
  const av = a && a.avatar;
  if(!av) return "";
  if(reducedMotion() && av.still) return av.still;
  return av.url || av.thumb || "";
}
function mosaicTile(a){
  const code=esc((a.code||"??").slice(0,2));
  const live = a.status==="ready"||a.status==="working"||a.status==="active";
  const go = "agents";
  const url = faceUrl(a);
  const img = url ? `<img class="faceimg" src="${esc(url)}" alt="${esc(a.name||a.code||'')}">` : "";
  const yaml = a.in_yaml===true ? (LANG==="en"?"in yaml":"di yaml") : (a.in_yaml===false ? (LANG==="en"?"not in yaml":"belum di yaml") : (a.status_label||a.status||""));
  return `<button type="button" class="mosaic" onclick="show('${go}')">
    ${img}
    <i class="live ${live||a.in_yaml?"":"off"}"></i>
    <div class="xl">${code}</div>
    <div class="nm">${esc(a.name||a.short||"")}</div>
    <div class="th">${esc(a.thread_id? "#"+a.thread_id : "")}${yaml? " · "+esc(yaml):""}</div>
  </button>`;
}
function seatCard(s){
  const url=faceUrl(s);
  const face=url?`<img src="${esc(url)}" alt="${esc(s.name||s.code||'')}">`:esc(s.code||"");
  const yaml = s.in_yaml ? (LANG==="en"?"in yaml":"di yaml") : (LANG==="en"?"not in yaml":"belum di yaml");
  const pill = s.in_yaml ? "good" : "warn";
  return `<div class="card agent">
    <div class="split"><div class="avatar">${face}</div>
      <div style="min-width:0"><h4>${esc(s.name)}</h4>
        <div class="code">${esc(s.code)} · #${esc(s.thread_id)}</div></div>
      <div style="margin-left:auto"><span class="pill ${pill}">${esc(yaml)}</span></div></div>
    <p style="margin:12px 0 6px;font-size:14px;line-height:1.45">${esc(s.job||"")}</p>
    <div class="sub">${esc(s.not_this||"")}</div>
  </div>`;
}
function agentCard(a){
  const initials=(a.code||a.short||a.name||"AG").slice(0,2).toUpperCase();
  const url = a.avatar && a.avatar.url ? a.avatar.url
            : (a.avatar && a.avatar.thumb) ? a.avatar.thumb : "";
  const face = url ? `<img src="${esc(url)}" alt="" onerror="this.replaceWith(document.createTextNode('${esc(initials)}'))">`
                   : esc(initials);
  const st = a.stats||{};
  const bars=(st.hourly_24h&&st.hourly_24h.agent||[]).slice(-24);
  const max=Math.max(1,...bars);
  return `<div class="card agent">
    <div class="split"><div class="avatar">${face}</div>
      <div style="min-width:0">
        <h4>${esc(a.name||a.profile)}</h4>
        <div class="code">${esc(a.code||"")} · ${esc(a.profile||"")} · ${esc(a.model||"no model")}</div>
      </div>
      <div style="margin-left:auto">${statusPill(a.status_label||a.status)}</div></div>
    <div class="sub" style="margin:10px 0 6px">${esc(a.role||"")}</div>
    <div class="row sub" style="gap:14px">
      <span>${nf(st.sessions_24h)} ${t("stat.sessions")}</span>
      <span>${nf(st.messages_7d)} messages / 7d</span>
      <span>${st.last_active? ago(st.last_active) : "never active"}</span>
    </div>
    <div class="spark" title="activity, last 24h">${bars.map(v=>`<i style="height:${Math.max(2,Math.round(v/max*24))}px"></i>`).join("")}</div>
  </div>`;
}

/* ----------------------------- Agents ------------------------------------ */
RENDERERS.agents = async (ctx) => {
  const id="agents";
  try{
    const [a, lib, house] = await Promise.all([api("/api/agents"), api("/api/avatars/library").catch(()=>({portraits:[]})), api("/api/house").catch(()=>STATE.house)]);
    STATE.agents=a.agents||[]; STATE.lib=lib; if(house) STATE.house=house;
    body(id, `
      <h2>Sepuluh kursi</h2>
      <p class="lede">Setiap kursi satu pekerjaan yang tidak boleh dicuri kursi lain. Kerja tetap di Telegram. Di sini hanya peta.</p>
      <div class="agents">${(STATE.house&&STATE.house.seats?STATE.house.seats:[]).map(seatCard).join("")}</div>
      <h3>Ganti foto (opsional)</h3>
      <div class="card">
        <div class="sub" style="margin-bottom:8px">Foto unggahan opsional di <code>~/mirai/data/avatars/</code>. Tanpa unggahan, dipakai bust paket. Reset = kembali ke bust, bukan identicon.</div>
        <div class="row">
          <select id="av-agent" style="max-width:220px">${STATE.agents.map(x=>`<option value="${esc(x.code)}">${esc(x.name)} (${esc(x.code)})</option>`).join("")}</select>
          <input type="file" id="av-file" accept="image/png,image/jpeg,image/webp" style="max-width:280px">
          <button class="btn pri" id="av-go">Pasang foto</button>
          <button class="btn" id="av-reset">Kembali ke bust</button>
        </div>
        ${(STATE.lib.portraits||[]).length ? `<div class="sub" style="margin-top:10px">Already added:
          ${STATE.lib.portraits.map(p=>`<span class="pill info">${esc(p.name||p.id||p)}</span>`).join(" ")}</div>` : ""}
      </div>
      ${a.mode||a.board ? `<div class="sub" style="margin-top:12px">board: ${esc(a.mode||"")} ${esc(a.board||"")}</div>`:""}
    `);
    $("#av-go").onclick = async () => {
      const f=$("#av-file").files[0]; if(!f) return toast("pick an image first", false);
      try{
        const data = await new Promise(r=>{const rd=new FileReader(); rd.onload=()=>r(rd.result); rd.readAsDataURL(f);});
        await api("/api/avatars/set", {method:"POST", body:{owner:$("#av-agent").value, upload:data}});
        toast("picture set"); RENDERED.delete("agents"); show("agents");
      }catch(e){ toast(e.message,false); }
    };
    $("#av-reset").onclick = async () => {
      try{ await api("/api/avatars/set", {method:"POST", body:{owner:$("#av-agent").value, reset:true}});
        toast("reset"); RENDERED.delete("agents"); show("agents"); }catch(e){ toast(e.message,false); }
    };
  }catch(e){ fail(id,e); }
};

/* --------------------------- Deploy an agent ----------------------------- */
RENDERERS.deploy = async () => {
  const id="deploy";
  try{
    const lib = await api("/api/workforce/library");
    const roles = lib.roles||lib.templates||[];
    body(id, `
      <h2>Deploy an agent</h2>
      <p class="lede">Clones a profile, copies the login across, writes the SOUL, sets the model and probes it once.
      A failure rolls the whole thing back — no half-created agents.</p>
      <div class="grid g2">
        <div class="card">
          <h4>Pick a role</h4>
          <input id="dp-search" placeholder="filter roles…" style="margin-bottom:8px">
          <div id="dp-roles" style="max-height:260px;overflow:auto">
            ${roles.map(r=>`<label class="row" style="text-transform:none;letter-spacing:0;color:var(--ink);gap:8px;margin:6px 0">
              <input type="radio" name="role" value="${esc(r.id)}" style="width:auto">
              <span><b>${esc(r.role||r.name)}</b> <span class="sub">${esc(r.category||"")}</span>
              <div class="sub">${esc(r.description||"")}</div></span></label>`).join("") || "<p class='empty'>No roles in ~/mirai/data/roles.json.</p>"}
          </div>
        </div>
        <div class="card">
          <h4>The new agent</h4>
          <label>Name</label><input id="dp-name" placeholder="Nova">
          <label>Model (optional)</label><input id="dp-model" placeholder="gpt-5.4-mini">
          <label>SOUL (optional — overrides the role)</label>
          <textarea id="dp-soul" placeholder="Leave empty to use the role's own SOUL."></textarea>
          <div class="row end" style="margin-top:12px"><button class="btn pri" id="dp-go">Deploy</button></div>
          <div id="dp-out" class="sub" style="margin-top:8px"></div>
        </div>
      </div>
      <h3>The crew on record</h3>
      <div id="dp-team"><p class="empty">loading…</p></div>`);
    $("#dp-search").oninput = e => {
      const q=e.target.value.toLowerCase();
      $$("#dp-roles label").forEach(l=>l.style.display = l.textContent.toLowerCase().includes(q)?"":"none");
    };
    const team = await api("/api/workforce/team");
    $("#dp-team").innerHTML = `<div class="card"><table><thead><tr>
      <th>Agent</th><th>Profile</th><th>In sync</th><th>Actions</th></tr></thead><tbody>
      ${(team.agents||[]).map(a=>`<tr>
        <td>${esc(a.name)} <span class="sub">${esc(a.code||"")}</span></td>
        <td class="mono">${esc(a.profile||"")}</td>
        <td>${a.in_sync?'<span class="pill good">yes</span>':'<span class="pill warn">no</span>'}</td>
        <td class="row">
          <button class="btn" data-rename="${esc(a.code)}" data-name="${esc(a.name)}">Rename</button>
          <button class="btn danger" data-remove="${esc(a.code)}" data-name="${esc(a.name)}">Remove</button>
        </td></tr>`).join("") || "<tr><td colspan=4 class='empty'>no agents</td></tr>"}
      </tbody></table>
      <div class="row end" style="margin-top:10px"><button class="btn" id="dp-sync">Re-sync team record</button>
      <span class="sub">in_sync ${esc(String(team.in_sync))} ${team.synced_at?"· "+ago(team.synced_at):""}</span></div></div>`;
    $("#dp-sync").onclick = async ()=>{ try{ await api("/api/workforce/team/sync",{method:"POST",body:{}});
      toast("team record synced"); RENDERED.delete("deploy"); show("deploy"); }catch(e){toast(e.message,false);} };
    $$("[data-rename]").forEach(b=>b.onclick=async()=>{
      const n=prompt("New name for "+b.dataset.name+"?", b.dataset.name); if(!n) return;
      try{ await api("/api/workforce/rename",{method:"POST",body:{code:b.dataset.rename,name:n}});
        toast("renamed"); RENDERED.delete("deploy"); show("deploy"); }catch(e){toast(e.message,false);} });
    $$("[data-remove]").forEach(b=>b.onclick=async()=>{
      const typed=prompt(`This archives the profile and deletes it. Type the agent's name to confirm:\n\n${b.dataset.name}`);
      if(typed===null) return;
      try{ await api("/api/workforce/remove",{method:"POST",body:{code:b.dataset.remove,confirm:typed}});
        toast("removed (archive kept)"); RENDERED.delete("deploy"); show("deploy"); }catch(e){toast(e.message,false);} });
    $("#dp-go").onclick = async () => {
      const role=($$("#dp-roles input:checked")[0]||{}).value||"";
      const name=$("#dp-name").value.trim();
      if(!name) return toast("the new agent needs a name", false);
      const out=$("#dp-out"); out.textContent="deploying… (this takes about 180 s: it is probed with a real turn)";
      try{
        const r = await api("/api/workforce/deploy",{method:"POST",body:{name, template:role,
          model:$("#dp-model").value.trim(), directions:$("#dp-soul").value.trim()}});
        out.innerHTML = `<span class="pill good">deployed in ${nf(r.seconds,1)}s</span> ${esc((r.probe||"").slice(0,160))}`;
        toast("agent deployed");
      }catch(e){ out.innerHTML=`<span class="pill bad">failed and rolled back</span> ${esc(e.message)}`; toast(e.message,false); }
    };
  }catch(e){ fail(id,e); }
};

/* ----------------------------- Missions ---------------------------------- */
RENDERERS.missions = async () => {
  const id="missions";
  try{
    const [m, agents] = await Promise.all([api("/api/missions"), api("/api/agents")]);
    STATE.agents=agents.agents||[];
    const list=m.missions||[];
    const roleOpts = STATE.agents.map(a=>`<option value="${esc(a.code)}">${esc(a.name)} (${esc(a.code)})</option>`).join("");
    body(id, `
      <h2>Missions</h2>
      <p class="lede">A mission is planned, approved, run on the crew, and has to come back with something you can read.
      Mode: <b>${esc(m.mode||"local")}</b>${m.mode==="board"?" (Hermes kanban board)":" (no board — steps are tracked here)"}.</p>
      <div class="grid g2">
        <div class="card">
          <h4>Brief one</h4>
          <label>Name</label><input id="ms-name" placeholder="Riset kopi gayo">
          <label>Objective</label><textarea id="ms-obj" placeholder="What must be true when this is done?"></textarea>
          <div class="row">
            <div style="flex:1"><label>Owner</label><select id="ms-owner">${roleOpts}</select></div>
            <div style="flex:1"><label>Steps</label><select id="ms-steps">${(m.limits.steps||[2,3,4]).map(n=>`<option${n===3?" selected":""}>${n}</option>`).join("")}</select></div>
            <div style="flex:1"><label>Time limit</label><select id="ms-time">${(m.limits.time||[15,30,60]).map(n=>`<option${n===30?" selected":""}>${n}</option>`).join("")}</select></div>
          </div>
          <div class="row end" style="margin-top:12px"><button class="btn pri" id="ms-go">Plan it</button></div>
        </div>
        <div class="card">
          <h4>By state</h4>
          <div class="row" id="ms-counts" style="gap:10px"></div>
          <div class="sub" style="margin-top:10px">Verbs: approve · accept · send back · replan · stop · cancel · clear.</div>
        </div>
      </div>
      <h3>All missions</h3>
      <div id="ms-list"></div>`);
    const counts={}; list.forEach(x=>counts[x.status]=(counts[x.status]||0)+1);
    $("#ms-counts").innerHTML = Object.keys(counts).sort().map(k=>`<span class="pill info">${esc(k)} ${counts[k]}</span>`).join("") || "<span class='empty'>none yet</span>";
    $("#ms-list").innerHTML = list.length ? list.map(missionCard).join("") : "<p class='empty'>No missions. Brief one above.</p>";
    wireMissionButtons();
    $("#ms-go").onclick = async () => {
      try{
        const r = await api("/api/missions",{method:"POST",body:{name:$("#ms-name").value.trim(),
          objective:$("#ms-obj").value.trim(), owner:$("#ms-owner").value,
          max_steps:Number($("#ms-steps").value), time_limit_min:Number($("#ms-time").value)}});
        toast(`planned ${r.id} — review the steps, then approve`);
        RENDERED.delete("missions"); show("missions");
      }catch(e){ toast(e.message,false); }
    };
  }catch(e){ fail(id,e); }
};
function missionCard(m){
  const steps=(m.steps||[]).map(s=>`<tr>
    <td class="mono">${nf(s.idx)}</td>
    <td>${esc(s.agent||"")}</td>
    <td>${esc(s.title||"")}</td>
    <td>${statusPill(s.status)}</td></tr>`).join("");
  const events=(m.events||[]).slice(-4).map(e=>`<div class="sub">${esc(e.kind)} · ${ago(e.at)} ${e.note?"· "+esc(e.note):""}</div>`).join("");
  return `<div class="card" style="margin-bottom:12px">
    <div class="split"><b class="mono">${esc(m.id)}</b><span>${esc(m.name)}</span>
      <div style="margin-left:auto">${statusPill(m.status)}</div></div>
    <div class="sub" style="margin:6px 0 10px">${esc(m.objective||"")}</div>
    <table><thead><tr><th>#</th><th>Agent</th><th>Step</th><th>State</th></tr></thead><tbody>${steps}</tbody></table>
    ${events?`<div style="margin-top:10px">${events}</div>`:""}
    <div class="row" style="margin-top:12px">
      ${["approve","accept","send_back","replan","stop","cancel","clear"].map(v=>
        `<button class="btn${v==="approve"?" pri":""}${v==="cancel"? " danger":""}" data-mid="${esc(m.id)}" data-act="${v}">${v.replace("_"," ")}</button>`).join("")}
    </div>
    ${m.error?`<div class="notice bad" style="margin-top:8px">${esc(String(m.error).slice(0,240))}</div>`:""}
    <div class="sub" style="margin-top:8px">
      ${m.mode?`mode ${esc(m.mode)} · `:""}${m.max_steps?`up to ${nf(m.max_steps)} steps · `:""}${m.time_limit_min?`${nf(m.time_limit_min)} min`:"no time limit"}
      ${m.time_left_s!=null?` · ${nf(m.time_left_s/60,1)} min left`:""}
      ${m.review?" · review required":""}
      ${m.result?` · <b>result:</b> ${esc(String(m.result).slice(0,160))}`:""}
    </div>
  </div>`;
}
function wireMissionButtons(){
  $$("[data-mid]").forEach(b=>b.onclick=async()=>{
    b.disabled=true;
    try{
      const r=await api("/api/missions/action",{method:"POST",body:{id:b.dataset.mid,action:b.dataset.act}});
      toast(`${b.dataset.mid}: ${b.dataset.act.replace("_"," ")} → ${(r.mission&&r.mission.status)||"ok"}`);
      RENDERED.delete("missions"); show("missions");
    }catch(e){ toast(e.message,false); b.disabled=false; }
  });
}

/* ------------------------------- Chat ------------------------------------ */
let CHAT = {agent:null, files:[]};
RENDERERS.chat = async () => {
  const id="chat";
  try{
    const agents = (STATE.agents.length? STATE.agents : (await api("/api/agents")).agents||[]).filter(x=>x.kind==="profile");
    STATE.agents=STATE.agents.length?STATE.agents: (await api("/api/agents")).agents||[];
    const talk = agents.length? agents : STATE.agents.filter(x=>x.kind==="profile");
    if(!CHAT.agent && talk.length) CHAT.agent = talk[0].code;
    body(id, `
      <h2>Chat</h2>
      <p class="lede">Obrolan lokal ke profil Hermes default di mesin ini. Bukan grup Telegram dan bukan saingan sepuluh topik. Kerja kru tetap di forum.</p>
      <div class="card" style="margin-bottom:12px">
        <div class="row">
          <select id="ch-agent" style="max-width:240px">
            ${talk.map(a=>`<option value="${esc(a.code)}"${a.code===CHAT.agent?" selected":""}>${esc(a.name)} (${esc(a.code)})</option>`).join("")}
          </select>
          <input type="file" id="ch-file" multiple style="max-width:260px">
          <div class="sub" id="ch-files"></div>
          <button class="btn" id="ch-forget" style="margin-left:auto">Forget this thread</button>
        </div>
      </div>
      <div class="card" style="display:flex;flex-direction:column;gap:12px">
        <div id="ch-log" class="scroll" style="max-height:46vh;overflow:auto;display:flex;flex-direction:column;gap:10px"></div>
        <div class="row">
          <textarea id="ch-text" style="min-height:70px;flex:1" placeholder="Write to the agent…  (⌘/Ctrl+Enter sends)"></textarea>
        </div>
        <div class="row end"><span class="sub" id="ch-state"></span><button class="btn pri" id="ch-send">Send</button></div>
      </div>`);
    $("#ch-agent").onchange = e => { CHAT.agent=e.target.value; loadHistory(); };
    $("#ch-file").onchange = async e => {
      CHAT.files = await Promise.all(Array.from(e.target.files).map(f => new Promise(r=>{
        const rd=new FileReader(); rd.onload=()=>r({name:f.name, data:rd.result}); rd.readAsDataURL(f); })));
      $("#ch-files").textContent = CHAT.files.map(f=>f.name).join(", ");
    };
    $("#ch-send").onclick = sendChat;
    $("#ch-text").onkeydown = e => { if((e.metaKey||e.ctrlKey)&&e.key==="Enter") sendChat(); };
    $("#ch-forget").onclick = async () => {
      try{ await api("/api/chat/forget",{method:"POST",body:{agent:CHAT.agent}}); toast("thread cleared"); loadHistory(); }
      catch(e){ toast(e.message,false); }
    };
    loadHistory();
  }catch(e){ fail(id,e); }
};
async function loadHistory(){
  const log=$("#ch-log"); if(!log) return;
  log.innerHTML = `<p class="empty">${LANG==="en"?"loading…":"memuat…"}</p>`;
  try{
    const h = await api("/api/chat/history?agent="+encodeURIComponent(CHAT.agent));
    if($("#ch-state")) $("#ch-state").textContent = h.thinking ? "the agent is thinking…" : "";
    const ag = (STATE.agents||[]).find(x=>x.code===CHAT.agent);
    const au = faceUrl(ag);
    log.innerHTML = (h.messages||[]).map(m=>{
      const crewFace = (m.role!=="you" && au)
        ? `<img src="${esc(au)}" alt="" style="width:36px;height:36px;border-radius:12px;object-fit:cover;flex:0 0 36px;border:1px solid var(--border)">`
        : "";
      return `
      <div style="align-self:${m.role==="you"?"flex-end":"flex-start"};display:flex;align-items:flex-end;gap:8px;max-width:84%">
        ${m.role==="you"?"":crewFace}
        <div style="display:flex;flex-direction:column;gap:6px;min-width:0">
        <div class="sub mono" style="text-align:${m.role==="you"?"right":"left"};letter-spacing:.14em;text-transform:uppercase;font-size:9px">
          ${m.role==="you"?"you":esc(h.agent)} \u00b7 ${ago(m.at)}${m.ms?" \u00b7 "+nf(m.ms/1000,1)+"s":""}</div>
        <div class="bubble ${m.role==="you"?"you":"crew"}">${esc(m.text)}</div>
        </div>
      </div>`;
    }).join("") || `<p class='empty'>${LANG==='en'?'nothing here yet':'belum ada percakapan'}</p>`;
    log.scrollTop = log.scrollHeight;
  }catch(e){ log.innerHTML = `<div class="notice bad">${esc(e.message)}</div>`; }
}
async function sendChat(){
  const t=$("#ch-text").value.trim(); if(!t && !CHAT.files.length) return;
  const btn=$("#ch-send"); btn.disabled=true; $("#ch-state").textContent="sent — waiting for the agent (up to 5 minutes)…";
  try{
    await api("/api/chat",{method:"POST",body:{agent:CHAT.agent,text:t,files:CHAT.files}});
    $("#ch-text").value=""; CHAT.files=[]; $("#ch-files").textContent=""; $("#ch-file").value="";
    await loadHistory();
  }catch(e){ toast(e.message,false); $("#ch-state").textContent=""; }
  btn.disabled=false;
}

/* ------------------------------- Docs ------------------------------------ */
RENDERERS.docs = async () => {
  const id="docs";
  try{
    const d = await api("/api/docs");
    const docs = d.documents||[];
    body(id, `
      <h2>Docs</h2>
      <p class="lede">Documents the crew produces, on disk at <code>${esc(d.dir||"~/mirai/data/docs")}</code>, nothing hidden in a database.</p>
      <div class="grid g2">
        <div class="card">
          <h4>Write one</h4>
          <label>Title</label><input id="dc-title" placeholder="Proposal for Acme">
          <label>Agent</label><select id="dc-agent">${STATE.agents.map(a=>`<option value="${esc(a.code)}">${esc(a.name)}</option>`).join("")}</select>
          <label>Body (markdown)</label><textarea id="dc-text" style="min-height:150px"></textarea>
          <div class="row end" style="margin-top:10px"><button class="btn pri" id="dc-save">Save</button></div>
        </div>
        <div class="card">
          <h4>From a chat reply</h4>
          <p class="sub">In Chat, hover a reply and use <span class="kbd">Save as doc</span> — or paste it here and file it under the agent that wrote it.</p>
          <label>Agent</label><select id="dc-fc-agent">${STATE.agents.map(a=>`<option value="${esc(a.code)}">${esc(a.name)}</option>`).join("")}</select>
          <label>Reply text</label><textarea id="dc-fc-text"></textarea>
          <div class="row end" style="margin-top:10px"><button class="btn" id="dc-fc">File it</button></div>
        </div>
      </div>
      <h3>Library</h3>
      <div class="card"><table><thead><tr><th>Id</th><th>Title</th><th>Agent</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody>
        ${docs.map(x=>`<tr>
          <td class="mono">${esc(x.id)}</td><td>${esc(x.title)}</td><td>${esc(x.agent||"")}</td>
          <td>${statusPill(x.status)}</td><td class="sub">${ago(x.mtime)}</td>
          <td class="row"><button class="btn" data-doc-read="${esc(x.id)}">Read</button>
            <a class="btn" href="/api/docs/download?id=${encodeURIComponent(x.id)}">Download</a>
            <button class="btn danger" data-doc-del="${esc(x.id)}">Delete</button></td></tr>`).join("")
          || "<tr><td colspan=6 class='empty'>nothing filed yet</td></tr>"}
      </tbody></table></div>
      <div id="dc-view"></div>`);
    $("#dc-save").onclick=async()=>{
      try{ await api("/api/docs/save",{method:"POST",body:{title:$("#dc-title").value.trim(),
        text:$("#dc-text").value, agent:$("#dc-agent").value}}); toast("saved"); RENDERED.delete("docs"); show("docs"); }
      catch(e){ toast(e.message,false); } };
    $("#dc-fc").onclick=async()=>{
      try{ await api("/api/docs/from-chat",{method:"POST",body:{agent:$("#dc-fc-agent").value,
        text:$("#dc-fc-text").value}}); toast("filed"); RENDERED.delete("docs"); show("docs"); }
      catch(e){ toast(e.message,false); } };
    $$("[data-doc-read]").forEach(b=>b.onclick=async()=>{
      try{ const r=await api("/api/docs/read?id="+encodeURIComponent(b.dataset.docRead));
        const meta=r.meta||{};
        $("#dc-view").innerHTML=`<h3>${esc(meta.title||b.dataset.docRead)}</h3>
          <div class="sub">${esc(meta.agent||"")} · ${esc(meta.status||"")} · created ${esc(meta.created||"")} · updated ${esc(meta.updated||"")}</div>
          <pre>${esc(r.text||"")}</pre>`;
      }catch(e){ toast(e.message,false); } });
    $$("[data-doc-del]").forEach(b=>b.onclick=async()=>{
      if(!confirm("Delete "+b.dataset.docDel+"? It is moved to docs-deleted/ with a timestamp, not erased.")) return;
      try{ await api("/api/docs/delete",{method:"POST",body:{id:b.dataset.docDel}});
        toast("deleted (kept in docs-deleted/)"); RENDERED.delete("docs"); show("docs"); }catch(e){ toast(e.message,false); } });
  }catch(e){ fail(id,e); }
};

/* ----------------------------- Schedule ---------------------------------- */
RENDERERS.schedule = async () => {
  const id="schedule";
  try{
    const c = await api("/api/cron");
    const s=c.scheduler||{};
    body(id, `
      <h2>Schedule</h2>
      <p class="lede">Jadwal yang terbaca di Hermes. Yang diizinkan hanya lima job wiki. Jendela ini tidak membuat cron.</p>
      <div class="grid g3">
        <div class="card"><h4>Ticker</h4><div class="metric">${s.running?"live":"down"}</div>
          <div class="sub">${s.heartbeat_s!=null?"last beat "+ago(Date.now()/1000-s.heartbeat_s):"no heartbeat file"}</div></div>
        <div class="card"><h4>Jobs</h4><div class="metric">${(c.jobs||[]).length}</div><div class="sub">${nf(c.seats)} seats</div></div>
        <div class="card"><h4>Where</h4><div class="sub mono">~/.hermes/**/cron/jobs.json</div>
          <div class="sub">MIRAI writes here only when you press a verb — that is the sanctioned exception.</div></div>
      </div>
      <h3>Jobs</h3>
      <div class="card"><table><thead><tr><th>Job</th><th>Agent</th><th>Schedule</th><th>Live</th><th>Last run</th><th></th></tr></thead><tbody>
      ${(c.jobs||[]).map(j=>`<tr>
        <td>${esc(j.name||j.id)}<div class="sub">${esc((j.prompt||"").slice(0,110))}${(j.prompt||"").length>110?"…":""}</div></td>
        <td>${esc(j.agent_name||j.agent||"")}<div class="sub mono">${esc(j.agent||"")}</div></td>
        <td>${esc(j.english||j.expr||"")}<div class="sub mono">${esc(j.expr||"")}</div></td>
        <td>${j.live?'<span class="pill good">live</span>':'<span class="pill warn">paused</span>'}${j.paused_reason?`<div class="sub">${esc(j.paused_reason)}</div>`:""}</td>
        <td class="sub">${j.last_run_at? ago(j.last_run_at):"never"}<div>${esc(j.last_status||"")}</div>${j.last_error?`<div>${esc(String(j.last_error).slice(0,80))}</div>`:""}
          <div>${nf(j.runs)} runs</div></td>
        <td class="row">
          ${["run","pause","resume"].map(v=>`<button class="btn" data-job="${esc(j.id)}" data-prof="${esc(j.agent||"")}" data-verb="${v}">${v}</button>`).join("")}
          <button class="btn danger" data-job="${esc(j.id)}" data-prof="${esc(j.agent||"")}" data-verb="delete">delete</button>
        </td></tr>`).join("") || "<tr><td colspan=6 class='empty'>no jobs — the crew has no standing orders yet (see memory/schedule/cron-jobs.json)</td></tr>"}
      </tbody></table>
      <div class="sub" style="margin-top:8px">MIRAI asks the CLI for a run and then watches <code>last_run_at</code>: depending on the
      Hermes version, <code>cron run</code> either fires now or waits for the next tick, and the exit code does not say which.</div></div>`);
    $$("[data-job]").forEach(b=>b.onclick=async()=>{
      if(b.dataset.verb==="delete" && !confirm("Remove this job? Pause is the safer verb.")) return;
      b.disabled=true;
      try{ await api("/api/cron/action",{method:"POST",body:{agent:b.dataset.prof, id:b.dataset.job, action:b.dataset.verb}});
        toast(`${b.dataset.job}: ${b.dataset.verb} ok`); RENDERED.delete("schedule"); show("schedule"); }
      catch(e){ toast(e.message,false); b.disabled=false; } });
  }catch(e){ fail(id,e); }
};

/* ------------------------------ Health ----------------------------------- */
RENDERERS.health = async () => {
  const id="health";
  try{
    const h = await api("/api/health");
    STATE.health=h;
    const m=h.memory||{}, d=h.disk||{}, c=h.cpu||{}, net=h.network||{}, hos=h.host||{}, pr=h.processes||{count:0,top:[]};
    const diag=h.diagnostics||{}, hist=h.history||{cpu:[],ram:[],disk:[],network:[]};
    const spark=(arr,col,max)=>`<div class="spark">${(arr||[]).slice(-40).map(v=>{
      const h2=Math.max(1,Math.min(24,Math.round((v||0)/(max||1)*24)));
      return `<i style="height:${h2}px;background:${col}"></i>`;}).join("")}</div>`;
    const maxC=Math.max(10,...(hist.cpu||[])), maxN=Math.max(0.1,...(hist.network||[]));
    body(id, `
      <h2>Health</h2>
      <p class="lede">What the machine is doing right now, sampled every ${esc(h.interval_s)}s by the backend, so the page is a
      window and not a poller. Read on ${esc(hos.os||"")}, ${esc(hos.arch||"")}, ${esc(hos.cores||"")} cores.</p>
      <div class="grid g3">
        <div class="card"><h4>CPU</h4><div class="metric">${nf(c.pct,1)}<small>%</small></div>${spark(hist.cpu,"var(--info)",maxC)}
          <div class="sub">load ${esc((hos.load||[]).join(" "))} · ${nf(hos.cores)} cores</div></div>
        <div class="card"><h4>Memory</h4><div class="metric">${nf(m.pct,1)}<small>%</small></div>${spark(hist.ram,"var(--lib)",100)}
          <div class="sub">${nf(m.used_gb,1)} of ${nf(m.total_gb,1)} GB · ${nf(m.available_gb,1)} GB available</div></div>
        <div class="card"><h4>Disk</h4><div class="metric">${nf(d.pct,0)}<small>%</small></div>${spark(hist.disk,"var(--ok)",100)}
          <div class="sub">${nf(d.used_gb,0)} of ${nf(d.total_gb,0)} GB · ${esc(d.mount||"")} (${esc(d.kind||"")})</div></div>
        <div class="card"><h4>Network</h4><div class="metric">${nf(net.mb_s,2)}<small>MB/s</small></div>${spark(hist.network,"var(--warn)",maxN)}
          <div class="sub">${nf(net.total_bytes? net.total_bytes/1e9 : 0,2)} GB moved · ${nf(h.connections)} connections</div></div>
        <div class="card"><h4>Uptime</h4><div class="metric">${nf(hos.uptime_h|| (hos.uptime_s/3600),1)}<small>h</small></div>
          <div class="sub">${esc(hos.hostname||"")} · kernel ${esc(hos.kernel||"")}</div></div>
        <div class="card"><h4>Checks</h4><div class="metric">${nf(diag.passed)}<small>/ ${nf(diag.checks)}</small></div>
          <div class="sub">${esc(diag.status||"")}${diag.warnings?` · ${nf(diag.warnings)} warnings`:""}</div></div>
      </div>
      <h3>Diagnostics — every line is a thing you can fix</h3>
      <div class="card"><table><tbody>
        ${(diag.items||[]).map(i=>`<tr>
          <td style="width:34%">${i.ok?'<span class="dot good"></span>':'<span class="dot warn"></span>'} ${esc(i.name||"")}</td>
          <td class="sub">${esc(i.detail||"")}</td></tr>`).join("")
          || "<tr><td class='empty' colspan=2>no diagnostics reported</td></tr>"}
      </tbody></table></div>
      <h3>The machine itself</h3>
      <div class="grid g2">
        <div class="card"><h4>Volumes</h4><table><thead><tr><th>Mount</th><th>Device</th><th>Used</th><th></th></tr></thead><tbody>
          ${(h.volumes||[]).map(v=>`<tr><td class="mono">${esc(v.mount)}</td><td class="sub">${esc(v.what||"")}</td>
            <td>${nf(v.used_gb,1)} / ${nf(v.total_gb,1)} GB</td><td>${nf(v.pct,0)}%</td></tr>`).join("")}
        </tbody></table></div>
        <div class="card"><h4>Processes <span class="sub">(${nf(pr.count)} running, top ${(pr.top||[]).length} shown)</span></h4>
          <table><thead><tr><th>PID</th><th>Process</th><th>CPU</th><th>Mem</th></tr></thead><tbody>
          ${(pr.top||[]).map(p=>`<tr><td class="mono">${esc(p.pid)}</td>
            <td>${esc(p.name||"")}${p.agent?` <span class="pill info">${esc(p.agent)}</span>`:""}<div class="sub">${esc((p.what||"").slice(0,80))}</div></td>
            <td>${nf(p.cpu,1)}%</td><td>${nf(p.mem_gb*1024,0)} MB</td></tr>`).join("")}
        </tbody></table></div>
      </div>
      <div class="sub" style="margin-top:10px">MIRAI server up ${nf((h.server||{}).uptime_s)}s · sampled ${ago(h.sampled_at)}</div>`);
  }catch(e){ fail(id,e); }
};

/* ------------------------------- Files ----------------------------------- */
let FILES = {agent:null, path:null, text:"", mtime:0};
RENDERERS.files = async () => {
  const id="files";
  try{
    const t = await api("/api/files/tree");
    const agents = t.agents||[];
    if(!FILES.agent && agents.length) FILES.agent = agents[0].code;
    const cur = agents.find(a=>a.code===FILES.agent) || agents[0] || {groups:[]};
    body(id, `
      <h2>Files</h2>
      <p class="lede">The four things a person is meant to edit: who the agent is, how it behaves, what it knows about you,
      what it remembers. Everything else in <code>~/.hermes</code> is the crew's own and MIRAI will not touch it.
      Backups land in <code>${esc(t.backups_dir||"~/mirai/data/file-backups")}</code> (${nf(t.backups_total)} kept).</p>
      <div class="card" style="margin-bottom:12px"><div class="row">
        <select id="fl-agent" style="max-width:260px">
          ${agents.map(a=>`<option value="${esc(a.code)}"${a.code===FILES.agent?" selected":""}>${esc(a.name)} (${esc(a.code)})</option>`).join("")}
        </select>
        <span class="sub">${esc(cur.home||"")}</span>
        <span class="pill info" style="margin-left:auto">${nf(cur.count)} files · ${nf(cur.custom)} edited by hand · ${nf(cur.backups)} backups</span>
      </div></div>
      <div class="grid g2">
        <div class="card"><h4>Files</h4>
          ${(cur.groups||[]).map(g=>`<div style="margin-bottom:12px">
            <div class="sub" style="margin-bottom:4px">${esc(g.label)}</div>
            ${g.files.map(f=>`<div class="row" style="margin:4px 0">
              <button class="btn" data-fl="${esc(f.path)}" style="flex:1;text-align:left">${esc(f.name)}
                <span class="sub"> · ${nf(f.size)} B · ${ago(f.mtime)}</span></button>
              ${f.sensitive?'<span class="pill warn">secrets</span>':""}</div>`).join("")}
            <div class="sub">${esc(g.note||"")}</div></div>`).join("")}
        </div>
        <div class="card">
          <h4 id="fl-title">Pick a file</h4>
          <div class="sub" id="fl-note"></div>
          <textarea id="fl-text" style="min-height:300px;margin-top:8px" disabled></textarea>
          <div class="row end" style="margin-top:10px">
            <span class="sub" id="fl-state"></span>
            <button class="btn" id="fl-reload" disabled>Reload</button>
            <button class="btn pri" id="fl-save" disabled>Save (with backup)</button>
          </div>
          <div class="notice" style="margin-top:12px">A save is refused if the file changed on disk since you opened it —
            the crew writes its own files constantly and silently overwriting it would undo real work. Reload and re-apply.</div>
        </div>
      </div>`);
    $("#fl-agent").onchange = e => { FILES={agent:e.target.value, path:null, text:"", mtime:0}; RENDERED.delete("files"); show("files"); };
    $$("[data-fl]").forEach(b=>b.onclick=()=>openFile(b.dataset.fl));
    $("#fl-save").onclick = saveFile;
    $("#fl-reload").onclick = () => openFile(FILES.path);
  }catch(e){ fail(id,e); }
};
async function openFile(path){
  try{
    const f = await api(`/api/files/read?agent=${encodeURIComponent(FILES.agent)}&path=${encodeURIComponent(path)}`);
    FILES.path = path; FILES.text = f.text||""; FILES.mtime = f.mtime||0;
    $("#fl-title").textContent = path.split("/").pop();
    $("#fl-note").innerHTML = `${esc(f.kind||"")}${f.sensitive?' · <span class="pill warn">holds secrets</span>':""}
      <span class="sub">· ${nf((f.text||"").length)} B · ${ago(f.mtime)}</span>`;
    $("#fl-text").value = FILES.text; $("#fl-text").disabled=false;
    $("#fl-save").disabled=false; $("#fl-reload").disabled=false; $("#fl-state").textContent="";
  }catch(e){ toast(e.message,false); }
}
async function saveFile(){
  $("#fl-state").textContent = "saving…";
  try{
    const r = await api("/api/files/write",{method:"POST",body:{agent:FILES.agent, path:FILES.path,
      text:$("#fl-text").value, mtime:FILES.mtime}});
    FILES.mtime = r.mtime||FILES.mtime;
    $("#fl-state").textContent = "saved"+(r.backup? ` · backup ${r.backup}`:" · backup kept");
    toast("saved (backup kept)");
  }catch(e){ $("#fl-state").textContent=""; toast(e.message,false); }
}

/* ----------------------------- Terminal ---------------------------------- */
let TERM = {session:null, es:null};
RENDERERS.terminal = async () => {
  const id="terminal";
  try{
    const l = await api("/api/terminal/list");
    const cmds = await api("/api/terminal/commands").catch(()=>({commands:[]}));
    body(id, `
      <h2>Terminal</h2>
      <p class="lede">A real shell on this machine, for the owner. Sessions survive a page reload and are closed after an
      hour idle. Output arrives over SSE, so nothing here is polled.</p>
      <div class="card" style="margin-bottom:12px"><div class="row">
        <select id="tm-runtime" style="max-width:160px">
          ${["shell","bash","python","node"].map(r=>`<option>${r}</option>`).join("")}
        </select>
        <button class="btn pri" id="tm-open">Open session</button>
        <span class="sub" id="tm-state"></span>
        <span class="sub" style="margin-left:auto">${(l.sessions||[]).length} open</span>
      </div>
      ${(cmds.commands||[]).length?`<div class="sub">remembered: ${cmds.commands.slice(0,12).map(c=>`<span class="pill info">${esc(c)}</span>`).join(" ")}</div>`:""}
      </div>
      <div class="term">
        <pre id="tm-out">Press “Open session” to start. Type a command and press Enter.\n</pre>
        <div class="in">
          <input id="tm-in" placeholder="command…">
          <button class="btn" id="tm-send">Send</button>
          <button class="btn" id="tm-kill">Kill (HUP→TERM→KILL)</button>
        </div>
      </div>`);
    $("#tm-open").onclick = async () => {
      try{
        const r = await api("/api/terminal/open",{method:"POST",body:{runtime:$("#tm-runtime").value, cols:100, rows:30}});
        TERM.session = r.session; $("#tm-state").textContent = `session ${r.session.id.slice(0,8)} · pid ${r.session.pid}`;
        attachStream(r.session.id);
      }catch(e){ toast(e.message,false); }
    };
    $("#tm-send").onclick = sendTerm; 
    $("#tm-in").onkeydown = e => { if(e.key==="Enter") sendTerm(); };
    $("#tm-kill").onclick = async () => {
      if(!TERM.session) return;
      try{ await api("/api/terminal/close",{method:"POST",body:{id:TERM.session.id}});
        out("\n[session closed]\n"); $("#tm-state").textContent="closed"; }catch(e){ toast(e.message,false); }
    };
  }catch(e){ fail(id,e); }
};
function out(s){ const p=$("#tm-out"); if(!p) return; p.textContent += s; p.scrollTop = p.scrollHeight; }
function attachStream(sid){
  if(TERM.es) TERM.es.close();
  const es = new EventSource(`/api/terminal/stream?id=${encodeURIComponent(sid)}`);
  TERM.es = es;
  es.onmessage = ev => {
    try{ out(atob(ev.data)); }catch(e){ /* a keep-alive frame */ }
  };
  es.onerror = () => { out("\n[stream closed — reopen the session if the shell is gone]\n"); es.close(); };
}
async function sendTerm(){
  if(!TERM.session){ toast("open a session first", false); return; }
  const v=$("#tm-in").value; if(!v) return;
  try{ await api("/api/terminal/input",{method:"POST",body:{id:TERM.session.id,data:v+"\n"}}); $("#tm-in").value=""; }
  catch(e){ toast(e.message,false); }
}

/* ------------------------------- Voice ----------------------------------- */
RENDERERS.voice = async () => {
  const id="voice";
  try{
    const [v, h] = await Promise.all([api("/api/voice/config"), api("/api/voice/health").catch(()=>null)]);
    const c=v.config||{};
    body(id, `
      <h2>Voice</h2>
      <p class="lede">Three modes. The mode is a number, and it decides which engine speaks when the crew answers.</p>
      <div class="grid g3">
        ${[1,2,3].map(n=>{const m=(c.modes||{})[n]||{}; return `
          <div class="card" style="${c.mode===n?"border-color:var(--ember); box-shadow:0 0 0 3px oklch(0.66 0.22 38 / .12)":""}">
            <h4>Mode ${n} — ${esc(m.name||"")}</h4>
            <div class="sub">${esc(m.note||"")}</div>
            <div class="row" style="margin-top:8px">${(m.tags||[]).map(t=>`<span class="pill info">${esc(t)}</span>`).join("")}</div>
            <div class="row end" style="margin-top:10px">
              <button class="btn ${c.mode===n?"pri":""}" data-vm="${n}">${c.mode===n?"active":"use this"}</button></div>
          </div>`; }).join("")}
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h4>Engines</h4>
          <table><tbody>
            <tr><td>Local voice service</td><td>${c.engine_up?'<span class="pill good">up</span>':`<span class="pill warn">${c.engine_installed?"installed, not running":"not installed"}</span>`}</td>
              <td class="sub">${esc(c.start_command||"")}</td></tr>
            <tr><td>ElevenLabs key</td><td>${c.el_key_present?'<span class="pill good">present</span>':'<span class="pill warn">absent</span>'}</td>
              <td class="sub">stored in ~/mirai/data/secrets.env, never printed back</td></tr>
            <tr><td>Speech out</td><td colspan=2 class="sub">${esc((h&&h.engine)||c.engine||"")} ${h? JSON.stringify(h.detail||{}).slice(0,120):""}</td></tr>
          </tbody></table>
          <label>ElevenLabs key (stored, never echoed)</label>
          <div class="row"><input id="vo-key" type="password" placeholder="sk-…">
            <button class="btn" id="vo-key-save">Save</button></div>
          <label>Speed</label>
          <div class="row"><input id="vo-speed" type="range" min="0.5" max="2" step="0.05" value="${esc(c.speed||1)}" style="max-width:240px">
            <span class="sub" id="vo-speed-v">${esc(c.speed||1)}×</span></div>
          <div class="row" style="margin-top:10px"><button class="btn" id="vo-greet">Speak the greeting</button></div>
        </div>
        <div class="card"><h4>Transcription</h4>
          <p class="sub">Speech IN is browser-side in mode 1 and ElevenLabs in modes 2 and 3. This build will not pretend to
          transcribe: with no engine configured, /api/transcribe returns the reason rather than an empty string.</p>
          <input type="file" id="vo-file" accept="audio/*">
          <div class="row end" style="margin-top:10px"><button class="btn" id="vo-tr">Transcribe</button></div>
          <pre id="vo-out" style="max-height:20vh">—</pre>
        </div>
      </div>`);
    $$("[data-vm]").forEach(b=>b.onclick=async()=>{
      try{ await api("/api/voice/config",{method:"POST",body:{mode:Number(b.dataset.vm)}});
        toast("mode "+b.dataset.vm); RENDERED.delete("voice"); show("voice"); }catch(e){ toast(e.message,false); } });
    $("#vo-speed").oninput = e => $("#vo-speed-v").textContent = e.target.value+"×";
    $("#vo-speed").onchange = async e => {
      try{ await api("/api/voice/config",{method:"POST",body:{speed:Number(e.target.value)}}); toast("speed saved"); }
      catch(err){ toast(err.message,false); } };
    $("#vo-key-save").onclick = async () => {
      try{ await api("/api/voice/elevenlabs-key",{method:"POST",body:{key:$("#vo-key").value.trim()}});
        $("#vo-key").value=""; toast("key stored (0600, never echoed)"); }catch(e){ toast(e.message,false); } };
    $("#vo-greet").onclick = async () => {
      try{ const r = await api("/api/greeting"); toast("greeting: "+(r.greeting||r.text||"spoken")); }
      catch(e){ toast(e.message,false); } };
    $("#vo-tr").onclick = async () => {
      const f=$("#vo-file").files[0]; if(!f) return toast("pick an audio file", false);
      const data = await new Promise(r=>{const rd=new FileReader(); rd.onload=()=>r(rd.result); rd.readAsDataURL(f);});
      try{ const r = await api("/api/transcribe",{method:"POST",body:{audio:data, name:f.name}});
        $("#vo-out").textContent = r.text||JSON.stringify(r,null,2); }
      catch(e){ $("#vo-out").textContent = "refused: "+e.message; }
    };
  }catch(e){ fail(id,e); }
};

/* ----------------------------- Agent City -------------------------------- */
RENDERERS.city = async () => {
  const id="city";
  try{
    const a = await api("/api/agents");
    STATE.agents=a.agents||[];
    body(id, `
      <h2>Agent City</h2>
      <p class="lede">The campus view: one building per agent, drawn from what the roster says. The designed dashboard draws
      this in 3D with portraits; this console keeps the same information flat, so nothing here is decorative-only.</p>
      <div class="agents">
        ${STATE.agents.map(x=>`<div class="card agent">
          <div class="split"><div class="avatar">${faceUrl(x)?`<img src="${esc(faceUrl(x))}" alt="">`:esc((x.code||x.short||x.name||"AG").slice(0,2).toUpperCase())}</div>
            <div><h4>${esc(x.building||x.name)}</h4><div class="code">${esc(x.code)} · ${esc(x.profile)}</div></div>
            <div style="margin-left:auto">${statusPill(x.status_label||x.status)}</div></div>
          <div class="sub" style="margin-top:8px">${esc(x.role||"")}</div>
          <div class="row sub" style="gap:12px;margin-top:6px">
            <span>${x.model?esc(x.model):"no model set"}</span>
            <span>${x.stats&&x.stats.sessions_24h?nf(x.stats.sessions_24h)+" sessions today":"quiet today"}</span>
            <span>${x.last_active?ago(x.last_active):""}</span></div>
        </div>`).join("") || "<p class='empty'>No agents yet — deploy one.</p>"}
      </div>
      <div class="notice">A ghost agent (a role that exists in the plan but has no profile yet) appears in the designed page
      as a red link. Here it is simply absent: MIRAI reports what is on the machine, not what could be.</div>`);
  }catch(e){ fail(id,e); }
};

/* ------------------------------ Hand mode -------------------------------- */
const HAND_FILES = [
  "vision_bundle.mjs", "hand_landmarker.task",
  "wasm/vision_wasm_internal.js", "wasm/vision_wasm_internal.wasm",
  "wasm/vision_wasm_nosimd_internal.js", "wasm/vision_wasm_nosimd_internal.wasm",
];
RENDERERS.hand = async () => {
  const id="hand";
  try{
    const results = await Promise.all(HAND_FILES.map(async f => {
      try{ const r = await fetch("/lib/mediapipe/"+f, {method:"HEAD"});
        return {f, ok:r.ok, bytes:Number(r.headers.get("Content-Length")||0)};
      }catch(e){ return {f, ok:false, bytes:0}; }
    }));
    const have=results.filter(r=>r.ok), missing=results.filter(r=>!r.ok);
    body(id, `
      <h2>Hand mode</h2>
      <p class="lede">Camera hand tracking, straight from the browser. It needs six files beside the page — about 26 MB of
      Google's models — because they are too big to sit inside the dashboard file.</p>
      <div class="card">
        <h4>Models</h4>
        <table><tbody>${results.map(r=>`<tr>
          <td class="mono">${esc(r.f)}</td>
          <td>${r.ok?'<span class="pill good">present</span>':'<span class="pill warn">missing</span>'}</td>
          <td class="sub">${r.bytes?nf(r.bytes/1024,0)+" kB":""}</td></tr>`).join("")}</tbody></table>
        ${missing.length? `
          <p class="sub" style="margin-top:10px">Fetch them with (run on the Mac):</p>
          <pre>bash ~/mirai-src/mission-control/scripts/fetch-mediapipe.sh</pre>` :
          `<p class="sub" style="margin-top:10px">All six are in place — open Hand mode on the designed page and press
          “Start the camera”.</p>`}
      </div>
      <div class="notice">Hand mode belongs to the designed dashboard: it is the page that embeds itself as
      <code>index.html?holo=1</code> and draws with three.js. This console tells you whether the models are where the page
      will look for them, which is the only part the backend can check.</div>`);
  }catch(e){ fail(id,e); }
};

/* ---------------------------- Integrations ------------------------------- */
RENDERERS.integrations = async () => {
  const id="integrations";
  try{
    const a = await api("/api/agents");
    const g = a.gateway||a.gateways||null;
    body(id, `
      <h2>Integrations</h2>
      <p class="lede">What the crew is plugged into, and where each plug lives. MIRAI reads these; it configures none of them
      except the files a person edits.</p>
      <div class="grid g2">
        <div class="card"><h4>Gateway</h4>
          <pre>${esc(JSON.stringify(g||(a.status&&a.status.gateway)||{state:"unknown", note:"not reported by /api/agents on this build"},null,2))}</pre>
          <div class="sub">Gateway milik Hermes. Jendela ini hanya lampu hidup/mati — tidak ada tombol restart di sini.</div></div>
        <div class="card"><h4>Platforms</h4>
          <table><tbody>
            <tr><td>Telegram</td><td class="sub">satu bot, sepuluh topik. Router = config.yaml. Plugin MIRAI OFF.</td></tr>
            <tr><td>Cron</td><td class="sub">the crew's own scheduler — <code>~/wiki/_wiki-health.md</code> carries the heartbeats</td></tr>
            <tr><td>Voice</td><td class="sub">local service on 127.0.0.1:8768, ElevenLabs when configured — see the Voice page</td></tr>
            <tr><td>Board</td><td class="sub">${esc(a.mode||"local")} mode${a.board? " · "+esc(a.board):""}</td></tr>
          </tbody></table></div>
      </div>
      <div class="notice">Anything that speaks to the outside world is configured in the crew's own files, never here. That is
      deliberate: a control panel that could silently re-point the crew at a different account is a control panel nobody
      should trust.</div>`);
  }catch(e){ fail(id,e); }
};

/* ------------------------------ Settings --------------------------------- */
RENDERERS.settings = async () => {
  const id="settings";
  try{
    const s = await api("/api/settings");
    const c = s.settings||{};
    body(id, `
      <h2>Settings</h2>
      <p class="lede">Four values, and the set is closed. Anything else the dashboard wants to store gets its own table, not a
      key here.</p>
      <div class="grid g2">
        <div class="card"><h4>You</h4>
          <label>Display name (≤ 24 characters; falls back to the crew's name for you)</label>
          <input id="st-name" value="${esc(c.display_name||"")}" placeholder="${esc(c.operator_name||"")}">
          <label>Timezone (a zone Python's zoneinfo knows)</label>
          <input id="st-tz" value="${esc(c.timezone||"UTC")}" list="tzlist">
          <datalist id="tzlist">${["UTC","Asia/Jakarta","Asia/Makassar","Asia/Singapore","Asia/Tokyo","Australia/Sydney","Europe/London","Europe/Berlin","America/New_York","America/Los_Angeles"].map(z=>`<option value="${z}">`).join("")}</datalist>
          <label>Voice engine</label>
          <select id="st-ve">${["local","studio","both"].map(v=>`<option${v===c.voice_engine?" selected":""}>${v}</option>`).join("")}</select>
          <div class="row end" style="margin-top:12px"><button class="btn pri" id="st-save">Save</button></div>
        </div>
        <div class="card"><h4>What the crew calls you</h4>
          <div class="row"><span class="pill info">${esc(c.operator_name||"—")}</span>
            <span class="sub">read only, from the crew's own files</span></div>
          <p class="sub" style="margin-top:10px">This is the name in <code>~/.hermes/memories/USER.md</code>. It is theirs, not
          MIRAI's, which is why a POST that includes it is refused rather than obeyed. Teach the crew your name once and it
          appears here.</p>
          <h4 style="margin-top:16px">Server</h4>
          <div class="row"><button class="btn" id="st-ping">Ping</button>
            <span class="sub" id="st-ping-out">—</span></div>
          <div class="sub" style="margin-top:8px">Bound to 127.0.0.1 only. Restart with
            <code>bash ~/mirai-src/mission-control/scripts/restart.sh</code>.</div>
        </div>
      </div>
      <h3>What is stored where</h3>
      <div class="card"><table><tbody>
        <tr><td>MIRAI's own state</td><td class="mono">~/mirai/data/mirai.db</td><td class="sub">missions, docs index, sessions, settings, audit</td></tr>
        <tr><td>Secrets</td><td class="mono">~/mirai/data/secrets.env</td><td class="sub">0600, excluded from backups by name</td></tr>
        <tr><td>The crew</td><td class="mono">~/.hermes</td><td class="sub">read only, except the cron store, the editable files, and a new hire's login</td></tr>
        <tr><td>Screenshots / files</td><td class="mono">~/mirai/data/files/</td><td class="sub">confined: a path that tries to leave is refused</td></tr>
      </tbody></table></div>`);
    $("#st-save").onclick = async () => {
      try{ await api("/api/settings",{method:"POST",body:{settings:{
        display_name:$("#st-name").value.trim(), timezone:$("#st-tz").value.trim(), voice_engine:$("#st-ve").value}}});
        toast("settings saved"); refreshHeader(); }
      catch(e){ toast(e.message,false); } };
    $("#st-ping").onclick = async () => {
      try{ const r=await api("/api/ping"); $("#st-ping-out").textContent = `up ${nf(r.uptime_s,1)}s`; }
      catch(e){ $("#st-ping-out").textContent = e.message; } };
  }catch(e){ fail(id,e); }
};

/* ------------------------------- Boot ------------------------------------ */
async function boot(){
  buildShell();
  try{
    await api("/api/agents");           // the pulse: two failures and the shell says so
  }catch(e){
    toast("MIRAI is out of reach: "+e.message, false);
  }
  await refreshHeader();
  show("cockpit");
  setInterval(async () => {          // cockpit numbers stay fresh without a reload
    if(CURRENT!=="cockpit") return;
    RENDERED.delete("cockpit"); await show("cockpit");
  }, 45000);
}
boot();
