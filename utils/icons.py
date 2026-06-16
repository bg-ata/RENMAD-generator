"""Small geometric icons drawn with PIL — no emoji fonts needed."""
import math
from PIL import Image, ImageDraw


def _canvas(size: int):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def calendar(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    img, d = _canvas(size)
    p = max(1, size // 12)
    s = size
    # Outer box
    d.rounded_rectangle([p, p*2, s-p-1, s-p-1], radius=p*2, outline=color, width=p)
    # Header fill bar
    d.rectangle([p+1, p*2+1, s-p-2, p*5], fill=color)
    # Binding posts (top)
    for bx in [s//3, s*2//3]:
        d.rectangle([bx-p, 0, bx+p, p*3+1], fill=color)
    # Grid: 2 rows × 3 dots
    dot_r = max(1, p)
    for row in range(2):
        for col in range(3):
            cx = p*3 + col * (s - p*5) // 2
            cy = p*7 + row * (s - p*10) // 2
            d.ellipse([cx-dot_r, cy-dot_r, cx+dot_r, cy+dot_r], fill=color)
    return img


def clock(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    img, d = _canvas(size)
    p = max(1, size // 12)
    cx = cy = size // 2
    r = size // 2 - p
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color, width=p)
    # Hour hand ~10 o'clock
    ah = -math.pi * 2 / 3
    d.line([cx, cy,
            int(cx + r * 0.48 * math.sin(ah)),
            int(cy - r * 0.48 * math.cos(ah))],
           fill=color, width=p + 1)
    # Minute hand pointing up
    d.line([cx, cy, cx, cy - int(r * 0.7)], fill=color, width=p)
    d.ellipse([cx-p, cy-p, cx+p, cy+p], fill=color)
    return img


def pin(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    img, d = _canvas(size)
    p = max(1, size // 12)
    s = size
    cx = s // 2
    r  = s // 3
    top = p
    # Filled teardrop head
    d.ellipse([cx-r, top, cx+r, top + r*2], fill=color)
    # Inner hole
    ir = max(2, r // 3)
    mid = top + r
    d.ellipse([cx-ir, mid-ir, cx+ir, mid+ir], fill=(0, 0, 0, 0))
    # Tail triangle
    d.polygon([(cx - r//2 + p, top + r*2 - p*2),
                (cx + r//2 - p, top + r*2 - p*2),
                (cx,            s - p)], fill=color)
    return img


def arrow(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Right-pointing arrow for URL / CTA."""
    img, d = _canvas(size)
    p  = max(1, size // 12)
    s  = size
    cy = s // 2
    x1, x2 = p * 2, s - p * 2
    d.line([x1, cy, x2, cy], fill=color, width=p + 1)
    arr = p * 3
    d.polygon([(x2 - arr, cy - arr), (x2, cy), (x2 - arr, cy + arr)], fill=color)
    return img


def people(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Group of two people (for attendees stat)."""
    img, d = _canvas(size)
    s = size
    p = max(1, s // 12)
    hr = max(2, s // 7)           # head radius
    # Back person (right-shifted, slightly smaller)
    for cx, cy, r_scale in ((s * 7 // 12, s // 5, 0.82), (s * 5 // 12, s // 5, 1.0)):
        r = max(1, int(hr * r_scale))
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=color)
        bw = max(2, int(r * 1.9))
        d.rounded_rectangle([cx-bw//2, cy+r, cx+bw//2, s - p*2],
                             radius=max(1, p), fill=color)
    return img


def speaker(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Single person at a podium (for speakers stat)."""
    img, d = _canvas(size)
    s = size
    p = max(1, s // 12)
    hr = max(2, s // 6)
    cx = s // 2
    cy = s // 4
    # Head
    d.ellipse([cx-hr, cy-hr, cx+hr, cy+hr], fill=color)
    # Body
    bw = max(2, int(hr * 2.0))
    body_bot = cy + hr + int(hr * 2.2)
    d.rounded_rectangle([cx-bw//2, cy+hr, cx+bw//2, body_bot],
                         radius=max(1, p), fill=color)
    # Podium bar
    pw = max(4, s * 2 // 3)
    ph = max(2, s // 8)
    d.rounded_rectangle([cx-pw//2, body_bot + p, cx+pw//2, body_bot + p + ph],
                         radius=max(1, p), fill=color)
    return img


def coffee(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Coffee cup with handle + steam (for coffee break)."""
    img, d = _canvas(size)
    p = max(1, size // 14)
    s = size
    cup_l, cup_r = s * 3 // 14, s * 9 // 14
    cup_t, cup_b = s * 5 // 12, s * 10 // 12
    d.rounded_rectangle([cup_l, cup_t, cup_r, cup_b], radius=p * 2,
                        outline=color, width=p)
    # handle
    d.arc([cup_r - p, cup_t + p, cup_r + s * 3 // 14, cup_b - p],
          start=-70, end=70, fill=color, width=p)
    # steam
    for sx in (cup_l + (cup_r - cup_l) // 3, cup_l + 2 * (cup_r - cup_l) // 3):
        d.arc([sx - p * 2, s * 2 // 12, sx + p * 2, s * 5 // 12],
              start=120, end=300, fill=color, width=p)
    return img


def meal(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Fork + knife (for lunch)."""
    img, d = _canvas(size)
    p = max(1, size // 16)
    s = size
    top, bot = s * 2 // 12, s * 10 // 12
    # knife (right)
    kx = s * 8 // 12
    d.line([kx, top, kx, bot], fill=color, width=p * 2)
    d.polygon([(kx - p * 2, top), (kx, top), (kx, top + s // 3)], fill=color)
    # fork (left)
    fx = s * 4 // 12
    d.line([fx, s * 5 // 12, fx, bot], fill=color, width=p * 2)
    for tx in (fx - p * 3, fx, fx + p * 3):
        d.line([tx, top, tx, s * 5 // 12], fill=color, width=p)
    d.line([fx - p * 3, s * 5 // 12, fx + p * 3, s * 5 // 12], fill=color, width=p)
    return img


def cocktail(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Martini glass (for cocktail / aperitivo)."""
    img, d = _canvas(size)
    p = max(1, size // 16)
    s = size
    top = s * 2 // 12
    cx = s // 2
    half = s * 4 // 12
    # bowl (triangle)
    d.line([cx - half, top, cx + half, top], fill=color, width=p)
    d.line([cx - half, top, cx, s * 7 // 12], fill=color, width=p)
    d.line([cx + half, top, cx, s * 7 // 12], fill=color, width=p)
    # stem + base
    d.line([cx, s * 7 // 12, cx, s * 10 // 12], fill=color, width=p)
    d.line([cx - half // 2, s * 10 // 12, cx + half // 2, s * 10 // 12],
           fill=color, width=p)
    # olive
    d.ellipse([cx - p, top + p, cx + p, top + p * 3], fill=color)
    return img


def badge(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Lanyard badge (for registration)."""
    img, d = _canvas(size)
    p = max(1, size // 14)
    s = size
    l, r = s * 3 // 12, s * 9 // 12
    t, b = s * 3 // 12, s * 10 // 12
    d.rounded_rectangle([l, t, r, b], radius=p * 2, outline=color, width=p)
    d.line([s // 2, 0, s // 2, t], fill=color, width=p)            # lanyard
    d.ellipse([s // 2 - p, t - p, s // 2 + p, t + p], fill=color)  # clip
    d.line([l + p * 2, b - p * 3, r - p * 2, b - p * 3], fill=color, width=p)
    return img


def phone(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Smartphone with a 'silence' slash (for mute-your-phone)."""
    img, d = _canvas(size)
    p = max(1, size // 16)
    s = size
    l, r = s * 4 // 12, s * 8 // 12
    t, b = s * 1 // 12, s * 11 // 12
    d.rounded_rectangle([l, t, r, b], radius=p * 2, outline=color, width=p)
    d.line([s // 2 - p * 2, t + p * 2, s // 2 + p * 2, t + p * 2], fill=color, width=p)
    d.ellipse([s // 2 - p, b - p * 3, s // 2 + p, b - p], fill=color)
    d.line([l - p, t - p, r + p, b + p], fill=color, width=p + 1)   # mute slash
    return img


def wifi(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """WiFi signal arcs (for the WiFi slide)."""
    img, d = _canvas(size)
    s = size
    p = max(1, size // 14)
    cx, cy = s // 2, s * 9 // 12
    for rad in (s * 4 // 12, s * 3 // 12, s * 2 // 12):
        d.arc([cx - rad, cy - rad, cx + rad, cy + rad],
              start=210, end=330, fill=color, width=p + 1)
    d.ellipse([cx - p, cy - p, cx + p, cy + p], fill=color)
    return img


def qr(size: int = 26, color: tuple = (255, 255, 255)) -> Image.Image:
    """Stylised QR glyph (decorative placeholder, not a real code)."""
    img, d = _canvas(size)
    s = size
    u = max(2, s // 7)
    # three finder squares
    for ox, oy in ((0, 0), (s - 3 * u, 0), (0, s - 3 * u)):
        d.rectangle([ox, oy, ox + 3 * u - 1, oy + 3 * u - 1], outline=color, width=max(1, u // 2))
        d.rectangle([ox + u, oy + u, ox + 2 * u - 1, oy + 2 * u - 1], fill=color)
    # a few modules
    for mx, my in ((4, 4), (5, 5), (4, 6), (6, 4), (6, 6), (5, 3), (3, 5)):
        d.rectangle([mx * u, my * u, mx * u + u - 1, my * u + u - 1], fill=color)
    return img


def paste_icon_text(canvas: Image.Image, draw: ImageDraw.ImageDraw,
                    icon: Image.Image, text: str, font,
                    x: int, y: int, fill, gap: int = 8) -> int:
    """Paste icon then draw text beside it. Returns the x right-edge."""
    text_bb = draw.textbbox((0, 0), text, font=font)
    text_h  = text_bb[3]
    icon_y  = y + max(0, (text_h - icon.height) // 2)
    canvas.paste(icon, (x, icon_y), mask=icon)
    tx = x + icon.width + gap
    draw.text((tx, y), text, font=font, fill=fill)
    return tx + text_bb[2] + gap * 3
