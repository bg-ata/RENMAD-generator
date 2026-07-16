"""RENMAD Webinar Slide Generator (single-session)."""
import io, os, sys, zipfile, re, unicodedata
import streamlit as st
from PIL import Image

# This file lives in pages/, so add the project root to sys.path BEFORE
# importing project modules like `config` or `utils.*`.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config import THEMES, LANGUAGE_STRINGS
from utils.slide_store import (
    save_slide, list_slides, load_slide, delete_slide, thumb_bytes,
    MAX_SLIDES, STORE_DIR,
)

st.set_page_config(page_title="RENMAD Webinar Generator", page_icon="🎤", layout="wide")

from dc_auth import require_dispatch_login  # gate: Dispatch Center only
require_dispatch_login()

# Assets live in the project root, NOT next to this page file
ASSETS_DIR = os.path.join(_PROJECT_ROOT, "assets")
LOGO_DIR   = os.path.join(ASSETS_DIR, "logos")
BG_DIR     = os.path.join(ASSETS_DIR, "backgrounds")


# Cap any input image at this pixel count to stay within Streamlit Cloud memory limits.
# 16 megapixels = e.g. 4000x4000 or 5333x3000 — plenty for any logo/photo use case.
_MAX_INPUT_PIXELS = 16_000_000


def _shrink_if_huge(img: Image.Image) -> Image.Image:
    """Resize image in-place if it exceeds the safe pixel budget."""
    if img.width * img.height > _MAX_INPUT_PIXELS:
        ratio = (_MAX_INPUT_PIXELS / (img.width * img.height)) ** 0.5
        new_size = (int(img.width * ratio), int(img.height * ratio))
        img.thumbnail(new_size, Image.LANCZOS)
    return img


def load_pil(uploaded) -> Image.Image | None:
    if uploaded is None:
        return None
    img = Image.open(io.BytesIO(uploaded.read())).convert("RGBA")
    return _shrink_if_huge(img)



def make_zip(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def sort_speakers(speakers):
    def key(s):
        company    = (s.get("company") or "").strip().lower()
        name_parts = (s.get("name")    or "").strip().split()
        surname    = name_parts[-1].lower() if name_parts else ""
        is_mod     = bool(s.get("is_moderator", False))
        return (is_mod, company, surname)
    return sorted(speakers, key=key)


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", " ", s.lower())
    return s.strip()


def best_match(needle: str, candidates: list[str]) -> str:
    words = [w for w in _normalize(needle).split() if len(w) > 1]
    if not words:
        return "(none)"
    for c in candidates:
        c_norm = _normalize(os.path.splitext(c)[0])
        if any(w in c_norm for w in words):
            return c
    return "(none)"


def _fill_from_url(url: str) -> None:
    """Scrape a webinar page → fill fields, photo/logo pools and selections.

    Reuses the Reports-page scraper (title, speakers+photos, logos) and adds a
    best-effort date/time parse from the visible page text. Must run BEFORE
    the Step-2 widgets are instantiated (it sets their session_state keys).
    """
    import requests
    from report_core.scraper.scrape import scrape_webinar, UA

    if url.startswith("www."):
        url = "https://" + url
    html = requests.get(url, headers=UA, timeout=30).text
    data = scrape_webinar(url, html=html)

    st.session_state["session_title"] = data.get("title", "")
    st.session_state["cta_url"]       = url

    # Language: the scraper's guess defaults to EN — override with a simple
    # Spanish check on the title (accents / very common ES words)
    _lang  = data.get("language_guess", "")
    _title = (data.get("title") or "").lower()
    if _lang == "en" and re.search(
            r"[ñáéíóú¿¡]|\b(el|la|los|las|del|para|qué|como|cómo|nuevo|nueva|"
            r"mercado|almacenamiento|energía|españa)\b", _title):
        _lang = "es"
    st.session_state["_pending_language"] = _lang

    # Best-effort date/time from the visible page text
    plain = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"\s+", " ", plain)
    mdate = re.search(
        r"\b\d{1,2}\s+(?:de\s+)?(?:enero|febrero|marzo|abril|mayo|junio|julio|"
        r"agosto|septiembre|octubre|noviembre|diciembre|january|february|march|"
        r"april|may|june|july|august|september|october|november|december)"
        r"(?:\s+(?:de\s+)?\d{4})?\b", plain, re.I)
    mtime = re.search(
        r"\b\d{1,2}[:.]\d{2}\s*(?:h(?:rs)?\b|am\b|pm\b|ce[s]?t\b)?", plain, re.I)
    if mdate:
        st.session_state["date_str"] = mdate.group(0).strip()
    if mtime:
        st.session_state["time_str"] = mtime.group(0).strip()

    def _dl(u):
        try:
            r = requests.get(u, headers=UA, timeout=20)
            if r.ok and len(r.content) > 100:
                return r.content
        except Exception:
            pass
        return None

    ph_pool, lg_pool = {}, {}

    spks = data.get("speakers", [])[:6]
    st.session_state["n"] = max(len(spks), 1)
    for i in range(7):
        for k in (f"name_{i}", f"title_{i}", f"company_{i}"):
            st.session_state[k] = ""
        st.session_state[f"mod_{i}"]  = False
        st.session_state[f"psel_{i}"] = "(none)"
        st.session_state[f"lsel_{i}"] = "(none)"
    for i, sp in enumerate(spks):
        st.session_state[f"name_{i}"]    = sp.get("name", "")
        st.session_state[f"title_{i}"]   = sp.get("role", "")
        st.session_state[f"company_{i}"] = sp.get("company", "")
        st.session_state[f"mod_{i}"]     = bool(sp.get("is_moderator"))
        pu = sp.get("photo")
        if pu:
            b = _dl(pu)
            if b:
                fn = os.path.basename(pu.split("?")[0])
                ph_pool[fn] = b
                st.session_state[f"psel_{i}"] = fn

    for lu in data.get("logos", []):
        if lu.lower().endswith(".svg"):
            continue                      # PIL can't render SVG
        _bn = os.path.basename(lu.split("?")[0]).lower()
        # Skip the webinar's own hero/thumbnail images that slip past the scraper
        if any(t in _bn for t in ("miniatura", "thumb", "banner", "webinar", "hero")):
            continue
        b = _dl(lu)
        if b:
            lg_pool[os.path.basename(lu.split("?")[0])] = b

    # Match company logos to speakers by company name
    for i, sp in enumerate(spks):
        co = (sp.get("company") or "").strip()
        if co:
            m = best_match(co, list(lg_pool.keys()))
            if m != "(none)":
                st.session_state[f"lsel_{i}"] = m

    # Fresh project: replace pools, drop any editing context / loaded background
    st.session_state["_photo_pool_bytes"]   = ph_pool
    st.session_state["_logo_pool_bytes"]    = lg_pool
    st.session_state["_suppress_automatch"] = True
    st.session_state.pop("_editing_slide_id", None)
    st.session_state.pop("_editing_label",    None)
    st.session_state.pop("_loaded_bg",        None)

    extra = " (page has more than 6 — first 6 loaded)" if len(data.get("speakers", [])) > 6 else ""
    st.session_state["_load_toast"] = (
        f"✅ Loaded from page — {len(spks)} speaker(s){extra}, "
        f"{len(ph_pool)} photo(s), {len(lg_pool)} logo(s)"
    )


