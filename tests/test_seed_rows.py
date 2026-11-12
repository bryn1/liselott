"""T1.3 — row-level parse goldens: annotation strip (F-6/P2-2/P2-6) BEFORE the
LAST-' av ' author split (F-6 red-proof: first-split corrupts the 4 census
rows). Hand-written cases, no corpus needed."""
import pytest

from app.seed import parse_row

# (case id, raw row, expected date_read, expected title, expected authors, expected rating)
GOLDENS = [
    ("god-jul-agnes", "261029 God jul Agnes av Kristin Emilsson",
     "2026-10-29", "God jul Agnes", ["Kristin Emilsson"], None),
    ("ett-hav-av-minnen", "Ett hav av minnen av Fiona Valpy",
     None, "Ett hav av minnen", ["Fiona Valpy"], None),
    ("i-hjartat-av-adala", "I hjärtat av Ådala av Åsa Liaböck",
     None, "I hjärtat av Ådala", ["Åsa Liaböck"], None),
    ("flera-sidor-av-oss", "Flera sidor av oss av Karin Wallén",
     None, "Flera sidor av oss", ["Karin Wallén"], None),
    ("en-bur-av-guld", "En bur av guld av Camilla Läckberg",
     None, "En bur av guld", ["Camilla Läckberg"], None),
    ("boije-af-gennas", "Högre än alla himlar av Louise Boije af Gennäs",
     None, "Högre än alla himlar", ["Louise Boije af Gennäs"], None),
    ("ahrnsredt-annotation",
     "En enda hemlighet av Simona Ahrnsredt (särskrivning i källan: Ahrnstedt)",
     None, "En enda hemlighet", ["Simona Ahrnsredt"], None),
    ("evelyn-fel-ar", "261026 (Fel år i källan; står i 2025-listan) Evelyn Hugos sju äkta män av Taylor Jenkins Reid",
     "2026-10-26", "Evelyn Hugos sju äkta män", ["Taylor Jenkins Reid"], None),
    ("utan-datum-varkanslor",
     "(utan datum) Vårkänslor och gemenskap på Kanelholmen del 4 av Yvonne Ehn",
     None, "Vårkänslor och gemenskap på Kanelholmen del 4", ["Yvonne Ehn"], None),
    ("betyg-3", "Folk som sår i snö av Tina Harnesk (betyg 3 i källan)",
     None, "Folk som sår i snö", ["Tina Harnesk"], 3),
    ("atlas-co-author", "Atlas av Lucinda Riley – Harry Whittaker",
     None, "Atlas", ["Lucinda Riley", "Harry Whittaker"], None),
    ("krinta-agg-subtitle",
     "Knäckta ägg och krossade hjärtan – en alldeles omöjlig påsk av Maria Ernestam",
     None, "Knäckta ägg och krossade hjärtan – en alldeles omöjlig påsk",
     ["Maria Ernestam"], None),
    ("ta-min-hand", "Ta min hand", None, "Ta min hand", [], None),
    ("tre-forefattare",
     "Sensommarvals av Sara Molin, Johanna Johansson och Birgitta Gunnarsson",
     None, "Sensommarvals",
     ["Sara Molin", "Johanna Johansson", "Birgitta Gunnarsson"], None),
    ("jularen-devert", "Hur blir det med julen? av Jessica Devert & Annica Devert",
     None, "Hur blir det med julen?", ["Jessica Devert", "Annica Devert"], None),
    ("bed-frukost", "Bed & Breakfast för lata brudpar av Frida Gråsjö",
     None, "Bed & Breakfast för lata brudpar", ["Frida Gråsjö"], None),
    ("ellens-val-serie", "Ellens val 10 – Den ljusnande framtid av Helena Dahlgren",
     None, "Ellens val 10 – Den ljusnande framtid", ["Helena Dahlgren"], None),
    ("apostrof", "Je m'appelle Agneta av Emma Hamberg",
     None, "Je m'appelle Agneta", ["Emma Hamberg"], None),
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
