"""T1 — Single Speaker Slide  1920 × 1080  (dark dramatic style)."""
import io, math
from PIL import Image, ImageDraw, ImageFilter
from utils.image_utils import make_circular
from utils.gender import moderator_label
from config import LANGUAGE_STRINGS

W, H = 1920, 1080


def _font(name, size):
    from utils.fonts import get
    return get({"heavy": "montserrat-black",
                "bold":  "montserrat-bold",
                "reg":   "inter"}.get(name, "inter"), size)


def _draw_text_cx(draw, text, font, cx, y, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - bb[2] // 2, y), text, font=font, fill=fill)
    return y + bb[3]


def generate(session: dict, theme: dict, language: str = "es",
             renmad_logo: Image.Image | None = None,
             bg_image:    Image.Image | None = None,
             ata_logo:    Image.Image | None = None) -> tuple[bytes, bytes]:

    strings   = LANGUAGE_STRINGS.get(language, LANGUAGE_STRINGS["es"])
    theme_rgb = tuple(theme["rgb"])

    speakers = session.get("speakers", [])
    spk = next((s for s in speakers if not s.get("is_moderator")), speakers[0] if speakers else {})

    # ── Background ────────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (W, H), (15, 15, 20))

    if bg_image:
        bg = bg_image.convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=3))
        canvas.paste(bg)
        overlay = Image.new("RGB", (W, H), (10, 10, 15))
        canvas.paste(overlay, mask=Image.new("L", (W, H), 160))
    else:
        draw_tmp = ImageDraw.Draw(canvas)
        for y in range(H):
            r = int(15 + math.sin(y / H * math.pi) * 12)
            draw_tmp.line([(0, y), (W, y)], fill=(r, r, r + 5))

    draw = ImageDraw.Draw(canvas)

    # ── Top accent bar ────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, 8], fill=theme_rgb)

    # ── Left column: photo + accent strip ────────────────────────────────────
    col_split  = W // 2   # photo on left half
    photo_size = 480
    cx_photo   = col_split // 2
    cy_photo   = H // 2 - 30

    if spk.get("photo"):
        try:
            photo = make_circular(spk["photo"].convert("RGBA"), photo_size,
                                  border_color=theme_rgb, border_width=6)
            px = cx_photo - photo.width // 2
            py = cy_photo - photo.height // 2
            canvas.paste(photo, (px, py), mask=photo)
        except Exception:
            pass

    # Vertical accent line between columns
    draw.line([(col_split, 60), (col_split, H - 100)], fill=theme_rgb, width=3)

    # ── Right column: text ────────────────────────────────────────────────────
    cx_text = col_split + (W - col_split) // 2
    ty      = H // 2 - 160  # starting y for text block

    # Company logo
    if spk.get("company_logo"):
        try:
            clogo = spk["company_logo"].convert("RGBA")
            clogo.thumbnail((240, 64), Image.LANCZOS)
            pad = 10
            pill = Image.new("RGB", (clogo.width + pad*2, clogo.height + pad*2), (230, 230, 230))
            canvas.paste(pill, (cx_text - clogo.width // 2 - pad, ty - pad))
            canvas.paste(clogo, (cx_text - clogo.width // 2, ty), mask=clogo)
            ty += clogo.height + pad * 2 + 18
        except Exception:
            pass

    # Moderator badge
    if spk.get("is_moderator"):
        mod_label = moderator_label(spk.get("name", ""), strings)
        mf        = _font("bold", 22)
        mb        = draw.textbbox((0, 0), mod_label, font=mf)
        pad       = 10
        draw.rounded_rectangle(
            [cx_text - mb[2]//2 - pad, ty - 4,
             cx_text + mb[2]//2 + pad, ty + mb[3] + 4],
            radius=6, fill=theme_rgb,
        )
        draw.text((cx_text - mb[2] // 2, ty), mod_label, font=mf, fill=(255, 255, 255))
        ty += mb[3] + 20

    # Name
    ty = _draw_text_cx(draw, spk.get("name", ""), _font("bold", 56), cx_text, ty, (255, 255, 255))
    ty += 8

    # Accent rule under name
    draw.line([(cx_text - 120, ty), (cx_text + 120, ty)], fill=theme_rgb, width=3)
    ty += 16

    # Job title
    ty = _draw_text_cx(draw, spk.get("title", ""), _font("reg", 34), cx_text, ty, (200, 200, 200))
    ty += 8

    # Company
    _draw_text_cx(draw, spk.get("company", ""), _font("bold", 32), cx_text, ty, theme_rgb)

    # ── Footer band ───────────────────────────────────────────────────────────
    cta      = session.get("cta_url", "").strip()
    footer_h = 120 if cta else 90
    fy       = H - footer_h

    foot = Image.new("RGBA", (W, footer_h), (*theme_rgb, 230))
    canvas.paste(foot.convert("RGB"), (0, fy))
    draw.line([(0, fy), (W, fy)], fill=(255, 255, 255), width=2)

    # RENMAD logo bottom-right (reserve space)
    logo_reserve = 0
    if renmad_logo:
        logo = renmad_logo.convert("RGBA")
        lh   = 70
        lw   = int(logo.width * lh / logo.height)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        canvas.paste(logo, (W - lw - 24, fy + (footer_h - lh) // 2), mask=logo)
        logo_reserve = lw + 40

    cx_footer = (W - logo_reserve) // 2

    # Session title
    bar_f = _font("heavy", 34)
    title_text = session.get("title", "").upper()
    title_y = fy + 14
    _draw_text_cx(draw, title_text, bar_f, cx_footer, title_y, (255, 255, 255))

    # Event details: date | time | location
    parts = [p for p in [session.get("date_str",""), session.get("time_str",""),
                          session.get("location","")] if p]
    detail_y = title_y + 42
    if parts:
        detail = "   |   ".join(parts).upper()
        df     = _font("reg", 22)
        db     = draw.textbbox((0, 0), detail, font=df)
        draw.text((cx_footer - db[2] // 2, detail_y), detail, font=df, fill=(230, 230, 230))
        detail_y += db[3] + 6

    # CTA / URL — translated label + bare URL
    if cta:
        href     = cta if cta.startswith("http") else cta
        label    = strings.get("cta_label", "Regístrate gratis hoy")
        cta_line = f"{label}  →  {href}"
        uf = _font("reg", 20)
        ub = draw.textbbox((0, 0), cta_line, font=uf)
        draw.text((cx_footer - ub[2] // 2, detail_y), cta_line, font=uf, fill=(255, 255, 200))

    png_buf = io.BytesIO()
    canvas.save(png_buf, format="PNG", dpi=(150, 150))
    return _build_pptx(canvas, W, H), png_buf.getvalue()


def _build_pptx(img, w, h):
    from pptx import Presentation
    from pptx.util import Emu
    DPI = 96
    def px(p): return Emu(int(p / DPI * 914400))
    prs = Presentation()
    prs.slide_width  = px(w)
    prs.slide_height = px(h)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    buf = io.BytesIO()
    img.save(buf, format="PNG"); buf.seek(0)
    slide.shapes.add_picture(buf, 0, 0, px(w), px(h))
    out = io.BytesIO(); prs.save(out)
    return out.getvalue()
