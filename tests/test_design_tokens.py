"""T7.1 — DESIGN.md is the design truth, and this test is what keeps it true.

The document names every CSS custom property the app may use; the stylesheet
may declare exactly those properties with exactly those values (both
directions — a token in app.css that DESIGN.md does not name is just as much
drift as a DESIGN.md token the stylesheet dropped). The FORBIDDEN list from
§9 must be carried in the document verbatim: the calm posture is readable
contract, not folklore. Values compare byte-identically; the §9 table is the
source (PLAN-c3 §9 = cycle-1 PLAN §9).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESIGN = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
CSS = (ROOT / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")

# §9's FORBIDDEN row, verbatim, every item named
FORBIDDEN = ["parallax", "scroll effects", "animation libraries (GSAP incl.)",
             "gradients-as-decoration", "glassmorphism", "carousels",
             "hover-lift", "icon fonts"]


def _decls(text):
    """--token -> value, from a CSS-flavoured text (whitespace normalised,
    one value per name; a name redeclared with a different value is drift and
    is caught by the equality assertions below via the first occurrence)."""
    out = {}
    for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;{}\n]+)", text):
        out.setdefault(name, " ".join(value.split()))
    return out


def _doc_token_block():
    """The fenced :root css block of DESIGN.md — the canonical declaration set."""
    blocks = re.findall(r"```css\s*(:root\s*\{[^}]*\})\s*```", DESIGN)
    assert len(blocks) == 1, "DESIGN.md must carry exactly one fenced :root token block"
    return blocks[0]


def test_forbidden_block_present_verbatim():
    assert "FORBIDDEN" in DESIGN
    section = DESIGN.split("FORBIDDEN", 1)[1]
    for item in FORBIDDEN:
        assert item in section, f"FORBIDDEN list in DESIGN.md misses {item!r}"


def test_every_design_token_is_declared_by_the_stylesheet_same_value():
    doc = _decls(_doc_token_block())
    assert doc, "no tokens parsed from DESIGN.md — the gate would be vacuous"
    css = _decls(CSS)
    for name, value in sorted(doc.items()):
        assert name in css, f"{name} is in DESIGN.md but not in app.css"
        assert css[name] == value, f"{name}: DESIGN.md says {value!r}, app.css says {css[name]!r}"


def test_the_stylesheet_declares_no_token_the_design_doc_does_not():
    doc = _decls(_doc_token_block())
    css = _decls(CSS)
    extra = sorted(set(css) - set(doc))
    assert not extra, f"app.css declares tokens DESIGN.md does not name: {extra}"


def test_color_tokens_match_the_plan_table_hexes():
    """The nine §9 colour hexes, hard-pinned here as well: DESIGN.md parsing it
    right is a second claim, this is the contract itself."""
    expected = {"--paper": "#FAF6F1", "--card": "#FFFFFF", "--ink": "#2E2B27",
                "--muted": "#5E5750", "--line": "#E4DCCF", "--accent": "#6B7F65",
                "--link": "#4E6348", "--star": "#B07A2B", "--danger": "#8C4A3F"}
    for name, hexval in expected.items():
        assert name in DESIGN and hexval in DESIGN, f"DESIGN.md table lost {name} {hexval}"
        assert _decls(CSS).get(name, "").upper() == hexval, f"app.css {name} drifted from {hexval}"
