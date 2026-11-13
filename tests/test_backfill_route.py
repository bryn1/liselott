"""T5.6 — POST /backfill, the in-app twin of scripts/enrich_backfill.py.

The cursor contract is the plan's PINNED selection rule (P2-d): rows with
id > `after` ORDER BY id LIMIT n, and `last_id` = the highest id CONSIDERED —
including permanently-failed (enrich_fail=1) rows, so the scan COMPLETES and
never spins on poisoned ground. `after` ≥ max id answers
processed==0, last_id==after: the loop's wrap signal.

ONE mechanism: the route runs enrich_loop.scope_ids + run_pass — the very
functions the CLI drives (their module, not a copy); the pacing/budget is
with_budget; the transports seam is bound HERE for fixtures to replace.
/backfill is tokenless (a same-origin machine POST, T2.5 vocabulary) but
behind the login guard like everything owner-only."""
import sqlite3

import pytest

from app import create_app
from tests.test_browse import PASSWORD, seed_shelf


def no_providers():
    def dead(title, authors):
        from app import enrich
        raise enrich.ProviderUnavailable("fixture: offline")
    return {"libris": dead, "ol": dead, "gb": dead}


def covering_transport():
    """ol answers a policy-passing hit whose cover bytes are a REAL small
    JPEG — the same shape tests/test_add's fixture uses."""
    from tests.test_add import COVER_FIXTURE
    data = COVER_FIXTURE.read_bytes()

    def libris(title, authors):
        return []

    def ol(title, authors):
        return [{"source": "openlibrary", "title": title,
                 "authors": list(authors) or ["Någon"],
                 "isbn13": "9789198559699", "isbn10": None, "year": 2022,
                 "cover_id": 77,
                 "cover_url": "https://covers.openlibrary.org/b/id/77-M.jpg",
                 "subjects": []}]

    return {"libris": libris, "ol": ol, "gb": None}, data


@pytest.fixture()
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    seed_shelf(tmp_path / "liselott.db")
    app = create_app()
    app.testing = True
    client = app.test_client()
    assert client.post("/liselott/satt-loesenord",
                       data={"loesenord": PASSWORD, "bekrafta": PASSWORD}).status_code == 302
    return tmp_path, client, app


def silence(monkeypatch, transports=None, fetch=None, search=None):
    """The seam lives on app.backfill's module attributes (omslag/tillagg
    pattern): transports, http fetch and the OL author search."""
    from app import backfill
    monkeypatch.setattr(backfill, "live_transports",
                        lambda conn: transports or no_providers())
    monkeypatch.setattr(backfill, "pacer", lambda s: None)
    monkeypatch.setattr(backfill, "http_get",
                        fetch or (lambda url, **kw: b""))
    if search is not None:
        monkeypatch.setattr(backfill, "ol_author_search", search)


def missing_count(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return conn.execute("SELECT COUNT(*) FROM book"
                            " WHERE cover_path IS NULL").fetchone()[0]
    finally:
        conn.close()


# ── the pinned cursor ────────────────────────────────────────────────────────
def test_backfill_processes_scope_and_reports_the_pinned_json(shelf, monkeypatch):
    """Scope on the corpus: books 1,3,4,5 lack isbn and/or cover (book 2 has
    both) → processed 4, every cover lands, last_id is the HIGHEST considered
    id (5), remaining drops to 0."""
    tmp, client, _ = shelf
    transports, data = covering_transport()
    silence(monkeypatch, transports,
            fetch=lambda url, **kw: data)
    r = client.post("/liselott/backfill?n=5")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/json")
    got = r.get_json()
    assert got["processed"] == 4
    assert got["new_covers"] == 4
    assert got["new_isbn"] == 4
    assert got["last_id"] == 5
    assert got["remaining_missing_covers"] == missing_count(tmp) == 0


def test_cursor_advances_PAST_poisoned_rows(shelf, monkeypatch):
    """Two enrich_fail=1 rows (id 3 and 5) are still IN scope and examined —
    last_id must pass them (the scan completes; no spinning on poisoned
    ground). With every provider dead nothing new is written and the cursor
    still lands on the highest id considered."""
    tmp, client, _ = shelf
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("UPDATE book SET enrich_fail = 1,"
                 " tried_providers = 'libris,ol,gb' WHERE id IN (3,5)")
    conn.commit()
    conn.close()
    silence(monkeypatch, no_providers())
    got = client.post("/liselott/backfill?n=5").get_json()
    assert got["processed"] == 4 and got["new_covers"] == 0
    assert got["last_id"] == 5           # past the poisoned 3 AND 5


def test_second_call_with_the_cursor_returns_DISJOINT_ids(shelf, monkeypatch):
    """First call n=2 examines ids 1,3 (ORDER BY id LIMIT 2) and hands back
    last_id=3; the second call ?after=3 can only see 4 and 5 — disjoint by the
    cursor, asserted even though NOTHING was written (providers dead), so the
    scope did not shrink out from under the claim."""
    _, client, _ = shelf
    silence(monkeypatch, no_providers())
    first = client.post("/liselott/backfill?n=2").get_json()
    assert first["processed"] == 2 and first["last_id"] == 3
    second = client.post("/liselott/backfill?n=5&after=3").get_json()
    assert second["processed"] == 2 and second["last_id"] == 5


def test_wrap_signal_after_past_everything(shelf, monkeypatch):
    _, client, _ = shelf
    silence(monkeypatch, no_providers())
    got = client.post("/liselott/backfill?after=5").get_json()
    assert got == {"processed": 0, "new_covers": 0, "new_isbn": 0,
                   "last_id": 5, "remaining_missing_covers": 4}


def test_n_above_twenty_is_clamped(shelf, monkeypatch):
    tmp, client, _ = shelf
    conn = sqlite3.connect(tmp / "liselott.db")
    for i in range(6, 36):
        conn.execute("INSERT INTO book (id, title, format, read_year,"
                     " status, book_key, created, updated) VALUES (?,?,?,"
                     " 0, 'read', ?, datetime(), datetime())",
                     (i, f"Extra bok", "bok", f"synthetic-extra-{i}"))
    conn.commit()
    conn.close()
    silence(monkeypatch, no_providers())
    got = client.post("/liselott/backfill?n=50").get_json()
    assert got["processed"] == 20                    # the clamp
    assert got["last_id"] == 21                      # ids 1,3,4,5 + 6..21


# ── ?mode=candidates: the same cursor over the author queue ──────────────────
def authors_of_read_books(tmp):
    conn = sqlite3.connect(tmp / "liselott.db")
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT a.id FROM author a"
            " JOIN book_author ba ON ba.author_id = a.id"
            " JOIN book b ON b.id = ba.book_id AND b.status = 'read'"
            " ORDER BY a.id")]
    finally:
        conn.close()


