"""MC 12547 (M9a-2a) — the pris-vakt RUNNER legs over faked seams (zero
network, zero real browser — the first REAL Bokus visit is M9a-2b's). The
parser legs these depend on, with the synthetic fragments they feed, are in
tests/test_pris_parse.py; the class semantics are restated below. Planted-red
per gate (one mutant at a time, sha-verified restore):
`.tmp/m9a2a-planted-red.md`.
(continued from the card contract: five classes — PRICE one token 1..20000 in
the first token-bearing ancestor of the cart leaf; AMBIGUOUS two+ tokens, the
named campaign expected-miss, never a posted price; FORMAT identity-OK but no
cart leaf after the hydration wait (e-bok/ljudbok), never another number on
the page; NOT-CARRIED identity fail — the title tail `| Bokus` + the /bok/
URL are the ONLY gates, a status code never reaches the parser (measured:
not-found answers HTTP 200); NO-PRICE the one unexpected-parse class — and
THE READING THIS CARD FIXED: the N=3 consecutive stop and the 7-day chronic
escalator key on NO-PRICE ONLY, because the measured shelf answers
NOT-CARRIED/FORMAT for 5 of its 6 books PERMANENTLY and any wider key cools
the watch down every single day.)

RUNNER legs (seams faked end-to-end: get/post/launch/clock/sleep/rng/rss):
  flush-at-25             30 priced books => POSTs of exactly [25, 5]
  row-shape               the five §6e client-owned fields, bokus/SEK,
                          checked_at in the door's pinned stamp shape
  budget-stop             a 300 s/book clock: stop at 6 600 s elapsed
                          (10 min before §6a's 7200), partial flush banks,
                          exit non-zero, un-asked books carried
  n3-stop                 3 consecutive NO-PRICE books: stop, watch_state
                          (reason=consecutive_no_price) + cooldown_until =
                          now + 24 h written, exit non-zero
  cooldown-honored        the next tick rests: exit 0, ZERO asks
  cooldown-self-clears    after the stamp passes, the auto-stop clears and
                          the watch asks again
  owner-stop              watch_stopped reason=owner-stop rests WITHOUT a
                          cooldown (it stands until §6c's resume)
  scope-empty-alarm       section_missing / empty_section / fetch_failed =>
                          ALARM line + non-zero + ZERO boots, ZERO posts
  fifo-carry-250          a 260-book scope: 250 asked, 10 carried; the next
                          tick asks the CARRIED 10 FIRST
  version-alarm           a fake browser answering 148.* => ALARM + non-zero
                          with ZERO asks (never the library-default boot)
  pin-missing             the pinned binary path absent => ALARM, never a
                          launch call
  pacing                  every pre-visit sleep ≥ 5.0 s (jitter injectable,
                          fake clock — tests never sleep)
  chronic-escalates       the same isbn NO-PRICE 3 days within 7 => the tick
                          names it + non-zero
  chronic-blind-proof     3 days of NOT-CARRIED (a permanently unlisted isbn,
                          measured 2/6 of the shelf!) => chronic stays EMPTY
                          (the weekly-cry case is dead, not untested)
  zero-store-alarm        asked > 0 and stored == 0 => non-zero (§3's
                          zero-price sentinel), stop stays "-"
  door-503                the door answers 503: ONE try, no retry loop, stop
                          =door, non-zero
  door-rejected           counters with rejected_* > 0 => non-zero (§6e)
  config-missing          LISELOTT_URL / PRIS_DOOR_TOKEN absent => ALARM
                          before ANY get, ANY boot, ANY post
  no-isbn-and-gone        the legit skip + the 404-gone are counted, green
  summary                 exactly ONE summary line per tick, class counts,
                          posted rows, injected peak rss shows up, version
  tree-rss                the own-tree instrument reads /proc and answers >0
"""
import re
from datetime import datetime, timedelta, timezone

from scripts import pris_state as st
from scripts import pris_vakt as pv
from tests.test_pris_parse import BOKUS_URL, FRAG, bok_html, isbn, scope_html

NU = datetime(2026, 11, 15, 7, 20, tzinfo=timezone.utc)
DOOR_CRED = "syntetisk-dorr-979"        # fixture-only credential (MC 12546 idiom)


# --- runner fakes (seams; zero network, zero real browser) ------------------
class Clock:
    def __init__(self):
        self.t = 1_000.0

    def monotonic(self):
        return self.t


