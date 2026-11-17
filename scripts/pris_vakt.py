#!/usr/bin/env python3
"""MC 12547 (M9a-2a) — the daily pris-vakt runner (Bokus-only, §6a's unit
ExecStarts this; the parse rules live in the pure scripts/pris_parse.py and
the state files in scripts/pris_state.py — this file is the tick's mechanics).

CREDENTIALS — env NAMES only, values never here, never in a log, never in
git (MC 12546 owner ruling: Liselott's own password is copied NOWHERE):
  LISELOTT_URL     the site's own public edge; BOTH legs ride it (scope GET
                   `{base}/bibliotek`, door POST `{base}/pris`, HTTPS pinned
                   §6a). Missing => the tick goes RED before anything.
  PRIS_DOOR_TOKEN  the dedicated door credential, sent as `X-Pris-Token`
                   through the per-call 0600 `--config` tmpfile — never on
                   argv (MC 12616 c5, DA F-P2-1).
                   Missing => RED before anything (the door answers 503
                   disarmed anyway — asking Bokus for a tick that cannot
                   bank is waste, not politeness).

BROWSER PIN (§6a v2.2/§3 rule 4): boots
`~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome` by EXPLICIT
executable_path and asserts the launched version starts `153.` — python
playwright 1.60.0 resolves r1223 (Chrome 148) silently, so an unpinned boot
is an ALARM + non-zero exit with ZERO asks, and `playwright install` is
never called at tick time. No UA spoofing, no extra headers, no proxy
(§3 rule 3): the plain default chromium is the whole posture.

BUDGETS as printed constants, the §6a math in ONE place:
TimeoutStartSec=7200 covers the doc's own worst sweep —
  250 asks × (≥ PACE_S 5 s gap + PRIS_HYDRATE_TIMEOUT_MS 15 s ceiling)
  = 5 000 s + git pull/boot ≈ 5 100 s, so 7200 keeps ≈ 2 100 s margin
  (which absorbs the PRIS_GOTO_TIMEOUT_MS 15 s goto tail). The runner STOPS
asking at BUDGET_STOP_S (10 min BEFORE that line), flushes what it has and
exits non-zero `stop=time-budget` — a sweep never rides into the kill.

PER-TICK: scope from the public page (§2, ALARM on any scope_error), ≤ 250
asks with the excess FIFO-carried (§3 v2.4), a selector WAIT for hydration
(never a sleep), ≥ 5 s + jitter between Bokus visits, a door POST flush
every 25 accepted rows AND one at tick end (§6e cap 500 — never approached),
N=3 consecutive NO-PRICE books => STOP + watch_state + 24 h self-clearing
cooldown (the counter keys on NO-PRICE ONLY: the measured shelf answers
NOT-CARRIED/FORMAT for 5 of its 6 books PERMANENTLY, and a counter that
counted those would cool the watch down every single day — the same
misfire §3 F-D names for the chronic escalator, applied to its twin),
per-book outcome lines, ONE summary line (class counts, posted rows, own-
tree peak RSS) and exit 0 for a done or a resting tick.

ALARMKLASSER (owner ruling 2026-11-15, option 1 verbatim "alarm only for
real failures"): ALARM + non-zero ONLY for true failures — scope errors,
pin/version mismatch, door 503/rejected, N=3 stop, chronic parse-fails,
crash. A HEALTHY COMPLETE TICK that stored nothing (the shelf legitimately
holds ~0 readable Bokus prices) is a SUMMARY fact, not an alarm: the line
carries `stored 0 av N kollade` visibly, journald reads INFO, exit 0 — a
nightly zero alarm trains everyone to ignore real alarms (MC 12549).
"""
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import pris_parse as pp      # noqa: E402
from scripts import pris_state as st      # noqa: E402
from scripts.curl_transport import _curl, _curl_config   # noqa: E402
                                          # (MC 12570 transport, shared with
                                          # ai_rek_pass, MC 12601; secret
                                          # headers via _curl_config, MC 12616)

