"""The shelf-page reader's legs (MC 12606, M11-N4b): the graded cards the
served /bibliotek markup yields — the two legs `scripts/pris_parse.py` still
owes, because its one live caller (`scripts/ai_rek_pass.py::read_library`)
reads exactly this.

What MC 12606 deleted with the price/sale feature: the fifteen Bokus
buy-box legs (physical-one-price, script-text-excluded, campaign-two-prices ⇒
AMBIGUOUS, format-page ⇒ FORMAT, not-found ⇒ NOT-CARRIED, the two identity-
gate legs, the NBSP/token leg, the three price-bound legs, cart-without-box,
bytes-in) and the five §2 scope/ISBN legs (only-"Att läsa"-is-scope,
section_missing, empty_section, the legit no_isbn, isbn_shape). Every one of
them drove code whose ONLY caller was `scripts/pris_vakt.py`, the nightly
runner this commit deletes; their measured shapes stay in the LEDGER rows of
MC 12547/MC 12549, not as capability the tree no longer runs. The fragments
they shared (`isbn`, `scope_html`, `bok_html`, `FRAG`, `BOKUS_URL`) went with
them — their last other consumer, tests/test_pris_vakt.py, is deleted here.
"""
from scripts import pris_parse as pp


# --- MC 12601 (M11-N5R): the graded-shelf reader -----------------------------

def hyll_html(kort):
    """The served /bibliotek card markup (the measured bytes of the app's
    own _bokkort.html, from the public shelf fetched 2026-11-16)."""
    stjärna, tom_stjärna = "\u2605", "\u2606"
    ut = ['<html><body>']
    for t, a, b in kort:
        ut.append('<li class="bok-kort"><a class="bok-lank" '
                  'href="/liselott/bok/1"><img class="omslag" src="/c" '
                  'alt="Omslag" width="340" height="510" loading="lazy">'
                  f'<span class="titel">{t}</span></a>'
                  f'<p class="forfattare">{a}</p>'
                  '<p class="meta">Inbunden</p>')
        if b:
            ut.append(f'<span class="stjarnor" role="img" aria-label="Betyg '
                      f'{b} av 5"><span aria-hidden="true">'
                      f'{stjärna * b}{tom_stjärna * (5 - b)}'
                      '</span></span>')
        ut.append('</li>')
    ut.append('</body></html>')
    return "".join(ut)


def test_read_graded_keeps_only_betygsatta_kort():
    got = pp.read_graded(hyll_html([("Påhittad Pärm", "Påhittad Person", 4),
                                    ("Ograderad Önskan", "Okänd person", 0),
                                    ("Inbillad pärm", "Inbillad person", 5)]))
    assert got == [{"title": "Påhittad Pärm", "author": "Påhittad Person",
                    "rating": 4},
                   {"title": "Inbillad pärm", "author": "Inbillad person",
                    "rating": 5}]


def test_read_graded_empty_page_is_empty_list():
    assert pp.read_graded("<html><body><p>tom hylla</p></body></html>") == []
