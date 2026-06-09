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
    from assemble import assemble, parse_email_block, derive_comp_sample, top_job_titles
    from design.render_proposal import generate_report
    from library import save_report, list_reports, path_of, cover_of
except Exception as e:
    _CORE_OK, _CORE_ERR = False, str(e)

LANGS = {"English": "en", "Español": "es", "Italiano": "it", "Polski": "pl"}
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

st.title("📊 Webinar Reports")
st.caption("Branded **Marketing & Audience Report** (editable PPTX) for a paid webinar.")
if not _CORE_OK:
    st.error("Report core not available: %s" % _CORE_ERR); st.stop()

# ── Saved reports (last 5) ───────────────────────────────────────────────────
_saved = list_reports()
if _saved:
    with st.expander("📁 Saved reports (last %d)" % len(_saved), expanded=False):
        for i, e in enumerate(_saved):
            cc = st.columns([1, 4, 2])
            cov = cover_of(e)
            if cov and os.path.exists(cov):
                cc[0].image(cov, use_container_width=True)
            cc[1].markdown("**%s**  \n%s · %s" % (e.get("title") or e["file"],
                           (e.get("lang") or "").upper(), e.get("when", "")))
            p = path_of(e)
            if os.path.exists(p):
                cc[2].download_button("⬇ PPTX", open(p, "rb").read(), file_name=e["file"],
                                      mime=PPTX_MIME, key="dl_saved_%d" % i, use_container_width=True)

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
            ss["title"] = ss["scraped"].get("title", "")     # pre-fill the title box
        except Exception as e:
            st.error("Couldn't read that page: %s" % e)

sc = ss.get("scraped")
# These inputs are ALWAYS visible — Fetch just pre-fills the title + speaker list.
t1, t2 = st.columns(2)
title = t1.text_input("Title (cover)", key="title")
subtitle = t2.text_input("Subtitle (cover)", key="subtitle")
y1, y2, y3 = st.columns([2, 1, 1])
youtube_url = y1.text_input("YouTube link (recording)", key="yt",
                            placeholder="https://youtube.com/live/…")
youtube_views = y2.text_input("YouTube views", key="ytv", placeholder="auto / type it")
# 🔄 force a fresh auto-read (clears the cached result so the fetch logic below re-runs)
if youtube_url.strip() and y2.button("🔄 Retry auto-read", key="yt_retry",
                                     help="Re-fetch the YouTube view count from the link"):
    ss.pop("_yt_url_cache", None)
    ss.pop("_yt_views_cache", None)
logo_opts = ["(none)"] + [l.split("/uploads/")[-1] for l in (sc or {}).get("logos", [])]
sponsor_sel = y3.selectbox("Sponsor logo (optional)", logo_opts)
sponsor_name = st.text_input("Sponsor name (excluded from the company lists)", key="sponsor_name",
                             placeholder="e.g. One Hub Energy")
# show the resolved YouTube views (manual wins, else auto-fetch) so it's never a surprise
_resolved_views = (youtube_views or "").strip()
if not _resolved_views and youtube_url.strip():
    _url_now = youtube_url.strip()
    # Re-fetch when the URL changes OR the previous attempt failed. Never cache a
    # failure as permanent: a one-off timeout / consent hiccup must self-heal on the
    # next rerun, otherwise the warning sticks forever even though the scrape works.
    if ss.get("_yt_url_cache") != _url_now or not ss.get("_yt_views_cache"):
        from assemble import youtube_views as _fetch_views
        ss["_yt_url_cache"] = _url_now
        ss["_yt_views_cache"] = _fetch_views(_url_now)
    _resolved_views = ss.get("_yt_views_cache")
if youtube_url.strip():
    if _resolved_views:
        st.caption("▶ YouTube views to be used: **%s** (added to Zoom for the total)." % _resolved_views)
    else:
        st.warning("Couldn't auto-read YouTube views — type the number in the **YouTube views** box "
                   "or it won't be counted in the total.")
if sc:
    st.caption("Speakers — edit, or use the **+** at the bottom to add people by hand "
               "(a photo is optional; names with no photo show a placeholder circle):")
    ss["speakers_edit"] = st.data_editor(
        [{"Name": s["name"], "Role": s["role"], "Company": s["company"],
          "Moderator": s["is_moderator"]} for s in sc.get("speakers", [])],
        num_rows="dynamic", use_container_width=True, hide_index=True, key="spk_editor",
    )
