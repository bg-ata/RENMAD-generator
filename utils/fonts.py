"""Central font loader — Montserrat + Inter (RENMAD brand guidelines 2026)."""
import os
from PIL import ImageFont

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts")

_PATHS = {
    # Montserrat — headlines / identity
    "montserrat-black":    [os.path.join(_ASSETS, "Montserrat-Black.ttf"),
                            "C:/Windows/Fonts/Montserrat-Black.ttf"],
    "montserrat-bold":     [os.path.join(_ASSETS, "Montserrat-Bold.ttf"),
                            "C:/Windows/Fonts/Montserrat-Bold.ttf"],
    "montserrat-semibold": [os.path.join(_ASSETS, "Montserrat-SemiBold.ttf"),
                            "C:/Windows/Fonts/Montserrat-SemiBold.ttf"],
    "montserrat":          [os.path.join(_ASSETS, "Montserrat-Regular.ttf"),
                            "C:/Windows/Fonts/Montserrat-Regular.ttf"],
    # Inter — body / digital
    "inter":               [os.path.join(_ASSETS, "Inter-Regular.ttf"),
                            "C:/Windows/Fonts/Inter-Regular.ttf",
                            "C:/Windows/Fonts/inter.ttf"],
    "inter-semibold":      [os.path.join(_ASSETS, "Inter-SemiBold.ttf"),
                            os.path.join(_ASSETS, "Inter-Regular.ttf")],
    # Windows fallbacks
    "_bold_fallback":      ["C:/Windows/Fonts/arialbd.ttf"],
    "_reg_fallback":       ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"],
}


def get(style: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font by style name and size.
    Styles: montserrat-black, montserrat-bold, montserrat-semibold, montserrat,
            inter, inter-semibold
    Falls back to Arial/Calibri if brand fonts aren't available.
    """
    candidates = _PATHS.get(style, []) + _PATHS["_reg_fallback"]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# Convenience aliases matching the brand type scale
def h1(size: int = 52) -> ImageFont.FreeTypeFont:
    return get("montserrat-black", size)

def h2(size: int = 32) -> ImageFont.FreeTypeFont:
    return get("montserrat-bold", size)

def subtitle(size: int = 18) -> ImageFont.FreeTypeFont:
    return get("montserrat-semibold", size)

def label(size: int = 11) -> ImageFont.FreeTypeFont:
    return get("montserrat-bold", size)

def body(size: int = 16) -> ImageFont.FreeTypeFont:
    return get("inter", size)

def note(size: int = 12) -> ImageFont.FreeTypeFont:
    return get("inter", size)
