"""T5.6 — POST /backfill: the in-app twin of scripts/enrich_backfill.py.

One mechanism (P2-d): the route runs enrich_loop.scope_ids + run_pass +
candidates_pass — the CLI's own functions, looked up on the module AT CALL
TIME so tests can pin the mechanism (test_route_runs_the_CLIS_OWN_functions).
The pinned cursor (P2-d) is the whole contract: rows id > `after` ORDER BY id
LIMIT n, last_id = highest id CONSIDERED (poisoned rows included — the scan
completes), `after` past everything answers processed 0 / last_id == after.
n defaults 5, clamped to ≤20: a batch is a batch, not a hang.

/backfill is TOKENLESS (a same-origin machine POST, the /seed//bundle
vocabulary — T2.5's Origin gate still stands) but behind the login guard like
every owner door. It lives in app/backfill.py, not routes.py as the plan's
File line predates: routes.py was 166 lines and the brief's file-hygiene law
(~250 target) outranks a plan comment; the behavior is the plan's verbatim.

live_transports/pacer/http_get/ol_author_search are bound HERE (the
omslag/tillagg seam pattern) so a fixture substitutes the transport and
nothing else.
"""
import time

from flask import request

from app import db, enrich, enrich_loop, enrich_ol, seed

live_transports = enrich.live_transports     # bound: the fixture seam
pacer = time.sleep                            # bound: production paces 1 req/s
http_get = enrich.http_get                    # bound: the ONE http mechanism
ol_author_search = enrich_ol.author_search    # bound: candidates-mode transport

MAX_N = 20                          # the plan's clamp
REFRESH_DAYS = enrich_loop.REFRESH_DAYS     # T6.3: the window moved to the
                                   # shared core — route and CLI read it once


def _ints(request):
    try:
        n = int(request.args.get("n", 5))
        after = int(request.args.get("after", 0))
    except ValueError:
        return None, None
    return min(max(n, 1), MAX_N), max(after, 0)


def init_backfill(app):

    @app.post("/backfill")
    def backfill():
        n, after = _ints(request)
        if n is None:
            return {"fel": "n och after måste vara heltal."}, 400
        conn = db.get_db()
        mode = request.args.get("mode", "covers")
        if mode == "candidates":
            authors = enrich_loop.author_queue(conn, limit=n, after=after)
            last_id = authors[-1][0] if authors else after
            now, stale_before = enrich_loop.candidates_window()
            report = enrich_loop.candidates_pass(
                conn, authors,
                enrich_loop.paced_search(ol_author_search, pacer),
                now=now, stale_before=stale_before,
                aliases=seed.app_aliases())
            return {"processed": report["processed"],
                    "new_candidates": report["new_candidates"],
                    # the refresh observability: WHO was re-asked (the pool
                    # dedupe keeps new_candidates 0 on a healthy re-ask)
                    "fetched_authors": report["fetched"],
                    "failures": report["failures"],
                    "last_id": last_id}
        ids = enrich_loop.scope_ids(conn, limit=n, after=after)
        last_id = ids[-1] if ids else after        # the wrap signal, verbatim
        report = enrich_loop.run_pass(
            conn, ids,
            transports=enrich_loop.paced(live_transports(conn), pacer),
            fetch=enrich_loop.paced_fetch(http_get, pacer), pace=pacer)
        remaining = conn.execute(
            "SELECT COUNT(*) FROM book WHERE cover_path IS NULL"
        ).fetchone()[0]
        return {"processed": report["processed"],
                "new_covers": report["covers_stored"],
                "new_isbn": report["isbn_resolved"],
                "last_id": last_id,
                "remaining_missing_covers": remaining}
