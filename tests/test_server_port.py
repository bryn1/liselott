"""T0.2 — server.py must bind $PORT (no fallback: a missing PORT dies loudly)."""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT = 8199


def test_server_binds_env_port(tmp_path):
    env = dict(os.environ, PORT=str(PORT), LISELOTT_ENV="dev",
               LISELOTT_DATA_DIR=str(tmp_path))
    proc = subprocess.Popen(
        [sys.executable, "server.py"], cwd=REPO_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{PORT}/healthz"
    deadline = time.time() + 15
    try:
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    assert resp.status == 200
                    assert resp.read() == b"ok"
                return
            except (urllib.error.URLError, ConnectionError, TimeoutError):
                if proc.poll() is not None:
                    out = proc.stdout.read().decode(errors="replace")
                    raise AssertionError(f"server exited early:\n{out}")
                time.sleep(0.2)
        raise AssertionError(f"no 200 on {url} within 15 s")
    finally:
        proc.terminate()
        proc.wait(timeout=10)
