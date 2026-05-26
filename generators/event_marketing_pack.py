"""
Event Marketing Pack generator.

Per sponsor / partner entry, produces 4 banner PNGs:
  • EN horizontal (1920×1080)
  • EN square     (1080×1080)
  • {event_lang} horizontal
  • {event_lang} square

Design reference: event_preview/marketing_pack_blank.html (approved by user).

Layout:
  • Theme-colour background covers the top portion (left zone in horizontal)
  • Dotted white pattern overlays the theme-colour area
  • Composite RENMAD theme logo + date/location badge in the top-left
  • Role label (e.g. "DIAMOND SPONSOR") in white, top-right
  • Slanted white pill across mid-area containing the sponsor logo
  • Theme background photo at the bottom, with theme-tinted gradient overlay
  • Localised CTA text at the bottom-centre (white with subtle shadow)
"""
import io
import os
from PIL import Image, ImageDraw, ImageOps

from config import THEMES, LANGUAGE_STRINGS
from utils.fonts import get as get_font


# ── Canvas sizes (final output) ───────────────────────────────────────────────
W_H, H_H = 1920, 1080   # horizontal banner (16:9)
W_S, H_S = 1080, 1080   # square banner (1:1)

# ── Layout proportions ───────────────────────────────────────────────────────
# Horizontal: theme zone is the TOP 62%, bottom 38% is the photo strip
LAYOUT_H = {
    "theme_h_pct":    0.62,
    "dot_zone_w_pct": 0.50,    # dots only in the left half
    "pill_left_pct":  0.54,
    "pill_right_pct": 0.96,
    "pill_top_pct":   0.30,
    "pill_bot_pct":   0.55,
    "logo_w_pct":     0.215,   # RENMAD theme logo width
    "logo_pad":       (40, 36),
    "role_max_w_pct": 0.44,
    "role_top":       50,
    "role_right_pad": 50,
    "role_font":      52,
    "cta_font":       54,
    "cta_bot_pct":    0.09,
    "date_font":      28,
}

# Square: theme zone is top 60%, bottom 40% photo
LAYOUT_S = {
    "theme_h_pct":    0.60,
    "dot_zone_w_pct": 1.00,    # dots cover the whole top
    "pill_left_pct":  0.14,
    "pill_right_pct": 0.95,
    "pill_top_pct":   0.36,
    "pill_bot_pct":   0.54,
    "logo_w_pct":     0.27,
    "logo_pad":       (40, 36),
    "role_max_w_pct": 0.50,
    "role_top":       40,
    "role_right_pad": 40,
    "role_font":      42,
    "cta_font":       46,
    "cta_bot_pct":    0.09,
    "date_font":      24,
}

# ── Dotted pattern ───────────────────────────────────────────────────────────
DOT_GRID   = 18          # spacing in px (scaled up from the 9px HTML preview at 480w)
DOT_RADIUS = 3
DOT_ALPHA  = 85          # ~33% opacity white

# ── Asset roots ──────────────────────────────────────────────────────────────
_HERE         = os.path.dirname(__file__)
ASSETS_LOGOS  = os.path.normpath(os.path.join(_HERE, "..", "assets", "logos"))
ASSETS_BG     = os.path.normpath(os.path.join(_HERE, "..", "assets", "backgrounds"))


# ── Font helpers ─────────────────────────────────────────────────────────────

def _f(style: str, size: int):
    mapping = {"black": "montserrat-black", "bold": "montserrat-bold",
               "semibold": "montserrat-semibold", "reg": "inter"}
    return get_font(mapping.get(style, "inter"), size)


def _strings(lang: str) -> dict:
    return LANGUAGE_STRINGS.get(lang, LANGUAGE_STRINGS["es"])


