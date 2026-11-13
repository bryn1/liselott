"""T9.2 — the backup mechanism (plan §11): ONE sqlite snapshot + ONE covers
tar, written by `scripts/backup.sh` and streamed by `GET /backup` from THESE
same functions, so the operator's pull and the owner's door can never disagree
about what a backup IS. The lane gives no cron on vm106 (no login), so the
plan-owned mechanism is the session-gated route; retention belongs to the
written pair (keep-last-14), not to the route's throwaway snapshot.

The modes are the plan's: the backup dir is 0700 and every file inside it 600.
sqlite3 and tarfile create under the process umask (022 here), so each file is
chmodded AFTER it is written and the dir on every use, never only at creation.

Shell entry: `python -m app.backup [backup|restore|list] [--stem STEM]` —
scripts/backup.sh is the operator's name for the same three verbs, and the
output is key=value lines so a shell can read it without a JSON parser. Env is
the app's own: LISELOTT_DATA_DIR picks the state dir, LISELOTT_BACKUP_DIR the
backup dir (default $HOME/liselott-backups, inside the StateDirectory root).
"""
import argparse
import os
import re
import shutil
import sqlite3
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from app import db
from app.enrich_cover import COVER_SUBDIR

KEEP = 14                                   # §11: retention keep-last-14
DB_SUFFIX = ".db"
COVERS_SUFFIX = "-covers.tar.gz"
# 20261113T131500Z, or 20261113T131500Z-07 when several runs land in the same
# second — the counter keeps every pair distinct (and the sort chronological).
_STEM_RE = re.compile(r"^\d{8}T\d{6}Z(-\d{2,})?$")


class BackupError(Exception):
    """A backup or restore this contract refuses, naming what is missing."""


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)                   # re-asserted, never only on create
    return path


def backup_dir() -> Path:
    """$LISELOTT_BACKUP_DIR, default $HOME/liselott-backups (§11), 0700."""
    env, home = os.environ.get("LISELOTT_BACKUP_DIR"), os.environ.get("HOME")
    if not env and not home:
        raise BackupError("no backup dir — set LISELOTT_BACKUP_DIR or HOME")
    return _ensure_dir(Path(env) if env else Path(home) / "liselott-backups")


def snapshot_db(state_dir, dest) -> Path:
    """A consistent copy of the live DB through sqlite's OWN backup API
    (§11) — never a `cp` of a file that may be mid-write in WAL mode."""
    src = Path(state_dir) / db.DB_NAME
    if not src.is_file():
        raise BackupError(f"no database at {src} — seed or serve first")
    _ensure_dir(Path(dest).parent)
    Path(dest).unlink(missing_ok=True)      # a fresh file: no stale bytes kept
    src_conn, dst_conn = sqlite3.connect(src), sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    os.chmod(dest, 0o600)
    return Path(dest)


def snapshot_covers(state_dir, dest) -> Path:
    """Everything under covers/ as ONE tar.gz, arcnames staying `covers/…`.
    A state dir with no covers yet yields a valid EMPTY tar — a fresh install
    has nothing to carry, and the round trip still proves the PAIR."""
    _ensure_dir(Path(dest).parent)
    src = Path(state_dir) / COVER_SUBDIR
    with tarfile.open(dest, "w:gz") as tar:
        if src.is_dir():
            tar.add(src, arcname=COVER_SUBDIR)
    os.chmod(dest, 0o600)
    return Path(dest)


def stems(bkdir) -> list:
    """The pairs present, oldest first (the stamp sorts chronologically)."""
    bkdir = Path(bkdir)
    return sorted(p.name[:-len(DB_SUFFIX)] for p in bkdir.glob("*" + DB_SUFFIX)
                  if _STEM_RE.fullmatch(p.name[:-len(DB_SUFFIX)]))


def _new_stem(bkdir) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem, n = stamp, 1
    while any((Path(bkdir) / f"{stem}{s}").exists()
              for s in (DB_SUFFIX, COVERS_SUFFIX)):
        stem, n = f"{stamp}-{n:02d}", n + 1
    return stem


