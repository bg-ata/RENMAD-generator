# -*- coding: utf-8 -*-
"""
📊 Webinar Reports — post-webinar marketing & audience report (paid webinars).

Separate from the Webinar (slide) tool: produces the branded, editable PPTX
"Marketing & Audience Report" we send to the sponsor of a paid webinar.

Colleague flow:
  paste the webinar link → upload registration + Zoom CSVs → type the email
  numbers → pick language → Generate → download the editable PPTX.

Engine + scraper + renderer are vendored in ./report_core.
"""
import os
import sys
import tempfile

import streamlit as st

_CORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "report_core")
if _CORE not in sys.path:
    sys.path.insert(0, _CORE)

_CORE_OK, _CORE_ERR = True, ""
try:
    from scraper.scrape import scrape_webinar
    from engine.ingest import build_stats, load_registrations
    from assemble import assemble, relevant_orgs_rich
    from canonicalize import add_alias
    from design.render_proposal import generate_report
except Exception as e:
    _CORE_OK, _CORE_ERR = False, str(e)

LANGS = {"English": "en", "Español": "es", "Italiano": "it", "Polski": "pl"}

st.title("📊 Webinar Reports")
st.caption("Branded **Marketing & Audience Report** (editable PPTX) for a paid webinar.")
if not _CORE_OK:
    st.error("Report core not available: %s" % _CORE_ERR); st.stop()

ss = st.session_state


def _tmp_csv(uploaded):
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    f.write(uploaded.getvalue()); f.close(); return f.name


# ── 1 · Webinar ──────────────────────────────────────────────────────────────
st.subheader("1 · Webinar")
c1, c2 = st.columns([4, 1])
url = c1.text_input("Webinar link", placeholder="https://my.atainsights.com/webinar/…")
lang_label = c2.selectbox("Report language", list(LANGS.keys()))
lang = LANGS[lang_label]

if st.button("Fetch details", disabled=not url):
    with st.spinner("Reading the webinar page…"):
        try:
            ss["scraped"] = scrape_webinar(url)
            ss["speaker_photos"] = [s.get("photo") for s in ss["scraped"]["speakers"]]
        except Exception as e:
            st.error("Couldn't read that page: %s" % e)

sc = ss.get("scraped")
if sc:
    t1, t2 = st.columns(2)
    title = t1.text_input("Title (cover)", value=ss.get("title", sc["title"]), key="title")
    subtitle = t2.text_input("Subtitle (cover)", value=ss.get("subtitle", ""), key="subtitle")
    y1, y2 = st.columns(2)
    youtube_url = y1.text_input("YouTube link (recording)", value=ss.get("yt", ""), key="yt")
    logo_opts = ["(none)"] + [l.split("/uploads/")[-1] for l in sc.get("logos", [])]
    sponsor_sel = y2.selectbox("Sponsor logo (optional)", logo_opts)
    st.caption("Speakers — edit names / roles / companies before generating:")
    ss["speakers_edit"] = st.data_editor(
        [{"Name": s["name"], "Role": s["role"], "Company": s["company"],
          "Moderator": s["is_moderator"]} for s in sc["speakers"]],
        num_rows="dynamic", use_container_width=True, hide_index=True, key="spk_editor",
    )

# ── 2 · Data files ───────────────────────────────────────────────────────────
st.subheader("2 · Data files")
d1, d2 = st.columns(2)
reg_csv = d1.file_uploader("Registration CSV (CRM export)", type=["csv"])
zoom_csv = d2.file_uploader("Zoom attendee CSV", type=["csv"])
if reg_csv and zoom_csv:
    try:
        ss["reg_path"] = _tmp_csv(reg_csv)
        ss["zoom_path"] = _tmp_csv(zoom_csv)
        ss["stats"] = build_stats(ss["reg_path"], ss["zoom_path"])
        ss["orgs_rich"] = relevant_orgs_rich(load_registrations(ss["reg_path"]))
        kf = ss["stats"]["key_facts"]; m = st.columns(5)
        m[0].metric("Registrations", f"{kf['registrations']:,}")
        m[1].metric("Companies", kf["companies"]); m[2].metric("Countries", kf["countries"])
        m[3].metric("Live", kf["live_attendees"]); m[4].metric("Attendance", f"{kf['attendance_rate_pct']:.0f}%")
    except Exception as e:
        st.error("Could not read the CSVs: %s" % e)