class FakeNow:
    def __init__(self, start=NU):
        self.t = start

    def __call__(self):
        return self.t


class FakeSleep:
    def __init__(self, clock, advance=0.0):
        self.clock, self.advance, self.calls = clock, advance, []

    def __call__(self, seconds):
        self.calls.append(seconds)
        self.clock.t += self.advance


class FakeSite:
    def __init__(self, ids, pages=None, scope=None):
        self.ids, self.scope, self.calls = ids, scope, []
        self.pages = pages or {}

    def get(self, url):
        self.calls.append(url)
        if url.endswith("/bibliotek"):
            return 200, self.scope if self.scope is not None else scope_html(self.ids)
        bid = re.search(r"/bok/(\d+)$", url).group(1)
        return self.pages.get(bid, (200, bok_html(isbn(int(bid)))))


class FakePage:
    def __init__(self, browser, isbn13):
        self.browser, self.isbn = browser, isbn13

    def goto(self, url, **kw):
        if self.browser.crash and self.isbn in self.browser.crash:
            raise RuntimeError("page crashed")
        self.browser.asked.append(self.isbn)

    def wait_for_selector(self, selector, timeout=None):
        if self.browser.kinds.get(self.isbn, self.browser.default) == "format":
            raise TimeoutError("hydration ceiling")   # the measured shape

    def content(self):
        return FRAG[self.browser.kinds.get(self.isbn, self.browser.default)]

    @property
    def url(self):
        return BOKUS_URL + self.isbn

    def close(self):
        pass


class FakeBrowser:
    """goto(BOKUS_ASK+isbn) is the only channel — the page answers per isbn."""

    def __init__(self, kinds=None, default="price", version="153.0.8010.12",
                 crash=()):
        self.kinds, self.default, self.version = kinds or {}, default, version
        self.crash = set(crash)
        self.asked, self.closed = [], False

    def new_page(self):
        browser = self

        class _Maker(FakePage):
            def __init__(self):
                super().__init__(browser, None)

            def goto(self, url, **kw):
                self.isbn = url.rsplit("/", 1)[-1]
                super().goto(url, **kw)
        return _Maker()

    def close(self):
        self.closed = True


class FakePW:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class FakeLaunch:
    def __init__(self, browser):
        self.browser, self.n = browser, 0

    def __call__(self):
        self.n += 1
        return FakePW(), self.browser


class FakeDoor:
    def __init__(self, status=200, rejected=0):
        self.status, self.rejected, self.posts = status, rejected, []

    def post(self, url, token, rows):
        assert url == "https://sibbamala.test/liselott/pris"
        assert token == DOOR_CRED
        self.posts.append(list(rows))
        if self.status != 200:
            return self.status, {}
        return 200, {"accepted": len(rows) - self.rejected, "inserted": len(rows),
                     "updated": 0, "suspect": 0, "rejected_unknown": self.rejected,
                     "rejected_shape": 0, "rejected_date": 0}


def summary(lines):
    got = [ln for ln in lines if ln.startswith("PRIS SAMMANFATTNING")]
    assert len(got) == 1, lines               # ONE summary line — asserted always
    return got[0]


def run(tmp_path, monkeypatch, *, site=None, browser=None, door=None,
        now=None, advance=0.0, rng=lambda: 0.0, rss=lambda: 4242,
        token=DOOR_CRED, url_env="https://sibbamala.test/liselott/", pin=True):
    """One fake-seamed tick; returns (code, lines, sleeper, launch)."""
    if url_env is None:
        monkeypatch.delenv(pv.ENV_URL, raising=False)
    else:
        monkeypatch.setenv(pv.ENV_URL, url_env)
    if token is None:
        monkeypatch.delenv(pv.ENV_TOKEN, raising=False)
    else:
        monkeypatch.setenv(pv.ENV_TOKEN, token)
    exe = tmp_path / "pinned-chrome"
    if pin:
        exe.touch()
    monkeypatch.setattr(pv, "PIN_EXE", exe)
    site, browser, door = site or FakeSite([]), browser or FakeBrowser(), \
        door or FakeDoor()
    clock, lines = Clock(), []
    sleeper = FakeSleep(clock, advance)
    launch = FakeLaunch(browser)
    code = pv.run_tick(state_dir=tmp_path / "state", now=now or FakeNow(),
                       clock=clock.monotonic, sleep=sleeper, get=site.get,
                       post=door.post, launch=launch, rng=rng, rss=rss,
                       say=lines.append)
    return code, lines, sleeper, launch, site, browser, door


