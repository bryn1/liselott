"""T1.3 — row-level parse goldens: annotation strip (F-6/P2-2/P2-6) BEFORE the
LAST-' av ' author split (F-6 red-proof: first-split corrupts the 4 census
rows). Hand-written cases, no corpus needed."""
import pytest

from app.seed import parse_row

# (case id, raw row, expected date_read, expected title, expected authors, expected rating)
GOLDENS = [
    ("god-jul-agnes", "261029 [personlig-data-purgad] av Kristin Emilsson",
     "2026-10-29", "[personlig-data-purgad]", ["Kristin Emilsson"], None),
    ("ett-hav-av-minnen", "[personlig-data-purgad] av Fiona Valpy",
     None, "[personlig-data-purgad]", ["Fiona Valpy"], None),
    ("i-hjartat-av-adala", "[personlig-data-purgad] av Åsa Liaböck",
     None, "[personlig-data-purgad]", ["Åsa Liaböck"], None),
    ("flera-sidor-av-oss", "[personlig-data-purgad] av Karin Wallén",
     None, "[personlig-data-purgad]", ["Karin Wallén"], None),
    ("en-bur-av-guld", "[personlig-data-purgad] av Camilla Läckberg",
     None, "[personlig-data-purgad]", ["Camilla Läckberg"], None),
    ("boije-af-gennas", "[personlig-data-purgad] av Louise Boije af Gennäs",
     None, "[personlig-data-purgad]", ["Louise Boije af Gennäs"], None),
    ("ahrnsredt-annotation",
     "[personlig-data-purgad] av Simona Ahrnsredt (särskrivning i källan: Ahrnstedt)",
     None, "[personlig-data-purgad]", ["Simona Ahrnsredt"], None),
    ("evelyn-fel-ar", "261026 (Fel år i källan; står i 2025-listan) [personlig-data-purgad] av Taylor Jenkins Reid",
     "2026-10-26", "[personlig-data-purgad]", ["Taylor Jenkins Reid"], None),
    ("utan-datum-varkanslor",
     "(utan datum) [personlig-data-purgad] av Yvonne Ehn",
     None, "[personlig-data-purgad]", ["Yvonne Ehn"], None),
    ("betyg-3", "[personlig-data-purgad] av Tina Harnesk (betyg 3 i källan)",
     None, "[personlig-data-purgad]", ["Tina Harnesk"], 3),
    ("atlas-co-author", "[personlig-data-purgad] av Lucinda Riley – Harry Whittaker",
     None, "[personlig-data-purgad]", ["Lucinda Riley", "Harry Whittaker"], None),
    ("krinta-agg-subtitle",
     "[personlig-data-purgad] av Maria Ernestam",
     None, "[personlig-data-purgad]",
     ["Maria Ernestam"], None),
    ("ta-min-hand", "[personlig-data-purgad]", None, "[personlig-data-purgad]", [], None),
    ("tre-forefattare",
     "[personlig-data-purgad] av Sara Molin, Johanna Johansson och Birgitta Gunnarsson",
     None, "[personlig-data-purgad]",
     ["Sara Molin", "Johanna Johansson", "Birgitta Gunnarsson"], None),
    ("jularen-devert", "[personlig-data-purgad] av Jessica Devert & Annica Devert",
     None, "[personlig-data-purgad]", ["Jessica Devert", "Annica Devert"], None),
    ("bed-frukost", "[personlig-data-purgad] av Frida Gråsjö",
     None, "[personlig-data-purgad]", ["Frida Gråsjö"], None),
    ("ellens-val-serie", "[personlig-data-purgad] av Helena Dahlgren",
     None, "[personlig-data-purgad]", ["Helena Dahlgren"], None),
    ("apostrof", "[personlig-data-purgad] av Emma Hamberg",
     None, "[personlig-data-purgad]", ["Emma Hamberg"], None),
]


@pytest.mark.parametrize("raw,date,title,authors,rating",
                         [g[1:] for g in GOLDENS], ids=[g[0] for g in GOLDENS])
def test_golden_rows(raw, date, title, authors, rating):
    got = parse_row(raw)
    assert got["date_read"] == date
    assert got["title"] == title
    assert got["authors"] == authors
    assert got["rating"] == rating
    assert got["bad_author_tail"] is False


def test_annotation_residue_never_survives():
    """No golden may leave 'i källan' or '(utan datum)' in title or authors."""
    for case in GOLDENS:
        got = parse_row(case[1])
        fields = [got["title"], *got["authors"]]
        assert all("i källan" not in f and "(utan datum)" not in f for f in fields), case[0]


def test_malformed_author_tail_is_flagged():
    """§5.4 validator: author tail still containing av-splitting (tab-form,
    which the literal ' av ' split cannot see) flags the row, never corrupts."""
    got = parse_row("Nån titel av Författare\tav\tNågon")
    assert got["bad_author_tail"] is True