_FALLBACK_MONTHS_SHORT = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _format_event_date(start_iso: str | None, end_iso: str | None,
                       language: str) -> str:
    """
    Format an event date range, localising the month abbreviation:
      Single day:      '18 NOV 2026'
      Same month:      '18-19 NOV 2026'
      Same year, ≠ M.: '30 OCT - 2 NOV 2026'
      Cross-year:      '30 DEC 2025 - 2 JAN 2026'

    Returns empty string if the dates can't be parsed.
    """
    from datetime import date
    try:
        if not start_iso:
            return ""
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso) if end_iso else start
    except (ValueError, TypeError):
        return ""
    if end < start:
        start, end = end, start
    months = _strings(language).get("months_short", _FALLBACK_MONTHS_SHORT)
    sm = months[start.month - 1]
    em = months[end.month - 1]
    if start == end:
        return f"{start.day} {sm} {start.year}"
    if start.month == end.month and start.year == end.year:
        return f"{start.day}-{end.day} {sm} {start.year}"
    if start.year == end.year:
        return f"{start.day} {sm} - {end.day} {em} {start.year}"
    return f"{start.day} {sm} {start.year} - {end.day} {em} {end.year}"


# ── Generic helpers ──────────────────────────────────────────────────────────

def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list:
    """Greedy word-wrap."""
    words = (text or "").split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textbbox((0, 0), test, font=font)[2] > max_w and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def _fit_role(draw, text, max_w, max_size, min_size=22, max_lines=2):
    """Find the largest size where the role label fits within max_w in ≤ max_lines."""
    for size in range(max_size, min_size - 1, -2):
        f = _f("black", size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
    f = _f("black", min_size)
    return f, _wrap(draw, text, f, max_w), min_size


def _draw_dots(canvas: Image.Image, x0: int, y0: int, x1: int, y1: int,
               exclude: tuple | None = None) -> None:
    """
    Tile small white dots in a grid over the rect.
    `exclude` is an optional (ex0, ey0, ex1, ey1) sub-rect — dots whose centres
    fall inside it are skipped (so we can keep the role label area clean).
    """
    d = ImageDraw.Draw(canvas, "RGBA")
    color = (255, 255, 255, DOT_ALPHA)
    ex0 = ey0 = ex1 = ey1 = None
    if exclude:
        ex0, ey0, ex1, ey1 = exclude
    for y in range(y0, y1, DOT_GRID):
        for x in range(x0, x1, DOT_GRID):
            if exclude and ex0 <= x <= ex1 and ey0 <= y <= ey1:
                continue
            d.ellipse([x - DOT_RADIUS, y - DOT_RADIUS,
                       x + DOT_RADIUS, y + DOT_RADIUS], fill=color)


def _slanted_pill(canvas: Image.Image, x_left: int, x_right: int,
                  y_top: int, y_bot: int, slant_pct: float = 0.07) -> tuple:
    """
    Draw a left-slanted white pill (mimics CSS clip-path:polygon(7% 0, 100% 0, 100% 100%, 0 100%)).
    Returns the inner usable rect for placing content.
    """
    slant = int((x_right - x_left) * slant_pct)
    poly = [
        (x_left + slant, y_top),
        (x_right,        y_top),
        (x_right,        y_bot),
        (x_left,         y_bot),
    ]
    ImageDraw.Draw(canvas, "RGBA").polygon(poly, fill=(255, 255, 255, 255))
    # Inner safe area is slightly inset so logos don't touch edges
    return (x_left + slant + 10, y_top + 10, x_right - 10, y_bot - 10)


def _fit_logo(logo_img: Image.Image, box_w: int, box_h: int, pad: int = 24):
    """Resize logo to fit in (box_w - 2*pad) × (box_h - 2*pad), preserving aspect."""
    if logo_img is None:
        return None
    max_w = max(1, box_w - 2 * pad)
    max_h = max(1, box_h - 2 * pad)
    lw, lh = logo_img.size
    scale = min(max_w / lw, max_h / lh)
    nw, nh = max(1, int(lw * scale)), max(1, int(lh * scale))
    return logo_img.resize((nw, nh), Image.LANCZOS)


def _paste_centered(canvas: Image.Image, img: Image.Image, cx: int, cy: int) -> None:
    if img is None:
        return
    x = cx - img.width // 2
    y = cy - img.height // 2
    mask = img if img.mode == "RGBA" else None
    canvas.paste(img, (x, y), mask=mask)


def _load_theme_logo(theme_key: str) -> Image.Image | None:
    fn = THEMES.get(theme_key, {}).get("logo_filename")
    if not fn:
        return None
    path = os.path.join(ASSETS_LOGOS, fn)
    if os.path.exists(path):
        return Image.open(path).convert("RGBA")
    return None


def _load_default_bg(theme_key: str) -> Image.Image | None:
    bg_folder = THEMES.get(theme_key, {}).get("bg_folder", theme_key)
    if bg_folder == "__all__":
        # ATA Insights — aggregate; just pick from datacenters as a generic
        bg_folder = "datacenters"
    folder = os.path.join(ASSETS_BG, bg_folder)
    if not os.path.isdir(folder):
        return None
    files = sorted(f for f in os.listdir(folder)
                   if f.lower().endswith((".png", ".jpg", ".jpeg")))
    if not files:
        return None
    return Image.open(os.path.join(folder, files[0])).convert("RGB")


# ── Section renderers ────────────────────────────────────────────────────────

def _draw_date_badge(canvas, draw, font, text, x, y) -> int:
    """Draw rounded dark badge with date+location. Returns the bottom y."""
    if not text:
        return y
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad_x, pad_y = 20, 12
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    draw.rounded_rectangle(box, radius=6, fill=(0, 0, 0, 90))
    draw.text((x + pad_x - bb[0], y + pad_y - bb[1]), text,
              font=font, fill=(255, 255, 255, 255))
    return box[3]


def _draw_role(canvas, draw, role_text, x_right, y_top, max_w, max_size):
    """Right-aligned role label, auto-fit to ≤ 2 lines."""
    if not role_text:
        return
    f, lines, _ = _fit_role(draw, role_text.upper(), max_w, max_size,
                             min_size=24, max_lines=2)
    y = y_top
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=f)
        lw = bb[2] - bb[0]
        draw.text((x_right - lw, y - bb[1]), line, font=f,
                  fill=(255, 255, 255, 255))
        y += (bb[3] - bb[1]) + 8