# ── Load-saved-project request handler ───────────────────────────────────────
# Runs BEFORE any widgets so session_state is fully populated before the
# sidebar and main body render — no second st.rerun() needed.

if "load_request" in st.session_state:
    _sid = st.session_state.pop("load_request")
    try:
        _data = load_slide(_sid)
        _form = _data.get("form", {})

        # ── Form fields ──
        st.session_state["session_title"] = _form.get("session_title", "")
        st.session_state["date_str"]      = _form.get("date_str",      "")
        st.session_state["time_str"]      = _form.get("time_str",      "")
        st.session_state["location"]      = _form.get("location",      "")
        st.session_state["cta_url"]       = _form.get("cta_url",       "")
        st.session_state["paste"]         = _form.get("paste_text",    "")

        _spks    = _form.get("speakers", [])
        _n_load  = max(len(_spks), 1)
        st.session_state["n_slider"] = _n_load
        for _i, _spk in enumerate(_spks):
            st.session_state[f"name_{_i}"]    = _spk.get("name",         "")
            st.session_state[f"title_{_i}"]   = _spk.get("title",        "")
            st.session_state[f"company_{_i}"] = _spk.get("company",      "")
            st.session_state[f"mod_{_i}"]     = _spk.get("is_moderator", False)
            st.session_state[f"psel_{_i}"]    = _spk.get("psel", "(none)")
            st.session_state[f"lsel_{_i}"]    = _spk.get("lsel", "(none)")
        for _i in range(_n_load, 7):
            for _k in (f"name_{_i}", f"title_{_i}", f"company_{_i}",
                       f"mod_{_i}", f"psel_{_i}", f"lsel_{_i}"):
                st.session_state.pop(_k, None)

        # ── Sidebar options ──
        if _data.get("theme_key") in THEMES:
            st.session_state["theme_choice"] = _data["theme_key"]
        if _data.get("language") in ["es", "en", "it", "pl"]:
            st.session_state["language"]     = _data["language"]
        if _data.get("template") in ["A", "B", "C"]:
            st.session_state["template"]     = _data["template"]

        # ── Background ──
        st.session_state["bg_lib_choice"] = _form.get("bg_lib_choice") or "(none)"

        # ── Photos & logos — use PIL Images already loaded by load_slide() ──────
        # load_slide() already resolved paths correctly (it found meta.json).
        # Converting back to bytes here is the most reliable path — no separate
        # path resolution needed, no accent-in-username issues, no missing-folder crashes.
        _ph_bytes2 = {}
        _lg_bytes2 = {}
        for _fn2, _img2 in (_data.get("photos") or {}).items():
            try:
                _buf2 = io.BytesIO()
                _img2.convert("RGBA").save(_buf2, format="PNG")
                _ph_bytes2[_fn2] = _buf2.getvalue()
            except Exception:
                pass
        for _fn2, _img2 in (_data.get("logos") or {}).items():
            try:
                _buf2 = io.BytesIO()
                _img2.convert("RGBA").save(_buf2, format="PNG")
                _lg_bytes2[_fn2] = _buf2.getvalue()
            except Exception:
                pass
        # Derive slide dir from STORE_DIR (used only for bg.png lookup below)
        _slide_dir2 = os.path.abspath(os.path.join(STORE_DIR, _sid))

        st.session_state["_photo_pool_bytes"] = _ph_bytes2
        st.session_state["_logo_pool_bytes"]  = _lg_bytes2
        st.session_state["_suppress_automatch"] = True

        # ── Custom background ─────────────────────────────────────────────────
        _bg_lib2  = _form.get("bg_lib_choice") or "(none)"
        _bg_path2 = os.path.join(_slide_dir2, "bg.png")
        if _bg_lib2 in ("", "(none)") and os.path.exists(_bg_path2):
            try:
                st.session_state["_loaded_bg"] = Image.open(_bg_path2).convert("RGBA")
            except Exception:
                st.session_state.pop("_loaded_bg", None)
        else:
            st.session_state.pop("_loaded_bg", None)

        st.session_state["_last_bg"]       = st.session_state.get("_loaded_bg")
        st.session_state["_last_theme"]    = _data.get("theme_key",  "almacenamiento")
        st.session_state["_last_language"] = _data.get("language",   "es")
        st.session_state["_last_template"] = _data.get("template",   "A")
        st.session_state["_last_form"]     = _form

        if _ph_bytes2 or _lg_bytes2:
            st.session_state["_expand_photos_expander"] = True

        # ── Restore slide preview (saved bytes = the LinkedIn version) ────────
        st.session_state.pop("last_mini_png",  None)
        st.session_state.pop("last_mini_pptx", None)
        st.session_state.pop("last_ingo_pack", None)
        st.session_state["last_linkedin_png"]  = _data["png_bytes"]  if _data.get("png_bytes")  else st.session_state.pop("last_linkedin_png",  None)
        st.session_state["last_linkedin_pptx"] = _data["pptx_bytes"] if _data.get("pptx_bytes") else st.session_state.pop("last_linkedin_pptx", None)

        st.session_state["_editing_slide_id"] = _sid
        st.session_state["_editing_label"]    = _data.get("label", "")

        n_ph = len(_ph_bytes2)
        n_lg = len(_lg_bytes2)
        st.session_state["_load_toast"] = f"✅ Loaded — {n_ph} photo(s), {n_lg} logo(s)"

    except Exception as _e:
        st.session_state["_load_error_msg"] = f"Could not load slide: {_e}"

