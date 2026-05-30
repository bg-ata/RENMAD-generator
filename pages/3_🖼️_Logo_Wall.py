# -*- coding: utf-8 -*-
"""
🖼️ Logo Wall — Event sponsor + speaker logo wall, 1920 px wide.
"""
import io
import json
import os
import unicodedata
import re
import zipfile

import streamlit as st
from PIL import Image

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THEMES
from generators.t_logowall import generate_all_variants


# ── Paths ─────────────────────────────────────────────────────────────────────
_HERE    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(_HERE, "..", "event_data"))
os.makedirs(DATA_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_").lower()
    return t or "x"


def _event_dir(eid: str) -> str:
    return os.path.join(DATA_DIR, eid)


def _load_event_logos(eid: str) -> dict:
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


TIER_ORDER = ["diamond", "platinum", "global", "gold", "silver", "bronze", "standard", "sponsor"]
TIER_SET   = set(TIER_ORDER)


def role_to_banner_text(role: str) -> str:
    role = (role or "").strip()
    if not role:
        return "SPONSOR"
    lower = role.lower()
    if lower in TIER_SET:
        if lower in ("standard", "sponsor"):
            return "SPONSOR"
        return f"{role.upper()} SPONSOR"
    return role.upper()


def role_rank_key(role: str) -> tuple:
    role = (role or "").strip().lower()
    if role in TIER_SET:
        return (0, f"{TIER_ORDER.index(role):02d}")
    if "partner" in role:
        return (1, role)
    return (2, role)


def _build_logo_wall_groups(partners, pool_bytes):
    tier_map, sec_map = {}, {}
    for p in partners:
        role  = (p.get("Role") or "").strip()
        fname = p.get("Logo file", "")
        logo_img = None
        if fname and fname in pool_bytes:
            try:
                logo_img = Image.open(io.BytesIO(pool_bytes[fname])).convert("RGBA")
            except Exception:
                pass
        gidx, _ = role_rank_key(role)
        display  = role_to_banner_text(role)
        if gidx == 0:
            tier_map.setdefault(display, [])
            if logo_img:
                tier_map[display].append(logo_img)
        else:
            sec_map.setdefault(display, [])
            if logo_img:
                sec_map[display].append(logo_img)

    def _tier_sort(name):
        lower = name.lower()
        for i, t in enumerate(TIER_ORDER):
            if t in lower:
                return i
        return 99

    tiers     = [{"name": n, "logos": l}
                 for n, l in sorted(tier_map.items(), key=lambda x: _tier_sort(x[0]))]
    secondary = [{"name": n, "logos": l} for n, l in sec_map.items()]
    return tiers, secondary


# ── Page chrome ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Logo Wall", page_icon="🖼️")
st.title("🖼️ Logo Wall")
st.caption("Event sponsor + speaker logo wall — 1920 px wide")


# ── Step 1: Pick event ────────────────────────────────────────────────────────
st.subheader("1. Pick event")

saved_events = []
if os.path.isdir(DATA_DIR):
    for eid in os.listdir(DATA_DIR):
        ej = os.path.join(DATA_DIR, eid, "event.json")
        if os.path.exists(ej):
            try:
                with open(ej, encoding="utf-8") as f:
                    meta = json.load(f)
                saved_events.append({"id": eid, "name": meta.get("name", eid), "_meta": meta})
            except Exception:
                pass
saved_events.sort(key=lambda x: x["name"])

if not saved_events:
    st.info("No saved events found. Create one on the Event page first.")
    st.stop()

event_options = [e["name"] for e in saved_events]
selected_name = st.selectbox("Event", event_options)
selected_entry = next(e for e in saved_events if e["name"] == selected_name)
active_event_id = selected_entry["id"]
event_meta      = selected_entry["_meta"]

theme_key = event_meta.get("theme_key", "datacenters")
theme     = THEMES.get(theme_key, list(THEMES.values())[0])
language  = event_meta.get("language", "es")
partners  = event_meta.get("partners", [])


# ── Step 2: Sponsors (auto-loaded) ────────────────────────────────────────────
st.subheader("2. Sponsors")

pool_bytes = _load_event_logos(active_event_id)

tiers, secondary = _build_logo_wall_groups(partners, pool_bytes)

n_sponsors  = sum(len(g["logos"]) for g in tiers)
n_secondary = sum(len(g["logos"]) for g in secondary)
tier_names  = ", ".join(g["name"] for g in tiers) if tiers else "—"
sec_names   = ", ".join(g["name"] for g in secondary) if secondary else "—"

st.caption(
    f"{n_sponsors} sponsors loaded ({tier_names}) · "
    f"{n_secondary} secondary ({sec_names})"
)


# ── Step 3: Speaker logos ──────────────────────────────────────────────────────
st.subheader("3. Speaker logos")
st.caption(
    "Upload speaker / attendee company logos. "
    "These go in the 'Confirmed Speakers' section below the sponsor strip."
)

spk_files = st.file_uploader(
    "Speaker logos", accept_multiple_files=True,
    type=["png", "jpg", "jpeg", "svg"],
    label_visibility="collapsed",
)

speaker_imgs = []
if spk_files:
    for f in spk_files:
        try:
            img = Image.open(io.BytesIO(f.getvalue())).convert("RGBA")
            speaker_imgs.append(img)
        except Exception:
            st.warning(f"Could not open {f.name} — skipped.")

speakers = [{"name": "speakers", "logos": speaker_imgs}] if speaker_imgs else []

if speaker_imgs:
    st.caption(f"{len(speaker_imgs)} speaker logo(s) loaded")


# ── Step 4: Generate ──────────────────────────────────────────────────────────
st.divider()
gen_btn = st.button("🖼️ Generate Logo Wall", type="primary", disabled=not active_event_id)

if gen_btn:
    _logo_dir    = os.path.normpath(os.path.join(_HERE, "..", "assets", "logos"))
    renmad_logo  = None
    for _rname in ("logo_renmad_events.png", "renmad_logo.png", "logo_renmad.png"):
        _rpath = os.path.join(_logo_dir, _rname)
        if os.path.exists(_rpath):
            try:
                renmad_logo = Image.open(_rpath).convert("RGBA")
            except Exception:
                pass
            break

    event_payload = {
        "title":    event_meta.get("name", ""),
        "date_str": "",
        "location": event_meta.get("location", ""),
    }

    with st.spinner("Generating logo wall…"):
        try:
            result = generate_all_variants(
                event=event_payload,
                tiers=tiers,
                secondary=secondary,
                speakers=speakers,
                theme=theme,
                language=language,
                renmad_logo=renmad_logo,
            )
            st.session_state["_last_logowall"]      = result
            st.session_state["_last_logowall_name"] = _slugify(event_meta.get("name", "event"))
        except Exception as err:
            st.error(f"Generation failed: {err}")
            import traceback
            st.code(traceback.format_exc())


# ── Step 5: Preview & download ────────────────────────────────────────────────
result = st.session_state.get("_last_logowall")
if result:
    slug = st.session_state.get("_last_logowall_name", "event")
    st.divider()
    st.subheader("Preview")

    col_es, col_en = st.columns(2)

    with col_es:
        st.markdown("**🇪🇸 Español**")
        if "es" in result:
            st.image(result["es"], use_container_width=True)
            st.download_button(
                "⬇️ Download ES",
                data=result["es"],
                file_name=f"{slug}_logowall_es.png",
                mime="image/png",
                use_container_width=True,
                key="dl_logowall_es",
            )

    with col_en:
        st.markdown("**🇬🇧 English**")
        if "en" in result:
            st.image(result["en"], use_container_width=True)
            st.download_button(
                "⬇️ Download EN",
                data=result["en"],
                file_name=f"{slug}_logowall_en.png",
                mime="image/png",
                use_container_width=True,
                key="dl_logowall_en",
            )

    # ZIP download
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for lang, data in result.items():
            zf.writestr(f"{slug}_logowall_{lang}.png", data)
    st.download_button(
        "📦 Download both (ZIP)",
        data=zip_buf.getvalue(),
        file_name=f"{slug}_logowall.zip",
        mime="application/zip",
        use_container_width=True,
        key="dl_logowall_zip",
    )

    # Save to event folder
    save_btn = st.button(
        "💾 Save to event folder",
        disabled=not active_event_id,
        key="save_logowall_btn",
        help=f"Saves PNGs to event_data/{active_event_id}/logowall/",
    )
    if save_btn and active_event_id:
        out_dir = os.path.join(_event_dir(active_event_id), "logowall")
        os.makedirs(out_dir, exist_ok=True)
        for lang, data in result.items():
            with open(os.path.join(out_dir, f"logowall_{lang}.png"), "wb") as fh:
                fh.write(data)
        st.success(f"Saved to `{out_dir}`")
