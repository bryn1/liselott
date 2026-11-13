"""OQ-2 — the admin "hitta omslag" helper (owner ruling 2026-11-12).

The admin pastes the url of a PAGE (a publisher's book page, a library record).
The app fetches that page server-side, takes its `og:image` — or, when the page
carries no og:image, its largest `<img>` — and stores it as the book's cover
with cover_source='manual-url'. The UI wiring lands in S5; this is the server
side, and the route inherits the §6.4 login guard and the §6.6 CSRF gate (no new
gate mechanism).

The bounds are the ruling's, and each one is tested in
tests/test_omslag_hitta.py: http/https only, refused BEFORE a single byte is
requested (measured: `enrich.http_get("file:///etc/hostname")` really returns
that file, so this refusal is load-bearing, not ceremony); response bodies
capped at MAX_FETCH (900 000 B); the image allowed only if its magic bytes say
it is one; a 3 s timeout via the ONE http mechanism; and a redirect into
file://, gopher:// or any other scheme is never followed (urllib's redirect
handler declines non-http targets — proven with a real loopback 302).
"""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from app import enrich

MAX_FETCH = enrich.MAX_FETCH        # the one byte budget (§10), same as everywhere
http_get = enrich.http_get        # the ONE http mechanism, bound here so a test
                                  # can substitute the transport and nothing else
# The image types the app will write as a cover — recognized by MAGIC BYTES
# (what a server claims about a body is not evidence of what the body is).
IMAGE_MAGIC = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"), (b"GIF89a", "gif"),
    (b"BM", "bmp"),
)
WEBP_RIFF = b"RIFF"
WEBP_TAG = b"WEBP"

NOT_HTTP = ("Endast http- och https-adresser får användas — "
            "ingen annan adressetyp hämtas.")


def image_kind(data):
    """Magic bytes, not a Content-Type header: what a server SAYS a body is
    proves nothing, and the app is about to write it to disk as a cover."""
    if not isinstance(data, (bytes, bytearray)):
        return None
    for magic, kind in IMAGE_MAGIC:
        if data.startswith(magic):
            return kind
    if data.startswith(WEBP_RIFF) and data[8:12] == WEBP_TAG:
        return "webp"
    return None


def is_http_url(url):
    parts = urlsplit(str(url or "").strip())
    return parts.scheme in ("http", "https") and bool(parts.netloc)


class _Images(HTMLParser):
    """og:image first, `<img>` sizes as the fallback (§ the ruling). Widths and
    heights come from the attributes the page itself declares; an <img> with no
    size attrs scores 0 and therefore loses to any declared one."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og = None
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        got = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (got.get("property") or got.get("name") or "").lower()
            if key in ("og:image", "og:image:url", "og:image:secure_url") and not self.og:
                self.og = got.get("content") or None
        elif tag == "img":
            try:
                size = (int(float(got.get("width") or 0)), int(float(got.get("height") or 0)))
            except ValueError:
                size = (0, 0)
            if got.get("src"):
                self.imgs.append((got["src"], size[0] * size[1]))


def extract_cover_url(html, base_url):
    """The cover url a page advertises, absolute, http(s) — or None. A data:
    URI is content, never something this app fetches back."""
    parser = _Images()
    try:
        parser.feed(html)
    except Exception:                      # a broken page is not a crash
        return None
    candidates = []
    if parser.og:
        candidates.append(parser.og)
    candidates += [src for src, _ in sorted(parser.imgs, key=lambda kv: -kv[1])]
    for raw in candidates:
        absolute = urljoin(base_url, raw.strip())
        if is_http_url(absolute):
            return absolute
    return None


def hamta_omslag(conn, book_id, page_url, *, get=None):
    """Fetch the page, take its cover, store it. Never raises: every failure
    comes back as {'ok': False, 'fel': <Swedish message>} — the admin sees a
    reason, the row keeps whatever cover it had."""
    get = get or http_get
    if not is_http_url(page_url):
        return {"ok": False, "fel": NOT_HTTP}
    row = conn.execute("SELECT id FROM book WHERE id = ?", (book_id,)).fetchone()
    if row is None:
        return {"ok": False, "fel": "Boken finns inte."}

    page_url = page_url.strip()
    try:
        page = get(page_url)
    except enrich.ProviderUnavailable:
        return {"ok": False, "fel": "Sidan kunde inte hämtas — försök igen."}
    if len(page) > MAX_FETCH:
        return {"ok": False, "fel": f"Sidan är större än {MAX_FETCH} byte — nekas."}

    found = extract_cover_url(page.decode("utf-8", "replace"), page_url)
    if not found:
        return {"ok": False, "fel": "Hittade ingen omslagsbild på sidan."}
    try:
        image = get(found)
    except enrich.ProviderUnavailable:
        return {"ok": False, "fel": "Bilden kunde inte hämtas — försök igen."}
    if len(image) > MAX_FETCH:
        return {"ok": False, "fel": f"Bilden är större än {MAX_FETCH} byte — nekas."}
    if image_kind(image) is None:
        return {"ok": False, "fel": "Det som hittades är ingen bild."}
    try:
        enrich.store_cover(conn, book_id, image, "manual-url")
    except enrich.CoverRejected:
        return {"ok": False, "fel": "Bilden kunde inte sparas som omslag."}
    return {"ok": True, "cover_source": "manual-url", "book_id": book_id}
