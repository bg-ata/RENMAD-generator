"""T_Logowall — Event logo wall / footer  1920 px wide, dynamic height

Layout
──────
  WHITE background throughout.

  TOP section:
    · 5 px theme-colour accent line across full width
    · Columns (left → right): RENMAD | secondary groups | main tier groups
        – Each column: coloured header band (theme for tiers, grey for secondary)
          with bold white label text
        – Logos centred below the header, scaled by tier importance
        – Light grey vertical divider between columns
    · RENMAD column (optional): far left, no header, logo vertically centred

  BOTTOM section (optional):
    · Full-width theme-colour "CONFIRMED SPEAKERS" bar
    · Speaker logos on white, centred

Public API:
  generate(event, tiers, secondary, speakers, theme, language, renmad_logo) -> bytes
  generate_all_variants(...)                                                  -> dict
"""

import io
import math
from PIL import Image, ImageDraw

# ── Canvas ────────────────────────────────────────────────────────────────────
W = 1920

# ── Layout constants ──────────────────────────────────────────────────────────
H_ACCENT  = 8     # top theme-colour accent line height
H_HEADER  = 66    # coloured label band height
PAD_X     = 40    # outer left / right margin
COL_PAD   = 24    # horizontal padding inside each column (total L+R)
PAD_Y     = 32    # vertical padding above/below logos in a column
GAP_X     = 24    # horizontal gap between logos in a row
ROW_GAP   = 18    # vertical gap between wrapped logo rows

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = (255, 255, 255)   # white canvas
DIVIDER     = (210, 210, 218)   # light grey column dividers
SEC_HDR     = (105, 105, 120)   # grey header for secondary columns
TEXT_WHITE  = (255, 255, 255)

# ── Tier system ───────────────────────────────────────────────────────────────
TIER_ORDER = ["diamond", "platinum", "global", "gold", "silver", "bronze", "standard", "sponsor"]

# Logo target height per tier rank (0 = diamond/biggest → 7 = sponsor/smallest)
_TIER_LOGO_H = [190, 165, 145, 125, 105, 88, 75, 65]

# Column width weight per tier rank (higher tier → wider column)
_TIER_WEIGHT = [2.0, 1.8, 1.6, 1.4, 1.2, 1.0, 0.9, 0.85]

# Secondary groups (Media Partner, Host, Co-Host, …)
SEC_LOGO_H = 72
SEC_WEIGHT = 0.75

# ── Speaker section ───────────────────────────────────────────────────────────
SPK_HDR_H   = 90
SPK_H       = 72
SPK_MAX_W   = 160
SPK_GAP     = 32
SPK_ROW_GAP = 20
SPK_PAD_Y   = 24

_SPK_LABEL = {
    "es": "PONENTES CONFIRMADOS",
    "en": "CONFIRMED SPEAKERS",
    "it": "RELATORI CONFERMATI",
    "pl": "POTWIERDZENI PRELEGENCI",
}


# ── Font helper ───────────────────────────────────────────────────────────────
def _f(name, size):
    from utils.fonts import get
    return get(
        {"heavy": "montserrat-black",
         "bold":  "montserrat-bold",
         "reg":   "inter"}.get(name, "inter"),
        size,
    )


# ── Tier helpers ──────────────────────────────────────────────────────────────
def _tier_rank(name: str) -> int:
    """0 = diamond (highest / largest), 7 = sponsor (smallest)."""
    lower = (name or "").lower()
    for i, t in enumerate(TIER_ORDER):
        if t in lower:
            return i
    return 7


def _logo_h_for_col(col: dict) -> int:
    if col["kind"] == "secondary":
        return SEC_LOGO_H
    return _TIER_LOGO_H[min(col["rank"], len(_TIER_LOGO_H) - 1)]


