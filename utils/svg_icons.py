# -*- coding: utf-8 -*-
"""
Clean line-art icons for the title-slide break / utility slides.

Hand-drawn PIL primitives looked amateurish and were hard to recognise. These are
proper vector icons (Lucide-style: 24×24 viewBox, consistent stroke, round caps)
rasterised crisply via PyMuPDF — the same SVG engine already used for sponsor
logos, so no new dependency.
"""
import io

from PIL import Image

# Each entry is the inner SVG markup for a 24×24 viewBox. `fill="none"` +
# round-cap strokes by default; filled bits set their own fill.
_ICONS = {
    # smartphone with a mute slash — unmistakably a phone
    "phone": (
        '<rect x="6" y="2" width="12" height="20" rx="2.6"/>'
        '<line x1="10" y1="5.2" x2="14" y2="5.2"/>'
        '<circle cx="12" cy="18.4" r="0.9" fill="{c}" stroke="none"/>'
        '<line x1="4.2" y1="3.4" x2="19.8" y2="20.6"/>'
    ),
    # coffee cup + steam (Lucide coffee)
    "coffee": (
        '<path d="M10 2v2"/><path d="M14 2v2"/><path d="M6 2v2"/>'
        '<path d="M4 8h13a4 4 0 0 1 0 8h-1"/>'
        '<path d="M4 8v9a4 4 0 0 0 4 4h5a4 4 0 0 0 4-4V8z"/>'
    ),
    # fork + knife
    "meal": (
        '<line x1="6" y1="2.5" x2="6" y2="8"/>'
        '<line x1="9" y1="2.5" x2="9" y2="8"/>'
        '<line x1="12" y1="2.5" x2="12" y2="8"/>'
        '<path d="M6 8c0 1.7 1.3 3 3 3s3-1.3 3-3"/>'
        '<line x1="9" y1="11" x2="9" y2="21.5"/>'
        '<path d="M18 2.5c-2 1.5-2 8 0 9.5z" fill="{c}"/>'
        '<line x1="18" y1="12" x2="18" y2="21.5"/>'
    ),
    # martini glass (Lucide martini)
    "cocktail": (
        '<path d="M8 22h8"/><path d="M12 11v11"/><path d="M19 3 12 11 5 3Z"/>'
        '<line x1="14.5" y1="6" x2="18.5" y2="2.5"/>'
        '<circle cx="18.7" cy="2.6" r="1.1" fill="{c}" stroke="none"/>'
    ),
    # event badge on a lanyard (registration)
    "badge": (
        '<path d="M9 5l3-3 3 3"/>'
        '<rect x="5" y="5" width="14" height="16" rx="2.4"/>'
        '<circle cx="12" cy="11" r="2.3"/>'
        '<line x1="8.5" y1="16.5" x2="15.5" y2="16.5"/>'
    ),
    # two people (networking) — Lucide users
    "people": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    # clock (welcome / closing / time)
    "clock": (
        '<circle cx="12" cy="12" r="9.5"/>'
        '<path d="M12 6.5V12l4 2.2"/>'
    ),
    # wifi
    "wifi": (
        '<path d="M2.5 9a15 15 0 0 1 19 0"/>'
        '<path d="M5.5 12.6a10 10 0 0 1 13 0"/>'
        '<path d="M8.5 16.2a5 5 0 0 1 7 0"/>'
        '<circle cx="12" cy="19.4" r="0.9" fill="{c}" stroke="none"/>'
    ),
    # QR-ish glyph (decorative placeholder)
    "qr": (
        '<rect x="3" y="3" width="7" height="7" rx="1"/>'
        '<rect x="6" y="6" width="1.5" height="1.5" fill="{c}" stroke="none"/>'
        '<rect x="14" y="3" width="7" height="7" rx="1"/>'
        '<rect x="17" y="6" width="1.5" height="1.5" fill="{c}" stroke="none"/>'
        '<rect x="3" y="14" width="7" height="7" rx="1"/>'
        '<rect x="6" y="17" width="1.5" height="1.5" fill="{c}" stroke="none"/>'
        '<path d="M14 14h3v3M21 14v3M14 21h3M21 19v2h-2" />'
    ),
}


def available() -> set:
    return set(_ICONS)


def render(name: str, px: int = 480, color: tuple = (255, 255, 255),
           stroke: float = 1.7) -> "Image.Image | None":
    """Rasterise an icon to a crisp RGBA PIL image at `px`×`px`."""
    body = _ICONS.get(name)
    if body is None:
        return None
    try:
        import fitz  # PyMuPDF — already a dependency (sponsor-logo SVGs)
    except Exception:
        return None
    c = "#%02x%02x%02x" % tuple(color[:3])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'{body.replace("{c}", c)}</svg>'
    )
    try:
        doc = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
        pix = doc[0].get_pixmap(alpha=True)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
        doc.close()
        if img.size != (px, px):
            img = img.resize((px, px), Image.LANCZOS)
        return img
    except Exception:
        return None