# Apply a language chosen by "Fill from URL" BEFORE the sidebar widget renders
# (a widget's state key can't be set after the widget is instantiated).
if "_pending_language" in st.session_state:
    _pl = st.session_state.pop("_pending_language")
    if _pl in ("es", "en", "it", "pl"):
        st.session_state["language"] = _pl

# ── Sidebar ───────────────────────────────────────────────────────────────────

ata_logo_path = os.path.join(LOGO_DIR, "ata_logo.png")
if os.path.exists(ata_logo_path):
    st.sidebar.image(ata_logo_path, width=120)

st.sidebar.title("RENMAD Generator")

theme_choice = st.sidebar.selectbox(
    "Event",
    options=sorted(THEMES.keys(), key=lambda k: THEMES[k]["name"]),
    format_func=lambda k: THEMES[k]["name"],
    key="theme_choice",
)
theme = THEMES[theme_choice]
st.sidebar.markdown(
    f"<div style='display:flex;align-items:center;gap:8px;margin-top:-8px'>"
    f"<div style='width:14px;height:14px;border-radius:3px;background:{theme['hex']}'></div>"
    f"<span style='font-size:0.85em;color:#888'>{theme['label_es']}</span></div>",
    unsafe_allow_html=True,
)

language = st.sidebar.selectbox(
    "Language",
    options=["es", "en", "it", "pl"],
    format_func=lambda x: {"es": "Spanish", "en": "English",
                            "it": "Italian", "pl": "Polish"}[x],
    key="language",
)

template = st.sidebar.selectbox(
    "Slide template",
    options=["A", "B", "C"],
    format_func=lambda t: {
        "A": "Circles     — speaker photos cropped in circles",
        "B": "Silhouettes — speaker photos cut to person shape",
        "C": "Squares     — speaker photos in square cards",
    }[t],
    key="template",
)

li_variant = st.sidebar.selectbox(
    "LinkedIn variant",
    options=["normal", "starting_soon", "recording_available"],
    format_func=lambda v: {
        "normal":              "Promoción (normal)",
        "starting_soon":       "Empezamos pronto — pre-webinar",
        "recording_available": "Grabación disponible — recording",
    }[v],
    key="li_variant",
)

with st.sidebar.expander("⚙️ Advanced — override logos"):
    st.caption(
        "Event and ATA Insights logos are loaded **automatically** from the "
        "assets/logos folder based on the event you selected above. "
        "Only upload here if you want to temporarily use a different logo."
    )
    renmad_logo_file = st.file_uploader("Override event logo",       type=["png","jpg","jpeg"],
                                        key="renmad_logo")
    ata_logo_file    = st.file_uploader("Override ATA Insights logo", type=["png","jpg","jpeg"],
                                        key="ata_logo")



renmad_logo = load_pil(renmad_logo_file) if renmad_logo_file else None
ata_logo    = load_pil(ata_logo_file)    if ata_logo_file    else None

if renmad_logo is None:
    path = os.path.join(LOGO_DIR, theme["logo_filename"])
    if os.path.exists(path):
        renmad_logo = Image.open(path).convert("RGBA")
if ata_logo is None:
    path = os.path.join(LOGO_DIR, "ata_logo.png")
    if os.path.exists(path):
        ata_logo = Image.open(path).convert("RGBA")


# ── Main area ─────────────────────────────────────────────────────────────────

st.title("RENMAD Webinar Generator")

# Show any load toast / error that was stored by the load handler above
if "_load_toast" in st.session_state:
    st.toast(st.session_state.pop("_load_toast"))
if "_load_error_msg" in st.session_state:
    st.error(st.session_state.pop("_load_error_msg"))

# ── Saved Slides gallery ──────────────────────────────────────────────────────

saved      = list_slides()
editing_id = st.session_state.get("_editing_slide_id")

_gallery_label = (
    f"📂 Saved projects ({len(saved)} / {MAX_SLIDES})"
    if saved else "📂 Saved projects — empty"
)
with st.expander(_gallery_label, expanded=bool(editing_id and not saved)):

    if not saved:
        st.caption(
            "No saved projects yet. Generate a slide below and click **💾 Save project** "
            "to start your library."
        )
    else:
        COLS = 4
        for chunk in [saved[i:i+COLS] for i in range(0, len(saved), COLS)]:
            cols = st.columns(COLS)
            for col, slide in zip(cols, chunk):
                with col:
                    tb = thumb_bytes(slide["id"])
                    if tb:
                        st.image(tb, use_container_width=True)

                    is_editing = (slide["id"] == editing_id)
                    label_str  = slide.get("label", "Untitled")[:38]
                    badge      = " ✏️" if is_editing else ""
                    st.markdown(f"**{label_str}{badge}**")

                    tname = THEMES.get(slide.get("theme_key", ""), {}).get("name",
                            slide.get("theme_key", "?"))
                    date_part = (slide.get("updated_at") or "")[:10]
                    st.caption(f"{tname} · {slide.get('template','?')} · {date_part}")

                    bc1, bc2 = st.columns(2)
                    if bc1.button("✏️ Edit", key=f"load_{slide['id']}",
                                  use_container_width=True):
                        st.session_state["load_request"] = slide["id"]
                        st.rerun()
                    if bc2.button("🗑 Del", key=f"del_{slide['id']}",
                                  use_container_width=True):
                        if editing_id == slide["id"]:
                            st.session_state.pop("_editing_slide_id",  None)
                            st.session_state.pop("_editing_label",     None)
                        delete_slide(slide["id"])
                        st.rerun()

