"""T5.3 — the add door and the two provider/upload cover doors.

/lagg-till (GET page + POST), POST /omslag/<id> ("Hämta omslag": the SAME
resolve_book the backfill loop runs, in-request, under the runbook's 6 s
budget), POST /omslag/<id>/ladda-up (manual upload). All three ride existing
mechanisms and add none: form validation is redigera.form_to_fields (the same
field vocabulary and messages as the edit door — two doors, one validator),
the key/author write is seed.set_authors + seed.book_key, the byte budget is
enrich.MAX_BODY, the image normalizer is enrich.store_cover (its 1×1 stub
gate guards this door too — no fake covers, ever), and pacing is
app.enrich_loop.with_budget.

Enrichment is on the PRODUCTION code path: a book added in production
self-enriches through live_transports — no bundle, no VM350 in this loop
(F-1's ruling). It runs AFTER the row commits: an add must never fail because
a provider did; the residue lands in the honest evidence columns and the
placeholder keeps painting honestly.

live_transports/pacer/http_get are bound HERE (the omslag.py pattern) so a
test substitutes the transport and nothing else.
"""
from datetime import date, datetime
import time

from flask import abort, render_template, request

from app import auth, books, db, enrich, enrich_loop, redigera, seed

BUDGET_S = 6.0                     # runbook: /omslag/<id> is synchronous ≤6 s
MAX_UPLOAD = enrich.MAX_BODY       # 900 000 — the ONE byte budget (P1-1)
OVER_CAP_COPY = "Bilden är för stor — ladda upp en mindre fil"

live_transports = enrich.live_transports     # bound: the test seam (omslag pattern)
pacer = time.sleep                           # bound: production paces 1 req/s
http_get = enrich.http_get                   # bound: the ONE http mechanism


def _enrich_in_request(conn, book_id):
    """Add and Hämta-omslag share this ONE call — resolve_book under the 6 s
    budget; never raises out (resolve_book's own contract is 'a failing row is
    a written row'; the try is the belt for the add flow: the row is already
    the owner's and stays whatever the providers managed to fill)."""
    try:
        enrich.resolve_book(
            conn, book_id,
            transports=enrich_loop.with_budget(live_transports(conn), BUDGET_S,
                                               sleep=pacer, clock=time.monotonic),
            fetch=enrich_loop.paced_fetch(http_get, pacer))
    except Exception:
        pass


def init_tillagg(app):

    @app.get("/lagg-till")
    def lagg_till():
        return render_template("tillagg.html", today=date.today().isoformat(),
                               fel=None, bok=None, current="lagg-till")

    @app.post("/lagg-till")
    def spara_tillagg():
        conn = db.get_db()
        form = dict(request.form)
        form.setdefault("titel", "")             # a title-less POST is an empty title
        values, fel = redigera.form_to_fields(form, {})
        if fel:
            return render_template("tillagg.html", today=date.today().isoformat(),
                                   fel=fel, bok=None, current="lagg-till"), 400
        authors = seed.split_authors(form.get("forfattare", ""))
        read_date = values["date_read"] or date.today().isoformat()
        now = auth.utcnow_iso()
        # The key uses the CSV alias mapping exactly as seed.load does (the
        # author_alias TABLE is the audit trail, not the resolver — T1.4's
        # implemented contract); set_authors then registers + links under the
        # same door the edit form uses, so add and edit cannot drift.
        aliases = seed.app_aliases()
        canonical = [aliases.get(name, name) for name in authors]
        try:
            cur = conn.execute(
                "INSERT INTO book (title, year, format, date_read, read_year,"
                " isbn13, isbn10, notes, status, book_key, created, updated)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (values["title"], values["year"], values["format"] or "bok",
                 read_date,
                 datetime.strptime(read_date, "%Y-%m-%d").year,
                 values["isbn13"], values["isbn10"], values["notes"],
                 "read", seed.book_key(values["title"], canonical), now, now))
            seed.set_authors(conn, cur.lastrowid, authors)
            conn.commit()
            book_id = cur.lastrowid
        except Exception as e:
            conn.rollback()
            if "UNIQUE" not in str(e):
                raise
            return render_template(
                "tillagg.html", today=date.today().isoformat(),
                fel="Den boken finns redan i hyllan.", bok=None,
                current="hylla"), 400
        _enrich_in_request(conn, book_id)
        return auth.redirect_prefixed(f"/bok/{book_id}")

    @app.post("/omslag/<int:book_id>")
    def hamta_omslag(book_id):
        """T5.3 button: ONE row, synchronous, ≤6 s, then back to the page she
        pressed it from. All-providers-failed is not an error page: the row
        keeps its placeholder and the evidence columns say who was asked."""
        conn = db.get_db()
        if conn.execute("SELECT 1 FROM book WHERE id = ?",
                        (book_id,)).fetchone() is None:
            abort(404)
        _enrich_in_request(conn, book_id)
        return auth.redirect_prefixed(f"/redigera/{book_id}")

    @app.post("/omslag/<int:book_id>/ladda-up")
    def ladda_up_omslag(book_id):
        conn = db.get_db()
        rows = books.load_books(conn, ids=[book_id])
        if not rows:
            abort(404)

        def back(fel):
            return render_template("redigera.html", bok=rows[0], fel=fel,
                                   current="hylla"), 400

        filed = request.files.get("fil")
        if filed is None or not filed.filename:
            return back("Välj en bildfil först.")
        data = filed.read(MAX_UPLOAD + 1)         # reads one past: a lying
        if len(data) > MAX_UPLOAD:                # Content-Type never outruns the cap
            return back(OVER_CAP_COPY)
        try:
            enrich.store_cover(conn, book_id, data, "manual")
        except enrich.CoverRejected:
            return back("Det filen innehöll ingen giltig bild.")
        return auth.redirect_prefixed(f"/bok/{book_id}")
