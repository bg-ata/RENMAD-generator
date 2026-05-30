"""T_Ingo — Event info-graphic (Ingo)  1200 × 630 px

Layout
──────
  LEFT half (0 → SPLIT_X): dark background
    · Thin theme-colour accent line (top)
    · RENMAD logo + theme badge
    · Variant label (white, large, underlined)
    · Event title (white, Montserrat Black, mixed-case, ≤ 3 lines)
    · Date + location bar (theme colour, full width)
    · Stats row (theme-colour numbers, readable light labels)
    · WHITE SPONSOR PANEL (bottom of left half):
        – Main sponsor tiers (logos large, directly on white)
        – Thin separator
        – Secondary logos (Media Partner, Knowledge Partner, Host…)
          also on white — readable, compact row

  RIGHT half (SPLIT_X → 1200): light/white panel
    · Empty circle (subtle border) — placeholder for sharer's photo
    · Space below circle intentionally blank (white) — person's name
      and job title will appear there when the template is used

Variants (all generated at once):
  ""          → plain event
  "ponente"   → PONENTE CONFIRMADO / CONFIRMED SPEAKER / …
  "asistente" → ASISTENTE CONFIRMADO / CONFIRMED ATTENDEE / …
  "patro"     → SPONSOR OFICIAL / OFFICIAL SPONSOR / …
"""

import io, math
from PIL import Image, ImageDraw
from config import LANGUAGE_STRINGS

W, H      = 1200, 630
SPLIT_X   = 648          # divides dark left from white right

# ── Left panel ────────────────────────────────────────────────────────────────
PAD_L     = 32
PAD_T     = 20

# ── Circle (right white panel) ────────────────────────────────────────────────
# Centred in the right half, smaller than before to leave room for name/title below
_R_HALF_CX = SPLIT_X + (W - SPLIT_X) // 2   # horizontal centre of right half  ≈ 924
CIR_CX     = _R_HALF_CX
CIR_CY     = 240          # above vertical centre — leaves ~175 px below for text
CIR_R      = 160          # diameter 320 px (was 220)

# ── Logo sizes ────────────────────────────────────────────────────────────────
TIER_H    = [78, 62, 48, 36, 27]   # main sponsor heights by tier rank
SEC_H     = 28                      # secondary logo height inside white panel
PILL_PAD  = 0                       # logos sit directly on white — no pill needed

# ── Colours ───────────────────────────────────────────────────────────────────
BG_DARK      = (19, 19, 24)
RIGHT_BG     = (247, 247, 249)    # near-white right panel
PANEL_BG     = (255, 255, 255)    # white sponsor panel
WHITE        = (255, 255, 255)
DARK_TEXT    = (18, 18, 22)
LABEL_GREY   = (130, 130, 138)    # tier / secondary labels
DIVIDER_DARK = (48, 48, 56)
DIVIDER_LT   = (215, 215, 220)

_VARIANTS = {
    "es": {"ponente":    "PONENTE CONFIRMADO",
           "asistente":  "ASISTENTE CONFIRMADO",
           "patro":      "SPONSOR OFICIAL"},
    "en": {"ponente":    "CONFIRMED SPEAKER",
           "asistente":  "CONFIRMED ATTENDEE",
           "patro":      "OFFICIAL SPONSOR"},
    "it": {"ponente":    "RELATORE CONFERMATO",
           "asistente":  "PARTECIPANTE CONFERMATO",
           "patro":      "SPONSOR UFFICIALE"},
    "pl": {"ponente":    "POTWIERDZONY PRELEGENT",
           "asistente":  "POTWIERDZONY UCZESTNIK",
           "patro":      "OFICJALNY SPONSOR"},
}

ALL_VARIANTS = ["", "ponente", "asistente", "patro"]


# ── Font helper ────────────────────────────────────────────────────────────────
def _f(name, size):
    from utils.fonts import get
    return get({"heavy": "montserrat-black",
                "bold":  "montserrat-bold",
                "reg":   "inter"}.get(name, "inter"), size)


