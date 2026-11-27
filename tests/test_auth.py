import os, json, time, pytest
from base64 import b64encode
from urllib.parse import quote

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from flask import Flask
from dash import Dash, html

from chm_utils.ext import auth

AUTH_REDIRECT_URI = "https://test_uri.com/auth/login"
ISSUER = "https://auth.test.ch"
TEST_USER = 'test_user'
TEST_PWD = 'test_pwd'
TEST_EMAIL = 'jane.doe@chmedia.ch'
TEST_DASH_PATH = '/test/'
TEST_FLASK_PATH = '/test'
TEST_DASH_BASIC_PATH = '/test/admin'

os.environ['AUTH_REDIRECT_URI'] = AUTH_REDIRECT_URI
os.environ['AUTH_BASIC_USER'] = TEST_USER
os.environ['AUTH_BASIC_PWD'] = TEST_PWD
os.environ['AUTH_ISSUER'] = ISSUER

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
JWKS_SIGNING_KEY = auth._signing_key


def jwk(key, kid):
    return {**json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key())), "kid": kid, "use": "sig", "alg": "RS256"}


def session_token(key=KEY, algorithm="RS256", kid=None, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": auth.SESSION_AUDIENCE,
        "sub": TEST_EMAIL,
        "email": TEST_EMAIL,
        "name": "Jane Doe",
        "iat": now,
        "exp": now + 3600,
        **overrides,
    }
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid} if kid else None)


@pytest.fixture(autouse=True)
def jwks(monkeypatch):
    monkeypatch.setattr(auth, "_signing_key", lambda token: KEY.public_key())


@pytest.fixture()
def flask_server():
    # No SECRET_KEY: verifying a login must not need a secret.
    yield Flask('my_flask')


def with_token(client, token):
    client.set_cookie("chmdtoken", token)
    return client


@pytest.fixture()
def flask_login_required(flask_server):

    @flask_server.route(TEST_FLASK_PATH,methods=['GET'])
    @auth.login_required
    def send_status():
        return (auth.current_user()["email"],200)

    return flask_server.test_client()


@pytest.fixture()
def flask_basic_required(flask_server):

    @flask_server.route(TEST_FLASK_PATH,methods=['GET'])
    @auth.basic_required
    def send_status():
        return ('OK!',200)

    return flask_server.test_client()


def test_auth_flask_login_redirect(flask_login_required):

    response = flask_login_required.get(TEST_FLASK_PATH, query_string={"a": "1"})

    assert response.status_code == 302
    next_url = quote("http://localhost/test?a=1", safe="")
    assert response.location == f"{AUTH_REDIRECT_URI}?next={next_url}"
    assert 'Set-Cookie' not in response.headers


def test_auth_flask_login_redirect_keeps_existing_query(flask_login_required, monkeypatch):
    monkeypatch.setenv("AUTH_REDIRECT_URI", f"{AUTH_REDIRECT_URI}?prompt=login")

    response = flask_login_required.get(TEST_FLASK_PATH)

    assert response.location.startswith(f"{AUTH_REDIRECT_URI}?prompt=login&next=")


def test_auth_flask_login_access(flask_login_required):

    response = with_token(flask_login_required, session_token()).get(TEST_FLASK_PATH)

    assert response.status_code == 200
    assert response.get_data(as_text=True) == TEST_EMAIL


@pytest.mark.parametrize("token", [
    pytest.param(session_token(key=OTHER_KEY), id="foreign-key"),
    pytest.param(session_token(aud="https://mcp.data.chmedia.ch/mcp"), id="access-token-audience"),
    pytest.param(session_token(iss="https://evil.example"), id="wrong-issuer"),
    pytest.param(session_token(exp=int(time.time()) - 60), id="expired"),
    pytest.param(session_token(email=None), id="no-email"),
    pytest.param(session_token(key=None, algorithm="none"), id="unsigned"),
    pytest.param("not-a-jwt", id="garbage"),
])
def test_auth_flask_login_rejects_invalid_tokens(flask_login_required, token):

    response = with_token(flask_login_required, token).get(TEST_FLASK_PATH)

    assert response.status_code == 302


