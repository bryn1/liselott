"""The ONE http mechanism for every provider AND for the admin hitta-omslag
fetcher (§10, F-1: enrichment runs where the plan says it runs — the VM350
build passes AND the app's own clients inside its jail): stdlib urllib, 3 s
timeout, retries with exponential backoff on 429/5xx, a byte cap on every
body it reads. A 429 that survives the retries surfaces as RateLimited so a
caller can act on it (the gb cooldown, T3.2) without a second http path.
Bodies are capped, never streamed into memory blind: an over-budget body
raises BodyTooLarge naming the budget.

Split out of app/enrich.py in the M4 clean-code pass (§9 seam of
.audits/20261112-phase2); app.enrich re-exports every name below, so no
import site changed."""
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

# ASCII ONLY: urllib encodes headers as latin-1, so one em dash here would
# kill every real request (UnicodeEncodeError) while fixture transports, which
# never encode a header, stay green — the live smoke caught it (guarded in
# tests/test_enrich_ol.py).
USER_AGENT = "liselott-bokhylla/1.0 (personal book diary)"

# Lane fact (§10, P1-1): every byte transfer INTO the app is chunked below a
# 900,000-byte budget; the same number bounds what the app itself accepts to
# read back from any single response.
MAX_FETCH = 900_000


class ProviderUnavailable(Exception):
    """The provider could not be consulted (DNS/timeout/refused/definitive 4xx).
    Callers record the attempt in tried_providers; nothing here crashes a row."""


class RateLimited(ProviderUnavailable):
    """429 after the retries — a provider-side cooldown signal, not a failure
    of the row."""


class BodyTooLarge(ProviderUnavailable):
    """Response body exceeded max_bytes — refuse, never half-read."""


def http_get(url, *, timeout=3.0, attempts=3, backoff=2.0,
             max_bytes=MAX_FETCH, opener=None, sleep=time.sleep):
    """GET url -> bytes. Retries URLError/429/5xx with exponential backoff
    (backoff * 2**n, VERIFIED red-capable in tests/test_enrich_ol.py); a
    definitive 4xx (not 429) is not retried. Raises RateLimited on a final 429,
    ProviderUnavailable otherwise."""
    # Scheme rule in the MECHANISM, not in each caller: urllib's default opener
    # ships FileHandler/FTPHandler, so an unchecked url turns this function into
    # a local file reader (measured: file:///etc/hostname returned its bytes).
    parts = urlsplit(str(url))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ProviderUnavailable(f"endast http/https hämtas — nekar {url!r}")
    op = opener or _default_opener()
    last = None
    for attempt in range(attempts):
        try:
            resp = op.open(url, timeout=timeout)
            try:
                body = resp.read(max_bytes + 1)
            finally:
                resp.close()
            if len(body) > max_bytes:
                raise BodyTooLarge(
                    f"svaret är större än {max_bytes} byte — nekas")
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                if attempt == attempts - 1:
                    raise RateLimited(f"429 from {url}") from e
            elif e.code >= 500:
                if attempt == attempts - 1:
                    raise ProviderUnavailable(f"{e.code} from {url}") from e
            else:
                raise ProviderUnavailable(f"{e.code} from {url}") from e
        except (urllib.error.URLError, OSError) as e:   # DNS, timeout, reset
            last = e
            if attempt == attempts - 1:
                raise ProviderUnavailable(f"transport failed for {url}") from e
        sleep(backoff * (2 ** attempt))
    raise ProviderUnavailable(f"transport failed for {url}: {last}")


def http_get_json(url, **kw):
    """http_get + json.loads; a body that is not JSON is a ProviderUnavailable
    (a WAF page or an HTML error screen must never parse as a hit)."""
    body = http_get(url, **kw)
    try:
        return json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise ProviderUnavailable(f"non-JSON body from {url}") from e


def build_opener():
    op = urllib.request.build_opener()
    op.addheaders = [("User-Agent", USER_AGENT),
                     ("Accept", "application/json, image/*;q=0.8, */*;q=0.5")]
    return op


def _default_opener():
    # Built per call on purpose: a module-level opener would keep connection
    # state across tests that inject their own (the opener= parameter is the
    # single seam every test uses — fixture transport, never the network).
    return build_opener()
