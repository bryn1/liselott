"""T0.3 — state_base() fail-fast (F-4, fest40 pattern) + connect() WAL."""
import os
import sqlite3
from pathlib import Path

import pytest

from app import db

UNWRITABLE = 0o500  # r-x: no write for the owner


def make_unwritable(parent: Path, name: str) -> Path:
    d = parent / name
    d.mkdir()
    d.chmod(UNWRITABLE)
    return d


def test_data_dir_env_used_and_created(tmp_path, monkeypatch):
    target = tmp_path / "outer" / "nested"  # not created yet — must be mkdir -p'd
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(target))
    assert db.state_base() == target
    assert target.is_dir()


def test_home_candidate_is_production_shape(tmp_path, monkeypatch):
    """$HOME/liselott-state wins when the env override is unset (unit sets HOME)."""
    monkeypatch.delenv("LISELOTT_DATA_DIR", raising=False)
    home = tmp_path / "fake-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    make_unwritable(tmp_path, "cwd")
    monkeypatch.chdir(tmp_path / "cwd")
    assert db.state_base() == home / "liselott-state"


def test_all_candidates_unwritable_refuses_to_start(tmp_path, monkeypatch):
    blocked1 = make_unwritable(tmp_path, "d1")
    blocked2 = make_unwritable(tmp_path, "home")
    blocked3 = make_unwritable(tmp_path, "cwd")
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(blocked1 / "sub"))
    monkeypatch.setenv("HOME", str(blocked2))
    monkeypatch.chdir(blocked3)
    with pytest.raises(SystemExit) as exc:
        db.state_base()
    assert "refusing to start" in str(exc.value)
    for d in (blocked1, blocked2, blocked3):
        d.chmod(0o700)


def test_connect_creates_wal_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    conn = db.connect()
    try:
        assert (tmp_path / "liselott.db").is_file()
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    finally:
        conn.close()
