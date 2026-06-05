# -*- coding: utf-8 -*-
"""Assemble the renderer's data dicts from scraped meta + stats + form inputs.

assemble() returns (webinar, insights, orgs) ready for
design.render_proposal.generate_report(webinar, insights, stats, orgs, ...).
"""
from __future__ import annotations
import os
import re
import csv
from collections import Counter
from datetime import datetime

import requests

from canonicalize import canonical, clean_list, is_notable, seniority_score

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# industry → cover-grid segment (keys must match STRINGS[lang]["seg"])
SEG_MAP = {
    "Developer": "Developers & IPPs", "IPP": "Developers & IPPs",
    "Utility": "Utilities & Energy",
    "Financial Services": "Finance & Advisory", "Consultancy": "Finance & Advisory",
    "Legal Services": "Finance & Advisory", "International Financial Institution (IFI)": "Finance & Advisory",
    "EPC Contractor": "EPC, Tech & Equipment", "Equipment Supplier or Manufacturer": "EPC, Tech & Equipment",
    "Installer": "EPC, Tech & Equipment",
}
SEG_ORDER = ["Developers & IPPs", "Utilities & Energy", "Finance & Advisory", "EPC, Tech & Equipment"]
SENIOR = re.compile(r"\b(CEO|CTO|COO|CFO|chief|founder|owner|president|vice president|VP|partner|"
                    r"managing|director|head|principal|lead|manager)\b", re.I)
MONTHS = {
    "en": ["January","February","March","April","May","June","July","August","September","October","November","December"],
    "es": ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"],
    "it": ["gennaio","febbraio","marzo","aprile","maggio","giugno","luglio","agosto","settembre","ottobre","novembre","dicembre"],
    "pl": ["stycznia","lutego","marca","kwietnia","maja","czerwca","lipca","sierpnia","września","października","listopada","grudnia"],
}


# ── helpers ──────────────────────────────────────────────────────────────────
def _clean_company(c: str) -> str:
    c = re.sub(r"\s+", " ", (c or "")).strip(" .,")
    return c


def _is_real_company(c: str) -> bool:
    c = (c or "").strip()
    return len(c) >= 2 and not c.isdigit()


