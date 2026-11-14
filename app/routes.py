"""Page routes (§6.7 password lifecycle; M4 adds browse/search; T5.1
adds grading). Guard + CSRF already ran before any view here: reads ride
the §6.4 allow-list as widened by the public-read contract (MC 12497 —
shelf, bok, search, recs and covers answer an anonymous GET on a
configured site; the root keeps the fixed-copy landing the M8 staging
gate pinned, see rot() and templates/start.html), and every state change
is owner-authenticated and token- and origin-checked (T2.3/T2.5)."""
import re
import shutil
import tempfile
from pathlib import Path

from flask import (Response, abort, jsonify, render_template, request,
                   send_file, session)

from app import auth, backup, books, db, omslag, recommend, search, seed

# F-2 (SEC-verdict-12497): werkzeug's int converter matches \d+ WITHOUT
# bound, and binding an id >= 2**63 into sqlite OverflowErrors — the
# anonymous traceback generator (generic 500 + server-log traceback) the
# verdict measured on the freshly-public /bok and /cover, live through the
# edge. sqlite INTEGER is signed 64-bit: outside its domain no row CAN
# stand, so the honest answer is the route's own 404, before the bind.
SQLITE_INT_MIN, SQLITE_INT_MAX = -(2 ** 63), 2 ** 63 - 1


def _stream_and_delete(path: Path, tmp_dir: Path, mimetype: str, filename: str):
    """Stream a snapshot away and remove it when the response ends: a backup
    pull is a moment, not something the app keeps on disk. Generator + own
    cleanup (not send_file on a temp dir the view already deleted) so the file
    is guaranteed to outlive every byte the server has left to write."""
    handle = path.open("rb")

    def chunks():
        try:
            for block in iter(lambda: handle.read(1 << 16), b""):
                yield block
        finally:
            handle.close()
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(chunks(), mimetype=mimetype,
                    headers={"Content-Disposition":
                             f'attachment; filename="{filename}"'})


