"""
Gender inference from first name — used to pick Moderador / Moderadora.
Returns 'f', 'm', or '' (unknown → fall back to Moderador/a).
Accent-insensitive. Covers Spanish, Italian, Polish names common in RENMAD events.
"""
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Female names that do NOT end in 'a' (would otherwise be missed)
_FEMALE = {
    "belen", "carmen", "pilar", "ester", "esther", "mercedes", "montserrat",
    "isabel", "raquel", "maribel", "mar", "luz", "paz", "ines", "amparo",
    "lourdes", "nieves", "rocio", "sol", "ruth", "miriam", "naomi", "judith",
    "leire", "edurne", "amaia", "nerea", "nagore", "miren", "itziar", "olatz",
    "maialen", "ainhoa", "june", "alazne", "garazi", "oihane", "beatriz",
    "trinidad", "rosario", "dolores", "milagros", "encarnacion", "inmaculada",
    "concepcion", "asuncion", "remedios", "flor", "noemi", "maider", "uxue",
    "noel", "rachel", "abigail", "margaret", "helen", "karen", "susan",
    "kathleen", "marzena", "agnieszka", "katarzyna", "monika", "dorota",
    "joanna", "beata", "elzbieta", "krystyna", "halina",
}

# Male names that end in 'a' or have unusual endings (would otherwise be missed)
_MALE = {
    "luca", "andrea", "nikita", "battista", "barnaba",
    "ezra", "joshua", "noah", "jonah",
    # Catalan / regional Spanish male names
    "josep", "andreu", "lluis", "joan", "jordi",
    # Names ending in 's' that look female or ambiguous after normalization
    "andres", "marcos", "jesus", "moises", "elias",
    # Polish male names
    "bartosz", "lukasz", "tomasz", "maciej", "grzegorz",
    "krzysztof", "przemyslaw", "radoslaw", "slawomir",
}


def guess_gender(full_name: str) -> str:
    """Return 'f', 'm', or '' (unknown)."""
    parts = full_name.strip().split()
    if not parts:
        return ""
    fn = _norm(parts[0])
    if fn in _FEMALE:
        return "f"
    if fn in _MALE:
        return "m"
    if fn.endswith("a"):
        return "f"
    # Common male endings (after accent-stripping)
    if fn.endswith(("o", "os", "el", "al", "an", "on", "or", "er", "us", "is", "ix",
                     "io", "ian", "uel", "ael", "iel")):
        return "m"
    return ""


def moderator_label(full_name: str, strings: dict) -> str:
    """Return the correctly gendered moderator label in ALL CAPS."""
    g = guess_gender(full_name)
    if g == "f":
        return strings.get("moderator_f", "Moderadora").upper()
    if g == "m":
        return strings.get("moderator_m", "Moderador").upper()
    return strings.get("moderator", "Moderador/a").upper()