st.divider()

# ── Step 1: Fill from URL, or Paste & Parse ───────────────────────────────────

st.subheader("1. Fill from your webinar page — or paste the info below")
st.caption(
    "Paste the webinar page URL (my.atainsights.com) and click **Fetch ⤵** — "
    "title, speakers, photos and company logos are pulled automatically, and "
    "the page URL becomes the registration link. Review the fields after."
)
_uc1, _uc2 = st.columns([4, 1])
webinar_url = _uc1.text_input(
    "Webinar URL", key="webinar_url", label_visibility="collapsed",
    placeholder="https://my.atainsights.com/webinar/…",
)
if _uc2.button("Fetch ⤵", type="primary", use_container_width=True, key="fetch_btn"):
    _wu = (webinar_url or "").strip()
    if not _wu.lower().startswith(("http://", "https://", "www.")):
        st.warning("Paste the full webinar page URL first.")
    else:
        with st.spinner("Reading the webinar page…"):
            try:
                _fill_from_url(_wu)
                st.rerun()
            except Exception as e:
                st.error(f"Could not read that page: {e}")

st.markdown("")
st.caption(
    "Paste any agenda text below. Click **Parse & fill ▶** and the fields in "
    "Step 2 will be filled in automatically. "
    "Format each speaker as **Name, Job title, Company** on its own line. "
    "Add **Moderador/a:** before a speaker's name to mark them as moderator."
)

paste_text = st.text_area(
    "session",
    height=230,
    placeholder=(
        "TITLE\n"
        "Write the webinar title here\n"
        "\n"
        "DATE\n"
        "e.g. 23 October 2026\n"
        "\n"
        "TIME\n"
        "e.g. 11:00h CEST\n"
        "\n"
        "LOCATION\n"
        "e.g. Madrid / Online\n"
        "\n"
        "REGISTRATION URL\n"
        "e.g. www.renmad.com/register\n"
        "\n"
        "SPEAKERS  (Name, Role, Company)\n"
        "First Last, Role, Company\n"
        "First Last, Role, Company\n"
        "Moderator: First Last, Role, Company"
    ),
    key="paste",
    label_visibility="collapsed",
)

col_btn, col_note = st.columns([1, 5])
if col_btn.button("Parse & fill ▶", type="primary", key="parse_btn"):
    if paste_text.strip():
        with st.spinner("Parsing…"):
            from utils.parse_session import parse_session
            try:
                result = parse_session(paste_text)
                spks   = result.get("speakers", [])
                count  = max(len(spks), 1)
                st.session_state["session_title"] = result.get("title",    "")
                st.session_state["date_str"]      = result.get("date_str", "")
                st.session_state["time_str"]      = result.get("time_str", "")
                st.session_state["location"]      = result.get("location", "")
                st.session_state["cta_url"]       = result.get("cta_url",  "")
                st.session_state["n"]             = count
                for i, spk in enumerate(spks):
                    st.session_state[f"name_{i}"]    = spk.get("name",         "")
                    st.session_state[f"title_{i}"]   = spk.get("title",        "")
                    st.session_state[f"company_{i}"] = spk.get("company",      "")
                    st.session_state[f"mod_{i}"]     = spk.get("is_moderator", False)
                # If NOT editing a saved project, clear everything for a fresh start.
                # If editing, keep the image pool and editing context — the user just
                # wants to update the text fields, not lose their photos/logos.
                if not st.session_state.get("_editing_slide_id"):
                    st.session_state.pop("_loaded_photos", None)
                    st.session_state.pop("_loaded_logos",  None)
                    st.session_state.pop("_loaded_bg",     None)
                    st.session_state.pop("_last_photos",   None)
                    st.session_state.pop("_last_logos",    None)
                    st.session_state.pop("_last_bg",       None)
                    st.session_state["_photo_pool_bytes"] = {}
                    st.session_state["_logo_pool_bytes"]  = {}
                st.toast(f"✅ {count} speaker(s) filled — review below, then generate")
                st.rerun()
            except Exception as e:
                st.error(f"Parse error: {e}")
    else:
        st.warning("Paste some text first.")
col_note.caption("Reads your pasted text and fills in the fields automatically.")

st.divider()

# ── Step 2: Review & edit ─────────────────────────────────────────────────────

st.subheader("2. Review & edit")

if "n" in st.session_state:
    st.session_state["n_slider"] = st.session_state.pop("n")
n_speakers = st.slider("Number of speakers  (drag ▶ to add a new empty row)", 1, 6, 3, key="n_slider")

col_t, col_url = st.columns([3, 2])
session_title = col_t.text_area(
    "Session title  (press Enter to force a line break on the slide)",
    key="session_title", height=80,
)
cta_url       = col_url.text_input("Registration URL (optional — label added automatically)",
                                    key="cta_url",
                                    placeholder="www.renmad.com/registro")

col_d, col_tm, col_loc = st.columns([2.5, 1.5, 1.5])
date_str = col_d.text_input("Date",             key="date_str",
                              placeholder="27 de noviembre de 2026")
time_str = col_tm.text_input("Time (optional)", key="time_str",
                               placeholder="11:00h CET")
