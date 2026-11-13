"""Libris client (owner requirement: the national library is consulted first).

HOST CORRECTION 2026-11-13, owner-of-run decision: PLAN-c3 §12 pinned
`librisxl.net` and recorded NO-DNS for it — that measurement was right, the
host was wrong. `libris.kb.se` IS reachable from the build clone, and it is the
same institution's own API. The client therefore keeps its architecture
(find → get, availability cache, silent degradation) and changes endpoint,
query syntax and response mapping.

Measured against the live API while this was rewritten (not assumed):
- `xsearch?format=json&query=…` answers JSON; the FIELDed syntax the plan
  pinned (`titel:"…" AND creators:"…"`) returns 0 records, while the plain
  free-text form finds the book — so the query is free text.
- the `limit` parameter is IGNORED by xsearch (asked for 3, got the 10 it
  wanted); the client therefore processes at most MAX_HITS items.
- a full record needs `Accept: application/json`, sent by this module's opener:
  `?format=json` and `.json` both return HTML (verified), and without the
  header the record endpoint answers `text/html`.
- `resource/bib/<id>` answers JSON only for the legacy NUMERIC bib ids; newer
  hashed production ids 404 on every JSON form tried
  (/<id>, /<id>.json, /resource/<id>, /get.json?uri=…, ?_format=json). For
  those the client keeps its find fields (isbn/year/author) and asks nobody
  else for detail — a missing detail is a partial answer, never a failure.

So: find gives identity (title/creator/isbn/date), get adds what only Libris
has — subjects and, when the national library has an image, a cover. A
transport failure still marks the provider DOWN for DOWN_S seconds (§12
availability cache) and the caller skips it without an exception reaching a
row; DEFAULT is the process-wide instance the build CLI and the future
/backfill route share (P2-b — one mechanism).

Fixture note: tests/fixtures/libris_*.json are RECORDED live responses from
libris.kb.se on 2026-11-13 (the synthetic pair that stood here while the host
was assumed dead is deleted). Tests replay them offline."""
import re
import time
import urllib.request
from urllib.parse import quote, unquote, urlencode

from app import enrich

HOST = "https://libris.kb.se"          # the ONE named host constant (§12 correction)
XSEARCH_ENDPOINT = f"{HOST}/xsearch"
RECORD_ENDPOINT = f"{HOST}/resource/bib"   # legacy numeric bib ids answer JSON here
MAX_HITS = 10                          # what one xsearch page actually returns

_YEAR_RE = re.compile(r"\b(1[4-9]\d{2}|20\d{2})\b")


class _AcceptJSON(urllib.request.BaseHandler):
    """The record endpoint negotiates: no Accept → text/html (verified)."""

    def http_request(self, request):
        request.add_header("Accept", "application/json")
        return request

    https_request = http_request


_OPENER = None


def json_opener():
    """The shared mechanism's opener plus Libris' Accept header — the same
    retries, timeout, byte cap and UA as every other provider call."""
    global _OPENER
    if _OPENER is None:
        _OPENER = enrich.build_opener()
        _OPENER.add_handler(_AcceptJSON())
    return _OPENER


def _get_json(url, **kw):
    kw.setdefault("opener", json_opener())
    return enrich.http_get_json(url, **kw)


