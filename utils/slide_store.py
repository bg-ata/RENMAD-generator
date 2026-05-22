"""Slide history store — persists the last MAX_SLIDES generated slides to disk.

Each slide is stored in  saved_slides/{slide_id}/
    meta.json       — all metadata + form state (no images)
    thumbnail.png   — 384 × 216 preview
    slide.png       — full-resolution PNG
    slide.pptx      — editable PPTX (if available)
    photos/         — speaker photos keyed by original filename
    logos/          — company logos keyed by original filename
    bg.png          — custom background (only when NOT from the library)
"""
import io, json, os, shutil, uuid
from datetime import datetime
from PIL import Image

_HERE      = os.path.dirname(__file__)
STORE_DIR  = os.path.join(_HERE, "..", "saved_slides")
MAX_SLIDES = 30
THUMB_W    = 384     # pixels


# ── Paths ─────────────────────────────────────────────────────────────────────

def _sdir(sid):  return os.path.join(STORE_DIR, sid)
def _meta(sid):  return os.path.join(_sdir(sid), "meta.json")
def _thumb(sid): return os.path.join(_sdir(sid), "thumbnail.png")
def _png(sid):   return os.path.join(_sdir(sid), "slide.png")
def _pptx(sid):  return os.path.join(_sdir(sid), "slide.pptx")


def _ensure():
    os.makedirs(STORE_DIR, exist_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def list_slides() -> list[dict]:
    """Return slide metadata sorted newest-first (max MAX_SLIDES)."""
    _ensure()
    items = []
    for sid in os.listdir(STORE_DIR):
        mp = _meta(sid)
        if not os.path.exists(mp):
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                m = json.load(f)
            m["id"] = sid
            items.append(m)
        except Exception:
            pass
    items.sort(key=lambda m: m.get("updated_at", m.get("created_at", "")), reverse=True)
    return items[:MAX_SLIDES]


def save_slide(
    label:      str,
    theme_key:  str,
    language:   str,
    template:   str,
    form_state: dict,
    png_bytes:  bytes,
    pptx_bytes: bytes | None      = None,
    photos:     dict | None       = None,   # {filename: PIL.Image}
    logos:      dict  | None      = None,   # {filename: PIL.Image}
    bg_image:   Image.Image | None = None,
    slide_id:   str | None        = None,   # pass to overwrite
) -> str:
    """Save (or overwrite) a slide.  Returns the slide_id."""
    _ensure()
    sid  = slide_id or uuid.uuid4().hex[:8]
    sd   = _sdir(sid)
    os.makedirs(sd, exist_ok=True)

    now = datetime.now().isoformat(timespec="seconds")

    # ── Thumbnail ──
    thumb = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    ratio = THUMB_W / thumb.width
    thumb = thumb.resize((THUMB_W, int(thumb.height * ratio)), Image.LANCZOS)
    thumb.save(_thumb(sid), format="PNG", optimize=True)

    # ── Full files ──
    with open(_png(sid),  "wb") as f: f.write(png_bytes)
    if pptx_bytes:
        with open(_pptx(sid), "wb") as f: f.write(pptx_bytes)
    elif os.path.exists(_pptx(sid)):
        os.remove(_pptx(sid))   # clean stale file if overwriting without PPTX

    # ── Speaker photos ──
    photos_dir = os.path.join(sd, "photos")
    os.makedirs(photos_dir, exist_ok=True)
    # Clear previous photos so renamed/removed speakers don't linger
    for old in os.listdir(photos_dir):
        os.remove(os.path.join(photos_dir, old))
    for fn, img in (photos or {}).items():
        try:
            img.convert("RGBA").save(os.path.join(photos_dir, fn), format="PNG")
        except Exception:
            pass

    # ── Company logos ──
    logos_dir = os.path.join(sd, "logos")
    os.makedirs(logos_dir, exist_ok=True)
    for old in os.listdir(logos_dir):
        os.remove(os.path.join(logos_dir, old))
    for fn, img in (logos or {}).items():
        try:
            img.convert("RGBA").save(os.path.join(logos_dir, fn), format="PNG")
        except Exception:
            pass

    # ── Custom background (skip if from library — library path persists) ──
    bg_path = os.path.join(sd, "bg.png")
    _bg_lib = form_state.get("bg_lib_choice") or ""
    _uses_library = _bg_lib not in ("", "(none)")
    if bg_image is not None and not _uses_library:
        bg_image.convert("RGB").save(bg_path, format="PNG")
    elif os.path.exists(bg_path) and _uses_library:
        os.remove(bg_path)   # library choice replaces custom bg

    # ── Metadata ──
    existing_created = None
    if os.path.exists(_meta(sid)):
        try:
            with open(_meta(sid), encoding="utf-8") as f:
                existing_created = json.load(f).get("created_at")
        except Exception:
            pass

    meta = {
        "label":      label or form_state.get("session_title", "") or "Untitled",
        "created_at": existing_created or now,
        "updated_at": now,
        "theme_key":  theme_key,
        "language":   language,
        "template":   template,
        "form":       form_state,
    }
    with open(_meta(sid), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ── Prune: keep only MAX_SLIDES ──
    all_slides = list_slides()
    for old in all_slides[MAX_SLIDES:]:
        try:
            shutil.rmtree(_sdir(old["id"]))
        except Exception:
            pass

    return sid


def load_slide(sid: str) -> dict:
    """Return full slide data: meta + photos + logos + bg + file bytes."""
    sd = _sdir(sid)
    with open(_meta(sid), encoding="utf-8") as f:
        meta = json.load(f)
    meta["id"] = sid

    photos = {}
    pd = os.path.join(sd, "photos")
    if os.path.isdir(pd):
        for fn in os.listdir(pd):
            try:
                photos[fn] = Image.open(os.path.join(pd, fn)).convert("RGBA")
            except Exception:
                pass

    logos = {}
    ld = os.path.join(sd, "logos")
    if os.path.isdir(ld):
        for fn in os.listdir(ld):
            try:
                logos[fn] = Image.open(os.path.join(ld, fn)).convert("RGBA")
            except Exception:
                pass

    bg = None
    if os.path.exists(os.path.join(sd, "bg.png")):
        bg = Image.open(os.path.join(sd, "bg.png")).convert("RGBA")

    png_bytes  = open(_png(sid),  "rb").read() if os.path.exists(_png(sid))  else None
    pptx_bytes = open(_pptx(sid), "rb").read() if os.path.exists(_pptx(sid)) else None

    return {**meta, "photos": photos, "logos": logos, "bg": bg,
            "png_bytes": png_bytes, "pptx_bytes": pptx_bytes}


def delete_slide(sid: str):
    sd = _sdir(sid)
    if os.path.isdir(sd):
        shutil.rmtree(sd)


def thumb_bytes(sid: str) -> bytes | None:
    p = _thumb(sid)
    return open(p, "rb").read() if os.path.exists(p) else None
