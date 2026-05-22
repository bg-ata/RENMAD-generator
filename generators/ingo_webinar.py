"""
Ingo — Webinar promotional images (1200×630px)
Two variants:
  "confirmado" — Registro confirmado / Registration confirmed
  "ponencia"   — No te pierdas mi ponencia (speaker sharing)
"""
import io
from PIL import Image, ImageDraw, ImageFont
from config import LANGUAGE_STRINGS

W, H = 1200, 630

# Layout
TOP_BAR_H = 82
GREEN_BAR_H = 38
BOTTOM_H = 110
CONTENT_TOP = TOP_BAR_H         # for confirmado (green bar in top_bar zone)
DIAG_LEFT_TOP = 390             # x of diagonal top edge
DIAG_LEFT_BOT = 510             # x of diagonal bottom edge (above bottom strip)
CONTENT_BOT = H - BOTTOM_H


def _font(style: str, size: int) -> ImageFont.FreeTypeFont:
    from utils.fonts import get
    mapping = {"heavy": "montserrat-black", "bold": "montserrat-bold", "reg": "inter"}
    return get(mapping.get(style, "inter"), size)


def _wrap(draw, text, font, max_w):
    words = text.split()
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


def _paste_logo(canvas, logo_img, x, y, target_h):
    """Resize logo to target_h, paste at (x, y). Returns actual width used."""
    if logo_img is None:
        return 0
    logo = logo_img.convert("RGBA")
    ratio = logo.width / logo.height
    w = int(target_h * ratio)
    logo = logo.resize((w, target_h), Image.LANCZOS)
    canvas.paste(logo, (x, y), mask=logo)
    return w


def _build_canvas(background_img, theme_rgb):
    """Create base canvas: background on right, white on left with diagonal."""
    canvas = Image.new("RGBA", (W, H), (255, 255, 255, 255))

    if background_img:
        bg = background_img.convert("RGBA").resize((W, H), Image.LANCZOS)
    else:
        r, g, b = theme_rgb
        bg = Image.new("RGBA", (W, H), (r, g, b, 255))

    # Diagonal mask — photo fills the right side; white covers the left
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    # Polygon: top-right → bottom-right → bottom-left-edge → top-left-edge
    md.polygon([
        (DIAG_LEFT_TOP, TOP_BAR_H),
        (W, TOP_BAR_H),
        (W, CONTENT_BOT),
        (DIAG_LEFT_BOT, CONTENT_BOT),
    ], fill=255)
    canvas.paste(bg, (0, 0), mask=mask)
    return canvas


