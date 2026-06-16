# -*- coding: utf-8 -*-
"""
📅 Event Image Generator — bulk per-event marketing material.

Three-step flow:
  1. Pick or create the event (sidebar).
  2. Fill the event details + sponsors/logos (shared inputs).
  3. Choose ONE output to make — Ingo, Marketing partners, or Logo wall.

Single "Role" field per row. The system infers tier/rank automatically:
  • "Diamond" / "Platinum" / "Global" / "Gold" / "Silver" / "Bronze" → "{TIER} SPONSOR"
  • "Standard" → just "SPONSOR"
  • Anything else (e.g. "Knowledge Partner", "Media Partner") → verbatim on banner

Logo workflow (mirrors the slide app pattern that's proven to work):
  • Upload all logos to a shared pool
  • Paste Company + Role into the table
  • For each row, pick the logo from a per-row selectbox below the table
"""
import io
import json
import os
import re
import unicodedata
import zipfile
from datetime import datetime
from difflib import SequenceMatcher

import streamlit as st
from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THEMES, LANGUAGE_STRINGS
from generators.event_marketing_pack import generate_marketing_pack, _format_event_date
from generators.t_ingo import generate as _generate_ingo


# ── Paths ────────────────────────────────────────────────────────────────────
_HERE     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.normpath(os.path.join(_HERE, "..", "event_data"))
BG_DIR    = os.path.normpath(os.path.join(_HERE, "..", "assets", "backgrounds"))
os.makedirs(DATA_DIR, exist_ok=True)

NO_LOGO = "— no logo —"


# ── SVG support ──────────────────────────────────────────────────────────────
# PIL can't open SVG natively. We use PyMuPDF (fitz) which ships its own native
# renderer in the pip wheel (no Cairo / GTK dependency required on Windows).

def _svg_to_png_bytes(svg_bytes: bytes, target_px: int = 1200) -> tuple:
    """
    Rasterise SVG bytes to PNG bytes at ~target_px on the longest edge.
    Returns (png_bytes_or_None, error_message_or_empty).
    """
    try:
        import fitz  # PyMuPDF
    except Exception as e:
        return None, f"PyMuPDF not installed: {e}"
    try:
        doc = fitz.open(stream=svg_bytes, filetype="svg")
    except Exception as e:
        return None, f"PyMuPDF couldn't open the SVG: {e}"
    try:
        if doc.page_count < 1:
            return None, "SVG has no pages (file may be empty or malformed)"
        page = doc[0]
        rect = page.rect
        if rect.width <= 0 or rect.height <= 0:
            return None, ("SVG has no width/height in its root element "
                          "(missing or zero width/height/viewBox)")
        longest = max(rect.width, rect.height)
        zoom = target_px / longest
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=True)
        out = pix.tobytes("png")
        doc.close()
        return out, ""
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        return None, f"PyMuPDF render error: {e}"


# ── Tier inference ───────────────────────────────────────────────────────────
TIER_ORDER = ["diamond", "platinum", "global", "gold", "silver", "bronze", "standard", "sponsor"]
TIER_SET   = set(TIER_ORDER)


def role_to_banner_text(role: str) -> str:
    """User's free-text Role → banner label text."""
    role = (role or "").strip()
    if not role:
        return "SPONSOR"
    lower = role.lower()
    if lower in TIER_SET:
        if lower in ("standard", "sponsor"):
            return "SPONSOR"
        return f"{role.upper()} SPONSOR"
    return role.upper()


def role_rank_key(role: str) -> tuple[int, str]:
    """Return a (group_idx, sub_label) for logo-wall ordering."""
    role = (role or "").strip().lower()
    if role in TIER_SET:
        return (0, f"{TIER_ORDER.index(role):02d}")
    if "partner" in role:
        return (1, role)
    return (2, role)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower()
    return t or "x"


def _event_dir(eid: str) -> str:
    return os.path.join(DATA_DIR, eid)


def _events_list() -> list[dict]:
    out = []
    if not os.path.isdir(DATA_DIR):
        return out
    for d in os.listdir(DATA_DIR):
        meta = os.path.join(DATA_DIR, d, "event.json")
        if os.path.exists(meta):
            try:
                with open(meta, encoding="utf-8") as f:
                    data = json.load(f)
                data["_id"] = d
                out.append(data)
            except Exception:
                pass
    out.sort(key=lambda e: e.get("updated_at", ""), reverse=True)
    return out


