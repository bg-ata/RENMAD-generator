# -*- coding: utf-8 -*-
"""Scrape an ATA / RENMAD webinar page → structured webinar metadata.

Reliable fields: title, speakers [name, role, photo_url, is_moderator].
Best-effort: sponsor/theme logo. Company-per-speaker is left for the form
(the page caption omits it). Webinar DATE should come from the Zoom CSV
(actual session datetime), not the page (page shows only a promo time).
"""
from __future__ import annotations
import re, sys, json
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
MOD_RE = re.compile(r"\[\s*(moderator|moderador|moderadora|moderatore|moderatrice|moderatorka)\s*\]", re.I)


def _clean_title(t: str) -> str:
    t = re.sub(r"\s*[-–]\s*My ATA.*$", "", t, flags=re.I)            # strip site suffix
    t = re.sub(r"^\s*Webinar\s*[:\-–]\s*", "", t, flags=re.I)         # strip "Webinar:" prefix
    return t.strip()


def _company_from_filename(photo: str) -> str:
    # convention: First-Last(-Middle).Company-N.png  → company = segment after the dot
    base = (photo or "").split("/")[-1]
    segs = base.split(".")
    if len(segs) >= 3:
        c = re.sub(r"-\d+$", "", segs[-2]).replace("-", " ").strip()
        return "ATA Insights" if c.lower() == "ata" else c
    return ""


def _guess_lang(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(magazyn|energii|możliwo|wyzwania|rynku|jak|projekt[óo]w)\b", t): return "pl"
    if re.search(r"\b(della|allopportun|quadro|progett|rendere|bancabili|riforma|energetico)\b", t): return "it"
    if re.search(r"\b(cómo|cadena|proyecto|máxima|bancabilidad|demanda|movilidad|energ[íi]a)\b", t): return "es"
    return "en"


def scrape_webinar(url: str, html: str | None = None) -> dict:
    if html is None:
        html = requests.get(url, headers=UA, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    og = lambda p: (soup.find("meta", property=p) or {}).get("content") if soup.find("meta", property=p) else None
    title = _clean_title(og("og:title") or (soup.title.string if soup.title else "") or "")
    cover = og("og:image")

    # speakers: name in the caption heading (<h4>/<strong>), role in the <p>(s)
    speakers, seen = [], set()
    for cap in soup.select(".wp-caption"):
        img = cap.find("img")
        photo = (img.get("src") or img.get("data-src")) if img else None
        figcap = cap.find("figcaption") or cap
        full = re.sub(r"\s+", " ", figcap.get_text(" ", strip=True)).strip()
        if not full:
            continue
        is_mod = bool(MOD_RE.search(full))
        name_el = figcap.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong"])
        name = name_el.get_text(" ", strip=True).strip() if name_el else ""
        ps = [p.get_text(" ", strip=True) for p in figcap.find_all("p")]
        role = " ".join(ps).strip() if ps else (full.replace(name, "", 1) if name else full)
        if not name:                                  # fallback: 2-token heuristic
            parts = full.split(); name = " ".join(parts[:2]); role = " ".join(parts[2:])
        role = re.sub(r"\s+", " ", MOD_RE.sub("", role)).strip(" -·")
        company = _company_from_filename(photo)
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        speakers.append({"name": name, "role": role, "company": company,
                         "photo": photo, "is_moderator": is_mod})

    # logos: RENMAD theme logo and/or a sponsor logo among uploads
    logos = []
    for img in soup.select("img"):
        src = img.get("src") or img.get("data-src") or ""
        low = src.lower()
        if "uploads" in low and ("logo" in low) and "favicon" not in low and "logo-3-blanco" not in low and "logo-prueba" not in low:
            logos.append(src.split("?")[0])
    logos = list(dict.fromkeys(logos))

    return {
        "url": url,
        "title": title,
        "language_guess": _guess_lang(title),
        "cover_image": cover,
        "speakers": speakers,
        "logos": logos,   # disambiguate theme vs sponsor in the form
    }


if __name__ == "__main__":
    urls = sys.argv[1:] or [
        "https://my.atainsights.com/webinar/webinar-how-green-hydrogen-projects-can-reach-fid-in-europe/",
        "https://my.atainsights.com/webinar/webinar-como-llegar-a-la-puntuacion-maxima-de-cadena-de-valor-europea-en-tu-proyecto-bess-con-feder/",
        "https://my.atainsights.com/webinar/webinar-financing-the-future-of-data-centers-capital-energy-and-investment-strategies/",
        "https://my.atainsights.com/webinar/webinar-distribucion-y-demanda-el-dilema-de-la-bancabilidad-del-biometano/",
        "https://my.atainsights.com/webinar/webinar-movilidad-terrestre-con-hidrogeno-el-reto-de-coordinar-infraestructura-y-demanda/",
        "https://my.atainsights.com/webinar/webinar-dalla-compliance-allopportunita-data-center-e-il-nuovo-quadro-energetico/",
        "https://my.atainsights.com/webinar/webinar-rendere-bancabili-i-progetti-bess-in-italia-fondamentali-su-ricavi-e-finanziamento/",
        "https://my.atainsights.com/webinar/webinar-riforma-del-permitting-in-italia-cosa-cambia-con-il-tufer-per-i-progetti-di-storage/",
        "https://my.atainsights.com/webinar/webinar-jak-sfinansowac-magazyn-energii-mozliwosci-i-wyzwania-na-polskim-rynku/",
        "https://my.atainsights.com/webinar/webinar-optymalizacja-modeli-przychodow-w-wielkoskalowych-magazynach-energii-w-polsce/",
    ]
    for u in urls:
        try:
            d = scrape_webinar(u)
            print("=" * 80)
            print("[%s] %s" % (d["language_guess"].upper(), d["title"]))
            print("  speakers (%d):" % len(d["speakers"]))
            for s in d["speakers"]:
                print("     %s %-22s | %-40s | %s" % ("(MOD)" if s["is_moderator"] else "     ",
                      s["name"], s["role"][:40], s["company"]))
            print("  logos:", [l.split("/uploads/")[-1] for l in d["logos"]][:4])
        except Exception as e:
            print("ERR", u, e)
