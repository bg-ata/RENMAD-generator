"""Parse free-form session text into structured speaker + event data."""
import re

# ── Patterns ──────────────────────────────────────────────────────────────────

_DATE_RE = re.compile(
    r"\b\d{1,2}\s+(?:de\s+)?"
    r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre|"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december)"
    r"(?:\s+(?:de\s+)?\d{4})?\b",
    re.IGNORECASE,
)

# Catches: 11h, 11:00h, 11.00h, 11:00, 11:00h CET, 11:00 CEST, 11am, 11:00pm
# Note: timezone is captured separately via _extract_time_with_tz() because
# separators like "–" between a time range and the timezone break the inline match.
_TIME_RE = re.compile(
    r"\b\d{1,2}[:\.]?\d{0,2}\s*h(?:oras?)?\s*(?:CET|CEST|GMT|UTC)?\b"
    r"|\b\d{1,2}:\d{2}\s*(?:CET|CEST|GMT|UTC|am|pm)?\b"
    r"|\b\d{1,2}\s*(?:am|pm)\b",
    re.IGNORECASE,
)

_TZ_RE = re.compile(r"\b(CET|CEST|GMT|UTC(?:[+-]\d{1,2})?)\b", re.IGNORECASE)

_ONLINE_RE = re.compile(
    r"\b(online|virtual|webinar|streaming|zoom|teams|digital)\b", re.IGNORECASE
)

_CITY_RE = re.compile(
    r"\b(madrid|barcelona|bilbao|valencia|sevilla|lisboa|lisbon|london|berlin|"
    r"paris|amsterdam|rome|roma|warsaw|varsovia|presencial|in[\-\s]person)\b",
    re.IGNORECASE,
)

_MOD_PREFIXES = ("Moderador:", "Moderadora:", "Moderador/a:", "Moderator:")

# Particles that can appear lowercase inside a proper name
_NAME_PARTICLES = {"de", "del", "van", "von", "le", "la", "el", "al", "y",
                   "und", "di", "da", "dos", "das", "bin", "binti", "mac", "mc"}


def _looks_like_name(s: str) -> bool:
    """Return True only if *s* plausibly looks like a person's name.

    Rules:
    - 2–5 words  (single words are likely a city / keyword / random word)
    - No digits  (dates / phone numbers / codes are not names)
    - Max 60 characters
    - Every non-particle word starts with an uppercase letter
    """
    s = s.strip()
    if not s or len(s) > 60:
        return False
    if any(c.isdigit() for c in s):
        return False
    words = s.split()
    if len(words) < 2 or len(words) > 5:
        return False
    for w in words:
        clean = w.strip("'\".()")
        if clean.lower() in _NAME_PARTICLES:
            continue
        if not clean or not clean[0].isupper():
            return False
    return True


def _extract_time_with_tz(line: str) -> str:
    """Extract the first time token from *line*, then append a timezone if one
    appears anywhere in the same line but was not captured inline.

    This handles formats like '10:00h – 12:00h CET' where the separator between
    the time and the timezone breaks the regex's inline timezone group.
    """
    m = _TIME_RE.search(line)
    if not m:
        return ""
    time_str = m.group(0).strip()
    # If timezone is already part of the match, we're done
    if _TZ_RE.search(time_str):
        return time_str
    # Otherwise look for a timezone anywhere in the line and append it
    tz_m = _TZ_RE.search(line)
    if tz_m:
        time_str = time_str + " " + tz_m.group(1).upper()
    return time_str

# URL / CTA patterns
_URL_RE = re.compile(
    r'(?:https?://\S+|www\.\S+|\S+\.(?:com|es|org|net|io|eu)/\S*)',
    re.IGNORECASE,
)
_CTA_PREFIX_RE = re.compile(
    r'(?:m[aá]s\s+info(?:rmaci[oó]n)?|registr[aeo]te?|inscripci[oó]n|'
    r'sign[\s\-]?up|link|enlace|cta|url|regist(?:er|ro)|'
    r'accede|acc[eé]s(?:o|s)?)\s*[:→–\-]\s*(.+)',
    re.IGNORECASE,
)


