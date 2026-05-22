"""
Shared text-wrapping utilities for slide generators.

wrap_title()   — smart title wrap: respects explicit \\n AND tries semantic
                 break points (:, -, –) before falling back to word-by-word.
wrap_words()   — plain word-by-word wrap (for non-title text: roles, etc.)
"""
import re


# Semantic break patterns, tried in priority order.
# Each tuple: (regex pattern, how many chars of the match to keep on line 1)
_TITLE_BREAK_PATTERNS = [
    (re.compile(r':\s?'),        True),   # colon  → "A:" / "B"
    (re.compile(r'\s[-–—]\s?'), False),  # dash   → "A" / "B"  (dash dropped)
]


def wrap_words(draw, text, font, max_w):
    """Standard word-by-word wrap. Returns a list of line strings."""
    words = text.split()
    if not words:
        return []
    lines, cur = [], ""
    for w in words:
        candidate = (cur + " " + w).strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return lines or [""]


def _break_one_segment(draw, text, font, max_w):
    """
    Wrap a single no-newline segment intelligently.

    Priority:
    1. Fits on one line → return as-is.
    2. Try each semantic break pattern; use the FIRST occurrence where
       line 1 fits (≤ max_w).  The break point is the natural separator
       (colon, dash).
    3. Fall back to word-by-word.
    """
    text = text.strip()
    if not text:
        return []
    if draw.textbbox((0, 0), text, font=font)[2] <= max_w:
        return [text]

    for pattern, keep_sep_on_line1 in _TITLE_BREAK_PATTERNS:
        for m in pattern.finditer(text):
            if keep_sep_on_line1:
                # e.g. ': ' → keep ':' on line 1
                p1 = text[:m.start() + 1].rstrip()   # "A:"
                p2 = text[m.end():].lstrip()           # "B"
            else:
                # e.g. ' - ' → drop the separator, put rest on line 2
                p1 = text[:m.start()].rstrip()         # "A"
                p2 = text[m.end():].lstrip()            # "B"

            if not p1 or not p2:
                continue
            if draw.textbbox((0, 0), p1, font=font)[2] <= max_w:
                # Line 1 fits → accept this break; word-wrap remainder
                return [p1] + wrap_words(draw, p2, font, max_w)

    # No semantic break worked → plain word-wrap
    return wrap_words(draw, text, font, max_w)


def wrap_title(draw, text, font, max_w, max_lines=3):
    """
    Smart title wrap for slide generators.

    · Explicit \\n in `text` → forced line break (user presses Enter in the
      title field to control exactly where the slide breaks).
    · Within each segment, tries semantic breaks (:, -, –) before
      falling back to word-by-word.
    · Returns at most `max_lines` lines.
    """
    lines = []
    for seg in text.split("\n"):
        seg = seg.strip()
        if seg:
            lines.extend(_break_one_segment(draw, seg, font, max_w))
    return lines[:max_lines] if lines else [""]
