"""T6.1 — scoring (cycle-1 §8 formula, PLAN-c3 §8 seams pinned).

    score(c) = 0.55 · max A(a) + 0.35 · avg G(g) + 0.10 · is_wishlist
    A(a) = Σ ratings of her rated books by a / (5 · n) ; none → 0
    G(g) = Σ ratings of her rated books in g / (5 · n) ; none → 0

Universe: wishlist books ∪ candidate rows, minus status='read', minus
dismissed ('book:<id>' AND 'cand:<id>'). Ties: author name, then title
(plain string compare, pinned). The hand-computed fixture below is the
red-proof the seams can go RED on: an empty-genre candidate dividing, an
alias author not joining to the canonical, or a reason naming the wrong
rated book each flips this exact list.

Every expected score is computed by hand beside its row — the test pins
the ORDER (kind, id) exactly and the reasons verbatim, so a formula drift
cannot hide inside float tolerance.
"""
import sqlite3
from datetime import datetime, timezone

import pytest
from pytest import approx

from app.db import init_db
from app.recommend import top_recommendations

# (id, title, read_year, date_read, rating, status) — all 'bok'
BOOKS = [
    (1, "Nordanvind", 2024, "2024-05-01", 5, "read"),        # Aino, 5
    (2, "Söderut", 2023, "2023-01-01", 4, "read"),           # Aino, 4
    (3, "Sommarstugan", 2024, "2024-06-06", 2, "read"),      # Bertil, 2
    (4, "Hostregn", 2024, None, None, "read"),               # Bertil, unrated
    (5, "Vinterberget", 2025, None, None, "read"),           # Cecilia, unrated
    (6, "Tid och tid igen", 2024, "2024-04-04", 4, "read"),  # Tilde, 4 (newest)
    (7, "Tid för alltid", 2023, None, 4, "read"),            # Tilde, 4, no date
    (8, "Tid att leva", 2023, "2023-03-03", 4, "read"),      # Tilde, 4, older
    (20, "Kvällsboken", 0, None, None, "wishlist"),          # w1: Aino + Krim
    (21, "Nattboken", 0, None, None, "wishlist"),            # w2: Cecilia + Rom
    (22, "Morgonboken", 0, None, None, "wishlist"),          # w3: Bertil only
    (23, "Redan läst", 2024, "2024-01-02", 5, "read"),       # would top the
]                                                              # list if READ
BOOK_AUTHORS = {1: [1], 2: [1], 3: [2], 4: [2], 5: [3],
                6: [4], 7: [4], 8: [4], 20: [1], 21: [3], 22: [2], 23: [1]}
BOOK_GENRES = {1: ["Kriminalitet"], 3: ["Romantik"], 20: ["Kriminalitet"],
               21: ["Romantik"]}

AUTHORS = {1: "Aino A", 2: "Bertil B", 3: "Cecilia C", 4: "Tilde T"}
ALIAS = {"Bertil B-stavning": 2}

# candidate rows: (id, title, author_name) — the table carries no genres, so
# EVERY cand row runs the avg-over-empty-set := 0 seam.
CANDIDATES = [
    (1, "Kändis bok ett", "Aino A"),               # c1, dismissed below
    (2, "Alias kandidaten", "Bertil B-stavning"),  # alias → canonical A=0.4
    (3, "Helt okänd", "Okänd Författare"),         # unresolvable → A=0
    (4, "Cecílias bok", "Cecilia C"),              # author known, unrated
    (5, "Tiden löper", "Tilde T"),                 # tie→newest date, NULL last
    (6, "A-Anna", "Okänd Författare"),             # title tie-break legs
    (7, "B-Bertil", "Okänd Författare"),
]


