# -*- coding: utf-8 -*-
"""
🎬 Title Slides — turn an event agenda into the on-screen / marketing title slides.

ONE choice drives everything: **Marketing** vs **Event**.

  • Marketing  → title in a TOP band, NO transition slides, speaker-reveal cards
                 only. Produces TWO separate monolingual decks (one per language).
                 Drives the LinkedIn "progressing panel" assets.

  • Event      → WITH transition / break dividers + cover + utility slides, one
                 bilingual deck. The title band can sit at the bottom (default) or
                 the top, depending on where the screen is in the room.

All output is a fully-editable PPTX: photos are movable/replaceable pictures and
every name / role / title is native editable text — nothing is baked into a flat
image. Auto-matched photos that miss just fall back to an initials placeholder you
can swap in PowerPoint.
"""
import io
import os
import sys
import tempfile

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THEMES, LANGUAGE_STRINGS
from utils.parse_agenda import parse_agenda_docx, parse_agenda_rows
from utils.asset_match import match_assets
from generators.title_slides import build_event_deck


# ── Page chrome ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Title Slides", page_icon="🎬", layout="wide")
st.title("🎬 Title Slides")
st.caption(
    "Upload the event agenda and generate the on-screen **title slides** "
    "(fully editable PPTX). You only pick one thing: **Marketing** or **Event** — "
    "everything else is set for you."
)
st.caption("🟢 Build **2026-06-16h** · slimmer SPX top strip · bilingual transitions · balanced logos · one-click download "
           "— if you don't see this line, the app is still on an older version.")

LANGS = {"en": "English", "es": "Spanish", "it": "Italian", "pl": "Polish"}


# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_uploaded_agenda(uploaded) -> dict | None:
    """Dispatch on file extension → canonical agenda dict (or None on failure)."""
    if uploaded is None:
        return None
    name = uploaded.name.lower()
    raw = uploaded.getvalue()
    if name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
            tf.write(raw)
            tmp_path = tf.name
        try:
            return parse_agenda_docx(tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
    if name.endswith(".csv"):
        import csv as _csv
        text = raw.decode("utf-8-sig", errors="replace")
        rows = [(r[0], r[1]) for r in _csv.reader(io.StringIO(text)) if len(r) >= 2]
        return parse_agenda_rows(rows)
    if name.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
        except ImportError:
            st.error("Reading Excel needs `openpyxl`. Upload the agenda as Word (.docx) or CSV.")
            return None
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            if r and len(r) >= 2 and (r[0] or r[1]):
                rows.append((str(r[0] or ""), str(r[1] or "")))
        return parse_agenda_rows(rows)
    st.error(f"Unsupported format: {uploaded.name}. Use Word (.docx), Excel (.xlsx) or CSV.")
    return None


def _agenda_summary(agenda: dict) -> str:
    sessions = agenda.get("sessions", [])
    n_talk = sum(1 for s in sessions if s.get("type") in ("panel", "presentation", "speaker"))
    n_break = sum(1 for s in sessions if s.get("type") == "break")
    n_spk = sum(len([sp for sp in s.get("speakers", []) if (sp.get("name") or "").strip()])
                for s in sessions)
    return f"{n_talk} sessions · {n_spk} speakers · {n_break} breaks/transitions"


def _merge_bilingual(primary: dict, secondary: dict) -> dict:
    """Build ONE agenda whose sessions carry both languages on the title band:
    primary title on `title` (bigger) + secondary on `title_2` (below).
    Sessions are matched by position; if counts differ we match what we can."""
    merged = {k: v for k, v in primary.items()}
    p_sessions = primary.get("sessions", [])
    s_sessions = secondary.get("sessions", [])
    out = []
    for i, ps in enumerate(p_sessions):
        ns = dict(ps)
        sec = s_sessions[i] if i < len(s_sessions) else None
        if sec:
            sec_title = (sec.get("title") or "").strip()
            if sec_title and sec_title.lower() != (ps.get("title") or "").strip().lower():
                ns["title_2"] = sec_title
        out.append(ns)
    merged["sessions"] = out
    return merged


def _match_pool(agenda: dict, pool: dict) -> dict:
    """Write the uploaded photo/logo pool to a temp folder and auto-match it
    against the agenda's speakers & companies (filename heuristics)."""
    if not pool:
        return {"photos": {}, "logos": {}, "report": {}}
    tmpdir = tempfile.mkdtemp(prefix="titleslides_")
    try:
        for fname, b in pool.items():
            with open(os.path.join(tmpdir, fname), "wb") as f:
                f.write(b)
        return match_assets(agenda, tmpdir)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════
# 1 · MARKETING OR EVENT?
# ══════════════════════════════════════════════════════════════════════════════
st.header("1 · Marketing or Event?")

MODE_MARKETING = "📣 Marketing  ·  title on top · no transitions · 2 decks (one per language)"
MODE_EVENT     = "🎤 Event  ·  with transitions · 1 bilingual deck"

mode = st.radio("Type of slides", [MODE_MARKETING, MODE_EVENT],
                key="ts_mode", label_visibility="collapsed")
is_event = mode == MODE_EVENT

event_band = "bottom"
if is_event:
    band_label = st.radio(
        "Where should the session title sit on the event slides?",
        ["Bottom (default)", "Top"],
        horizontal=True, key="ts_band",
        help="Pick based on where the screen is in the room — a low screen often "
             "gets blocked at the bottom by people, so the title can go on top.",
    )
    event_band = "top" if band_label == "Top" else "bottom"

    spx_space = st.checkbox(
        "Leave a blank space at the top for sponsor logos (add by hand)",
        value=False, key="ts_spx",
        help="For small events with no LED screen/background carrying the sponsor "
             "logos. Reserves an empty top strip + a slim band, and pushes the "
             "speakers down. No logos are added — you paste them in PowerPoint.",
    )
else:
    spx_space = False


# ══════════════════════════════════════════════════════════════════════════════
# 2 · BASICS
# ══════════════════════════════════════════════════════════════════════════════
st.header("2 · Details")

c1, c2, c3 = st.columns([1.4, 1, 1])
theme_keys = sorted(THEMES.keys(), key=lambda k: THEMES[k]["name"])
theme_key = c1.selectbox("Theme (colour)", theme_keys,
                         format_func=lambda k: THEMES[k]["name"], key="ts_theme")
lang1 = c2.selectbox("Language 1 (primary)", list(LANGS.keys()),
                     format_func=lambda k: LANGS[k], index=0, key="ts_lang1")
lang2 = c3.selectbox("Language 2 (optional)", ["—"] + list(LANGS.keys()),
                     format_func=lambda k: "— none —" if k == "—" else LANGS[k],
                     index=0, key="ts_lang2")
has_lang2 = lang2 != "—"

if is_event and not has_lang2:
    st.info("ℹ️ The **Event** deck is bilingual. Without a 2nd language you'll get a single-language deck.")
if not is_event and not has_lang2:
    st.caption("With one language, Marketing produces **1 deck**.")


# ══════════════════════════════════════════════════════════════════════════════
# 3 · AGENDAS
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 · Agenda(s)")
st.caption("Word (.docx), Excel (.xlsx) or CSV. Upload one agenda per language — "
           "they're matched by session order.")

ac1, ac2 = st.columns(2)
ag_file1 = ac1.file_uploader(f"Agenda · {LANGS[lang1]}", type=["docx", "xlsx", "xls", "csv"],
                             key="ts_agenda1")
ag_file2 = None
if has_lang2:
    ag_file2 = ac2.file_uploader(f"Agenda · {LANGS[lang2]}", type=["docx", "xlsx", "xls", "csv"],
                                 key="ts_agenda2")

agenda1 = _parse_uploaded_agenda(ag_file1) if ag_file1 else None
agenda2 = _parse_uploaded_agenda(ag_file2) if (has_lang2 and ag_file2) else None

if agenda1:
    ac1.success(f"✅ {_agenda_summary(agenda1)}")
if agenda2:
    ac2.success(f"✅ {_agenda_summary(agenda2)}")


# ══════════════════════════════════════════════════════════════════════════════
# 4 · PHOTOS & LOGOS
# ══════════════════════════════════════════════════════════════════════════════
st.header("4 · Photos & logos")
st.caption(
    "Upload the speaker photos and company logos together. They're matched "
    "automatically by **file name** (e.g. `Mario_Rossi.jpg`, `Enel_logo.png`). "
    "Anything that doesn't match gets an initials circle you can swap in PowerPoint."
)

pool_uploads = st.file_uploader(
    "Photos + logos (PNG, JPG)", type=["png", "jpg", "jpeg"],
    accept_multiple_files=True, key="ts_pool",
)
pool: dict[str, bytes] = {}
if pool_uploads:
    for f in pool_uploads:
        pool[f.name] = f.getvalue()
    st.caption(f"{len(pool)} file(s) loaded.")


# ══════════════════════════════════════════════════════════════════════════════
# 5 · OPTIONS (sensible defaults — usually leave as-is)
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("⚙️ Options (the defaults usually work)", expanded=False):
    if is_event:
        opt_cover = st.checkbox("Cover slide (Welcome + sponsor logo wall)", value=True,
                                key="ts_cover")
        opt_breaks = st.checkbox("Transition slides (coffee, lunch, cocktail…)", value=True,
                                 key="ts_breaks")
        util_pick = st.multiselect(
            "Utility slides",
            options=["mute", "wifi", "qr"],
            default=["mute", "qr"],
            format_func={"mute": "📵 Mute your phone", "wifi": "📶 WiFi",
                         "qr": "📱 Scan to register"}.get,
            key="ts_utils",
        )
    else:
        opt_cover = False
        opt_breaks = False
        util_pick = []
        st.caption("Marketing = speaker slides only (no cover, transitions or utility slides).")
    opt_cards = st.checkbox(
        "Include an individual card per speaker in panels", value=True, key="ts_cards",
        help="As well as the combined panel slide, one card per panellist "
             "(the progressive-reveal LinkedIn assets).",
    )
    title_fit = st.radio(
        "Title size", ["flexible", "uniform"], horizontal=True, key="ts_fit",
        format_func={"flexible": "Flexible (big title, band adapts)",
                     "uniform": "Uniform (fixed band, title adapts)"}.get,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6 · DOWNLOAD  (builds on the fly — a single click gets you the file)
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("6 · Download")


def _build_one(agenda: dict, lang: str, layout: str, label: str,
               lang2: str | None = None) -> dict:
    """Match assets for THIS agenda and build one deck. Returns {bytes, report}."""
    res = _match_pool(agenda, pool)
    out_path = os.path.join(tempfile.mkdtemp(prefix="ts_out_"), f"{label}.pptx")
    build_event_deck(
        agenda, theme_key, out_path,
        photos=res["photos"], logos=res["logos"],
        lang_strings=LANGUAGE_STRINGS.get(lang, LANGUAGE_STRINGS["en"]),
        include_cards=opt_cards, layout=layout, title_fit=title_fit,
        include_breaks=opt_breaks, cover=opt_cover, lang=lang,
        utility_kinds=util_pick or None, event_band=event_band, spx_space=spx_space,
        lang2=lang2,
    )
    with open(out_path, "rb") as f:
        data = f.read()
    return {"bytes": data, "report": res.get("report", {})}


if agenda1 is None:
    st.info("Upload at least the primary-language agenda to get your slides.")
else:
    # Build whenever the inputs change, keyed by a signature, so the download
    # button below is always armed with an up-to-date deck → one click to save.
    import hashlib
    sig = [mode, theme_key, lang1, lang2, title_fit, opt_cover, opt_breaks,
           tuple(util_pick), opt_cards, event_band]
    hsh = hashlib.sha1("|".join(str(x) for x in sig).encode())
    if ag_file1:
        hsh.update(ag_file1.getvalue())
    if ag_file2:
        hsh.update(ag_file2.getvalue())
    for fn in sorted(pool):
        hsh.update(fn.encode()); hsh.update(pool[fn])
    key = hsh.hexdigest()

    cache = st.session_state.setdefault("_ts_cache", {})
    if cache.get("key") != key:
        try:
            with st.spinner("Building your title slides…"):
                built = []
                if is_event:
                    deck_agenda = _merge_bilingual(agenda1, agenda2) if agenda2 else agenda1
                    _l2 = lang2 if (agenda2 and has_lang2) else None
                    built.append(("event_title_slides.pptx",
                                  _build_one(deck_agenda, lang1, "event", "event", lang2=_l2)))
                else:
                    built.append((f"marketing_title_slides_{lang1}.pptx",
                                  _build_one(agenda1, lang1, "marketing", f"m_{lang1}")))
                    if agenda2:
                        built.append((f"marketing_title_slides_{lang2}.pptx",
                                      _build_one(agenda2, lang2, "marketing", f"m_{lang2}")))
            cache["key"] = key
            cache["decks"] = built
        except Exception as e:
            import traceback
            cache["key"] = key
            cache["decks"] = []
            st.error(f"Generation failed: {e}")
            st.code(traceback.format_exc())

    MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    for fname, res in cache.get("decks", []):
        st.download_button(
            f"⬇️ Download {fname}", data=res["bytes"], file_name=fname, mime=MIME,
            type="primary", use_container_width=True, key=f"dl_{fname}",
        )
        rep = res.get("report") or {}
        miss_p = rep.get("photo_missing") or []
        miss_l = rep.get("logo_missing") or []
        n_p = len(rep.get("photo_matched") or []) + len(rep.get("photo_fuzzy") or [])
        n_l = len(rep.get("logo_matched") or [])
        st.caption(f"Photos matched: {n_p} · Logos matched: {n_l}")
        if miss_p or miss_l:
            with st.expander("⚠️ Not matched (will use an editable placeholder)", expanded=False):
                if miss_p:
                    st.markdown("**Missing photos:** " + ", ".join(miss_p))
                if miss_l:
                    st.markdown("**Missing logos:** " + ", ".join(miss_l))
                st.caption("Rename the file to the speaker / company name and re-upload, "
                           "or just swap it in PowerPoint (the slides are editable).")
