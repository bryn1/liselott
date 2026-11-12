#!/usr/bin/env python3
"""Password reset for VM350/dev use only, against state_base() (or
LISELOTT_DATA_DIR). Production has NO shell (ADR-0044): forgotten-password
recovery there is a rebuild or a vm106-ROOT DB action — named as such in the
plan §12, never assumed automatic. Writes the same settings keys the setup
route writes; min length rule shared with app/auth."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import auth, db  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("password", help=f"new password (min {auth.PASSWORD_MIN} chars)")
    args = ap.parse_args(argv)
    if len(args.password) < auth.PASSWORD_MIN:
        print(f"FAIL: lösenordet måste vara minst {auth.PASSWORD_MIN} tecken",
              file=sys.stderr)
        return 1
    conn = db.connect()
    db.init_db(conn)
    auth.set_setting(conn, "password_hash", auth.hash_password(args.password))
    auth.set_setting(conn, "password_set_at", auth.utcnow_iso())
    conn.close()
    print("OK: lösenord satt om")
    return 0


if __name__ == "__main__":
    sys.exit(main())