ENV_URL, ENV_TOKEN = "LISELOTT_URL", "PRIS_DOOR_TOKEN"
PIN_EXE = Path.home() / ".cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
PIN_VERSION_PREFIX = "153."                # the r1243 boot, measured 153.0.8010.12
PRIS_GOTO_TIMEOUT_MS = 15_000              # §3 named page-load ceiling
PRIS_HYDRATE_TIMEOUT_MS = 15_000           # §3 named hydration ceiling
TIMEOUT_START_S = 7200                     # §6a TimeoutStartSec (see header math)
BUDGET_STOP_S = TIMEOUT_START_S - 10 * 60  # stop 10 min before the systemd kill
MAX_ASKS_PER_TICK = 250                    # §3 ceiling; excess FIFO-carried (§6d)
PRIS_FLUSH_EVERY = 25                      # §3 delivery: flush every 25 rows
PACE_S, PACE_JITTER_S = 5.0, 2.0           # §6d ≥ 5 s + jitter before EVERY visit
SCOPE_PACE_S = 0.5                         # §2 same-origin courtesy
N_STOP = 3                                 # §3 fail-fast on consecutive NO-PRICE
COOLDOWN_S = 24 * 3600                     # §3 runner-local cooldown stamp
BOKUS_ASK = "https://www.bokus.com/bok/"   # + isbn13; slug is INERT (measured)
RETAILER, CURRENCY = "bokus", "SEK"        # §6e payload constants (door-checked)
STAMP_FMT = "%Y-%m-%dT%H:%M:%SZ"           # the door's checked_at shape (§1)
STATE_DIR = Path("/var/lib/pris-liselott")  # §6a StateDirectory
GET_TIMEOUT_S, POST_TIMEOUT_S = 15, 30      # ceilings: --max-time + watchdog


def http_get(url):
    """One anonymous GET of the site's OWN public page (§2 — the only
    plain-GET leg in the design; Bokus is never plain-fetched). Returns
    (status, text); status 0 is a transport failure, never a zero result.
    The transport is curl-subprocess (_curl, MC 12570 — urllib is GONE,
    the measured CF block); a non-200 rides with an empty body, exactly
    the old HTTPError mapping, so §2's alarm path is byte-for-byte."""
    status, body = _curl([url], timeout_s=GET_TIMEOUT_S)
    if 200 <= status < 300:
        return status, body.decode("utf-8", "replace")
    return status, ""


def door_post(url, token, rows):
    """The flush POST (§6e): JSON array of the five client-owned fields,
    `X-Pris-Token` on the dedicated header, the body via --data-binary @-
    on stdin — the same transport as the scope GET (MC 12570). MC 12616
    c5 (DA F-P2-1, fleet law "a shared fix reaches EVERY caller"): the
    secret header rides `_curl_config`'s per-call 0600 --config file —
    byte-identical ON THE WIRE (same name, same value), ZERO token bytes
    on the nightly tick's /proc/<curl>/cmdline. (N4b/MC 12606 retires
    this runner wholesale; this keeps the interval leak-free, minimal.)
    ONE try, then loud — §3's no-retry-loop. Returns (status,
    counters-dict); non-200 gives 0-status or the door's own error shape,
    and the runner never reads a body it cannot trust."""
    status, body = _curl_config(
        [("X-Pris-Token", token)],
        lambda config: ["--request", "POST",
                        "--header", "Content-Type: application/json",
                        "--config", config,
                        "--data-binary", "@-", url],
        timeout_s=POST_TIMEOUT_S,
        stdin_data=json.dumps(rows).encode("utf-8"))
    if not 200 <= status < 300:
        return status, {}
    try:
        return status, json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return 0, {}