location = col_loc.text_input("Location",        key="location",
                                placeholder="Madrid / Online")

# ── Photo / logo pool ─────────────────────────────────────────────────────────
# Persists in session_state. Populated on project load; user can add/remove files.
# Rendered BEFORE speaker rows so the pool is ready when dropdowns are built.

if "_photo_pool_bytes" not in st.session_state:
    st.session_state["_photo_pool_bytes"] = {}
if "_logo_pool_bytes" not in st.session_state:
    st.session_state["_logo_pool_bytes"] = {}

_ph_pool = st.session_state["_photo_pool_bytes"]
_lg_pool = st.session_state["_logo_pool_bytes"]

# ── Upload row (always visible) ──────────────────────────────────────────────
st.markdown("**📷 Speaker photos & company logos**")
_upl_ph_col, _upl_lg_col, _upl_folder_col = st.columns([2, 2, 3])

with _upl_ph_col:
    _new_ph = st.file_uploader(
        "Speaker photos", type=["png", "jpg", "jpeg"],
        accept_multiple_files=True, key="photo_files",
    )
    for _f in (_new_ph or []):
        try:
            _f.seek(0)
            st.session_state["_photo_pool_bytes"][_f.name] = _f.read()
        except Exception:
            pass

with _upl_lg_col:
    _new_lg = st.file_uploader(
        "Company logos", type=["png", "jpg", "jpeg"],
        accept_multiple_files=True, key="logo_files",
    )
    for _f in (_new_lg or []):
        try:
            _f.seek(0)
            st.session_state["_logo_pool_bytes"][_f.name] = _f.read()
        except Exception:
            pass

with _upl_folder_col:
    st.caption("Or load from a folder — filenames with 'logo' → logos; rest → photos")
    _folder_path = st.text_input(
        "Folder path", placeholder=r"C:\Users\Belén\Desktop\Panel 1",
        key="folder", label_visibility="collapsed",
    )
    if _folder_path and os.path.isdir(_folder_path):
        for _f in sorted(os.listdir(_folder_path)):
            if not _f.lower().endswith((".png", ".jpg", ".jpeg")):
                continue
            try:
                _img_bytes = open(os.path.join(_folder_path, _f), "rb").read()
                _stem = os.path.splitext(_f)[0].lower()
                if "logo" in _stem:
                    st.session_state["_logo_pool_bytes"][_f]  = _img_bytes
                else:
                    st.session_state["_photo_pool_bytes"][_f] = _img_bytes
            except Exception:
                pass
    elif _folder_path:
        st.warning("Folder not found — check the path.")

# ── Loaded files list (collapsible) ──────────────────────────────────────────
_exp_open = st.session_state.pop("_expand_photos_expander", False)
if _ph_pool or _lg_pool:
    _pool_label = f"📂 Loaded files — {len(_ph_pool)} photo(s), {len(_lg_pool)} logo(s)  _(click to remove)_"
    with st.expander(_pool_label, expanded=_exp_open):
        _ph_col, _lg_col = st.columns(2)
        with _ph_col:
            for _fn in list(_ph_pool.keys()):
                _rc1, _rc2 = st.columns([5, 1])
                _rc1.caption(f"📷 {_fn}")
                if _rc2.button("✕", key=f"rm_ph_{_fn}", help=f"Remove {_fn}"):
                    del st.session_state["_photo_pool_bytes"][_fn]
                    for _j in range(8):
                        if st.session_state.get(f"psel_{_j}") == _fn:
                            st.session_state[f"psel_{_j}"] = "(none)"
                    st.rerun()
        with _lg_col:
            for _fn in list(_lg_pool.keys()):
                _rc1, _rc2 = st.columns([5, 1])
                _rc1.caption(f"🏷 {_fn}")
                if _rc2.button("✕", key=f"rm_lg_{_fn}", help=f"Remove {_fn}"):
                    del st.session_state["_logo_pool_bytes"][_fn]
                    for _j in range(8):
                        if st.session_state.get(f"lsel_{_j}") == _fn:
                            st.session_state[f"lsel_{_j}"] = "(none)"
                    st.rerun()

# Re-read pool after any uploads/removals above
_ph_pool = st.session_state["_photo_pool_bytes"]
_lg_pool = st.session_state["_logo_pool_bytes"]

# Auto-match when pool changes; skip on first render after a project load
_photo_keys = ["(none)"] + list(_ph_pool.keys())
_logo_keys  = ["(none)"] + list(_lg_pool.keys())
_file_sig   = tuple(sorted(_ph_pool.keys())) + tuple(sorted(_lg_pool.keys()))
_suppress   = st.session_state.pop("_suppress_automatch", False)

if not _suppress and st.session_state.get("_file_sig") != _file_sig and _file_sig:
    st.session_state["_file_sig"] = _file_sig
    for _i in range(n_speakers):
        _nm = st.session_state.get(f"name_{_i}", "").strip()
        _co = st.session_state.get(f"company_{_i}", "").strip()
        if _nm:
            _ap = best_match(_nm, list(_ph_pool.keys()))
            _al = best_match(_co, list(_lg_pool.keys()))
            st.session_state[f"psel_{_i}"] = _ap if _ap in _photo_keys else "(none)"
            st.session_state[f"lsel_{_i}"] = _al if _al in _logo_keys  else "(none)"
elif _suppress:
    st.session_state["_file_sig"] = _file_sig
    for _i in range(n_speakers):
        if st.session_state.get(f"psel_{_i}") not in _photo_keys:
            st.session_state[f"psel_{_i}"] = "(none)"
        if st.session_state.get(f"lsel_{_i}") not in _logo_keys:
            st.session_state[f"lsel_{_i}"] = "(none)"

# ── Speaker table ─────────────────────────────────────────────────────────────
st.markdown("**Speakers**")
_has_pool = bool(_ph_pool or _lg_pool)