def _draw_webinar_box(canvas, draw, date_str, time_str, theme_rgb):
    """Draw the white WEBINAR date/time box on the left."""
    bx, by = 28, TOP_BAR_H + 28
    bw, bh = 220, 130
    draw.rectangle([bx, by, bx + bw, by + bh], fill=(255, 255, 255))
    draw.rectangle([bx, by, bx + bw, by + bh],
                   outline=(180, 180, 180), width=2)

    f_label = _font("heavy", 18)
    f_date  = _font("bold", 22)
    f_time  = _font("bold", 22)

    label_h = draw.textbbox((0, 0), "WEBINAR", font=f_label)[3]
    # Coloured header inside box
    draw.rectangle([bx, by, bx + bw, by + label_h + 10], fill=theme_rgb)
    draw.text((bx + bw // 2, by + 5), "WEBINAR", font=f_label,
              fill=(255, 255, 255), anchor="mt")

    ty = by + label_h + 18
    draw.text((bx + bw // 2, ty), date_str, font=f_date,
              fill=(30, 30, 30), anchor="mt")
    ty += draw.textbbox((0, 0), date_str, font=f_date)[3] + 8
    draw.text((bx + bw // 2, ty), time_str, font=f_time,
              fill=(30, 30, 30), anchor="mt")


def _draw_bottom_strip(canvas, draw, renmad_logo, ata_logo, language):
    """White bottom strip with HOSTS label and logos."""
    strings = LANGUAGE_STRINGS.get(language, LANGUAGE_STRINGS["es"])
    draw.rectangle([0, CONTENT_BOT, W, H], fill=(255, 255, 255))
    draw.line([(0, CONTENT_BOT), (W, CONTENT_BOT)], fill=(220, 220, 220), width=1)

    f_host = _font("bold", 18)
    host_label = strings.get("hosted_by", "HOST:")
    draw.text((28, CONTENT_BOT + 18), host_label, font=f_host, fill=(80, 80, 80))

    logo_y = CONTENT_BOT + 14
    logo_h = BOTTOM_H - 28
    lx = 28 + draw.textbbox((0, 0), host_label, font=f_host)[2] + 20

    if ata_logo:
        w = _paste_logo(canvas, ata_logo, lx, logo_y, logo_h)
        lx += w + 20
    if renmad_logo:
        _paste_logo(canvas, renmad_logo, lx, logo_y, logo_h)


# ── Variant 1: Registro Confirmado ───────────────────────────────────────────

def _generate_confirmado(session, theme, language, background_img, renmad_logo, ata_logo):
    theme_rgb = tuple(theme["rgb"])
    strings = LANGUAGE_STRINGS.get(language, LANGUAGE_STRINGS["es"])

    canvas = _build_canvas(background_img, theme_rgb)
    draw = ImageDraw.Draw(canvas)

    # Top theme-colour title bar
    draw.rectangle([0, 0, W, TOP_BAR_H], fill=theme_rgb)
    f_title = _font("heavy", 26)
    title = session.get("title", "").upper()
    lines = _wrap(draw, title, f_title, W - 40)
    ty = (TOP_BAR_H - len(lines) * 30) // 2
    for line in lines[:2]:
        draw.text((20, ty), line, font=f_title, fill=(255, 255, 255))
        ty += 32

    # Green "REGISTRO CONFIRMADO ✓" bar  (below top bar, spanning ~60% of width)
    green = (34, 180, 34)
    bar_y = TOP_BAR_H
    bar_h = GREEN_BAR_H
    draw.rectangle([0, bar_y, int(W * 0.62), bar_y + bar_h], fill=green)
    f_conf = _font("bold", 20)
    label = f"  {strings.get('welcome', 'REGISTRO CONFIRMADO')}  ✓" if language != "es" else "  REGISTRO CONFIRMADO  ✓"
    draw.text((16, bar_y + 8), label, font=f_conf, fill=(255, 255, 255))

    # Shift content top down past green bar
    global CONTENT_TOP
    ct = TOP_BAR_H + bar_h + 10

    # Webinar date/time box
    bx, by = 28, ct + 10
    bw, bh = 220, 130
    draw.rectangle([bx, by, bx + bw, by + bh], fill=(255, 255, 255))
    draw.rectangle([bx, by, bx + bw, by + bh], outline=(180, 180, 180), width=2)
    f_label = _font("heavy", 18)
    f_dt = _font("bold", 21)
    lh = draw.textbbox((0, 0), "WEBINAR", font=f_label)[3]
    draw.rectangle([bx, by, bx + bw, by + lh + 10], fill=theme_rgb)
    draw.text((bx + bw // 2, by + 5), "WEBINAR", font=f_label,
              fill=(255, 255, 255), anchor="mt")
    dy = by + lh + 18
    date_str = session.get("date_str", "")
    time_str = session.get("time_str", "")
    draw.text((bx + bw // 2, dy), date_str, font=f_dt, fill=(30, 30, 30), anchor="mt")
    dy += draw.textbbox((0, 0), date_str, font=f_dt)[3] + 10
    draw.text((bx + bw // 2, dy), time_str, font=f_dt, fill=(30, 30, 30), anchor="mt")

    _draw_bottom_strip(canvas, draw, renmad_logo, ata_logo, language)
    return canvas.convert("RGB")


# ── Variant 2: No te pierdas mi ponencia ─────────────────────────────────────

def _generate_ponencia(session, theme, language, background_img, renmad_logo, ata_logo):
    theme_rgb = tuple(theme["rgb"])

    canvas = _build_canvas(background_img, theme_rgb)
    draw = ImageDraw.Draw(canvas)

    # Dark top bar
    dark = (25, 25, 35)
    draw.rectangle([0, 0, W, TOP_BAR_H], fill=dark)

    # Monitor emoji (text stand-in) + headline
    headline = "NO TE PIERDAS MI PONENCIA EN EL WEBINAR:"
    f_hl = _font("heavy", 20)
    draw.text((20, 16), "🖥  " + headline, font=f_hl, fill=(255, 255, 255))

    # Session title on white area below dark bar
    f_ttl = _font("heavy", 30)
    title = session.get("title", "").upper()
    max_w = DIAG_LEFT_TOP - 20
    lines = _wrap(draw, title, f_ttl, max_w)
    ty = TOP_BAR_H + 18
    for line in lines[:3]:
        draw.text((20, ty), line, font=f_ttl, fill=(30, 30, 30))
        ty += draw.textbbox((0, 0), line, font=f_ttl)[3] + 6

    # Webinar date/time box
    bx, by = 28, ty + 16
    bw, bh = 210, 120
    draw.rectangle([bx, by, bx + bw, by + bh], fill=(255, 255, 255))
    draw.rectangle([bx, by, bx + bw, by + bh], outline=(180, 180, 180), width=2)
    f_label = _font("heavy", 17)
    f_dt = _font("bold", 20)
    lh = draw.textbbox((0, 0), "WEBINAR", font=f_label)[3]
    draw.rectangle([bx, by, bx + bw, by + lh + 10], fill=theme_rgb)
    draw.text((bx + bw // 2, by + 5), "WEBINAR", font=f_label,
              fill=(255, 255, 255), anchor="mt")
    dy = by + lh + 16
    date_str = session.get("date_str", "")
    time_str = session.get("time_str", "")
    draw.text((bx + bw // 2, dy), date_str, font=f_dt, fill=(30, 30, 30), anchor="mt")
    dy += draw.textbbox((0, 0), date_str, font=f_dt)[3] + 8
    draw.text((bx + bw // 2, dy), time_str, font=f_dt, fill=(30, 30, 30), anchor="mt")

    _draw_bottom_strip(canvas, draw, renmad_logo, ata_logo, language)
    return canvas.convert("RGB")


# ── Public entry point ────────────────────────────────────────────────────────

def generate(session: dict, theme: dict, language: str,
             background_img: Image.Image | None,
             renmad_logo: Image.Image | None,
             ata_logo: Image.Image | None,
             variant: str = "confirmado") -> bytes:
    """
    Returns png_bytes for the requested variant.
    variant: "confirmado" | "ponencia"
    """
    if variant == "ponencia":
        img = _generate_ponencia(session, theme, language, background_img, renmad_logo, ata_logo)
    else:
        img = _generate_confirmado(session, theme, language, background_img, renmad_logo, ata_logo)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()
