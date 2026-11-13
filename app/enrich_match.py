"""The match policy (T3.4): title normalization + similarity floor, the
author gate, the row-format→hit-type tie-break, and the cycle-1 §5 genre
vocabulary. Pure functions over data — no http, no db — split out of
app/enrich.py in the M4 clean-code pass (§9 seam of
.audits/20261112-phase2); app.enrich re-exports every name below, so no
import site changed."""
import difflib
import re
import unicodedata

MAX_TITLE_SIMILARITY_MIN = 0.80      # difflib ratio floor for a provider hit
# The row's own format -> the provider hit types that fit it (§7 enum 'bok' /
# 'ljudbok'). Libris answers one title as several editions; see prefer_format.
HIT_TYPE_BY_FORMAT = {"bok": ("book", "text"), "ljudbok": ("sound recording",)}

# cycle-1 §5 (binding): substring match on lower-cased subject strings, max 3
# labels per book, anything unmatched or no subjects at all → Övrigt.
GENRE_RULES = (
    ("Romantik", ("romanc", "love story", "kärlek")),
    ("Familjesaga", ("family", "släkt", "saga", "generation")),
    ("Kriminalitet", ("crime", "detective", "mord", "polis", "thriller")),
    ("Historisk roman", ("histor", "krig", "world war", "historisk")),
    ("Självbiografiskt", ("biograph", "memoir", "självbiograf")),
    ("Reseskildring", ("travel", "rese", "reportage")),
    ("Natur och vardag", ("nature", "garden", "natur", "trädgård", "mat", "food")),
    ("Samhälle och aktualitet", ("societ", "samhälle", "current affairs")),
)
GENRE_OTHER = "Övrigt"


def normalize_title(text):
    folded = unicodedata.normalize("NFKD", str(text or "").casefold())
    return re.sub(r"[^a-z0-9åäöéèé]+", "", folded)


def title_similarity(a, b):
    return difflib.SequenceMatcher(None, normalize_title(a),
                                   normalize_title(b)).ratio()


def authors_overlap(book_authors, hit_authors):
    """The §T3.4 gate applies only when BOTH sides name an author; then any
    near-equal pair (equal, containment, or ratio ≥ 0.85) opens it."""
    if not book_authors or not hit_authors:
        return True
    for mine in book_authors:
        m = normalize_title(mine)
        for theirs in hit_authors:
            t = normalize_title(theirs)
            if not m or not t:
                continue
            if m == t or m in t or t in m:
                return True
            if difflib.SequenceMatcher(None, m, t).ratio() >= 0.85:
                return True
    return False


def map_genres(subjects):
    """§5 mapping: max 3 labels, else Övrigt (also when there are no
    subjects at all — the plan's own wording, verified Swedish subjects such
    as 'Skönlitteratur' match no rule and therefore land on Övrigt)."""
    found = []
    for label, needles in GENRE_RULES:
        if label in found:
            continue
        for subject in subjects or []:
            low = str(subject).casefold()
            if any(needle in low for needle in needles):
                found.append(label)
                break
    return found[:3] if found else [GENRE_OTHER]


def prefer_format(candidates, book_format):
    """Among the hits that PASSED the match policy, the row's own format picks
    the edition. Measured on the recorded Libris page for Stöld: one title
    answers as an analysis booklet, an article, a ljudbok and the book, the
    ljudbok listed first — and taking it for a print row writes an audiobook
    ISBN into the diary. Candidates from a provider that names no type
    (OpenLibrary, Google Books) keep the plan's first-hit order untouched."""
    wanted = HIT_TYPE_BY_FORMAT.get(book_format, ())
    for hit in candidates:
        if str(hit.get("type") or "").lower() in wanted:
            return hit
    for hit in candidates:
        if not hit.get("type"):
            return hit                     # ol/gb answers: order wins as pinned
    return candidates[0]
