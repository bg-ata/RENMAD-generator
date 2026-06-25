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
import json
import os
import sys
import tempfile

import streamlit as st
from PIL import Image, ImageOps


# Streamlit Community Cloud has ~1 GB RAM. Full-resolution phone photos (4000×3000
# ≈ 36 MB once decoded) run through OpenCV face-detection + RGBA decode and blow
# past that limit → the process is OOM-killed ("Oh no. Error running app"). Cap
# every uploaded image at the entry point so the whole pipeline stays light.
_MAX_PX = 1600

def _shrink_image(name: str, raw: bytes, maxpx: int = _MAX_PX) -> bytes:
    """Downscale an uploaded image so its longest side is <= maxpx. 1600 px is
    ample for 1920 px slides and face detection. Returns the original bytes
    unchanged if it's already small or can't be read."""
    try:
        im = Image.open(io.BytesIO(raw))
        if max(im.size) <= maxpx:
            return raw
        im.draft("RGB", (maxpx, maxpx))           # fast partial JPEG decode (no-op for PNG)
        im = ImageOps.exif_transpose(im)          # respect phone-camera rotation
        im.thumbnail((maxpx, maxpx), Image.LANCZOS)
        buf = io.BytesIO()
        if name.lower().endswith((".jpg", ".jpeg")):
            im.convert("RGB").save(buf, "JPEG", quality=88)
        else:                                      # keep PNG (preserves logo transparency)
            im.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return raw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THEMES, LANGUAGE_STRINGS
from utils.parse_agenda import (parse_agenda_docx, parse_agenda_rows,
                                break_kind_from_title, parse_speaker_text)
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
st.caption("🟢 Build **2026-06-25** · reads both JSON shapes (Slides JSON + saved project) · Word still supported · one-click download "
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


def _json_meta(data: dict) -> dict:
    """Event title / theme / languages from EITHER JSON shape (the Slides JSON
    `{event:…}` or a project/state JSON with top-level titleA/themeKey/langA)."""
    ev = data.get("event") or {}
    title = (ev.get("title") or data.get("titleA") or "").strip()
    theme = (ev.get("theme") or data.get("themeKey") or "").strip()
    langs = [l for l in (ev.get("languages") or []) if l]
    if not langs:
        langs = [data.get("langA") or "en"]
        has_b = any(b.get("bT") for d in (data.get("days") or [])
                    for t in (d.get("tracks") or []) for b in (t.get("blocks") or []))
        if data.get("langB") and has_b:
            langs.append(data.get("langB"))
    return {"title": title, "theme": theme, "languages": langs or ["en"]}


def _json_sessions(data: dict) -> list:
    """Normalise either JSON shape to a flat list of raw sessions
    {time, type, break_kind, title_a, title_b, speakers[{name,role,company,mod}]}."""
    if isinstance(data.get("sessions"), list):
        return data["sessions"]                       # the Slides JSON
    raw = []                                           # a project/state JSON
    for day in (data.get("days") or []):
        for track in (day.get("tracks") or []):
            for b in (track.get("blocks") or []):
                spk = [{"name": sp["name"], "role": sp["role"],
                        "company": sp["company"], "mod": sp["is_moderator"]}
                       for sp in parse_speaker_text(b.get("spk"))]
                raw.append({"time": "", "type": b.get("type"), "break_kind": None,
                            "title_a": (b.get("aT") or ""),
                            "title_b": (b.get("bT") or b.get("aT") or ""),
                            "speakers": spk})
    return raw


def _agenda_from_json(data: dict, primary: str) -> dict:
    """Build a canonical agenda dict from EITHER agenda-generator JSON shape,
    using the title in language `primary` ('a' or 'b'). Skips ALL Word parsing."""
    sessions = []
    for i, s in enumerate(_json_sessions(data)):
        ta = (s.get("title_a") or "").strip()
        tb = (s.get("title_b") or "").strip()
        title = (ta if primary == "a" else tb) or ta or tb
        spk = []
        for sp in (s.get("speakers") or []):
            nm = (sp.get("name") or "").strip()
            if nm:
                spk.append({"name": nm, "role": (sp.get("role") or "").strip(),
                            "company": (sp.get("company") or "").strip(),
                            "is_moderator": bool(sp.get("mod"))})
        non_mod = [x for x in spk if not x["is_moderator"]]
        bk = (s.get("break_kind") or "").strip() or break_kind_from_title(title)
        jtype = (s.get("type") or "").strip().lower()
        if jtype == "break" or bk:
            stype, break_kind = "break", (bk or "break")
        elif jtype in ("panel", "presentation"):
            stype, break_kind = jtype, None
        else:
            stype = "panel" if len(non_mod) >= 2 else "presentation"
            break_kind = None
        sessions.append({
            "id": f"s{i}", "day": int(s.get("day", 1) or 1),
            "time": (s.get("time") or "").strip(), "start": (s.get("time") or "").strip(),
            "type": stype, "break_kind": break_kind,
            "title": title, "title_2": None, "delivery_language": None,
            "speakers": spk,
        })
    meta = _json_meta(data)
    return {"event": {"title": meta["title"], "language": meta["languages"][0],
                      "register_url": (data.get("event") or {}).get("register_url")},
            "sessions": sessions, "logo_wall": None}


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
# 3 · AGENDA
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 · Agenda")
st.caption("Two ways in: a **JSON** from our agenda generator (recommended — no "
           "formatting surprises, both languages in one file), or the **Word/Excel/"
           "CSV** agenda (for events that aren't ours).")

ag_file1 = ag_file2 = None
agenda1 = agenda2 = None

json_file = st.file_uploader("① JSON from the agenda generator (RENMAD events)",
                             type=["json"], key="ts_json")

if json_file is not None:
    try:
        jdata = json.loads(json_file.getvalue().decode("utf-8-sig"))
        meta = _json_meta(jdata)
        jlangs = meta["languages"]
        lang1 = jlangs[0]
        if len(jlangs) > 1:
            lang2, has_lang2 = jlangs[1], True
        if meta["theme"] in THEMES:
            theme_key = meta["theme"]
        agenda1 = _agenda_from_json(jdata, "a")
        agenda2 = _agenda_from_json(jdata, "b") if has_lang2 else None
        n_spk = sum(len(s.get("speakers", [])) for s in agenda1["sessions"])
        _ln = " + ".join(LANGS.get(l, l) for l in jlangs)
        st.success(f"✅ JSON loaded — {_agenda_summary(agenda1)} · {_ln} · "
                   f"theme: {THEMES.get(theme_key, {}).get('name', theme_key)}")
        if n_spk == 0:
            st.warning("⚠️ This JSON has **no speakers**. Make sure you exported it with "
                       "the **🎬 Slides JSON** button in the agenda generator (not a saved "
                       "project), and that the agenda actually has speakers filled in.")
    except Exception as e:
        st.error(f"Couldn't read that JSON: {e}")
else:
    st.caption("② …or upload the Word/Excel/CSV agenda — one file per language:")
    ac1, ac2 = st.columns(2)
    ag_file1 = ac1.file_uploader(f"Agenda · {LANGS[lang1]}",
                                 type=["docx", "xlsx", "xls", "csv"], key="ts_agenda1")
    if has_lang2:
        ag_file2 = ac2.file_uploader(f"Agenda · {LANGS[lang2]}",
                                     type=["docx", "xlsx", "xls", "csv"], key="ts_agenda2")
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
        pool[f.name] = _shrink_image(f.name, f.getvalue())   # cap size → avoid Cloud OOM
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
    if json_file:
        hsh.update(json_file.getvalue())
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
