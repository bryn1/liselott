"""T4.1 — app/search.py query parsing (cycle-1 §7, the ONE search mechanism).

Five keys, one entry point: ISBN (normalized, hyphen/space-tolerant, 10 and
13 digit via the mod-10 EAN conversion), year, genre, and diacritic-folded
text. parse_query is pure (no DB); the genre key resolves against the genre
names the caller already read from the DB, so the module never grows a second
vocabulary. A bad ISBN-13 check digit is NOT an ISBN — it falls back to text
exactly as §7 words it."""
import pytest

from app.search import fold, isbn10_to_13, normalize_isbn, parse_query

NATT_13 = "9789173710015"
GENRES = ["Kriminalitet", "Historisk roman", "Romantik"]


# ── ISBN normalization ──────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", [
    NATT_13,                       # bare 13
    "978-91-7371-001-5",            # hyphenated (T4.3's query shape)
    "978 91 7371 001 5",            # spaced
    "9173710016",                   # 10-digit, the OL fixture's own form
    "91-7371-001-6",                # hyphenated 10
    " 9789173710015 ",              # surrounding whitespace
])
def test_isbn_forms_normalize_to_the_thirteen_digit_form(raw):
    kind, value = parse_query(raw)
    assert kind == "isbn"
    assert value == NATT_13


def test_isbn10_to_13_is_the_mod_10_ean_conversion():
    # 9173710016 -> 978 + 917371001 + check digit 5 (computed, not copied)
    assert isbn10_to_13("9173710016") == NATT_13
    assert isbn10_to_13("9173711020") == "9789173711029"
    # the X check digit case-folds
    assert isbn10_to_13("917371108X") == "9789173711081"


def test_bad_check_digit_falls_back_to_text():
    """§7: a 13-digit token whose mod-10 check digit is wrong is text, not an
    ISBN search — the only checksum §7 pins as a rejection. The text value is
    what she typed, folded (§7 folds case and accents, nothing else), so the
    fallback is a plain word search that answers "Inga träffar"."""
    assert parse_query("978-91-7371-001-4") == ("text", "978-91-7371-001-4")
    assert parse_query("9789173710014") == ("text", "9789173710014")


def test_normalize_isbn_returns_none_for_non_isbn():
    assert normalize_isbn("Nattfjärden") is None
    assert normalize_isbn("12345") is None


# ── year ────────────────────────────────────────────────────────────────────
def test_four_digit_year_is_a_year_query():
    assert parse_query("2023") == ("year", 2023)


@pytest.mark.parametrize("raw", ["1399", "2100", "9999", "202"])
def test_outside_the_year_window_is_text(raw):
    assert parse_query(raw)[0] == "text"


# ── genre ───────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["kriminalitet", "Kriminalitet", " KRIMINALITET "])
def test_a_token_equal_to_a_genre_name_is_a_genre_query(raw):
    assert parse_query(raw, GENRES) == ("genre", "Kriminalitet")


def test_genre_key_is_diacritic_and_case_insensitive():
    assert parse_query("HISTORISK ROMAN", GENRES) == ("genre", "Historisk roman")


def test_without_known_genres_the_token_stays_text():
    assert parse_query("kriminalitet", [])[0] == "text"


# ── text folding ────────────────────────────────────────────────────────────
def test_text_folds_diacritics_and_case():
    assert parse_query("Ekelund") == ("text", "ekelund")
    assert parse_query("Björkvik") == ("text", "bjorkvik")
    assert parse_query("  Näckrosten  ") == ("text", "nackrosten")
    assert parse_query("Nattfjärden") == ("text", "nattfjarden")


def test_fold_matches_raw_and_folded_input():
    """§7's "match raw too": the SAME fold applied to both sides makes the
    accented and unaccented spellings land on one value."""
    assert fold("Björkvik") == fold("Bjorkvik") == "bjorkvik"


def test_nfkc_before_the_isbn_test():
    # full-width digits are NFKC-normalized before the ISBN/year tests (§7)
    assert parse_query("２０２３") == ("year", 2023)


def test_empty_query_is_empty():
    assert parse_query("") == ("empty", "")
    assert parse_query("   ") == ("empty", "")
