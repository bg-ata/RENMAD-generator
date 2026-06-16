# -*- coding: utf-8 -*-
"""
Match a folder of speaker photos + company logos to the speakers/companies in a
parsed agenda, purely by filename. Files are named like:

    Intesa_Sanpaolo_Alessandro_Steffanoni.jpg   ← photo (company + person)
    Aquila_Clean_Energy_logo.png                 ← logo  (company, no person)
    SMBC.png                                      ← logo  (bare company)

Strategy:
  1. Photos = files whose name contains a speaker's name → assign to that speaker.
  2. Logos  = the remaining image files → assign to companies by core-token match.

Returns PIL images keyed by speaker name / company, plus a coverage report so
the UI (or a quick run) can show what matched and what's still missing.
"""
from __future__ import annotations

import io
import os
import re
import unicodedata
from difflib import SequenceMatcher

from PIL import Image

_IMG_EXT = (".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".gif")
_VECTOR_EXT = (".svg",)
_SKIP_EXT = (".eps", ".pdf", ".ai")

# Generic company words that don't help identify a logo file.
_COMPANY_STOP = {
    "energy", "energia", "capital", "bank", "banca", "financial", "advisors",
    "advisory", "group", "groupe", "italia", "italy", "spa", "srl", "sl", "plc",
    "the", "of", "and", "clean", "investment", "investments", "partners",
    "holding", "holdings", "co", "inc", "ltd", "gmbh", "ag", "sa", "limited",
    "logo", "png", "positive", "rgb", "vectorizado",
}


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s


def _toks(s: str) -> list[str]:
    return [t for t in _slug(s).split("_") if t]


def _nosep(s: str) -> str:
    return _slug(s).replace("_", "")


def _load_image(path: str) -> Image.Image | None:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in _VECTOR_EXT:
            import fitz  # PyMuPDF rasterises SVG without external deps
            doc = fitz.open(path)
            page = doc[0]
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0:
                doc.close(); return None
            zoom = 1200 / max(rect.width, rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
            data = pix.tobytes("png")
            doc.close()
            return Image.open(io.BytesIO(data)).convert("RGBA")
        if ext in _IMG_EXT:
            return Image.open(path).convert("RGBA")
    except Exception:
        return None
    return None


def match_assets(agenda: dict, folder: str) -> dict:
    """
    Returns:
      {
        "photos": {speaker_name: PIL.Image},
        "logos":  {company: PIL.Image},
        "report": {
          "photo_matched": [(name, filename)],
          "photo_missing": [name],
          "logo_matched":  [(company, filename)],
          "logo_missing":  [company],
        }
      }
    """
    files = [f for f in (os.listdir(folder) if os.path.isdir(folder) else [])
             if os.path.splitext(f)[1].lower() in (_IMG_EXT + _VECTOR_EXT)]
    file_slugs = {f: _slug(os.path.splitext(f)[0]) for f in files}

    # gather speakers + companies (de-duped, in first-seen order)
    speakers, companies, seen_c = [], [], set()
    for s in agenda.get("sessions", []):
        for sp in s.get("speakers", []):
            nm = (sp.get("name") or "").strip()
            co = (sp.get("company") or "").strip()
            if nm:
                speakers.append((nm, co))
            if co and co.lower() not in seen_c:
                seen_c.add(co.lower()); companies.append(co)

    # ── 1) photos: match a file to a speaker name ─────────────────────────────
    photos: dict[str, Image.Image] = {}
    photo_files: set[str] = set()
    photo_report: list[tuple[str, str]] = []
    photo_missing: list[str] = []

    for nm, co in speakers:
        if nm in photos:
            continue
        ntoks = set(_toks(nm))
        nslug = _nosep(nm)
        best_f, best_score = None, 0.0
        for f, fslug in file_slugs.items():
            ftoks = set(fslug.split("_"))
            shared = ntoks & ftoks
            ratio = SequenceMatcher(None, nslug, fslug.replace("_", "")).ratio()
            # need a strong personal-name signal: a shared name token, or a high
            # fuzzy ratio (handles spelling slips like Allcock↔Alcock)
            if not shared and ratio < 0.62:
                continue
            score = len(shared) * 1.0 + ratio
            # small boost if the company also appears in the filename
            if co and _nosep(co)[:5] and _nosep(co)[:5] in fslug.replace("_", ""):
                score += 0.3
            if score > best_score:
                best_score, best_f = score, f
        if best_f and best_score >= 1.0:
            img = _load_image(os.path.join(folder, best_f))
            if img is not None:
                photos[nm] = img
                photo_files.add(best_f)
                photo_report.append((nm, best_f))
                continue
        photo_missing.append(nm)

    # ── 1b) photo fallback: a still-missing speaker may have a file named by
    #         company + first-name only (e.g. "Carola CHIOMENTI.jpg" for the
    #         Chiomenti rep). Claim such a file as a photo so it never leaks into
    #         the logo pool. Marked low-confidence in the report.
    photo_fuzzy: list[tuple[str, str]] = []
    if photo_missing:
        still_missing = list(photo_missing)
        photo_missing = []
        for nm in still_missing:
            co = next((c for n, c in speakers if n == nm), "")
            core_co = [t for t in _toks(co) if t not in _COMPANY_STOP]
            picked = None
            if core_co:
                for f, fslug in file_slugs.items():
                    if f in photo_files or "logo" in fslug:
                        continue
                    ftoks = set(fslug.split("_"))
                    extra = [t for t in ftoks if t not in _COMPANY_STOP
                             and t not in core_co]
                    if (set(core_co) & ftoks) and extra:
                        picked = f
                        break
            if picked:
                img = _load_image(os.path.join(folder, picked))
                if img is not None:
                    photos[nm] = img
                    photo_files.add(picked)
                    photo_fuzzy.append((nm, picked))
                    continue
            photo_missing.append(nm)

    # ── 2) logos: match remaining files to companies by core tokens ───────────
    logo_candidates = {f: s for f, s in file_slugs.items() if f not in photo_files}
    logos: dict[str, Image.Image] = {}
    logo_report: list[tuple[str, str]] = []
    logo_missing: list[str] = []

    for co in companies:
        core = [t for t in _toks(co) if t not in _COMPANY_STOP] or _toks(co)
        co_nosep = "".join(core)
        best_f, best_score = None, 0.0
        for f, fslug in logo_candidates.items():
            f_nosep = fslug.replace("_", "")
            ftoks = set(fslug.split("_"))
            shared = set(core) & ftoks
            contains = co_nosep and (co_nosep in f_nosep or f_nosep.startswith(co_nosep[:6]))
            if not shared and not contains:
                continue
            # Guard: a logo file should not carry an extra personal-name token
            # (that means it's actually somebody's photo). Allow it only if the
            # filename explicitly says "logo".
            extra = [t for t in ftoks if t not in _COMPANY_STOP and t not in core]
            if extra and "logo" not in fslug:
                continue
            score = len(shared) * 1.0 + (1.0 if contains else 0.0)
            if "logo" in fslug:
                score += 0.4
            if score > best_score:
                best_score, best_f = score, f
        if best_f and best_score >= 1.0:
            img = _load_image(os.path.join(folder, best_f))
            if img is not None:
                logos[co] = img
                logo_report.append((co, best_f))
                continue
        logo_missing.append(co)

    return {
        "photos": photos,
        "logos": logos,
        "report": {
            "photo_matched": photo_report,
            "photo_fuzzy": photo_fuzzy,
            "photo_missing": photo_missing,
            "logo_matched": logo_report,
            "logo_missing": logo_missing,
        },
    }
