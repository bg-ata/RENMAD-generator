# -*- coding: utf-8 -*-
"""
🎬 Title Slides — turn an event agenda into the on-screen / marketing title slides.

ONE choice drives everything: **Marketing** vs **Event**.

  • Marketing  → title in a TOP band, NO transition slides, speaker-reveal cards
                 only. Produces TWO separate monolingual decks (one per language).
                 Drives the LinkedIn "progressing panel" assets.

  • Event      → title in a BOTTOM band (photos pushed high for the live screen),
                 WITH transition / break dividers + cover + utility slides.
                 Produces ONE bilingual deck (both languages on each title band).

Everything else (title position, transitions, deck count, language layout) follows
automatically from that one pick — the page stays deliberately minimal.

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
    "Sube la agenda del evento y genera las **slides de título** (PPTX 100 % editable). "
    "Solo eliges una cosa: **Marketing** o **Evento** — todo lo demás se ajusta solo."
)

LANGS = {"en": "English", "es": "Español", "it": "Italiano", "pl": "Polski"}


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
            st.error("Para leer Excel hace falta `openpyxl`. Sube la agenda en Word (.docx) o CSV.")
            return None
        wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            if r and len(r) >= 2 and (r[0] or r[1]):
                rows.append((str(r[0] or ""), str(r[1] or "")))
        return parse_agenda_rows(rows)
    st.error(f"Formato no soportado: {uploaded.name}. Usa Word (.docx), Excel (.xlsx) o CSV.")
    return None


def _agenda_summary(agenda: dict) -> str:
    sessions = agenda.get("sessions", [])
    n_talk = sum(1 for s in sessions if s.get("type") in ("panel", "presentation", "speaker"))
    n_break = sum(1 for s in sessions if s.get("type") == "break")
    n_spk = sum(len([sp for sp in s.get("speakers", []) if (sp.get("name") or "").strip()])
                for s in sessions)
    return f"{n_talk} sesiones · {n_spk} ponentes · {n_break} pausas/transiciones"


def _merge_bilingual(primary: dict, secondary: dict) -> dict:
    """Build ONE agenda whose sessions carry both languages on the title band:
    primary title on `title` (top, bigger) + secondary on `title_2` (below).
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
# 1 · THE ONE CHOICE
# ══════════════════════════════════════════════════════════════════════════════
st.header("1 · ¿Marketing o Evento?")

MODE_MARKETING = "📣 Marketing  ·  título arriba · sin transiciones · 2 decks (uno por idioma)"
MODE_EVENT     = "🎤 Evento  ·  título abajo · con transiciones · 1 deck bilingüe"

mode = st.radio("Tipo de slides", [MODE_MARKETING, MODE_EVENT],
                key="ts_mode", label_visibility="collapsed")
is_event = mode == MODE_EVENT


# ══════════════════════════════════════════════════════════════════════════════
# 2 · EVENT BASICS
# ══════════════════════════════════════════════════════════════════════════════
st.header("2 · Datos")

c1, c2, c3 = st.columns([1.4, 1, 1])
theme_keys = sorted(THEMES.keys(), key=lambda k: THEMES[k]["name"])
theme_key = c1.selectbox("Tema (color)", theme_keys,
                         format_func=lambda k: THEMES[k]["name"], key="ts_theme")
lang1 = c2.selectbox("Idioma 1 (principal)", list(LANGS.keys()),
                     format_func=lambda k: LANGS[k], index=0, key="ts_lang1")
lang2 = c3.selectbox("Idioma 2 (opcional)", ["—"] + list(LANGS.keys()),
                     format_func=lambda k: "— ninguno —" if k == "—" else LANGS[k],
                     index=0, key="ts_lang2")
has_lang2 = lang2 != "—"

if is_event and not has_lang2:
    st.info("ℹ️ El deck de **Evento** es bilingüe. Sin idioma 2 saldrá un deck en un solo idioma.")
if not is_event and not has_lang2:
    st.caption("Con un solo idioma, Marketing genera **1 deck**.")


# ══════════════════════════════════════════════════════════════════════════════
# 3 · AGENDAS
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 · Agenda(s)")
st.caption("Word (.docx), Excel (.xlsx) o CSV. Sube una agenda por idioma — "
           "se emparejan por orden de sesión.")

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
st.header("4 · Fotos y logos")
st.caption(
    "Sube las fotos de los ponentes y los logos de empresa juntos. Se emparejan "
    "automáticamente por el **nombre del archivo** (p. ej. `Mario_Rossi.jpg`, "
    "`Enel_logo.png`). Lo que no encaje sale con un círculo de iniciales que puedes "
    "cambiar en PowerPoint."
)

pool_uploads = st.file_uploader(
    "Fotos + logos (PNG, JPG)", type=["png", "jpg", "jpeg"],
    accept_multiple_files=True, key="ts_pool",
)
pool: dict[str, bytes] = {}
if pool_uploads:
    for f in pool_uploads:
        pool[f.name] = f.getvalue()
    st.caption(f"{len(pool)} archivo(s) cargados.")


