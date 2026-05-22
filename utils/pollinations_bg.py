"""Free background generation via Pollinations.ai — no API key required."""
import io
import urllib.parse
import requests
from PIL import Image

from utils.gemini_bg import THEME_PROMPTS


def generate_backgrounds_free(theme_key: str, n: int = 4) -> list[Image.Image]:
    """
    Generate n background images using Pollinations.ai (free, no API key).
    Returns a list of PIL Images.
    """
    prompts = THEME_PROMPTS.get(theme_key, THEME_PROMPTS["naranja"])
    results = []
    for i in range(min(n, len(prompts))):
        encoded = urllib.parse.quote(prompts[i])
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1920&height=1080&nologo=true&model=flux&seed={i}"
        )
        try:
            r = requests.get(url, timeout=90)
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGBA")
            results.append(img)
        except Exception as e:
            print(f"Pollinations image {i} failed: {e}")
    return results
