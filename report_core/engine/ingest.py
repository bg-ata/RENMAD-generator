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


def load_zoom(path: str) -> tuple[ZoomSummary, list[ZoomAttendee]]:
    rows = _read_csv_rows(path)
    summary = ZoomSummary()

    # --- summary block: header row "Tema,..." followed by its value row ---
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Tema" and i + 1 < len(rows):
            hdr, val = row, rows[i + 1]
            idx = {h.strip(): j for j, h in enumerate(hdr)}

            def g(name, cast=str):
                j = idx.get(name)
                if j is None or j >= len(val):
                    return cast() if cast is not str else ""
                raw = val[j].strip()
                if cast is int:
                    m = re.search(r"\d+", raw)
                    return int(m.group()) if m else 0
                return raw

            summary.topic = g("Tema")
            summary.registered = g("N.º inscritos", int)
            summary.unique_viewers = g("Espectadores exclusivos", int)
            summary.total_users = g("Usuarios totales", int)
            summary.peak_concurrent = g("Vistas simultáneas máximas", int)
            summary.actual_duration_min = g("Duración real (minutos)", int)
            break

    # --- attendee block: header "...,Nombre,Apellido,...,Tiempo en la sesión..." ---
    # The attendee section is the one whose header contains both "Nombre" and
    # "Apellido" (host/panelist sections omit those split-name columns).
    att_header_idx = None
    for i, row in enumerate(rows):
        joined = ",".join(row)
        if "Nombre" in row and "Apellido" in row and "Tiempo en la sesión (minutos)" in joined:
            att_header_idx = i
            break

    merged: dict[str, ZoomAttendee] = {}
    if att_header_idx is not None:
        hdr = rows[att_header_idx]
        idx = {h.strip(): j for j, h in enumerate(hdr)}

        def col(row, name):
            j = idx.get(name)
            return row[j].strip() if (j is not None and j < len(row)) else ""

        for row in rows[att_header_idx + 1:]:
            if not row or not any(c.strip() for c in row):
                continue
            # next section marker ("Detalles de ...") => stop
            if row[0].strip().startswith("Detalles"):
                break
            attended = col(row, "Asistió")
            if attended.lower() not in ("sí", "si", "yes"):
                continue
            email = (col(row, "Correo electrónico") or col(row, "Correo")).lower().strip()
            if not email:
                continue
            mins_raw = col(row, "Tiempo en la sesión (minutos)")
            mins = int(re.search(r"\d+", mins_raw).group()) if re.search(r"\d+", mins_raw) else 0
            name = col(row, "Nombre de usuario (nombre original)") or \
                   " ".join(p for p in (col(row, "Nombre"), col(row, "Apellido")) if p)
            country = col(row, "Nombre de país/región")
            if email in merged:
                merged[email].minutes += mins
                merged[email].sessions += 1
            else:
                merged[email] = ZoomAttendee(email=email, name=name, country=country,
                                             minutes=mins, sessions=1)

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
    country_counts = Counter(a.country for a in attendees if a.country)
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
    countries = _distribution((r.country for r in regs), top=50)
    region_counts = Counter(region_of(r.country) for r in regs if r.country)

    attendance_rate = _pct(live["unique_attendees"], n_reg)

    return {
        "key_facts": {
            "registrations": n_reg,
            "companies": len(companies),
            "countries": countries["total"] and len({r.country for r in regs if r.country}),
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
