"""Logged-in page routes (§6.7 password lifecycle; M4+ adds browse/search).
Guard + CSRF already ran before any view here — request is owner-authenticated
and (for state changes) token- and origin-checked (T2.3/T2.5)."""
from flask import render_template, request

from app import auth, db


def init_routes(app):

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