class Libris:
    DOWN_S = 10 * 60                     # §12: 10-minute availability cache

    def __init__(self):
        self._down_until = 0.0           # process-local, not DB state

    def available(self, *, now=time.time) -> bool:
        return now() >= self._down_until

    def _mark_down(self, now):
        self._down_until = now() + self.DOWN_S

    def build_find_url(self, title, author):
        """Free-text query: the API's fielded form returns nothing, the plain
        form finds the book (verified 2026-11-13)."""
        query = " ".join(part for part in (str(title or "").strip(),
                                           str(author or "").strip()) if part)
        return f"{XSEARCH_ENDPOINT}?{urlencode({'format': 'json', 'query': query})}"

    @staticmethod
    def build_get_url(identifier):
        """Legacy numeric bib ids only — a hashed id has no JSON form here, so
        no request is made at all (manners: do not hammer a 404 per row)."""
        last = str(identifier or "").rstrip("/").split("/")[-1]
        if not last.isdigit():
            return None
        return f"{RECORD_ENDPOINT}/{quote(last, safe='')}"

    @staticmethod
    def map_find(payload):
        """xsearch.list -> partial hits. `creator` is Libris' inverted
        'Surname, First, 1900-' form, normalized for the author gate."""
        hits = []
        block = (payload or {}).get("xsearch") or {}
        for item in (block.get("list") or [])[:MAX_HITS]:
            hit = {
                "source": "libris",
                "id": item.get("identifier"),
                "title": _text(item.get("title")),
                "authors": _persons(item.get("creator")),
                "isbn13": None, "isbn10": None,
                "year": _year(item.get("date") or item.get("pubyear")),
                "type": _text(item.get("type")),
                "cover_id": None,
                "cover_url": None,
                "subjects": [],
            }
            hit["isbn13"], hit["isbn10"] = _isbns(item.get("isbn"))
            hits.append(hit)
        return hits

    @staticmethod
    def map_doc(payload):
        """A full record (Accept: application/json) sits under mainEntity:
        hasTitle/publication/identifiedBy for identity, instanceOf for the
        authors and subjects, image for the national library's own cover.
        Libris' JSON-LD answers a single value or a list interchangeably
        (verified on two real records), so every walk normalizes first."""
        me = _one((payload or {}).get("mainEntity"))
        if not me:
            return {}
        work = _one(me.get("instanceOf"))
        isbn13, isbn10 = _isbns([i.get("value") for i in _many(me.get("identifiedBy"))
                                 if "ISBN" in str(i.get("@type"))])
        titles = [t.get("mainTitle") for t in _many(me.get("hasTitle"))
                  if t.get("mainTitle")]
        years = [_year(p.get("year")) for p in _many(me.get("publication"))]
        authors = []
        for c in _many(work.get("contribution")):
            # a contribution with no role is a PrimaryContribution (the author);
            # a narrator/illustrator role must NOT become a book's author
            codes = {str(r.get("code") or "") for r in _many(c.get("role"))}
            if codes and not codes & {"aut", ""}:
                continue
            for agent in _many(c.get("agent")):
                name = " ".join(p for p in (agent.get("givenName"), agent.get("familyName"))
                                if p) or _text(agent.get("label"))
                if name:
                    authors.append(name)
        subjects = [_text(s.get("prefLabel") or s.get("label"))
                    for s in _many(work.get("subject"))]
        return {
            "title": _text(titles),
            "authors": authors,
            "isbn13": isbn13,
            "isbn10": isbn10,
            "year": next((y for y in years if y), None),
            "subjects": [s for s in subjects if s],
            "cover_url": _cover_url(me.get("image")),
        }

    def search(self, title, author, get_json=None, *, now=time.time, **kw):
        """xsearch for candidates, then the full record for the first one that
        has a legacy id, to add subjects/cover. A find failure = unavailable
        (marks DOWN); a missing or failing record keeps the find fields."""
        get_json = get_json or _get_json
        if not self.available(now=now):
            return None
        try:
            hits = self.map_find(get_json(self.build_find_url(title, author), **kw))
        except enrich.ProviderUnavailable:
            self._mark_down(now)
            return None
        self._down_until = 0.0           # a live answer clears the DOWN mark
        for hit in hits:
            url = self.build_get_url(hit.get("id"))
            if url is None:
                continue                 # hashed id: no JSON form, keep find fields
            try:
                detail = self.map_doc(get_json(url, **kw))
            except enrich.ProviderUnavailable:
                continue                 # keep the find-doc fields
            for field in ("title", "year", "cover_url"):
                if detail.get(field):
                    hit[field] = detail[field]
            for field in ("authors", "subjects"):
                if detail.get(field):
                    hit[field] = detail[field]
            for field in ("isbn13", "isbn10"):
                if detail.get(field) and not hit.get(field):
                    hit[field] = detail[field]
        return hits


def search(title, author, get_json=None, *, now=time.time, **kw):
    return DEFAULT.search(title, author, get_json=get_json, now=now, **kw)


def available(*, now=time.time):
    return DEFAULT.available(now=now)


DEFAULT = Libris()


def _text(value):
    """xsearch answers a scalar or a one-element list depending on the field."""
    if isinstance(value, list):
        return _text(value[0]) if value else ""
    return str(value).strip() if value is not None else ""


def _one(value):
    """Libris' JSON-LD answers one object or a list of them (verified on two
    real records: `role` is a dict in one, a list in the other)."""
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
        return {}
    return value if isinstance(value, dict) else {}


def _many(value):
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, dict)]


def _persons(value):
    """'Emilsson, Kristin' / 'Strömberg, Louise' -> ['Kristin Emilsson'].
    Libris inverts names and appends life dates ('1971-'), which would otherwise
    sit in the way of the author gate's comparison."""
    names = value if isinstance(value, list) else [value]
    out = []
    for raw in names:
        text = str(raw or "").strip()
        if not text:
            continue
        parts = [p.strip() for p in text.split(",")]
        named = [p for p in parts if p and not re.fullmatch(r"[\d\sbcop.\-–—()]*", p)]
        if len(named) >= 2 and len(parts) > 1:      # "Surname, First[, 1900-]"
            out.append(f"{named[1]} {named[0]}")
        else:
            out.append(named[0] if named else text)
    return out


def _isbns(values):
    isbn13 = isbn10 = None
    for raw in (values or [] if isinstance(values, list) else [values]):
        for token in re.split(r"[,; ]+", str(raw or "")):
            digits = token.replace("-", "").strip()
            if len(digits) == 13 and digits.isdigit() and isbn13 is None:
                isbn13 = digits
            elif len(digits) == 10 and isbn10 is None and digits[:-1].isdigit():
                isbn10 = digits
    return isbn13, isbn10


def _year(value):
    """Libris dates are bibliographic strings: 'cop. 2016', '[2017]',
    'p 2016', '2015)', or a list of them. First plausible year wins."""
    for item in (value if isinstance(value, list) else [value]):
        found = _YEAR_RE.search(str(item or ""))
        if found:
            return int(found.group(1))
    return None


def _px(value):
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def _cover_url(images):
    """Prefer a thumbnail that already fits the cover budget (≤340×510) rather
    than pulling a 1400×2265 original down for nothing; fall back to the full
    image, which store_cover resizes anyway."""
    best = None
    for image in _many(images):
        candidates = [(_px(image.get("width")), _px(image.get("height")),
                       image.get("@id"))]
        for thumb in _many(image.get("thumbnail")):
            same_as = _one(thumb.get("sameAs")).get("@id")
            candidates.append((_px(thumb.get("width")), _px(thumb.get("height")),
                               same_as))
        for width, height, url in candidates:
            if not url or not url.startswith("http"):
                continue
            fits = width <= enrich.MAX_COVER_EDGE[0] and height <= enrich.MAX_COVER_EDGE[1]
            area = width * height
            if fits and (best is None or area > best[0]):
                best = (area if fits else 0, url)
            elif best is None and not fits:
                best = (0, url)
    return best[1] if best else None
