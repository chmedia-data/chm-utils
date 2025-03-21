import os, pytest, json
from flask import Flask, session
from itsdangerous import base64_decode
from base64 import b64encode
from dash import Dash, html

from chm_utils.ext import auth

AUTH_REDIRECT_URI = "https://test_uri.com/auth/login"
SESSION_COOKIE_NAME = 'test_cookie'
SESSION_SECRET_KEY = 'test_secret'
TEST_USER = 'test_user'
TEST_PWD = 'test_pwd'
TEST_DASH_PATH = '/test/'
TEST_FLASK_PATH = '/test'
TEST_DASH_BASIC_PATH = '/test/admin'

os.environ['AUTH_REDIRECT_URI'] = AUTH_REDIRECT_URI
os.environ['AUTH_BASIC_USER'] = TEST_USER
os.environ['AUTH_BASIC_PWD'] = TEST_PWD


def get_cookie_data(response):
    set_cookie = response.headers['Set-Cookie']
    cookie_value = set_cookie.split('=')[1].split(';')[0]
    b64_data = cookie_value.split('.')[0]
    json_str = base64_decode(b64_data).decode()
    return json.loads(json_str)


@pytest.fixture()
def flask_server():
    flask = Flask('my_flask')
    flask.config.update(
        SESSION_COOKIE_NAME=SESSION_COOKIE_NAME,
        SECRET_KEY=SESSION_SECRET_KEY
    )
    yield flask


@pytest.fixture()
def flask_login_required(flask_server):

    @flask_server.route(TEST_FLASK_PATH,methods=['GET'])
    @auth.login_required
    def send_status():
        return ('OK!',200)
    
    return flask_server.test_client()


@pytest.fixture()
def flask_basic_required(flask_server):

    @flask_server.route(TEST_FLASK_PATH,methods=['GET'])
    @auth.basic_required
    def send_status():
        return ('OK!',200)
    
    return flask_server.test_client()


def test_auth_flask_login_redirect(flask_login_required):

    response = flask_login_required.get(TEST_FLASK_PATH)

    assert response.status_code == 302
    assert response.location == AUTH_REDIRECT_URI
    assert 'next' in get_cookie_data(response)


def test_auth_flask_login_access(flask_login_required):

    with flask_login_required.session_transaction() as session:
        session["user"] = TEST_USER

    response = flask_login_required.get(TEST_FLASK_PATH)

    assert response.status_code == 200


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
    assert response.location == AUTH_REDIRECT_URI
    assert 'next' in get_cookie_data(response)


def test_auth_dash_register_access(dash_login_required):

    with dash_login_required.session_transaction() as session:
        session["user"] = TEST_USER

    response = dash_login_required.get(TEST_DASH_PATH)
    assert response.status_code == 200


def test_auth_dash_basic_admin_access(dash_login_required):

    basic_auth_value = b64encode(f"{TEST_USER}:{TEST_PWD}".encode()).decode()
    response = dash_login_required.get(TEST_DASH_BASIC_PATH, headers={'Authorization': f'Basic {basic_auth_value}'})
    assert response.status_code == 200


def test_auth_dash_basic_admin_redirect(dash_login_required):

    response = dash_login_required.get(TEST_DASH_BASIC_PATH)
    assert response.status_code == 302
