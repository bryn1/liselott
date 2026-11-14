"""Lane entrypoint (hosting.yaml exec): serve the app on $PORT.

No port fallback — the unit sets PORT (renderer L104), and starting on a
guessed port beside the real one is exactly the silent failure this avoids.
Flask is WSGI and uvicorn is ASGI, so the app crosses on uvicorn's own
WSGIMiddleware — zero new dependencies, the adapter stays inside the pinned
uvicorn requirement.
"""
import os

import uvicorn
from uvicorn.middleware.wsgi import WSGIMiddleware

from app import create_app

if __name__ == "__main__":
    # F-4 (SEC-verdict-12497): proxy_headers is uvicorn's DEFAULT and it
    # rewrites REMOTE_ADDR from a client-written X-Forwarded-For whenever
    # the socket peer is on the forwarding_allow_ips default (localhost =
    # always) — an origin-local spoofer therefore picked its own rate-limit
    # bucket BELOW the app, no matter what app.auth.client_ip reads (the
    # verdict's exact bypass, reproduced raw-socket on this entrypoint).
    # The app's own trust order (CF-Connecting-IP else socket peer) is only
    # honest with uvicorn's header trust OFF: the socket peer stays the
    # socket peer. Scheme stays http (TLS ends at the edge; the app never
    # branched on it — cookies are pinned by config, URLs are path-only).
    uvicorn.run(WSGIMiddleware(create_app()), host="0.0.0.0",
                port=int(os.environ["PORT"]), proxy_headers=False)
