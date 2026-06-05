# -*- coding: utf-8 -*-
"""
RENMAD Content Generator — landing page.

Three tools live inside:
  • 🎤 Webinar  — marketing material for a single webinar session
  • 📅 Event    — full-event marketing pack (banners per sponsor / partner)
  • 📊 Reports  — post-webinar marketing & audience report (paid webinars)
"""
import os
import streamlit as st

st.set_page_config(page_title="RENMAD Content Generator", page_icon="🎨", layout="wide")

# ── ATA logo + sidebar ───────────────────────────────────────────────────────
_LOGO_DIR = os.path.join(os.path.dirname(__file__), "assets", "logos")
_ata_logo = os.path.join(_LOGO_DIR, "ata_logo.png")
if os.path.exists(_ata_logo):
    st.sidebar.image(_ata_logo, width=140)
st.sidebar.title("RENMAD Generator")
st.sidebar.caption("Switch between **Webinar**, **Event** and **Reports** above.")

# ── Main landing ─────────────────────────────────────────────────────────────
st.title("🎨 RENMAD Content Generator")
st.markdown("##### Pick a tool")
st.write("")

col_a, col_b, col_c = st.columns(3, gap="large")

with col_a:
    with st.container(border=True):
        st.markdown(
            """
### 🎤 Webinar
Marketing assets for **one webinar session**.

- Title slide (PNG + editable PPTX)
- LinkedIn post · miniature · Ingo templates
"""
        )
        if st.button("Open Webinar →", type="primary", use_container_width=True, key="goto_webinar"):
            st.switch_page("pages/1_🎤_Webinar.py")

with col_b:
    with st.container(border=True):
        st.markdown(
            """
### 📅 Event
Marketing pack for a **multi-day event**.

- 4 banners per sponsor / partner
- Add sponsors as they come in, regenerate just the new
"""
        )
        if st.button("Open Event →", type="primary", use_container_width=True, key="goto_event"):
            st.switch_page("pages/2_📅_Event.py")

with col_c:
    with st.container(border=True):
        st.markdown(
            """
### 📊 Reports
**Marketing & audience report** for a paid webinar.

- Branded editable PPTX (EN · ES · IT · PL)
- From the webinar link + registration & Zoom CSVs
"""
        )
        if st.button("Open Reports →", type="primary", use_container_width=True, key="goto_reports"):
            st.switch_page("pages/3_📊_Reports.py")

st.write("")
st.caption("💡 All three are also in the sidebar.")