def prune(bkdir, keep=KEEP) -> int:
    """Keep the last `keep` PAIRS (§11) — and remove exactly the two files of
    each pair that goes. NOT a `stem*` glob: the stem of 20261113T133024Z owns
    the -01…-99 same-second family too, and deleting that family while counting
    it as one pair silently eats live backups (measured in
    tests/test_backup.sh's retention leg)."""
    bkdir = Path(bkdir)
    stale = stems(bkdir)[:-keep] if keep else stems(bkdir)
    for stem in stale:
        for victim in (bkdir / (stem + DB_SUFFIX),
                       bkdir / (stem + COVERS_SUFFIX)):
            victim.unlink(missing_ok=True)
    return len(stale)


def create_backup(state_dir=None, bkdir=None) -> dict:
    """The pair + retention, in that order: the new pair is never pruned away
    by its own arrival."""
    state_dir = Path(state_dir) if state_dir else db.state_base()
    bkdir = Path(bkdir) if bkdir else backup_dir()
    stem = _new_stem(bkdir)
    out = {"stem": stem,
           "db": snapshot_db(state_dir, bkdir / (stem + DB_SUFFIX)),
           "covers": snapshot_covers(state_dir, bkdir / (stem + COVERS_SUFFIX))}
    out["pruned"] = prune(bkdir)
    out["kept"] = len(stems(bkdir))
    return out


def _extract_covers(tar_path, state_dir) -> int:
    """Unpack a covers tar WITHOUT trusting its names: only plain files and
    dirs under covers/ land, and the tarfile security filter is used wherever
    the interpreter has it. Returns the number of FILES restored."""
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            parts = Path(m.name).parts
            if (not parts or parts[0] != COVER_SUBDIR or ".." in parts
                    or m.name.startswith("/")
                    or not (m.isfile() or m.isdir())):
                raise BackupError(f"unsafe entry in {tar_path}: {m.name!r}")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(path=str(state_dir), filter="data")
        else:                               # names validated just above
            tar.extractall(path=str(state_dir))
    return sum(1 for m in members if m.isfile())


def _book_count(db_path) -> int:
    """Rows in the restored DB, read-only. No book table is NOT "0 books" —
    it is a file that was never this app's DB, and saying so is the point."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table'"
                        " AND name='book'").fetchone() is None:
            raise BackupError(f"{db_path} has no book table — not this"
                              " app's database")
        return conn.execute("SELECT COUNT(*) FROM book").fetchone()[0]
    finally:
        conn.close()


def restore(bkdir=None, state_dir=None, stem=None) -> dict:
    """Copy one pair BACK into a state dir and report what came home (the
    round-trip leg the plan's DoD measures). A stale -wal/-shm beside the old
    DB goes first: replaying the OLD wal onto a restored main file would
    resurrect rows the backup never contained."""
    bkdir = Path(bkdir) if bkdir else backup_dir()
    stem = stem or (stems(bkdir) or [""])[-1]
    src_db, src_covers = bkdir / (stem + DB_SUFFIX), bkdir / (stem + COVERS_SUFFIX)
    if not (src_db.is_file() and src_covers.is_file()):
        raise BackupError(f"no complete pair to restore from {bkdir}"
                          f"{' for stem ' + stem if stem else ''}")
    state_dir = _ensure_dir(Path(state_dir) if state_dir else db.state_base())
    target = state_dir / db.DB_NAME
    for stale in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
        stale.unlink(missing_ok=True)
    shutil.copyfile(src_db, target)
    os.chmod(target, 0o600)
    covers = _extract_covers(src_covers, state_dir)
    return {"stem": stem, "books": _book_count(target), "covers": covers,
            "state_dir": state_dir}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.backup", description=__doc__)
    ap.add_argument("verb", nargs="?", default="backup",
                    choices=("backup", "restore", "list"))
    ap.add_argument("--stem", help="restore THIS pair (default: the newest)")
    args = ap.parse_args(argv)
    if args.verb == "backup":
        out = create_backup()
        print(f"STEM={out['stem']}\nDB_FILE={out['db']}\n"
              f"COVERS_FILE={out['covers']}\nKEPT={out['kept']}")
    elif args.verb == "restore":
        out = restore(stem=args.stem)
        print(f"STEM={out['stem']}\nBOOKS_RESTORED={out['books']}\n"
              f"COVERS_RESTORED={out['covers']}")
    else:
        for stem in stems(backup_dir()):
            print(stem)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BackupError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
