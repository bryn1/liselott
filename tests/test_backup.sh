#!/usr/bin/env bash
# T9.2 — the §11 round-trip gate. Plan DoD, verbatim: this file "exits 0
# printing BOOKS_RESTORED=724". The four legs the plan names, in order:
#   1. scripts/backup.sh on a SEEDED tmp DB makes the pair, dir 700 / 600, and
#      the snapshot is a whole 724-row sqlite file (PRAGMA integrity_check ok);
#   2. retention keeps the last 14 pairs, oldest first out;
#   3. the pair restores into a scratch state dir — BOOKS_RESTORED=724 and the
#      cover travels;
#   4. GET /backup streams the same pair to a session (valid sqlite file,
#      integrity ok; covers tar lists the cover), 400s an unknown kind and
#      302s a stranger — before AND after the password is set.
# VM350 build clone leg (§13): it seeds from the corpus file, and a missing
# corpus FAILS loudly — a skip would be the vacuous-green defect class.
# Run: bash tests/test_backup.sh
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
py="$here/.venv/bin/python"
[ -x "$py" ] || py="$(command -v python3)"
raw="$here/data-import/seed-books-raw.md"

tmp="$(mktemp -d)"
server_pid=""
cleanup() {
  [ -n "$server_pid" ] && kill "$server_pid" 2>/dev/null || true
  rm -rf "$tmp"
}
trap cleanup EXIT
fail() {
  echo "FAIL: $*" >&2
  [ -s "$tmp/server.log" ] && tail -20 "$tmp/server.log" >&2
  exit 1
}

integrity_and_count() {                      # -> "ok 724" for a whole DB
  "$py" - "$1" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
print(conn.execute("PRAGMA integrity_check").fetchone()[0],
      conn.execute("SELECT COUNT(*) FROM book").fetchone()[0])
PY
}

[ -f "$raw" ] || fail "$raw saknas — VM350 build clone leg (§13), never skip"

state="$tmp/state"; scratch="$tmp/scratch"
mkdir -p "$state/covers" "$scratch"
export LISELOTT_BACKUP_DIR="$tmp/backups"
cp "$here/tests/fixtures/cover_sample.jpg" "$state/covers/1.jpg"
"$py" "$here/data-import/import_seed.py" --db "$state/liselott.db" >/dev/null \
  || fail "seeden landade inte (data-import/import_seed.py)"

echo "== leg 1: the pair, the §11 modes, a whole snapshot"
LISELOTT_DATA_DIR="$state" PYTHON="$py" bash "$here/scripts/backup.sh" \
  > "$tmp/backup.out" || fail "scripts/backup.sh exitade nonzero"
db_file="$(sed -n 's/^DB_FILE=//p' "$tmp/backup.out")"
covers_file="$(sed -n 's/^COVERS_FILE=//p' "$tmp/backup.out")"
first_stem="$(sed -n 's/^STEM=//p' "$tmp/backup.out")"
[ -n "$db_file" ] && [ -f "$db_file" ] || fail "db-delen av paret saknas"
[ -n "$covers_file" ] && [ -f "$covers_file" ] || fail "covers-delen av paret saknas"
[ "$(stat -c %a "$LISELOTT_BACKUP_DIR")" = 700 ] || fail "backuppsdir ar inte 700"
[ "$(stat -c %a "$db_file")" = 600 ] || fail "db-filen ar inte 600"
[ "$(stat -c %a "$covers_file")" = 600 ] || fail "covers-filen ar inte 600"
[ "$(integrity_and_count "$db_file")" = "ok 724" ] \
  || fail "snapshoten ar inte en hel 724-raders databas"
tar -tzf "$covers_file" | grep -qx "covers/1.jpg" || fail "covers-taren saknar omslaget"

echo "== leg 2: retention keep-last-14"
for _ in $(seq 1 16); do
  LISELOTT_DATA_DIR="$state" PYTHON="$py" bash "$here/scripts/backup.sh" \
    > "$tmp/last.out" || fail "en backup i retention-loopen exitade nonzero"
done
newest_stem="$(sed -n 's/^STEM=//p' "$tmp/last.out")"
LISELOTT_DATA_DIR="$state" PYTHON="$py" bash "$here/scripts/backup.sh" list \
  > "$tmp/list.out" || fail "list exitade nonzero"
