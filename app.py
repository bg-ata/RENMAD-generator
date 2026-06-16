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

# One tile per tool: title + a single line. The detail lives inside each tool.
# A 2×2 grid keeps the cards roomy; align-items:stretch makes each row's pair
# match height so the buttons line up.
st.markdown(
    "<style>div[data-testid='stHorizontalBlock']{align-items:stretch;}"
    "div[data-testid='stVerticalBlockBorderWrapper']{height:100%;}</style>",
    unsafe_allow_html=True,
)

TILES = [
    ("🎤 Webinar", "Promo images for a single webinar.",
     "Open Webinar", "pages/1_🎤_Webinar.py", "goto_webinar"),
    ("📅 Event", "Full-event images — Ingo, sponsor banners, logo wall.",
     "Open Event", "pages/2_📅_Event.py", "goto_event"),
    ("🎬 Title slides", "Session title slides from an agenda — marketing or event.",
     "Open Title slides", "pages/4_🎬_Title_slides.py", "goto_titleslides"),
    ("📊 Reports", "Post-webinar audience report as a branded PPTX.",
     "Open Reports", "pages/3_📊_Reports.py", "goto_reports"),
]

for row_start in (0, 2):
    cols = st.columns(2, gap="large")
    for col, (title, blurb, btn, page, key) in zip(cols, TILES[row_start:row_start + 2]):
        with col:
            with st.container(border=True):
                st.markdown(f"### {title}\n{blurb}")
                if st.button(f"{btn} →", type="primary",
                             use_container_width=True, key=key):
                    st.switch_page(page)