def score_db(db_path):
    """The whole corpus through the REAL schema — hand-written inserts,
    corpus-free (§13): this test runs in any clone."""
    conn = sqlite3.connect(db_path)
    init_db(conn)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for author_id, name in AUTHORS.items():
        conn.execute("INSERT INTO author (id, name) VALUES (?,?)",
                     (author_id, name))
    for alias, author_id in ALIAS.items():
        conn.execute("INSERT INTO author_alias (alias, author_id)"
                     " VALUES (?,?)", (alias, author_id))
    for (bid, title, read_year, date_read, rating, status) in BOOKS:
        conn.execute(
            "INSERT INTO book (id, title, format, read_year, date_read,"
            " rating, status, book_key, created, updated) VALUES (?,?,?,"
            " ?,?,?,?, ?, ?, ?)",
            (bid, title, "bok", read_year, date_read, rating, status,
             f"key-{bid}", now, now))
        for author_id in BOOK_AUTHORS[bid]:
            conn.execute("INSERT INTO book_author (book_id, author_id)"
                         " VALUES (?,?)", (bid, author_id))
        for name in BOOK_GENRES.get(bid, []):
            conn.execute("INSERT OR IGNORE INTO genre (name) VALUES (?)",
                         (name,))
            gid = conn.execute("SELECT id FROM genre WHERE name = ?",
                               (name,)).fetchone()[0]
            conn.execute("INSERT OR IGNORE INTO book_genre (book_id,"
                         " genre_id) VALUES (?,?)", (bid, gid))
    for cid, title, author_name in CANDIDATES:
        conn.execute("INSERT INTO candidate (id, title, author_name,"
                     " fetched_at) VALUES (?,?,?,?)",
                     (cid, title, author_name, now))
    conn.commit()
    return conn


# ── the exact ordered list, hand-computed ────────────────────────────────────
def test_exact_ordered_top12_with_both_dismissals(tmp_path):
    """Dismissed: 'cand:1' (Aino's candidate, 0.513 — would sit second) and
    'book:21' (the Romantik wish, 0.24). Hand-computed survivors — note
    A(Aino) = (5+4+5)/15 = 14/15: book 23 is READ (never listed) yet HER
    RATING of it is still taste signal, exactly as §8 words A(a):

      20  0.55·14/15 + 0.35·1.0 + 0.10 = 0.963…  Aino, Krim 5/5
       5  0.55·0.8                    = 0.440    Tilde 12/15, no genres
      22  0.55·0.4           + 0.10   = 0.320    Bertil 2/5, no genres
       2  0.55·0.4                    = 0.220    alias-resolved Bertil 2/5
       4  0.0  Cecilia known, unrated — ties break on author name…
       6  0.0  …Cecilia C < Okänd Författare…
       7  0.0  …then title among the three Okänd rows…
       3  0.0  A-Anna < B-Bertil < Helt okänd.
    """
    conn = score_db(tmp_path / "t.db")
    conn.execute("INSERT INTO dismissed (key, ts) VALUES ('cand:1','x')")
    conn.execute("INSERT INTO dismissed (key, ts) VALUES ('book:21','x')")
    conn.commit()
    got = top_recommendations(conn, 12)
    assert [(item["kind"], item["id"]) for item in got] == [
        ("book", 20), ("cand", 5), ("book", 22), ("cand", 2),
        ("cand", 4), ("cand", 6), ("cand", 7), ("cand", 3),
    ]
    assert [item["score"] for item in got] == approx(
        [0.55 * 14 / 15 + 0.35 + 0.10, 0.44, 0.32, 0.22, 0.0, 0.0, 0.0, 0.0])
    conn.close()


def test_read_status_never_recommended(tmp_path):
    """Book 23 (Aino, rated 5, status 'read') would score above the whole
    list — a read row is not a candidate, ever (the §8 minus-clause)."""
    conn = score_db(tmp_path / "t.db")
    ids = [item["id"] for item in top_recommendations(conn, 12)
           if item["kind"] == "book"]
    assert 23 not in ids and 20 in ids
    conn.close()


def test_n_truncates(tmp_path):
    """Nothing dismissed here: c1 (0.495) is back and sits second; n=2 cuts."""
    conn = score_db(tmp_path / "t.db")
    got = top_recommendations(conn, 2)
    assert [(item["kind"], item["id"]) for item in got] == [
        ("book", 20), ("cand", 1)]
    conn.close()


