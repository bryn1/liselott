"""The ONE cover normalizer (T3.4; T5.3 upload and T6.4 bundle write reuse
THIS, no second pipeline) and its candidate fetcher: scheme-checked download,
Pillow → RGB → thumbnail ≤340×510 → JPEG q82, written beside the row so file
and row can never disagree. Split out of app/enrich.py in the M4 clean-code
pass (§9 seam of .audits/20261112-phase2); app.enrich re-exports every name
below, so no import site changed."""
import io

from app.enrich_http import MAX_FETCH, BodyTooLarge, http_get

MAX_COVER_EDGE = (340, 510)          # §5.11: normalized covers are ≤340×510
COVER_QUALITY = 82
COVER_SUBDIR = "covers"
# OpenLibrary's "no cover" answer is a 200 with a 1×1 GIF, and an arbitrary page
# url can hand over anything; anything this small is a placeholder, never art.
MIN_COVER_PX = 60


class CoverRejected(Exception):
    """Bytes that are not a storable image, or a cover URL that is not an
    http(s) image — refuse, never write a broken cover file."""


def fetch_cover(url, *, fetch=None, max_bytes=MAX_FETCH):
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


def validate_cover_bytes(data):
    """The image refusal, factored out of store_cover for T6.4's PARSE phase:
    a POSTed bundle must reject a broken cover line BEFORE anything is
    written, so the whole POST can roll back (T6.4 leg g). ONE definition of
    "is this an image" — store_cover calls the same function it guards."""
    from PIL import Image, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Image.DecompressionBombError as e:
        # F-D2 leg 3 (MC 12451): a plain Exception, invisible to the tuple
        # below — 438 KB carrying 400 M px was a 500 at the door (and at
        # /redigera's upload). The byte cap can NEVER guard pixel counts;
        # PIL's own bomb guard does, and its refusal joins THE cover
        # refusal: Swedish copy here, the named-line 400 via parse.
        raise CoverRejected(
            f"bilden är för stor för att vara ett omslag ({e})") from e
    except (UnidentifiedImageError, OSError, ValueError) as e:
        raise CoverRejected(f"inte en bild: {e}") from e
    if img.width < MIN_COVER_PX or img.height < MIN_COVER_PX:
        # A 1×1 GIF is not a cover. covers.openlibrary.org answers 200 with
        # exactly that when it has none (RECORDED in tests/fixtures/
        # ol_no_cover_stub.gif), so accepting it would write a blank square as
        # the book's cover and let the F-2 loop converge on garbage.
        raise CoverRejected(
            f"bilden är {img.width}×{img.height} px — för liten för att vara ett omslag")
    return img


def normalize_image(data) -> bytes:
    """THE byte pipeline behind store_cover, exposed for T6.4's idempotence
    check: a re-POST's raw bytes differ from the stored JPEG q82, so only
    normalizing first can answer "does this write change anything" — and the
    definition of normalizing lives in ONE place (P1-2's reuse rule)."""
    img = validate_cover_bytes(data)
    img = img.convert("RGB")
    img.thumbnail(MAX_COVER_EDGE)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=COVER_QUALITY)
    return buf.getvalue()


def store_cover(conn, book_id, data, source, commit=True):
    """THE cover normalizer (T5.3 upload and T6.4 bundle write reuse THIS):
    normalize_image → covers/<book_id>.jpg, and the row's cover_path/
    cover_source are written here so file and row can never disagree. Bytes
    that are not an image are refused with nothing written. A write whose
    bytes are already on disk byte-identical touches the disk not at all
    (T6.4 leg e); the rel path is returned either way — the row IS the
    cover's truth. commit=False (P3-4, MC 12451) leaves the row-update in
    the CALLER's transaction: the /bundle POST is ONE transaction whose
    rollback must reach every earlier line, cover included — a mid-chunk
    commit here would make that rollback a partial import."""
    from app import db
    payload = normalize_image(data)
    rel = f"{COVER_SUBDIR}/{book_id}.jpg"
    target = db.state_base() / COVER_SUBDIR / f"{book_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    if (not target.exists()) or target.read_bytes() != payload:
        target.write_bytes(payload)

    from app import auth
    conn.execute("UPDATE book SET cover_path = ?, cover_source = ?, updated = ? "
                 "WHERE id = ?", (rel, source, auth.utcnow_iso(), book_id))
    if commit:
        conn.commit()
    return rel
