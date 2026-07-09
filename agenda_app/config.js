// RENMAD Agenda — cloud connection settings.
// The publishable key is meant to be public (security is enforced by the passcode +
// the row-level rules in supabase_setup.sql). The actual passcode is NOT here — it's the
// password you set on the shared SUPA_SHARED_EMAIL account in Supabase, known only to the team.
window.SUPA_URL          = "https://abxsnwmjbcnhjhzydqii.supabase.co";
window.SUPA_KEY          = "sb_publishable_dJOHQcN4hTkrXs0it2fZYw_zrvNPADo";
window.SUPA_DOMAIN       = "ata.email";            // people identify themselves with an @ata.email address
window.SUPA_SHARED_EMAIL = "agenda@ata.email";     // (legacy) the shared account the old team passcode unlocked

// Access is now the RENMAD Dispatch Center login: the Tools page frames this app
// and appends the signed-in colleague's token as ?dc_token=…, which we validate
// against the Dispatch Center's Supabase Auth. These are the Dispatch Center's
// PUBLIC client credentials (same as its store.js) — no secret is exposed here.
window.DC_SUPA_URL  = "https://dxgvbufsifgowwfggvmr.supabase.co";
window.DC_SUPA_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4Z3ZidWZzaWZnb3d3Zmdndm1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0ODM1OTUsImV4cCI6MjA5ODA1OTU5NX0.EDMWWjMuDM0jS0d0SwzdhuW_ZnHP0T0kqwL3xc6Cw-w";
window.DC_TOOLS_URL = "https://bg-ata.github.io/dispatch-center/tools.html";
