"""MC 12493 — the owner's edit entry is ALWAYS there (M9e edit-path fix).

The defect: the ONE owner link to `/redigera/<id>` sat inside the
`inloggad() and not bok.has_cover` figcaption of `bok.html`. Wave W16 covered
723 of 724 books, so that branch stopped painting and the owner lost Edit /
Inställningar / Ta bort entirely — with it the rating door she needs on her
own pages (owner ruling, verbatim: "Ai list refreshes each 20 books graded",
so grading must be reachable, and the bok page is where it lives).

The fix is a COPY switch in that ONE figcaption slot — `inloggad()` is the
only gate: a covered book paints a quiet "Redigera", a coverless book keeps
the action copy "Omslag saknas — fixa" (§9's fix-me hint, unchanged). No new
widget beside the slot, no new route, no authz change: the entry opens the
same edit page the coverless path always opened.

THE FOUR LEGS, named as the card names them:

1. `test_owner_bok_page_with_cover_carries_the_edit_entry` — RED at 3dfe2b4
   (her covered fixture row carried no `/redigera` link at all).
2. `test_owner_bok_page_without_cover_keeps_the_action_copy` — the copy the
   hint always carried, in the same single slot.
3. `test_anonymous_bok_page_is_the_pinned_page` — the public bytes, MEASURED
   at 3dfe2b4 before one line was edited (the MC 12522 idiom: the `?v=`
   version token is normalized away, every other byte pinned; re-render
   stable, and fixture-independent — the same numbers fall out with
   `konfigurerad`'s two private rows added, since a single book page carries
   no shelf rows). This is the red line the fix may not cross.
4. `test_public_shelf_and_landing_pins_are_untouched` — the sealed MC 12522 /
   MC 12551 pins IMPORTED from tests/test_public_filter, not re-measured here.

Red-proof duty (fleet rule: a gate that never went red is not a gate) — the
two plants the card names, run against this file: link-shown-for-anon (the
`inloggad()` gate dropped from the figcaption) goes RED on leg 3;
link-dropped-for-covered (the pre-fix `and not bok.has_cover` restored) goes
RED on leg 1. Transcripts alongside this commit's LEDGER row.
"""
import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf
# Reuse, never re-derive: the pin instrument and the SEALED public pins this
# card must leave untouched, plus the fixture they were measured on.
from tests.test_public_filter import (  # noqa: F401  (konfigurerad = fixture)
    FORM_ROW, PIN_LANDING, PIN_OWNER, PIN_SHELF, _pin, konfigurerad)

# MEASURED at 3dfe2b4 (pre-change) with this fixture, `?v=` normalized.
PIN_ANON_BOK_1 = (919, "d2be624baf561c9a5028f149cd1cd6b30c5944a05c890b59b02e805b73f6fcb4")
PIN_ANON_BOK_2 = (1011, "264eb6557e5adaa86b069c59bf6f3ae3f302b2e9bfdab8fe08d27e820019f9e0")

# The whole slot, byte for byte — the shape IS the contract: one figcaption,
# one anchor, the copy switched by has_cover and nothing else.
SLOT_COVERED = '<figcaption><a href="/liselott/redigera/2">Redigera</a></figcaption>'
SLOT_COVERLESS = '<figcaption><a href="/liselott/redigera/1">Omslag saknas — fixa</a></figcaption>'


@pytest.fixture()
def owner_and_anon(tmp_path, monkeypatch):
    """The synthetic shelf, the password set (that POST lands her session),
    and the anonymous visitor — the two postures the contract speaks about."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = create_app()
    app.testing = True
    owner = app.test_client()
    assert owner.post("/liselott/satt-loesenord",
                      data={"loesenord": PASSWORD,
                            "bekrafta": PASSWORD}).status_code == 302
    anon_app = create_app()
    anon_app.testing = True
    return owner, anon_app.test_client()


# ── leg 1 ───────────────────────────────────────────────────────────────────
def test_owner_bok_page_with_cover_carries_the_edit_entry(owner_and_anon):
    """The defect's page: book 2 HAS a cover (covers/2.jpg) and, before the
    fix, carried no door into the edit surface at all."""
    owner, _ = owner_and_anon
    html = owner.get("/liselott/bok/2").text
    assert SLOT_COVERED in html
    assert html.count("<figcaption>") == 1          # the slot, not a widget beside it
    assert "Omslag saknas" not in html              # the fix-me copy stays coverless-only
    # The entry is a DOOR, not decoration — it opens the same edit page the
    # coverless path has always opened (no new route, no new authz).
    edit = owner.get("/liselott/redigera/2")
    assert edit.status_code == 200
    assert 'action="/liselott/redigera/2"' in edit.text


# ── leg 2 ───────────────────────────────────────────────────────────────────
def test_owner_bok_page_without_cover_keeps_the_action_copy(owner_and_anon):
    """Book 1 has no cover: §9's action copy stays exactly as it was, in the
    same one slot, and the grading form rides the same page — the rating door
    the owner ruling depends on ("Ai list refreshes each 20 books graded")."""
    owner, _ = owner_and_anon
    html = owner.get("/liselott/bok/1").text
    assert SLOT_COVERLESS in html
    assert html.count("<figcaption>") == 1
    assert 'name="betyg"' in html                   # rating reachable from here too


# ── leg 3 ───────────────────────────────────────────────────────────────────
def test_anonymous_bok_page_is_the_pinned_page(owner_and_anon):
    """The red line: the public bok page — coverless row AND covered row —
    renders byte for byte as it did before the fix, and carries no door into
    the edit surface (`/redigera/` is a write door, MC 12497)."""
    _, anon = owner_and_anon
    for path, pin in (("/liselott/bok/1", PIN_ANON_BOK_1),
                      ("/liselott/bok/2", PIN_ANON_BOK_2)):
        r = anon.get(path)
        assert r.status_code == 200, path
        assert _pin(r.data) == pin, f"{path} moved from the pre-fix bytes"
        assert b"/redigera/" not in r.data, path


# ── leg 4 ───────────────────────────────────────────────────────────────────
def test_public_shelf_and_landing_pins_are_untouched(konfigurerad):
    """The MC 12522/12551 byte pins, imported and re-run: the anonymous
    landing, the anonymous shelf beside its one filter row, and the owner's
    landing/shelf — none of them is a page this fix touched."""
    owner, anon = konfigurerad
    assert _pin(anon.get("/liselott/").data) == PIN_LANDING
    stripped, hits = FORM_ROW.subn(b"", anon.get("/liselott/bibliotek").data,
                                   count=1)
    assert hits == 1, "the page must carry exactly one filter row"
    assert _pin(stripped) == PIN_SHELF
    for path in ("/liselott/", "/liselott/bibliotek"):
        assert _pin(owner.get(path).data) == PIN_OWNER, path
