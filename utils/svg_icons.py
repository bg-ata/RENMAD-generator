# -*- coding: utf-8 -*-
"""
Icons for the title-slide break / utility slides.

These are the REAL Tabler icons (MIT-licensed, https://tabler.io/icons) — the exact
glyphs shown in the picker previews — embedded as path data and rasterised crisply
via PyMuPDF. No hand-drawn approximations: what the preview shows is what the deck
renders. Tabler outline style: 24×24 viewBox, stroke-width 2, round caps/joins.
"""
import io

from PIL import Image

# Inner path data copied verbatim from the Tabler outline SVGs (background rect
# dropped). `coffee` composes the real `mug` + `cookie` (cookie scaled and seated
# on the rim) per the approved design.
_MUG = (
    '<path d="M4.083 5h10.834a1.08 1.08 0 0 1 1.083 1.077v8.615c0 2.38 -1.94 4.308 '
    '-4.333 4.308h-4.334c-2.393 0 -4.333 -1.929 -4.333 -4.308v-8.615a1.08 1.08 0 0 1 '
    '1.083 -1.077"/>'
    '<path d="M16 8h2.5c1.38 0 2.5 1.045 2.5 2.333v2.334c0 1.288 -1.12 2.333 -2.5 '
    '2.333h-2.5"/>'
)
_COOKIE = (
    '<path d="M8 13v.01"/><path d="M12 17v.01"/><path d="M12 12v.01"/>'
    '<path d="M16 14v.01"/><path d="M11 8v.01"/>'
    '<path d="M13.148 3.476l2.667 1.104a4 4 0 0 0 4.656 6.14l.053 .132a3 3 0 0 1 0 '
    '2.296q -.745 1.18 -1.024 1.852q -.283 .684 -.66 2.216a3 3 0 0 1 -1.624 1.623q '
    '-1.572 .394 -2.216 .661q -.712 .295 -1.852 1.024a3 3 0 0 1 -2.296 0q -1.203 -.754 '
    '-1.852 -1.024q -.707 -.292 -2.216 -.66a3 3 0 0 1 -1.623 -1.624q -.397 -1.577 -.661 '
    '-2.216q -.298 -.718 -1.024 -1.852a3 3 0 0 1 0 -2.296q .719 -1.116 1.024 -1.852q '
    '.257 -.62 .66 -2.216a3 3 0 0 1 1.624 -1.623q 1.547 -.384 2.216 -.661q .687 -.285 '
    '1.852 -1.024a3 3 0 0 1 2.296 0"/>'
)

_ICONS = {
    # mug with a real cookie resting on the rim (Tabler mug + cookie)
    "coffee": _MUG + f'<g transform="translate(3.7,-4.3) scale(0.48)" stroke-width="4.0">{_COOKIE}</g>',
    # fork + knife (Tabler tools-kitchen-2)
    "meal": ('<path d="M19 3v12h-5c-.023 -3.681 .184 -7.406 5 -12zm0 12v6h-1v-3m-10 -14v17'
             'm-3 -17v3a3 3 0 1 0 6 0v-3"/>'),
    # cocktail / drinks glass (Tabler glass-full)
    "cocktail": ('<path d="M8 21l8 0"/><path d="M12 15l0 6"/>'
                 '<path d="M17 3l1 7c0 3.012 -2.686 5 -6 5s-6 -1.988 -6 -5l1 -7h10z"/>'
                 '<path d="M6 10a5 5 0 0 1 6 0a5 5 0 0 0 6 0"/>'),
    # person with a tick — registration / check-in (Tabler user-check)
    "checkin": ('<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0"/>'
                '<path d="M6 21v-2a4 4 0 0 1 4 -4h4"/><path d="M15 19l2 2l4 -4"/>'),
    # muted speaker — mute your phone (Tabler volume-off)
    "volume_off": ('<path d="M15 8a5 5 0 0 1 1.912 4.934m-1.377 2.602a5 5 0 0 1 -.535 .464"/>'
                   '<path d="M17.7 5a9 9 0 0 1 2.362 11.086m-1.676 2.299a9 9 0 0 1 -.686 .615"/>'
                   '<path d="M9.069 5.054l.431 -.554a.8 .8 0 0 1 1.5 .5v2m0 4v8a.8 .8 0 0 1 '
                   '-1.5 .5l-3.5 -4.5h-2a1 1 0 0 1 -1 -1v-4a1 1 0 0 1 1 -1h2l1.294 -1.664"/>'
                   '<path d="M3 3l18 18"/>'),
    # clock — welcome / closing (Tabler clock)
    "clock": ('<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/><path d="M12 7v5l3 3"/>'),
    # two people — networking (Tabler users)
    "people": ('<path d="M9 7m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/>'
               '<path d="M3 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2"/>'
               '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
               '<path d="M21 21v-2a4 4 0 0 0 -3 -3.85"/>'),
    # wifi (Tabler wifi)
    "wifi": ('<path d="M12 18l.01 0"/><path d="M9.172 15.172a4 4 0 0 1 5.656 0"/>'
             '<path d="M6.343 12.343a8 8 0 0 1 11.314 0"/>'
             '<path d="M3.515 9.515c4.686 -4.687 12.284 -4.687 17 0"/>'),
    # QR code (Tabler qrcode)
    "qr": ('<path d="M4 4m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 '
           '-1 -1z"/><path d="M7 17l0 .01"/>'
           '<path d="M14 4m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 '
           '-1 -1z"/><path d="M7 7l0 .01"/>'
           '<path d="M4 14m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 '
           '-1 -1z"/><path d="M17 7l0 .01"/><path d="M14 14l3 0"/><path d="M20 14l0 .01"/>'
           '<path d="M14 14l0 3"/><path d="M14 20l3 0"/><path d="M17 17l3 0"/>'
           '<path d="M20 17l0 3"/>'),
}


def available() -> set:
    return set(_ICONS)


def render(name: str, px: int = 480, color: tuple = (255, 255, 255),
           stroke: float = 2.0) -> "Image.Image | None":
    """Rasterise a Tabler icon to a crisp RGBA PIL image at `px`×`px`."""
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
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
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