# --- runner legs ------------------------------------------------------------
def test_flush_at_25(tmp_path, monkeypatch):
    """30 priced books => exactly POSTs of [25, 5] (the 25-row flush + the
    end-of-tick flush); nothing beyond the door's 500 cap, ever."""
    site = FakeSite([str(n) for n in range(1, 31)])
    code, lines, _, _, _, _, door = run(tmp_path, monkeypatch, site=site)
    assert [len(p) for p in door.posts] == [25, 5]
    assert code == 0
    assert "stored=30" in summary(lines)


def test_row_shape_is_the_five_door_fields(tmp_path, monkeypatch):
    site = FakeSite(["1"])
    _, _, _, _, _, _, door = run(tmp_path, monkeypatch, site=site)
    row = door.posts[0][0]
    assert set(row) == {"isbn", "retailer", "price", "currency", "checked_at"}
    assert row["isbn"] == isbn(1) and row["price"] == 99
    assert row["retailer"] == "bokus" and row["currency"] == "SEK"
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", row["checked_at"])


def test_budget_stop_banks_and_carries(tmp_path, monkeypatch):
    """300 s per book against the injected clock: the tick stops at 6 600 s
    (10 min before §6a's 7200), banks the 22 rows it has, keeps the 8 it
    never asked, and exits non-zero naming time-budget."""
    site = FakeSite([str(n) for n in range(1, 31)])
    code, lines, _, _, _, browser, door = run(
        tmp_path, monkeypatch, site=site, advance=300.0)
    assert code == 1 and "stop=time-budget" in summary(lines)
    assert len(browser.asked) == 22
    assert [len(p) for p in door.posts] == [22]
    carry = (tmp_path / "state" / st.CARRY).read_text().split()
    assert carry == [isbn(n) for n in range(23, 31)]


def test_n3_stops_writes_watch_and_cooldown(tmp_path, monkeypatch):
    site = FakeSite(["1", "2", "3", "4", "5"])
    browser = FakeBrowser(kinds={isbn(n): "nobox" for n in (1, 2)},
                          crash={isbn(3)})
    code, lines, _, _, _, browser, door = run(
        tmp_path, monkeypatch, site=site, browser=browser)
    assert code == 1
    assert "stop=consecutive_no_price" in summary(lines)
    assert "parse_fail=3" in summary(lines)        # the 3rd book CRASHED at
    assert browser.asked == [isbn(1), isbn(2)]     # goto — counted NO-PRICE,
    #                                                never a restart-the-world
    assert isbn(4) not in browser.asked            # the stop precedes book 4
    assert not door.posts                          # nothing banked yet
    state = tmp_path / "state"
    assert f"watch_stopped=1 reason={st.AUTO_REASON}" in \
        (state / st.WATCH).read_text()
    assert (state / st.COOLDOWN).read_text().strip() == \
        (NU + timedelta(hours=24)).strftime(pv.STAMP_FMT)


def test_cooldown_is_honored_next_tick(tmp_path, monkeypatch):
    site1 = FakeSite(["1", "2", "3"])
    browser1 = FakeBrowser(kinds={isbn(1): "nobox", isbn(2): "nobox",
                                  isbn(3): "nobox"})
    run(tmp_path, monkeypatch, site=site1, browser=browser1)
    site2, browser2, door2 = FakeSite(["1"]), FakeBrowser(), FakeDoor()
    code, lines, _, launch, _, _, _ = run(
        tmp_path, monkeypatch, site=site2, browser=browser2, door=door2,
        now=FakeNow(NU + timedelta(hours=1)))
    assert code == 0 and "vilar=cooldown" in summary(lines)
    assert site2.calls == [] and browser2.asked == [] and not door2.posts
    assert launch.n == 0                            # no browser booted at all


def test_cooldown_self_clears_after_24h(tmp_path, monkeypatch):
    site1 = FakeSite(["1", "2", "3"])
    kinds = {isbn(n): "nobox" for n in (1, 2, 3)}
    run(tmp_path, monkeypatch, site=site1, browser=FakeBrowser(kinds=kinds))
    code, lines, _, _, _, browser, door = run(
        tmp_path, monkeypatch, site=FakeSite(["1"]),
        now=FakeNow(NU + timedelta(hours=25)))
    assert code == 0 and browser.asked == [isbn(1)]
    assert not (tmp_path / "state" / st.WATCH).exists()   # SELF-cleared


