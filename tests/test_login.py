"""T2.2 — login/logout + cookie contract (§6.3, P2-4/P2-9). Cookie assertions
include the UNSET-env Secure case: unset LISELOTT_ENV = production = Secure ON."""
import pytest

from app import create_app

PASSWORD = "_test_losenord_"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Configured app: password set through the real first-run flow."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    flask_app = create_app()
    flask_app.testing = True

    @flask_app.route("/bibliotek")
    def _bibliotek_stub():
        return "hylla", 200

    @flask_app.route("/")
    def _root_stub():
        return "rot", 200

    client = flask_app.test_client()
    r = client.post("/liselott/satt-loesenord",
                    data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    assert r.status_code == 302

    return flask_app, client


def test_login_page_selector_and_copy(env):
    _, client = env
    r = client.get("/logga-in")
    assert r.status_code == 200
    assert "Logga in" in r.text  # publish bar T8.8 requires this literal
    assert 'id="loesenord"' in r.text


def test_login_while_unconfigured_redirects_to_setup(tmp_path, monkeypatch):
    """§6.1 open state: /logga-in GET -> 302 /satt-loesenord (login page only
    exists once the password is set)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.delenv("LISELOTT_ENV", raising=False)
    app = create_app()
    app.testing = True
    r = app.test_client().get("/logga-in")
    assert r.status_code == 302
    assert r.headers["Location"] == "/liselott/satt-loesenord"


def test_wrong_password_401_fel_meddelande(env):
    _, client = env
    r = client.post("/logga-in", data={"loesenord": "_fel_losenord_"})
    assert r.status_code == 401
    assert "Fel lösenord" in r.text
    assert "fel-meddelande" in r.text


def test_wrong_password_bodies_byte_identical(env):
    """No oracle: two different wrong passwords give the exact same bytes."""
    _, client = env
    r1 = client.post("/logga-in", data={"loesenord": "_fel_losenord_"})
    r2 = client.post("/logga-in", data={"loesenord": "annan-fel-siffra-9"})
    assert r1.status_code == r2.status_code == 401
    assert r1.data == r2.data


def test_cookie_contract_production_default(env):
    """LISELOTT_ENV unset (production): name, HttpOnly, SameSite=Lax,
    Path=/liselott, Secure — all asserted on the Set-Cookie header."""
    _, client = env
    r = client.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    assert r.status_code == 302
    cookie = r.headers["Set-Cookie"]
    assert cookie.startswith("liselott_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/liselott" in cookie
    assert "Secure" in cookie
    assert client.get("/liselott/").status_code == 200  # session established


def test_cookie_no_secure_only_in_dev(tmp_path, monkeypatch):
    """The ONLY dev escape hatch: LISELOTT_ENV=dev drops Secure (localhost
    testing); every other flag stays (§6.3 fail-safe: unset = production)."""
    monkeypatch.setenv("LISELOTT_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("LISELOTT_PREFIX", raising=False)
    monkeypatch.setenv("LISELOTT_ENV", "dev")
    app = create_app()
    app.testing = True
    client = app.test_client()
    client.post("/liselott/satt-loesenord",
                data={"loesenord": PASSWORD, "bekrafta": PASSWORD})
    r = client.post("/liselott/logga-in", data={"loesenord": PASSWORD})
    cookie = r.headers["Set-Cookie"]
    assert cookie.startswith("liselott_session=")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert "Secure" not in cookie


def test_logout_clears_session(env):
    _, client = env
    assert client.get("/liselott/").status_code == 200
    r = client.get("/liselott/logga-ut")
    assert r.status_code == 302  # back to login
    assert client.get("/liselott/").status_code == 302
    assert client.get("/liselott/").headers["Location"] == "/liselott/logga-in"