def test_mode_candidates_uses_the_same_cursor_contract(shelf, monkeypatch):
    """The authors of READ books (3 of them on the corpus) with ≤5 per pass;
    the fixture search answers EACH author with her own book plus a hit that
    repeats an EXISTING title plus one credited to a misspelling — the
    existing title may never enter, and the misspelling must be stored
    canonical (alias chain at INSERT, T1.4)."""
    tmp, client, _ = shelf

    def search(name):
        return [{"title": f"Ny bok om {name}", "isbn13": "9781111111111",
                 "year": 2023,
                 "authors": ["Simona Ahrnsredt" if name.startswith("Kristin")
                             else name]},
                {"title": "Stöld", "authors": ["Ann-Helén Laestadius"],
                 "isbn13": "9789198559699", "year": 2022}]

    silence(monkeypatch, search=search)
    queue = authors_of_read_books(tmp)
    got = client.post("/liselott/backfill?mode=candidates&n=5").get_json()
    assert got["processed"] == len(queue) == 3
    assert got["last_id"] == max(queue)
    assert got["new_candidates"] == 3              # own book per author; Stöld never
    conn = sqlite3.connect(tmp / "liselott.db")
    stored = conn.execute("SELECT DISTINCT author_name FROM candidate"
                          " ORDER BY author_name").fetchall()
    titles = conn.execute("SELECT COUNT(*) FROM candidate WHERE title='Stöld'"
                          ).fetchone()[0]
    conn.close()
    assert ("Simona Ahrnstedt",) in stored           # alias-resolved at INSERT
    assert titles == 0                               # existing titles never enter


def test_mode_candidates_resumes_and_refreshes_at_ninety_days(shelf, monkeypatch):
    """Re-POST inside the 90-day window: the authors are still EXAMINED (the
    cursor contract holds) but nothing is fetched — new_candidates 0. An
    author whose candidates are older than 90 days is fetched again."""
    tmp, client, _ = shelf
    silence(monkeypatch, search=lambda name: [
        {"title": f"Frisk kandidat av {name}", "authors": [name],
         "isbn13": None, "year": None}])
    first = client.post("/liselott/backfill?mode=candidates").get_json()
    assert first["new_candidates"] == 3 and first["fetched_authors"] == 3
    again = client.post("/liselott/backfill?mode=candidates").get_json()
    assert again["processed"] == 3 and again["fetched_authors"] == 0
    conn = sqlite3.connect(tmp / "liselott.db")
    conn.execute("UPDATE candidate SET fetched_at ="
                 " '2020-01-01T00:00:00Z'")            # stale the window
    conn.commit()
    conn.close()
    stale = client.post("/liselott/backfill?mode=candidates").get_json()
    assert stale["fetched_authors"] == 3              # window stale -> re-asked
    # the pool stays STABLE (same author+title re-asked is not a new row):
    assert stale["new_candidates"] == 0


# ── the gate ─────────────────────────────────────────────────────────────────
def test_unauthenticated_backfill_is_302(shelf):
    fresh = shelf[2].test_client()
    r = fresh.post("/liselott/backfill")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/logga-in"


def test_route_runs_the_CLIS_OWN_functions(shelf, monkeypatch):
    """One-mechanism doctrine, pinned: the route must drive
    enrich_loop.scope_ids + run_pass — patch the MECHANISM, watch it work,
    and a route-local copy would sail through this RED."""
    import app.enrich_loop as loop

    calls = []
    real_scope, real_pass = loop.scope_ids, loop.run_pass
    spy_scope = lambda conn, limit=None, after=0: (    # noqa: E731
        calls.append(("scope", limit, after)) or real_scope(conn, limit, after))
    monkeypatch.setattr(loop, "scope_ids", spy_scope)
    silence(monkeypatch, no_providers())
    shelf[1].post("/liselott/backfill?n=2&after=1")
    assert ("scope", 2, 1) in calls
    monkeypatch.setattr(loop, "scope_ids", real_scope)
