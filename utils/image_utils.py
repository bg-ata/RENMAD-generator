"""Image processing utilities."""
import io
from PIL import Image, ImageDraw, ImageOps, ImageFilter


def make_circular(img: Image.Image, size: int = 300, border_color=None, border_width=0) -> Image.Image:
    """Crop image to a circle with optional coloured border."""
    img = img.convert("RGBA")
    img = ImageOps.fit(img, (size, size), method=Image.LANCZOS)

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    img.putalpha(mask)

    if border_color and border_width:
        canvas_size = size + border_width * 2
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        bd = ImageDraw.Draw(canvas)
        bd.ellipse((0, 0, canvas_size - 1, canvas_size - 1), fill=border_color)
        canvas.paste(img, (border_width, border_width), mask=img)
        return canvas

    return img


def make_square_crop(img: Image.Image, width: int, height: int) -> Image.Image:
    """Fit-crop image to exact dimensions (centre crop)."""
    img = img.convert("RGBA")
    return ImageOps.fit(img, (width, height), method=Image.LANCZOS)


def make_rounded_rect(img: Image.Image, w: int, h: int,
                       radius: int = 20,
                       border_color=None, border_width: int = 0) -> Image.Image:
    """Crop image to a rounded rectangle with optional coloured border."""
    img = img.convert("RGBA")
    img = ImageOps.fit(img, (w, h), method=Image.LANCZOS)

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w-1, h-1], radius=radius, fill=255)
    img.putalpha(mask)

    if border_color and border_width:
        bw  = border_width
        cw, ch = w + bw * 2, h + bw * 2
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ImageDraw.Draw(canvas).rounded_rectangle(
            [0, 0, cw-1, ch-1], radius=radius + bw, fill=border_color
        )
        canvas.paste(img, (bw, bw), mask=img)
        return canvas

    return img


def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def img_to_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def load_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGBA")