# ── Logo helpers ───────────────────────────────────────────────────────────────
def _trim(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    bbox = rgba.split()[3].getbbox()
    return rgba.crop(bbox) if bbox else rgba


def _scale(img: Image.Image, target_h: int, max_w: int):
    """Scale logo to fit target_h × max_w. Returns RGBA."""
    logo = _trim(img)
    lw, lh = logo.size
    if lh == 0:
        return None
    s = min(target_h / lh, max_w / max(lw, 1))
    nw, nh = max(1, int(lw * s)), max(1, int(lh * s))
    return logo.resize((nw, nh), Image.LANCZOS)


def _paste(canvas, logo, x, y):
    """Paste RGBA logo onto RGB canvas."""
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")
    canvas.paste(logo, (x, y), mask=logo)


# ── Background ────────────────────────────────────────────────────────────────
def _make_canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(img)
    # subtle gradient on dark side
    for yi in range(H):
        v = int(19 + 5 * math.sin(yi / H * math.pi))
        d.line([(0, yi), (SPLIT_X, yi)], fill=(v, v, v + 4))
    # right white panel
    d.rectangle([SPLIT_X, 0, W, H], fill=RIGHT_BG)
    return img


# ── Main generator ─────────────────────────────────────────────────────────────
def generate(
    event:        dict,
    stats:        list,
    tiers:        list,
    secondary:    list,
    theme:        dict,
    language:     str                = "es",
    renmad_logo:  Image.Image | None = None,
    bg_image:     Image.Image | None = None,
    variant:      str                = "",
) -> bytes:

    theme_rgb = tuple(theme["rgb"])

    canvas = _make_canvas()
    draw   = ImageDraw.Draw(canvas)

    # ── Full-width date bar accent (drawn first, full width) ──────────────────
    # (will be drawn later at the right y position — placeholder)

    # ── Circle on right white panel ───────────────────────────────────────────
    draw.ellipse(
        [CIR_CX - CIR_R, CIR_CY - CIR_R,
         CIR_CX + CIR_R, CIR_CY + CIR_R],
        fill=WHITE,
        outline=theme_rgb,
        width=4,
    )

    # ── Top accent line (left panel only) ─────────────────────────────────────
    draw.rectangle([0, 0, SPLIT_X, 5], fill=theme_rgb)

    y = PAD_T

    # ── RENMAD logo ───────────────────────────────────────────────────────────
    badge_x = PAD_L
    if renmad_logo:
        rl  = renmad_logo.convert("RGBA")
        rh  = 44
        rw  = max(1, int(rl.width * rh / rl.height))
        rl  = rl.resize((rw, rh), Image.LANCZOS)
        _paste(canvas, rl, PAD_L, y)
        badge_x = PAD_L + rw + 14

    # ── Theme badge ───────────────────────────────────────────────────────────
    badge_text = (
        theme.get("label_es") or theme.get("label_en") or theme.get("name", "")
        if language == "es" else
        theme.get("label_en") or theme.get("label_es") or theme.get("name", "")
    ).upper()
    bf   = _f("bold", 14)
    bb   = draw.textbbox((0, 0), badge_text, font=bf)
    bpad = 9
    bw   = bb[2] + bpad * 2
    bh   = bb[3] + bpad
    by   = y + (44 - bh) // 2
    draw.rounded_rectangle([badge_x, by, badge_x + bw, by + bh],
                            radius=5, fill=theme_rgb)
    draw.text((badge_x + bpad, by + bpad // 2), badge_text,
              font=bf, fill=WHITE)

    # ── Variant label (white, large, underlined) ──────────────────────────────
    _variant_own_row = False
    _vtext = ""
    if variant:
        _vtext = _VARIANTS.get(language, _VARIANTS["es"]).get(variant, "")
        if _vtext:
            vf  = _f("bold", 20)
            vbb = draw.textbbox((0, 0), _vtext, font=vf)
            vx  = SPLIT_X - vbb[2] - PAD_L
            if vx - (badge_x + bw) >= 14:
                vy = y + (44 - vbb[3]) // 2
                draw.text((vx, vy), _vtext, font=vf, fill=WHITE)
                draw.line([(vx, vy + vbb[3] + 3),
                           (vx + vbb[2], vy + vbb[3] + 3)],
                          fill=WHITE, width=2)
            else:
                _variant_own_row = True

    y += 58

    if _variant_own_row and _vtext:
        vf  = _f("bold", 20)
        vbb = draw.textbbox((0, 0), _vtext, font=vf)
        draw.text((PAD_L, y), _vtext, font=vf, fill=WHITE)
        draw.line([(PAD_L, y + vbb[3] + 3),
                   (PAD_L + vbb[2], y + vbb[3] + 3)],
                  fill=WHITE, width=2)
        y += vbb[3] + 12

    # ── Event title (white, mixed-case) ───────────────────────────────────────
    title = event.get("title", "")
    if title:
        from utils.text_utils import wrap_title
        tf      = _f("heavy", 48)
        t_lines = wrap_title(draw, title, tf, SPLIT_X - PAD_L - 8, max_lines=3)
        for line in t_lines:
            lb = draw.textbbox((0, 0), line, font=tf)
            draw.text((PAD_L, y), line, font=tf, fill=WHITE)
            y += lb[3] + 4
        y += 8

    # ── Date + location bar (theme colour, left half only — circle on right) ────
    date_str = event.get("date_str", "")
    location = event.get("location", "")
    dt_parts = [p for p in (date_str, location) if p]
    if dt_parts:
        bar_h   = 34
        dt_text = "  ·  ".join(dt_parts)
        dt_f    = _f("bold", 18)
        draw.rectangle([0, y, SPLIT_X, y + bar_h], fill=theme_rgb)
        dt_bb = draw.textbbox((0, 0), dt_text, font=dt_f)
        draw.text((PAD_L, y + (bar_h - dt_bb[3]) // 2),
                  dt_text, font=dt_f, fill=WHITE)
        y += bar_h + 14

    # ── Stats row (on dark, theme-colour numbers, readable labels) ────────────
    if stats:
        from utils.icons import people, speaker, clock
        icon_fns   = [people, speaker, clock]
        icon_size  = 30
        num_f      = _f("heavy", 27)
        lab_f      = _f("bold", 12)     # was 10 — now bigger and readable
        stat_col_w = (SPLIT_X - PAD_L) // 3
        row_h      = 0
        for idx, stat in enumerate(stats[:3]):
            sx       = PAD_L + idx * stat_col_w
            icon_img = icon_fns[idx](icon_size, theme_rgb)
            _paste(canvas, icon_img, sx, y)
            num_text = stat.get("num", "")
            nb       = draw.textbbox((0, 0), num_text, font=num_f)
            ix       = sx + icon_size + 7
            draw.text((ix, y + (icon_size - nb[3]) // 2),
                      num_text, font=num_f, fill=theme_rgb)
            lab_text = stat.get("label", "").upper()
            lb2      = draw.textbbox((0, 0), lab_text, font=lab_f)
            draw.text((ix, y + icon_size - lb2[3] // 2 + 2),
                      lab_text, font=lab_f, fill=(185, 185, 192))
            row_h = max(row_h, icon_size + lb2[3] + 4)
        y += row_h + 10

    # ── WHITE SPONSOR PANEL (left half, bottom) ───────────────────────────────
    panel_top = y + 8
    panel_bot = H - 8
    draw.rectangle([0, panel_top, SPLIT_X, panel_bot], fill=PANEL_BG)

    y = panel_top + 10

    # Main sponsor tiers
    active_tiers = [t for t in tiers if t.get("logos")]
    n_active     = len(active_tiers)

    # Secondary logos to embed at the bottom of the panel
    active_sec = [g for g in secondary if g.get("logos")]
    # Reserve space at panel bottom for secondary logos if any
    sec_reserve = (SEC_H + 20 + 14) if active_sec else 0

    tier_f = _f("bold", 11)    # was 10 — slightly bigger

    if active_tiers:
        avail  = panel_bot - y - 4 - sec_reserve - (n_active * 17) - (n_active * 8)
        needed = sum(TIER_H[:n_active])
        scale  = min(1.0, avail / max(needed, 1))
        actual_h = [max(20, int(TIER_H[min(i, len(TIER_H) - 1)] * scale))
                    for i in range(n_active)]

        for tier, logo_h in zip(active_tiers, actual_h):
            t_name = tier.get("name", "").upper()
            if t_name:
                draw.text((PAD_L, y), t_name, font=tier_f, fill=LABEL_GREY)
                y += 16

            n_logos    = max(len(tier["logos"]), 1)
            max_logo_w = min(
                int(logo_h * 4.5),
                (SPLIT_X - PAD_L - (n_logos - 1) * 16) // n_logos,
            )
            x_cur  = PAD_L
            row_h2 = 0
            scaled = []
            for logo_img in tier["logos"]:
                try:
                    s = _scale(logo_img, logo_h, max_logo_w)
                    if s:
                        scaled.append(s)
                        row_h2 = max(row_h2, s.height)
                except Exception:
                    pass

            for sl in scaled:
                if x_cur + sl.width > SPLIT_X - 4:
                    break
                _paste(canvas, sl, x_cur, y + (row_h2 - sl.height) // 2)
                x_cur += sl.width + 16

            y += row_h2 + 8
            if y > panel_bot - sec_reserve - 20:
                break

    # ── Secondary logos inside the white panel (bottom strip) ─────────────────
    if active_sec:
        sep_y = panel_bot - sec_reserve + 4
        draw.line([(PAD_L, sep_y), (SPLIT_X - PAD_L, sep_y)],
                  fill=DIVIDER_LT, width=1)
        sy     = sep_y + 10
        sx_cur = PAD_L
        sec_name_f = _f("bold", 10)   # was 9

        for grp in active_sec:
            g_name = grp.get("name", "").upper()
            if g_name:
                nb = draw.textbbox((0, 0), g_name, font=sec_name_f)
                # Estimate group width to wrap if needed
                est = nb[2] + 7 + len(grp["logos"]) * 80
                if sx_cur > PAD_L and sx_cur + est > SPLIT_X - PAD_L:
                    sx_cur = PAD_L
                    sy    += SEC_H + 10
                draw.text((sx_cur, sy + (SEC_H - nb[3]) // 2),
                          g_name, font=sec_name_f, fill=LABEL_GREY)
                sx_cur += nb[2] + 7

            for logo_img in grp["logos"]:
                try:
                    s = _scale(logo_img, SEC_H, 90)
                    if s:
                        _paste(canvas, s, sx_cur, sy + (SEC_H - s.height) // 2)
                        sx_cur += s.width + 8
                except Exception:
                    pass
            sx_cur += 14

    # ── Output ────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


def generate_all_variants(
    event:        dict,
    stats:        list,
    tiers:        list,
    secondary:    list,
    theme:        dict,
    language:     str                = "es",
    renmad_logo:  Image.Image | None = None,
) -> dict:
    """Generate all 4 Ingo variants. Returns {variant_key: png_bytes}."""
    return {v: generate(event=event, stats=stats, tiers=tiers,
                        secondary=secondary, theme=theme, language=language,
                        renmad_logo=renmad_logo, bg_image=None, variant=v)
            for v in ALL_VARIANTS}
