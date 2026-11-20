"""Named schema migrations for databases already on disk.

app/schema.sql is idempotent for CREATING (every CREATE carries IF NOT
EXISTS) — which is exactly why it can never CHANGE an existing table. SQLite
bakes CHECK constraints at CREATE TABLE, so widening the cover_source
vocabulary to 'manual-url' (the OQ-2 ruling, 7eee210) left every pre-existing
DB still rejecting the value; s3 §9 flagged it ("any pre-existing DB needs
recreation before S5's UI can use the helper"). S5 ships that UI, so instead
of a recreation runbook this is the mechanism: one named migration per
contract that outgrew a live DB, run from db.init_db — the ONE schema entry
point every caller (app requests, CLIs, the offline scratch copy, tests)
already routes through. Idempotent by construction: the trigger is the stored
DDL missing the required value, so a migrated DB is never rewritten.

The rebuild is SQLite's documented table-edit pattern (create new DDL →
copy → drop → rename): ids survive on purpose, because covers live at
covers/<id>.jpg and a renumber would orphan every stored cover. DROP TABLE
takes the table's indexes with it, so schema.sql re-runs after the rename to
restore them. An old table carrying a column today's DDL does not know ABORTS
naming it — copying only the column intersection would silently eat data, and
a migration that eats the owner's diary is the exact failure this repo has
guard tests against everywhere else.
"""
import re

# One entry per CHECK a live DB may predate: table -> value its stored DDL
# must contain. 'manual-url': the OQ-2 cover_source widening (7eee210), the
# s3 §9 finding, on BOTH tables that carry the column.
COVER_SOURCE_CHECK = {"book": "'manual-url'", "candidate": "'manual-url'"}
# MC 12733 (M12 W1): the status vocabulary widens to ('read','wishlist',
# 'reading','aborted'). REPRESENTATIVE LITERAL: "'aborted'" — the CHECK's
# last-listed token. A stored DDL either carries the whole widened list (the
# rebuild rewrites the table from schema.sql wholesale) or none of it, so
# testing the last token is exact; A FUTURE WIDENING OF THIS CHECK MUST BUMP
# THE LITERAL to its own last-listed value, exactly as this row does.
STATUS_CHECK_WIDENING = {"book": "'aborted'"}
CHECK_WIDENINGS = (COVER_SOURCE_CHECK, STATUS_CHECK_WIDENING)


def table_sql(conn, table):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'"
                       " AND name = ?", (table,)).fetchone()
    return row[0] if row else None


def _create_current(conn, table):
    """Create this table's CURRENT DDL — taken from schema.sql (the one source
    of the truth being migrated to) — under a temporary name; a hand-copied
    twin would drift the moment either moved. Returns the temp name."""
    from app import db
    stmt = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\);",
                     db.SCHEMA_PATH.read_text(encoding="utf-8"),
                     re.DOTALL).group(0)
    tmp = f"{table}__mig"
    conn.execute(stmt.replace(f"CREATE TABLE IF NOT EXISTS {table}",
                              f"CREATE TABLE {tmp}", 1))
    return tmp


def _rebuild(conn, table):
    conn.execute("BEGIN")
    try:
        tmp = _create_current(conn, table)
        old_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        new_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tmp})")]
        unknown = sorted(set(old_cols) - set(new_cols))
        if unknown:
            raise RuntimeError(
                f"liselott: migrate({table}) vägrar — kolumnen "
                f"{', '.join(unknown)} finns inte i nuvarande schema; en "
                f"rebuild skulle tyst försvaga den.")
        shared = ", ".join(new_cols)
        conn.execute(f"INSERT INTO {tmp} ({shared})"
                     f" SELECT {shared} FROM {table}")
        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {tmp} RENAME TO {table}")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    conn.commit()


def apply(conn):
    """Run every named migration; returns the tables actually migrated (empty
    = nothing to do, the normal case). Called from db.init_db."""
    from app import db          # late: db imports this module (repo pattern)
    conn.execute("PRAGMA foreign_keys=OFF")   # rebuild window only
    migrated = []
    try:
        for widening in CHECK_WIDENINGS:
            for table, required in widening.items():
                sql = table_sql(conn, table)
                if sql is None or required in sql:
                    continue                    # absent (fresh) or already widened
                _rebuild(conn, table)
                migrated.append(table)
        # F-F (PLAN-M12 REV 2 §5, DA-verdict-plan): the rebuild COMMITs inside
        # _rebuild, so a crash before THIS line used to leave `book` rebuilt
        # without its indexes for a next apply that saw migrated == [] and
        # skipped the restore forever. schema.sql is CREATE-idempotent BY
        # CONTRACT (its header line) — so the re-run runs UNCONDITIONALLY:
        # a no-op on a current DB, the self-heal after a crash in the window.
        conn.executescript(db.SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    return migrated
