"""F-B2 (DA-verdict-c2, MC 12451) — the /bundle POST is ONE TRANSACTION FOR REAL.

The c2 rollback leg was FALSE-GREEN for its own named mechanism: it threw its
error with `rating 99`, which parse_bundle now refuses BEFORE the upsert loop
— so the `commit=False` wiring at the two store_cover call sites (the exact
thing that test's docstring claims to guard) never executed, and a
commit=True plant left all 20 route tests green (the DA's measurement). The
suite-blindness dies here: these errors arrive INSIDE the loop, on real code
paths —

* the FILE-WRITE PLANT F-B2 names: store_cover's THIRD call raises OSError
  (the disk refuses line 3 of 5) while lines 1–2 are already real INSERTs
  with real JPEGs on disk;
* the KeyError family — the DA's own paired proof (line 1 valid WITH cover
  bytes, line 2 a new key without title).

After the 400 both legs assert: books COUNT is BACK TO THE PREVIOUS value
(two rows existed before the POST — not zero), AND no orphan cover file
remains — the written-but-rejected JPEGs are unlinked (F-K's orphan-file
finding closes with it). A MERGE-path cover rewrite deliberately keeps its
file: after the rollback the row's own cover_path still points at it, so
unlinking would break a live reference rather than clean an orphan.
"""
import sqlite3

import pytest

from app import enrich, seed
from tests.test_seed_routes import (B64, authed, bundle_bytes, line,
                                    stored_count)
from tests.test_ingest_vocab import sur_line


def cover_files(tmp):
    d = tmp / "covers"
    return sorted(p.name for p in d.glob("*.jpg")) if d.is_dir() else []


@pytest.fixture()
def pre_stored(authed):
    """Two existing rows FIRST (books=2, no covers) — "back to previous" is
    the number BEFORE the failing POST, not a vacuous zero."""
    tmp, client = authed
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kPre1", title="Redan bok"),
        line(book_key="kPre2", title="Redan bok två")),
        content_type="application/octet-stream")
    assert r.status_code == 200 and r.get_json()["books"] == 2
    return tmp, client


def test_bundle_file_write_failure_mid_loop_rolls_back_everything(pre_stored,
                                                                  monkeypatch):
    """THE file-write plant: 5 valid lines WITH cover bytes; the third
    store_cover call fails like a disk refusing the write. The shipped
    answer was a 500 (the OSError escaped the loop's catch list) AND a
    commit=True plant would leave rows behind. Now: 400 naming rad 3, COUNT
    back to 2, and lines 1–2's already-written JPEGs are unlinked — the
    covers dir holds ZERO files."""
    tmp, client = pre_stored
    real = enrich.store_cover
    calls = []

    def failing(conn, book_id, data, source, commit=True):
        calls.append(book_id)
        if len(calls) == 3:
            raise OSError("anropsplantering: write: disk full")
        return real(conn, book_id, data, source, commit=commit)

    monkeypatch.setattr(enrich, "store_cover", failing)
    r = client.post("/liselott/bundle", data=bundle_bytes(*(
        line(book_key=f"kW{i}", title=f"Skrivbok {i}",
             cover_b64=B64, cover_source="openlibrary") for i in range(1, 6))),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 3" in r.get_data(as_text=True)
    assert stored_count(tmp) == 2
    assert cover_files(tmp) == []


def test_bundle_mid_loop_key_error_rolls_back_cover_of_first_line(pre_stored):
    """The DA's paired proof, no monkeypatch: line 1 is valid WITH cover
    bytes, line 2 is a NEW key without title → the KeyError catch fires
    INSIDE the loop, after line 1's INSERT and its cover write. rows_after
    is back to 2 (the plant measured 1 on the broken wiring) and line 1's
    cover file is gone with the rollback."""
    tmp, client = pre_stored
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kM1", title="Med omslag", cover_b64=B64,
             cover_source="openlibrary"),
        '{"book_key": "kM2", "read_year": 2024}'),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 2" in r.get_data(as_text=True)
    assert stored_count(tmp) == 2
    assert cover_files(tmp) == []


def test_bundle_cover_survives_on_a_later_clean_post(pre_stored):
    """The unlink only removes ROLLED-BACK bytes: the very next clean POST
    of the same lines imports all five with covers again, and the files
    really land — hygiene must not eat the next import."""
    tmp, client = pre_stored
    chunk = bundle_bytes(*(
        line(book_key=f"kR{i}", title=f"Ren bok {i}",
             cover_b64=B64, cover_source="openlibrary") for i in range(1, 4)))
    r = client.post("/liselott/bundle", data=chunk,
                    content_type="application/octet-stream")
    assert r.status_code == 200
    assert r.get_json()["covers"] == 3 and r.get_json()["books"] == 5
    assert len(cover_files(tmp)) == 3


# ── F-L2 (c4, MC 12451): the arm that the 500 escaped, and its orphan file ──
def test_bundle_surrogate_line_after_a_cover_writes_no_orphan(pre_stored):
    """THE F-L2 repro (verifier .tmp/c3/FL2-repro-run1.log shape 2): a valid
    line WITH cover bytes, then a lone-surrogate line. Shipped: HTTP 500, the
    door's rollback+unlink never ran and `covers/1.jpg` stayed on disk —
    bytes no row points at. Now the guard refuses at parse, so the POST
    answers the named-line 400 and never reaches the write at all: rows back
    to 2 AND zero files (both halves asserted, refusal shape and residue)."""
    tmp, client = pre_stored
    r = client.post("/liselott/bundle", data=bundle_bytes(
        line(book_key="kS1", title="Omslag före", cover_b64=B64,
             cover_source="openlibrary"),
        sur_line(book_key="kSur", title="Surrogat \ud800 bok")),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 2" in r.get_data(as_text=True)
    assert stored_count(tmp) == 2
    assert cover_files(tmp) == []


@pytest.mark.parametrize("boom", [
    sqlite3.IntegrityError("plantering: UNIQUE constraint failed"),
    sqlite3.OperationalError("plantering: disk vägrar skriva"),
    UnicodeEncodeError("utf-8", "x\ud800", 1, 2, "surrogates not allowed"),
], ids=["integrity", "operational", "unicode-bind"])
def test_db_family_error_mid_loop_still_unwinds(pre_stored, monkeypatch,
                                                boom):
    """The M7 plant's target, now PAIRED (the c3 mutation pass: narrowing
    `except sqlite3.Error` to `except sqlite3.IntegrityError` left that tree's
    whole 466-test suite green — no test ever let a non-Integrity sqlite
    error, least of all
    the UnicodeEncodeError F-L2 proved reachable, into the loop). Three plants
    arrive INSIDE the loop at a real call site: line 1 has ALREADY written its
    JPEG, so every one of them must still answer the named-line 400, wind the
    transaction back to 2 rows and unlink line 1's file."""
    tmp, client = pre_stored
    real = enrich.store_cover
    calls = []

    def planting(conn, book_id, data, source, commit=True):
        calls.append(book_id)
        if len(calls) == 2:
            raise boom
        return real(conn, book_id, data, source, commit=commit)

    monkeypatch.setattr(enrich, "store_cover", planting)
    r = client.post("/liselott/bundle", data=bundle_bytes(*(
        line(book_key=f"kD{i}", title=f"Databasbok {i}", cover_b64=B64,
             cover_source="openlibrary") for i in range(1, 4))),
        content_type="application/octet-stream")
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "rad 2" in r.get_data(as_text=True)
    assert stored_count(tmp) == 2
    assert cover_files(tmp) == []