# ── the pinned seams (PLAN-c3 §8) ────────────────────────────────────────────
def test_candidate_empty_genres_is_zero_not_division(tmp_path):
    """No candidate row carries a genre; the 0.35 lane must be exactly 0 —
    cand 5 = 0.55·0.8 = 0.44 with nothing added, no crash, no division (the
    seam's avg-over-the-empty-set := 0, pinned in T6.1's fixture)."""
    conn = score_db(tmp_path / "t.db")
    c5 = next(i for i in top_recommendations(conn, 12)
              if i["kind"] == "cand" and i["id"] == 5)
    assert c5["score"] == approx(0.55 * 0.8)
    conn.close()


def test_candidate_author_alias_resolves_to_canonical(tmp_path):
    """'Bertil B-stavning' is an ALIAS of author 2 (2/5 = 0.4) — the join runs
    through author_alias to the canonical id, so the candidate scores
    0.55·0.4 and its reason names Bertil B (the canonical), never the alias
    spelling."""
    conn = score_db(tmp_path / "t.db")
    c2 = next(i for i in top_recommendations(conn, 12)
              if i["kind"] == "cand" and i["id"] == 2)
    assert c2["score"] == approx(0.55 * 0.4)
    assert c2["reason"] == ('För att du gav ”Sommarstugan” 2 i betyg av '
                            'Bertil B')
    conn.close()


def test_unresolvable_candidate_author_is_zero(tmp_path):
    """'Okänd Författare' is no author at all → A(a)=0 (the seam, pinned): the
    row still renders (score 0.0, no reason line), it never crashes the join."""
    conn = score_db(tmp_path / "t.db")
    c3 = next(i for i in top_recommendations(conn, 12)
              if i["kind"] == "cand" and i["id"] == 3)
    assert c3["score"] == approx(0.0)
    assert c3["reason"] is None
    conn.close()


def test_reason_names_highest_rated_tie_newest_date_read(tmp_path):
    """Tilde has THREE books all rated 4 — the reason names the one with the
    NEWEST date_read (book 6, 2024-04-04): the NULL-date row loses (NULLs
    last) and the 2023 row loses. Copy is the plan literal, title in ”…”."""
    conn = score_db(tmp_path / "t.db")
    c5 = next(i for i in top_recommendations(conn, 12)
              if i["kind"] == "cand" and i["id"] == 5)
    assert c5["reason"] == ('För att du gav ”Tid och tid igen” 4 i betyg av '
                            'Tilde T')
    conn.close()


def test_genre_reason_when_no_author_signal(tmp_path):
    """Cecilia has zero rated books; her wishlist row keeps its genre lane
    (Romantik, G = 2/5) and answers the §8 genre copy instead — 'För att du
    gillar Romantik'."""
    conn = score_db(tmp_path / "t.db")
    w2 = next(i for i in top_recommendations(conn, 12)
              if i["kind"] == "book" and i["id"] == 21)
    assert w2["reason"] == "För att du gillar Romantik"
    assert w2["score"] == approx(0.35 * 0.4 + 0.10)
    conn.close()


# ── t=0: the owner has rated NOTHING yet (the plan's zero-rated leg) ─────────
def test_zero_rated_recommends_wishlist_first_no_reasons(tmp_path):
    """"Recommendations render even when zero rated books exist (wishlist
    order)": strip every rating → A and G are all 0 → the wishes score 0.10
    and lead in (author, title) order, then the pool at 0.0 in (author,
    title) order. NO division, NO crash, no reason line anywhere."""
    conn = score_db(tmp_path / "t.db")
    conn.execute("UPDATE book SET rating = NULL")
    conn.commit()
    got = top_recommendations(conn, 12)
    assert [(i["kind"], i["id"]) for i in got] == [
        ("book", 20),    # wishes, 0.10: Aino A < Bertil B < Cecilia C
        ("book", 22),
        ("book", 21),
        ("cand", 1),     # pool, 0.0: Aino A < Bertil B-stavning < Cecilia C
        ("cand", 2),     # < Okänd Författare (by title: A-Anna, B-Bertil,
        ("cand", 4),     # Helt okänd) < Tilde T
        ("cand", 6),
        ("cand", 7),
        ("cand", 3),
        ("cand", 5),
    ]
    assert [i["score"] for i in got] == approx([0.10] * 3 + [0.0] * 7)
    assert all(i["reason"] is None for i in got)
    conn.close()
