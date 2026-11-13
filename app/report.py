"""T5.5 — the F-2 loop's instrument: what covers exist, what is missing, and
which rows are VERIFIED-unobtainable.

Two JSON doors and one HTML page, all owner-only behind the guard:
* /rapa/omslag-rapport — the plan's verbatim contract: total / with_cover /
  missing / manual + `unobtainable` rows. The unobtainable definition is the
  M3 evidence columns taken seriously: enrich_fail=1 AND tried_providers
  covering ALL THREE provider names — a row nobody was ever allowed to ask is
  missing, not exhausted. Honest marking, never a fake cover.
* /rapa/omslag — the HTML worklist: every missing row with per-row buttons
  wired to THE three doors that already exist (retry through the provider
  door /omslag/<id>, a bare ISBN field posting to the edit door's per-field
  merge /redigera/<id>, a link to the upload form on the same page).
* /rapa/rekommendation-rapport — the P1-4 acceptance instrument:
  {"rated", "candidates", "pool_nonempty": candidates>0}.

The queries live here; M6's recommendation machinery will read the same
counts, not re-derive them (one mechanism, one place).
"""
from flask import render_template

from app import books, db, enrich

PROVIDER_NAMES = frozenset(enrich.PROVIDER_ORDER)      # ("libris","ol","gb")


def omslag_rapport(conn):
    q = lambda sql: conn.execute(sql).fetchone()[0]    # noqa: E731
    unobtainable = [
        {"id": rid, "title": title, "tried_providers": tried}
        for rid, title, tried in conn.execute(
            "SELECT id, title, tried_providers FROM book"
            " WHERE enrich_fail = 1 AND cover_path IS NULL ORDER BY id")
        if set((tried or "").split(",")) >= PROVIDER_NAMES]
    return {
        "total": q("SELECT COUNT(*) FROM book"),
        "with_cover": q("SELECT COUNT(*) FROM book"
                        " WHERE cover_path IS NOT NULL"),
        "missing": q("SELECT COUNT(*) FROM book WHERE cover_path IS NULL"),
        "manual": q("SELECT COUNT(*) FROM book"
                    " WHERE cover_source IN ('manual','manual-url')"),
        "unobtainable": unobtainable,
    }


def rekommendation_rapport(conn):
    return {
        "rated": conn.execute("SELECT COUNT(*) FROM book"
                              " WHERE rating IS NOT NULL").fetchone()[0],
        "candidates": conn.execute(
            "SELECT COUNT(*) FROM candidate").fetchone()[0],
        "pool_nonempty": conn.execute(
            "SELECT 1 FROM candidate LIMIT 1").fetchone() is not None,
    }


def init_report(app):

    @app.get("/rapa/omslag-rapport")
    def omslag_rapport_route():
        return omslag_rapport(db.get_db())             # Flask serialises dicts

    @app.get("/rapa/rekommendation-rapport")
    def rekommendation_rapport_route():
        return rekommendation_rapport(db.get_db())

    @app.get("/rapa/omslag")
    def omslag_sida():
        conn = db.get_db()
        report = omslag_rapport(conn)
        exhausted = {u["id"] for u in report["unobtainable"]}
        missing = [b for b in books.sort_by_read_date(books.load_books(conn))
                   if not b["has_cover"]]
        return render_template("omslag_rapa.html", saknar=missing,
                               rapport=report, uttomott=exhausted,
                               current="rapporter")