def test_auth_flask_login_ignores_legacy_session_cookie():
    legacy = Flask('legacy')
    legacy.config.update(SECRET_KEY='test_secret')

    @legacy.route(TEST_FLASK_PATH)
    @auth.login_required
    def send_status():
        return ('OK!',200)

    client = legacy.test_client()
    with client.session_transaction() as session:
        session["user"] = {"email": TEST_EMAIL}

    assert client.get(TEST_FLASK_PATH).status_code == 302


def test_auth_unreachable_jwks_fails_instead_of_redirecting(flask_login_required, monkeypatch):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("down")
    monkeypatch.setattr(auth, "_signing_key", unreachable)

    response = with_token(flask_login_required, session_token()).get(TEST_FLASK_PATH)

    assert response.status_code == 500


def test_auth_key_removed_from_jwks_stops_verifying(flask_login_required, monkeypatch):
    monkeypatch.setattr(auth, "_signing_key", JWKS_SIGNING_KEY)
    monkeypatch.setattr(auth, "_jwks_clients", {})
    published = {"keys": [jwk(KEY, "k1")]}
    monkeypatch.setattr(auth._jwks_client(), "fetch_data", lambda: published)
    token = session_token(kid="k1")

    assert with_token(flask_login_required, token).get(TEST_FLASK_PATH).status_code == 200

    published["keys"] = [jwk(OTHER_KEY, "k2")]
    auth._jwks_client().jwk_set_cache.put(None)  # the JWKS lifespan has passed
    assert with_token(flask_login_required, token).get(TEST_FLASK_PATH).status_code == 302


def test_auth_valid_basic_survives_jwks_outage(flask_server, monkeypatch):
    def unreachable(token):
        raise jwt.PyJWKClientConnectionError("down")
    monkeypatch.setattr(auth, "_signing_key", unreachable)

    @flask_server.route(TEST_FLASK_PATH)
    @auth.login_or_basic_required
    def send_status():
        return ('OK!',200)

    client = with_token(flask_server.test_client(), session_token())
    basic = b64encode(f"{TEST_USER}:{TEST_PWD}".encode()).decode()
    response = client.get(TEST_FLASK_PATH, headers={'Authorization': f'Basic {basic}'})

    assert response.status_code == 200


def test_auth_jwks_url_follows_issuer():
    assert auth._jwks_client().uri == f"{ISSUER}/.well-known/jwks.json"


def test_auth_flask_basic_headers(flask_basic_required):

    response = flask_basic_required.get('/test')

    assert response.status_code == 401
    assert response.headers['WWW-Authenticate'] == 'Basic realm=""'


def test_auth_flask_basic_access(flask_basic_required):

    basic_auth_value = b64encode(f"{TEST_USER}:{TEST_PWD}".encode()).decode()
    response = flask_basic_required.get('/test', headers={'Authorization': f'Basic {basic_auth_value}'})

    assert response.status_code == 200


@pytest.fixture()
def dash_login_required(flask_server):

    dash = Dash(
        'my_dash',
        server = flask_server,
        url_base_pathname = TEST_DASH_PATH,
        compress = False
    )
    dash.layout = html.Div('Hello World!')
    dash = auth.register_dash(dash)

    @dash.server.route(TEST_DASH_BASIC_PATH)
    @auth.basic_required
    def send_status():
        return ('OK!',200)

    return flask_server.test_client()


def test_auth_dash_register_redirect(dash_login_required):

    response = dash_login_required.get(TEST_DASH_PATH)

    assert response.status_code == 302
    assert response.location == f"{AUTH_REDIRECT_URI}?next={quote('http://localhost/test/', safe='')}"


def test_auth_dash_register_access(dash_login_required):

    response = with_token(dash_login_required, session_token()).get(TEST_DASH_PATH)
    assert response.status_code == 200


def test_auth_dash_basic_admin_access(dash_login_required):

    basic_auth_value = b64encode(f"{TEST_USER}:{TEST_PWD}".encode()).decode()
    response = dash_login_required.get(TEST_DASH_BASIC_PATH, headers={'Authorization': f'Basic {basic_auth_value}'})
    assert response.status_code == 200


def test_auth_dash_basic_admin_redirect(dash_login_required):

    response = dash_login_required.get(TEST_DASH_BASIC_PATH)
    assert response.status_code == 302
