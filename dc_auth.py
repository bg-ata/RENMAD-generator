# -*- coding: utf-8 -*-
"""Dispatch Center gate — this app only opens from the RENMAD Dispatch Center.

The Tools page (bg-ata.github.io/dispatch-center) frames the app and appends
the logged-in colleague's Supabase access token as ?dc_token=… . We validate
that token once per browser session against the Dispatch Center's Supabase
Auth; without a valid token the app shows a wall instead of running.

`require_dispatch_login(require_tiers=(...))` additionally checks the person's
access tier in the Dispatch roster (dc_people) — used by the Proposals
Dashboard to admit only managers and above.

The URL + anon key below are the PUBLIC client credentials already shipped in
the Dispatch Center's own store.js — embedding them here exposes no new secret.

Local development bypass: put  [dc]\ngate = "off"  in .streamlit/secrets.toml
(git-ignored) and the gate lets you straight through.
"""
import requests
import streamlit as st

DC_SUPABASE_URL = "https://dxgvbufsifgowwfggvmr.supabase.co"
DC_ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
               "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR4Z3ZidWZzaWZnb3d3Zmdndm1yIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI0ODM1OTUsImV4cCI6MjA5ODA1OTU5NX0."
               "EDMWWjMuDM0jS0d0SwzdhuW_ZnHP0T0kqwL3xc6Cw-w")
DC_TOOLS_URL = "https://bg-ata.github.io/dispatch-center/tools.html"


def _gate_off() -> bool:
    try:
        return st.secrets.get("dc", {}).get("gate") == "off"
    except Exception:
        return False


def _email_of(token):
    try:
        r = requests.get(
            DC_SUPABASE_URL + "/auth/v1/user",
            headers={"apikey": DC_ANON_KEY, "Authorization": "Bearer " + token},
            timeout=8,
        )
        if r.status_code == 200:
            return (r.json() or {}).get("email")
    except Exception:
        pass
    return None


def _tier_of(token, email):
    """The person's access tier (member / manager / admin) from the Dispatch
    roster, read with their own token so row-level security is satisfied.
    Returns None if it can't be determined (caller fails closed)."""
    try:
        r = requests.get(
            DC_SUPABASE_URL + "/rest/v1/dc_people",
            headers={"apikey": DC_ANON_KEY, "Authorization": "Bearer " + token},
            params={"select": "access,deleted", "email": "eq." + email},
            timeout=8,
        )
        if r.status_code == 200:
            for row in (r.json() or []):
                if not row.get("deleted"):
                    return row.get("access") or "member"
    except Exception:
        pass
    return None


def _wall(restricted=False):
    if restricted:
        head = ("You’re signed in, but this tool is limited to "
                "<b>managers and above</b>.")
        msg = "If you think you should have access, ask Belén."
    else:
        head = ("This tool opens from the Dispatch Center's <b>Tools</b> "
                "page — it can’t be used from a direct link.")
        msg = ("If you got here from the Tools page, your session may have "
               "expired: go back and click the tile again.")
    st.markdown(
        """
        <div style="max-width:460px;margin:60px auto;font-family:'Segoe UI',sans-serif;
                    background:#fff;border:1px solid #e3e1da;border-radius:14px;padding:28px 30px">
          <div style="font-size:20px;font-weight:700;color:#2B2B2B">
            RENMAD <span style="color:#FF4A00">Dispatch Center</span></div>
          <p style="color:#3a3a3a;font-size:14px;margin:12px 0 4px">%s</p>
          <p style="color:#7c7c78;font-size:12.5px;margin:0">%s</p>
        </div>
        """ % (head, msg),
        unsafe_allow_html=True,
    )
    st.link_button("Open the Dispatch Center → Tools", DC_TOOLS_URL)


def require_dispatch_login(require_tiers=None):
    """Call right after st.set_page_config on every page. Returns the
    colleague's email (or 'local' in dev), else renders a wall and stops.
    If require_tiers is given (e.g. ("admin","manager")), the person must hold
    one of those Dispatch access tiers or they're shown a 'managers only' wall."""
    if st.session_state.get("_dc_user"):
        return st.session_state["_dc_user"]
    if _gate_off():
        st.session_state["_dc_user"] = "local"
        return "local"

    token = st.query_params.get("dc_token", "")
    email = _email_of(token) if token else None

    if email and require_tiers:
        tier = _tier_of(token, email)
        if tier not in require_tiers:          # unknown tier fails closed
            _wall(restricted=True)
            st.stop()

    if email:
        st.session_state["_dc_user"] = email
        try:
            del st.query_params["dc_token"]    # tidy the visible URL
        except Exception:
            pass
        return email

    _wall()
    st.stop()
