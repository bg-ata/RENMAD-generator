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
