/* RENMAD Agenda — cloud mode, stored in the RENMAD Dispatch Center's Supabase.
   Loaded LAST, so it overrides the app's local-storage functions with online ones.
   - Login: the Dispatch Center's. The Tools page frames this app with ?dc_token=<access
     token>&dc_refresh=<refresh token>; every request goes out AS that colleague, so the
     table's RLS (dc_agendas: Dispatch roster only, anon gets nothing) does the gating.
   - The access token lives ~1h; dc_refresh mints a fresh one before it dies, so an agenda
     left open all afternoon still saves (same pattern as the Proposal Builder's dc_auth.py).
   - "Last edited by" is stamped server-side by dc_stamp() from the signed-in user.
   - Live: realtime refresh so colleagues see each other's agendas appear/update.
   Until 19 Oct 2026 the agendas lived in a separate project (timedagenda). */
(function(){
  if(!window.DC_SUPA_URL || !window.DC_SUPA_ANON || !window.supabase){ return; }
  const TABLE = "dc_agendas";
  const qs = new URLSearchParams(location.search);
  let TOKEN = qs.get("dc_token")||"", REFRESH = qs.get("dc_refresh")||"";
  const host = location.hostname;
  // Local dev with no Dispatch token: stay out of the way, the app runs on localStorage.
  if(!TOKEN && (host==="localhost" || host==="127.0.0.1" || host==="")){ return; }

  const jwtExp = t=>{ try{ return JSON.parse(atob(t.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).exp||0; }catch(e){ return 0; } };
  let refreshing = null;
  async function freshToken(){
    if(TOKEN && jwtExp(TOKEN) - Date.now()/1000 > 120) return TOKEN;
    if(!REFRESH) return TOKEN;
    if(!refreshing){
      refreshing = (async ()=>{
        try{
          const r = await fetch(window.DC_SUPA_URL+"/auth/v1/token?grant_type=refresh_token",
            { method:"POST", headers:{ apikey:window.DC_SUPA_ANON, "Content-Type":"application/json" }, body:JSON.stringify({ refresh_token:REFRESH }) });
          if(r.ok){ const j = await r.json(); if(j.access_token) TOKEN = j.access_token; if(j.refresh_token) REFRESH = j.refresh_token; }  // refresh tokens rotate
        }catch(e){}
        refreshing = null;
      })();
    }
    await refreshing;
    return TOKEN;
  }
  const sb = window.supabase.createClient(window.DC_SUPA_URL, window.DC_SUPA_ANON, { accessToken: freshToken });
  let CLOUD = [];                 // cache of all agendas: {id,name,updated,data,by}
  let CURRENT_EMAIL = "";
  const newId = ()=> (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : (Date.now()+"-"+Math.round(performance.now()*1000));

  // ── overlay (login / loading) ─────────────────────────────────────────────
  const ov = document.createElement("div");
  ov.id = "cloudOverlay";
  ov.style.cssText = "position:fixed;inset:0;z-index:2147483646;background:#1c2529;color:#fff;display:flex;align-items:center;justify-content:center;font-family:'Open Sans',Arial,sans-serif";
  document.body.appendChild(ov);
  const cardCSS = "background:#fff;color:#1c2529;max-width:430px;width:90%;padding:30px 28px;border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.4)";
  const inpCSS  = "width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #d9dce0;border-radius:8px;font-size:15px;margin-bottom:10px";
  const btnCSS  = "background:#E0392B;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;font-size:15px;cursor:pointer;width:100%";
  function showLoading(msg){ ov.style.display="flex"; ov.innerHTML='<div style="'+cardCSS+';text-align:center"><div style="font-weight:800;font-size:18px;margin-bottom:8px">RENMAD Agenda</div><div style="color:#5a616a">'+(msg||"Loading…")+'</div></div>'; }
  // Access wall: this app opens only from the Dispatch Center's Tools page.
  function showWall(){
    ov.style.display="flex";
    ov.innerHTML='<div style="'+cardCSS+'">'
      +'<div style="font-weight:800;font-size:20px;margin-bottom:2px">RENMAD <span style="color:#E0392B">Dispatch Center</span></div>'
      +'<div style="color:#5a616a;margin:12px 0 16px;font-size:14px">This tool opens from the Dispatch Center’s <b>Tools</b> page — it can’t be used from a direct link. If you came from Tools and see this, your session may have expired: go back and click the tile again.</div>'
      +'<a href="'+esc(window.DC_TOOLS_URL||"#")+'" style="'+btnCSS+';display:block;text-align:center;text-decoration:none;box-sizing:border-box">Open the Dispatch Center → Tools</a>'
      +'</div>';
  }
  // Validate the Dispatch Center token → the signed-in colleague's email, or null.
  async function validateDispatch(token){
    if(!token || !window.DC_SUPA_URL || !window.DC_SUPA_ANON) return null;
    try{
      const r=await fetch(window.DC_SUPA_URL+"/auth/v1/user",{ headers:{ apikey:window.DC_SUPA_ANON, Authorization:"Bearer "+token } });
      if(r.ok){ const j=await r.json(); return (j&&j.email)||null; }
    }catch(e){}
    return null;
  }
  function hideOverlay(){ ov.style.display="none"; }

  // ── cloud store: overrides the app's local functions (same names) ──────────
  async function refreshCloud(){
    const { data, error } = await sb.from(TABLE).select("id,title,data,updated_at,updated_by");
    if(error){ console.warn("load failed", error); return false; }
    CLOUD = (data||[]).map(r=>({ id:r.id, name:r.title||((r.data&&r.data.titleA)||"Untitled"), updated:Date.parse(r.updated_at)||0, data:r.data||{}, by:r.updated_by||"" }));
    return true;
  }
  function setSyncCloud(state){ const e=document.getElementById("syncDot"); if(!e) return; e.style.display="inline"; const m={saving:["⏳ saving…","#8a9098"],saved:["✓ saved online","#2e7d32"],error:["⚠ not saved","#c0392b"]}[state]||["",""]; e.textContent=m[0]; e.style.color=m[1]; }
  let cloudTimer;
  function installCloudStore(){
    homeTab="mine";                 // single shared list (no My/Team split in cloud mode)
    homeTabs   = function(){ return ""; };
    bindHomeTabs = function(){};
    loadProjects = function(){ return CLOUD; };
    saveProjects = function(){};    // writes go through autosave/upsert instead
    scheduleTeamSync = function(){};

    // data.slides = the same session list the Slides JSON button exports, so the
    // Dispatch's Event Decks page (🎬 Title slides) never re-implements timings/speakers.
    async function saveNow(){
      let slides=null; try{ slides=buildSlideJson(); }catch(e){}
      const row={ id:curId, title:(S.titleA||"Untitled event"), data:Object.assign({},S,{slides:slides}), updated_at:new Date().toISOString(), updated_by:CURRENT_EMAIL };
      const { error } = await sb.from(TABLE).upsert(row, { onConflict:"id" });
      if(error){ setSyncCloud("error"); toast("⚠ Couldn’t save online — check your connection"); throw error; }
      const rec={ id:curId, name:row.title, updated:Date.now(), data:S, by:CURRENT_EMAIL };
      const i=CLOUD.findIndex(p=>p.id===curId); if(i>=0) CLOUD[i]=rec; else CLOUD.push(rec);
      setSyncCloud("saved");
    }
    autosave = function(){
      clearTimeout(cloudTimer); setSyncCloud("saving");
      cloudTimer=setTimeout(()=>{ saveNow().catch(()=>{}); }, 800);
    };
    window.agFlush = function(){ clearTimeout(cloudTimer); setSyncCloud("saving"); return saveNow(); };
    window.agFetchEvents = async function(){
      const { data, error } = await sb.from("dc_events").select("id,name,topic,city,country,date,days,kind,ecode,deleted");
      if(error) throw error; return data||[];
    };
    newProject = function(){ S=blankState(); curId=newId(); view={type:"overview"}; render(); autosave(); toast("New agenda — give it a title in Event details"); };
    openProjectId = function(id){ const p=CLOUD.find(x=>x.id===id); if(!p) return; S=p.data; normalize(); curId=id; if(typeof closeModal==="function") closeModal(); view=(S.days&&S.days.length)?{type:"day",id:S.days[0].id}:{type:"overview"}; render(); };
    deleteProjectId = async function(id){
      const { error } = await sb.from(TABLE).delete().eq("id", id);
      if(error){ toast("Could not delete: "+(error.message||error)); return; }
      CLOUD = CLOUD.filter(x=>x.id!==id);
      if(curId===id){ if(CLOUD.length){ openProjectId(CLOUD.slice().sort((a,b)=>b.updated-a.updated)[0].id); } else { newProject(); } } else { render(); }
    };
    importFile = function(file){ const rd=new FileReader(); rd.onload=()=>{ try{ const data=JSON.parse(rd.result); S=data; normalize(); curId=newId(); if(typeof closeModal==="function") closeModal(); view={type:"overview"}; render(); autosave(); toast("Imported into the team library"); }catch(e){ toast("Could not read that file"); } }; rd.readAsText(file); };
  }

  function userChip(email){
    let c=document.getElementById("cloChip");
    if(!c){ c=document.createElement("div"); c.id="cloChip"; c.style.cssText="position:fixed;bottom:10px;left:12px;z-index:60;background:#fff;border:1px solid #e6e8ec;border-radius:20px;padding:5px 10px;font:600 12px 'Open Sans',Arial;color:#5a616a;box-shadow:0 2px 10px rgba(0,0,0,.08);display:flex;gap:8px;align-items:center"; document.body.appendChild(c); }
    c.innerHTML='👤 '+esc(email)+' <a href="'+esc(window.DC_TOOLS_URL||"#")+'" id="cloOut" style="color:#E0392B;text-decoration:none;font-weight:700">Tools</a>';
  }
  function subscribeRealtime(){
    try{ sb.channel("agendas-live").on("postgres_changes",{event:"*",schema:"public",table:TABLE}, async ()=>{ await refreshCloud(); if(view && view.type==="home") render(); }).subscribe(); }catch(e){}
  }

  async function proceed(){
    installCloudStore();
    showLoading("Loading agendas…");
    // a failed load must never look like an empty library (someone would start over)
    if(!await refreshCloud()){ showWall(); return; }
    const arr=CLOUD.slice().sort((a,b)=>b.updated-a.updated);
    if(arr.length){ S=arr[0].data; normalize(); curId=arr[0].id; } else { S=blankState(); curId=newId(); }
    view={type:"home"}; render();
    userChip(CURRENT_EMAIL); hideOverlay(); subscribeRealtime();
  }

  // ── boot ──────────────────────────────────────────────────────────────────
  async function start(){
    showLoading("Loading…");
    // Require a valid Dispatch Center token (added by the Tools tile).
    const email=await validateDispatch(await freshToken());
    if(!email){ showWall(); return; }
    CURRENT_EMAIL=email;
    try{ localStorage.setItem("renmad_user_email", email); }catch(e){}
    try{ const u=new URL(location.href); u.searchParams.delete("dc_token"); u.searchParams.delete("dc_refresh"); history.replaceState(null,"",u.toString()); }catch(e){}  // tidy the URL
    proceed();
  }
  start();
})();
