"""
Ingo — LinkedIn share images (1200×630 px)

Two variants per webinar:
  "speaker"  — one per speaker, with the speaker's photo + speaker CTA
               (e.g. "JOIN MY SESSION" / "ÚNETE A MI INTERVENCIÓN")
  "attendee" — one generic, with the event background in the circle + attendee CTA
               (e.g. "SEE YOU AT"     / "NOS VEMOS EN")

No logos of speaker companies — only the event/theme logo in the HOST area,
to avoid conflicts of interest when shared by multiple people on LinkedIn.

Design reference: ingo_preview/ingo_templates_blank.html
"""
import io
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

from config import LANGUAGE_STRINGS
from utils.fonts import get as get_font
from utils import icons


# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 1200, 630

# Layout
LEFT_PAD       = 50
# The right side is deliberately left clear: Ingo composites the sharer's
# LinkedIn photo there at share time, at its own position/size.


# ── Small helpers ─────────────────────────────────────────────────────────────

def _f(style: str, size: int) -> ImageFont.FreeTypeFont:
    mapping = {
        "black":    "montserrat-black",
        "bold":     "montserrat-bold",
        "semibold": "montserrat-semibold",
        "reg":      "montserrat",
        "body":     "inter",
    }
    return get_font(mapping.get(style, "inter"), size)


def _strings(lang: str) -> dict:
    return LANGUAGE_STRINGS.get(lang, LANGUAGE_STRINGS["es"])


def _darken(rgb: tuple, factor: float = 0.30) -> tuple:
    """Return a darker version of an (r,g,b) tuple. factor in [0..1], lower = darker."""
    return tuple(max(0, int(c * factor)) for c in rgb)


# ── Date parsing → "DD DE MES" + weekday ─────────────────────────────────────

_MONTHS_ANY = {
    # ES
    "enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,
    "julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12,
    # EN
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12,
    # IT
    "gennaio":1,"febbraio":2,"aprile":4,"maggio":5,"giugno":6,
    "luglio":7,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12,
    # PL (genitive forms used in dates)
    "stycznia":1,"lutego":2,"marca":3,"kwietnia":4,"maja":5,"czerwca":6,
    "lipca":7,"sierpnia":8,"września":9,"wrzesnia":9,"października":10,"pazdziernika":10,
    "listopada":11,"grudnia":12,
}


def _parse_date(date_str: str) -> datetime | None:
    """Try hard to extract a (day, month, year) from a free-form date string."""
    if not date_str:
        return None
    s = date_str.strip().lower()
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    m = re.search(r"\b(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?\b", s)
    if m:
        d, mo, y = m.group(1), m.group(2), m.group(3)
        try:
            yi = int(y) if y else datetime.now().year
            if yi < 100:
                yi += 2000
            return datetime(yi, int(mo), int(d))
        except ValueError:
            pass
    # "21 de mayo (de 2026)" / "21 May 2026"
    m = re.search(r"\b(\d{1,2})\s+(?:de\s+)?([a-zñáéíóúąęśćźżł]+)(?:\s+(?:de\s+)?(\d{4}))?\b", s)
    if m:
        d, mon_name, y = m.group(1), m.group(2), m.group(3)
        mo = _MONTHS_ANY.get(mon_name)
        if mo:
            try:
                yi = int(y) if y else datetime.now().year
                return datetime(yi, mo, int(d))
            except ValueError:
                pass
    return None


_FALLBACK_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
_FALLBACK_WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves",
                      "Viernes", "Sábado", "Domingo"]


def _format_date_line(date_str: str, language: str) -> tuple[str, str]:
    """
    Returns (main_text, weekday_text) for the date line.
    Falls back to (date_str, "") if parsing fails.
    """
    strings = _strings(language)
    # Use literal fallbacks (not LANGUAGE_STRINGS["es"][...]) so this works even
    # if the running config is older / missing these keys.
    months   = strings.get("months",   _FALLBACK_MONTHS)
    weekdays = strings.get("weekdays", _FALLBACK_WEEKDAYS)

    dt = _parse_date(date_str)
    if dt is None:
        return (date_str or "", "")

    # "21 DE MAYO" style for ES/IT, "21 MAY" for EN/PL etc.
    mon = months[dt.month - 1].upper()
    if language == "es":
        main = f"{dt.day} DE {mon}"
    elif language == "it":
        main = f"{dt.day} {mon}"
    else:
        main = f"{dt.day} {mon}"

    wd = weekdays[dt.weekday()].upper()
    return (main, wd)


