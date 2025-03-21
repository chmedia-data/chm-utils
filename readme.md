# CHM Utils

A custom python package with common utilities.
```
pip install git+https://github.com/chmedia-data/chm-utils
```

To split python dependencies into different groups, one can install dependency groups separately: `pip install "chm_utils[auth,snowflake] git+https://github.com/chmedia-data/chm-utils"`

## Testing
One can execute `pytest` in a local environment or use `just test` for dockerized tests.

## Features
### Serverless Environment Resolution
With CLI:
```bash
chm_utils sls.get_env --sls_env_path functions.myfunction.environment
# or before script exec
export `chm_utils sls.get_env --sls_env_path functions.myfunction.environment` && python main.py
```

In python:
```python
from chm_utils import sls
sls.set_env(env_path='functions.myfunction.environment')
```

## Clients
### Snowflake
A small snowflake wrapper using common environment variables as connection settings and frequently used SQL to pandas DataFrame helper function `get_query_df`:

```python
from chm_utils.clients import Snowflake
snowflake = Snowflake()
df = snowflake.get_query_df("select * from some_table limit 10")
```

To make sure optional dependencies are installed use: `pip install "chm_utils[snowfalke] git+https://github.com/chmedia-data/chm-utils"`

Following environment vars will be considered:
- SNOWFLAKE_ACCOUNT
- SNOWFLAKE_USER
- SNOWFLAKE_PRIVATE_KEY
- SNOWFLAKE_PRIVATE_KEY_PWD
- SNOWFLAKE_ROLE
- SNOWFLAKE_WAREHOUSE


## Extensions

### Auth
With the `auth` extension, one can use either [basic](https://developer.mozilla.org/en-US/docs/Web/HTTP/Authentication) or [cookie](https://flask.palletsprojects.com/en/stable/quickstart/#sessions) based authentication methods for various web interfaces.

#### Basic
For basic authentication to work, one has to set `AUTH_BASIC_USER` and `AUTH_BASIC_PWD`. Then one can use our custom decorator to protect routes

```python
from flask import Flask
from chm_utils.ext import auth

flask = Flask(__name__)

@flask.route('/',methods=['GET'])
@auth.basic_required
def send_response():
    return 'Ok!'
```

#### Cookie
To be able to use cookie based authentication with centralised auth routes, one has to use the same `SESSION_COOKIE_NAME` and `SESSION_SECRET_KEY` across services (see [chm-auth](https://github.com/chmedia-data/chm-auth)). When those environment variables are set, flask can authenticate a user by it's cookie and redirect towards `AUTH_REDIRECT_URI` when a user isn't yet logged in.
```python
from flask import Flask
from chm_utils.ext import auth

flask = Flask(__name__)

@flask.route('/')
@auth.login_required
def send_response():
    return 'Ok!'
```

With dash one can register an instance like this:
```python
from dash import Dash
from chm_utils.ext import auth

dash = Dash(__name__)
dash = auth.register_dash(dash)
```