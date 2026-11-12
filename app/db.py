"""State dir + DB connection (F-4). Production sets ONLY HOME/PORT (unit, VERIFIED
renderer L100/L104), and under ProtectSystem=strict the StateDirectory is the
one writable path — so candidates are tried in order and the first writable
one wins; none writable means the process must die loudly, never write blind.
"""
import os
import sqlite3
from pathlib import Path

DB_NAME = "liselott.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def state_base() -> Path:
    """First writable candidate wins (§4): LISELOTT_DATA_DIR (dev/test/build
    only) → $HOME/liselott-state (production StateDirectory) → ./data."""
    candidates = []
    env_dir = os.environ.get("LISELOTT_DATA_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    home = os.environ.get("HOME")
    if home:
        candidates.append(Path(home) / "liselott-state")
    candidates.append(Path.cwd() / "data")

    for cand in candidates:
        try:
            cand.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        if os.access(cand, os.W_OK):
            return cand
    raise SystemExit(
        "liselott: FATAL no writable state dir (tried $LISELOTT_DATA_DIR, "
        "$HOME/liselott-state, ./data) — refusing to start")


def init_db(conn: sqlite3.Connection) -> None:
    """Apply app/schema.sql; idempotent (every CREATE carries IF NOT EXISTS)."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    """Open the app DB inside state_base(); WAL per §4 (single worker)."""
    conn = sqlite3.connect(state_base() / DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