# ── Icons used in the CTA badge ──────────────────────────────────────────────

def _sparkle_icon(size: int = 22, color: tuple = (255, 255, 255)) -> Image.Image:
    """
    Four-pointed sparkle / star (✦). Filled polygon with concave indents so
    the four points are clearly visible at small sizes.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = size // 2
    r = size // 2 - 1
    inner = max(2, r // 3)   # concave inner radius — controls how "pointy" it looks
    pts = [
        (cx,         cy - r),          # top point
        (cx + inner, cy - inner),
        (cx + r,     cy),              # right point
        (cx + inner, cy + inner),
        (cx,         cy + r),          # bottom point
        (cx - inner, cy + inner),
        (cx - r,     cy),              # left point
        (cx - inner, cy - inner),
    ]
    d.polygon(pts, fill=color)
    return img


# Kept for future use / backwards compatibility (not currently called)
def _person_icon(size: int = 24, color: tuple = (255, 255, 255)) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    head_r = size // 4
    cx = size // 2
    head_cy = head_r + 1
    d.ellipse([cx - head_r, head_cy - head_r,
               cx + head_r, head_cy + head_r], outline=color, width=max(2, size // 12))
    body_top = head_cy + head_r + 1
    body_bot = size - 2
    pad = size // 5
    d.arc([pad, body_top - head_r,
           size - pad, body_bot + head_r],
          start=200, end=340, fill=color, width=max(2, size // 12))
    return img


# ── Background photo + theme-tinted overlay ──────────────────────────────────

def _build_background(theme_rgb: tuple, background_img: Image.Image | None) -> Image.Image:
    """
    Cover the full canvas with the background image (or a dark theme-coloured
    gradient if none), then paint a left-to-right colour overlay that fades
    out around 78% across, so the photo is fully visible on the right.
    """
    canvas = Image.new("RGB", (W, H), (20, 20, 30))

    if background_img is not None:
        bg = ImageOps.fit(background_img.convert("RGB"), (W, H), method=Image.LANCZOS)
        canvas.paste(bg, (0, 0))
    else:
        # No photo: dark diagonal gradient in the theme colour
        dark = _darken(theme_rgb, 0.18)
        mid  = _darken(theme_rgb, 0.55)
        grad = Image.new("RGB", (W, H), dark)
        gd = ImageDraw.Draw(grad)
        for x in range(W):
            t = x / W
            r = int(dark[0] + (mid[0] - dark[0]) * t)
            g = int(dark[1] + (mid[1] - dark[1]) * t)
            b = int(dark[2] + (mid[2] - dark[2]) * t)
            gd.line([(x, 0), (x, H)], fill=(r, g, b))
        canvas.paste(grad, (0, 0))

    # Left-to-right alpha gradient overlay in the theme colour
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    tint = _darken(theme_rgb, 0.72)        # slightly darkened tint
    for x in range(W):
        t = x / W
        if t < 0.45:
            a = 235          # 92% opacity at the very left
        elif t < 0.78:
            # Smooth fade between 0.45 and 0.78 (235 → 0)
            local = (t - 0.45) / (0.78 - 0.45)
            a = int(235 * (1 - local))
        else:
            a = 0
        od.line([(x, 0), (x, H)], fill=(tint[0], tint[1], tint[2], a))
    canvas.paste(overlay, (0, 0), mask=overlay)
    return canvas.convert("RGBA")


# ── CTA badge top-left ────────────────────────────────────────────────────────

def _draw_cta_badge(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                    cta_text: str, theme_rgb: tuple) -> int:
    """Draw the personalised CTA pill. Returns its bottom-Y for next-element placement."""
    # Lighter weight than Black + slightly smaller → less "blocky" feel
    font = _f("bold", 19)
    text_bb = draw.textbbox((0, 0), cta_text, font=font)
    text_w  = text_bb[2] - text_bb[0]
    text_h  = text_bb[3] - text_bb[1]

    pad_x, pad_y = 22, 13
    icon_size = 22
    gap = 12
    pill_w = pad_x + icon_size + gap + text_w + pad_x
    pill_h = pad_y + max(text_h, icon_size) + pad_y

    x, y = LEFT_PAD, 36
    bg = _darken(theme_rgb, 0.18)
    # Pill-shaped background (corner radius ≈ half the height = real pill)
    radius = pill_h // 2
    draw.rounded_rectangle([x, y, x + pill_w, y + pill_h], radius=radius, fill=bg)
    draw.rounded_rectangle([x, y, x + pill_w, y + pill_h], radius=radius,
                            outline=(255, 255, 255, 55), width=1)

    icon = _sparkle_icon(icon_size, color=(255, 255, 255))
    icon_y = y + (pill_h - icon_size) // 2
    canvas.paste(icon, (x + pad_x, icon_y), mask=icon)

    tx = x + pad_x + icon_size + gap
    ty = y + (pill_h - text_h) // 2 - text_bb[1]
    draw.text((tx, ty), cta_text, font=font, fill=(255, 255, 255))

    return y + pill_h


# ── WEBINAR + title ───────────────────────────────────────────────────────────

def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list:
    """Greedy word-wrap into lines that fit within max_w."""
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


def _fit_lines(draw: ImageDraw.ImageDraw, lines: list[str], max_w: int,
               max_size: int, min_size: int) -> tuple:
    """Largest font size where every line in `lines` fits within max_w."""
    for size in range(max_size, min_size - 1, -2):
        f = _f("bold", size)
        if all(draw.textbbox((0, 0), ln, font=f)[2] <= max_w for ln in lines):
            return f, size
    return _f("bold", min_size), min_size


def _fit_wrap(draw: ImageDraw.ImageDraw, text: str, max_w: int,
              max_lines: int, max_size: int, min_size: int) -> tuple:
    """Largest font size where wrapping `text` yields ≤ max_lines lines."""
    for size in range(max_size, min_size - 1, -2):
        f = _f("bold", size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
    f = _f("bold", min_size)
    return f, _wrap(draw, text, f, max_w), min_size


def _title_parts(raw_title: str) -> list[str]:
    """
    Decide where to break the title into chunks BEFORE wrapping:
      1. Explicit '\\n' in the title → exactly those lines (every one, no truncation)
      2. Title contains ':' → break into [before+':', after]
      3. Otherwise → one chunk (free word-wrap will handle it)
    """
    raw = (raw_title or "").strip()
    if not raw:
        return []
    if "\n" in raw:
        parts = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        return [p.upper() for p in parts] if parts else [raw.upper()]
    if ":" in raw:
        a, b = raw.split(":", 1)
        if a.strip() and b.strip():
            return [(a.strip() + ":").upper(), b.strip().upper()]
    return [raw.upper()]


def _fit_title(draw: ImageDraw.ImageDraw, parts: list[str], max_w: int,
               soft_max_lines: int, max_size: int, min_size: int) -> tuple:
    """
    Find the biggest font where each chunk word-wraps independently and the
    total line count is ≤ soft_max_lines.

    CRITICAL: never drops content. If the title can't fit in soft_max_lines at
    min_size, we still return every wrapped line — the caller renders them all.
    """
    for size in range(max_size, min_size - 1, -2):
        f = _f("bold", size)
        all_lines = []
        for p in parts:
            all_lines.extend(_wrap(draw, p, f, max_w))
        if len(all_lines) <= soft_max_lines:
            return f, all_lines, size
    # Couldn't fit in soft_max_lines even at min_size — still return EVERY line
    f = _f("bold", min_size)
    all_lines = []
    for p in parts:
        all_lines.extend(_wrap(draw, p, f, max_w))
    return f, all_lines, min_size


def _draw_title_block(draw: ImageDraw.ImageDraw, top: int, session_title: str,
                      theme_rgb: tuple) -> int:
    """
    WEBINAR headline + full session title.

    Title break rules:
      • '\\n' in input → exactly those lines (all preserved)
      • ':' in input → split into [before:, after], each word-wraps if needed
      • neither      → free word-wrap

    Font auto-shrinks (max 52 → min 22). The caller's vertical layout adapts so
    the title can grow to 4 lines without colliding with the date row.
    Returns bottom-Y.
    """
    max_w          = 760   # ring left edge ≈ 790 now, with 30px breathing room
    soft_max_lines = 4     # allow up to 4 lines so the font stays bigger
    max_size       = 36    # quieter — was too dominant before
    min_size       = 20    # absolute floor — below this readability suffers

    # ── WEBINAR — bigger so it occupies more real estate ──────────────────
    f_webinar = _f("black", 78)
    y = top + 2
    draw.text((LEFT_PAD, y), "WEBINAR", font=f_webinar, fill=(255, 255, 255))
    wb_bb = draw.textbbox((0, 0), "WEBINAR", font=f_webinar)
    y += (wb_bb[3] - wb_bb[1]) + 36   # generous breathing room — was 18, felt cramped

    # ── Title — ALWAYS renders every line, never truncates ─────────────────
    parts = _title_parts(session_title)
    if parts:
        f_title, lines, _size = _fit_title(
            draw, parts, max_w, soft_max_lines, max_size, min_size,
        )
        line_h = draw.textbbox((0, 0), "Ag", font=f_title)[3] + 8
        for line in lines:
            draw.text((LEFT_PAD, y), line, font=f_title, fill=(255, 255, 255))
            y += line_h
        y += 6

    # ── Divider ────────────────────────────────────────────────────────────
    accent = tuple(min(255, int(c * 1.30) + 30) for c in theme_rgb)
    draw.rectangle([LEFT_PAD, y, LEFT_PAD + 160, y + 3], fill=accent + (255,))
    y += 16
    return y


# ── Date + time/location row ──────────────────────────────────────────────────

def _draw_datetime_row(canvas: Image.Image, draw: ImageDraw.ImageDraw, top: int,
                       date_str: str, time_str: str, location_str: str,
                       language: str, theme_rgb: tuple) -> int:
    strings = _strings(language)
    online_label = strings.get("ingo_online", "Online")

    # Calendar icon inside a dark circle
    circle_d = 54
    cx, cy = LEFT_PAD + circle_d // 2, top + circle_d // 2
    bg_circle = _darken(theme_rgb, 0.16)
    draw.ellipse([LEFT_PAD, top, LEFT_PAD + circle_d, top + circle_d], fill=bg_circle)
    draw.ellipse([LEFT_PAD, top, LEFT_PAD + circle_d, top + circle_d],
                 outline=(255, 255, 255, 60), width=1)
    cal = icons.calendar(28, color=(255, 255, 255))
    canvas.paste(cal, (cx - 14, cy - 14), mask=cal)

    # Vertical divider
    div_x = LEFT_PAD + circle_d + 14
    draw.line([(div_x, top + 6), (div_x, top + circle_d - 6)],
              fill=(255, 255, 255, 110), width=1)

    text_x = div_x + 14

    # Main: "DD DE MES · MIÉRCOLES"
    main_text, wd_text = _format_date_line(date_str, language)
    f_main = _f("black", 26)
    accent = tuple(min(255, int(c * 1.30) + 30) for c in theme_rgb)
    draw.text((text_x, top + 2), main_text, font=f_main, fill=accent + (255,))
    main_bb = draw.textbbox((0, 0), main_text, font=f_main)
    after_main_x = text_x + (main_bb[2] - main_bb[0])

    if wd_text:
        # Separator dot
        dot_x = after_main_x + 12
        f_dot  = _f("bold", 22)
        draw.text((dot_x, top + 5), "·", font=f_dot, fill=(255, 255, 255, 140))
        dot_bb = draw.textbbox((0, 0), "·", font=f_dot)
        dow_x = dot_x + (dot_bb[2] - dot_bb[0]) + 10
        f_wd  = _f("semibold", 20)
        draw.text((dow_x, top + 8), wd_text, font=f_wd, fill=(255, 255, 255, 220))

    # Sub-line: "11:00 CEST · 📍 Online"
    sub_y = top + 38
    f_sub = _f("semibold", 17)
    sub_time = (time_str or "").strip()
    if sub_time:
        draw.text((text_x, sub_y), sub_time, font=f_sub, fill=(255, 255, 255, 240))
        st_bb = draw.textbbox((0, 0), sub_time, font=f_sub)
        loc_x = text_x + (st_bb[2] - st_bb[0]) + 14
    else:
        loc_x = text_x

    # Decide location text: explicit location > Online fallback
    loc_text = (location_str or "").strip() or online_label

    # Separator dot
    if sub_time:
        f_dot_s = _f("bold", 17)
        draw.text((loc_x - 4, sub_y - 1), "·", font=f_dot_s, fill=(255, 255, 255, 140))
        loc_x += 10

    # Pin icon
    pin_ic = icons.pin(18, color=(255, 255, 255, 240))
    canvas.paste(pin_ic, (loc_x, sub_y), mask=pin_ic)
    draw.text((loc_x + 22, sub_y), loc_text,
              font=f_sub, fill=(255, 255, 255, 240))

    return top + circle_d + 10


# ── HOST block (label + theme logo, all INSIDE the white box) ────────────────

def _draw_host_block(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                     logo_img: Image.Image | None, language: str,
                     theme_rgb: tuple) -> None:
    """
    Compact host card sitting at the bottom-left:
      ┌──────────────────────────────────┐
      │ HOST                             │
      │       [ theme logo here ]        │
      └──────────────────────────────────┘
    'HOST' label sits inside the box (top-left), rendered in the theme colour.
    """
    strings = _strings(language)
    label = strings.get("ingo_host_label", "HOST")

    # Compact box, kept short so the date row above doesn't overlap
    box_w, box_h = 290, 78
    y_box = H - 28 - box_h
    x_box = LEFT_PAD

    # White rounded rectangle
    draw.rounded_rectangle([x_box, y_box, x_box + box_w, y_box + box_h],
                           radius=12, fill=(255, 255, 255, 250))

    # HOST label INSIDE the box, top-left, in theme colour
    f_lbl = _f("black", 14)
    inner_pad_x = 14
    label_top = y_box + 9
    draw.text((x_box + inner_pad_x, label_top), label,
              font=f_lbl, fill=theme_rgb + (255,))

    # Logo region — below the label, centered (no divider line)
    if logo_img is not None:
        logo = logo_img.convert("RGBA")
        lbl_bb = draw.textbbox((0, 0), label, font=f_lbl)
        logo_zone_top = label_top + (lbl_bb[3] - lbl_bb[1]) + 8
        logo_zone_bot = y_box + box_h - 10
        max_w = box_w - inner_pad_x * 2
        max_h = logo_zone_bot - logo_zone_top
        lw, lh = logo.size
        scale = min(max_w / lw, max_h / lh)
        nw, nh = max(1, int(lw * scale)), max(1, int(lh * scale))
        logo_r = logo.resize((nw, nh), Image.LANCZOS)
        lx = x_box + (box_w - nw) // 2
        ly = logo_zone_top + (max_h - nh) // 2
        canvas.paste(logo_r, (lx, ly), mask=logo_r)


# ── Variant generators ────────────────────────────────────────────────────────

def _render(cta_text: str,
            session: dict,
            theme: dict,
            language: str,
            background_img: Image.Image | None,
            host_logo: Image.Image | None) -> Image.Image:
    theme_rgb = tuple(theme["rgb"])

    canvas = _build_background(theme_rgb, background_img)
    # NOTE: right side deliberately left clear — Ingo composites the sharer's
    #       LinkedIn photo there at share time (diagonal stripes removed).
    # NOTE: no placeholder ring — Ingo composites the sharer's LinkedIn photo
    # at its own position, which never matched a pre-drawn circle.

    draw = ImageDraw.Draw(canvas, "RGBA")
    bottom_after_cta = _draw_cta_badge(canvas, draw, cta_text, theme_rgb)
    bottom_after_title = _draw_title_block(
        draw, bottom_after_cta + 6, session.get("title", ""), theme_rgb
    )
    _draw_datetime_row(
        canvas, draw, bottom_after_title + 4,
        session.get("date_str", ""),
        session.get("time_str", ""),
        session.get("location", ""),
        language, theme_rgb,
    )
    _draw_host_block(canvas, draw, host_logo, language, theme_rgb)

    return canvas.convert("RGB")


# ── Public entry point ────────────────────────────────────────────────────────

def generate_speaker(session: dict, theme: dict, language: str,
                     background_img: Image.Image | None,
                     renmad_logo: Image.Image | None) -> bytes:
    """
    Generate the speaker-variant Ingo template.
    The circle is left empty — Ingo overlays the sharer's LinkedIn picture.
    """
    strings = _strings(language)
    cta = strings.get("ingo_speaker_cta", "JOIN MY SESSION")
    img = _render(cta, session, theme, language, background_img, renmad_logo)
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


def generate_attendee(session: dict, theme: dict, language: str,
                      background_img: Image.Image | None,
                      renmad_logo: Image.Image | None) -> bytes:
    """
    Generate the attendee-variant Ingo template.
    The circle is left empty — Ingo overlays the sharer's LinkedIn picture.
    """
    strings = _strings(language)
    cta = strings.get("ingo_attendee_cta", "SEE YOU AT")
    img = _render(cta, session, theme, language, background_img, renmad_logo)
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


def generate_all(session: dict, theme: dict, language: str,
                 background_img: Image.Image | None,
                 renmad_logo: Image.Image | None) -> dict:
    """
    Generate the Ingo template pack for a webinar — TWO images total:
      • ingo_speaker.png   — empty template, speaker CTA
      • ingo_attendee.png  — empty template, attendee CTA

    Returns: {filename: png_bytes}
    """
    return {
        "ingo_speaker.png":  generate_speaker(session, theme, language, background_img, renmad_logo),
        "ingo_attendee.png": generate_attendee(session, theme, language, background_img, renmad_logo),
    }


