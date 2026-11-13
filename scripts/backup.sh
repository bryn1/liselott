#!/usr/bin/env bash
# T9.2 — the operator's backup entry point (plan §11). Three verbs, one
# mechanism: everything happens in app/backup.py, the SAME module GET /backup
# streams, so a pull through the door and a run on the shell produce the same
# pair (liselott.db + covers tar, dir 700 / files 600, keep-last-14).
#
#   scripts/backup.sh              # make the pair, prune to the last 14
#   scripts/backup.sh list         # the pairs present, oldest first
#   scripts/backup.sh restore [STEM]   # newest pair back, or the named one
#
# Env is the app's own: LISELOTT_DATA_DIR (state dir), LISELOTT_BACKUP_DIR
# (default $HOME/liselott-backups). PYTHON picks the interpreter; the default
# is the repo's .venv because the mechanism imports the app.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
py="${PYTHON:-}"
if [ -z "$py" ]; then
  py="$here/.venv/bin/python"
  [ -x "$py" ] || py="$(command -v python3)"
fi

cd "$here"
verb="${1:-backup}"
if [ $# -gt 0 ]; then shift; fi        # no argument means "backup"
case "$verb" in
  backup)  exec "$py" -m app.backup backup "$@" ;;
  list)    exec "$py" -m app.backup list "$@" ;;
  restore) exec "$py" -m app.backup restore ${1:+--stem "$1"} ;;
  *) echo "usage: scripts/backup.sh [backup | list | restore [STEM]]" >&2
     exit 2 ;;
esac