if _has_pool:
    _hcols = st.columns([2.5, 2, 2, 2, 2, 0.6])
    _hcols[0].markdown("**Name**");   _hcols[1].markdown("**Job title**")
    _hcols[2].markdown("**Company**"); _hcols[3].markdown("**Photo**")
    _hcols[4].markdown("**Logo**");   _hcols[5].markdown("**Mod?**")
else:
    _hcols = st.columns([3, 2.5, 2.5, 0.7])
    _hcols[0].markdown("**Name**"); _hcols[1].markdown("**Job title**")
    _hcols[2].markdown("**Company**"); _hcols[3].markdown("**Mod?**")

speakers_text = []
for i in range(n_speakers):
    if _has_pool:
        c0, c1, c2, cph, clg, c3 = st.columns([2.5, 2, 2, 2, 2, 0.6])
    else:
        c0, c1, c2, c3 = st.columns([3, 2.5, 2.5, 0.7])
    name    = c0.text_input(f"Name {i+1}",    key=f"name_{i}",    label_visibility="collapsed")
    title_s = c1.text_input(f"Title {i+1}",   key=f"title_{i}",   label_visibility="collapsed")
    company = c2.text_input(f"Company {i+1}", key=f"company_{i}", label_visibility="collapsed")
    is_mod  = c3.checkbox(f"Mod {i+1}",       key=f"mod_{i}",     label_visibility="collapsed")
    photo_img = logo_img = None
    if _has_pool:
        _psel = cph.selectbox(
            f"Photo {i+1}", _photo_keys, key=f"psel_{i}", label_visibility="collapsed",
        )
        _lsel = clg.selectbox(
            f"Logo {i+1}",  _logo_keys,  key=f"lsel_{i}", label_visibility="collapsed",
        )
        # Convert stored bytes → PIL Image at point of use (bytes survive rerenders)
        _ph_b = _ph_pool.get(_psel)
        _lg_b = _lg_pool.get(_lsel)
        photo_img = Image.open(io.BytesIO(_ph_b)).convert("RGBA") if _ph_b else None
        logo_img  = Image.open(io.BytesIO(_lg_b)).convert("RGBA") if _lg_b else None
    speakers_text.append({
        "name": name.strip(), "title": title_s.strip(),
        "company": company.strip(), "is_moderator": is_mod,
        "photo": photo_img, "company_logo": logo_img,
    })

speakers_text = [s for s in speakers_text if s["name"]]

st.divider()

# ── Step 3: Background photo ──────────────────────────────────────────────────

st.subheader("3. Background photo (optional)")
st.caption("Pick from the library, or upload your own. If none, a dark gradient is used automatically.")

bg_image: Image.Image | None = None

