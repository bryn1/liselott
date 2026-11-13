"""The ONE cover normalizer (T3.4; T5.3 upload and T6.4 bundle write reuse
THIS, no second pipeline) and its candidate fetcher: scheme-checked download,
Pillow → RGB → thumbnail ≤340×510 → JPEG q82, written beside the row so file
and row can never disagree. Split out of app/enrich.py in the M4 clean-code
pass (§9 seam of .audits/20261112-phase2); app.enrich re-exports every name
below, so no import site changed."""
import io

from app.enrich_http import MAX_BODY, BodyTooLarge, http_get

MAX_COVER_EDGE = (340, 510)          # §5.11: normalized covers are ≤340×510
COVER_QUALITY = 82
COVER_SUBDIR = "covers"
# OpenLibrary's "no cover" answer is a 200 with a 1×1 GIF, and an arbitrary page
# url can hand over anything; anything this small is a placeholder, never art.
MIN_COVER_PX = 60


class CoverRejected(Exception):
    """Bytes that are not a storable image, or a cover URL that is not an
    http(s) image — refuse, never write a broken cover file."""


def fetch_cover(url, *, fetch=None, max_bytes=MAX_BODY):
    """Download a candidate cover. Scheme-checked BEFORE any fetch (a provider
    field is data, never a command: file:// and friends are refused outright),
    then size-capped."""
    fetch = fetch or http_get
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        raise CoverRejected(f"inte en http(b)-bild: {url!r}")
    data = fetch(url, max_bytes=max_bytes)
    if len(data) > max_bytes:
        raise BodyTooLarge(f"bilden är större än {max_bytes} byte — nekas")
    return data


def store_cover(conn, book_id, data, source):
    """THE cover normalizer (T5.3 upload and T6.4 bundle write reuse THIS):
    Pillow → RGB → thumbnail ≤340×510 → JPEG q82 → <state_base()>/covers/
    <book_id>.jpg, and the row's cover_path/cover_source are written here so
    file and row can never disagree. Bytes that are not an image are refused
    with nothing written."""
    from PIL import Image, UnidentifiedImageError

    from app import db
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise CoverRejected(f"inte en bild: {e}") from e
    if img.width < MIN_COVER_PX or img.height < MIN_COVER_PX:
        # A 1×1 GIF is not a cover. covers.openlibrary.org answers 200 with
        # exactly that when it has none (RECORDED in tests/fixtures/
        # ol_no_cover_stub.gif), so accepting it would write a blank square as
        # the book's cover and let the F-2 loop converge on garbage.
        raise CoverRejected(
            f"bilden är {img.width}×{img.height} px — för liten för att vara ett omslag")
    img = img.convert("RGB")
    img.thumbnail(MAX_COVER_EDGE)
    rel = f"{COVER_SUBDIR}/{book_id}.jpg"
    target = db.state_base() / COVER_SUBDIR / f"{book_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=COVER_QUALITY)
    target.write_bytes(buf.getvalue())

    from app import auth
    conn.execute("UPDATE book SET cover_path = ?, cover_source = ?, updated = ? "
                 "WHERE id = ?", (rel, source, auth.utcnow_iso(), book_id))
    conn.commit()
    return rel
