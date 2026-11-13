"""The loop core shared by every door that walks enrichment (P2-d's one
mechanism, §8): ONE pacing courtesy (1 req/s, §12), ONE budget wrapper, and —
from T5.6 — the one scope/cursor selection. scripts/enrich_backfill.py (the
CLI) and app/backfill.py (the route) both run THESE functions, not twins.

The budget rule is deliberately honest: a provider the budget stopped is NOT
consulted, so it answers None (= "not asked"), the exact posture a cooldown
has since T3 — never an error, and never recorded in tried_providers. An
honest attempt log beats a full-looking one."""

PACE_S = 1.0                       # §12: 1 req/s against the providers


def with_budget(transports, budget_s, *, sleep, clock):
    """1 PACE_S pause before every CONSULTED provider call; past the budget the
    provider answers None (not consulted — the cooldown posture, NOT recorded
    in tried_providers). sleep/clock are parameters so the 6 s budget is
    testable without a wall clock (see test_add's budget leg)."""
    start = clock()
    wrapped = {}
    for name, transport in transports.items():
        if transport is None:
            wrapped[name] = None
            continue

        def call(title, authors, _t=transport):
            if clock() - start + PACE_S > budget_s:
                return None
            sleep(PACE_S)
            return _t(title, authors)

        wrapped[name] = call
    return wrapped


def paced(transports, pace):
    """1 req/s wrapped around every CONSULTED provider call (a transport the
    caller skips with None is not asked, so it never costs a pause). Moved
    verbatim from scripts/enrich_backfill.py when the app's own doors became
    its second caller — the CLI imports THIS, so there is no twin."""
    wrapped = {}
    for name, transport in transports.items():
        if transport is None:
            wrapped[name] = None
            continue

        def call(title, authors, _t=transport):
            pace(PACE_S)
            return _t(title, authors)

        wrapped[name] = call
    return wrapped


def paced_fetch(fetch, pace):
    """A cover image is an outbound request too — the 1 req/s courtesy covers
    it, not just the search calls. (Moved with paced; same reason.)"""
    def call(url, **kw):
        pace(PACE_S)
        return fetch(url, **kw)

    return call
