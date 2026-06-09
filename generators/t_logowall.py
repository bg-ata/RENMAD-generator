"""T_Logowall — Event logo wall  1920 px wide, dynamic height

Layout  (stacked rows, biggest at the top)
──────────────────────────────────────────
  WHITE background throughout.

    · 8 px theme-colour accent line across the top
    · RENMAD logo, centred (optional)
    · One ROW PER SPONSOR TIER, most important first:
        – small centred tier label (theme colour) e.g. "DIAMOND SPONSOR"
        – the tier's logos centred below it, scaled to that tier's height
      Each tier is laid out across the FULL width, so its logos always reach
      the tier's target height — the more important the tier, the bigger.
      Rough size hierarchy: each tier is ~half the height (≈4× the area) of the
      tier below it, so Diamond towers over Gold towers over a plain Sponsor.
    · Secondary groups (Media Partner, Host, …) — small, after the sponsors.
    · Speaker logos — smallest, under a full-width "CONFIRMED SPEAKERS" bar.

Public API:
  generate(event, tiers, secondary, speakers, theme, language, renmad_logo) -> bytes
  generate_all_variants(...)                                                  -> dict
"""

import io
from PIL import Image, ImageDraw

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
# Heights are assigned to the tiers that are ACTUALLY PRESENT, in importance
# order — not by absolute rank. So the top present tier is always the biggest
# (Diamond if present, otherwise the highest tier there is) and each subsequent
# tier steps down hard.
H_FIRST_TIER = 260    # logo height of the most important present tier
TIER_RATIO   = 0.5    # each next tier ≈ half the height (≈ 1/4 the area)
H_TIER_MIN   = 64     # floor so low tiers stay legible
H_SEC        = 54     # secondary groups (Media Partner, Host, …) — small
H_SPK        = 50     # speaker logos — smallest

# ── Colours ───────────────────────────────────────────────────────────────────
BG          = (255, 255, 255)   # white canvas
TEXT_WHITE  = (255, 255, 255)
SEC_LABEL   = (105, 105, 120)   # grey label for secondary groups

# ── Tier system ───────────────────────────────────────────────────────────────
TIER_ORDER = ["diamond", "platinum", "global", "gold", "silver", "bronze", "standard", "sponsor"]

# ── Speaker section ───────────────────────────────────────────────────────────
SPK_HDR_H   = 72
SPK_MAX_W   = 150
SPK_GAP     = 36
SPK_ROW_GAP = 22
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


def _tier_heights(n: int) -> list[int]:
    """Staircase of logo heights for the n present tiers (biggest first)."""
    out, h = [], float(H_FIRST_TIER)
    for _ in range(n):
        out.append(max(H_TIER_MIN, int(round(h))))
        h = h * TIER_RATIO
    return out


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


# ── Row layout ──────────────────────────────────────────────────────────────--
def _layout_rows(logos: list, target_h: int, usable_w: int) -> list:
    """Scale every logo to target_h (capped to the full width) and wrap into
    centred rows that each fit inside usable_w. Returns a list of rows."""
    scaled = []
    for lg in logos:
        try:
            s = _scale(lg, target_h, usable_w)
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


def _rows_block_h(rows: list) -> int:
    if not rows:
        return 0
    total = sum(max(s.height for s in row) for row in rows)
    total += ROW_GAP * (len(rows) - 1)
    return total


