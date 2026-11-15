#!/usr/bin/env bash
# MC 12533 — the pre-push SEALED-SHAPE smoke: run knut's vm100 verify seal over
# this repo's suite BEFORE pushing (MC 12526/12532: a file-posture bug passed
# five manual greens on two hosts and died ONLY under the seal; this is that
# seal, on demand, in ~2 min).
#
#   scripts/sealed_smoke.sh [SHA]      # default HEAD; KEEP=1 keeps the remote tree
#
# Flow mirrors knut's rerun (vm100:/opt/knut/bin/sandbox.py): fresh state dir,
# git-archive the SHA into it, NON-sealed pip fetch (pip needs the network),
# then the sealed verify unit writing a log whose tail is the answer.
# Exit = the pytest unit's exit. Honest limit: the flag list below is a MIRROR
# of vm100's seal — if the seal changes, refresh the literals (source named
# above them). This is a pre-push smoke, not the verifier.
set -euo pipefail

HOST=192.168.5.230                 # vm100, where knut's seal lives
SSH_USER=a3090                     # sudo -n is passwordless there
SSH="ssh -o BatchMode=yes $SSH_USER@$HOST"

SHA=$(git rev-parse "${1:-HEAD}")
S8=${SHA:0:8}
STATE=/var/tmp/sealed-smoke/$S8    # /var/tmp, never /tmp: the sealed unit is PrivateTmp=yes
SRC=$STATE/src

# knut's verify seal VERBATIM: the pairs of verify_argv in
# vm100:/opt/knut/bin/sandbox.py:105-125, read there 2026-11-15.
# RuntimeMaxSec=900 is that file's RUNTIME_MAX_VERIFY_S default;
# IPAddressAllow=localhost is its PRIVATE_LOOPBACK.
SEAL=(-p DynamicUser=yes -p PrivateDevices=yes -p DevicePolicy=closed
      -p IPAddressDeny=any -p IPAddressAllow=localhost -p PrivateNetwork=yes
      -p ProtectHome=yes -p ProtectSystem=strict -p NoNewPrivileges=yes
      -p MemoryMax=4G -p RuntimeMaxSec=900
      -p BindPaths="$STATE" -p ReadWritePaths="$STATE" -p WorkingDirectory="$SRC")

cleanup() { [ "${KEEP:-0}" = 1 ] || $SSH "sudo -n rm -rf $STATE" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "== $S8: shipping git-archive to $STATE"
git archive "$SHA" | $SSH "sudo -n rm -rf $STATE && sudo -n mkdir -p $SRC && sudo -n tar -x -C $SRC"

echo "== fetch stage (non-sealed — the network the seal denies)"
$SSH "sudo -n systemd-run --wait --collect --pipe --unit sealed-smoke-fetch /bin/sh -c 'cd $SRC && python3 -m pip install -q --no-cache-dir --disable-pip-version-check --no-input --target .knut-deps -r requirements.txt pytest==8.4.2'"

# ProtectSystem=strict + DynamicUser make the unit "other": the state tree is
# granted unit-writable here, the same preflight knut's rerun.py runs (the
# F-G note beside BindPaths in sandbox.py).
$SSH "sudo -n chmod -R a+rwX $STATE"

# \$\$PWD is systemd's literal \$ (sandbox.py systemd_literal): systemd eats
# bare $VAR, so /bin/sh must RECEIVE $$PWD to run its own $PWD after cd.
echo "== sealed verify stage"
rc=0
$SSH "sudo -n systemd-run --wait --collect --pipe --unit sealed-smoke-verify ${SEAL[*]} /bin/sh -c 'cd $SRC && PYTHONPATH=\$\$PWD/.knut-deps python3 -s -m pytest -q -p no:cacheprovider tests/ > ../out.txt 2>&1'" || rc=$?

echo "== tail $STATE/out.txt"
$SSH "sudo -n tail -n 12 $STATE/out.txt" || true
exit "$rc"