def test_owner_stop_rests_without_a_cooldown(tmp_path, monkeypatch):
    st.stop_watch(tmp_path / "state", "owner-stop")
    site, browser, door = FakeSite(["1"]), FakeBrowser(), FakeDoor()
    code, lines, _, launch, _, _, _ = run(
        tmp_path, monkeypatch, site=site, browser=browser, door=door)
    assert code == 0 and "vilar=owner-stop" in summary(lines)
    assert site.calls == [] and not door.posts and launch.n == 0


def test_scope_empty_section_missing_alarms(tmp_path, monkeypatch):
    site = FakeSite([], scope="<html><body><h2>Något annat</h2></body></html>")
    code, lines, _, launch, _, browser, door = run(tmp_path, monkeypatch,
                                                   site=site)
    assert code == 1 and "scope_error=section_missing" in " ".join(lines)
    assert launch.n == 0 and not browser.asked and not door.posts


def test_scope_empty_section_alarms(tmp_path, monkeypatch):
    site = FakeSite([], scope='<section class="grupp"><h2>Att läsa</h2>'
                             "<ul></ul></section>")
    code, lines, *_ = run(tmp_path, monkeypatch, site=site)
    assert code == 1 and "scope_error=empty_section" in " ".join(lines)


def test_scope_fetch_failed_alarms(tmp_path, monkeypatch):
    site = FakeSite([])
    site.get = lambda url: (500, "")
    code, lines, *_ = run(tmp_path, monkeypatch, site=site)
    assert code == 1 and "scope_error=fetch_failed" in " ".join(lines)


def test_fifo_carry_past_250(tmp_path, monkeypatch):
    """260 books in scope: the tick asks the FIRST 250 and carries 10; the
    next tick asks the CARRIED 10 FIRST, then fresh ones (oldest wish
    first — the shelf renders wish age)."""
    ids = [str(n) for n in range(1, 261)]
    site1, browser1 = FakeSite(ids), FakeBrowser()
    code, lines, _, _, _, browser1, door1 = run(tmp_path, monkeypatch,
                                                site=site1)
    assert code == 0
    assert browser1.asked == [isbn(n) for n in range(1, 251)]
    carry_file = (tmp_path / "state" / st.CARRY).read_text().split()
    assert carry_file == [isbn(n) for n in range(251, 261)]
    assert len(door1.posts) == 10                   # 250 rows, flush-at-25
    browser2 = FakeBrowser()
    code2, lines2, *_ , _, browser2, _ = run(
        tmp_path, monkeypatch, site=FakeSite(ids), browser=browser2,
        door=FakeDoor())
    assert code2 == 0
    assert browser2.asked[:10] == [isbn(n) for n in range(251, 261)]


def test_pinned_version_assert_alarm_without_asks(tmp_path, monkeypatch):
    """A browser answering 148.* (what playwright 1.60 boots on its own
    r1223 default) is an ALARM + non-zero with ZERO asks — the pin is
    load-bearing, not decorative (F-E)."""
    browser = FakeBrowser(version="148.0.7778.97")
    code, lines, _, _, _, browser, door = run(
        tmp_path, monkeypatch, site=FakeSite(["1"]), browser=browser)
    assert code == 1 and "browser_ej_pinad" in " ".join(lines)
    assert not browser.asked and not door.posts
    assert browser.closed


def test_missing_pin_binary_alarms_without_launch(tmp_path, monkeypatch):
    launch_seen = []
    site = FakeSite(["1"])
    code, lines, _, launch, _, _, _ = run(tmp_path, monkeypatch, site=site,
                                          pin=False)
    assert code == 1 and "browser_pin saknas" in " ".join(lines)
    assert launch.n == 0


def test_pacing_floor_5s_injected_clock(tmp_path, monkeypatch):
    site = FakeSite(["1", "2", "3"])
    code, lines, sleeper, _, _, browser, _ = run(tmp_path, monkeypatch,
                                                 site=site)
    visit_paces = [s for s in sleeper.calls if s >= pv.PACE_S]
    assert len(visit_paces) == len(browser.asked) == 3
    assert all(s >= 5.0 for s in visit_paces)         # the ≥ 5 s floor
    assert all(s == pv.SCOPE_PACE_S for s in sleeper.calls
               if s < pv.PACE_S)                      # own-origin courtesy


