"""T1.4 — alias resolution incl. the L711 phantom-author chain (P2-2)."""
import csv
from pathlib import Path

import pytest

from app import db, seed

ALIASES_CSV = Path(__file__).resolve().parent.parent / "data-import/author_aliases.csv"


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    c = db.connect()
    db.init_db(c)
    yield c
    c.close()


def author_names(c):
    return sorted(r[0] for r in c.execute("SELECT name FROM author"))


def test_csv_has_15_alias_rows_resolving_canonical():
    amap = seed.load_aliases(ALIASES_CSV)
    with ALIASES_CSV.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == len(amap) == 15
    for canonical, alias in rows:
        assert amap[alias] == canonical
    assert amap["Simona Ahrnsredt"] == "Simona Ahrnstedt"
    assert amap["Sara H Olsson"] == "Sara H. Olsson"


def test_unknown_name_passes_through(conn):
    seed.register_author(conn, "Helt Okänd Författare", seed.load_aliases(ALIASES_CSV))
    assert author_names(conn) == ["Helt Okänd Författare"]


def test_sara_both_spellings_same_author_id(conn):
    amap = seed.load_aliases(ALIASES_CSV)
    id1 = seed.register_author(conn, "Sara H Olsson", amap)
    id2 = seed.register_author(conn, "Sara H. Olsson", amap)
    assert id1 == id2
    assert author_names(conn) == ["Sara H. Olsson"]
    assert conn.execute("SELECT COUNT(*) FROM author_alias").fetchone()[0] == 1


def test_l711_strip_then_alias_chain(conn):
    """Parse strip ('(särskrivning i källan: Ahrnstedt)' gone) -> alias ->
    canonical — no phantom author row survives (P2-2)."""
    row = seed.parse_row(
        "En enda hemlighet av Simona Ahrnsredt (särskrivning i källan: Ahrnstedt)")
    assert row["authors"] == ["Simona Ahrnsredt"]  # strip keeps the raw spelling
    for name in row["authors"]:
        seed.register_author(conn, name, seed.load_aliases(ALIASES_CSV))
    assert author_names(conn) == ["Simona Ahrnstedt"]
