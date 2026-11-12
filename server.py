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
    uvicorn.run(WSGIMiddleware(create_app()), host="0.0.0.0",
                port=int(os.environ["PORT"]))
