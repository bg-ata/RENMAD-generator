"""Gemini Imagen background generation for RENMAD themes."""
import io
import base64
from PIL import Image

# Themed prompts — professional, photorealistic, no people, wide angle
THEME_PROMPTS = {
    "naranja": [
        "Professional wide-angle photograph of a large-scale battery energy storage facility, rows of white BESS containers in an open industrial site, golden hour warm lighting, dramatic sky, no people, photorealistic, cinematic",
        "Aerial wide-angle photograph of a battery energy storage park, modern industrial landscape, blue sky with clouds, clean lines, no people, photorealistic",
        "Battery storage containers in a field at dusk, orange sky, reflective surfaces, industrial infrastructure, no people, wide angle, photorealistic",
        "Close-up wide shot of BESS battery storage units, industrial textures, soft daylight, technology and energy storage theme, no people, photorealistic",
    ],
    "morado": [
        "Professional wide-angle photograph of a biogas plant with large white dome digesters in green agricultural countryside, overcast dramatic sky, no people, photorealistic",
        "Anaerobic digester domes at a biomethane facility, lush green fields, twilight sky with purple tones, no people, wide angle, photorealistic",
        "Modern biogas and biomethane production facility, industrial green domes, rural landscape, soft morning light, no people, photorealistic, cinematic",
        "Wide shot of a renewable gas production plant with circular digester tanks, European countryside setting, dramatic clouds, no people, photorealistic",
    ],
    "azul": [
        "Professional wide-angle photograph of a modern data center interior, illuminated blue server racks in long corridor, cool blue LED lighting, high-tech atmosphere, no people, photorealistic",
        "Data center server rows with glowing blue and white lights, futuristic technology interior, depth of field, no people, wide angle, photorealistic",
        "Aerial view of a large hyperscale data center campus, modern architecture, blue sky, no people, photorealistic, cinematic",
        "Close perspective of server rack infrastructure, blue and cyan lighting, digital technology theme, no people, wide angle, photorealistic",
    ],
    "verde": [
        "Professional wide-angle photograph of large white hydrogen storage tanks at a green hydrogen facility, renewable energy infrastructure, blue sky and green landscape, no people, photorealistic",
        "Green hydrogen electrolysis plant with large metal tanks and pipework, clean energy facility, wide angle, bright daylight, no people, photorealistic",
        "Hydrogen fuel facility with cylindrical pressure vessels, wind turbines in background, dramatic sky, no people, wide angle, photorealistic, cinematic",
        "Renewable hydrogen production site, electrolyzer building and storage tanks, lush green surroundings, soft golden light, no people, photorealistic",
    ],
}


PAID_PLAN_ERRORS = (
    "only available on paid plans",
    "billing",
    "RESOURCE_EXHAUSTED",
    "quota",
)


def generate_backgrounds(theme_key: str, api_key: str, n: int = 4) -> list[Image.Image]:
    """
    Generate n background images using Gemini Imagen 4 for the given theme.
    Returns a list of PIL Images.
    Raises RuntimeError with a user-friendly message if the API key lacks image generation access.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    prompts = THEME_PROMPTS.get(theme_key, THEME_PROMPTS["naranja"])

    results = []
    for i in range(min(n, len(prompts))):
        try:
            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompts[i],
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    safety_filter_level="block_low_and_above",
                    person_generation="dont_allow",
                ),
            )
            for img_obj in response.generated_images:
                img_bytes = img_obj.image.image_bytes
                img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
                results.append(img)
        except Exception as e:
            err_str = str(e).lower()
            if any(kw in err_str for kw in PAID_PLAN_ERRORS):
                raise RuntimeError(
                    "Image generation requires a paid Google AI plan.\n\n"
                    "To enable it:\n"
                    "1. Go to https://aistudio.google.com/app/apikey\n"
                    "2. Enable billing for your project at https://console.cloud.google.com/billing\n"
                    "3. Come back and try again.\n\n"
                    f"(API error: {e})"
                ) from e
            print(f"Gemini image {i} failed: {e}")
            continue

    return results


def save_to_library(images: list[Image.Image], theme_key: str, assets_dir: str):
    """Save generated images to the background library folder."""
    import os
    folder = os.path.join(assets_dir, "backgrounds", theme_key)
    os.makedirs(folder, exist_ok=True)
    # Count existing to avoid overwriting
    existing = len([f for f in os.listdir(folder) if f.endswith(".png")])
    saved = []
    for i, img in enumerate(images):
        path = os.path.join(folder, f"gemini_{existing + i + 1:02d}.png")
        img.convert("RGB").save(path, format="PNG")
        saved.append(path)
    return saved
