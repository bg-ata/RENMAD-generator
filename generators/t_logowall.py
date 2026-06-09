"""T_Logowall — Event logo wall  1920 px wide, dynamic height

Layout  (stacked rows, biggest at the top)
──────────────────────────────────────────
  WHITE background throughout.

    · 8 px theme-colour accent line across the top
    · RENMAD logo, centred (optional)
    · One ROW PER SPONSOR TIER, most important first:
        – small centred tier label (theme colour) e.g. "DIAMOND SPONSOR"
        – the tier's logos centred below it, scaled to that tier's size
      Each tier is laid out across the FULL width, so its logos always reach
      the tier's target size — the more important the tier, the bigger.
    · Secondary groups (Media Partner, Host, …) — small, after the sponsors.
    · Speaker logos — smallest, under a full-width "CONFIRMED SPEAKERS" bar.

Logo sizing
───────────
  Each logo is first TRIMMED of its surrounding white / transparent margin so
  only the real artwork counts, then scaled to EQUAL VISUAL AREA within its
  tier (geometric-mean normalisation). So a wide wordmark and a square badge end
  up looking similarly prominent, instead of the wide one dwarfing the square.

Output
──────
  Every wall is produced as PNG, PDF and a fully-editable PPTX (each logo is a
  separate movable picture, each label a real text box) — all from one shared
  layout plan, so the three formats match pixel-for-pixel.

Public API:
  generate(event, tiers, secondary, speakers, theme, language, renmad_logo) -> PNG bytes
  generate_pack(...)          -> {"png": bytes, "pdf": bytes, "pptx": bytes}
  generate_all_variants(...)  -> {"es": pack, "en": pack}
"""

import io
import math
from PIL import Image, ImageDraw, ImageChops

# ── Canvas ────────────────────────────────────────────────────────────────────
W = 1920

# ── Layout constants ──────────────────────────────────────────────────────────
H_ACCENT          = 8     # top theme-colour accent line height
PAD_X             = 60    # outer left / right margin
TOP_PAD           = 36    # space under the accent line
BOTTOM_PAD        = 48    # space at the very bottom
RENMAD_H          = 76    # RENMAD logo height
GAP_AFTER_RENMAD  = 44    # space below the RENMAD logo
LABEL_GAP         = 14    # space between a tier label and its logos
GROUP_GAP         = 50    # vertical space between tier groups
GAP_X             = 46    # horizontal gap between logos in a row
ROW_GAP           = 26    # vertical gap between wrapped logo rows

# ── Size hierarchy ──────────────────────────────────────────────────────────--
# A "nominal size" is assigned to each PRESENT tier, in importance order (not by
# absolute rank). The top present tier is always the biggest (Diamond if there,
# else the highest tier present) and each next tier steps down hard.
# The nominal size is the geometric-mean side a logo is normalised to, so all
# logos in a tier share roughly the same visual AREA regardless of aspect ratio.
H_FIRST_TIER = 230    # nominal size of the most important present tier
TIER_RATIO   = 0.5    # each next tier ≈ half the size (≈ 1/4 the area)
H_TIER_MIN   = 60     # floor so low tiers stay legible
H_SEC        = 52     # secondary groups (Media Partner, Host, …) — small
H_SPK        = 48     # speaker logos — smallest

# Per-logo caps, as multiples of the tier's nominal size, so an extreme aspect
# ratio can't blow a logo up vertically or horizontally.
H_CAP_MULT   = 1.30   # max height  = nominal * this
W_CAP_MULT   = 3.40   # max width   = nominal * this

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = (255, 255, 255)   # white canvas
TEXT_WHITE  = (255, 255, 255)
SEC_LABEL   = (105, 105, 120)   # grey label for secondary groups

# ── Tier system ───────────────────────────────────────────────────────────────
TIER_ORDER = ["diamond", "platinum", "global", "gold", "silver", "bronze", "standard", "sponsor"]

# ── Speaker section ───────────────────────────────────────────────────────────
SPK_HDR_H   = 72
SPK_PAD_Y   = 28

_SPK_LABEL = {
    "es": "PONENTES CONFIRMADOS",
    "en": "CONFIRMED SPEAKERS",
    "it": "RELATORI CONFERMATI",
    "pl": "POTWIERDZENI PRELEGENCI",
}

# ── Scratch surface for measuring text ──────────────────────────────────────--
_SCRATCH   = Image.new("RGB", (8, 8))
_SCRATCH_D = ImageDraw.Draw(_SCRATCH)

# Pixels → EMU (PowerPoint), at 96 dpi
_PX_EMU = 9525


