# -*- coding: utf-8 -*-
"""
RENMAD Content Generator — landing page.

Four tools live inside:
  • 🎤 Webinar      — promo images for a single webinar session
  • 📅 Event        — event images: Ingo, Marketing partners (sponsor banners), or Logo wall
  • 🎬 Title slides — agenda → on-screen / marketing title slides (editable PPTX)
  • 📊 Reports      — post-webinar audience report (branded PPTX from Zoom CSVs)
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
st.sidebar.caption("Pick a tool here or on the home page.")

# ── Main landing ─────────────────────────────────────────────────────────────
st.title("🎨 RENMAD Content Generator")
st.markdown("On-brand marketing images for RENMAD webinars and events. Pick a tool:")
st.write("")

# Equal-height cards with the button pinned to the bottom, so the four tiles
# line up regardless of how much copy each one has.
st.markdown(
    """
    <style>
    div[data-testid="stHorizontalBlock"] { align-items: stretch; }
    div[data-testid="stVerticalBlockBorderWrapper"] { height: 100%; }
    div[data-testid="stVerticalBlockBorderWrapper"] > div { height: 100%; }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlock"] {
        height: 100%; display: flex; flex-direction: column;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stButton"] {
        margin-top: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_a, col_b, col_c, col_d = st.columns(4, gap="large")

with col_a:
    with st.container(border=True):
        st.markdown(
            """
### 🎤 Webinar
Promo images for **one webinar**.

- Title slide (editable PPTX)
- LinkedIn, miniature & Ingo images
"""
        )
        if st.button("Open Webinar →", type="primary", use_container_width=True, key="goto_webinar"):
            st.switch_page("pages/1_🎤_Webinar.py")

with col_b:
    with st.container(border=True):
        st.markdown(
            """
### 📅 Event
Images for a **full event** — pick one to make:

- 📸 **Ingo** — event infographic (ES + EN)
- 🎨 **Marketing partners** — 4 banners per sponsor
- 🖼️ **Logo wall** — all sponsors by tier
"""
        )
        if st.button("Open Event →", type="primary", use_container_width=True, key="goto_event"):
            st.switch_page("pages/2_📅_Event.py")

with col_c:
    with st.container(border=True):
        st.markdown(
            """
### 🎬 Title slides
Session **title slides** from an agenda (editable PPTX).

- 📣 **Marketing** — title top, 2 decks
- 🎤 **Event** — title bottom + transitions
"""
        )
        if st.button("Open Title slides →", type="primary", use_container_width=True, key="goto_titleslides"):
            st.switch_page("pages/4_🎬_Title_slides.py")

with col_d:
    with st.container(border=True):
        st.markdown(
            """
### 📊 Reports
**Audience report** after a webinar.

- Branded PPTX (EN · ES · IT · PL)
- Built from the webinar link + Zoom CSVs
"""
        )
        if st.button("Open Reports →", type="primary", use_container_width=True, key="goto_reports"):
            st.switch_page("pages/3_📊_Reports.py")