# ── Logo helpers ──────────────────────────────────────────────────────────────
def _trim(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    bbox = rgba.split()[3].getbbox()
    return rgba.crop(bbox) if bbox else rgba


def _scale(img: Image.Image, target_h: int, max_w: int) -> Image.Image | None:
    logo = _trim(img)
    lw, lh = logo.size
    if lh == 0 or lw == 0:
        return None
    s = min(target_h / lh, max_w / lw)
    nw, nh = max(1, int(lw * s)), max(1, int(lh * s))
    return logo.resize((nw, nh), Image.LANCZOS)


def _paste(canvas: Image.Image, logo: Image.Image, x: int, y: int) -> None:
    if logo.mode != "RGBA":
        logo = logo.convert("RGBA")
    canvas.paste(logo, (x, y), mask=logo)


# ── Column layout helpers ─────────────────────────────────────────────────────
def _fit_logos_in_column(logos: list, target_h: int, max_w: int, inner_w: int) -> list:
    scaled = []
    for lg in logos:
        try:
            s = _scale(lg, target_h, max_w)
            if s:
                scaled.append(s)
        except Exception:
            pass
    if not scaled:
        return []

    rows, cur_row, cur_w = [], [], 0
    for s in scaled:
        needed = s.width + (GAP_X if cur_row else 0)
        if cur_row and cur_w + needed > inner_w:
            rows.append(cur_row)
            cur_row, cur_w = [s], s.width
        else:
            cur_row.append(s)
            cur_w += needed
    if cur_row:
        rows.append(cur_row)
    return rows


def _column_logos_height(rows: list) -> int:
    if not rows:
        return 0
    total = 0
    for i, row in enumerate(rows):
        total += max((s.height for s in row), default=0)
        if i < len(rows) - 1:
            total += ROW_GAP
    return total


# ── Column width computation ───────────────────────────────────────────────────
def _compute_col_widths(
    renmad_logo,
    secondary: list,
    tiers: list,
    renmad_logo_w: int,
) -> tuple[int, list[dict]]:
    active_sec   = [g for g in (secondary or []) if g.get("logos")]
    active_tiers = [t for t in (tiers or []) if t.get("logos")]

    renmad_col_w = (renmad_logo_w + COL_PAD) if renmad_logo_w > 0 else 0
    avail_w      = W - PAD_X * 2 - renmad_col_w

    columns, weights = [], []

    for grp in active_sec:
        columns.append({
            "kind":  "secondary",
            "rank":  99,
            "name":  grp.get("name", ""),
            "logos": grp["logos"],
        })
        weights.append(SEC_WEIGHT)

    for tier in active_tiers:
        rank = _tier_rank(tier.get("name", ""))
        columns.append({
            "kind":  "tier",
            "rank":  rank,
            "name":  tier.get("name", ""),
            "logos": tier["logos"],
        })
        weights.append(_TIER_WEIGHT[min(rank, len(_TIER_WEIGHT) - 1)])

    if not columns:
        return renmad_col_w, []

    total_w   = sum(weights)
    col_widths = [max(80, int(avail_w * w / total_w)) for w in weights]
    # Give rounding remainder to the last column
    col_widths[-1] += avail_w - sum(col_widths)

    for col, cw in zip(columns, col_widths):
        col["col_w"] = cw

    return renmad_col_w, columns


# ── Strip height computation ───────────────────────────────────────────────────
def _compute_strip_h(columns: list) -> int:
    """Compute the height of the sponsor strip from the tallest column."""
    max_logos_h = 0
    for col in columns:
        logo_h  = _logo_h_for_col(col)
        inner_w = max(10, col["col_w"] - COL_PAD)
        max_w   = min(int(logo_h * 3.5), inner_w - 4)
        rows    = _fit_logos_in_column(col["logos"], logo_h, max_w, inner_w)
        max_logos_h = max(max_logos_h, _column_logos_height(rows))

    return H_ACCENT + H_HEADER + PAD_Y + max(max_logos_h, 40) + PAD_Y


# ── Renderer: sponsor strip ───────────────────────────────────────────────────
def _draw_strip(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    theme_rgb: tuple,
    columns: list,
    renmad_col_w: int,
    renmad_scaled: Image.Image | None,
    strip_h: int,
) -> None:
    # Top accent line + full-width header band in one pass
    draw.rectangle([0, 0, W, H_ACCENT], fill=theme_rgb)
    draw.rectangle([0, H_ACCENT, W, H_ACCENT + H_HEADER], fill=theme_rgb)

    header_f = _f("heavy", 28)
    x = PAD_X

    # RENMAD column — no label text, just logo below the band
    if renmad_scaled and renmad_col_w > 0:
        logo_area_top = H_ACCENT + H_HEADER + PAD_Y
        logo_area_h   = strip_h - logo_area_top - PAD_Y
        rx = x + (renmad_col_w - renmad_scaled.width) // 2
        ry = logo_area_top + max(0, (logo_area_h - renmad_scaled.height) // 2)
        _paste(canvas, renmad_scaled, rx, ry)
        x += renmad_col_w

    for col_idx, col in enumerate(columns):
        col_w  = col["col_w"]
        logo_h = _logo_h_for_col(col)
        name   = col["name"].upper()

        # (band already drawn full-width above)

        # Label text, centred in header band — shrink font if too wide
        if name:
            try:
                max_text_w = col_w - 16
                f = header_f
                for size in range(28, 9, -2):
                    f = _f("heavy", size)
                    lb = draw.textbbox((0, 0), name, font=f)
                    if lb[2] <= max_text_w:
                        break
                lb = draw.textbbox((0, 0), name, font=f)
                tx = x + (col_w - lb[2]) // 2
                ty = H_ACCENT + (H_HEADER - lb[3]) // 2
                draw.text((tx, ty), name, font=f, fill=TEXT_WHITE)
            except Exception:
                pass

        # Logos
        logo_top = H_ACCENT + H_HEADER + PAD_Y
        logo_bot = strip_h - PAD_Y
        inner_w  = max(10, col_w - COL_PAD)
        max_w    = min(int(logo_h * 3.5), inner_w - 4)

        rows = _fit_logos_in_column(col["logos"], logo_h, max_w, inner_w)

        if rows:
            total_h  = _column_logos_height(rows)
            area_h   = max(10, logo_bot - logo_top)
            y_block  = logo_top + max(0, (area_h - total_h) // 2)

            for row in rows:
                row_w = sum(s.width for s in row) + GAP_X * (len(row) - 1)
                row_h = max(s.height for s in row)
                lx    = x + (col_w - row_w) // 2
                for sl in row:
                    _paste(canvas, sl, lx, y_block + (row_h - sl.height) // 2)
                    lx += sl.width + GAP_X
                y_block += row_h + ROW_GAP

        x += col_w


# ── Renderer: speaker section ─────────────────────────────────────────────────
def _draw_speakers(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    theme_rgb: tuple,
    speakers: list,
    strip_h: int,
    language: str,
    canvas_h: int,
) -> None:
    # Full-width theme-colour header bar
    draw.rectangle([0, strip_h, W, strip_h + SPK_HDR_H], fill=theme_rgb)

    label   = _SPK_LABEL.get(language, _SPK_LABEL["en"])
    label_f = _f("heavy", 28)
    try:
        lb = draw.textbbox((0, 0), label, font=label_f)
        lx = (W - lb[2]) // 2
        ly = strip_h + (SPK_HDR_H - lb[3]) // 2
        draw.text((lx, ly), label, font=label_f, fill=TEXT_WHITE)
    except Exception:
        pass

    # Collect + scale speaker logos
    all_logos = [lg for spk in speakers for lg in spk.get("logos", [])]
    scaled    = [s for lg in all_logos for s in [_scale(lg, SPK_H, SPK_MAX_W)] if s]

    if not scaled:
        return

    grid_top = strip_h + SPK_HDR_H + SPK_PAD_Y
    usable_w = W - PAD_X * 2
    total_w  = sum(s.width for s in scaled) + SPK_GAP * (len(scaled) - 1)
    n_rows   = max(1, math.ceil(total_w / usable_w))
    per_row  = math.ceil(len(scaled) / n_rows)

    rows   = [scaled[i:i + per_row] for i in range(0, len(scaled), per_row)]
    row_h  = max((s.height for s in scaled), default=SPK_H)
    total_block_h = len(rows) * row_h + (len(rows) - 1) * SPK_ROW_GAP
    area_h        = max(10, canvas_h - grid_top - SPK_PAD_Y)
    y             = grid_top + max(0, (area_h - total_block_h) // 2)

    for row in rows:
        rw = sum(s.width for s in row) + SPK_GAP * (len(row) - 1)
        xc = (W - rw) // 2
        for sl in row:
            _paste(canvas, sl, xc, y + (row_h - sl.height) // 2)
            xc += sl.width + SPK_GAP
        y += row_h + SPK_ROW_GAP


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
    theme_rgb = tuple(theme["rgb"])

    # Pre-scale RENMAD logo to get its column width
    renmad_scaled = None
    renmad_logo_w = 0
    if renmad_logo:
        try:
            rl_h          = 60
            renmad_scaled = _scale(renmad_logo, rl_h, int(rl_h * 4))
            if renmad_scaled:
                renmad_logo_w = renmad_scaled.width
        except Exception:
            pass

    renmad_col_w, columns = _compute_col_widths(
        renmad_logo, secondary, tiers, renmad_logo_w
    )

    active_spk    = [s for s in (speakers or []) if s.get("logos")]
    show_speakers = bool(active_spk)

    strip_h = _compute_strip_h(columns) if columns else (H_ACCENT + H_HEADER + 80)

    # Re-scale RENMAD to fit the computed strip height
    if renmad_logo and renmad_logo_w > 0:
        rl_h = min(60, strip_h - H_ACCENT - PAD_Y * 2)
        try:
            renmad_scaled = _scale(renmad_logo, max(20, rl_h), int(rl_h * 4))
        except Exception:
            renmad_scaled = None

    # Speaker section height
    if show_speakers:
        all_spk  = [lg for s in active_spk for lg in s.get("logos", [])]
        spk_sc   = [s for lg in all_spk for s in [_scale(lg, SPK_H, SPK_MAX_W)] if s]
        if spk_sc:
            usable_w     = W - PAD_X * 2
            total_w      = sum(s.width for s in spk_sc) + SPK_GAP * (len(spk_sc) - 1)
            n_rows       = max(1, math.ceil(total_w / usable_w))
            row_h        = max(s.height for s in spk_sc)
            spk_grid_h   = n_rows * row_h + (n_rows - 1) * SPK_ROW_GAP
        else:
            spk_grid_h = SPK_H
        canvas_h = strip_h + SPK_HDR_H + spk_grid_h + SPK_PAD_Y * 2
    else:
        canvas_h = strip_h

    canvas_h = max(80, canvas_h)

    canvas = Image.new("RGB", (W, canvas_h), BG)
    draw   = ImageDraw.Draw(canvas)

    _draw_strip(canvas, draw, theme_rgb, columns, renmad_col_w, renmad_scaled, strip_h)

    if show_speakers:
        _draw_speakers(canvas, draw, theme_rgb, active_spk, strip_h, language, canvas_h)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


def generate_all_variants(
    event:       dict,
    tiers:       list,
    secondary:   list,
    speakers:    list,
    theme:       dict,
    language:    str = "es",
    renmad_logo: Image.Image | None = None,
) -> dict:
    """Generate ES and EN variants. Returns {"es": bytes, "en": bytes}."""
    return {
        lang: generate(
            event=event, tiers=tiers, secondary=secondary,
            speakers=speakers, theme=theme, language=lang,
            renmad_logo=renmad_logo,
        )
        for lang in ("es", "en")
    }