# ── Font helper ───────────────────────────────────────────────────────────────
def _f(name, size):
    from utils.fonts import get
    return get(
        {"heavy": "montserrat-black",
         "bold":  "montserrat-bold",
         "reg":   "inter"}.get(name, "inter"),
        size,
    )


def _text_size(text: str, font) -> tuple[int, int]:
    b = _SCRATCH_D.textbbox((0, 0), text, font=font)
    return b[2] - b[0], b[3] - b[1]


# ── Tier helpers ──────────────────────────────────────────────────────────────
def _tier_rank(name: str) -> int:
    """0 = diamond (highest / largest), 7 = sponsor (smallest)."""
    lower = (name or "").lower()
    for i, t in enumerate(TIER_ORDER):
        if t in lower:
            return i
    return 7


def _tier_sizes(n: int) -> list[int]:
    """Staircase of nominal sizes for the n present tiers (biggest first)."""
    out, h = [], float(H_FIRST_TIER)
    for _ in range(n):
        out.append(max(H_TIER_MIN, int(round(h))))
        h = h * TIER_RATIO
    return out


# ── Logo helpers ──────────────────────────────────────────────────────────────
def _trim(img: Image.Image) -> Image.Image:
    """Crop away the surrounding margin so only the real artwork counts.

    Removes BOTH transparent padding and a solid (typically white) border, which
    is what makes logos look inconsistently sized — a logo with lots of built-in
    whitespace would otherwise be scaled down relative to a tightly-cropped one.
    """
    rgba = img.convert("RGBA")

    # 1) Trim fully-transparent margin first.
    alpha = rgba.split()[3]
    abox = alpha.getbbox()
    if abox:
        rgba = rgba.crop(abox)

    # 2) Trim a solid background border (e.g. white). Composite over white so any
    #    remaining transparency reads as white, then keep only pixels that differ
    #    from white by more than a small threshold (drops anti-alias haloes too).
    try:
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        comp  = Image.alpha_composite(white, rgba).convert("RGB")
        diff  = ImageChops.difference(comp, Image.new("RGB", comp.size, (255, 255, 255)))
        mask  = diff.convert("L").point(lambda p: 255 if p > 18 else 0)
        cbox  = mask.getbbox()
        if cbox:
            cw, ch = cbox[2] - cbox[0], cbox[3] - cbox[1]
            w, h   = rgba.size
            # Guard: only crop if there is sane content (avoids nuking a logo that
            # is genuinely light-on-transparent, which would vanish on white).
            if cw * ch >= 0.015 * w * h:
                rgba = rgba.crop(cbox)
    except Exception:
        pass

    return rgba


def _scale_area(img: Image.Image, nominal: int) -> Image.Image | None:
    """Scale so the logo's geometric-mean side ≈ nominal (→ equal visual area
    across logos), then clamp height/width so extreme aspects stay sane."""
    logo = _trim(img)
    lw, lh = logo.size
    if lw == 0 or lh == 0:
        return None
    s = nominal / math.sqrt(lw * lh)
    s = min(s, (nominal * H_CAP_MULT) / lh, (nominal * W_CAP_MULT) / lw)
    nw, nh = max(1, int(round(lw * s))), max(1, int(round(lh * s)))
    return logo.resize((nw, nh), Image.LANCZOS)


def _scale_h(img: Image.Image, target_h: int, max_w: int) -> Image.Image | None:
    """Plain height-based scale (used for the single RENMAD wordmark)."""
    logo = _trim(img)
    lw, lh = logo.size
    if lh == 0 or lw == 0:
        return None
    s = min(target_h / lh, max_w / lw)
    return logo.resize((max(1, int(lw * s)), max(1, int(lh * s))), Image.LANCZOS)


def _paste(canvas: Image.Image, logo: Image.Image, x: int, y: int) -> None:
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")
    canvas.paste(logo, (x, y), mask=logo)


# ── Row layout ──────────────────────────────────────────────────────────────--
def _layout_rows(logos: list, nominal: int, usable_w: int) -> list:
    """Equal-area-scale every logo and wrap into rows that fit usable_w."""
    scaled = []
    for lg in logos:
        try:
            s = _scale_area(lg, nominal)
            if s:
                scaled.append(s)
        except Exception:
            pass
    if not scaled:
        return []

    rows, cur, cur_w = [], [], 0
    for s in scaled:
        need = s.width + (GAP_X if cur else 0)
        if cur and cur_w + need > usable_w:
            rows.append(cur)
            cur, cur_w = [s], s.width
        else:
            cur.append(s)
            cur_w += need
    if cur:
        rows.append(cur)
    return rows


