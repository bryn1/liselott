"""MC 12734 (M12 W2) — "Året": her reading life in calm words (PLAN-M12 REV 2
§2 F3 recap + §3 F5 quiet stats, ONE page per R2: "Årets läsning <år>" +
"Genom åren").

Pure read model, ZERO new columns (§2's law): every number derives from the
ONE loader's rows — `books.load_books` over the OWNER's full shelf (the page
is owner-only BY GUARD: /aret rides none of auth.PUBLIC_READ_PATHS/_PREFIXES,
so an anonymous GET never reaches this view; the guard's uniform 302 answers,
pinned in tests/test_aret.py). The year select REUSES `filtrering.parse`
(R5: the same AR_RE, invalid == absent == calm) and `filtrering.years` over
the READ rows only — aborted/reading rows never enter a year's numbers (§2's
exclusion), and the year list is never wider than her own data.

The NEVER-DO §3-8/9 line binds this module: no comparisons, no streaks, no
goals, no charts — just the counts of what she actually read. Snitt carries
one decimal with a COMMA (sv style); a year or tail with nothing to say
stays silent, so no zero ever stands where data should. The month lines
count through `books.shelf_month` (W1's guarded primitive) — monthless read
rows as ONE "Utan datum" count, never a filled-in today.
"""
from flask import render_template, request

from app import books, db, filtrering
from app.books import STATUS_WORDS
from app.text import fold


def _snitt(rated):
    """Medelbetyget som en lugn siffra: ett decimal, komma, sv stil — eller
    None när inget är betygssatt (tystnad framför nolla, §9)."""
    if not rated:
        return None
    medel = sum(b["rating"] for b in rated) / len(rated)
    return f"{medel:.1f}".replace(".", ",")


def _titel_text(titlar):
    """"A", "B" och "C" — samma sammansättning som books.authors_text gör
    för namn (§9: två och med "och", fler med komma)."""
    om = sorted(titlar, key=fold)
    if len(om) == 1:
        return om[0]
    return ", ".join(om[:-1]) + " och " + om[-1]


def _lasning(read_rows):
    """§2's recap values for the selected year's READ rows (the caller has
    already narrowed by status AND year — the exclusion law lives HERE, at
    the ONE read, not in the template)."""
    rated = [b for b in read_rows if b["rating"] is not None]
    toppar = [b["title"] for b in rated if b["rating"] == 5]
    manadsantal = {}
    for bok in read_rows:
        manad = books.shelf_month(bok)
        manadsantal[manad] = manadsantal.get(manad, 0) + 1
    manader = [f"{books.MONTHS_SV[m - 1]}: {manadsantal[m]}"
               for m in sorted(manadsantal) if m]
    if manadsantal.get(0):
        manader.append(f"Utan datum: {manadsantal[0]}")
    return {
        "antal": len(read_rows),
        "betyg": len(rated),
        "snitt": _snitt(rated),
        "toppar": _titel_text(toppar) if toppar else None,
        "ljud": sum(1 for b in read_rows if b["format"] == "ljudbok"),
        "noter": sum(1 for b in read_rows if (b["notes"] or "").strip()),
        "manader": ", ".join(manader),
    }


def _genom_aren(bocker):
    """§3: the per-year lines over READ rows only (F-I: a wishlist, reading
    or aborted row belongs to no year line), newest first; yearless READ
    rows ride as their own quiet line, and the status tails are the honest
    rest — the words read through STATUS_WORDS where the map owns them.
    `totalt` is the whole table, so the page's own numbers can close."""
    read = [b for b in bocker if b["status"] == "read"]
    ar = []
    for year in filtrering.years(read):
        rows = [b for b in read if books.shelf_year(b) == year]
        rated = [b for b in rows if b["rating"] is not None]
        ar.append({"year": year, "antal": len(rows), "snitt": _snitt(rated)})
    antal = {}
    for bok in bocker:
        antal[bok["status"]] = antal.get(bok["status"], 0) + 1
    halor = [("Önskelistan", antal.get("wishlist", 0)),
             (STATUS_WORDS["reading"], antal.get("reading", 0)),
             (STATUS_WORDS["aborted"], antal.get("aborted", 0))]
    return {
        "ar": ar,
        "utan_ar": sum(1 for b in read if not books.shelf_year(b)),
        "halor": [(ord_, n) for ord_, n in halor if n],
        "lasta_totalt": len(read),
        "totalt": len(bocker),
    }


def init_aret(app):
    @app.get("/aret")
    def aret():
        """Owner-only (the guard answers every anonymous GET with its
        uniform 302 — NOT in PUBLIC_READ, §2's public-surface proof); her
        full shelf through the ONE loader, never the public projection.
        ?ar= rides filtrering.parse: invalid == absent; a valid year with
        no read rows renders ONE quiet line (§2, never a zero scoreboard)."""
        bocker = books.load_books(db.get_db())
        read = [b for b in bocker if b["status"] == "read"]
        ar_alla = filtrering.years(read)
        ar = filtrering.parse(request.args)["ar"]
        if ar is None and ar_alla:
            ar = ar_alla[0]                    # newest year present, else none
        rows = [b for b in read if books.shelf_year(b) == ar] if ar else []
        return render_template("aret.html", current="aret", ar=ar,
                               ar_alla=ar_alla,
                               lasning=(_lasning(rows) if ar else None),
                               historik=_genom_aren(bocker))

    # The explicit slash rule beside the canonical one (ai_rek.py's F-3
    # precedent, MC 12597): registered AFTER the view, so the first rule of
    # the endpoint — the one url_for builds — stays the canonical "/aret".
    # The owner's /aret/ answers the page in place; the anonymous /aret/
    # meets the guard's uniform 302 before the router (the path is not a
    # public read, slash-stripped or not).
    app.add_url_rule("/aret/", endpoint="aret")
