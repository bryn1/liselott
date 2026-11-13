"""Libris client (owner requirement: the national library is consulted first).
THE LIVE REALITY FROM VM350 IS NO-DNS on both domains (VERIFIED, PLAN-c3 §2),
so this client is built to be quietly absent: find.json/get.json each run on
app.enrich.http_get (3 s timeout, ONE http mechanism); a transport failure
marks the provider DOWN for DOWN_S seconds (§12 availability cache — one 3 s
DNS-timeout per unavailability window, the §12 P3-3 cost), and the caller
skips it without an exception reaching any row.

Fixture-only by nature (§2): tests/fixtures/libris_*.json are SYNTHETIC and
labelled as such; production egress from vm106 MAY resolve rows the build run
never could — an upside the plan names, never a premise.

Return contract is the shared one (T3.1/T3.2): list = answered ([] nothing
found), None = could not be asked. DEFAULT is the process-wide instance the
build CLI and the later /backfill route share (P2-b — one mechanism)."""
import time
from urllib.parse import quote, urlencode

from app import enrich

FIND_ENDPOINT = "https://librisxl.net/find.json"
GET_ENDPOINT = "https://librisxl.net/get.json"
LIMIT = 3


class Libris:
    DOWN_S = 10 * 60                     # §12: 10-minute availability cache

    def __init__(self):
        self._down_until = 0.0           # process-local, not DB state

    def available(self, *, now=time.time) -> bool:
        return now() >= self._down_until

    def _mark_down(self, now):
        self._down_until = now() + self.DOWN_S

    def build_find_url(self, title, author):
        q = f'titel:"{title}"'
        if author:
            q += f' AND creators:"{author}"'
        return f"{FIND_ENDPOINT}?{urlencode({'q': q, 'limit': LIMIT})}"

    @staticmethod
    def build_get_url(doc_id):
        return f"{GET_ENDPOINT}?{urlencode({'uri': doc_id})}"

    @staticmethod
    def map_find(payload):
        """find.json hits.docs -> partial hits (the shape cycle-1 T3.3 pins)."""
        hits = []
        for doc in (payload or {}).get("hits", {}).get("docs") or []:
            isbn13, isbn10 = _split_isbns(doc.get("isbn"))
            hits.append({
                "source": "libris",
                "id": doc.get("id"),
                "title": doc.get("title") or "",
                "authors": [str(a) for a in doc.get("creators") or []],
                "isbn13": isbn13,
                "isbn10": isbn10,
                "year": _year(doc.get("year")),
                "cover_id": None,
                "cover_url": None,
                "subjects": [],
            })
        return hits

    @staticmethod
    def map_doc(payload):
        """get.json JSON-LD: the doc sits under @graph; the marc-ish fields are
        read by their flattened keys (SYNTHETIC fixture documents this)."""
        graph = (payload or {}).get("@graph") or []
        doc = next((g for g in graph if g.get("title") or g.get("mainTitle")), None)
        if doc is None:
            return {}
        isbn13, isbn10 = _split_isbns(doc.get("isbn"))
        return {
            "title": doc.get("mainTitle") or doc.get("title") or "",
            "authors": [str(c.get("name", "")) for c in doc.get("creators") or []
                        if isinstance(c, dict) and c.get("name")]
                       or [str(c) for c in doc.get("creators") or []
                           if not isinstance(c, dict)],
            "isbn13": isbn13,
            "isbn10": isbn10,
            "year": _year(doc.get("year")),
            "subjects": [str(s) for s in doc.get("subject") or []],
        }

    def search(self, title, author, get_json=None, *, now=time.time, **kw):
        """find.json for candidates, then get.json on the first doc for the
        subject/creator detail. A find failure = unavailable (marks DOWN);
        a get failure keeps the find-doc fields (a partial answer)."""
        get_json = get_json or enrich.http_get_json
        if not self.available(now=now):
            return None
        try:
            hits = self.map_find(get_json(self.build_find_url(title, author), **kw))
        except enrich.ProviderUnavailable:
            self._mark_down(now)
            return None
        self._down_until = 0.0        # a live answer clears the DOWN mark
        for hit in hits:
            if not hit.get("id"):
                continue
            try:
                detail = self.map_doc(get_json(self.build_get_url(hit["id"]), **kw))
            except enrich.ProviderUnavailable:
                continue          # keep the find-doc fields
            for field in ("title", "year"):
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


def _split_isbns(values):
    isbn13 = isbn10 = None
    for raw in values or []:
        digits = str(raw).replace("-", "").strip()
        if len(digits) == 13 and isbn13 is None:
            isbn13 = digits
        elif len(digits) == 10 and isbn10 is None:
            isbn10 = digits
    return isbn13, isbn10


def _year(value):
    text = str(value or "").strip()
    return int(text[:4]) if len(text) >= 4 and text[:4].isdigit() else None