def _save_event(eid: str, event: dict, partners: list[dict],
                logo_pool_bytes: dict[str, bytes],
                bg_image: Image.Image | None = None) -> None:
    edir = _event_dir(eid)
    os.makedirs(edir, exist_ok=True)
    logos_dir = os.path.join(edir, "logos")
    os.makedirs(logos_dir, exist_ok=True)

    used_files = {p.get("Logo file") for p in partners
                  if p.get("Logo file") and p["Logo file"] != NO_LOGO}
    for fname in used_files:
        b = logo_pool_bytes.get(fname)
        if b:
            with open(os.path.join(logos_dir, fname), "wb") as f:
                f.write(b)
    for existing in os.listdir(logos_dir):
        if existing not in used_files:
            try:
                os.remove(os.path.join(logos_dir, existing))
            except Exception:
                pass

    # Save custom-uploaded background (if any) — only if it's not from the library
    bg_path = os.path.join(edir, "bg.png")
    bg_lib = (event or {}).get("bg_lib_choice", "(none)")
    if bg_image is not None and bg_lib == "(none)":
        try:
            bg_image.convert("RGB").save(bg_path, format="PNG")
        except Exception:
            pass
    elif os.path.exists(bg_path) and bg_lib != "(none)":
        os.remove(bg_path)   # library choice supersedes any previously stored custom bg

    meta = {
        **event,
        "partners":  partners,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(os.path.join(edir, "event.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _load_event_logos(eid: str) -> dict[str, bytes]:
    out = {}
    logos_dir = os.path.join(_event_dir(eid), "logos")
    if not os.path.isdir(logos_dir):
        return out
    for fname in os.listdir(logos_dir):
        try:
            with open(os.path.join(logos_dir, fname), "rb") as f:
                out[fname] = f.read()
        except Exception:
            pass
    return out


def _best_logo_for(company: str, pool_filenames: list[str],
                   threshold: float = 0.55) -> str | None:
    """Fuzzy-match a Company name to the best logo filename in the pool."""
    co_slug = _slugify(company)
    if not co_slug:
        return None
    best_fname = None
    best_score = threshold
    for fname in pool_filenames:
        f_slug = _slugify(os.path.splitext(fname)[0])
        if not f_slug:
            continue
        if co_slug == f_slug:
            return fname        # perfect equal slug — short-circuit
        if co_slug in f_slug or f_slug in co_slug:
            score = 0.9
        else:
            score = SequenceMatcher(None, co_slug, f_slug).ratio()
        if score > best_score:
            best_score = score
            best_fname = fname
    return best_fname


def _generate_for_partner(partner: dict, event_payload: dict,
                          bg_image: Image.Image | None,
                          logo_pool_local: dict[str, bytes]) -> dict[str, bytes]:
    """Render the 4-banner marketing pack for one partner. Returns {filename: bytes}."""
    logo_img = None
    fname = partner.get("Logo file")
    if fname and fname != NO_LOGO and fname in logo_pool_local:
        try:
            logo_img = Image.open(io.BytesIO(logo_pool_local[fname])).convert("RGBA")
        except Exception:
            logo_img = None
    partner_payload = {
        "company":    partner["Company"],
        "role_label": role_to_banner_text(partner.get("Role", "")),
        "logo_img":   logo_img,
    }
    return generate_marketing_pack(event_payload, partner_payload, bg_image=bg_image)


def _build_ingo_tiers(partners_sorted_list, pool_bytes):
    """Group partners into tiers (sponsors) and secondary (partners) for t_ingo / logo wall."""
    tier_map      = {}
    secondary_map = {}

    for p in partners_sorted_list:
        role  = (p.get("Role") or "").strip()
        fname = p.get("Logo file", "")
        logo_img = None
        if fname and fname != NO_LOGO and fname in pool_bytes:
            try:
                logo_img = Image.open(io.BytesIO(pool_bytes[fname])).convert("RGBA")
            except Exception:
                logo_img = None

        gidx, _ = role_rank_key(role)
        display  = role_to_banner_text(role)

        if gidx == 0:   # named sponsor tier
            tier_map.setdefault(display, [])
            if logo_img:
                tier_map[display].append(logo_img)
        else:            # partner / host / media / other → secondary
            secondary_map.setdefault(display, [])
            if logo_img:
                secondary_map[display].append(logo_img)

    def _tier_sort(name):
        lower = name.lower()
        for i, t in enumerate(TIER_ORDER):
            if t in lower:
                return i
        return 99

    tiers     = [{"name": n, "logos": logos}
                 for n, logos in sorted(tier_map.items(), key=lambda x: _tier_sort(x[0]))]
    secondary = [{"name": n, "logos": logos} for n, logos in secondary_map.items()]
    return tiers, secondary


def _renmad_logo_img() -> Image.Image | None:
    """Load the RENMAD events logo from assets, if present."""
    _logo_dir = os.path.normpath(os.path.join(_HERE, "..", "assets", "logos"))
    for _rname in ("logo_renmad_events.png", "renmad_logo.png", "logo_renmad.png"):
        _rpath = os.path.join(_logo_dir, _rname)
        if os.path.exists(_rpath):
            try:
                return Image.open(_rpath).convert("RGBA")
            except Exception:
                return None
    return None


# ── Page chrome ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Event Image Generator", page_icon="📅", layout="wide")
st.title("📅 Event Image Generator")
st.caption(
    "Pick the event (sidebar), choose **which image you want to make** "
    "(Ingo · Marketing partners · Logo wall), fill in the details and generate."
)


# ── Sidebar: pick / create the event ─────────────────────────────────────────
existing = _events_list()

with st.sidebar:
    st.header("📅 Events")
    st.caption("Pick the event you're working on, or create a new one.")
    options = ["➕ New event"] + [f"📁 {e.get('name', e['_id'])}" for e in existing]
    pick = st.selectbox("Open or create", options, key="event_pick")

    if pick == "➕ New event":
        active_event_id = None
        loaded_event = None
    else:
        idx = options.index(pick) - 1
        active_event_id = existing[idx]["_id"]
        loaded_event = existing[idx]

    st.divider()
    if active_event_id:
        st.success(f"✏️ Editing **{loaded_event.get('name', active_event_id)}**")
        if st.button("🗑️ Delete this event", use_container_width=True,
                     type="secondary"):
            import shutil
            try:
                shutil.rmtree(_event_dir(active_event_id))
                for k in list(st.session_state.keys()):
                    if k.startswith("_evt_") or k.startswith("logo_pick_") or k == "partners_table":
                        del st.session_state[k]
                st.toast(f"Deleted {active_event_id}")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't delete: {e}")
    else:
        st.info("Creating a new event. Fill in the details and click **💾 Save event**.")


# ── Detect event switch and POPULATE session_state directly ─────────────────
# Streamlit widgets only honour `value=` if their key isn't already in
# session_state. The most reliable pattern (used in the slides app too) is to
# directly write the loaded values into session_state BEFORE the widgets render.
import datetime as _dt_init

_last_evt = st.session_state.get("_last_active_event_id", "<unset>")
if _last_evt != (active_event_id or "_new_"):
    # Wipe per-row logo selectboxes (their count depends on the loaded event)
    for k in list(st.session_state.keys()):
        if k.startswith("logo_pick_"):
            del st.session_state[k]
    # Reset bulk-paste accumulator, the paste box, and the data_editor version
    for k in list(st.session_state.keys()):
        if (k.startswith("_partners_v_") or k.startswith("_partners_extras_")
                or k.startswith("bulk_paste_") or k.startswith("_paste_v_")):
            del st.session_state[k]
    # Reset Ingo stats / variant (scoped per-event via widget keys so these clear automatically)
    for k in list(st.session_state.keys()):
        if k.startswith("_ingo_"):
            del st.session_state[k]

    if loaded_event:
        st.session_state["ev_name"]  = loaded_event.get("name", "")
        st.session_state["ev_theme"] = loaded_event.get("theme_key", "datacenters")
        st.session_state["ev_lang"]  = loaded_event.get("language", "es")
        st.session_state["ev_loc"]   = loaded_event.get("location", "")

        # Date range — single calendar picker accepts a (start, end) tuple
        _s = loaded_event.get("start_date")
        _e = loaded_event.get("end_date")
        try:
            _ds = _dt_init.date.fromisoformat(_s) if _s else _dt_init.date.today()
        except (ValueError, TypeError):
            _ds = _dt_init.date.today()
        try:
            _de = _dt_init.date.fromisoformat(_e) if _e else _ds
        except (ValueError, TypeError):
            _de = _ds
        st.session_state["ev_date_range"] = (_ds, _de)

        st.session_state["ev_bg_choice"] = loaded_event.get("bg_lib_choice", "(none)")

        # Pre-fill each row's logo selectbox from the saved event
        _saved_partners = loaded_event.get("partners", []) or []
        for i, p in enumerate(_saved_partners):
            st.session_state[f"logo_pick_{i}"] = p.get("Logo file", NO_LOGO)
    else:
        # "➕ New event" → blank slate (skip partners_table — handled by widget key)
        for k in ("ev_name", "ev_theme", "ev_lang", "ev_loc",
                  "ev_date_range", "ev_bg_choice", "ev_bg_upload"):
            st.session_state.pop(k, None)

    st.session_state["_last_active_event_id"] = (active_event_id or "_new_")


# ── Logo pool persisted in session_state ─────────────────────────────────────
pool_key = f"_evt_logo_pool_{active_event_id or 'new'}"
if pool_key not in st.session_state:
    pool: dict[str, bytes] = {}
    if active_event_id:
        pool = _load_event_logos(active_event_id)
    st.session_state[pool_key] = pool
logo_pool: dict[str, bytes] = st.session_state[pool_key]


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 · WHAT DO YOU WANT TO CREATE?  (pick first — this is the headline choice)
# ══════════════════════════════════════════════════════════════════════════════
st.header("1 · What do you want to create?")

MODE_INGO    = "📸 Ingo"
MODE_PARTNER = "🎨 Marketing partners"
MODE_WALL    = "🖼️ Logo wall"

mode = st.radio(
    "Pick the image you want to make",
    [MODE_INGO, MODE_PARTNER, MODE_WALL],
    horizontal=True,
    key="event_output_mode",
    label_visibility="collapsed",
)
st.caption({
    MODE_INGO:    "📸 **Ingo** — the 1200×630 event infographic (Event · Speaker · Attendee · Sponsor), ES + EN.",
    MODE_PARTNER: "🎨 **Marketing partners** — 4 banners per sponsor/partner, with the event background.",
    MODE_WALL:    "🖼️ **Logo wall** — the 1920px logo wall, sponsors ordered by tier, ES + EN.",
}[mode])
st.caption("Fill in the event details below, then click **generate** on your chosen option at the end.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 · EVENT DETAILS  (shared by every output)
# ══════════════════════════════════════════════════════════════════════════════
st.header("2 · Event details")

c1, c2, c3 = st.columns([2, 1.2, 1])
event_name = c1.text_input("Event name", key="ev_name",
                           placeholder="e.g. RENMAD Datacenters 2026")

theme_keys = sorted(THEMES.keys(), key=lambda k: THEMES[k]["name"])
default_theme = (loaded_event or {}).get("theme_key", "datacenters")
theme_idx = theme_keys.index(default_theme) if default_theme in theme_keys else 0
theme_key = c2.selectbox(
    "Theme", options=theme_keys,
    format_func=lambda k: THEMES[k]["name"],
    index=theme_idx, key="ev_theme",
)

LANGS = {"es": "Spanish", "en": "English", "it": "Italian", "pl": "Polish"}
default_lang = (loaded_event or {}).get("language", "es")
language = c3.selectbox(
    "Event language", options=list(LANGS.keys()),
    format_func=lambda k: LANGS[k],
    index=list(LANGS.keys()).index(default_lang) if default_lang in LANGS else 0,
    key="ev_lang",
)

import datetime as _dt

# Structured dates: single range picker (airline-style — click start, click end).
_today = _dt.date.today()
_saved_start = (loaded_event or {}).get("start_date")
_saved_end   = (loaded_event or {}).get("end_date")
try:
    _default_start = _dt.date.fromisoformat(_saved_start) if _saved_start else _today
except (ValueError, TypeError):
    _default_start = _today
try:
    _default_end = _dt.date.fromisoformat(_saved_end) if _saved_end else _default_start
except (ValueError, TypeError):
    _default_end = _default_start

c4, c5 = st.columns([1.5, 1])
date_range = c4.date_input(
    "Event dates (pick start, then end)",
    value=(_default_start, _default_end),
    key="ev_date_range",
    format="DD/MM/YYYY",
)

# date_input returns a tuple in range mode. Until both dates are picked it may
# transiently return a 1-element tuple — handle both.
if isinstance(date_range, (list, tuple)):
    if len(date_range) >= 2:
        start_date, end_date = date_range[0], date_range[1]
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date = end_date = _today
else:
    start_date = end_date = date_range

location = c5.text_input("Location", key="ev_loc")

# Preview the auto-localised date (so the user sees what will end up on the banner)
_dt_preview_en = _format_event_date(start_date.isoformat(), end_date.isoformat(), "en")
_dt_preview_lang = _format_event_date(start_date.isoformat(), end_date.isoformat(), language)
st.caption(
    f"📅 Banner will show: **EN** `{_dt_preview_en.upper()}` · "
    f"**{LANGS[language]}** `{_dt_preview_lang.upper()}`"
)


# ── Background photo (event-level look; used by the Partner-marketing banners) ─
# Tucked into a collapsed expander to keep the page tidy. The code inside still
# runs every render, so `bg_image` is always resolved regardless of expand state.
bg_image: Image.Image | None = None

with st.expander("🖼️ Background photo (optional — used by Partner-marketing banners)",
                 expanded=False):
    # Build library entries based on the selected theme
    _bg_folder = THEMES[theme_key].get("bg_folder", theme_key)
    if _bg_folder == "__all__":
        lib_entries = []
        for sub in sorted(os.listdir(BG_DIR) if os.path.isdir(BG_DIR) else []):
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

    saved_bg_choice = (loaded_event or {}).get("bg_lib_choice", "(none)")
    saved_custom_bg = os.path.join(_event_dir(active_event_id), "bg.png") if active_event_id else None

    bg_col_lib, bg_col_upload = st.columns([1, 1])

    with bg_col_lib:
        if lib_entries:
            display_names = ["(none)"] + [name for name, _ in lib_entries]
            path_map      = {name: path for name, path in lib_entries}
            default_idx = display_names.index(saved_bg_choice) if saved_bg_choice in display_names else 0
            choice = st.selectbox("Pick from library", display_names,
                                  index=default_idx, key="ev_bg_choice")
            if choice != "(none)":
                bg_image = Image.open(path_map[choice]).convert("RGBA")
                st.image(bg_image, use_container_width=True)
        else:
            save_hint = ("all theme folders" if _bg_folder == "__all__"
                         else f"assets/backgrounds/{_bg_folder}/")
            st.caption(f"Library empty — upload a photo or add images directly to `{save_hint}`")
            choice = "(none)"

    with bg_col_upload:
        bg_file = st.file_uploader(
            "Or upload your own photo",
            type=["png", "jpg", "jpeg"], key="ev_bg_upload",
        )
        if bg_file:
            bg_bytes = bg_file.getvalue()   # non-destructive
            bg_image = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
            st.image(bg_image, use_container_width=True,
                     caption="This photo will be darkened automatically")
            if st.button("💾 Save to this event's library", key="ev_save_bg",
                         disabled=not _bg_folder or _bg_folder == "__all__"):
                os.makedirs(lib_folder, exist_ok=True)
                save_path = os.path.join(lib_folder, bg_file.name)
                with open(save_path, "wb") as fout:
                    fout.write(bg_bytes)
                st.success(f"Saved **{bg_file.name}** to the {THEMES[theme_key]['name']} library.")
                st.rerun()
        elif bg_image is None and saved_custom_bg and os.path.exists(saved_custom_bg):
            try:
                bg_image = Image.open(saved_custom_bg).convert("RGBA")
                st.image(bg_image, use_container_width=True,
                         caption="Restored from this event's saved data")
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 · SPONSORS & LOGOS  (shared by every output)
# ══════════════════════════════════════════════════════════════════════════════
st.header("3 · Sponsors & logos")

# ── Logo pool ────────────────────────────────────────────────────────────────
st.markdown("**Logo pool** — upload all the event logos here; then assign each one to a company.")

uploads = st.file_uploader(
    "Drop logo files here (PNG, JPG, SVG)",
    type=["png", "jpg", "jpeg", "svg"],
    accept_multiple_files=True, key="logo_uploads",
)
if uploads:
    svg_failures: list[tuple[str, str]] = []   # (filename, error_message)
    for f in uploads:
        raw = f.getvalue()
        if f.name.lower().endswith(".svg"):
            converted, err = _svg_to_png_bytes(raw)
            if converted is None:
                svg_failures.append((f.name, err))
                continue
            logo_pool[os.path.splitext(f.name)[0] + ".png"] = converted
        else:
            logo_pool[f.name] = raw
    st.session_state[pool_key] = logo_pool

    if svg_failures:
        for fname, err in svg_failures:
            st.error(
                f"⚠️ Couldn't convert **{fname}** — {err}\n\n"
                "Fix: convert SVG to PNG with https://convertio.co/svg-png/ "
                "(drag → click → download, 5 seconds), then upload the PNG."
            )

if logo_pool:
    with st.expander(f"📁 Logo pool — {len(logo_pool)} file(s)", expanded=False):
        ncols = 6
        cols = st.columns(ncols)
        for i, (fname, b) in enumerate(sorted(logo_pool.items())):
            with cols[i % ncols]:
                st.image(b, caption=fname, use_container_width=True)
                if st.button("🗑️", key=f"del_logo_{fname}", help=f"Remove {fname}"):
                    del logo_pool[fname]
                    st.session_state[pool_key] = logo_pool
                    st.rerun()

# ── Sponsors & partners table ────────────────────────────────────────────────
st.markdown(
    """
**Sponsors & partners** — one column for the role; the system infers the rest:

| You type | Banner shows | Logo wall |
|---|---|---|
| `Diamond` / `Platinum` / `Global` / `Gold` / `Silver` / `Bronze` | `{TIER} SPONSOR` | Sponsor (by tier) |
| `Standard` *(or blank)* | `SPONSOR` | Sponsor tier 7 |
| `Knowledge Partner` / `Media Partner` / *freeform* | uppercase verbatim | Partner / Other |
""",
    unsafe_allow_html=False,
)

# Initialise from saved event or single empty row
default_partners = (loaded_event or {}).get("partners", [])
if not default_partners:
    default_partners = [{"Company": "", "Role": "", "Logo file": NO_LOGO}]

table_init = [{"Company": p.get("Company", ""), "Role": p.get("Role", "")}
              for p in default_partners]

# Bulk paste from Excel — solves Streamlit's multi-column paste issue.
# Paste here → clicking Add creates real rows, one per line.
#
# NOTE: the paste box key carries a per-event VERSION suffix. To clear the box
# after a bulk-add we simply bump that version and rerun, so the text_area
# re-instantiates empty. We must NOT assign st.session_state[paste_key] = ""
# directly — Streamlit forbids mutating a widget's state key after the widget
# has been instantiated in the same run (that was the StreamlitAPIException).
_paste_v_key = f"_paste_v_{active_event_id or 'new'}"
_paste_v = st.session_state.get(_paste_v_key, 0)
paste_key = f"bulk_paste_{active_event_id or 'new'}_v{_paste_v}"

with st.expander("📋 Paste the list of companies (bulk add)", expanded=True):
    st.caption(
        "Paste one company per line, in **any format** — works pasted from Excel, "
        "Word, email or Notion. Company first, role after, separated by a comma, "
        "dash, slash, semicolon, tab or parentheses. If you only put the company, "
        "the role is left blank."
    )
    paste_text = st.text_area(
        "Paste here", height=150, key=paste_key,
        placeholder=("HILTI, Diamond\n"
                     "Linklaters - Gold\n"
                     "Acme Media | Media Partner\n"
                     "Endesa (Platinum)\n"
                     "Iberdrola"),
    )
    bp1, bp2 = st.columns([1, 3])
    add_bulk = bp1.button("➕ Add to the table", use_container_width=True,
                          disabled=not paste_text.strip())
    bp2.caption("Each line = one company. Then assign each one's logo below.")

# data_editor's key MUST be unique per event. Streamlit forbids
# st.session_state[key] = ... for data_editor, so the only way to "load" data is
# to bump the widget key and pass new data as the positional argument.
_partners_version_key = f"_partners_v_{active_event_id or 'new'}"
_partners_extras_key  = f"_partners_extras_{active_event_id or 'new'}"
_partners_version = st.session_state.get(_partners_version_key, 0)
_partners_extras  = st.session_state.get(_partners_extras_key, [])

# Apply bulk paste BEFORE rendering the data_editor
if add_bulk and paste_text.strip():
    def _split_company_role(line):
        line = re.sub(r"^[\s•·*▪‣]+", "", line)               # drop bullets / leading space
        line = re.sub(r"^[-–]\s+", "", line).strip()          # drop a leading "- " bullet
        if not line:
            return None
        for sep in ("\t", "|", ";"):                          # explicit column separators
            if sep in line:
                a, _, b = line.partition(sep); return a.strip(), b.strip()
        m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", line)        # Company (Role)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        m = re.match(r"^(.*?)\s+[–-]\s+(.*)$", line)           # Company - Role  (spaced dash)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        if "," in line:                                       # Company, Role
            a, _, b = line.partition(","); return a.strip(), b.strip()
        return line.strip(), ""

    new_rows = []
    for line in paste_text.strip().splitlines():
        cr = _split_company_role(line)
        if cr and cr[0]:
            new_rows.append({"Company": cr[0], "Role": cr[1]})
    if new_rows:
        _partners_extras = list(_partners_extras) + new_rows
        st.session_state[_partners_extras_key] = _partners_extras
        st.session_state[_partners_version_key] = _partners_version + 1
        st.session_state[_paste_v_key] = _paste_v + 1   # bump → paste box clears on rerun
        st.toast(f"Added {len(new_rows)} row(s) from bulk paste")
        st.rerun()

# Merge saved-event partners with anything added via bulk paste this session
table_init_merged = list(table_init) + list(_partners_extras)
if any(r.get("Company", "").strip() for r in table_init_merged):
    table_init_merged = [r for r in table_init_merged if r.get("Company", "").strip()]
    if not table_init_merged:
        table_init_merged = [{"Company": "", "Role": ""}]

_partners_table_key = f"partners_table_{active_event_id or 'new'}_v{_partners_version}"

table = st.data_editor(
    table_init_merged,
    num_rows="dynamic",
    column_config={
        "Company": st.column_config.TextColumn(
            "Company", required=True, width="medium",
            help="Used as the filename for the generated banners.",
        ),
        "Role": st.column_config.TextColumn(
            "Role", width="medium",
            help="Either a tier (Diamond, Gold, …) or a freeform label "
                 "(e.g. 'Knowledge Partner').",
        ),
    },
    use_container_width=True,
    key=_partners_table_key,
)

# ── Assign logos (per-row selectbox — same pattern as the slides app) ─────────
st.markdown("**Assign a logo to each company**")

pool_options = [NO_LOGO] + sorted(logo_pool.keys())

if not logo_pool:
    st.info("📤 Upload logos above first, then you can assign them here.")

auto_col1, auto_col2 = st.columns([1, 3])
if auto_col1.button("🔗 Auto-match by name", use_container_width=True,
                    disabled=not logo_pool):
    pool_filenames = list(logo_pool.keys())
    matched = 0
    not_matched = []
    for i, row in enumerate(table):
        company = (row.get("Company") or "").strip()
        if not company:
            continue
        best = _best_logo_for(company, pool_filenames)
        if best:
            st.session_state[f"logo_pick_{i}"] = best
            matched += 1
        else:
            not_matched.append(company)
    msg = f"Auto-matched {matched} logo(s)."
    if not_matched:
        msg += f" Unmatched: {', '.join(not_matched)}"
    st.toast(msg)
    st.rerun()
auto_col2.caption(
    "Fuzzy match — pilla casos como `HILTI` ↔ `hilti-corporate.png`, "
    "`Linklaters` ↔ `LL-logo.png`, etc. Igual puedes corregir manualmente."
)

# Load saved logo selections so they persist across reruns
saved_logos_by_company = {p.get("Company", ""): p.get("Logo file", NO_LOGO)
                          for p in default_partners}

partners_clean = []
for i, row in enumerate(table):
    company = (row.get("Company") or "").strip()
    if not company:
        continue
    role = (row.get("Role") or "").strip()

    # Default index for the logo dropdown:
    #   priority: existing session_state pick → saved logo for this company → NO_LOGO
    sess_key = f"logo_pick_{i}"
    saved_for_co = saved_logos_by_company.get(company, NO_LOGO)

    if sess_key in st.session_state:
        current_value = st.session_state[sess_key]
        if current_value not in pool_options:
            current_value = NO_LOGO
            st.session_state[sess_key] = NO_LOGO
    else:
        current_value = saved_for_co if saved_for_co in pool_options else NO_LOGO
        st.session_state[sess_key] = current_value

    cc1, cc2, cc3, cc4 = st.columns([2.5, 2.5, 2.2, 1])
    cc1.markdown(f"**{company}**")
    cc2.markdown(f"`{role_to_banner_text(role)}`" if role
                 else "`SPONSOR` *(default — empty role)*")
    cc3.selectbox(
        f"Logo for row {i}", pool_options,
        key=sess_key,
        label_visibility="collapsed",
    )
    selected_logo = st.session_state[sess_key]
    if selected_logo and selected_logo != NO_LOGO and selected_logo in logo_pool:
        cc4.image(logo_pool[selected_logo], width=80)
    else:
        cc4.markdown("⚠️ *no logo*")

    partners_clean.append({
        "Company":   company,
        "Role":      role,
        "Logo file": selected_logo,
    })

# Sort by inferred rank for the logo-wall / ingo tiers
partners_clean_sorted = sorted(
    partners_clean,
    key=lambda p: (role_rank_key(p["Role"]), p["Company"].lower()),
)


# ── Save event (shared) ──────────────────────────────────────────────────────
st.divider()
sv1, sv2, sv3 = st.columns([1.4, 1, 3])
ev_id_for_save = active_event_id or _slugify(event_name) or "event"

save_btn = sv1.button("💾 Save event", type="primary",
                      use_container_width=True, disabled=not event_name)
if sv2.button("🔄 Refresh", use_container_width=True):
    st.rerun()
sv3.caption("Saves name, dates, sponsors and logos. Generated images are "
            "downloaded/saved in each section below.")

if save_btn:
    _eid_s = active_event_id or 'new'
    # Preserve previously-saved Ingo stats if the Info section wasn't opened this
    # session (its widget keys won't exist yet — fall back to the saved values).
    _ingo_default = (loaded_event or {}).get("ingo_stats") or [
        {"num": "", "label": "ATTENDEES"},
        {"num": "", "label": "SPEAKERS"},
        {"num": "", "label": "NETWORKING HOURS"},
    ]
    _saved_ingo_stats = []
    for i in range(3):
        kn = f"_ingo_num_{i}_{_eid_s}"
        kl = f"_ingo_lab_{i}_{_eid_s}"
        if kn in st.session_state or kl in st.session_state:
            _fallback_lab = _ingo_default[i]["label"] if i < len(_ingo_default) else ""
            _saved_ingo_stats.append({
                "num":   st.session_state.get(kn, ""),
                "label": st.session_state.get(kl, _fallback_lab),
            })
        else:
            _saved_ingo_stats.append(_ingo_default[i] if i < len(_ingo_default)
                                     else {"num": "", "label": ""})

    event_payload = {
        "name":           event_name,
        "theme_key":      theme_key,
        "language":       language,
        "start_date":     start_date.isoformat(),
        "end_date":       end_date.isoformat(),
        "location":       location,
        "bg_lib_choice":  st.session_state.get("ev_bg_choice", "(none)"),
        "ingo_stats":     _saved_ingo_stats,
    }
    _save_event(ev_id_for_save, event_payload, partners_clean, logo_pool,
                bg_image=bg_image)
    st.success(f"Saved event **{event_name}** (id: `{ev_id_for_save}`).")
    st.rerun()


# Shared event payload for all generators below
event_payload = {
    "name":       event_name,
    "theme_key":  theme_key,
    "language":   language,
    "start_date": start_date.isoformat(),
    "end_date":   end_date.isoformat(),
    "location":   location,
}
_eid_i = active_event_id or "new"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 · GENERATE  (only the output you picked in step 1 renders below)
# ══════════════════════════════════════════════════════════════════════════════
st.divider()
st.header(f"4 · Generate · {mode}")


# ──────────────────────────────────────────────────────────────────────────────
# MODE: Marketing partners
# ──────────────────────────────────────────────────────────────────────────────
if mode == MODE_PARTNER:
    st.subheader("🎨 Marketing partners — banner pack")

    generate_btn = st.button(
        "🎨 Generate marketing pack", type="primary",
        use_container_width=True,
        disabled=not partners_clean or not event_name,
    )
    if not partners_clean:
        st.info("Add at least one sponsor/partner above (step 2).")

    if generate_btn:
        all_outputs: dict[str, bytes] = {}
        with st.spinner(f"Generating banners for {len(partners_clean)} partners…"):
            for p in partners_clean_sorted:
                new_pack = _generate_for_partner(p, event_payload, bg_image, logo_pool)
                slug = _slugify(p["Company"])
                for fname2, fbytes in new_pack.items():
                    all_outputs[f"{slug}/{fname2}"] = fbytes
        st.session_state["_last_event_pack"] = all_outputs
        st.session_state["_last_event_name"] = event_name
        st.success(
            f"Generated {len(all_outputs)} banners for {len(partners_clean)} partners."
        )

    # ── Preview & download ────────────────────────────────────────────────────
    pack = st.session_state.get("_last_event_pack")
    if pack:
        st.divider()
        st.subheader(f"Preview — {len(pack)} banners")

        by_company: dict[str, dict[str, bytes]] = {}
        for key, b in pack.items():
            company, fname = key.split("/", 1)
            by_company.setdefault(company, {})[fname] = b

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path, data in pack.items():
                zf.writestr(path, data)
        pack_label = _slugify(st.session_state.get("_last_event_name") or "event")
        st.download_button(
            f"📦 Download all {len(pack)} banners (ZIP)",
            data=zip_buf.getvalue(),
            file_name=f"{pack_label}_marketing_pack.zip",
            mime="application/zip",
            use_container_width=True,
        )

        for company, files in by_company.items():
            with st.expander(f"**{company}** — {len(files)} banners", expanded=True):
                # Per-partner ZIP — handy when you only need to send out THAT
                # sponsor's pack, not the full event archive.
                partner_zip_buf = io.BytesIO()
                with zipfile.ZipFile(partner_zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for fname, fbytes in files.items():
                        zf.writestr(fname, fbytes)
                st.download_button(
                    f"📦 Download {company}'s {len(files)} banners (ZIP)",
                    data=partner_zip_buf.getvalue(),
                    file_name=f"{pack_label}_{_slugify(company)}_marketing_pack.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key=f"zip_{company}",
                )

                cols = st.columns(min(4, len(files)))
                for i, (fname, fbytes) in enumerate(files.items()):
                    col = cols[i % len(cols)]
                    col.image(fbytes, use_container_width=True, caption=fname)
                    col.download_button(
                        "Download", data=fbytes,
                        file_name=f"{_slugify(company)}_{fname}",
                        mime="image/png", use_container_width=True,
                        key=f"dl_{company}_{fname}",
                    )


# ──────────────────────────────────────────────────────────────────────────────
# MODE: Ingo (1200×630)
# ──────────────────────────────────────────────────────────────────────────────
elif mode == MODE_INGO:
    st.subheader("📸 Event Ingo — 1 200 × 630 px")
    st.caption(
        "Event infographic on a white background with an empty circle for the user's photo. "
        "Generates 8 formats: 4 ES + 4 EN (Event · Speaker · Attendee · Sponsor)."
    )

    from generators.t_ingo import (generate_all_variants as _gen_all_ingos,
                                    ALL_VARIANTS as _INGO_VARIANTS)

    _VARIANT_CAPTIONS = {
        "":          "Event",
        "ponente":   "Ponente / Speaker",
        "asistente": "Asistente / Attendee",
        "patro":     "Sponsor Oficial",
    }

    # Defaults from saved event (or blank if new)
    _saved_ingo = (loaded_event or {}).get("ingo_stats", [
        {"num": "", "label": "ATTENDEES"},
        {"num": "", "label": "SPEAKERS"},
        {"num": "", "label": "NETWORKING HOURS"},
    ])

    st.markdown("**Event stats** — shown as icons + numbers in the Ingo:")
    is1, is2, is3 = st.columns(3)

    with is1:
        st.caption("👥 Attendees")
        ingo_num_0 = st.text_input(
            "Attendees number", key=f"_ingo_num_0_{_eid_i}",
            value=_saved_ingo[0].get("num", "") if _saved_ingo else "",
            placeholder="e.g. 300+", label_visibility="collapsed",
        )
        ingo_lab_0 = st.text_input(
            "Attendees label", key=f"_ingo_lab_0_{_eid_i}",
            value=_saved_ingo[0].get("label", "ATTENDEES") if _saved_ingo else "ATTENDEES",
            label_visibility="collapsed",
        )

    with is2:
        st.caption("🎤 Speakers")
        ingo_num_1 = st.text_input(
            "Speakers number", key=f"_ingo_num_1_{_eid_i}",
            value=_saved_ingo[1].get("num", "") if len(_saved_ingo) > 1 else "",
            placeholder="e.g. 40", label_visibility="collapsed",
        )
        ingo_lab_1 = st.text_input(
            "Speakers label", key=f"_ingo_lab_1_{_eid_i}",
            value=_saved_ingo[1].get("label", "SPEAKERS") if len(_saved_ingo) > 1 else "SPEAKERS",
            label_visibility="collapsed",
        )

    with is3:
        st.caption("🤝 Networking")
        ingo_num_2 = st.text_input(
            "Networking number", key=f"_ingo_num_2_{_eid_i}",
            value=_saved_ingo[2].get("num", "") if len(_saved_ingo) > 2 else "",
            placeholder="e.g. 8", label_visibility="collapsed",
        )
        ingo_lab_2 = st.text_input(
            "Networking label", key=f"_ingo_lab_2_{_eid_i}",
            value=_saved_ingo[2].get("label", "NETWORKING HOURS") if len(_saved_ingo) > 2 else "NETWORKING HOURS",
            label_visibility="collapsed",
        )

    ingo_stats_current = [
        {"num": ingo_num_0, "label": ingo_lab_0},
        {"num": ingo_num_1, "label": ingo_lab_1},
        {"num": ingo_num_2, "label": ingo_lab_2},
    ]

    ig1, ig2 = st.columns([1, 3])
    gen_ingo_btn = ig1.button(
        "📸 Generate all Ingos", type="primary",
        use_container_width=True,
        disabled=not event_name,
    )
    ig2.caption(
        "Generates all 8 formats at once — 4 in Spanish + 4 in English "
        "(Event · Speaker · Attendee · Sponsor). "
        "The circle is left empty so each person can add their own photo."
    )

    if gen_ingo_btn:
        _tiers, _secondary = _build_ingo_tiers(partners_clean_sorted, logo_pool)
        _renmad_logo = _renmad_logo_img()

        _date_str_es = _format_event_date(
            start_date.isoformat(), end_date.isoformat(), "es").upper()
        _date_str_en = _format_event_date(
            start_date.isoformat(), end_date.isoformat(), "en").upper()

        _event_es = {"title": event_name, "date_str": _date_str_es,
                     "location": location.upper() if location else ""}
        _event_en = {"title": event_name, "date_str": _date_str_en,
                     "location": location.upper() if location else ""}

        _theme = THEMES[theme_key]

        with st.spinner("Generating 8 Ingos (ES + EN)…"):
            try:
                _ingos_es = _gen_all_ingos(
                    event=_event_es, stats=ingo_stats_current, tiers=_tiers,
                    secondary=_secondary, theme=_theme, language="es",
                    renmad_logo=_renmad_logo,
                )
                _ingos_en = _gen_all_ingos(
                    event=_event_en, stats=ingo_stats_current, tiers=_tiers,
                    secondary=_secondary, theme=_theme, language="en",
                    renmad_logo=_renmad_logo,
                )
                st.session_state["_last_ingos_es"]  = _ingos_es
                st.session_state["_last_ingos_en"]  = _ingos_en
                st.session_state["_last_ingo_name"] = _slugify(event_name)
            except Exception as _ingo_err:
                st.error(f"Ingo generation failed: {_ingo_err}")
                import traceback
                st.code(traceback.format_exc())

    # ── Preview & download ────────────────────────────────────────────────────
    _ingos_es = st.session_state.get("_last_ingos_es")
    _ingos_en = st.session_state.get("_last_ingos_en")

    if _ingos_es or _ingos_en:
        st.divider()
        _ingo_slug = st.session_state.get("_last_ingo_name", "event")

        _zia, _zib = st.columns(2)

        _ingo_zip_buf = io.BytesIO()
        with zipfile.ZipFile(_ingo_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _v, _b in (_ingos_es or {}).items():
                _suffix = f"_{_v}" if _v else ""
                _zf.writestr(f"{_ingo_slug}_ingo{_suffix}_es.png", _b)
            for _v, _b in (_ingos_en or {}).items():
                _suffix = f"_{_v}" if _v else ""
                _zf.writestr(f"{_ingo_slug}_ingo{_suffix}_en.png", _b)
        _zia.download_button(
            "📦 Download all 8 (ZIP)",
            data=_ingo_zip_buf.getvalue(),
            file_name=f"{_ingo_slug}_ingos.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_ingo_zip",
        )

        _save_ingo_btn = _zib.button(
            "💾 Save to event folder",
            use_container_width=True,
            disabled=not active_event_id,
            key="save_ingos_btn",
            help="Saves all 8 PNGs to event_data/{event_id}/ingos/",
        )
        if _save_ingo_btn and active_event_id:
            _ingo_dir = os.path.join(_event_dir(active_event_id), "ingos")
            os.makedirs(_ingo_dir, exist_ok=True)
            _saved_count = 0
            for _v, _b in (_ingos_es or {}).items():
                _suffix = f"_{_v}" if _v else ""
                with open(os.path.join(_ingo_dir, f"ingo{_suffix}_es.png"), "wb") as _fh:
                    _fh.write(_b)
                _saved_count += 1
            for _v, _b in (_ingos_en or {}).items():
                _suffix = f"_{_v}" if _v else ""
                with open(os.path.join(_ingo_dir, f"ingo{_suffix}_en.png"), "wb") as _fh:
                    _fh.write(_b)
                _saved_count += 1
            st.success(f"💾 Saved {_saved_count} Ingos to `{_ingo_dir}`")

        if _ingos_es:
            st.markdown("**🇪🇸 Spanish**")
            _es_cols = st.columns(4)
            for _col, _v in zip(_es_cols, _INGO_VARIANTS):
                if _v not in _ingos_es:
                    continue
                _suffix = f"_{_v}" if _v else ""
                _col.image(_ingos_es[_v], use_container_width=True,
                           caption=_VARIANT_CAPTIONS.get(_v, _v))
                _col.download_button(
                    "⬇️ ES",
                    data=_ingos_es[_v],
                    file_name=f"{_ingo_slug}_ingo{_suffix}_es.png",
                    mime="image/png",
                    use_container_width=True,
                    key=f"dl_ingo_es_{_v or 'event'}",
                )

        if _ingos_en:
            st.markdown("**🇬🇧 English**")
            _en_cols = st.columns(4)
            for _col, _v in zip(_en_cols, _INGO_VARIANTS):
                if _v not in _ingos_en:
                    continue
                _suffix = f"_{_v}" if _v else ""
                _col.image(_ingos_en[_v], use_container_width=True,
                           caption=_VARIANT_CAPTIONS.get(_v, _v))
                _col.download_button(
                    "⬇️ EN",
                    data=_ingos_en[_v],
                    file_name=f"{_ingo_slug}_ingo{_suffix}_en.png",
                    mime="image/png",
                    use_container_width=True,
                    key=f"dl_ingo_en_{_v or 'event'}",
                )


# ──────────────────────────────────────────────────────────────────────────────
# MODE: Logo wall (1920px wide)
# ──────────────────────────────────────────────────────────────────────────────
elif mode == MODE_WALL:
    st.subheader("🖼️ Logo Wall — 1 920 px wide")

    from generators.t_logowall import generate_all_variants as _gen_logowall

    _lw_spk_files = st.file_uploader(
        "Speaker / attendee logos (optional — shown in 'Confirmed Speakers' section)",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg"],
        key=f"lw_spk_upload_{_eid_i}",
        label_visibility="visible",
    )

    _lw_speaker_imgs = []
    if _lw_spk_files:
        for _sf in _lw_spk_files:
            try:
                _lw_speaker_imgs.append(Image.open(io.BytesIO(_sf.getvalue())).convert("RGBA"))
            except Exception:
                st.warning(f"Could not open {_sf.name} — skipped.")
    _lw_speakers = [{"name": "speakers", "logos": _lw_speaker_imgs}] if _lw_speaker_imgs else []
    if _lw_speaker_imgs:
        st.caption(f"{len(_lw_speaker_imgs)} speaker logo(s) loaded")

    lw1, lw2 = st.columns([1, 3])
    _gen_lw_btn = lw1.button(
        "🖼️ Generate Logo Wall", type="primary",
        use_container_width=True,
        disabled=not event_name,
    )
    lw2.caption("Generates the logo wall ES + EN at 1,920 px — event sponsors ordered by tier.")

    if _gen_lw_btn:
        _lw_tiers, _lw_secondary = _build_ingo_tiers(partners_clean_sorted, logo_pool)
        _renmad_lw = _renmad_logo_img()
        _lw_theme = THEMES[theme_key]
        _lw_event = {"title": event_name, "date_str": "", "location": location or ""}

        with st.spinner("Generating logo wall…"):
            try:
                _lw_result = _gen_logowall(
                    event=_lw_event,
                    tiers=_lw_tiers,
                    secondary=_lw_secondary,
                    speakers=_lw_speakers,
                    theme=_lw_theme,
                    language=language,
                    renmad_logo=_renmad_lw,
                )
                st.session_state["_last_logowall"]      = _lw_result
                st.session_state["_last_logowall_name"] = _slugify(event_name)
            except Exception as _lw_err:
                st.error(f"Logo wall generation failed: {_lw_err}")
                import traceback
                st.code(traceback.format_exc())

    # ── Preview & download ────────────────────────────────────────────────────
    # _lw_result shape: {"es": {"png":.., "pdf":.., "pptx":..}, "en": {...}}
    _lw_result = st.session_state.get("_last_logowall")
    if _lw_result:
        _lw_slug = st.session_state.get("_last_logowall_name", "event")
        st.divider()
        st.caption("Each language downloads as **PNG** (image), **PDF** (print) "
                   "and **PPTX** (editable PowerPoint — each logo is a movable image).")

        _LW_FMTS = [
            ("png",  "🖼️ PNG",  "image/png"),
            ("pdf",  "📄 PDF",   "application/pdf"),
            ("pptx", "📊 PPTX",  "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ]

        def _lw_lang_block(_lang, _flag):
            _pack = _lw_result.get(_lang)
            if not _pack:
                return
            st.markdown(f"**{_flag}**")
            if _pack.get("png"):
                st.image(_pack["png"], use_container_width=True)
            _dl_cols = st.columns(3)
            for _dc, (_fmt, _flabel, _mime) in zip(_dl_cols, _LW_FMTS):
                _bytes = _pack.get(_fmt)
                _dc.download_button(
                    _flabel,
                    data=_bytes if _bytes else b"",
                    file_name=f"{_lw_slug}_logowall_{_lang}.{_fmt}",
                    mime=_mime,
                    use_container_width=True,
                    disabled=not _bytes,
                    key=f"dl_lw_{_lang}_{_fmt}",
                )

        _lw_col_es, _lw_col_en = st.columns(2)
        with _lw_col_es:
            _lw_lang_block("es", "🇪🇸 Spanish")
        with _lw_col_en:
            _lw_lang_block("en", "🇬🇧 English")

        # ZIP — every format, both languages
        _lw_zip = io.BytesIO()
        with zipfile.ZipFile(_lw_zip, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _lang, _pack in _lw_result.items():
                for _fmt, _, _ in _LW_FMTS:
                    if _pack.get(_fmt):
                        _zf.writestr(f"{_lw_slug}_logowall_{_lang}.{_fmt}", _pack[_fmt])
        st.download_button(
            "📦 Download everything (ZIP — PNG + PDF + PPTX, ES + EN)",
            data=_lw_zip.getvalue(),
            file_name=f"{_lw_slug}_logowall.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_lw_zip",
        )

        _lw_save_btn = st.button(
            "💾 Save Logo Wall to event folder",
            disabled=not active_event_id,
            key="save_lw_btn",
            help=f"Saves PNG + PDF + PPTX to event_data/{active_event_id}/logowall/",
        )
        if _lw_save_btn and active_event_id:
            _lw_dir = os.path.join(_event_dir(active_event_id), "logowall")
            os.makedirs(_lw_dir, exist_ok=True)
            _lw_saved = 0
            for _lang, _pack in _lw_result.items():
                for _fmt, _, _ in _LW_FMTS:
                    if _pack.get(_fmt):
                        with open(os.path.join(_lw_dir, f"logowall_{_lang}.{_fmt}"), "wb") as _fh:
                            _fh.write(_pack[_fmt])
                        _lw_saved += 1
            st.success(f"💾 Saved {_lw_saved} file(s) to `{_lw_dir}`")
