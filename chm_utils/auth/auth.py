import os
from flask import request, session, current_app, redirect, Response
from functools import wraps


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authorised(methods=['login']):
            session["next"] = request.url
            return redirect(os.environ['AUTH_REDIRECT_URI'])
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
            session["next"]=request.url
            return redirect(os.environ['AUTH_REDIRECT_URI'])
        return f(*args, **kwargs)
    return decorated_function2


def register_dash(dash,**kwargs):
    @dash.server.before_request
    def dash_auth():
        url_prefix = dash.config.url_base_pathname
        if url_prefix and request.path.startswith(url_prefix):
            if not is_authorised(**kwargs):
                session["next"] = request.url
                return redirect(os.environ['AUTH_REDIRECT_URI'])
    return dash


def is_logged_in():
    return 'user' in session


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
    
    evals = []
    if 'login' in methods:
        evals.append(is_logged_in())
    if 'basic' in methods:
        evals.append(is_authorised_basic())

    return any(evals)
