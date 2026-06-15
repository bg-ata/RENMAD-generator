/* RENMAD Agenda — cloud mode.
   Loaded LAST, so it overrides the app's local-storage functions with online ones.
   - Login: passwordless email link, restricted to @ata.email.
   - Storage: one shared Supabase table = one place online for the whole team.
   - Live: realtime refresh so colleagues see each other's agendas appear/update.
   If config is missing, it stays out of the way and the app runs in local mode. */
(function(){
  if(!window.SUPA_URL || !window.SUPA_KEY || !window.supabase){ return; } // not configured → local mode
  const DOMAIN = (window.SUPA_DOMAIN||"ata.email").toLowerCase();
  const sb = window.supabase.createClient(window.SUPA_URL, window.SUPA_KEY, { auth:{ persistSession:true, detectSessionInUrl:true, autoRefreshToken:true } });
  const REDIRECT = location.origin + location.pathname;   // come back to this exact app page after the email link
  let CLOUD = [];                 // cache of all agendas: {id,name,updated,data,by}
  let CURRENT_EMAIL = "";
  const newId = ()=> (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : (Date.now()+"-"+Math.round(performance.now()*1000));

  // ── overlay (login / loading / denied) ────────────────────────────────────
  const ov = document.createElement("div");
  ov.id = "cloudOverlay";
  ov.style.cssText = "position:fixed;inset:0;z-index:2147483646;background:#1c2529;color:#fff;display:flex;align-items:center;justify-content:center;font-family:'Open Sans',Arial,sans-serif";
  document.body.appendChild(ov);
  const cardCSS = "background:#fff;color:#1c2529;max-width:420px;width:90%;padding:30px 28px;border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.4)";
  const btnCSS = "background:#E0392B;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;font-size:15px;cursor:pointer;width:100%";
  function showLoading(msg){ ov.style.display="flex"; ov.innerHTML='<div style="'+cardCSS+';text-align:center"><div style="font-weight:800;font-size:18px;margin-bottom:8px">RENMAD Agenda</div><div style="color:#5a616a">'+(msg||"Loading…")+'</div></div>'; }
  function showDenied(email){ ov.style.display="flex"; ov.innerHTML='<div style="'+cardCSS+'"><div style="font-weight:800;font-size:18px;margin-bottom:6px">Not allowed</div><p style="color:#5a616a">The address <b>'+esc(email)+'</b> isn’t an @'+esc(DOMAIN)+' account, so it can’t access the team agendas.</p><button id="cloLogout" style="'+btnCSS+';background:#5a616a;margin-top:8px">Sign out & try another email</button></div>'; document.getElementById("cloLogout").onclick=()=>sb.auth.signOut().then(()=>location.reload()); }
  function showLogin(prefill){
    ov.style.display="flex";
    ov.innerHTML='<div style="'+cardCSS+'">'
      +'<div style="font-weight:800;font-size:20px;margin-bottom:2px">RENMAD Agenda</div>'
      +'<div style="color:#5a616a;margin-bottom:18px;font-size:14px">Sign in with your ATA email — we’ll send you a one-click link, no password needed.</div>'
      +'<input id="cloEmail" type="email" placeholder="you@'+esc(DOMAIN)+'" value="'+esc(prefill||"")+'" style="width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #d9dce0;border-radius:8px;font-size:15px;margin-bottom:10px">'
      +'<button id="cloSend" style="'+btnCSS+'">Email me a login link</button>'
      +'<div id="cloMsg" style="margin-top:12px;font-size:13px;color:#5a616a;min-height:18px"></div>'
      +'</div>';
    const inp=document.getElementById("cloEmail"), btn=document.getElementById("cloSend"), msg=document.getElementById("cloMsg");
    inp.focus();
    const send=async()=>{
      const email=(inp.value||"").trim();
      if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ msg.textContent="Please enter a valid email."; return; }
      if(!email.toLowerCase().endsWith("@"+DOMAIN)){ msg.style.color="#c0392b"; msg.textContent="Use your @"+DOMAIN+" work email."; return; }
      btn.disabled=true; msg.style.color="#5a616a"; msg.textContent="Sending…";
      const { error } = await sb.auth.signInWithOtp({ email, options:{ emailRedirectTo: REDIRECT } });
      btn.disabled=false;
      if(error){ msg.style.color="#c0392b"; msg.textContent=error.message; }
      else { msg.style.color="#2e7d32"; msg.innerHTML="✓ Check your inbox — click the link we sent to <b>"+esc(email)+"</b> to open the agendas. (You can close this tab.)"; }
    };
    btn.onclick=send; inp.onkeydown=(e)=>{ if(e.key==="Enter") send(); };
  }
  function hideOverlay(){ ov.style.display="none"; }

  // ── cloud store: overrides the app's local functions (same names) ──────────
  async function refreshCloud(){
    const { data, error } = await sb.from("agendas").select("id,title,data,updated_at,updated_by");
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

    autosave = function(){
      clearTimeout(cloudTimer); setSyncCloud("saving");
      cloudTimer=setTimeout(async ()=>{
        const row={ id:curId, title:(S.titleA||"Untitled event"), data:S, updated_at:new Date().toISOString(), updated_by:CURRENT_EMAIL };
        const { error } = await sb.from("agendas").upsert(row, { onConflict:"id" });
        if(error){ setSyncCloud("error"); toast("⚠ Couldn’t save online — check your connection"); return; }
        const rec={ id:curId, name:row.title, updated:Date.now(), data:S, by:CURRENT_EMAIL };
        const i=CLOUD.findIndex(p=>p.id===curId); if(i>=0) CLOUD[i]=rec; else CLOUD.push(rec);
        setSyncCloud("saved");
      }, 800);
    };
    newProject = function(){ S=blankState(); curId=newId(); view={type:"overview"}; render(); autosave(); toast("New agenda — give it a title in Event details"); };
    openProjectId = function(id){ const p=CLOUD.find(x=>x.id===id); if(!p) return; S=p.data; normalize(); curId=id; if(typeof closeModal==="function") closeModal(); view=(S.days&&S.days.length)?{type:"day",id:S.days[0].id}:{type:"overview"}; render(); };
    deleteProjectId = async function(id){
      const { error } = await sb.from("agendas").delete().eq("id", id);
      if(error){ toast("Could not delete: "+(error.message||error)); return; }
      CLOUD = CLOUD.filter(x=>x.id!==id);
      if(curId===id){ if(CLOUD.length){ openProjectId(CLOUD.slice().sort((a,b)=>b.updated-a.updated)[0].id); } else { newProject(); } } else { render(); }
    };
    importFile = function(file){ const rd=new FileReader(); rd.onload=()=>{ try{ const data=JSON.parse(rd.result); S=data; normalize(); curId=newId(); if(typeof closeModal==="function") closeModal(); view={type:"overview"}; render(); autosave(); toast("Imported into the team library"); }catch(e){ toast("Could not read that file"); } }; rd.readAsText(file); };
  }

  function userChip(email){
    let c=document.getElementById("cloChip");
    if(!c){ c=document.createElement("div"); c.id="cloChip"; c.style.cssText="position:fixed;bottom:10px;left:12px;z-index:60;background:#fff;border:1px solid #e6e8ec;border-radius:20px;padding:5px 10px;font:600 12px 'Open Sans',Arial;color:#5a616a;box-shadow:0 2px 10px rgba(0,0,0,.08);display:flex;gap:8px;align-items:center"; document.body.appendChild(c); }
    c.innerHTML='👤 '+esc(email)+' <a href="#" id="cloOut" style="color:#E0392B;text-decoration:none;font-weight:700">Sign out</a>';
    document.getElementById("cloOut").onclick=(e)=>{ e.preventDefault(); sb.auth.signOut(); };
  }
  function subscribeRealtime(){
    try{ sb.channel("agendas-live").on("postgres_changes",{event:"*",schema:"public",table:"agendas"}, async ()=>{ await refreshCloud(); if(view && view.type==="home") render(); }).subscribe(); }catch(e){}
  }

  // ── boot ──────────────────────────────────────────────────────────────────
  async function start(){
    showLoading("Signing you in…");
    let session=null;
    try{ session=(await sb.auth.getSession()).data.session; }catch(e){}
    if(!session){ showLogin(); return; }
    const email=(session.user && session.user.email)||"";
    if(!email.toLowerCase().endsWith("@"+DOMAIN)){ showDenied(email); return; }
    CURRENT_EMAIL=email;
    installCloudStore();
    showLoading("Loading agendas…");
    await refreshCloud();
    const arr=CLOUD.slice().sort((a,b)=>b.updated-a.updated);
    if(arr.length){ S=arr[0].data; normalize(); curId=arr[0].id; } else { S=blankState(); curId=newId(); }
    view={type:"home"}; render();
    userChip(email); hideOverlay(); subscribeRealtime();
  }
  sb.auth.onAuthStateChange((event)=>{ if(event==="SIGNED_OUT"){ location.reload(); } });
  start();
})();
