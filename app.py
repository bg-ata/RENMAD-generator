# -*- coding: utf-8 -*-
"""
RENMAD Content Generator — landing page.

Two tools live inside:
  • 🎤 Webinar  — single-session marketing (slide + LinkedIn + miniature + Ingo)
  • 📅 Event    — full-event marketing pack (4 banners per sponsor / partner)

Pick what you need below and Streamlit takes you to the right page.
"""
import os
import streamlit as st

st.set_page_config(
    page_title="RENMAD Content Generator",
    page_icon="🎨",
    layout="wide",
)

# ── ATA logo at the top of the sidebar ───────────────────────────────────────
_LOGO_DIR = os.path.join(os.path.dirname(__file__), "assets", "logos")
_ata_logo = os.path.join(_LOGO_DIR, "ata_logo.png")
if os.path.exists(_ata_logo):
    st.sidebar.image(_ata_logo, width=140)

st.sidebar.title("RENMAD Generator")
st.sidebar.caption(
    "Use the navigation above to switch between **Webinar** and **Event**."
)


# ── Main landing ─────────────────────────────────────────────────────────────
st.title("🎨 RENMAD Content Generator")
st.markdown(
    """
##### Choose what you need to create

This tool covers two distinct marketing workflows. Pick the one that matches
what you're working on:
"""
)

st.write("")   # vertical spacer

col_a, col_b = st.columns(2, gap="large")

with col_a:
    with st.container(border=True):
        st.markdown(
            """
### 🎤 Webinar
**One-off online webinar**

Generate the marketing material for a single webinar session in minutes:

- 🎨 **Slide** — full title slide (PNG + editable PPTX)
- 💼 **LinkedIn** — square share post
- 🖼️ **Miniature** — website / email-header card
- 🌐 **Ingo** — speaker + attendee LinkedIn templates

Paste the speaker line-up from email/Notion, click Generate, download.
"""
        )
        if st.button("Open Webinar generator →", type="primary",
                     use_container_width=True, key="goto_webinar"):
            st.switch_page("pages/1_🎤_Webinar.py")

with col_b:
    with st.container(border=True):
        st.markdown(
            """
### 📅 Event
**Multi-day in-person event** (≈ 5 per year)

Bulk marketing material for the whole event:

- 4 personalised banners per **sponsor / partner** (EN + event language, horizontal + square)
- Single calendar picker for event dates
- Persistent: add new sponsors as they come in, regenerate just the new one
- 🌐 Ingo + 🏛️ Logo wall (coming soon)

Paste Company + Role from Excel, upload logos, click Generate, ship.
"""
        )
        if st.button("Open Event generator →", type="primary",
                     use_container_width=True, key="goto_event"):
            st.switch_page("pages/2_📅_Event.py")


st.write("")
st.caption(
    "💡 Tip: also accessible at any time via the sidebar navigation."
)