def webinar_date(zoom_csv_path: str, lang: str = "en") -> str:
    """Localised date from the Zoom 'Hora de inicio real' summary cell."""
    try:
        with open(zoom_csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        for i, r in enumerate(rows):
            if r and r[0].strip() == "Tema" and i + 1 < len(rows):
                idx = {h.strip(): j for j, h in enumerate(r)}
                j = idx.get("Hora de inicio real")
                if j is not None and j < len(rows[i + 1]):
                    dt = datetime.strptime(rows[i + 1][j].strip().split()[0], "%m/%d/%Y")
                    return "%d %s %d" % (dt.day, MONTHS.get(lang, MONTHS["en"])[dt.month - 1].capitalize(), dt.year)
    except Exception:
        pass
    return ""


def split_title(title: str):
    """Split a title into two balanced lines for the cover (short titles stay on one line)."""
    title = title.strip()
    words = title.split()
    if len(title) <= 28 or len(words) <= 2:
        return [title, ""]
    best, target = 1, len(title) / 2
    acc = 0
    for i, w in enumerate(words[:-1]):
        acc += len(w) + 1
        if acc >= target:
            best = i + 1
            break
    return [" ".join(words[:best]), " ".join(words[best:])]


def download_image(url: str, dest_dir: str, name: str) -> str | None:
    if not url:
        return None
    try:
        ext = os.path.splitext(url.split("?")[0])[1] or ".png"
        fn = name + ext
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        with open(os.path.join(dest_dir, fn), "wb") as f:
            f.write(r.content)
        return fn
    except Exception:
        return None


def youtube_views(url: str) -> str | None:
    """Best-effort view count using only `requests` (no yt-dlp). Returns None on
    failure — the form has a manual field as the reliable fallback."""
    if not url:
        return None
    try:
        m = re.search(r"(?:v=|/live/|youtu\.be/|/embed/)([A-Za-z0-9_-]{6,})", url)
        if not m:
            return None
        s = requests.Session()
        # accept the EU cookie wall so YouTube serves the real page
        s.cookies.set("SOCS", "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg")
        r = s.get("https://www.youtube.com/watch?v=%s&hl=en&gl=US" % m.group(1), headers=UA, timeout=20)
        v = re.search(r'"viewCount":\s*"(\d+)"', r.text)
        return f"{int(v.group(1)):,}" if v else None
    except Exception:
        return None


def fmt_k(n: int) -> str:
    return f"{round(n/1000)}K+" if n >= 1000 else str(n)


def _num_before(line, label):
    m = re.search(r"([\d][\d.,]*)\s*(?:%s)" % label, line, re.I)
    return int(re.sub(r"[^\d]", "", m.group(1))) if m else 0


def _sum_val(text, label):
    m = re.search(r"(?:over|m[aá]s de|oltre|ponad)?\s*([\d][\d.,]*\s*[KkMm]?)\s*(?:%s)" % label, text, re.I)
    if not m:
        return None
    v = m.group(1).replace(" ", "").upper()
    return v if v.endswith("+") else v + "+"


def parse_email_block(text):
    """Parse a pasted email-stats block (one campaign per line + optional summary)
    into (rows, totals). Handles bullets, '|' separators, EN/ES/IT/PL labels.

    e.g.  '• E-shot 1: Apr 15 | 11,081 sent | 3,783 opens | 400 clicks'
    """
    rows = []
    SENT = r"sent|envi\w*|invi\w*|wys[łl]\w*|consegn\w*"
    OPEN = r"opens?|apert\w*|aperture|otwar\w*"
    CLICK = r"clicks?|clic\w*|kli/ ?kn\w*|klikni\w*"
    summary_re = re.compile(r"(?i)^\s*(summary|resumen|riepilogo|podsumow|total)")
    summary_line = ""
    for raw in (text or "").splitlines():
        ln = raw.strip().lstrip("•·*-–\t ").strip()
        if not ln:
            continue
        if summary_re.match(ln):
            summary_line = ln
            continue
        if not re.search(r"(?i)(%s|%s|%s)" % (SENT, OPEN, CLICK), ln):
            continue
        name, date = ln, ""
        mc = re.match(r"^(.*?):(.*)$", ln)
        if mc:
            name = mc.group(1).strip()
            cand = re.split(r"\|", mc.group(2))[0].strip()
            if cand and not re.search(r"(?i)(%s|%s|%s)" % (SENT, OPEN, CLICK), cand) and not re.search(r"\d{3,}", cand):
                date = cand
        camp = name + (" · " + date if date else "")
        rows.append({"Campaign": camp, "Sent": _num_before(ln, SENT),
                     "Opens": _num_before(ln, OPEN), "Clicks": _num_before(ln, CLICK)})
    deliv = _sum_val(summary_line, r"delivered|entreg\w*|deliver\w*|consegn\w*|dostarcz\w*")
    opened = _sum_val(summary_line, r"opened|open\w*|apert\w*|otwar\w*")
    clicked = _sum_val(summary_line, r"clicked|click\w*|clic\w*|klikni\w*")
    totals = (deliv, opened, clicked) if (deliv and opened and clicked) else None
    return rows, totals


# ── derivations from registrants ─────────────────────────────────────────────
def derive_segments(regs, per_seg=8):
    buckets = {s: Counter() for s in SEG_ORDER}
    for r in regs:
        seg = SEG_MAP.get((r.industry or "").strip())
        c = _clean_company(r.company)
        if seg and _is_real_company(c):
            buckets[seg][c] += 1
    out = []
    for seg in SEG_ORDER:
        names = clean_list([c for c, _ in buckets[seg].most_common(per_seg * 2)])[:per_seg]
        if names:
            out.append((seg, names))
    return out


def derive_comp_sample(regs, n=12):
    cnt = Counter(_clean_company(r.company) for r in regs if _is_real_company(_clean_company(r.company)))
    return clean_list([c for c, _ in cnt.most_common(n * 2)])[:n]


def relevant_orgs_rich(regs, n=9):
    """Scored shortlist (seniority × notability), one per company, cleaned names.
    Returns dicts {company, raw, name, title, score} for an editable approval table."""
    cand = {}
    for r in regs:
        raw = _clean_company(r.company)
        if not _is_real_company(raw):
            continue
        comp = canonical(raw)
        score = seniority_score(r.job_title) * (1.6 if is_notable(comp) else 1.0)
        if score < 2:                       # require at least manager-level seniority
            continue
        cur = cand.get(comp)
        if not cur or score > cur["score"]:
            cand[comp] = {"company": comp, "raw": raw, "name": r.name, "title": r.job_title, "score": score}
    return sorted(cand.values(), key=lambda d: -d["score"])[:n]


def derive_relevant_orgs(regs, n=9):
    return [(d["company"], d["name"], d["title"]) for d in relevant_orgs_rich(regs, n)]


# ── insights (templated, per language) ───────────────────────────────────────
def build_insights(stats, email_totals, lang="en"):
    kf = stats["key_facts"]
    regions = {x["label"]: x["pct"] for x in stats.get("regions", [])}
    eu = round(regions.get("Europe", 0))
    latam = round(regions.get("LATAM", 0))
    inds = [x["label"] for x in stats["industries"]["rows"] if x["label"] != "Other"][:3]
    live = stats["live"]
    dur = stats.get("zoom_summary", {}).get("actual_duration_min", 60)
    deliv, opened, clicked = email_totals
    T = {
        "en": {
            "facts": f"{kf['registrations']:,} registrations from {kf['companies']} companies in {kf['countries']} countries — and a {kf['attendance_rate_pct']:.0f}% live show-up.",
            "country": f"Europe-led at {eu}%" + (f" with a strong {latam}% from LATAM" if latam else "") + f" — {kf['countries']} countries point to cross-border demand.",
            "industries": "Mostly " + ", ".join(inds[:3]).lower() + " — the people who actually buy and build in the sector.",
            "companies": "Across the value chain — developers, utilities, financiers and EPC / tech suppliers.",
            "engagement": f"{live['pct_ge_30min']:.0f}% stayed 30+ minutes and watched {live['avg_minutes']:.0f} of {dur} on average — a high-intent audience.",
            "reach": f"{deliv} deliveries and {opened} opens put the sponsor's topic in front of our 86K database many times over.",
            "orgs": "Senior, technically-relevant roles from leading companies watched live — the contacts a sponsor wants.",
        },
        "es": {
            "facts": f"{kf['registrations']:,} registros de {kf['companies']} empresas en {kf['countries']} países — y un {kf['attendance_rate_pct']:.0f}% de asistencia en directo.",
            "country": f"Liderado por Europa ({eu}%)" + (f" con un fuerte {latam}% de LATAM" if latam else "") + f" — {kf['countries']} países muestran demanda transfronteriza.",
            "industries": "Sobre todo " + ", ".join(inds[:3]).lower() + " — quienes realmente compran y construyen en el sector.",
            "companies": "De toda la cadena de valor: desarrolladores, utilities, financieros y proveedores EPC / tecnología.",
            "engagement": f"El {live['pct_ge_30min']:.0f}% permaneció 30+ minutos y vio {live['avg_minutes']:.0f} de {dur} de media — audiencia muy comprometida.",
            "reach": f"{deliv} entregas y {opened} aperturas pusieron el tema del patrocinador ante nuestra base de 86K muchas veces.",
            "orgs": "Cargos senior y técnicos de empresas líderes asistieron en directo — los contactos que busca un patrocinador.",
        },
        "it": {
            "facts": f"{kf['registrations']:,} registrazioni da {kf['companies']} aziende in {kf['countries']} paesi — e una partecipazione live del {kf['attendance_rate_pct']:.0f}%.",
            "country": f"Guidato dall'Europa ({eu}%)" + (f" con un forte {latam}% dal LATAM" if latam else "") + f" — {kf['countries']} paesi indicano domanda transfrontaliera.",
            "industries": "Soprattutto " + ", ".join(inds[:3]).lower() + " — chi davvero compra e costruisce nel settore.",
            "companies": "Lungo tutta la filiera: developer, utility, finanza e fornitori EPC / tech.",
            "engagement": f"Il {live['pct_ge_30min']:.0f}% è rimasto 30+ minuti e ha visto {live['avg_minutes']:.0f} di {dur} in media — pubblico molto coinvolto.",
            "reach": f"{deliv} consegne e {opened} aperture hanno messo il tema dello sponsor davanti al nostro database di 86K più volte.",
            "orgs": "Ruoli senior e tecnici di aziende leader hanno seguito live — i contatti che uno sponsor cerca.",
        },
        "pl": {
            "facts": f"{kf['registrations']:,} rejestracji z {kf['companies']} firm w {kf['countries']} krajach — i {kf['attendance_rate_pct']:.0f}% frekwencji na żywo.",
            "country": f"Z przewagą Europy ({eu}%)" + (f" i silnym {latam}% z LATAM" if latam else "") + f" — {kf['countries']} krajów wskazuje na popyt transgraniczny.",
            "industries": "Głównie " + ", ".join(inds[:3]).lower() + " — osoby, które realnie kupują i budują w branży.",
            "companies": "Z całego łańcucha wartości: deweloperzy, utilities, finanse i dostawcy EPC / tech.",
            "engagement": f"{live['pct_ge_30min']:.0f}% pozostało 30+ minut i obejrzało średnio {live['avg_minutes']:.0f} z {dur} — zaangażowana publiczność.",
            "reach": f"{deliv} dostaw i {opened} otwarć pokazało temat sponsora naszej bazie 86K wielokrotnie.",
            "orgs": "Stanowiska senior i techniczne z wiodących firm oglądały na żywo — kontakty, których szuka sponsor.",
        },
    }
    return T.get(lang, T["en"])


# ── main entry ───────────────────────────────────────────────────────────────
def assemble(scraped, stats, regs, form, assets_dir, lang="en", zoom_csv_path=None):
    """form keys: title, subtitle, youtube_url, sponsor_logo_url, email_rows[list of
    dicts], speakers[optional override list], contact{name,role,email}."""
    os.makedirs(assets_dir, exist_ok=True)

    # speakers → download photos
    speakers = []
    for i, sp in enumerate(form.get("speakers") or scraped.get("speakers", [])):
        fn = download_image(sp.get("photo"), assets_dir, "speaker_%d" % i)
        speakers.append({"name": sp["name"], "role": sp.get("role", ""),
                         "org": sp.get("company") or sp.get("org", ""),
                         "photo": fn, "mod": sp.get("is_moderator", sp.get("mod", False))})
    speakers = [s for s in speakers if s["photo"]]

    sponsor_fn = download_image(form.get("sponsor_logo_url"), assets_dir, "sponsor_logo")

    # email rows → totals
    rows, sent_t, open_t, click_t = [], 0, 0, 0
    for r in form.get("email_rows", []):
        try:
            s_, o_, c_ = int(r.get("Sent") or 0), int(r.get("Opens") or 0), int(r.get("Clicks") or 0)
        except Exception:
            s_ = o_ = c_ = 0
        sent_t += s_; open_t += o_; click_t += c_
        rows.append((r.get("Campaign", ""), f"{s_:,}" if s_ else "—",
                     f"{o_:,}" if o_ else "—", f"{c_:,}" if c_ else "—"))
    totals = form.get("email_totals") or (fmt_k(sent_t), fmt_k(open_t), fmt_k(click_t))

    title = (form.get("title") or scraped.get("title", "")).strip()
    subtitle = (form.get("subtitle") or "").strip()
    if not subtitle:                                   # split "Main – subtitle" off the scraped title
        parts = re.split(r"\s+[-–—:]\s+", title, 1)
        if len(parts) == 2 and len(parts[0]) >= 6:
            title, subtitle = parts[0].strip(), parts[1].strip()
    yt_url = form.get("youtube_url", "")
    contact = form.get("contact") or {"name": "Cintia Hernández", "role": "Business Development",
                                      "email": "cintia.hernandez@ata.email"}

    webinar = {
        "title_lines": split_title(title),
        "subtitle": subtitle,
        "date": webinar_date(zoom_csv_path, lang) if zoom_csv_path else "",
        "speakers": speakers,
        "sponsor_logo": sponsor_fn,
        "youtube": re.sub(r"^https?://", "", yt_url),
        "youtube_url": yt_url,
        "youtube_views": (form.get("youtube_views") or "").strip() or youtube_views(yt_url),
        "email": {"delivered": totals[0], "opened": totals[1], "clicked": totals[2], "rows": rows},
        "segments": derive_segments(regs),
        "comp_sample": derive_comp_sample(regs),
        "contact": contact,
    }
    insights = build_insights(stats, totals, lang)
    orgs = form.get("orgs_override") or derive_relevant_orgs(regs)
    return webinar, insights, orgs
