"""T3.6 — the enriched bundle export (§5.11 keys, F-1 export) + the BYTE-BUDGET
chunker (P1-1: the lane's effective body cap is nginx's default 1,048,576 B, so
every chunk is packed under a 900,000-byte budget with ~14 % margin) — tested
against a tmp seeded+enriched DB (corpus-free, no network).

The plan's test text exports to /home/claudecode/liselott-bundle-test/… via
--out; here the SAME flag writes into pytest's tmp dir instead — a fixed
absolute path inside a test is a collision waiting to happen between parallel
runs, and the plan's point is that --out is honoured (asserted below)."""
import base64
import hashlib
import json
from pathlib import Path

import pytest

from app import db, enrich
from scripts.chunk_bundle import main as chunk_main
from scripts.export_bundle import main as export_main

ROOT = Path(__file__).resolve().parent.parent
COVER_FIXTURE = ROOT / "tests" / "fixtures" / "cover_sample.jpg"

BUNDLE_KEYS = {"book_key", "title", "authors", "date_read", "read_year", "format",
               "rating", "status", "isbn13", "isbn10", "year", "genres",
               "cover_b64", "cover_source"}


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    for i in range(1, 4):
        conn.execute(
            "INSERT INTO book (id, title, book_key, format, date_read, read_year,"
            " rating, status, isbn13, isbn10, year, created, updated) VALUES"
            " (?, ?, ?, 'ljudbok', '2024-05-06', 2024, ?, 'read', ?, ?, ?, ?, ?)",
            (i, f"Bok {i}", f"bok-{i}", i, "9789198559699", "9198559699", 2022,
             "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
        conn.execute("INSERT OR IGNORE INTO author (id, name) VALUES (?, ?)",
                     (i, f"Författare {i}"))
        conn.execute("INSERT INTO book_author (book_id, author_id) VALUES (?, ?)", (i, i))
    conn.execute("INSERT INTO genre (id, name) VALUES (1, 'Kriminalitet')")
    conn.execute("INSERT INTO book_genre (book_id, genre_id) VALUES (1, 1)")
    enrich.store_cover(conn, 2, COVER_FIXTURE.read_bytes(), "openlibrary")   # has a cover
    conn.commit()
    yield conn, tmp_path
    conn.close()


def export(conn, out):
    assert export_main(["--out", str(out)]) == 0
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


# ---- export ----------------------------------------------------------------

def test_export_emits_one_line_per_book_with_exactly_the_5_11_keys(seeded):
    conn, tmp = seeded
    lines = export(conn, tmp / "seed-bundle.jsonl")
    assert len(lines) == 3
    for line in lines:
        assert set(line) == BUNDLE_KEYS          # EXACTLY, nothing extra or missing
        assert line["book_key"] and line["status"] == "read"
        assert line["format"] == "ljudbok" and line["rating"] in (1, 2, 3)
        assert line["date_read"] == "2024-05-06" and line["read_year"] == 2024
        assert line["isbn13"] == "9789198559699" and line["year"] == 2022


def test_export_carries_authors_and_genres_as_lists(seeded):
    conn, tmp = seeded
    lines = export(conn, tmp / "seed-bundle.jsonl")
    by_key = {l["book_key"]: l for l in lines}
    assert by_key["bok-1"]["genres"] == ["Kriminalitet"]
    assert by_key["bok-2"]["genres"] == []        # a book with no genre rows
    assert by_key["bok-1"]["authors"] == ["Författare 1"]


def test_cover_b64_decodes_to_the_stored_jpeg_bytes(seeded):
    conn, tmp = seeded
    lines = {l["book_key"]: l for l in export(conn, tmp / "seed-bundle.jsonl")}
    stored = (tmp / "covers" / "2.jpg").read_bytes()
    assert base64.b64decode(lines["bok-2"]["cover_b64"]) == stored
    assert lines["bok-2"]["cover_source"] == "openlibrary"
    assert lines["bok-1"]["cover_b64"] is None     # no cover -> null, not ""
    assert lines["bok-1"]["cover_source"] is None


def test_every_line_is_within_the_400kb_budget(seeded):
    conn, tmp = seeded
    export_main(["--out", str(tmp / "seed-bundle.jsonl")])
    for raw in (tmp / "seed-bundle.jsonl").read_bytes().splitlines():
        assert len(raw) <= 400_000


def test_export_prints_the_sha256_of_the_bundle(seeded, capsys):
    conn, tmp = seeded
    out = tmp / "seed-bundle.jsonl"
    export_main(["--out", str(out)])
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    assert digest in capsys.readouterr().out


def test_export_refuses_a_line_over_the_budget_naming_the_row(tmp_path, monkeypatch, capsys):
    """The §5.11 line budget is a transport contract, not a wish: a fatter row
    exits 1 and names the row, never a silently oversized bundle."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    db.init_db(conn)
    conn.execute("INSERT INTO book (id, title, book_key, format, read_year, status,"
                 " created, updated) VALUES (1, 'Kämpig', 'kampig', 'bok', 2024,"
                 " 'read', ?, ?)", ("2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"))
    conn.execute("INSERT INTO genre (id, name) VALUES (1, ?)", ("x" * 420_000,))
    conn.execute("INSERT INTO book_genre (book_id, genre_id) VALUES (1, 1)")
    conn.commit()
    assert export_main(["--out", str(tmp_path / "b.jsonl")]) == 1
    err = capsys.readouterr().err
    assert "kampig" in err and "400" in err
    conn.close()


# ---- chunker ----------------------------------------------------------------

def chunk(path, out_dir, max_bytes=900_000):
    return chunk_main(["--in", str(path), "--out-dir", str(out_dir),
                       "--max-bytes", str(max_bytes)])


def test_chunker_packs_under_the_budget_and_rebuilds_the_bundle_byte_exact(seeded):
    conn, tmp = seeded
    bundle = tmp / "seed-bundle.jsonl"
    export_main(["--out", str(bundle)])
    chunks_dir = tmp / "chunks"
    assert chunk(bundle, chunks_dir) == 0
    chunks = sorted(chunks_dir.glob("bundle-*.ndjson"))
    assert [c.name for c in chunks] == ["bundle-0001.ndjson"]   # small fixture, one chunk
    assert chunks and chunks[0].name == "bundle-0001.ndjson"      # the pinned name
    original = bundle.read_bytes()
    assert b"".join(c.read_bytes() for c in chunks) == original    # byte-concat exact
    assert sum(1 for _ in original.splitlines()) == \
        sum(1 for c in chunks for _ in c.read_bytes().splitlines())  # lines preserved
    for c in chunks:
        assert c.stat().st_size <= 900_000


def test_chunker_actually_splits_and_repacks_greedily(tmp_path):
    """The DoD's 900 000-B budget yields ONE chunk for a 3-book fixture, which
    would pass even if the splitter never split. Synthetic lines of a KNOWN
    size prove the packing: 5 × 100-byte lines at a 250-byte budget is 3
    chunks (100+100, 100+100, 100) — never one line per chunk, never over."""
    bundle = tmp_path / "five.ndjson"

    def line_of(key, target):            # pad grown until the line is EXACTLY target
        payload = {"book_key": key, "pad": ""}
        while len(json.dumps(payload)) + 1 < target:
            payload["pad"] += "x"
        return json.dumps(payload) + "\n"

    lines = [line_of(f"k{i}", 100) for i in range(5)]
    bundle.write_text("".join(lines), encoding="utf-8")
    assert [len(l) for l in lines] == [100] * 5
    assert chunk(bundle, tmp_path / "chunks", max_bytes=250) == 0
    chunks = sorted((tmp_path / "chunks").glob("bundle-*.ndjson"))
    assert [c.read_bytes().count(b"\n") for c in chunks] == [2, 2, 1]
    assert all(c.stat().st_size <= 250 for c in chunks)
    assert b"".join(c.read_bytes() for c in chunks) == bundle.read_bytes()


def test_chunker_prints_the_sha256_of_the_unchunked_bundle(seeded, capsys):
    conn, tmp = seeded
    bundle = tmp / "seed-bundle.jsonl"
    export_main(["--out", str(bundle)])
    capsys.readouterr()
    assert chunk(bundle, tmp / "chunks") == 0
    assert hashlib.sha256(bundle.read_bytes()).hexdigest() in capsys.readouterr().out


def test_chunker_refuses_an_oversized_single_line_naming_it(tmp_path, capsys):
    """A 500 KB single-line bundle: no chunk can ever hold it, so the splitter
    exits 1 NAMING the line — never a silent drop, never a chunk over budget."""
    bundle = tmp_path / "fat.ndjson"
    line = json.dumps({"book_key": "fet-rad", "blob": "x" * 500_000})
    bundle.write_text(line + "\n", encoding="utf-8")
    assert chunk(bundle, tmp_path / "chunks") == 1
    err = capsys.readouterr().err
    assert "fet-rad" in err and "500" in err


def test_chunker_rejects_a_budget_above_the_lane_cap(tmp_path, capsys):
    """900 000 is the transport budget (§10/P1-1). A bigger --max-bytes would
    write chunks the lane 413s, so the tool refuses the footgun outright."""
    bundle = tmp_path / "b.ndjson"
    bundle.write_text('{"a":1}\n', encoding="utf-8")
    assert chunk(bundle, tmp_path / "chunks", max_bytes=1_000_000) == 2
    assert "900" in capsys.readouterr().err
