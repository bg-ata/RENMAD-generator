# -*- coding: utf-8 -*-
"""Tiny on-disk library of the last few generated reports (keep most recent 5)."""
from __future__ import annotations
import json
import os
import shutil
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(_REPO, "saved_reports")
IDX = os.path.join(LIB, "index.json")
MAX = 5


def _load():
    try:
        return json.load(open(IDX, encoding="utf-8"))
    except Exception:
        return []


def _write(idx):
    os.makedirs(LIB, exist_ok=True)
    json.dump(idx, open(IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def save_report(pptx_path, cover_png, meta):
    os.makedirs(LIB, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = "%s_%s" % (ts, os.path.basename(pptx_path))
    shutil.copy2(pptx_path, os.path.join(LIB, fname))
    cov = ""
    if cover_png and os.path.exists(cover_png):
        cov = "%s_cover.png" % ts
        shutil.copy2(cover_png, os.path.join(LIB, cov))
    idx = _load()
    idx.insert(0, {"file": fname, "cover": cov, "title": meta.get("title", ""),
                   "lang": meta.get("lang", ""), "when": ts})
    for old in idx[MAX:]:                       # prune beyond the cap
        for f in (old.get("file"), old.get("cover")):
            if f:
                try:
                    os.remove(os.path.join(LIB, f))
                except Exception:
                    pass
    idx = idx[:MAX]
    _write(idx)
    return idx


def list_reports():
    return _load()


def path_of(entry):
    return os.path.join(LIB, entry["file"])


def cover_of(entry):
    return os.path.join(LIB, entry["cover"]) if entry.get("cover") else None