def _is_metadata_line(line: str) -> bool:
    """True if the line is clearly event metadata (date/time/location), not a speaker."""
    return bool(_DATE_RE.search(line) or _TIME_RE.search(line))


def _simple_parse(text: str) -> dict:
    lines = [l.strip() for l in text.strip().splitlines()]
    title        = ""
    date_str     = ""
    time_str     = ""
    location_str = ""
    cta_url      = ""
    speaker_lines = []

    # Track when the title block has ended. A title can span multiple lines
    # until we hit (a) a blank line or (b) a line that looks like metadata,
    # a CTA/URL, or a speaker entry. Without this, multi-line titles like
    # "Distribución y demanda:\nel dilema de la bancabilidad…" lose the 2nd line.
    title_open = True

    for line in lines:
        if not line:
            # Blank line ends the title block
            title_open = False
            continue
        if line.startswith(("•", "-", "·", "*")):
            continue

        # First non-empty non-bullet line = session title
        if not title:
            title = line
            continue

        # ── Multi-line title continuation ────────────────────────────────
        # Append to title only if we haven't yet hit a blank line and the
        # current line isn't metadata, a CTA/URL, or a speaker entry.
        if title_open:
            looks_metadata = _is_metadata_line(line)
            looks_cta = bool(_CTA_PREFIX_RE.match(line)) or bool(_URL_RE.search(line))
            looks_speaker = (
                "," in line
                and _looks_like_name(line.split(",")[0].strip())
            )
            if not looks_metadata and not looks_cta and not looks_speaker:
                title = title + "\n" + line
                continue
            # Otherwise the title block has implicitly ended
            title_open = False

        # CTA / URL detection — check before speaker parsing
        if not cta_url:
            # "Regístrate en: www...." style — store the FULL line as CTA text
            m = _CTA_PREFIX_RE.match(line)
            if m:
                cta_url = line.strip()   # keep full label + URL for display
                continue
            # bare URL line
            if _URL_RE.fullmatch(line.strip()):
                cta_url = line.strip()
                continue
            # URL embedded in a non-speaker line
            if "," not in line:
                m = _URL_RE.search(line)
                if m:
                    cta_url = line.strip()   # keep full line so label is preserved
                    continue

        # Always try to extract metadata from every line
        if not date_str:
            m = _DATE_RE.search(line)
            if m:
                date_str = m.group(0).strip()

        if not time_str:
            time_str = _extract_time_with_tz(line)

        if not location_str:
            m = _ONLINE_RE.search(line)
            if m:
                location_str = m.group(1).capitalize()

        if not location_str:
            m = _CITY_RE.search(line)
            if m:
                location_str = m.group(1).capitalize()

        # Skip this line for speaker parsing if it looks like event metadata
        if _is_metadata_line(line):
            continue

        # Skip lines with no comma (can't be "Name, Title, Company")
        if "," not in line:
            continue

        speaker_lines.append(line)

    # Handle speakers written as "A / B / C" on one line
    expanded = []
    for line in speaker_lines:
        if " / " in line:
            expanded.extend(p.strip() for p in line.split(" / "))
        else:
            expanded.append(line)

    speakers = []
    for line in expanded:
        is_mod = False
        for prefix in _MOD_PREFIXES:
            if line.lower().startswith(prefix.lower()):
                line   = line[len(prefix):].strip()
                is_mod = True
                break
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        name = parts[0]
        # Reject lines whose first segment doesn't look like a person's name
        # (catches pasted meeting notes, sentences, date lines with commas, etc.)
        if not _looks_like_name(name):
            continue
        company = parts[-1]
        title_s = ", ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
        speakers.append({"name": name, "title": title_s,
                         "company": company, "is_moderator": is_mod})

    return {"title": title, "speakers": speakers,
            "date_str": date_str, "time_str": time_str,
            "location": location_str, "cta_url": cta_url}


# ── Public entry point ────────────────────────────────────────────────────────

def parse_session(text: str) -> dict:
    return _simple_parse(text)
