"""Open Library client (primary provider — VERIFIED resolving Swedish titles,
DA-verdict.md reproduced "Stöld"/Laestadius → isbn 9789198559699, year 2022,
cover_i 14853286). The URL keeps the shape the plan probed live (q=title:"…"
author:"…"&fields=…), extended with `subject` so the genre mapping (T3.4)
rides the SAME call — no second search per row.

Transport is a parameter (http_get_json from app.enrich, ONE http mechanism):
tests replay committed fixtures, the live CLI reaches the network. An empty
`docs` list is a no-match (the empty list is falsy — callers branch on it; the
plan's "empty docs → None" reading: one falsy answer, not None-plus-[] two
answers, stated in the stage evidence)."""
from urllib.parse import urlencode

from app import enrich

SEARCH_ENDPOINT = "https://openlibrary.org/search.json"
COVER_ENDPOINT = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
FIELDS = "title,author_name,isbn,first_publish_year,cover_i,subject"
LIMIT = 5
AUTHOR_LIMIT = 10                          # §8: candidates ride the top 10


def build_url(title, author, *, limit=LIMIT, fields=FIELDS):
    q = f'title:"{title}"'
    if author:
        q += f' author:"{author}"'
    return f"{SEARCH_ENDPOINT}?{urlencode({'q': q, 'limit': limit, 'fields': fields})}"


def map_docs(payload):
    """search.json payload -> hit dicts (raw, unranked; the match policy and
    provider order are app.enrich.resolve's job, T3.4). Missing fields degrade
    to empty, never KeyError."""
    hits = []
    for doc in (payload or {}).get("docs") or []:
        isbn13 = isbn10 = None
        for raw in doc.get("isbn") or []:
            digits = str(raw).replace("-", "").strip()
            if len(digits) == 13 and isbn13 is None:
                isbn13 = digits
            elif len(digits) == 10 and isbn10 is None:
                isbn10 = digits
        cover_id = doc.get("cover_i")
        hits.append({
            "source": "openlibrary",
            "title": doc.get("title") or "",
            "authors": [str(a) for a in doc.get("author_name") or []],
            "isbn13": isbn13,
            "isbn10": isbn10,
            "year": doc.get("first_publish_year"),
            "cover_id": cover_id,
            "cover_url": COVER_ENDPOINT.format(cover_id=cover_id) if cover_id else None,
            "subjects": [str(s) for s in doc.get("subject") or []],
        })
    return hits


def search(title, author, get_json=None, **kw):
    """Live (or fixture-replayed) OL search for one book. Returns the hit list;
    [] means the provider answered 'nothing' — distinct from
    enrich.ProviderUnavailable, which means it could not be asked at all."""
    get_json = get_json or enrich.http_get_json
    return map_docs(get_json(build_url(title, author), **kw))


def build_author_url(name, *, limit=AUTHOR_LIMIT, fields=FIELDS):
    """§8 pins the CANDIDATES breadth: author search asks for the TOP 10 —
    the book-search LIMIT (5) is a different question and must not silently
    decide how wide the candidate pool may get (T6.3 leg)."""
    q = f'author:"{name}"'
    return f"{SEARCH_ENDPOINT}?{urlencode({'q': q, 'limit': limit, 'fields': fields})}"


def author_search(name, get_json=None, **kw):
    """Live (or fixture-replayed) OL author search — the candidates-mode
    transport (T5.6/T6.3), same [] vs ProviderUnavailable vocabulary as
    `search` (T3's contract, no new postures)."""
    get_json = get_json or enrich.http_get_json
    return map_docs(get_json(build_author_url(name), **kw))
