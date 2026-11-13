"""Logged-in page routes (§6.7 password lifecycle; M4+ adds browse/search).
Guard + CSRF already ran before any view here — request is owner-authenticated
and (for state changes) token- and origin-checked (T2.3/T2.5)."""
from pathlib import Path

from flask import abort, jsonify, render_template, request, send_file

from app import auth, db, omslag


def init_routes(app):

    @app.get("/cover/<int:book_id>")
    def cover(book_id):
        """T3.4 — the stored cover, or the placeholder SVG when the row has
        none (the §6.4 guard already put this route behind the login; the
        placeholder is served as data, never as a redirect to anything)."""
        conn = db.get_db()
        row = conn.execute("SELECT cover_path FROM book WHERE id = ?",
                           (book_id,)).fetchone()
        if row is None:
            abort(404)
        if row[0]:
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

    @app.post("/byter-losenord")
    def byter_losenord():
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
