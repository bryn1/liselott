"""T1.4 — alias resolution incl. the L711 phantom-author chain (P2-2).
MC 12523: the real author_aliases.csv is personal data (off-repo after this
card) — the mechanism legs run on synthetic CSV rows the test writes itself,
and the real file is pinned NAME-FREE (row count + every row resolving),
wherever its resolver path resolves it."""
import csv
from pathlib import Path

import pytest

from app import db, seed

# The synthetic alias table: canonical,alias rows with the shapes the real
# one has (misspelling, diacritic variant, space/punctuation variant).
SYNTH_CSV = ("Sissela Åhrnstedt,Sissela Åhrstedt\n"
             "Sara H. Ohlsson,Sara H Ohlsson\n"
             "Elsa Lindqvist,Elsie Lindqvist\n")


@pytest.fixture()
def conn(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    c = db.connect()
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture()
def aliases_csv(tmp_path):
    p = tmp_path / "synth_aliases.csv"
    p.write_text(SYNTH_CSV, encoding="utf-8")
    return p


def author_names(c):
    return sorted(r[0] for r in c.execute("SELECT name FROM author"))


def test_synthetic_csv_resolves_every_alias_to_canonical(aliases_csv):
    amap = seed.load_aliases(aliases_csv)
    with aliases_csv.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == len(amap) == 3
    for canonical, alias in rows:
        assert amap[alias] == canonical
    assert amap["Sissela Åhrstedt"] == "Sissela Åhrnstedt"
    assert amap["Sara H Ohlsson"] == "Sara H. Ohlsson"


def test_unknown_name_passes_through(conn, aliases_csv):
    seed.register_author(conn, "Helt Okänd Författare", seed.load_aliases(aliases_csv))
    assert author_names(conn) == ["Helt Okänd Författare"]


def test_both_spellings_same_author_id(conn, aliases_csv):
    amap = seed.load_aliases(aliases_csv)
    id1 = seed.register_author(conn, "Sara H Ohlsson", amap)
    id2 = seed.register_author(conn, "Sara H. Ohlsson", amap)
    assert id1 == id2
    assert author_names(conn) == ["Sara H. Ohlsson"]
    assert conn.execute("SELECT COUNT(*) FROM author_alias").fetchone()[0] == 1


def test_strip_then_alias_chain(conn, aliases_csv):
    """Parse strip ('(särskrivning i källan: Åhrnstedt)' gone) -> alias ->
    canonical — no phantom author row survives (P2-2)."""
    row = seed.parse_row(
        "En enda lögn av Sissela Åhrstedt (särskrivning i källan: Åhrnstedt)")
    assert row["authors"] == ["Sissela Åhrstedt"]  # strip keeps the raw spelling
    for name in row["authors"]:
        seed.register_author(conn, name, seed.load_aliases(aliases_csv))
    assert author_names(conn) == ["Sissela Åhrnstedt"]


def test_real_csv_still_resolves_name_free():
    """The personal CSV, pinned without naming it: row count 15 (§5.9's
    audit) and EVERY row resolving alias->canonical. The CSV is off-repo
    state data after MC 12523 — resolved through seed.aliases_file() (env
    first, else the off-repo home); skips with a loud reason where the host
    has no copy, the synthetic mechanism legs above run everywhere."""
    path = seed.aliases_file()
    if not path.is_file():
        pytest.skip("personal aliases CSV absent — path F; the mechanism legs "
                    "above run on synthetic rows in every checkout")
    amap = seed.load_aliases(path)
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert len(rows) == len(amap) == 15
    for canonical, alias in rows:
        assert canonical and alias
        assert amap[alias] == canonical


def test_env_file_wins_over_the_default_home(tmp_path, monkeypatch):
    """MC 12523: ONE resolver per CSV, env first — LISELOTT_ALIASES_FILE /
    LISELOTT_OVERRIDE_FILE win; without them both default to the off-repo
    home, and NO caller keeps a repo path (the old data-import/ paths are
    gone from the code, grep-proven in the card's sweep)."""
    env_a = tmp_path / "a.csv"
    env_o = tmp_path / "o.csv"
    monkeypatch.setenv("LISELOTT_ALIASES_FILE", str(env_a))
    monkeypatch.setenv("LISELOTT_OVERRIDE_FILE", str(env_o))
    assert seed.aliases_file() == env_a.resolve() or seed.aliases_file() == env_a
    assert seed.overrides_file() == env_o.resolve() or seed.overrides_file() == env_o
    monkeypatch.delenv("LISELOTT_ALIASES_FILE")
    monkeypatch.delenv("LISELOTT_OVERRIDE_FILE")
    assert seed.aliases_file() == seed.DATA_HOME / "author_aliases.csv"
    assert seed.overrides_file() == seed.DATA_HOME / "import_overrides.csv"