def launch_pinned():
    """Boot the pinned chromium. playwright is imported HERE (lazy): the
    runner-class seams and the pure parser need no browser at all, and the
    unit's dependency surface stays honest. Never `playwright install`."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    return pw, pw.chromium.launch(headless=True, executable_path=str(PIN_EXE))


def ask_book(browser, isbn):
    """One book through the measured recipe: goto (named ceiling) → SELECTOR
    WAIT for hydration (never a sleep; a wait-timeout is the page's OWN
    ANSWER — the parser classes it FORMAT/NOT-CARRIED) → serialize the
    hydrated DOM to the pure parser with the final URL (the /bok/<A> →
    /bok/<B> family switch is why the payload keys on the WISHLIST isbn,
    never the landed one — measured 2/6). A page crash or a goto at its
    ceiling is THIS book's failed fetch: NO-PRICE, counted, never a
    restart-the-world event (§3 rule 1, parse rule 4)."""
    page = browser.new_page()
    try:
        page.goto(BOKUS_ASK + isbn, wait_until="domcontentloaded",
                  timeout=PRIS_GOTO_TIMEOUT_MS)
        try:
            page.wait_for_selector("text=" + pp.CART_TEXT,
                                   timeout=PRIS_HYDRATE_TIMEOUT_MS)
        except Exception:
            pass                       # no leaf by the ceiling = an answer
        return pp.classify_product(page.content(), page.url)
    except Exception:
        return pp.NO_PRICE, None
    finally:
        try:
            page.close()
        except Exception:
            pass


def run_tick(*, state_dir=STATE_DIR, now=None, clock=time.monotonic,
             sleep=time.sleep, get=http_get, post=door_post,
             launch=launch_pinned, rng=random.random, rss=st.tree_rss_kib,
             say=None):
    """One daily tick end-to-end; returns the process exit code (§6b as
    re-ruled 2026-11-15: 0 = done — also a healthy stored-0 run — or RESTING
    (cooldown/owner-stop); non-zero = every true-failure alarm class).
    Every external touch is a keyword seam (now/clock/sleep/get/post/launch/
    rng/rss/say) so the whole runner contract is testable with zero network —
    the REAL first tick (and §6a's cgroup row) is M9a-2b's, not this card's.
    The chronic escalator names ISBNS (the §1 payload key), the design's
    "book id(s)" resolved to the only identity the state file carries."""
    now = now or (lambda: datetime.now(timezone.utc))
    say = say or (lambda line: print(line, flush=True))
    counts = {klass: 0 for klass in (pp.PRICE, pp.AMBIGUOUS, pp.FORMAT,
                                     pp.NOT_CARRIED, pp.NO_PRICE)}
    scanned = no_isbn = gone = posted = stored = rejected = flushes = 0
    scope_error = stop = "-"
    chronic, unasked, rest, carried, blocked, peak = [], [], [], [], 0, 0
    no_price_isbns, rows = [], []
    version = "-"
    base = token = ""
    alive = True

    def sample_peak():
        nonlocal peak
        peak = max(peak, rss())
        return peak

    def finish(code):
        asked = sum(counts.values())
        say(f"PRIS SAMMANFATTNING scanned={scanned} asked={asked}"
            f" price={counts[pp.PRICE]} ambiguous={counts[pp.AMBIGUOUS]}"
            f" format={counts[pp.FORMAT]} not_carried={counts[pp.NOT_CARRIED]}"
            f" parse_fail={counts[pp.NO_PRICE]} no_isbn={no_isbn} gone={gone}"
            f" carried={len(carried)} rest={len(rest)} flushes={flushes}"
            f" posted={posted} stored {stored} av {asked} kollade"
            f" rejected={rejected}"
            f" blocked={blocked} stop={stop} chronic={','.join(chronic) or '-'}"
            f" scope_error={scope_error} peak_rss_kib={sample_peak()}"
            f" browser={version} exit={code}")
        return code

    def resting(kind):
        say(f"PRIS SAMMANFATTNING vilar={kind} scanned=0 asked=0"
            f" t_o_m={st.cooldown_stamp(state_dir) or '-'} exit=0")
        return 0

    # 1. The resting paths (§3 cooldown stamp, §6b/§6c the ONE status file)
    #    — a resting tick asks NOTHING: no scope read, no browser, exit 0.
    if st.cooldown_left(state_dir, now()) > 0:
        return resting("cooldown")
    reason = st.read_watch(state_dir)
    if reason is not None:
        if reason == st.AUTO_REASON:
            st.clear_watch(state_dir)      # cooldown passed: SELF-CLEARED
        else:
            return resting("owner-stop")   # §6c: stands until she resumes

    # 2. Config (§6a EnvironmentFile) — red BEFORE anything is touched.
    base = (os.environ.get(ENV_URL) or "").rstrip("/")
    token = os.environ.get(ENV_TOKEN) or ""
    saknas = [n for n, v in ((ENV_URL, base), (ENV_TOKEN, token)) if not v]
    if saknas:
        say(f"ALARM konfigur saknas: {','.join(saknas)} — noll ask")
        return finish(1)

    # 3. The scope read (§2) — the app's OWN public page, before any boot.
    status, html = get(f"{base}/bibliotek")
    if status != 200:
        scope_error = "fetch_failed"
        say(f"ALARM scope_error={scope_error} scope=0 (bibliotek {status})")
        return finish(1)
    ids, scope_error = pp.read_scope(html)
    if scope_error:
        say(f"ALARM scope_error={scope_error} scope=0")   # F-1: never silent
        return finish(1)
    scanned = len(ids)

    # 4. Per-id ISBN reads (§2 rule 4, same-origin courtesy pace).
    scope, first = [], True
    for book_id in ids:
        if not first:
            sleep(SCOPE_PACE_S)
        first = False
        status, page = get(f"{base}/bok/{book_id}")
        if 300 <= status < 400 or status == 404:
            gone += 1                      # wish removed mid-pass, benign (§2)
            continue
        if status != 200:
            scope_error = "fetch_failed"
            say(f"ALARM scope_error={scope_error} scope={scanned}")
            return finish(1)
        isbn, err = pp.read_isbn(page)
        if err:
            scope_error = err              # isbn_shape: OUR markup changed
            say(f"ALARM scope_error={scope_error} scope={scanned}")
            return finish(1)
        if isbn is None:
            no_isbn += 1                   # legitimate enrich debt (§2)
            continue
        scope.append(isbn)

    # 5. The FIFO carry (§3 v2.4 F-2): carried lines first (oldest wish
    #    wins), and a wish gone from today's page drops out of the carry too.
    in_scope = set(scope)
    carried = [i for i in st.read_carry(state_dir) if i in in_scope]
    queue = carried + [i for i in scope if i not in set(carried)]
    ask_list, rest = queue[:MAX_ASKS_PER_TICK], queue[MAX_ASKS_PER_TICK:]

    # 6. The pin, booted LOUD or not at all (§3 rule 4, §6a pin row) — but
    #    only when there IS an ask to make; a tick that asks nothing boots
    #    no browser and logs browser=- beside its zero counts.
    if ask_list:
        if not PIN_EXE.exists():
            say(f"ALARM browser_pin saknas: {PIN_EXE}")
            return finish(1)
        pw, browser = launch()
        version = str(getattr(browser, "version", ""))
        if not version.startswith(PIN_VERSION_PREFIX):
            # launched ≠ pinned is a FAILED TICK, never a green on a
            # stranger browser (F-E): ALARM + non-zero, ZERO asks.
            say(f"ALARM browser_ej_pinad launched={version} "
                f"forvantad={PIN_VERSION_PREFIX}* — noll ask")
            _shutdown(pw, browser)
            return finish(1)

        # 7. The ask loop — sequential, paced, budgeted, flush-at-25, N=3.
        def flush():
            nonlocal posted, stored, rejected, flushes, stop, alive
            if not rows:
                return True
            flushes += 1
            status, counters = post(f"{base}/pris", token, rows)
            if status != 200:
                alive = False              # one try, then loud (§3)
                stop = "door"
                say(f"ALARM dorren {status} — ett forsok, ingen retry-loop")
                return False
            posted += len(rows)
            stored += int(counters.get("accepted", 0))
            rejected += sum(int(counters.get(k, 0)) for k in
                            ("rejected_shape", "rejected_date",
                             "rejected_unknown"))
            rows.clear()
            sample_peak()
            return True

        consec, t0 = 0, clock()
        for i, isbn in enumerate(ask_list):
            if clock() - t0 >= BUDGET_STOP_S:
                stop, unasked = "time-budget", ask_list[i:]
                break                      # flush what we have, then exit 1
            sleep(PACE_S + rng() * PACE_JITTER_S)   # jittered floor ≥ 5 s
            klass, price = ask_book(browser, isbn)
            counts[klass] += 1
            say(f"PRIS BOK isbn={isbn} klass={klass} pris={price or '-'}")
            if klass == pp.NO_PRICE:
                no_price_isbns.append(isbn)
            consec = consec + 1 if klass == pp.NO_PRICE else 0
            if klass == pp.PRICE:
                rows.append({"isbn": isbn, "retailer": RETAILER,
                             "price": price, "currency": CURRENCY,
                             "checked_at": now().strftime(STAMP_FMT)})
            if len(rows) >= PRIS_FLUSH_EVERY and not flush():
                unasked = ask_list[i + 1:]
                break
            if consec >= N_STOP:
                stop, blocked = "consecutive_no_price", consec
                unasked = ask_list[i + 1:]
                st.stop_watch(state_dir, st.AUTO_REASON)   # self-clearing pair
                st.set_cooldown(state_dir,
                                now() + timedelta(seconds=COOLDOWN_S))
                break
        _shutdown(pw, browser)

        # 8. The end-of-tick flush (§6e delivery: TWO flush places, not one
        #    — a budget/blocked-stopped tick still banks what it saw).
        if rows and alive:
            flush()

    st.write_carry(state_dir, unasked + rest)   # the un-asked keep their place

    # 9. Chronic escalator (§3 F-D): NO-PRICE days only — the permanently
    #    NOT-CARRIED/FORMAT shelf books (measured 5/6!) never feed it, and
    #    neither does this escalator fire weekly on the 2 unlisted ISBNs.
    for isbn in no_price_isbns:
        st.bump_parse_fail(state_dir, isbn, now())
    chronic = st.chronic_offenders(state_dir, now())

    # 10. The verdict (§2/§3/§6e's named red classes; PARTIAL stays data).
    #     The zero-store sentinel is GONE here (owner ruling 2026-11-15,
    #     MC 12549): a healthy complete tick with stored 0 is a SUMMARY fact
    #     — the `stored 0 av N kollade` clause, journald INFO, exit 0. A
    #     flush that delivered nothing against real rows stays red through
    #     the door's own counters: every non-accepted row lands in a
    #     rejected_* class (§6e), so `rejected > 0` still bites.
    code = 0
    if stop in ("time-budget", "consecutive_no_price", "door") \
            or rejected > 0 or chronic:
        code = 1
    if stop == "consecutive_no_price":
        say(f"ALARM blocker={blocked} stop={stop} — 24 h nedkylning satt")
    if chronic:
        say(f"ALARM chronic parse-fail 7 dagar: {','.join(chronic)}")
    return finish(code)


def _shutdown(pw, browser):
    try:
        browser.close()
    finally:
        try:
            pw.stop()
        except Exception:
            pass


def main():
    sys.exit(run_tick())


if __name__ == "__main__":
    main()
