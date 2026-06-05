# -*- coding: utf-8 -*-
"""Free, offline company-name cleanup + relevant-org scoring (no paid API).

- alias dictionary (aliases.json) that grows as colleagues fix names
- heuristic casing/acronym/legal-suffix cleanup
- fuzzy de-duplication (difflib, stdlib)
- seniority + notability scoring for the 'most relevant orgs' shortlist
"""
from __future__ import annotations
import json
import os
import re
from difflib import SequenceMatcher

_HERE = os.path.dirname(os.path.abspath(__file__))
ALIAS_PATH = os.path.join(_HERE, "aliases.json")

ACRONYMS = {"EDP", "ABB", "RWE", "NHOA", "RP", "EDF", "ENI", "SMA", "GE", "FRV", "ACWA", "DNV",
            "BESS", "EPC", "IPP", "PV", "KPMG", "PWC", "BBVA", "BNP", "IFC", "EBRD", "AES", "MN8",
            "RES", "WSP", "CVE", "BP", "TSK", "OHLA", "ABO", "SIG", "EGP", "FAEN", "FEUP", "AMM"}
_LEGAL = re.compile(r"[\s,]*\b(S\.?L\.?U?|S\.?A\.?U?|S\.?p\.?A|GmbH|Ltd|LLC|Inc|B\.?V|S\.?r\.?l|"
                    r"Lda|AB|AG|Oy|N\.?V|Pty|Co|Corp|Holdings?)\b\.?$", re.I)


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _load():
    try:
        return json.load(open(ALIAS_PATH, encoding="utf-8"))
    except Exception:
        return {}


ALIASES = _load()


def add_alias(raw: str, canonical: str):
    k = norm_key(raw)
    if k and canonical and ALIASES.get(k) != canonical:
        ALIASES[k] = canonical
        try:
            json.dump(ALIASES, open(ALIAS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        except Exception:
            pass


def _tok(t: str) -> str:
    if not t:
        return t
    if t.upper() in ACRONYMS or (len(t) <= 3 and t.isalpha()):
        return t.upper()
    return t[:1].upper() + t[1:]


def clean_name(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip(" .,"))
    n = _LEGAL.sub("", n).strip(" .,-")
    if not n:
        return ""
    if n.isupper() or n.islower():       # only recase obviously-wrong casing
        n = " ".join("-".join(_tok(p) for p in w.split("-")) for w in n.split(" "))
    return n


def canonical(name: str) -> str:
    return ALIASES.get(norm_key(name)) or clean_name(name)


def clean_list(names, fuzzy=0.92):
    """Canonicalise, fuzzy-merge near-duplicates, dedupe (keeps first/most-frequent)."""
    out, keys = [], []
    for nm in names:
        c = canonical(nm)
        if not c:
            continue
        k = norm_key(c)
        if any(k == ek or SequenceMatcher(None, k, ek).ratio() > fuzzy for ek in keys):
            continue
        keys.append(k)
        out.append(c)
    return out


NOTABLE = {norm_key(x) for x in [
    "Repsol", "Naturgy", "Engie", "EDP", "Iberdrola", "Endesa", "TotalEnergies", "Acciona", "RWE",
    "BayWa", "Sonnedix", "Voltalia", "Galp", "Statkraft", "Lightsource BP", "Q Energy", "Grenergy",
    "OPDEnergy", "Zelestra", "NHOA Energy", "Hitachi Energy", "Huawei", "ABB", "Siemens", "Fluence",
    "Sungrow", "Trina Solar", "Jinko", "DNV", "Ferrovial", "Elecnor", "Enel", "EDF", "Shell", "BP",
    "Equinor", "Orsted", "Brookfield", "Allianz", "Mapfre", "Swiss Re", "Munich RE", "BBVA",
    "Quintas Energy", "RP-Global", "Nidec", "Wartsila", "Octopus Energy", "Amazon", "Mott MacDonald",
]}


def is_notable(company: str) -> bool:
    k = norm_key(company)
    return any(nk and nk in k for nk in NOTABLE)


_TIERS = [
    (re.compile(r"\b(chief|ceo|cto|coo|cfo|founder|owner|president|partner|managing\s+director|managing\s+partner)\b", re.I), 5),
    (re.compile(r"\b(vp|vice\s+president|head|director|gerente\s+general)\b", re.I), 4),
    (re.compile(r"\b(principal|lead|senior)\b", re.I), 3),
    (re.compile(r"\b(manager|responsable|jefe|gerente)\b", re.I), 2),
]


def seniority_score(title: str) -> int:
    for rx, sc in _TIERS:
        if rx.search(title or ""):
            return sc
    return 1
