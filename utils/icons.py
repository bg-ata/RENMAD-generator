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
