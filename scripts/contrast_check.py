#!/usr/bin/env python3
"""T7.2 — the WCAG contrast gate over DESIGN.md's tokens (§9, PLAN-c3 M7).

Reads the token values from DESIGN.md itself (NOT from app.css): the document
is the design truth, and tests/test_design_tokens.py already chains the
stylesheet to it — so this gate checking the document closes the chain. Text
pairs must reach 4.5:1, the star and the accent (interactive/decorative-
meaningful) 3.0:1, exactly as §9 promises.

Usage: python3 scripts/contrast_check.py [DESIGN.md]   → exit 0 all pass,
exit 1 any pair below floor (naming the pair and its ratio), exit 2 usage.
WCAG 2.1 relative luminance + ratio math, stdlib only.
"""
import re
import sys
from pathlib import Path

# (foreground token, background token, floor) — the §9/PLAN T7.2 pair set
PAIRS = [
    ("--ink", "--paper", 4.5),
    ("--muted", "--paper", 4.5),
    ("--link", "--paper", 4.5),
    ("--link", "--card", 4.5),
    ("--danger", "--paper", 4.5),
    ("--star", "--paper", 3.0),
    ("--accent", "--paper", 3.0),
]


def tokens_from_doc(text):
    """--token -> #hex for every colour token DESIGN.md declares."""
    out = {}
    for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9A-Fa-f]{6})", text):
        out[name] = value
    return out


def channel(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexval):
    r, g, b = (int(hexval[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def main(argv):
    if len(argv) > 2:
        print("usage: contrast_check.py [DESIGN.md]", file=sys.stderr)
        return 2
    doc = Path(argv[1] if len(argv) == 2
               else Path(__file__).resolve().parent.parent / "DESIGN.md")
    tokens = tokens_from_doc(doc.read_text(encoding="utf-8"))
    missing = sorted({n for p in PAIRS for n in p[:2]} - set(tokens))
    if missing:
        print(f"FAIL: DESIGN.md declares no colour token for {missing}", file=sys.stderr)
        return 1
    failed = 0
    for fg, bg, floor in PAIRS:
        r = ratio(tokens[fg], tokens[bg])
        ok = r >= floor
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {fg} {tokens[fg]} on {bg} {tokens[bg]}: "
              f"{r:.2f}:1 (floor {floor}:1)")
    if failed:
        print(f"VERDICT: FAIL ({failed} pair(s) below WCAG floor)", file=sys.stderr)
        return 1
    print("VERDICT: PASS (all §9 contrast pairs meet WCAG AA)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
