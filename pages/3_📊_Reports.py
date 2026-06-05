# -*- coding: utf-8 -*-
"""
📊 Webinar Reports — post-webinar marketing & audience report (paid webinars).

Separate from the Webinar (slide) tool: this produces the branded, editable
PPTX "Marketing & Audience Report" we send to the sponsor of a paid webinar.

Inputs a colleague provides:
  • the webinar link        → title, speakers, sponsor logo (auto)
  • registration CSV (CRM)  → countries, industries, companies, job titles
  • Zoom attendee CSV       → live attendance, retention, date, YouTube via link
  • email campaign numbers  → reach slide (manual)

The stats engine and page scraper are vendored into ./report_core so the app
runs anywhere (the design renderer is wired in at the Generate step next).
"""
import os
import sys
import tempfile

import streamlit as st

# ── report core (vendored into this repo so it runs anywhere) ────────────────
_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report_core")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)

_CORE_OK, _CORE_ERR = True, ""
try:
    from scraper.scrape import scrape_webinar
    from engine.ingest import build_stats
except Exception as e:                       # degrade gracefully, never crash the page
    _CORE_OK, _CORE_ERR = False, str(e)

LANGS = {"English": "en", "Español": "es", "Italiano": "it", "Polski": "pl"}

st.title("📊 Webinar Reports")
st.caption("Branded **Marketing & Audience Report** (editable PPTX) for a paid webinar.")

if not _CORE_OK:
    st.error("Report core not available: %s" % _CORE_ERR)
    st.stop()

# ── 1 · Webinar details (auto from the link) ─────────────────────────────────
st.subheader("1 · Webinar")
c1, c2 = st.columns([4, 1])
url = c1.text_input("Webinar link", placeholder="https://my.atainsights.com/webinar/…")
lang = c2.selectbox("Report language", list(LANGS.keys()))

if st.button("Fetch details", disabled=not url):
    with st.spinner("Reading the webinar page…"):
        try:
            st.session_state["scraped"] = scrape_webinar(url)
        except Exception as e:
            st.error("Couldn't read that page: %s" % e)

sc = st.session_state.get("scraped")
if sc:
    st.success("**%s**" % sc["title"])
    st.write("**Speakers** (edit/confirm companies before generating):")
    st.dataframe(
        [{"Name": s["name"], "Role": s["role"], "Company": s["company"] or "—",
          "Moderator": "✓" if s["is_moderator"] else ""} for s in sc["speakers"]],
        use_container_width=True, hide_index=True,
    )
    if sc.get("logos"):
        st.caption("Logos found: " + " · ".join(l.split("/uploads/")[-1] for l in sc["logos"]))

# ── 2 · Data files ───────────────────────────────────────────────────────────
st.subheader("2 · Data files")
d1, d2 = st.columns(2)
reg_csv = d1.file_uploader("Registration CSV (CRM export)", type=["csv"])
zoom_csv = d2.file_uploader("Zoom attendee CSV", type=["csv"])

if reg_csv and zoom_csv:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as fr:
            fr.write(reg_csv.getvalue()); reg_path = fr.name
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as fz:
            fz.write(zoom_csv.getvalue()); zoom_path = fz.name
        stats = build_stats(reg_path, zoom_path)
        st.session_state["stats"] = stats
        kf = stats["key_facts"]
        m = st.columns(5)
        m[0].metric("Registrations", f"{kf['registrations']:,}")
        m[1].metric("Companies", kf["companies"])
        m[2].metric("Countries", kf["countries"])
        m[3].metric("Live attendees", kf["live_attendees"])
        m[4].metric("Attendance", f"{kf['attendance_rate_pct']:.0f}%")
    except Exception as e:
        st.error("Could not read the CSVs: %s" % e)

# ── 3 · Marketing numbers (manual) ───────────────────────────────────────────
st.subheader("3 · Marketing numbers")
st.caption("Email campaign sends / opens / clicks (from the email platform). "
           "YouTube views are fetched automatically from the link.")
st.data_editor(
    [{"Campaign": "E-shot 1", "Sent": 0, "Opens": 0, "Clicks": 0}],
    num_rows="dynamic", use_container_width=True, key="email_rows",
)

# ── 4 · Options ──────────────────────────────────────────────────────────────
st.subheader("4 · Options")
o1, o2 = st.columns(2)
o1.toggle("Add 'highlights' notes (annotated version)", value=False, key="annotated")
o2.text_input("Contact", value="Cintia Hernández · cintia.hernandez@ata.email", key="contact")

# ── Generate ─────────────────────────────────────────────────────────────────
st.divider()
ready = bool(sc and st.session_state.get("stats"))
if st.button("Generate report (PPTX)", type="primary", disabled=not ready, use_container_width=True):
    st.info("Final render wiring is the next build step — the engine, scraper and "
            "design renderer are ready; connecting them to these inputs comes next.")
if not ready:
    st.caption("Add the webinar link and both CSVs to enable generation.")