_bg_folder = theme["bg_folder"]
if _bg_folder == "__all__":
    lib_entries = []
    for sub in sorted(os.listdir(BG_DIR)):
        sub_path = os.path.join(BG_DIR, sub)
        if not os.path.isdir(sub_path) or sub == "__all__":
            continue
        for f in sorted(os.listdir(sub_path)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                lib_entries.append((f"{sub}/{f}", os.path.join(sub_path, f)))
    lib_folder = os.path.join(BG_DIR, "ata_insights")
else:
    lib_folder = os.path.join(BG_DIR, _bg_folder)
    lib_entries = [
        (f, os.path.join(lib_folder, f))
        for f in sorted(os.listdir(lib_folder) if os.path.isdir(lib_folder) else [])
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

bg_col_lib, bg_col_upload = st.columns([1, 1])

with bg_col_lib:
    if lib_entries:
        display_names = ["(none)"] + [name for name, _ in lib_entries]
        path_map      = {name: path for name, path in lib_entries}
        choice = st.selectbox("Pick from library", display_names, key="bg_lib_choice")
        if choice != "(none)":
            bg_image = Image.open(path_map[choice]).convert("RGBA")
            st.image(bg_image, use_container_width=True)
    else:
        save_hint = "all theme folders" if _bg_folder == "__all__" else f"assets/backgrounds/{_bg_folder}/"
        st.caption(f"Library empty — upload a photo and click 💾 to save it, or add images directly to `{save_hint}`")

with bg_col_upload:
    bg_file = st.file_uploader(
        "Or upload your own photo", type=["png", "jpg", "jpeg"], key="bg_upload"
    )
    if bg_file:
        bg_bytes = bg_file.read()
        bg_image = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
        st.image(bg_image, use_container_width=True,
                 caption="This photo will be darkened automatically")
        if st.button("💾 Save to this event's library", key="save_bg"):
            os.makedirs(lib_folder, exist_ok=True)
            save_path = os.path.join(lib_folder, bg_file.name)
            with open(save_path, "wb") as fout:
                fout.write(bg_bytes)
            st.success(f"Saved **{bg_file.name}** to the {theme['name']} library.")
            st.rerun()
    elif bg_image is None:
        # Use custom background restored from a saved slide (no library choice active)
        loaded_bg = st.session_state.get("_loaded_bg")
        if loaded_bg is not None:
            bg_image = loaded_bg
            st.image(loaded_bg, use_container_width=True,
                     caption="Background restored from saved project")


# ── Generate ──────────────────────────────────────────────────────────────────

st.markdown("")
gc1, gc2, gc3, gc4 = st.columns(4)
btn_linkedin = gc1.button("💼 Generate LinkedIn",  type="primary", use_container_width=True)
btn_mini     = gc2.button("🖼️ Generate Miniature", type="primary", use_container_width=True)
btn_ingo     = gc3.button("🌐 Generate Ingo",      type="primary", use_container_width=True)
btn_all      = gc4.button("⚡ Generate All",        type="primary", use_container_width=True)

if btn_linkedin or btn_mini or btn_ingo or btn_all:
    if not session_title and not speakers_text:
        st.warning("Add at least a session title or one speaker first.")
    else:
        sorted_spk = sort_speakers(speakers_text)
        session = {
            "title":    session_title,
            "speakers": sorted_spk,
            "date_str": date_str,
            "time_str": time_str,
            "location": location,
            "cta_url":  cta_url,
        }

        # Panel generator (Slide + LinkedIn share the same template)
        # 0 speakers → clean photo-less panel A (no empty speaker strip / silhouette)
        gen_kwargs = {}
        if len(sorted_spk) == 0:
            gen = __import__("generators.t2_panel_a", fromlist=["generate"]).generate
            gen_kwargs["hide_speakers"] = True
        elif len(sorted_spk) == 1:
            gen = __import__("generators.t1_speaker", fromlist=["generate"]).generate
        elif template == "A":
            gen = __import__("generators.t2_panel_a", fromlist=["generate"]).generate
        elif template == "B":
            gen = __import__("generators.t2_panel_b", fromlist=["generate"]).generate
        else:
            gen = __import__("generators.t2_panel_c", fromlist=["generate"]).generate

        rembg_warn = (template == "B" and any(s.get("photo") for s in sorted_spk))
        spinner_msg = ("Generating… (removing backgrounds — first run downloads model, ~30 s)"
                       if rembg_warn else "Generating…")

        with st.spinner(spinner_msg):
            try:
                do_linkedin = btn_linkedin or btn_all
                do_mini     = btn_mini     or btn_all
                do_ingo     = btn_ingo     or btn_all

                # ── Always stash photos/logos/bg/theme for Save feature ───────
                # Do this before any generation so Save works even if only
                # LinkedIn or Miniature is generated.
                st.session_state["_last_photos"]   = dict(st.session_state.get("_photo_pool_bytes", {}))
                st.session_state["_last_logos"]    = dict(st.session_state.get("_logo_pool_bytes",  {}))
                st.session_state["_last_bg"]       = bg_image
                st.session_state["_last_theme"]    = theme_choice
                st.session_state["_last_language"] = language
                st.session_state["_last_template"] = template
                # Mark that data is ready (used by Save as a "something to save" flag)
                st.session_state["_last_form"]     = {"_generated": True}

                # ── LinkedIn (CTA stripped) ───────────────────────────────────
                if do_linkedin:
                    session_li = {**session, "cta_url": ""}
                    pb_li, pgb_li = gen(session_li, theme, language,
                                        renmad_logo, bg_image, ata_logo,
                                        variant=li_variant, **gen_kwargs)
                    st.session_state["last_linkedin_pptx"] = pb_li
                    st.session_state["last_linkedin_png"]  = pgb_li

                # ── Miniature (web card, no names / titles / CTA) ────────────
                if do_mini:
                    from generators.t_miniature import generate as gen_mini
                    mini_pptx, mini_png = gen_mini(session, theme, language,
                                                   renmad_logo, bg_image, ata_logo,
                                                   template=template)
                    st.session_state["last_mini_png"]  = mini_png
                    st.session_state["last_mini_pptx"] = mini_pptx

                # ── Ingo (LinkedIn share pack: 1 per speaker + 1 attendee) ───
                if do_ingo:
                    from generators.ingo_webinar import generate_all as gen_ingo_all
                    ingo_pack = gen_ingo_all(
                        session, theme, language, bg_image, renmad_logo,
                    )
                    st.session_state["last_ingo_pack"] = ingo_pack

            except Exception as e:
                st.error(f"Generation error: {e}")
                import traceback; st.code(traceback.format_exc())


# ── Preview & downloads ───────────────────────────────────────────────────────

li_pptx_bytes = st.session_state.get("last_linkedin_pptx")
li_png_bytes  = st.session_state.get("last_linkedin_png")
mini_png      = st.session_state.get("last_mini_png")
mini_pptx     = st.session_state.get("last_mini_pptx")
ingo_pack     = st.session_state.get("last_ingo_pack") or {}

has_any = any([li_png_bytes, mini_png, ingo_pack])

if has_any:
    st.divider()
    tab_li, tab_mini, tab_ingo = st.tabs(
        ["💼 LinkedIn", "🖼️ Miniature", "🌐 Ingo"]
    )

    # ── LinkedIn tab ──────────────────────────────────────────────────────────
    with tab_li:
        if li_png_bytes:
            st.image(li_png_bytes, use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.download_button(
                "Download PNG", data=li_png_bytes,
                file_name=f"RENMAD_{theme_choice}_linkedin.png",
                mime="image/png", use_container_width=True,
            )
            if li_pptx_bytes:
                c2.download_button(
                    "Download PPTX", data=li_pptx_bytes,
                    file_name=f"RENMAD_{theme_choice}_linkedin.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
                c3.download_button(
                    "Download both (ZIP)",
                    data=make_zip({
                        f"RENMAD_{theme_choice}_linkedin.png":  li_png_bytes,
                        f"RENMAD_{theme_choice}_linkedin.pptx": li_pptx_bytes,
                    }),
                    file_name=f"RENMAD_{theme_choice}_linkedin.zip",
                    mime="application/zip", use_container_width=True,
                )
        else:
            st.caption("Click **💼 Generate LinkedIn** or **⚡ Generate All** to create this.")

    # ── Miniature tab ─────────────────────────────────────────────────────────
    with tab_mini:
        if mini_png:
            st.image(mini_png, use_container_width=True)
            mc1, mc2 = st.columns(2)
            mc1.download_button(
                "Download Miniature PNG", data=mini_png,
                file_name=f"RENMAD_{theme_choice}_miniature.png",
                mime="image/png", use_container_width=True,
            )
            if mini_pptx:
                mc2.download_button(
                    "Download Miniature PPTX", data=mini_pptx,
                    file_name=f"RENMAD_{theme_choice}_miniature.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
        else:
            st.caption("Click **🖼️ Generate Miniature** or **⚡ Generate All** to create this.")

    # ── Ingo tab ──────────────────────────────────────────────────────────────
    with tab_ingo:
        if ingo_pack:
            spk_png = ingo_pack.get("ingo_speaker.png")
            att_png = ingo_pack.get("ingo_attendee.png")

            col_s, col_a = st.columns(2)
            with col_s:
                st.markdown("**Speaker template**")
                if spk_png:
                    st.image(spk_png, use_container_width=True)
                    st.download_button(
                        "Download speaker PNG", data=spk_png,
                        file_name=f"RENMAD_{theme_choice}_ingo_speaker.png",
                        mime="image/png", use_container_width=True,
                        key="dl_ingo_speaker",
                    )
            with col_a:
                st.markdown("**Attendee template**")
                if att_png:
                    st.image(att_png, use_container_width=True)
                    st.download_button(
                        "Download attendee PNG", data=att_png,
                        file_name=f"RENMAD_{theme_choice}_ingo_attendee.png",
                        mime="image/png", use_container_width=True,
                        key="dl_ingo_attendee",
                    )

            zip_payload = {f"RENMAD_{theme_choice}_{n}": b for n, b in ingo_pack.items()}
            st.download_button(
                "📦 Download both Ingo templates (ZIP)",
                data=make_zip(zip_payload),
                file_name=f"RENMAD_{theme_choice}_ingo_pack.zip",
                mime="application/zip", use_container_width=True,
            )
            st.caption("Ingo overlays the sharer's LinkedIn picture on the right side automatically at share time.")
        else:
            st.caption("Click **🌐 Generate Ingo** or **⚡ Generate All** to create the speaker + attendee LinkedIn templates.")

    # ── Download ALL as ZIP ───────────────────────────────────────────────────
    all_files = {}
    if li_png_bytes:  all_files[f"RENMAD_{theme_choice}_linkedin.png"]   = li_png_bytes
    if li_pptx_bytes: all_files[f"RENMAD_{theme_choice}_linkedin.pptx"]  = li_pptx_bytes
    if mini_png:      all_files[f"RENMAD_{theme_choice}_miniature.png"]  = mini_png
    if mini_pptx:    all_files[f"RENMAD_{theme_choice}_miniature.pptx"] = mini_pptx
    for n, b in ingo_pack.items():
        all_files[f"RENMAD_{theme_choice}_{n}"] = b

    if len(all_files) > 2:
        st.download_button(
            "📦 Download all files (ZIP)",
            data=make_zip(all_files),
            file_name=f"RENMAD_{theme_choice}_all.zip",
            mime="application/zip",
            use_container_width=True,
        )

    # ── Save / Update project (tied to the LinkedIn version) ─────────────────
    if li_png_bytes:
        st.divider()
        editing_id = st.session_state.get("_editing_slide_id")
        _lf        = st.session_state.get("_last_form", {})

        sc1, sc2 = st.columns([5, 1.5])
        default_label = (
            st.session_state.get("_editing_label")
            or (_lf.get("session_title") or "").replace("\n", " ").strip()
            or session_title.replace("\n", " ").strip()
            or "My project"
        )
        save_label = sc1.text_input(
            "Project name", value=default_label, key="save_label_input",
            placeholder="e.g.  Panel 2 — Almacenamiento · Morning session",
        )

        def _build_current_form():
            """Build form_state from the live widget values (always up-to-date)."""
            return {
                "paste_text":    st.session_state.get("paste", ""),
                "session_title": session_title,
                "date_str":      date_str,
                "time_str":      time_str,
                "location":      location,
                "cta_url":       cta_url,
                "n_speakers":    n_speakers,
                "bg_lib_choice": st.session_state.get("bg_lib_choice", "(none)"),
                "speakers": [
                    {
                        "name":         st.session_state.get(f"name_{j}",    "").strip(),
                        "title":        st.session_state.get(f"title_{j}",   "").strip(),
                        "company":      st.session_state.get(f"company_{j}", "").strip(),
                        "is_moderator": st.session_state.get(f"mod_{j}",     False),
                        "psel":         st.session_state.get(f"psel_{j}",    "(none)"),
                        "lsel":         st.session_state.get(f"lsel_{j}",    "(none)"),
                    }
                    for j in range(n_speakers)
                    if st.session_state.get(f"name_{j}", "").strip()
                ],
            }

        def _current_photos():
            """Convert bytes pool → {filename: PIL.Image} for save_slide()."""
            return {
                fn: Image.open(io.BytesIO(b)).convert("RGBA")
                for fn, b in (st.session_state.get("_photo_pool_bytes") or {}).items()
            }

        def _current_logos():
            """Convert bytes pool → {filename: PIL.Image} for save_slide()."""
            return {
                fn: Image.open(io.BytesIO(b)).convert("RGBA")
                for fn, b in (st.session_state.get("_logo_pool_bytes") or {}).items()
            }

        def _current_bg():
            return st.session_state.get("_last_bg")

        # Single save button — overwrites in place if editing an existing project,
        # creates a new one otherwise.
        _btn_label = "💾 Save" if editing_id else "💾 Save as new"
        if sc2.button(_btn_label, use_container_width=True, type="primary"):
            saved_id = save_slide(
                label      = save_label,
                theme_key  = st.session_state.get("_last_theme",    theme_choice),
                language   = st.session_state.get("_last_language", language),
                template   = st.session_state.get("_last_template", template),
                form_state = _build_current_form(),
                png_bytes  = li_png_bytes,
                pptx_bytes = li_pptx_bytes,
                photos     = _current_photos(),
                logos      = _current_logos(),
                bg_image   = _current_bg(),
                slide_id   = editing_id,   # None → new file; set → overwrite
            )
            st.session_state["_editing_slide_id"] = saved_id
            st.session_state["_editing_label"]    = save_label
            st.toast(f"✅ Saved: **{save_label}**")
            st.rerun()