# ── Build the ordered list of sponsor groups ──────────────────────────────────
def _build_groups(tiers: list, secondary: list) -> list:
    active_tiers = [t for t in (tiers or []) if t.get("logos")]
    active_tiers.sort(key=lambda t: _tier_rank(t.get("name", "")))
    sizes = _tier_sizes(len(active_tiers))

    groups = []
    for tier, sz in zip(active_tiers, sizes):
        groups.append({
            "kind":   "tier",
            "name":   (tier.get("name", "") or "").upper(),
            "logos":  tier["logos"],
            "nominal": sz,
        })
    for grp in (secondary or []):
        if not grp.get("logos"):
            continue
        groups.append({
            "kind":   "secondary",
            "name":   (grp.get("name", "") or "").upper(),
            "logos":  grp["logos"],
            "nominal": H_SEC,
        })
    return groups


# ── Layout plan (shared by every output format) ───────────────────────────────
def _add_logo_rows(elements: list, rows: list, y: int) -> int:
    for row in rows:
        row_w = sum(s.width for s in row) + GAP_X * (len(row) - 1)
        row_h = max(s.height for s in row)
        x = (W - row_w) // 2
        for s in row:
            elements.append({"type": "image", "img": s,
                             "x": x, "y": y + (row_h - s.height) // 2,
                             "w": s.width, "h": s.height})
            x += s.width + GAP_X
        y += row_h + ROW_GAP
    return (y - ROW_GAP) if rows else y


