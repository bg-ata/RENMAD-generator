# -*- coding: utf-8 -*-
"""Dispatch Center gate — this app only opens from the RENMAD Dispatch Center.

The Tools page (bg-ata.github.io/dispatch-center) frames the app and appends
the logged-in colleague's Supabase access token as ?dc_token=… . We validate
that token once per browser session against the Dispatch Center's Supabase
Auth; without a valid token the app shows a wall instead of running.

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


def require_dispatch_login():
    """Call right after st.set_page_config on every page. Returns the
    colleague's email (or 'local' in dev), else renders a wall and stops."""
    if st.session_state.get("_dc_user"):
        return st.session_state["_dc_user"]
    if _gate_off():
        st.session_state["_dc_user"] = "local"
        return "local"

    token = st.query_params.get("dc_token", "")
    email = None
    if token:
        try:
            r = requests.get(
                DC_SUPABASE_URL + "/auth/v1/user",
                headers={"apikey": DC_ANON_KEY,
                         "Authorization": "Bearer " + token},
                timeout=8,
            )
            if r.status_code == 200:
                email = (r.json() or {}).get("email")
        except Exception:
            email = None

    if email:
        st.session_state["_dc_user"] = email
        try:
            del st.query_params["dc_token"]  # tidy the visible URL
        except Exception:
            pass
        return email

    # ---- wall ----
    st.markdown(
        """
        <div style="max-width:460px;margin:60px auto;font-family:'Segoe UI',sans-serif;
                    background:#fff;border:1px solid #e3e1da;border-radius:14px;padding:28px 30px">
          <div style="font-size:20px;font-weight:700;color:#2B2B2B">
            RENMAD <span style="color:#FF4A00">Dispatch Center</span></div>
          <p style="color:#3a3a3a;font-size:14px;margin:12px 0 4px">
            This tool opens from the Dispatch Center's <b>Tools</b> page —
            it can't be used from a direct link.</p>
          <p style="color:#7c7c78;font-size:12.5px;margin:0">
            If you got here from the Tools page, your session may have expired:
            go back and click the tile again.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button("Open the Dispatch Center → Tools", DC_TOOLS_URL)
    st.stop()
