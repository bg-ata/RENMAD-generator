# -*- coding: utf-8 -*-
"""Render a dramatic 'dawn of the transition' hero background for the
RENMAD 2026-2027 calendar poster, with an energy-icon frieze."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import math

W, H = 2400, 1350
OUT = r"C:\Users\Belén\renmad_generator\assets\calendar_hero_bg.png"

# ---------- base gradient (deep night -> ember) ----------
yy = np.linspace(0, 1, H)[:, None]
xx = np.linspace(0, 1, W)[None, :]

top    = np.array([10, 11, 16])     # near-black blue
bottom = np.array([28, 10, 14])     # deep ember
base = top[None, None, :] * (1 - yy[..., None]) + bottom[None, None, :] * yy[..., None]
base = np.broadcast_to(base, (H, W, 3)).astype(np.float64).copy()

# diagonal red wash growing toward bottom-right
diag = np.clip((xx * 0.6 + yy * 0.9 - 0.35), 0, 1) ** 1.6
red = np.array([120, 24, 34])
base += red[None, None, :] * diag[..., None] * 0.55

# ---------- sunrise radial glow (bottom-right horizon) ----------
gx, gy = 0.78, 0.96
dist = np.sqrt(((xx - gx) * 1.15) ** 2 + ((yy - gy) * 1.55) ** 2)
glow = np.clip(1 - dist / 0.95, 0, 1) ** 2.2
ember = np.array([226, 84, 34])
base += ember[None, None, :] * glow[..., None] * 0.95

# tight bright core
core = np.clip(1 - dist / 0.30, 0, 1) ** 3
base += np.array([255, 138, 66])[None, None, :] * core[..., None] * 0.5

# subtle second cool glow top-left for depth
d2 = np.sqrt(((xx - 0.12) * 1.0) ** 2 + ((yy - 0.05) * 1.4) ** 2)
g2 = np.clip(1 - d2 / 0.8, 0, 1) ** 2.5
base += np.array([60, 70, 110])[None, None, :] * g2[..., None] * 0.35

img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")

# ---------- halftone dot texture (upper area, very faint) ----------
dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
dd = ImageDraw.Draw(dots)
step = 34
for j in range(0, int(H * 0.55), step):
    for i in range(0, W, step):
        fade = max(0, 1 - j / (H * 0.55))
        a = int(16 * fade)
        if a > 0:
            dd.ellipse([i, j, i + 3, j + 3], fill=(255, 255, 255, a))
img = Image.alpha_composite(img.convert("RGBA"), dots)

# ================= ENERGY-ICON FRIEZE =================
fr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(fr)
ICON = (255, 150, 96, 95)      # warm translucent line colour
LW = 5
BASE = int(H * 0.945)          # ground line for the frieze
SC = 1.0


def turbine(cx, ground, s=1.0):
    h = 150 * s
    top = ground - h
    d.line([(cx, ground), (cx, top)], fill=ICON, width=LW)              # tower
    hub = (cx, top)
    for ang in (90, 210, 330):
        a = math.radians(ang)
        x2 = cx + math.cos(a) * 70 * s
        y2 = top - math.sin(a) * 70 * s
        d.line([hub, (x2, y2)], fill=ICON, width=LW)                    # blades
    d.ellipse([cx - 7, top - 7, cx + 7, top + 7], fill=ICON)


def solar(cx, ground, s=1.0):
    w, h = 130 * s, 70 * s
    # stand
    d.line([(cx, ground), (cx, ground - 45 * s)], fill=ICON, width=LW)
    # slanted panel (parallelogram)
    x0, y0 = cx - w / 2, ground - 45 * s
    pts = [(x0, y0), (x0 + w, y0 - h * 0.45),
           (x0 + w, y0 - h * 0.45 - 34 * s), (x0, y0 - 34 * s)]
    d.line(pts + [pts[0]], fill=ICON, width=LW, joint="curve")
    for k in range(1, 4):                                               # cell lines
        t = k / 4
        d.line([(x0 + w * t, y0 - 34 * s - h * 0.45 * t),
                (x0 + w * t, y0 - h * 0.45 * t)], fill=ICON, width=3)


def sun(cx, ground, s=1.0):
    cy = ground - 90 * s
    r = 34 * s
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ICON, width=LW)
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        d.line([(cx + math.cos(a) * (r + 14), cy + math.sin(a) * (r + 14)),
                (cx + math.cos(a) * (r + 34), cy + math.sin(a) * (r + 34))],
               fill=ICON, width=LW)


def h2(cx, ground, s=1.0):
    cy = ground - 78 * s
    r = 30 * s
    d.ellipse([cx - r * 2, cy - r, cx, cy + r], outline=ICON, width=LW)
    d.ellipse([cx, cy - r, cx + r * 2, cy + r], outline=ICON, width=LW)
    d.line([(cx, cy - r * 0.5), (cx, cy + r * 0.5)], fill=ICON, width=4)


def battery(cx, ground, s=1.0):
    w, h = 84 * s, 150 * s
    x0, y0 = cx - w / 2, ground - h
    d.rounded_rectangle([x0, y0, x0 + w, ground], radius=12 * s,
                        outline=ICON, width=LW)
    d.rectangle([cx - 18 * s, y0 - 16 * s, cx + 18 * s, y0], fill=ICON)  # nub
    bolt = [(cx + 8, y0 + 38), (cx - 16, y0 + 86), (cx + 2, y0 + 86),
            (cx - 8, y0 + 120), (cx + 20, y0 + 66), (cx + 2, y0 + 66)]
    d.line(bolt + [bolt[0]], fill=ICON, width=4, joint="curve")


# lay the frieze rhythmically across the width
seq = [turbine, solar, h2, battery, sun, turbine, solar, sun, h2, battery,
       turbine, solar, sun, turbine, solar, h2, battery, sun]
gap = W / (len(seq) + 1)
sizes = [1.0, 0.8, 0.9, 0.85, 0.95]
for n, fn in enumerate(seq):
    cx = gap * (n + 1)
    fn(cx, BASE, s=sizes[n % len(sizes)])

# soft glow on the frieze
glowlayer = fr.filter(ImageFilter.GaussianBlur(6))
img = Image.alpha_composite(img, glowlayer)
img = Image.alpha_composite(img, fr)

# ---------- bottom fade so the frieze sits in shadow ----------
fade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(fade)
for j in range(int(H * 0.82), H):
    t = (j - H * 0.82) / (H * 0.18)
    fd.line([(0, j), (W, j)], fill=(8, 6, 10, int(120 * t)))
img = Image.alpha_composite(img, fade)

# subtle vignette
vig = Image.new("L", (W, H), 0)
vd = ImageDraw.Draw(vig)
vd.ellipse([-W * 0.25, -H * 0.25, W * 1.25, H * 1.25], fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(300))
dark = Image.new("RGBA", (W, H), (0, 0, 0, 90))
img = Image.composite(img, Image.alpha_composite(img, dark), vig)

img.convert("RGB").save(OUT, quality=95)
print("Saved:", OUT)
