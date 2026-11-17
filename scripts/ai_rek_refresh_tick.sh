#!/usr/bin/env bash
# MC 12647 (M11-N11) — the refresh TICK wrapper (owner ruling verbatim: "Ai
# list refreshes each 20 books graded"). ONE lock, the door credential read
# from the env FILE (never echoed, never on argv), tick.log rotated at 1 MB.
# The systemd unit FILES live agent-town-side (infra/services/ai-rek/);
# installing the timer stays the orchestrator's. Exit codes: 0 ok/skippad,
# 2 env-file saknas, else the runner's own code.
set -u
umask 077
ROT="${LISELOTT_ROT:-/home/claudecode/liselott}"
STAT="${AI_REK_STATE_DIR:-/home/claudecode/.liselott-rek}"
ENVFIL="${AI_REK_ENV_FILE:-/home/claudecode/.secrets/ai-rec-door.env}"
KORPUS="${AI_REK_CORPUS:-$STAT/corpus.tsv}"
LOGG="$STAT/tick.log"
mkdir -p "$STAT" && chmod 700 "$STAT"
export AI_REK_STATE_DIR="$STAT"
exec 9>"$STAT/tick.lock" || exit 1
if ! flock -n 9; then                          # en tick i taget — aldrig två
    echo "$(date -u +%FT%TZ) REDAN IGANG — ticken skipas" >> "$LOGG"
    exit 0
fi
if [ -f "$LOGG" ] && [ "$(stat -c %s "$LOGG" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    mv "$LOGG" "$LOGG.1"                       # rotated-at-1MB, one generation —
fi                                             # F-DA12-5: ONLY under the flock
{
    echo "== $(date -u +%FT%TZ) ai-rek refresh tick =="
    if [ ! -f "$ENVFIL" ]; then
        echo "AVVISAT: env-filen $ENVFIL saknas — ingen POST (exit 2)"
        exit 2
    fi
    set -a; . "$ENVFIL"; set +a                # NEVER set -x: the token must
    cd "$ROT" || exit 1                        # never reach the log; only
    .venv/bin/python -m scripts.ai_rek_pass --corpus "$KORPUS" --check-refresh
    rc=$?                                      # F-DA12-1: capture NOW — a dead
    echo "exit=$rc"                            # trigger may not call itself
} >> "$LOGG" 2>&1                              # success; the code rides out
exit "${rc:-0}"