def _draw_cta(canvas, draw, cta_text, W, H, font_size, bot_pct):
    if not cta_text:
        return
    f = _f("black", font_size)
    text_up = cta_text.upper()
    bb = draw.textbbox((0, 0), text_up, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cx = W // 2
    cy = int(H * (1 - bot_pct)) - th // 2
    # subtle drop shadow for legibility on photo
    draw.text((cx - tw // 2 + 2, cy + 2 - bb[1]), text_up, font=f,
              fill=(0, 0, 0, 140))
    draw.text((cx - tw // 2,     cy     - bb[1]), text_up, font=f,
              fill=(255, 255, 255, 255))


def _render_photo_strip(canvas, theme_rgb, bg, top_y, W, H):
    """Paste the background photo at the bottom + theme-tinted gradient overlay."""
    if bg is None:
        # No bg → solid theme colour band
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.rectangle([0, top_y, W, H], fill=theme_rgb + (255,))
        return
    photo_h = H - top_y
    bg_fit = ImageOps.fit(bg, (W, photo_h), method=Image.LANCZOS).convert("RGB")
    canvas.paste(bg_fit, (0, top_y))
    # Gradient overlay: 0.5 alpha at top → 0.92 alpha at bottom (theme colour)
    overlay = Image.new("RGBA", (W, photo_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    r, g, b = theme_rgb
    for i in range(photo_h):
        t = i / max(1, photo_h - 1)
        alpha = int(255 * (0.50 + 0.42 * t))
        od.line([(0, i), (W, i)], fill=(r, g, b, alpha))
    canvas.paste(overlay, (0, top_y), mask=overlay)


# ── Main render ──────────────────────────────────────────────────────────────

def _render(orientation: str, language: str, event: dict, partner: dict,
            bg_image: Image.Image | None = None) -> Image.Image:
    """
    orientation : 'horizontal' | 'square'
    language    : 'en' / 'es' / 'it' / 'pl'
    event       : dict with theme_key, date_str, location, language
    partner     : dict with company, role_label, logo_img (PIL Image | None)
    bg_image    : optional explicit background photo. If None, picks the first
                  default from assets/backgrounds/{theme}/ for the event's theme.
    """
    L = LAYOUT_H if orientation == "horizontal" else LAYOUT_S
    W, H = (W_H, H_H) if orientation == "horizontal" else (W_S, H_S)

    theme_key = event.get("theme_key", "datacenters")
    theme_rgb = tuple(THEMES.get(theme_key, THEMES["datacenters"])["rgb"])

    # 1) Base canvas — solid theme colour
    canvas = Image.new("RGBA", (W, H), theme_rgb + (255,))

    # 2) Bottom photo strip with theme-tinted gradient
    photo_top = int(H * L["theme_h_pct"])
    bg = bg_image.convert("RGB") if bg_image is not None else _load_default_bg(theme_key)
    _render_photo_strip(canvas, theme_rgb, bg, photo_top, W, H)

    # ─── Pre-measure the role label so we can carve out a dot-free zone
    role_text = (partner.get("role_label") or "").strip()
    role_fit = None        # will hold (font, lines, x_right, y_top) for later drawing
    role_exclude = None    # exclusion rect for the dot pattern
    if role_text:
        tmp_draw = ImageDraw.Draw(canvas, "RGBA")
        max_w = int(W * L["role_max_w_pct"])
        f_role, lines, _ = _fit_role(tmp_draw, role_text.upper(),
                                      max_w, L["role_font"],
                                      min_size=24, max_lines=2)
        if lines:
            widths       = [tmp_draw.textbbox((0, 0), l, font=f_role)[2] for l in lines]
            line_heights = [tmp_draw.textbbox((0, 0), l, font=f_role)[3] for l in lines]
            max_w_actual = max(widths)
            total_h      = sum(line_heights) + 8 * (len(lines) - 1)
            x_right      = W - L["role_right_pad"]
            y_top        = L["role_top"]
            # Padded exclusion zone so dots don't kiss the letters
            pad = 24
            role_exclude = (
                x_right - max_w_actual - pad,
                max(0, y_top - pad),
                x_right + pad,
                y_top + total_h + pad,
            )
            role_fit = (f_role, lines, x_right, y_top)

    # 3) Dotted pattern on the theme zone — minus the role label zone
    dot_zone_w = int(W * L["dot_zone_w_pct"])
    _draw_dots(canvas, 0, 0, dot_zone_w, photo_top + 20, exclude=role_exclude)

    # 4) Slanted white logo pill
    px_left  = int(W * L["pill_left_pct"])
    px_right = int(W * L["pill_right_pct"])
    py_top   = int(H * L["pill_top_pct"])
    py_bot   = int(H * L["pill_bot_pct"])
    inner = _slanted_pill(canvas, px_left, px_right, py_top, py_bot, slant_pct=0.08)
    pill_inner_cx = (inner[0] + inner[2]) // 2
    pill_inner_cy = (inner[1] + inner[3]) // 2
    pill_inner_w  = inner[2] - inner[0]
    pill_inner_h  = inner[3] - inner[1]

    # 5) Sponsor logo OR placeholder text
    logo_img = partner.get("logo_img")
    fitted = _fit_logo(logo_img, pill_inner_w, pill_inner_h, pad=24)
    if fitted is not None:
        _paste_centered(canvas, fitted, pill_inner_cx, pill_inner_cy)
    else:
        # Placeholder text using the company name
        ph_font = _f("black", 56 if orientation == "horizontal" else 44)
        company = (partner.get("company") or "LOGO").upper()
        d = ImageDraw.Draw(canvas)
        bb = d.textbbox((0, 0), company, font=ph_font)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((pill_inner_cx - tw // 2 - bb[0],
                pill_inner_cy - th // 2 - bb[1]),
               company, font=ph_font, fill=(60, 60, 60))

    # 6) RENMAD theme logo (top-left)
    renmad = _load_theme_logo(theme_key)
    logo_y_bot = L["logo_pad"][1]
    if renmad is not None:
        target_w = int(W * L["logo_w_pct"])
        ratio = renmad.width / renmad.height
        target_h = int(target_w / ratio)
        renmad_resized = renmad.resize((target_w, target_h), Image.LANCZOS)
        canvas.paste(renmad_resized, L["logo_pad"], mask=renmad_resized)
        logo_y_bot = L["logo_pad"][1] + target_h

    # 7) Date + location badge (below RENMAD logo)
    # Prefer the structured start_date/end_date (auto-localised); fall back to
    # the legacy date_str for events saved before the structured field existed.
    date_localised = _format_event_date(
        event.get("start_date"), event.get("end_date"), language,
    )
    date_text_parts = []
    if date_localised:
        date_text_parts.append(date_localised.upper())
    elif event.get("date_str"):
        date_text_parts.append(event["date_str"].upper())
    if event.get("location"):
        date_text_parts.append(event["location"].upper())
    date_text = "  ·  ".join(date_text_parts)
    if date_text:
        d = ImageDraw.Draw(canvas, "RGBA")
        f_date = _f("black", L["date_font"])
        _draw_date_badge(canvas, d, f_date, date_text, L["logo_pad"][0], logo_y_bot + 18)

    # 8) Role label (top-right) — uses the fit pre-computed before dots
    if role_fit is not None:
        f_role, lines, x_right, y_top = role_fit
        d = ImageDraw.Draw(canvas, "RGBA")
        y = y_top
        for line in lines:
            bb = d.textbbox((0, 0), line, font=f_role)
            lw = bb[2] - bb[0]
            d.text((x_right - lw, y - bb[1]), line, font=f_role,
                   fill=(255, 255, 255, 255))
            y += (bb[3] - bb[1]) + 8

    # 9) CTA at bottom
    cta = _strings(language).get("event_cta", "Get your pass today!")
    d = ImageDraw.Draw(canvas, "RGBA")
    _draw_cta(canvas, d, cta, W, H, L["cta_font"], L["cta_bot_pct"])

    return canvas.convert("RGB")


# ── Public entry point ───────────────────────────────────────────────────────

def generate_marketing_pack(event: dict, partner: dict,
                             bg_image: Image.Image | None = None) -> dict[str, bytes]:
    """
    Generate the full 4-image marketing pack for one sponsor/partner.

    event = {
      "name":      "RENMAD Hidrógeno",
      "theme_key": "hidrogeno",
      "date_str":  "18-19 NOV. 2026",
      "location":  "ZARAGOZA",
      "language":  "es",
    }
    partner = {
      "company":    "HILTI",
      "role_label": "DIAMOND SPONSOR",
      "logo_img":   <PIL.Image | None>,
    }
    bg_image = optional shared event-wide background photo. If None, picks the
               first photo from assets/backgrounds/{theme}/ as a default.

    Returns: {filename: png_bytes} with 4 keys, e.g.
      'EN_horizontal.png', 'EN_square.png', 'ES_horizontal.png', 'ES_square.png'
    """
    out: dict[str, bytes] = {}
    event_lang = event.get("language", "es").lower()
    languages_to_render = ["en"]
    if event_lang != "en":
        languages_to_render.append(event_lang)

    for lang in languages_to_render:
        for orient in ("horizontal", "square"):
            img = _render(orient, lang, event, partner, bg_image=bg_image)
            buf = io.BytesIO()
            img.save(buf, format="PNG", dpi=(150, 150))
            key = f"{lang.upper()}_{orient}.png"
            out[key] = buf.getvalue()
    return out
