// RENMAD Agenda — cloud connection settings.
// Agendas live in the RENMAD Dispatch Center's Supabase (table dc_agendas) since
// 19 Oct 2026. The Tools page frames this app and appends the signed-in colleague's
// tokens as ?dc_token=…&dc_refresh=…; every request goes out as that colleague and the
// table's row-level rules let only the Dispatch roster in. These are the Dispatch
// Center's PUBLIC client credentials (same as its store.js) — no secret is exposed here.
window.DC_SUPA_URL  = "https://dxgvbufsifgowwfggvmr.supabase.co";
window.DC_SUPA_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4Z3ZidWZzaWZnb3d3Zmdndm1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0ODM1OTUsImV4cCI6MjA5ODA1OTU5NX0.EDMWWjMuDM0jS0d0SwzdhuW_ZnHP0T0kqwL3xc6Cw-w";
window.DC_TOOLS_URL = "https://bg-ata.github.io/dispatch-center/tools.html";