[ "$(wc -l < "$tmp/list.out")" = 14 ] \
  || fail "beholl $(wc -l < "$tmp/list.out") par i stallet for 14"
[ "$(find "$LISELOTT_BACKUP_DIR" -type f | wc -l)" = 28 ] \
  || fail "backuppsdir innehaller inte 28 filer (14 par)"
grep -qx "$newest_stem" "$tmp/list.out" || fail "det nyaste paret forsvann"
grep -qx "$first_stem" "$tmp/list.out" \
  && fail "det aldsta paret togs inte bort" || true

echo "== leg 3: restore into a scratch state dir (the DoD line)"
LISELOTT_DATA_DIR="$scratch" PYTHON="$py" \
  bash "$here/scripts/backup.sh" restore > "$tmp/restore.out" \
  || fail "restore exitade nonzero"
grep -qx 'BOOKS_RESTORED=724' "$tmp/restore.out" \
  || fail "restore svarade: $(tr '\n' ' ' < "$tmp/restore.out")"
grep -qx 'COVERS_RESTORED=1' "$tmp/restore.out" \
  || fail "omslaget folde inte med: $(tr '\n' ' ' < "$tmp/restore.out")"
[ -f "$scratch/covers/1.jpg" ] || fail "covers/1.jpg landade inte i scratch"
[ "$(integrity_and_count "$scratch/liselott.db")" = "ok 724" ] \
  || fail "den aterstallda databasen ar inte hel"
[ "$(stat -c %a "$scratch/liselott.db")" = 600 ] || fail "db-filen efter restore ar inte 600"

echo "== leg 4: GET /backup behind the login guard"
port="$("$py" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
LISELOTT_DATA_DIR="$state" LISELOTT_ENV=dev TMPDIR="$tmp" PORT="$port" \
  "$py" "$here/server.py" > "$tmp/server.log" 2>&1 &
server_pid=$!
for _ in $(seq 1 60); do
  curl -fsS "http://127.0.0.1:$port/liselott/healthz" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -fsS "http://127.0.0.1:$port/liselott/healthz" >/dev/null 2>&1 \
  || fail "serveren lyssnade inte pa :$port"

[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/liselott/backup?kind=db")" = 302 ] \
  || fail "anonym /backup fore installningen gav inte 302"
jar="$tmp/jar"
curl -s -o /dev/null -c "$jar" -X POST \
  --data-urlencode 'loesenord=runbook-curl-test-9' \
  --data-urlencode 'bekrafta=runbook-curl-test-9' \
  "http://127.0.0.1:$port/liselott/satt-loesenord"
[ -s "$jar" ] || fail "ingen session fickas av /satt-loesenord"
[ "$(curl -s -o /dev/null -w '%{http_code}' -b "$jar" "http://127.0.0.1:$port/liselott/backup?kind=fel")" = 400 ] \
  || fail "okant kind gav inte 400"
curl -s -b "$jar" -o "$tmp/pull.db" "http://127.0.0.1:$port/liselott/backup?kind=db"
[ "$(integrity_and_count "$tmp/pull.db")" = "ok 724" ] \
  || fail "draget ar inte en hel 724-raders sqlite-fil"
curl -s -b "$jar" -o "$tmp/pull-covers.tgz" "http://127.0.0.1:$port/liselott/backup?kind=covers"
tar -tzf "$tmp/pull-covers.tgz" | grep -qx "covers/1.jpg" \
  || fail "covers-draget ar inte en giltig tar med omslaget"
[ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/liselott/backup?kind=db")" = 302 ] \
  || fail "anonym /backup efter installningen gav inte 302"
kill "$server_pid"; wait "$server_pid" 2>/dev/null || true; server_pid=""
[ -z "$(find "$tmp" -maxdepth 1 -name 'liselott-backup-*' -print -quit)" ] \
  || fail "temp-snapshoten stannade kvar i TMPDIR"

books="$(sed -n 's/^BOOKS_RESTORED=//p' "$tmp/restore.out")"
echo "ROUND_TRIP_OK par=$newest_stem"
echo "BOOKS_RESTORED=$books"
