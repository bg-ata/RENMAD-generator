"""Phase 1 data engine for the ATA webinar marketing-report generator.

Ingests the two raw exports a colleague already has for every webinar:
  1. Registration CSV (ATA CRM export of everyone registered for the webinar)
  2. Zoom attendee CSV (the "Informe de asistentes" multi-section export)

…and computes every statistic the report needs, into one canonical dict
that later phases serialise to webinar.json and render to PPTX.

Nothing here is webinar-specific: column handling is driven by COLUMN_CANDIDATES
so the same code works across ATA's differing registration form layouts.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional


# --------------------------------------------------------------------------
# Registration CSV handling
# --------------------------------------------------------------------------
# ATA's registration forms vary per webinar/language, so a given logical field
# can live in any of several columns. We coalesce, first non-empty wins.
COLUMN_CANDIDATES = {
    "email": ["Email", "*Email Asistente"],
    "first_name": ["First Name"],
    "last_name": ["Last Name"],
    "job_title": ["*Job Title 2", "*Job Title", "Job Title"],
    "country": ["*Country", "Country"],
    "industry": ["*Organization type:", "*Organization Type", "*Type of Organization / Type d'organisation"],
    "company": ["*Organization", "*Company", "*Current Company"],
}


def _first_filled(row: dict, keys: list[str]) -> str:
    for k in keys:
        v = (row.get(k) or "").strip()
        if v:
            return v
    return ""


def _company_from_email(email: str) -> str:
    """Fallback company name derived from the email domain.

    gmail / outlook / etc. are personal inboxes, not companies, so we drop them.
    """
    m = re.search(r"@([\w.-]+)", email or "")
    if not m:
        return ""
    domain = m.group(1).lower()
    free = {
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com",
        "live.com", "me.com", "protonmail.com", "gmx.de", "web.de", "ukr.net",
        "qq.com", "163.com", "aol.com", "mail.com", "yandex.com",
    }
    if domain in free:
        return ""
    label = domain.split(".")[0]
    return label.capitalize()


@dataclass
class Registrant:
    email: str
    name: str
    job_title: str
    country: str
    industry: str
    company: str


def load_registrations(path: str) -> list[Registrant]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        out: list[Registrant] = []
        for row in reader:
            email = _first_filled(row, COLUMN_CANDIDATES["email"])
            if not email:
                continue
            first = _first_filled(row, COLUMN_CANDIDATES["first_name"])
            last = _first_filled(row, COLUMN_CANDIDATES["last_name"])
            company = _first_filled(row, COLUMN_CANDIDATES["company"]) or _company_from_email(email)
            out.append(Registrant(
                email=email.lower().strip(),
                name=" ".join(p for p in (first, last) if p).strip(),
                job_title=_first_filled(row, COLUMN_CANDIDATES["job_title"]),
                country=_first_filled(row, COLUMN_CANDIDATES["country"]),
                industry=_first_filled(row, COLUMN_CANDIDATES["industry"]),
                company=company,
            ))
    return out


# --------------------------------------------------------------------------
# Country -> continent / region grouping
# --------------------------------------------------------------------------
# Covers the countries ATA actually sees; unknowns fall through to "Other".
_REGION = {
    # Europe
    "Spain": "Europe", "Germany": "Europe", "France": "Europe", "Italy": "Europe",
    "Portugal": "Europe", "United Kingdom": "Europe", "Ireland": "Europe",
    "Netherlands": "Europe", "Belgium": "Europe", "Switzerland": "Europe",
    "Austria": "Europe", "Poland": "Europe", "Romania": "Europe", "Greece": "Europe",
    "Sweden": "Europe", "Norway": "Europe", "Denmark": "Europe", "Finland": "Europe",
    "Croatia": "Europe", "Cyprus": "Europe", "Latvia": "Europe", "Lithuania": "Europe",
    "Estonia": "Europe", "Czech Republic": "Europe", "Czechia": "Europe",
    "Hungary": "Europe", "Bulgaria": "Europe", "Ukraine": "Europe", "Turkey": "Europe",
    "Luxembourg": "Europe", "Slovenia": "Europe", "Slovakia": "Europe", "Serbia": "Europe",
    # LATAM
    "Mexico": "LATAM", "Brazil": "LATAM", "Chile": "LATAM", "Argentina": "LATAM",
    "Colombia": "LATAM", "Peru": "LATAM", "Bolivia": "LATAM", "Ecuador": "LATAM",
    "Uruguay": "LATAM", "Paraguay": "LATAM", "El Salvador": "LATAM", "Panama": "LATAM",
    "Costa Rica": "LATAM", "Guatemala": "LATAM", "Dominican Republic": "LATAM",
    "Honduras": "LATAM", "Venezuela": "LATAM",
    # North America
    "United States": "North America", "Canada": "North America",
    # MENA
    "Egypt": "MENA", "Morocco": "MENA", "Jordan": "MENA", "Saudi Arabia": "MENA",
    "United Arab Emirates": "MENA", "Israel": "MENA", "Tunisia": "MENA", "Algeria": "MENA",
    "Qatar": "MENA", "Oman": "MENA", "Kuwait": "MENA", "Lebanon": "MENA",
    # Sub-Saharan Africa
    "South Africa": "Africa", "Nigeria": "Africa", "Kenya": "Africa", "Togo": "Africa",
    "Ghana": "Africa", "Senegal": "Africa", "Ethiopia": "Africa", "Tanzania": "Africa",
    "Zambia": "Africa", "Zimbabwe": "Africa", "Uganda": "Africa",
    # Asia-Pacific
    "India": "Asia-Pacific", "Pakistan": "Asia-Pacific", "China": "Asia-Pacific",
    "Japan": "Asia-Pacific", "South Korea": "Asia-Pacific", "Australia": "Asia-Pacific",
    "New Zealand": "Asia-Pacific", "Singapore": "Asia-Pacific", "Philippines": "Asia-Pacific",
    "Indonesia": "Asia-Pacific", "Malaysia": "Asia-Pacific", "Thailand": "Asia-Pacific",
    "Vietnam": "Asia-Pacific", "Bangladesh": "Asia-Pacific", "Kazakhstan": "Asia-Pacific",
}


def region_of(country: str) -> str:
    return _REGION.get(country.strip(), "Other")


# Zoom exports country names in the account locale (often Spanish/Italian/Polish).
# Map them to the English canonical names so regions + display stay consistent.
_COUNTRY_CANON = {
    # Spanish
    "españa": "Spain", "alemania": "Germany", "francia": "France", "italia": "Italy",
    "portugal": "Portugal", "reino unido": "United Kingdom", "países bajos": "Netherlands",
    "holanda": "Netherlands", "bélgica": "Belgium", "suiza": "Switzerland", "austria": "Austria",
    "polonia": "Poland", "rumanía": "Romania", "rumania": "Romania", "grecia": "Greece",
    "suecia": "Sweden", "noruega": "Norway", "dinamarca": "Denmark", "finlandia": "Finland",
    "croacia": "Croatia", "chipre": "Cyprus", "letonia": "Latvia", "lituania": "Lithuania",
    "estonia": "Estonia", "hungría": "Hungary", "bulgaria": "Bulgaria", "ucrania": "Ukraine",
    "turquía": "Turkey", "luxemburgo": "Luxembourg", "eslovenia": "Slovenia", "eslovaquia": "Slovakia",
    "serbia": "Serbia", "irlanda": "Ireland", "república checa": "Czech Republic",
    "méxico": "Mexico", "brasil": "Brazil", "chile": "Chile", "argentina": "Argentina",
    "colombia": "Colombia", "perú": "Peru", "bolivia": "Bolivia", "ecuador": "Ecuador",
    "uruguay": "Uruguay", "paraguay": "Paraguay", "el salvador": "El Salvador", "panamá": "Panama",
    "costa rica": "Costa Rica", "guatemala": "Guatemala", "república dominicana": "Dominican Republic",
    "honduras": "Honduras", "venezuela": "Venezuela",
    "estados unidos": "United States", "canadá": "Canada",
    "egipto": "Egypt", "marruecos": "Morocco", "jordania": "Jordan", "arabia saudí": "Saudi Arabia",
    "arabia saudita": "Saudi Arabia", "emiratos árabes unidos": "United Arab Emirates",
    "israel": "Israel", "túnez": "Tunisia", "argelia": "Algeria", "catar": "Qatar", "qatar": "Qatar",
    "omán": "Oman", "kuwait": "Kuwait", "líbano": "Lebanon",
    "sudáfrica": "South Africa", "nigeria": "Nigeria", "kenia": "Kenya", "togo": "Togo",
    "ghana": "Ghana", "senegal": "Senegal", "etiopía": "Ethiopia", "tanzania": "Tanzania",
    "zambia": "Zambia", "zimbabue": "Zimbabwe", "uganda": "Uganda",
    "india": "India", "pakistán": "Pakistan", "china": "China", "japón": "Japan",
    "corea del sur": "South Korea", "australia": "Australia", "nueva zelanda": "New Zealand",
    "singapur": "Singapore", "filipinas": "Philippines", "indonesia": "Indonesia",
    "malasia": "Malaysia", "tailandia": "Thailand", "vietnam": "Vietnam",
    "bangladés": "Bangladesh", "kazajstán": "Kazakhstan",
    # Italian
    "spagna": "Spain", "germania": "Germany", "regno unito": "United Kingdom",
    "paesi bassi": "Netherlands", "belgio": "Belgium", "svizzera": "Switzerland",
    "stati uniti": "United States", "brasile": "Brazil", "messico": "Mexico", "grecia ": "Greece",
    # Polish
    "polska": "Poland", "niemcy": "Germany", "hiszpania": "Spain", "włochy": "Italy",
    "francja": "France", "wielka brytania": "United Kingdom", "stany zjednoczone": "United States",
}


def normalize_country(country: str) -> str:
    c = (country or "").strip()
    return _COUNTRY_CANON.get(c.lower(), c)


def _pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def _distribution(values, top: int = 15):
    """Counter -> ordered list of {label, count, pct} for the non-empty values."""
    vals = [v.strip() for v in values if v and v.strip()]
    total = len(vals)
    counts = Counter(vals)
    rows = [
        {"label": label, "count": c, "pct": _pct(c, total)}
        for label, c in counts.most_common(top)
    ]
    return {"total": total, "rows": rows}


def _normalize_company(name: str) -> str:
    n = re.sub(r"\s+", " ", name).strip()
    n = re.sub(r"[\s,]*(S\.?L\.?U?\.?|S\.?A\.?U?\.?|GmbH|Ltd\.?|LLC|Inc\.?|SpA|S\.?p\.?A\.?|B\.?V\.?|Srl|Lda)\b\.?$",
               "", n, flags=re.IGNORECASE).strip(" ,.")
    return n


def company_list(regs: list[Registrant]) -> list[str]:
    """Deduplicated, human-readable company names (case/suffix-insensitive)."""
    seen: dict[str, str] = {}
    for r in regs:
        if not r.company:
            continue
        norm = _normalize_company(r.company)
        key = norm.lower()
        if key and key not in seen:
            seen[key] = norm
    return sorted(seen.values(), key=str.lower)


# --------------------------------------------------------------------------
# Zoom attendee CSV handling
# --------------------------------------------------------------------------
@dataclass
class ZoomSummary:
    topic: str = ""
    registered: int = 0
    unique_viewers: int = 0
    total_users: int = 0
    peak_concurrent: int = 0
    actual_duration_min: int = 0


@dataclass
class ZoomAttendee:
    email: str
    name: str
    country: str
    minutes: int = 0          # summed across all join/leave rows
    sessions: int = 0


def _read_csv_rows(path: str) -> list[list[str]]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.reader(fh))


def _hcol(headers_lower, *subs):
    """Index of the first header containing any of the substrings (lowercase)."""
    for j, h in enumerate(headers_lower):
        if any(sub in h for sub in subs):
            return j
    return None


def _num(s):
    m = re.search(r"\d[\d.,]*", s or "")
    return int(re.sub(r"[^\d]", "", m.group())) if m else 0


# multilingual (EN/ES/IT/PL) substrings per Zoom column concept
_C = {
    "attended": ("asisti", "attend", "partecip", "uczestni", "obecn", "frekw"),
    "email": ("correo", "email", "e-mail", "mail", "poczta"),
    "country": ("país/", "pais/", "country/", "paese/", "kraj", "país", "country", "paese"),
    "uname": ("nombre de usuario", "user name", "nome utente", "nazwa użytk", "display name"),
    "firstname": ("first name", "imię"),
    "lastname": ("apellido", "last name", "cognome", "nazwisko"),
    "registered": ("inscrit", "registered", "registr", "iscritt", "zarejestrow"),
    "unique": ("exclusiv", "unique", "unici", "unikal"),
    "total": ("usuarios totales", "total users", "utenti totali", "łączna liczba u"),
    "peak": ("simultáneas máximas", "max concurrent", "simultanee massime", "jednoczesn", "concurrent"),
    "duration": ("duración real", "actual duration", "durata effettiva", "rzeczywisty czas", "duration", "durata"),
    "topic": ("tema", "topic", "argomento", "temat"),
}
_YES = ("sí", "si", "sì", "yes", "tak", "true", "1", "oui", "ja")
_SECTION = ("detalles", "details", "dettagli", "szczegół", "host", "panel", "anfitri", "relator")


def load_zoom(path: str) -> tuple[ZoomSummary, list[ZoomAttendee]]:
    rows = _read_csv_rows(path)
    summary = ZoomSummary()

    # --- summary block: header row with 'registered' + ('unique' or 'peak') ---
    for i, row in enumerate(rows):
        if i + 1 >= len(rows):
            break
        hl = [(c or "").strip().lower() for c in row]
        if _hcol(hl, *_C["registered"]) is not None and (
                _hcol(hl, *_C["unique"]) is not None or _hcol(hl, *_C["peak"]) is not None):
            val = rows[i + 1]

            def g(key, cast=str):
                j = _hcol(hl, *_C[key])
                if j is None or j >= len(val):
                    return 0 if cast is int else ""
                return _num(val[j]) if cast is int else val[j].strip()

            summary.topic = g("topic")
            summary.registered = g("registered", int)
            summary.unique_viewers = g("unique", int)
            summary.total_users = g("total", int)
            summary.peak_concurrent = g("peak", int)
            summary.actual_duration_min = g("duration", int)
            break

    # --- attendee section: header with first-name + last-name + email columns ---
    att_idx = None
    for i, row in enumerate(rows):
        hl = [(c or "").strip().lower() for c in row]
        fn = _hcol(hl, *_C["firstname"]) or next((j for j, h in enumerate(hl) if h in ("nombre", "nome")), None)
        if _hcol(hl, *_C["lastname"]) is not None and _hcol(hl, *_C["email"]) is not None and fn is not None:
            att_idx = i
            break

    merged: dict[str, ZoomAttendee] = {}
    if att_idx is not None:
        hl = [(c or "").strip().lower() for c in rows[att_idx]]
        c_att = _hcol(hl, *_C["attended"])
        c_email = _hcol(hl, *_C["email"])
        c_country = _hcol(hl, *_C["country"])
        c_uname = _hcol(hl, *_C["uname"])
        c_fn = next((j for j, h in enumerate(hl) if h in ("nombre", "nome", "first name", "imię")), None)
        c_ln = _hcol(hl, *_C["lastname"])
        c_time = next((j for j, h in enumerate(hl)
                       if "minut" in h and ("sesi" in h or "sessi" in h or "session" in h)), None)

        def cell(row, j):
            return row[j].strip() if (j is not None and j < len(row)) else ""

        for row in rows[att_idx + 1:]:
            if not row or not any(c.strip() for c in row):
                continue
            if (row[0] or "").strip().lower().startswith(_SECTION):   # next section => stop
                break
            if c_att is not None:
                a = cell(row, c_att).lower()
                if a and a not in _YES:                               # skip no-shows
                    continue
            email = cell(row, c_email).lower()
            if not email:
                continue
            mins = _num(cell(row, c_time))
            name = cell(row, c_uname) or " ".join(p for p in (cell(row, c_fn), cell(row, c_ln)) if p)
            country = cell(row, c_country)
            if email in merged:
                merged[email].minutes += mins
                merged[email].sessions += 1
            else:
                merged[email] = ZoomAttendee(email=email, name=name, country=country, minutes=mins, sessions=1)

    return summary, list(merged.values())


def live_analysis(summary: ZoomSummary, attendees: list[ZoomAttendee]) -> dict:
    n = len(attendees)
    mins = [a.minutes for a in attendees]
    avg = round(sum(mins) / n, 1) if n else 0.0

    # Two bucketing schemes the old decks used; we expose both, report picks one.
    ge30 = sum(1 for m in mins if m >= 30)
    buckets_4 = {
        "0-15": sum(1 for m in mins if m <= 15),
        "16-30": sum(1 for m in mins if 16 <= m <= 30),
        "31-45": sum(1 for m in mins if 31 <= m <= 45),
        ">45": sum(1 for m in mins if m > 45),
    }
    country_counts = Counter(normalize_country(a.country) for a in attendees if a.country)
    top_country, top_n = (country_counts.most_common(1)[0] if country_counts else ("", 0))

    return {
        "unique_attendees": n,
        "avg_minutes": avg,
        "pct_ge_30min": _pct(ge30, n),
        "pct_lt_30min": _pct(n - ge30, n),
        "buckets_4": {k: {"count": v, "pct": _pct(v, n)} for k, v in buckets_4.items()},
        "top_country": top_country,
        "top_country_pct": _pct(top_n, n),
        "peak_concurrent": summary.peak_concurrent,
        "attendee_countries_represented": len(country_counts),
    }


# --------------------------------------------------------------------------
# Top-level: compute everything for one webinar
# --------------------------------------------------------------------------
def build_stats(registration_csv: str, zoom_csv: str) -> dict:
    regs = load_registrations(registration_csv)
    summary, attendees = load_zoom(zoom_csv)
    live = live_analysis(summary, attendees)

    n_reg = len(regs)
    companies = company_list(regs)
    # country distribution + regions come from the ZOOM ATTENDEES (where they
    # actually joined from), normalised to English — NOT the registration list.
    att_countries = [normalize_country(a.country) for a in attendees if a.country]
    countries = _distribution(att_countries, top=50)
    countries["distinct"] = len(set(att_countries))
    region_counts = Counter(region_of(c) for c in att_countries)
    reg_countries_distinct = len({r.country for r in regs if r.country})

    attendance_rate = _pct(live["unique_attendees"], n_reg)

    return {
        "key_facts": {
            "registrations": n_reg,
            "companies": len(companies),
            "countries": reg_countries_distinct,          # reach = countries registered
            "live_attendees": live["unique_attendees"],
            "attendance_rate_pct": attendance_rate,
        },
        "countries": countries,
        "regions": [
            {"label": k, "count": v, "pct": _pct(v, sum(region_counts.values()))}
            for k, v in region_counts.most_common()
        ],
        "industries": _distribution((r.industry for r in regs), top=15),
        "job_titles": _distribution((r.job_title for r in regs), top=40),
        "companies": companies,
        "live": live,
        "zoom_summary": asdict(summary),
    }


if __name__ == "__main__":
    import json
    import sys

    base = r"C:\Users\Belén\OneDrive - ATA\Desktop\Webinar reports"
    reg = sys.argv[1] if len(sys.argv) > 1 else base + r"\c045 registros.csv"
    zoom = sys.argv[2] if len(sys.argv) > 2 else base + r"\attendee_89515278676_2026_05_28.csv"

    stats = build_stats(reg, zoom)

    kf = stats["key_facts"]
    print("=== KEY FACTS ===")
    print(f"  Registrations : {kf['registrations']}")
    print(f"  Companies     : {kf['companies']}")
    print(f"  Countries     : {kf['countries']}")
    print(f"  Live attendees: {kf['live_attendees']}")
    print(f"  Attendance    : {kf['attendance_rate_pct']}%")

    print("\n=== REGIONS ===")
    for r in stats["regions"]:
        print(f"  {r['label']:15} {r['count']:4}  {r['pct']}%")

    print("\n=== TOP COUNTRIES ===")
    for r in stats["countries"]["rows"][:10]:
        print(f"  {r['label']:20} {r['count']:4}  {r['pct']}%")

    print("\n=== INDUSTRIES ===")
    for r in stats["industries"]["rows"]:
        print(f"  {r['label']:40} {r['count']:4}  {r['pct']}%")

    print("\n=== LIVE (Zoom) ===")
    for k, v in stats["live"].items():
        print(f"  {k}: {v}")

    print(f"\n=== COMPANIES ({len(stats['companies'])}) ===")
    print("  " + " | ".join(stats["companies"][:40]) + (" ..." if len(stats["companies"]) > 40 else ""))

    print(f"\n=== JOB TITLES (sample of {len(stats['job_titles']['rows'])}) ===")
    print("  " + " | ".join(r["label"] for r in stats["job_titles"]["rows"][:25]))