# ══════════════════════════════════════════════════════════════════════════════
# 5 · OPTIONS (sensible defaults — usually leave as-is)
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("⚙️ Opciones (los valores por defecto suelen valer)", expanded=False):
    if is_event:
        opt_cover = st.checkbox("Slide de portada (Bienvenida + muro de logos)", value=True,
                                key="ts_cover")
        opt_breaks = st.checkbox("Slides de transición (café, comida, cóctel…)", value=True,
                                 key="ts_breaks")
        util_pick = st.multiselect(
            "Slides de utilidad",
            options=["mute", "wifi", "qr"],
            default=["mute", "qr"],
            format_func={"mute": "📵 Silenciar móvil", "wifi": "📶 WiFi",
                         "qr": "📱 QR registro"}.get,
            key="ts_utils",
        )
    else:
        opt_cover = False
        opt_breaks = False
        util_pick = []
        st.caption("Marketing = solo las slides de ponentes (sin portada, transiciones ni utilidades).")
    opt_cards = st.checkbox(
        "Incluir tarjeta individual por ponente en los paneles", value=True, key="ts_cards",
        help="Además del panel combinado, una tarjeta por panelista (revelado progresivo en LinkedIn).",
    )
    title_fit = st.radio(
        "Tamaño del título", ["flexible", "uniform"], horizontal=True, key="ts_fit",
        format_func={"flexible": "Flexible (título grande, banda se adapta)",
                     "uniform": "Uniforme (banda fija, título se ajusta)"}.get,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 6 · GENERATE
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header("6 · Generar")

ready = agenda1 is not None
gen_btn = st.button("🎬 Generar slides de título", type="primary",
                    use_container_width=True, disabled=not ready)
if not ready:
    st.info("Sube al menos la agenda del idioma principal para empezar.")


def _build_one(agenda: dict, lang: str, layout: str, label: str) -> dict:
    """Match assets for THIS agenda and build one deck. Returns {bytes, report}."""
    res = _match_pool(agenda, pool)
    out_path = os.path.join(tempfile.mkdtemp(prefix="ts_out_"), f"{label}.pptx")
    build_event_deck(
        agenda, theme_key, out_path,
        photos=res["photos"], logos=res["logos"],
        lang_strings=LANGUAGE_STRINGS.get(lang, LANGUAGE_STRINGS["en"]),
        include_cards=opt_cards, layout=layout, title_fit=title_fit,
        include_breaks=opt_breaks, cover=opt_cover, lang=lang,
        utility_kinds=util_pick or None,
    )
    with open(out_path, "rb") as f:
        data = f.read()
    return {"bytes": data, "report": res.get("report", {})}


if gen_btn and ready:
    decks: list[tuple[str, dict]] = []   # (filename, {bytes, report})
    try:
        with st.spinner("Generando…"):
            if is_event:
                # ONE bilingual deck (primary on top, secondary below)
                if agenda2:
                    deck_agenda = _merge_bilingual(agenda1, agenda2)
                else:
                    deck_agenda = agenda1
                res = _build_one(deck_agenda, lang1, "event", "event_title_slides")
                decks.append(("event_title_slides.pptx", res))
            else:
                # TWO monolingual marketing decks (one per language)
                res1 = _build_one(agenda1, lang1, "marketing", f"marketing_{lang1}")
                decks.append((f"marketing_title_slides_{lang1}.pptx", res1))
                if agenda2:
                    res2 = _build_one(agenda2, lang2, "marketing", f"marketing_{lang2}")
                    decks.append((f"marketing_title_slides_{lang2}.pptx", res2))
        st.session_state["_ts_decks"] = decks
        st.success(f"✅ Generado: {len(decks)} deck(s).")
    except Exception as e:
        import traceback
        st.error(f"Error generando: {e}")
        st.code(traceback.format_exc())


# ── Results ──────────────────────────────────────────────────────────────────
decks = st.session_state.get("_ts_decks")
if decks:
    st.divider()
    for fname, res in decks:
        st.subheader(f"📊 {fname}")
        st.download_button(
            f"⬇️ Descargar {fname}",
            data=res["bytes"], file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True, key=f"dl_{fname}",
        )
        rep = res.get("report") or {}
        miss_p = rep.get("photo_missing") or []
        miss_l = rep.get("logo_missing") or []
        n_p = len(rep.get("photo_matched") or []) + len(rep.get("photo_fuzzy") or [])
        n_l = len(rep.get("logo_matched") or [])
        st.caption(f"Fotos emparejadas: {n_p} · Logos emparejados: {n_l}")
        if miss_p or miss_l:
            with st.expander("⚠️ Sin emparejar (saldrán con marcador editable)", expanded=False):
                if miss_p:
                    st.markdown("**Fotos faltantes:** " + ", ".join(miss_p))
                if miss_l:
                    st.markdown("**Logos faltantes:** " + ", ".join(miss_l))
                st.caption("Renombra el archivo al nombre del ponente / empresa y vuelve a subir, "
                           "o cámbialo directamente en PowerPoint (las slides son editables).")
