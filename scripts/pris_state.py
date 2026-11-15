"""MC 12547 (M9a-2a) — the runner's local state files (§6a StateDirectory
= /var/lib/pris-liselott, the unit's ONLY writable path).

Four files, four concerns (§3 fail-fast / §6b-§6c the ONE status file /
§3 v2.4 F-2 the FIFO carry / §3 v2.3 F-D the chronic escalator) — nothing
here is authority (the app's own `price` table is, §2), it is politeness
and alarm state that cannot live in the vm106 DB the runner cannot see:

  watch_state      `watch_stopped=1 reason=<r>`. Written by an N=3 stop
                   (reason=consecutive_no_price, self-clearing: the runner
                   deletes it once its own cooldown has passed) and by the
                   owner's stop (reason=owner-stop, §6c: it stands until she
                   resumes). §6b's gap-alarm reads the SAME file — a
                   deliberate stop mutes the forever-alarm, never a state.
  cooldown_until   the §3 runner-local cooldown, an UTC stamp 24 h ahead
                   (the enrich_gb future-stamp posture, runner-side because
                   the settings table is in the vm106 jail). Future stamp =>
                   the tick asks NOTHING and exits 0 RESTING.
  carry_over       one isbn per line — the >250 books/tick FIFO (§3 v2.4
                   F-2), oldest wish first (page order), next tick asks the
                   carried lines BEFORE fresh ones.
  parse_fails.json {isbn: [iso-day, …]} of NO-PRICE days, pruned past 7.
                   >= 3 DISTINCT DAYS on one isbn => ESCALATE (F-D). Only
                   the unexpected-parse class is bumped — a permanently
                   NOT-CARRIED/FORMAT book is a clean answer forever and
                   must never fire this (measured: 2/6 of the shelf).

Plus `tree_rss_kib`: the tick's own process tree (driver + every chromium
descendant, the sweep's VmRSS-sum idiom), sampled through the pass — the
§6a first-tick cgroup row stays OWED by the real first tick (M9a-2b); this
is the runner's own peak line in its summary in the meantime.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

WATCH = "watch_state"
COOLDOWN = "cooldown_until"
CARRY = "carry_over"
FAILS = "parse_fails.json"
STAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"
AUTO_REASON = "consecutive_no_price"       # the self-clearing stop
CHRONIC_DAYS = 7
CHRONIC_MIN = 3


def _read(dir_, name):
    try:
        return (Path(dir_) / name).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def _write(dir_, name, text):
    Path(dir_).mkdir(parents=True, exist_ok=True)
    (Path(dir_) / name).write_text(text, encoding="utf-8")


def _rm(dir_, name):
    try:
        (Path(dir_) / name).unlink()
    except FileNotFoundError:
        pass


def read_watch(dir_):
    """The stop reason, or None: parses `watch_stopped=1 reason=<r>`."""
    for line in _read(dir_, WATCH).splitlines():
        parts = dict(p.split("=", 1) for p in line.split() if "=" in p)
        if parts.get("watch_stopped") == "1":
            return parts.get("reason") or "owner-stop"
    return None


def stop_watch(dir_, reason):
    _write(dir_, WATCH, f"watch_stopped=1 reason={reason}\n")


def clear_watch(dir_):
    _rm(dir_, WATCH)


def cooldown_left(dir_, now):
    """Seconds left on the future cooldown stamp (0 = none/expired)."""
    stamp = _read(dir_, COOLDOWN)
    if not stamp:
        return 0
    try:
        until = _parse_stamp(stamp)
    except ValueError:
        return 0
    return max(0, int((until - now).total_seconds()))


def cooldown_stamp(dir_):
    """The raw stamp text ("" when no cooldown file) — for the resting
    tick's `vilar (cooldown t.o.m. …)` summary line."""
    return _read(dir_, COOLDOWN)


def set_cooldown(dir_, until):
    _write(dir_, COOLDOWN, until.strftime(STAMP_FMT) + "\n")


def clear_cooldown(dir_):
    _rm(dir_, COOLDOWN)


def read_carry(dir_):
    return _read(dir_, CARRY).split()


def write_carry(dir_, isbns):
    if isbns:
        _write(dir_, CARRY, "".join(f"{i}\n" for i in isbns))
    else:
        _rm(dir_, CARRY)


def bump_parse_fail(dir_, isbn, now):
    """Record one NO-PRICE day (one per day — the set is DISTINCT days) for
    one isbn, pruned to the 7-day window. Returns the isbn's stored days."""
    day = now.strftime("%Y-%m-%d")
    fails = _load_fails(dir_, now)
    days = sorted({*fails.get(isbn, []), day})
    fails[isbn] = days
    Path(dir_).mkdir(parents=True, exist_ok=True)
    (Path(dir_) / FAILS).write_text(json.dumps(fails, sort_keys=True),
                                    encoding="utf-8")
    return days


def chronic_offenders(dir_, now):
    """isbns with >= CHRONIC_MIN distinct NO-PRICE days inside the last
    CHRONIC_DAYS (the F-D escalate names these isbns loudly)."""
    return sorted(isbn for isbn, days in _load_fails(dir_, now).items()
                  if len(days) >= CHRONIC_MIN)


def _load_fails(dir_, now):
    raw = _read(dir_, FAILS)
    if not raw:
        return {}
    floor = (now - timedelta(days=CHRONIC_DAYS)).strftime("%Y-%m-%d")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out = {}
    for isbn, days in data.items():
        keep = sorted({d for d in days if isinstance(d, str) and d >= floor})
        if keep:
            out[isbn] = keep
    return out


def _parse_stamp(stamp):
    return datetime.strptime(stamp, STAMP_FMT).replace(tzinfo=timezone.utc)


def tree_rss_kib(pid=None):
    """Sum of VmRSS (kB) over this pid's whole descendant tree — the sweep's
    own instrument idiom. Reads /proc; a pid that vanished mid-walk is
    skipped, never fatal (a summary line must not crash a tick)."""
    pid = pid or os.getpid()
    kids, rss = {}, {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        p = int(entry)
        try:
            stat = Path(f"/proc/{p}/stat").read_text()
            ppid = int(stat[stat.rindex(")") + 2:].split()[1])
            kids.setdefault(ppid, []).append(p)
            for line in Path(f"/proc/{p}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    rss[p] = int(line.split()[1])
                    break
        except (OSError, ValueError, IndexError):
            continue
    total, stack = 0, [pid]
    while stack:
        p = stack.pop()
        total += rss.get(p, 0)
        stack.extend(kids.get(p, []))
    return total