def test_pacing_jitter_stays_above_the_floor(tmp_path, monkeypatch):
    code, lines, sleeper, _, _, _, _ = run(
        tmp_path, monkeypatch, site=FakeSite(["1"]), rng=lambda: 0.999)
    pace = [s for s in sleeper.calls if s >= pv.PACE_S][0]
    assert pv.PACE_S <= pace <= pv.PACE_S + pv.PACE_JITTER_S


def test_chronic_escalates_on_three_no_price_days(tmp_path, monkeypatch):
    for day in range(3):
        code, lines, *_ = run(
            tmp_path, monkeypatch, site=FakeSite(["1"]),
            browser=FakeBrowser(kinds={isbn(1): "nobox"}),
            now=FakeNow(NU + timedelta(days=day)))
    assert code == 1 and isbn(1) in summary(lines)
    assert f"chronic={isbn(1)}" in summary(lines)


def test_chronic_never_fires_on_permanently_not_carried(tmp_path, monkeypatch):
    """The measured shelf carries TWO isbn Bokus does not list — permanently.
    Three ticks of NOT-CARRIED must keep chronic EMPTY (the alarm that cried
    weekly is this leg's red case). The zero-store alarm still makes the
    tick red, but the chronic escalator stays out of it."""
    for day in range(3):
        code, lines, *_ = run(
            tmp_path, monkeypatch, site=FakeSite(["1"]),
            browser=FakeBrowser(kinds={isbn(1): "notfound"}),
            now=FakeNow(NU + timedelta(days=day)))
    line = summary(lines)
    assert "chronic=-" in line and "parse_fail=0" in line
    assert code == 1 and "stop=-" in line


def test_zero_store_sentinel_alarms(tmp_path, monkeypatch):
    code, lines, *_ = run(tmp_path, monkeypatch, site=FakeSite(["1", "2"]),
                         browser=FakeBrowser(default="format"))
    assert code == 1 and "stop=-" in summary(lines)
    assert any("noll prisrad" in ln for ln in lines)


def test_door_503_one_try_no_retry_loop(tmp_path, monkeypatch):
    door = FakeDoor(status=503)
    code, lines, _, _, _, _, door = run(tmp_path, monkeypatch,
                                        site=FakeSite(["1", "2"]), door=door)
    assert code == 1
    assert len(door.posts) == 1                      # ONE try, then loud
    assert "stop=door" in summary(lines)


def test_door_rejected_rows_go_red(tmp_path, monkeypatch):
    code, lines, *_ = run(tmp_path, monkeypatch, site=FakeSite(["1"]),
                         door=FakeDoor(rejected=1))
    assert code == 1 and "rejected=1" in summary(lines)


def test_config_missing_is_red_before_anything(tmp_path, monkeypatch):
    site, browser, door = FakeSite(["1"]), FakeBrowser(), FakeDoor()
    code, lines, _, launch, site, browser, door = run(
        tmp_path, monkeypatch, site=site, browser=browser, door=door,
        token="")
    assert code == 1 and "konfigur saknas" in " ".join(lines)
    assert site.calls == [] and launch.n == 0 and not door.posts


def test_no_isbn_and_gone_are_counted_green(tmp_path, monkeypatch):
    site = FakeSite(["1", "2", "3"], pages={"2": (200, bok_html(None)),
                                            "3": (404, "")})
    code, lines, *_ = run(tmp_path, monkeypatch, site=site)
    line = summary(lines)
    assert code == 0 and "no_isbn=1" in line and "gone=1" in line
    assert "stored=1" in line


def test_summary_is_one_line_with_counts_and_peak(tmp_path, monkeypatch):
    code, lines, *_ = run(tmp_path, monkeypatch, site=FakeSite(["1", "2"]),
                         rss=lambda: 424242)
    line = summary(lines)
    assert "peak_rss_kib=424242" in line
    assert "browser=153.0.8010.12" in line
    assert "price=2" in line and "exit=0" in line
    assert sum(1 for ln in lines if ln.startswith("PRIS BOK")) == 2


def test_tree_rss_reads_the_real_proc(tmp_path):
    assert st.tree_rss_kib() > 0                     # this very process