def _draw_rows(canvas, rows: list, top: int) -> int:
    """Draw centred rows starting at y=top. Returns the y below the block."""
    y = top
    for row in rows:
        row_w = sum(s.width for s in row) + GAP_X * (len(row) - 1)
        row_h = max(s.height for s in row)
        x = (W - row_w) // 2
        for s in row:
            _paste(canvas, s, x, y + (row_h - s.height) // 2)
            x += s.width + GAP_X
        y += row_h + ROW_GAP
    return y - ROW_GAP if rows else top


# ── Build the ordered list of sponsor groups ──────────────────────────────────
def _build_groups(tiers: list, secondary: list) -> list:
    """Return groups in render order: tiers (by rank) then secondary, each with
    its assigned logo height. Only groups that actually have logos are kept."""
    active_tiers = [t for t in (tiers or []) if t.get("logos")]
    active_tiers.sort(key=lambda t: _tier_rank(t.get("name", "")))
    heights = _tier_heights(len(active_tiers))

    groups = []
    for tier, h in zip(active_tiers, heights):
        groups.append({
            "kind":   "tier",
            "name":   (tier.get("name", "") or "").upper(),
            "logos":  tier["logos"],
            "logo_h": h,
        })
    for grp in (secondary or []):
        if not grp.get("logos"):
            continue
        groups.append({
            "kind":   "secondary",
            "name":   (grp.get("name", "") or "").upper(),
            "logos":  grp["logos"],
            "logo_h": H_SEC,
        })
    return groups


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
    usable_w  = W - PAD_X * 2

    # ── Plan every section (scale logos + measure) so we can size the canvas ──
    renmad_scaled = None
    if renmad_logo:
        try:
            renmad_scaled = _scale(renmad_logo, RENMAD_H, int(RENMAD_H * 5))
        except Exception:
            renmad_scaled = None

    groups = _build_groups(tiers, secondary)
    for g in groups:
        g["rows"]    = _layout_rows(g["logos"], g["logo_h"], usable_w)
        g["block_h"] = _rows_block_h(g["rows"])
        # tier labels are bold theme text; secondary labels are smaller grey
        g["label_font"] = _f("heavy", 28 if g["kind"] == "tier" else 22)
        g["label_h"]    = _text_size(g["name"], g["label_font"])[1] if g["name"] else 0

    active_spk = [s for s in (speakers or []) if s.get("logos")]
    spk_logos  = [lg for s in active_spk for lg in s.get("logos", [])]
    spk_rows   = _layout_rows(spk_logos, H_SPK, usable_w) if spk_logos else []
    spk_block_h = _rows_block_h(spk_rows)

    # ── Measure total height ──────────────────────────────────────────────────
    y = H_ACCENT + TOP_PAD
    if renmad_scaled:
        y += renmad_scaled.height + GAP_AFTER_RENMAD
    for i, g in enumerate(groups):
        if g["name"]:
            y += g["label_h"] + LABEL_GAP
        y += g["block_h"]
        if i < len(groups) - 1:
            y += GROUP_GAP
    if not groups:
        y += 40
    if spk_rows:
        y += GROUP_GAP + SPK_HDR_H + SPK_PAD_Y + spk_block_h + SPK_PAD_Y
    canvas_h = max(120, y + BOTTOM_PAD)

    # ── Draw ──────────────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (W, canvas_h), BG)
    draw   = ImageDraw.Draw(canvas)

    # Top accent line
    draw.rectangle([0, 0, W, H_ACCENT], fill=theme_rgb)

    y = H_ACCENT + TOP_PAD

    # RENMAD logo, centred
    if renmad_scaled:
        _paste(canvas, renmad_scaled, (W - renmad_scaled.width) // 2, y)
        y += renmad_scaled.height + GAP_AFTER_RENMAD

    # Sponsor / partner tiers, biggest first
    for i, g in enumerate(groups):
        if g["name"]:
            f  = g["label_font"]
            tw = _text_size(g["name"], f)[0]
            colour = theme_rgb if g["kind"] == "tier" else SEC_LABEL
            draw.text(((W - tw) // 2, y), g["name"], font=f, fill=colour)
            y += g["label_h"] + LABEL_GAP
        if g["rows"]:
            y = _draw_rows(canvas, g["rows"], y)
        if i < len(groups) - 1:
            y += GROUP_GAP

    # Speakers
    if spk_rows:
        y += GROUP_GAP
        draw.rectangle([0, y, W, y + SPK_HDR_H], fill=theme_rgb)
        label   = _SPK_LABEL.get(language, _SPK_LABEL["en"])
        label_f = _f("heavy", 28)
        lw_, lh_ = _text_size(label, label_f)
        draw.text(((W - lw_) // 2, y + (SPK_HDR_H - lh_) // 2),
                  label, font=label_f, fill=TEXT_WHITE)
        y += SPK_HDR_H + SPK_PAD_Y
        _draw_rows(canvas, spk_rows, y)

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