def _build_plan(event, tiers, secondary, speakers, theme, language, renmad_logo) -> dict:
    theme_rgb = tuple(theme["rgb"])
    usable_w  = W - PAD_X * 2
    elements  = []

    # Top accent line
    elements.append({"type": "rect", "x": 0, "y": 0, "w": W, "h": H_ACCENT, "color": theme_rgb})

    y = H_ACCENT + TOP_PAD

    # RENMAD logo, centred
    if renmad_logo:
        rs = _scale_h(renmad_logo, RENMAD_H, int(RENMAD_H * 5))
        if rs:
            elements.append({"type": "image", "img": rs,
                             "x": (W - rs.width) // 2, "y": y, "w": rs.width, "h": rs.height})
            y += rs.height + GAP_AFTER_RENMAD

    # Sponsor / partner tiers, biggest first
    groups = _build_groups(tiers, secondary)
    for gi, g in enumerate(groups):
        if g["name"]:
            font_role = "heavy" if g["kind"] == "tier" else "bold"
            font_size = 28 if g["kind"] == "tier" else 22
            th = _text_size(g["name"], _f(font_role, font_size))[1]
            colour = theme_rgb if g["kind"] == "tier" else SEC_LABEL
            elements.append({"type": "label", "text": g["name"], "y": y,
                             "font": font_role, "size": font_size, "color": colour})
            y += th + LABEL_GAP
        rows = _layout_rows(g["logos"], g["nominal"], usable_w)
        y = _add_logo_rows(elements, rows, y)
        if gi < len(groups) - 1:
            y += GROUP_GAP
    if not groups:
        y += 40

    # Speakers
    active_spk = [s for s in (speakers or []) if s.get("logos")]
    spk_logos  = [lg for s in active_spk for lg in s.get("logos", [])]
    spk_rows   = _layout_rows(spk_logos, H_SPK, usable_w) if spk_logos else []
    if spk_rows:
        y += GROUP_GAP
        elements.append({"type": "barlabel",
                         "text": _SPK_LABEL.get(language, _SPK_LABEL["en"]),
                         "y": y, "barh": SPK_HDR_H, "font": "heavy", "size": 28,
                         "color": TEXT_WHITE, "barcolor": theme_rgb})
        y += SPK_HDR_H + SPK_PAD_Y
        y = _add_logo_rows(elements, spk_rows, y)
        y += SPK_PAD_Y

    canvas_h = max(120, y + BOTTOM_PAD)
    return {"canvas_h": canvas_h, "elements": elements, "theme_rgb": theme_rgb}


# ── Renderer: raster image (PNG / PDF source) ─────────────────────────────────
def _render_image(plan: dict) -> Image.Image:
    canvas = Image.new("RGB", (W, plan["canvas_h"]), BG)
    draw   = ImageDraw.Draw(canvas)
    for el in plan["elements"]:
        t = el["type"]
        if t == "rect":
            draw.rectangle([el["x"], el["y"], el["x"] + el["w"], el["y"] + el["h"]],
                           fill=el["color"])
        elif t == "image":
            _paste(canvas, el["img"], el["x"], el["y"])
        elif t == "label":
            f = _f(el["font"], el["size"])
            tw = _text_size(el["text"], f)[0]
            draw.text(((W - tw) // 2, el["y"]), el["text"], font=f, fill=el["color"])
        elif t == "barlabel":
            draw.rectangle([0, el["y"], W, el["y"] + el["barh"]], fill=el["barcolor"])
            f = _f(el["font"], el["size"])
            tw, th = _text_size(el["text"], f)
            draw.text(((W - tw) // 2, el["y"] + (el["barh"] - th) // 2),
                      el["text"], font=f, fill=el["color"])
    return canvas


# ── Renderer: fully-editable PPTX ─────────────────────────────────────────────
def _render_pptx(plan: dict) -> bytes:
    from pptx import Presentation
    from pptx.util import Emu, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE

    prs = Presentation()
    prs.slide_width  = Emu(W * _PX_EMU)
    prs.slide_height = Emu(plan["canvas_h"] * _PX_EMU)
    slide = prs.slides.add_slide(prs.slide_layouts[6])   # blank

    # White slide background
    try:
        bg = slide.background
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(255, 255, 255)
    except Exception:
        pass

    def _rect(x, y, w, h, rgb):
        sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                    Emu(x * _PX_EMU), Emu(y * _PX_EMU),
                                    Emu(w * _PX_EMU), Emu(h * _PX_EMU))
        sh.fill.solid()
        sh.fill.fore_color.rgb = RGBColor(*rgb)
        sh.line.fill.background()
        try:
            sh.shadow.inherit = False
        except Exception:
            pass
        return sh

    def _label(text, y, h, size, rgb, anchor_middle=False):
        tb = slide.shapes.add_textbox(Emu(PAD_X * _PX_EMU), Emu(y * _PX_EMU),
                                      Emu((W - PAD_X * 2) * _PX_EMU), Emu(h * _PX_EMU))
        tf = tb.text_frame
        tf.word_wrap = False
        tf.margin_top = tf.margin_bottom = tf.margin_left = tf.margin_right = 0
        if anchor_middle:
            try:
                tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            except Exception:
                pass
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = text
        r.font.bold = True
        r.font.size = Pt(size * 0.75)        # px → pt
        r.font.name = "Montserrat"
        r.font.color.rgb = RGBColor(*rgb)

    for el in plan["elements"]:
        t = el["type"]
        if t == "rect":
            _rect(el["x"], el["y"], el["w"], el["h"], el["color"])
        elif t == "image":
            b = io.BytesIO()
            el["img"].convert("RGBA").save(b, "PNG")
            b.seek(0)
            slide.shapes.add_picture(b, Emu(el["x"] * _PX_EMU), Emu(el["y"] * _PX_EMU),
                                     Emu(el["w"] * _PX_EMU), Emu(el["h"] * _PX_EMU))
        elif t == "label":
            _label(el["text"], el["y"], int(el["size"] * 1.6), el["size"], el["color"])
        elif t == "barlabel":
            _rect(0, el["y"], W, el["barh"], el["barcolor"])
            _label(el["text"], el["y"], el["barh"], el["size"], el["color"], anchor_middle=True)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────
def generate(
    event:       dict,
    tiers:       list,
    secondary:   list,
    speakers:    list,
    theme:       dict,
    language:    str = "es",
    renmad_logo: Image.Image | None = None,
) -> bytes:
    """Back-compat: return the PNG bytes only."""
    plan = _build_plan(event, tiers, secondary, speakers, theme, language, renmad_logo)
    buf = io.BytesIO()
    _render_image(plan).save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


def generate_pack(
    event:       dict,
    tiers:       list,
    secondary:   list,
    speakers:    list,
    theme:       dict,
    language:    str = "es",
    renmad_logo: Image.Image | None = None,
) -> dict:
    """Return {"png": bytes, "pdf": bytes, "pptx": bytes} for one language."""
    plan = _build_plan(event, tiers, secondary, speakers, theme, language, renmad_logo)
    img  = _render_image(plan)

    png = io.BytesIO()
    img.save(png, format="PNG", dpi=(150, 150))

    pdf = io.BytesIO()
    img.convert("RGB").save(pdf, format="PDF", resolution=150.0)

    out = {"png": png.getvalue(), "pdf": pdf.getvalue()}
    try:
        out["pptx"] = _render_pptx(plan)
    except Exception:
        out["pptx"] = None   # PPTX is best-effort; PNG/PDF always available
    return out


def generate_all_variants(
    event:       dict,
    tiers:       list,
    secondary:   list,
    speakers:    list,
    theme:       dict,
    language:    str = "es",
    renmad_logo: Image.Image | None = None,
) -> dict:
    """Generate ES and EN packs. Returns {"es": pack, "en": pack}."""
    return {
        lang: generate_pack(
            event=event, tiers=tiers, secondary=secondary,
            speakers=speakers, theme=theme, language=lang,
            renmad_logo=renmad_logo,
        )
        for lang in ("es", "en")
    }