def init_routes(app):
    # Templates get the mount helper and the formatters as globals — one place,
    # so no template ever hand-builds a URL or a Swedish date. `mount_url`
    # exists for the ONE link whose route is not implemented yet
    # (/redigera/<id>, T5.2): url_for would raise BuildError there, and this is
    # the same §6.5 SCRIPT_NAME mechanism url_for uses underneath — never a
    # root-absolute literal.
    app.jinja_env.globals.setdefault(
        "inloggad", lambda: bool(session.get(auth.SESSION_FLAG)))
    app.jinja_env.globals.setdefault(
        "mount_url", lambda path: (request.script_root or "") + path)
    for fn in (books.authors_text, books.format_word, books.sw_date,
               books.year_text):
        app.jinja_env.globals.setdefault(fn.__name__, fn)
    # "1 träff" / "13 träffar" on one line — a count and its noun may not be
    # split across source lines the reader then renders as a paragraph break.
    app.jinja_env.globals.setdefault(
        "number_and_word",
        lambda n, one, many: f"{n} {one if n == 1 else many}")

    def _hylla():
        """One read, one render — shared by the two rules below."""
        grupper = books.group_for_shelf(books.load_books(db.get_db()))
        return render_template("bibliotek.html", grupper=grupper,
                               current="hylla")

    @app.get("/")
    def rot():
        """The home page IS the shelf for the owner, and the public landing
        for everyone else (the root leg §6.4 got from the M8 staging gate,
        MC 12451): an anonymous GET answers 200 with the fixed data-free
        page and the ONE door legal in the current §6.1 state — window-open
        → /satt-loesenord "Välj ditt lösenord", configured → /logga-in
        "Logga in". The closed state never reaches this view; the guard's
        pinned gate page answers it. Two ENDPOINTS on one render (not two
        rules on one endpoint): with one endpoint url_for would collapse
        onto the shorter rule and the nav would emit /liselott without a
        path. §6.1's "after setup GET / -> 200" is answered here, not by a
        redirect."""
        if session.get(auth.SESSION_FLAG):
            return _hylla()
        if auth.is_configured(db.get_db()):
            return render_template("start.html", dorren="logga_in",
                                   etiketten="Logga in")
        return render_template("start.html", dorren="satt_losenord",
                               etiketten="Välj ditt lösenord")

    @app.get("/bibliotek")
    def bibliotek():
        """The shelf (§9 "Din hylla"): read years newest first, "Att läsa"
        last."""
        return _hylla()

    @app.get("/bok/<int:id>")
    def bok(id):
        """One book, honestly: the fields she kept, the format and date in
        Swedish words, and the §9 fix-me hint when the cover is missing."""
        if not SQLITE_INT_MIN <= id <= SQLITE_INT_MAX:
            abort(404)          # F-2: unbindable id — this route's own 404,
                                # never the bind's OverflowError
        rows = books.load_books(db.get_db(), ids=[id])
        if not rows:
            abort(404)          # the §9 404 page echoes nothing back
        return render_template("bok.html", bok=rows[0], current="hylla")

    @app.get("/sok")
    def sok():
        """T4.3 — the ONE search mechanism (§7) behind one form. `traffar` is
        None until she has actually asked for something (an empty q is a blank
        page, not a zero-result page), and the search module owns every rule
        about what a query means."""
        q = request.args.get("q", "")
        traffar = search.search(db.get_db(), q) if q.strip() else None
        return render_template("sok.html", q=q, traffar=traffar,
                               current="sok")

    DISMISS_KINDS = {"book": "book", "cand": "candidate"}

    @app.get("/rekommendationer")
    def rekommendationer():
        """T6.2 — the §8 page: the engine's top 12, best first. rated==0 is
        NOT an error state: the plan's empty-state copy answers and the
        wishlist-led list still renders (the t=0 leg)."""
        conn = db.get_db()
        rated = conn.execute("SELECT COUNT(*) FROM book"
                             " WHERE rating IS NOT NULL").fetchone()[0]
        return render_template("rekommendationer.html",
                               recs=recommend.top_recommendations(conn, 12),
                               rated=rated, current="rekommendationer")

    @app.post("/djem/<kind>/<int:item_id>")
    def djem(kind, item_id):
        """T6.2 — "Visa inte igen": the §8 dismissed row, keyed 'book:<id>'
        for a wish and 'cand:<id>' for a pool card (P2-3 — both kinds are
        dismissible). The engine excludes the key from the top-12; PRIMARY
        KEY makes a repeated click a no-op, never an error. The table name
        comes from a fixed whitelist dict, never from the URL."""
        if kind not in DISMISS_KINDS:
            abort(404)
        conn = db.get_db()
        if conn.execute(f"SELECT 1 FROM {DISMISS_KINDS[kind]} WHERE id = ?",
                        (item_id,)).fetchone() is None:
            abort(404)                       # the 404 page echoes nothing
        conn.execute("INSERT OR IGNORE INTO dismissed (key, ts) VALUES (?,?)",
                     (f"{kind}:{item_id}", auth.utcnow_iso()))
        conn.commit()
        return auth.redirect_prefixed("/rekommendationer")

    GRADE_RE = re.compile(r"[1-5]")          # §1: integers 1–5, ASCII digits only
    GRADE_CLEAR = "clear"                    # the Rensa button's own value

    @app.post("/betyg/<int:book_id>")
    def betyg(book_id):
        """T5.1 — grade one book. The plan's contract: 4 shown, 6 → 400,
        "clear" → NULL; and per §5.11 grading SETS 'read' (the helper owns the
        read_year sentinel) while never inventing a date_read. getlist, not
        get: a browser posts the checked radio AND the clicked clear button
        under the same name, and the clear click is the intent — .get() would
        return the radio and silently ignore her."""
        conn = db.get_db()
        if conn.execute("SELECT 1 FROM book WHERE id = ?",
                        (book_id,)).fetchone() is None:
            abort(404)                       # the 404 page echoes nothing
        values = request.form.getlist("betyg")
        if GRADE_CLEAR in values:
            rating = None
        elif len(values) == 1 and GRADE_RE.fullmatch(values[0]):
            rating = int(values[0])
        else:
            return render_template(
                "csrf-fel.html",
                fel="Betyget är ett heltal 1–5 — eller Rensa betiget."), 400
        conn.execute("UPDATE book SET rating = ?, updated = ? WHERE id = ?",
                     (rating, auth.utcnow_iso(), book_id))
        if rating is not None:
            seed.mark_read(conn, book_id)
        conn.commit()
        return auth.redirect_prefixed(f"/bok/{book_id}")

    @app.errorhandler(404)
    def inte_hittad(error):
        """The gate is NOT loosened here (T2.6): _guard already ran as a
        before_request for this unmatched path. Anonymous visitors reach this
        render for file-SHAPED names only (M8-hotfix-2: _file_shaped 404s the
        lane's quarantine probes instead of fingerprinting the gate with a
        302); every other unknown anonymous path was redirected long before
        this render. The body is static copy — it echoes nothing back and
        carries zero app data, so the anonymous 404 is indistinguishable
        from the owner's."""
        return render_template("404.html"), 404

    @app.get("/cover/<int:book_id>")
    def cover(book_id):
        """T3.4 — the stored cover, or the placeholder SVG when the row has
        none (public-read per MC 12497: the cover image belongs to the
        public shelf; the placeholder is served as data, never as a
        redirect to anything)."""
        if not SQLITE_INT_MIN <= book_id <= SQLITE_INT_MAX:
            abort(404)          # F-2 (SEC-verdict-12497): as in bok()
        conn = db.get_db()
        row = conn.execute("SELECT cover_path FROM book WHERE id = ?",
                           (book_id,)).fetchone()
        if row is None:
            abort(404)
        # The path comes from a DB column, so its SHAPE is checked before it
        # touches the filesystem: store_cover only ever writes
        # "covers/<that very book's id>.jpg", and anything else — a hand-edited
        # or corrupted value — is treated as "no cover" rather than as a file to
        # read. A file-read route must not be a path interpreter.
        if row[0] == f"covers/{book_id}.jpg":
            stored = db.state_base() / row[0]
            if stored.is_file():
                return send_file(stored, mimetype="image/jpeg")
        return send_file(Path(app.static_folder) / "omslag-saknas.svg",
                         mimetype="image/svg+xml")

    @app.post("/omslag/<int:book_id>/hitta")
    def hitta_omslag(book_id):
        """OQ-2 (owner ruling 2026-11-12): the admin pastes a page url, the app
        fetches it server-side, takes its og:image (or largest <img>) and keeps
        it as the cover, cover_source='manual-url'. Guard + CSRF already ran —
        this is a state change, so the session token is required (NOT a
        TOKENLESS_POSTS machine route). JSON answer: S5 wires the button."""
        outcome = omslag.hamta_omslag(db.get_db(), book_id,
                                      request.form.get("sida_url", ""))
        return jsonify(outcome), (200 if outcome["ok"] else 400)

    BACKUP_KINDS = {"db": ("liselott.db", "application/octet-stream"),
                    "covers": ("omslag.tar.gz", "application/gzip")}

    @app.get("/backup")
    def backup_door():
        """T9.2 (§11) — the plan-owned backup door. The lane gives no cron on
        vm106, so the named actor of the runbook pulls with curl through THIS
        door: the login guard answers an anonymous GET with its 302 before the
        function is ever called, and the snapshot is built by THE mechanism
        (app/backup.py — the same functions scripts/backup.sh runs), in a
        throwaway temp dir, streamed, then deleted."""
        kind = request.args.get("kind", "db")
        if kind not in BACKUP_KINDS:
            return ("Okänd backuppsort — kind är db eller covers."), 400
        name, mimetype = BACKUP_KINDS[kind]
        tmp_dir = Path(tempfile.mkdtemp(prefix="liselott-backup-"))
        target = tmp_dir / name
        try:
            snapshot = (backup.snapshot_db if kind == "db"
                        else backup.snapshot_covers)
            snapshot(db.state_base(), target)
        except backup.BackupError as error:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return f"Säkerhetskopieringen misslyckades: {error}", 400
        return _stream_and_delete(target, tmp_dir, mimetype, name)

    @app.route("/byter-losenord", methods=["GET", "POST"])
    def byter_losenord():
        # P1-1 (MC 12451): the door exists — GET renders the form the POST
        # below validates, csrf token riding the render (the logga-in GET/POST
        # idiom on one rule). Before this commit the template was reachable
        # only as the POST's 401/400 error body: no GET, no nav link, no door.
        # F-1 (SEC-verdict-12497): POST is the ONLY processing method — the
        # verdict's scenario (b), a HEAD+body under the owner's cookie with
        # BOTH CSRF defences bypassed, used to MOVE THE PASSWORD on this
        # branch-else. Reads render the form; the token rule (§6.6) still
        # guards the POST.
        if request.method != "POST":
            return render_template("byter-losenord.html", fel=None,
                                   current="byter-losenord")
        conn = db.get_db()
        current = request.form.get("nuvarande", "")
        new = request.form.get("ny", "")
        confirm = request.form.get("ny_bekrafta", "")
        stored = auth.get_setting(conn, "password_hash")
        if not stored or not auth.verify_password(stored, current):
            # wrong current -> 401, nothing touched (§6.7)
            return render_template("byter-losenord.html",
                                   fel="Fel nuvarande lösenord."), 401
        if len(new) < auth.PASSWORD_MIN:
            return render_template(
                "byter-losenord.html",
                fel=f"Lösenordet måste vara minst {auth.PASSWORD_MIN} tecken."), 400
        if new != confirm:
            return render_template("byter-losenord.html",
                                   fel="Lösenorden matchar inte."), 400
        auth.set_setting(conn, "password_hash", auth.hash_password(new))
        auth.set_setting(conn, "password_set_at", auth.utcnow_iso())
        auth.rotate_secret(app)  # all sessions die -> re-login (§6.7)
        return auth.redirect_prefixed("/logga-in")