else:
    st.caption("Paste a webinar link and click **Fetch details** to auto-fill the title and speakers.")

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
        _regs = load_registrations(ss["reg_path"])
        ss["comp_default"] = derive_comp_sample(_regs, exclude=[sponsor_name] if sponsor_name else None)
        ss["titles_default"] = top_job_titles(ss["stats"].get("live_job_titles", []))
        kf = ss["stats"]["key_facts"]; m = st.columns(5)
        m[0].metric("Registrations", f"{kf['registrations']:,}")
        m[1].metric("Companies", kf["companies"]); m[2].metric("Countries", kf["countries"])
        m[3].metric("Live", kf["live_attendees"]); m[4].metric("Attendance", f"{kf['attendance_rate_pct']:.0f}%")
    except Exception as e:
        st.error("Could not read the CSVs: %s" % e)

# ── 3 · Companies & job titles (auto — edit if needed) ───────────────────────
if ss.get("stats"):
    st.subheader("3 · Companies & job titles")
    st.caption("Auto-filled — edit, add or remove rows before generating.")
    cc1, cc2 = st.columns(2)
    cc1.markdown("**Companies shown (slide 4)**")
    ss["comp_edit"] = cc1.data_editor(
        [{"Company": c} for c in ss.get("comp_default", [])],
        num_rows="dynamic", use_container_width=True, hide_index=True, key="comp_editor")
    cc2.markdown("**Top job titles (slide 8)** — most senior first")
    ss["titles_edit"] = cc2.data_editor(
        [{"Job title": t} for t in ss.get("titles_default", [])],
        num_rows="dynamic", use_container_width=True, hide_index=True, key="titles_editor")

# ── 4 · Marketing numbers ────────────────────────────────────────────────────
st.subheader("4 · Marketing numbers")
st.caption("Paste your email stats exactly as you copied them — one campaign per line, "
           "plus the summary line. It's read automatically.")
email_text = st.text_area(
    "Email stats", height=170, key="email_text",
    placeholder=("• E-shot 1: Apr 15 | 11,081 sent | 3,783 opens | 400 clicks\n"
                 "• Weekly Spanish (x7): 253,786 sent | 57,966 opens | 22,227 clicks\n"
                 "• Summary: over 410K delivered | over 94K opened | over 34K clicked"))
email_rows, email_totals = parse_email_block(email_text)
if email_rows:
    st.dataframe(email_rows, use_container_width=True, hide_index=True)
    if email_totals:
        st.caption("Totals read: **%s** delivered · **%s** opened · **%s** clicked" % email_totals)
elif email_text.strip():
    st.warning("Couldn't read any campaign lines — check the format (name : numbers + 'sent/opens/clicks').")

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
                         "email": cbits[-1] if "@" in cbits[-1] else "cintia.hernandez@ata.email",
                         "phone": "+34 605 40 85 93"}
            # companies (slide 4) + job titles (slide 8) from the editable tables
            comp_override = [(r.get("Company") or "").strip() for r in ss.get("comp_edit", []) if (r.get("Company") or "").strip()]
            titles_override = [(r.get("Job title") or "").strip() for r in ss.get("titles_edit", []) if (r.get("Job title") or "").strip()]
            form = {"title": title, "subtitle": subtitle, "youtube_url": youtube_url,
                    "youtube_views": youtube_views, "sponsor_logo_url": sponsor_url,
                    "sponsor_name": sponsor_name, "email_rows": email_rows, "email_totals": email_totals,
                    "speakers": speakers, "contact": contact_d,
                    "comp_override": comp_override or None, "titles_override": titles_override or None}
            web, ins, orgs = assemble(sc, ss["stats"], load_registrations(ss["reg_path"]),
                                      form, assets_dir, lang=lang, zoom_csv_path=ss["zoom_path"])
            fname = "ATA_Webinar_Report_%s%s.pptx" % (lang.upper(), "_annotated" if annotated else "")
            path = generate_report(web, ins, ss["stats"], orgs, lang=lang,
                                   annotate=annotated, assets_dir=assets_dir, out_dir=out_dir, filename=fname)
            import glob
            slides = sorted(glob.glob(os.path.join(out_dir, "[0-9][0-9]_*.png")))
            save_report(path, slides[0] if slides else None, {"title": title, "lang": lang})
        st.success("Report ready — %s" % os.path.basename(path))
        st.download_button("⬇ Download PPTX", open(path, "rb").read(), file_name=os.path.basename(path),
                           mime=PPTX_MIME, use_container_width=True)
        st.markdown("#### Preview")
        for png in slides:
            st.image(png, use_container_width=True)
    except Exception as e:
        import traceback
        st.error("Generation failed: %s" % e)
        st.code(traceback.format_exc())
