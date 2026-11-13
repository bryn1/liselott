"""Google Books client — OPPORTUNISTIC only. VERIFIED (§2/§12): the no-key
shared consumer hard-429s from this host today, so the provider must never sit
in the way: a 429 (the RateLimited signal app.enrich raises after its own
backoff retries) writes settings.gb_cooldown_until = now + 6 h, and while that
timestamp is in the future `available()` is False and the transport is NEVER
called. The settings access reuses app.auth.get_setting/set_setting — one
settings mechanism, not two.

Return contract shared with T3.4's resolve: a LIST of hits means the provider
answered ([] = "nothing found"); None means it could not be consulted
(cooldown active, 429, or transport failure). That distinction is what lets
tried_providers record an attempt honestly."""
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from app import auth, enrich

COOLDOWN_S = 6 * 60 * 60           # §12: a 429 cools gb for six hours
COOLDOWN_KEY = "gb_cooldown_until"
ENDPOINT = "https://www.googleapis.com/books/v1/volumes"
ISO = "%Y-%m-%dT%H:%M:%SZ"


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(ISO)


def _epoch(stored: str):
    try:
        return datetime.strptime(stored, ISO).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None                # unreadable value = expired, re-ask


def build_url(title, author):
    q = f"intitle:{title}"
    if author:
        q += f" inauthor:{author}"
    return f"{ENDPOINT}?{urlencode({'q': q, 'maxResults': 5})}"


def available(conn, *, now=time.time) -> bool:
    """False ONLY while a future gb_cooldown_until sits in settings."""
    stored = auth.get_setting(conn, COOLDOWN_KEY)
    if not stored:
        return True
    until = _epoch(stored)
    if until is None or until <= now():
        return True
    return False


def set_cooldown(conn, until_epoch: float):
    auth.set_setting(conn, COOLDOWN_KEY, _iso(until_epoch))


def map_volume(item):
    """One volumes item -> the shared hit dict (no subjects: gb has no subject
    list, the §5 genre mapping lands on OL/Libris)."""
    info = (item or {}).get("volumeInfo") or {}
    isbn13 = isbn10 = None
    for ident in info.get("industryIdentifiers") or []:
        digits = str(ident.get("identifier", "")).replace("-", "").strip()
        if ident.get("type") == "ISBN_13" and len(digits) == 13:
            isbn13 = digits
        elif ident.get("type") == "ISBN_10" and len(digits) == 10:
            isbn10 = digits
    year = None
    published = str(info.get("publishedDate") or "")
    if len(published) >= 4 and published[:4].isdigit():
        year = int(published[:4])
    thumb = (info.get("imageLinks") or {}).get("thumbnail")
    return {
        "source": "googlebooks",
        "title": info.get("title") or "",
        "authors": [str(a) for a in info.get("authors") or []],
        "isbn13": isbn13,
        "isbn10": isbn10,
        "year": year,
        "cover_id": None,
        "cover_url": thumb,
        "thumbnail": thumb,
        "subjects": [],
    }


def search(title, author, conn, get_json=None, *, now=time.time, **kw):
    """[] = answered nothing; None = could not be asked (cooldown / 429 /
    transport). A 429 also STARTS the six-hour cooldown right here — the one
    place that knows gb is rate-limited."""
    get_json = get_json or enrich.http_get_json
    if not available(conn, now=now):
        return None
    try:
        payload = get_json(build_url(title, author), **kw)
    except enrich.RateLimited:
        set_cooldown(conn, now() + COOLDOWN_S)
        return None
    except enrich.ProviderUnavailable:
        return None
    return [map_volume(item) for item in (payload or {}).get("items") or []]
