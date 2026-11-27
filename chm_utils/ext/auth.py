import os
from functools import wraps
from urllib.parse import urlencode

import jwt
from flask import request, current_app, redirect, Response, g

SESSION_AUDIENCE = "chm-session"


def _issuer():
    return os.environ.get("AUTH_ISSUER", "https://auth.data.chmedia.ch").rstrip("/")


def _cookie_name():
    return os.environ.get("AUTH_TOKEN_COOKIE_NAME", "chmdtoken")


_jwks_clients = {}


def _jwks_client():
    url = f"{_issuer()}/.well-known/jwks.json"
    if url not in _jwks_clients:
        # cache_keys would pin each key for the process lifetime, past its removal from the JWKS.
        _jwks_clients[url] = jwt.PyJWKClient(url, cache_keys=False, lifespan=3600)
    return _jwks_clients[url]


def _signing_key(token):
    return _jwks_client().get_signing_key_from_jwt(token).key


def _verify(token):
    if not token:
        return None
    try:
        return jwt.decode(
            token,
            _signing_key(token),
            algorithms=["RS256"],
            audience=SESSION_AUDIENCE,
            issuer=_issuer(),
            options={"require": ["exp", "iat", "iss", "aud", "email"]},
        )
    except jwt.PyJWKClientConnectionError:
        # An unreachable JWKS must fail the request, not bounce the user into a login loop.
        raise
    except jwt.PyJWTError:
        return None


def current_user():
    """Claims of the verified chm-auth session token (email, name, ...), or None."""
    if "chm_auth_user" not in g:
        g.chm_auth_user = _verify(request.cookies.get(_cookie_name()))
    return g.chm_auth_user


def login_redirect():
    """Redirect to the chm-auth login, which returns to the current URL afterwards."""
    uri = os.environ["AUTH_REDIRECT_URI"]
    separator = "&" if "?" in uri else "?"
    return redirect(f"{uri}{separator}{urlencode({'next': request.url})}")


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authorised(methods=['login']):
            return login_redirect()
        return f(*args, **kwargs)
    return decorated_function


def basic_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.authorization:
            return Response(
                status=401,
                headers={'WWW-Authenticate': 'Basic realm=""'}
            )
        if not is_authorised(methods=['basic']):
            return Response('No authorized access',status=401)
        return f(*args, **kwargs)
    return decorated_function


def login_or_basic_required(f):
    @wraps(f)
    def decorated_function2(*args, **kwargs):
        if not is_authorised(methods=['basic','login']):
            return login_redirect()
        return f(*args, **kwargs)
    return decorated_function2


def register_dash(dash,**kwargs):
    @dash.server.before_request
    def dash_auth():
        url_prefix = dash.config.url_base_pathname
        if url_prefix and request.path.startswith(url_prefix):
            if not is_authorised(**kwargs):
                return login_redirect()
    return dash


def is_logged_in():
    return current_user() is not None


def is_authorised_basic():

    if not request.authorization:
        return False

    user_correct = request.authorization.username == os.environ.get('AUTH_BASIC_USER')
    pwd_correct = request.authorization.password == os.environ.get('AUTH_BASIC_PWD')

    return user_correct and pwd_correct


def is_authorised(methods=['login','basic']):

    is_debug = current_app.config.get('DEBUG',False)==True
    is_deactivated = os.environ.get('AUTH_DEACTIVATE','false').lower()=='true'
    if is_deactivated or is_debug:
        return True

    if 'basic' in methods and is_authorised_basic():
        return True
    return 'login' in methods and is_logged_in()
