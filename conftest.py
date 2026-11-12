# Makes the repo root importable for bare `pytest` (`python -m pytest` already
# puts the CWD on sys.path; plain `pytest` needs this root conftest to do it).
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _suite_state_dir(tmp_path_factory):
    """The auth guard reads the settings table on every request — keep the
    suite's state dir in pytest's tmp space unless the caller already set the
    build override (tests that exercise state_base() itself monkeypatch it
    per-test regardless)."""
    prev = os.environ.get("LISELOTT_DATA_DIR")
    if prev is None:
        os.environ["LISELOTT_DATA_DIR"] = str(tmp_path_factory.mktemp("suite-state"))
    yield
    if prev is None:
        del os.environ["LISELOTT_DATA_DIR"]
