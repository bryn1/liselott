"""T5.2 — the fix-me landing page: /redigera/<id> and /ta-bort/<id>.

The bok page's "Omslag saknas — fixa" link lands HERE (§9), which is also the
one door that edits a book's identity — so the §5.3 book_key is recomputed
from the STORED result (new title + alias-canonical authors), never from form
strings alone: a row whose key and content disagree would silently break the
P1-3 bundle upsert. Field-by-field semantics: a field present in the form was
rendered or intended, a field absent is untouched — the rapport page (T5.5)
posts ONLY the ISBN input through this same route and must not wipe titles by
absence.

Every validation answers 400 in Swedish with `.fel-meddelande`, because the
DB CHECKs would answer 500: 'bok'/'ljudbok' is vocabulary, not suggestions.
The ISBN field runs through search.normalize_isbn — THE §7 normalizer (one
mechanism; a second ISBN parser would drift from search itself). A key
collision (editing into another row's title+author pair) is a named 400, not
a silent overwrite and not an IntegrityError 500.

Delete honors the same shape discipline as the /cover route: cover_path is
trusted only when it is exactly "covers/<that id>.jpg" — a route that touches
the filesystem is never a path interpreter.
"""
from datetime import datetime

from flask import abort, render_template, request

from app import auth, books, db, search, seed

FORMATS = ("bok", "ljudbok")
CONFIRM_WORD = "ta bort"          # the delete button's own form value


def form_to_fields(form, existing):
    """Merge posted fields onto a value dict; returns (values, fel). Any
    invalid field aborts the whole merge with the Swedish message — a form
    POST is all-or-nothing, never a half-applied edit. TWO doors share it:
    the edit form (existing = the stored row) and the add form (existing =
    {}), so the field vocabulary and every Swedish message cannot drift.
    Fields not posted are not present in the result (the edit route keeps
    the stored value for those; the add route answers its own defaults)."""
    v = {"title": None, "year": None, "format": None, "date_read": None,
         "isbn13": None, "isbn10": None, "notes": None}
    v.update(existing)
    if "titel" in form:
        title = form.get("titel", "").strip()
        if not title:
            return v, "Titeln kan inte vara tom."
        v["title"] = title
    if "utgivningsar" in form:
        year = form.get("utgivningsar", "").strip()
        if not year:
            v["year"] = None
        elif year.isascii() and year.isdigit():
            v["year"] = int(year)
        else:
            return v, "Utgivningsåret måste vara fyra siffror."
    if "format" in form:
        if form.get("format") not in FORMATS:
            return v, "Formatet är antingen bok eller ljudbok."
        v["format"] = form["format"]
    if "last" in form:
        date = form.get("last", "").strip()
        if not date:
            v["date_read"] = None
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")     # 2026-13-01 is not a date
            except ValueError:
                return v, "Läsdatumet måste vara ett riktigt datum (ÅÅÅÅ-MM-DD)."
            v["date_read"] = date
    if "isbn13" in form:
        raw = form.get("isbn13", "").strip()
        if not raw:
            v["isbn13"], v["isbn10"] = None, None
        else:
            got = search.normalize_isbn(raw)            # THE §7 normalizer
            if got is None:
                return v, "ISBN numret är ogiltigt — kontrollera siffrorna."
            v["isbn13"], v["isbn10"] = got
    if "anteckningar" in form:
        v["notes"] = form.get("anteckningar", "").strip() or None
    return v, None


def _existing(conn, book_id):
    row = conn.execute("SELECT title, year, format, date_read, isbn13, isbn10,"
                       " notes FROM book WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        return None
    return dict(zip(("title", "year", "format", "date_read", "isbn13",
                     "isbn10", "notes"), row))


def init_redigera(app):

    @app.get("/redigera/<int:id>")
    def redigera(id):
        rows = books.load_books(db.get_db(), ids=[id])
        if not rows:
            abort(404)
        return render_template("redigera.html", bok=rows[0], fel=None,
                               current="hylla")

    @app.post("/redigera/<int:id>")
    def spara_redigera(id):
        conn = db.get_db()
        existing = _existing(conn, id)
        if existing is None:
            abort(404)
        values, fel = form_to_fields(request.form, existing)
        if fel:
            bok = books.load_books(conn, ids=[id])[0]
            return render_template("redigera.html", bok=bok, fel=fel,
                                   current="hylla"), 400

        authors = (seed.split_authors(request.form.get("forfattare", ""))
                   if "forfattare" in request.form
                   else books.load_books(conn, ids=[id])[0]["authors"])
        try:
            canonical = seed.set_authors(conn, id, authors)
            conn.execute(
                "UPDATE book SET title = ?, year = ?, format = ?,"
                " date_read = ?, isbn13 = ?, isbn10 = ?, notes = ?,"
                " book_key = ?, updated = ? WHERE id = ?",
                (values["title"], values["year"], values["format"],
                 values["date_read"], values["isbn13"], values["isbn10"],
                 values["notes"], seed.book_key(values["title"], canonical),
                 auth.utcnow_iso(), id))
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "UNIQUE" not in str(e):
                raise
            bok = books.load_books(conn, ids=[id])[0]
            return render_template(
                "redigera.html", bok=bok,
                fel="Det finns redan en bok med den titeln och den "
                    "författaren i hyllan.", current="hylla"), 400
        return auth.redirect_prefixed(f"/bok/{id}")

    @app.post("/ta-bort/<int:id>")
    def ta_bort(id):
        """Confirm-gated: the button on the edit page is the confirm ("Ta bort
        boken"), the form carries bekräfta — a stray POST without the word
        deletes nothing."""
        conn = db.get_db()
        if request.form.get("bekrafta") != CONFIRM_WORD:
            return render_template("csrf-fel.html",
                                   fel="Bekräfta borttagningen."), 400
        row = conn.execute("SELECT cover_path FROM book WHERE id = ?",
                           (id,)).fetchone()
        if row is None:
            abort(404)
        if row[0] == f"covers/{id}.jpg":           # the same shape rule as /cover
            (db.state_base() / row[0]).unlink(missing_ok=True)
        conn.execute("DELETE FROM book_author WHERE book_id = ?", (id,))
        conn.execute("DELETE FROM book_genre WHERE book_id = ?", (id,))
        conn.execute("DELETE FROM book WHERE id = ?", (id,))
        conn.commit()
        return auth.redirect_prefixed("/bibliotek")
