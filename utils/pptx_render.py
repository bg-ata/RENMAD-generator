# -*- coding: utf-8 -*-
"""
Flatten a .pptx to per-slide PNGs using PowerPoint COM automation (Windows).

This keeps the editable .pptx as the single source of truth: the PNG assets
(for LinkedIn etc.) are exported from the very same file, so they always match.

Requires PowerPoint installed. On non-Windows hosts a LibreOffice fallback would
be needed (not implemented yet).
"""
from __future__ import annotations

import os


def pptx_to_pngs(pptx_path: str, out_dir: str,
                 width: int = 1920, height: int = 1080) -> list[str]:
    """Export each slide of `pptx_path` to out_dir/slide{N}.png. Returns paths."""
    import win32com.client  # pywin32

    pptx_path = os.path.abspath(pptx_path)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    paths: list[str] = []
    deck = None
    try:
        deck = ppt.Presentations.Open(pptx_path, WithWindow=False)
        for i in range(1, deck.Slides.Count + 1):
            out = os.path.join(out_dir, f"slide{i}.png")
            deck.Slides.Item(i).Export(out, "PNG", width, height)
            paths.append(out)
    finally:
        if deck is not None:
            deck.Close()
        ppt.Quit()
    return paths
