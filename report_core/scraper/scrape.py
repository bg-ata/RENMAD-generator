# -*- coding: utf-8 -*-
"""Scrape an ATA / RENMAD webinar page → structured webinar metadata.

Dependency-free: uses only `requests` (already installed) + the standard library
(no beautifulsoup4). Reliable fields: title, speakers [name, role, photo_url,
is_moderator]. Best-effort: sponsor/theme logos. Company-per-speaker is parsed
from the image filename when present. Webinar DATE comes from the Zoom CSV.
"""
from __future__ import annotations
import re
from html import unescape

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
MOD_RE = re.compile(r"\[\s*(moderator|moderador|moderadora|moderatore|moderatrice|moderatorka)\s*\]", re.I)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def _clean_title(t: str) -> str:
    t = re.sub(r"\s*[-–]\s*My ATA.*$", "", t, flags=re.I)
    t = re.sub(r"^\s*Webinar\s*[:\-–]\s*", "", t, flags=re.I)
    return t.strip()


def _company_from_filename(photo: str) -> str:
    base = (photo or "").split("/")[-1]
    segs = base.split(".")
    if len(segs) >= 3:
        c = re.sub(r"-\d+$", "", segs[-2]).replace("-", " ").strip()
        return "ATA Insights" if c.lower() == "ata" else c
    return ""


def _guess_lang(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(magazyn|energii|możliwo|wyzwania|rynku|jak|projekt[óo]w|sfinansowa)\b", t): return "pl"
    if re.search(r"\b(della|allopportun|quadro|progett|rendere|bancabili|riforma|energetico)\b", t): return "it"
    if re.search(r"\b(cómo|cadena|proyecto|máxima|bancabilidad|demanda|movilidad|energ[íi]a)\b", t): return "es"
    return "en"


def _meta(html: str, prop: str) -> str:
    m = re.search(r'property=["\']%s["\']\s+content=["\']([^"\']*)["\']' % re.escape(prop), html)
    if not m:
        m = re.search(r'content=["\']([^"\']*)["\']\s+property=["\']%s["\']' % re.escape(prop), html)
    return unescape(m.group(1)) if m else ""


def scrape_webinar(url: str, html: str | None = None) -> dict:
    if html is None:
        html = requests.get(url, headers=UA, timeout=30).text

    _t = re.search(r"<title>(.*?)</title>", html, re.S)
    title = _clean_title(_meta(html, "og:title") or _text(_t.group(1) if _t else ""))
    cover = _meta(html, "og:image")

    speakers, seen = [], set()
    for block in re.findall(r'<figure[^>]*class=["\'][^"\']*wp-caption[^"\']*["\'][^>]*>(.*?)</figure>',
                            html, re.S | re.I):
        img = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block)
        photo = img.group(1) if img else None
        nm = re.search(r'<(?:h[1-6]|strong)[^>]*>(.*?)</(?:h[1-6]|strong)>', block, re.S | re.I)
        name = _text(nm.group(1)) if nm else ""
        ps = re.findall(r'<p[^>]*>(.*?)</p>', block, re.S | re.I)
        role = _text(" ".join(ps)) if ps else ""
        full = _text(block)
        is_mod = bool(MOD_RE.search(full))
        if not name:                                   # fallback: first two words
            parts = full.split(); name = " ".join(parts[:2]); role = " ".join(parts[2:])
        if not role and name:                          # role outside a <p>: caption text minus name
            role = full.replace(name, "", 1)
        role = re.sub(r"\s+", " ", MOD_RE.sub("", role)).strip(" -·")
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        speakers.append({"name": name, "role": role, "company": _company_from_filename(photo),
                         "photo": photo, "is_moderator": is_mod})

    logos = []
    for src in re.findall(r'https://my\.atainsights\.com/wp-content/uploads/[^"\'\) ]+', html):
        low = src.lower()
        if "logo" in low and "favicon" not in low and "logo-3-blanco" not in low and "logo-prueba" not in low:
            logos.append(src.split("?")[0])
    logos = list(dict.fromkeys(logos))

    return {"url": url, "title": title, "language_guess": _guess_lang(title),
            "cover_image": cover, "speakers": speakers, "logos": logos}


if __name__ == "__main__":
    import sys
    for u in sys.argv[1:]:
        d = scrape_webinar(u)
        print("[%s] %s" % (d["language_guess"].upper(), d["title"]))
        for s in d["speakers"]:
            print("   %s %-22s | %-36s | %s" % ("MOD" if s["is_moderator"] else "   ",
                  s["name"], s["role"][:36], s["company"]))