# ── 3 · Highlighted organizations (approve / edit) ───────────────────────────
if ss.get("orgs_rich"):
    st.subheader("3 · Highlighted organizations")
    st.caption("Auto-shortlisted from the live audience (job seniority + notable companies). "
               "Edit, swap or remove — your name fixes are remembered for next time.")
    ss["orgs_edit"] = st.data_editor(
        [{"Company": o["company"], "Role": o["title"]} for o in ss["orgs_rich"]],
        num_rows="dynamic", use_container_width=True, hide_index=True, key="orgs_editor",
    )

# ── 4 · Marketing numbers ────────────────────────────────────────────────────
st.subheader("4 · Marketing numbers")
st.caption("Email campaign sends / opens / clicks. YouTube views are fetched automatically.")
email_rows = st.data_editor(
    [{"Campaign": "E-shot 1", "Sent": 0, "Opens": 0, "Clicks": 0}],
    num_rows="dynamic", use_container_width=True, key="email_rows",
)

# ── 5 · Options ──────────────────────────────────────────────────────────────
st.subheader("5 · Options")
o1, o2 = st.columns(2)
annotated = o1.toggle("Add 'highlights' notes (annotated version)", value=False)
contact = o2.text_input("Contact", value="Cintia Hernández · Business Development · cintia.hernandez@ata.email")

# ── Generate ─────────────────────────────────────────────────────────────────
st.divider()
ready = bool(sc and ss.get("stats"))
if not ready:
    st.caption("Add the webinar link and both CSVs to enable generation.")

if st.button("Generate report (PPTX)", type="primary", disabled=not ready, use_container_width=True):
    try:
        with st.spinner("Building the report…"):
            assets_dir = tempfile.mkdtemp(prefix="rep_assets_")
            out_dir = tempfile.mkdtemp(prefix="rep_out_")
            # speakers: merge edited rows with the scraped photo URLs (by index)
            photos = ss.get("speaker_photos", [])
            speakers = []
            for i, row in enumerate(ss.get("speakers_edit", [])):
                speakers.append({"name": row.get("Name", ""), "role": row.get("Role", ""),
                                 "company": row.get("Company", ""),
                                 "is_moderator": bool(row.get("Moderator")),
                                 "photo": photos[i] if i < len(photos) else None})
            # sponsor logo url from the picked filename
            sponsor_url = ""
            for l in sc.get("logos", []):
                if sponsor_sel != "(none)" and l.endswith(sponsor_sel):
                    sponsor_url = l; break
            # contact parse "Name · Role · email"
            cbits = [c.strip() for c in contact.split("·")]
            contact_d = {"name": cbits[0] if cbits else "Cintia Hernández",
                         "role": cbits[1] if len(cbits) > 1 else "Business Development",
                         "email": cbits[-1] if "@" in cbits[-1] else "cintia.hernandez@ata.email"}
            # highlighted orgs: use the approved/edited table + remember name fixes
            orgs_override, rich = [], ss.get("orgs_rich", [])
            for i, row in enumerate(ss.get("orgs_edit", []) or []):
                comp = (row.get("Company") or "").strip()
                if not comp:
                    continue
                orgs_override.append((comp, "", row.get("Role", "")))
                if i < len(rich) and comp != rich[i]["company"]:
                    add_alias(rich[i]["raw"], comp)        # learn the fix
            form = {"title": title, "subtitle": subtitle, "youtube_url": youtube_url,
                    "sponsor_logo_url": sponsor_url, "email_rows": email_rows,
                    "speakers": speakers, "contact": contact_d,
                    "orgs_override": orgs_override or None}
            web, ins, orgs = assemble(sc, ss["stats"], load_registrations(ss["reg_path"]),
                                      form, assets_dir, lang=lang, zoom_csv_path=ss["zoom_path"])
            fname = "ATA_Webinar_Report_%s%s.pptx" % (lang.upper(), "_annotated" if annotated else "")
            path = generate_report(web, ins, ss["stats"], orgs, lang=lang,
                                   annotate=annotated, assets_dir=assets_dir, out_dir=out_dir, filename=fname)
        with open(path, "rb") as fh:
            st.success("Report ready — %s" % os.path.basename(path))
            st.download_button("⬇ Download PPTX", fh.read(), file_name=os.path.basename(path),
                               mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                               use_container_width=True)
    except Exception as e:
        import traceback
        st.error("Generation failed: %s" % e)
        st.code(traceback.format_exc())