def resize_keep_aspect(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    return img


# -- NEW combined speaker files (photo on top + company logo strip below) --
# Since Jul 2026 the webinar/event speaker images arrive as ONE file (observed
# template: 220x298 = a square photo with a ~78px logo strip under it, usually
# white but sometimes a brand colour). Fed raw into the circle crop they showed
# "a piece of the face, white, a piece of the logo", and the logo went unmatched.
# split_speaker_composite() detects the layout and returns the two halves so the
# rest of the pipeline (round photo + logo pill below) keeps working unchanged.

def _row_stats(px, w, y):
    """(whiteness fraction, mean, stddev-ish spread) of row y of a grayscale image"""
    vals = [px[x, y] for x in range(w)]
    m = sum(vals) / float(w)
    spread = sum(abs(v - m) for v in vals) / float(w)
    white = sum(1 for v in vals if v >= 238) / float(w)
    return white, m, spread


def _trim_logo(logo: Image.Image):
    """crop the logo strip to its content, whatever the strip's background colour"""
    from PIL import ImageChops
    rgb = logo.convert("RGB")
    w, h = rgb.size
    if w < 4 or h < 4:
        return None
    corners = [rgb.getpixel(p) for p in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2))]
    bg = max(set(corners), key=corners.count)
    diff = ImageChops.difference(rgb, Image.new("RGB", (w, h), bg))
    bbox = diff.convert("L").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bbox:
        return None
    padx = max(2, w // 40); pady = max(2, h // 20)
    box = (max(0, bbox[0] - padx), max(0, bbox[1] - pady),
           min(w, bbox[2] + padx), min(h, bbox[3] + pady))
    out = rgb.crop(box)
    if out.size[0] < 8 or out.size[1] < 6:
        return None
    return out


def split_speaker_composite(data: bytes):
    """(photo_bytes, logo_bytes | None) -- conservative: anything that does not
    clearly look like the photo-over-logo composite comes back untouched."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return data, None
    w, h = img.size
    if not w or not h:
        return data, None
    ratio = h / float(w)
    if ratio < 1.05:                      # composites are clearly taller than wide
        return data, None

    aw = 240
    ah = max(1, int(h * aw / float(w)))
    small = img.convert("L").resize((aw, ah))
    px = small.load()

    def strip_row(y):
        """a strip row is near-white OR a flat uniform colour (yellow bands etc.)"""
        white, _m, spread = _row_stats(px, aw, y)
        return white >= 0.90 or spread <= 7.0

    sep = None   # separator row in SMALL coordinates: photo ends here

    # PRIMARY rule -- the house template: square photo + logo strip below.
    # Verify before trusting it: the rows just under the square must look like a
    # strip, otherwise this is simply a tall portrait photo (3:4 is also ~1.33!).
    sq_y = int(round(ah * (float(w) / h)))          # y where the square photo ends
    if 1.20 <= ratio <= 1.60 and sq_y < ah - 4:
        band = list(range(sq_y, min(ah, sq_y + max(3, int(ah * 0.05)))))
        good = sum(1 for y in band if strip_row(y))
        if good >= 0.7 * len(band):
            sep = sq_y
        else:
            # coloured strips with content right at the cut (a crest on a yellow
            # band) fail the whole-row test — check the side EDGES instead: in a
            # composite the strip's edge colour is uniform and JUMPS at the cut
            # (grey photo bg -> yellow), while a plain portrait continues smoothly.
            rgb = img.convert("RGB").resize((aw, ah))
            rpx = rgb.load()
            def edge_mean(y0, y1):
                pts = [rpx[x, y] for y in range(max(0, y0), min(ah, y1))
                       for x in list(range(0, 6)) + list(range(aw - 6, aw))]
                n = float(len(pts)) or 1.0
                return tuple(sum(p[c] for p in pts) / n for c in (0, 1, 2))
            def edge_spread(y0, y1):
                m = edge_mean(y0, y1)
                pts = [rpx[x, y] for y in range(max(0, y0), min(ah, y1))
                       for x in list(range(0, 6)) + list(range(aw - 6, aw))]
                return sum(sum(abs(p[c] - m[c]) for c in (0, 1, 2)) for p in pts) / (float(len(pts)) or 1.0)
            above = edge_mean(sq_y - 8, sq_y - 2)
            below = edge_mean(sq_y + 2, sq_y + 8)
            jump = sum(abs(a - b) for a, b in zip(above, below))
            if jump > 60 and edge_spread(sq_y + 2, ah - 2) < 45:
                sep = sq_y

    # FALLBACK -- older files aren't exactly square: look for the first blank band
    # (white OR a flat uniform colour) below 45% height with real content under it
    if sep is None:
        def blank(y):
            white, _m, spread = _row_stats(px, aw, y)
            return white >= 0.985 or spread <= 6.5
        def content(y):
            white, _m, spread = _row_stats(px, aw, y)
            return white < 0.94 and spread > 10
        band_min = max(2, int(ah * 0.008))
        y = int(ah * 0.45)
        while y < int(ah * 0.97):
            if blank(y):
                run = y
                while run < ah and blank(run):
                    run += 1
                if (run - y) >= band_min and any(content(yy) for yy in range(run, ah)):
                    sep = y
                    break
                y = run
            y += 1
    if sep is None:
        return data, None

    # refine: the square cut can land a hair above the photo's true bottom edge,
    # bleeding a dark line into the logo — advance to the first clean strip row
    # (the extra rows belong to the photo, so it grows by the same amount)
    limit = min(ah - 1, sep + max(2, int(ah * 0.04)))
    while sep < limit and not strip_row(sep):
        sep += 1
    scale = h / float(ah)
    cut = int(sep * scale)
    photo = img.crop((0, 0, w, cut))
    logo = _trim_logo(img.crop((0, min(h, cut + 2), w, h)))
    if logo is None:
        return data, None
    if photo.size[1] < h * 0.45 or logo.size[1] > h * 0.45:
        return data, None
    return pil_to_bytes(photo.convert("RGB"), "PNG"), pil_to_bytes(logo, "PNG")
