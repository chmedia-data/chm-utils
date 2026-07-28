import os, pytest
import pandas as pd

from chm_utils.sls import resolve_ssm_params

snowflake_params = {
    'SNOWFLAKE_WAREHOUSE': 'compute_wh',
    'SNOWFLAKE_ROLE': 'chm_developer',
    'SNOWFLAKE_AUTHENTICATOR': 'username_password_mfa'
}
# a key-based local setup has no password in the environment, so pick these up
# optionally and skip the password test instead of failing collection
for key in ('SNOWFLAKE_PWD','SNOWFLAKE_USER'):
    if os.environ.get(key):
        snowflake_params[key] = os.environ[key]
ssm_params = [{
    'ssm_path': '/snowflake/chmd_account_id',
    'key': 'SNOWFLAKE_ACCOUNT'
},{
    'ssm_path': '/snowflake/recs_private_key',
    'key': 'SNOWFLAKE_PRIVATE_KEY'
}]
snowflake_params.update(resolve_ssm_params(ssm_params))


def clean_snowflake_env():
    for k in os.environ.keys():
        if k.startswith('SNOWFLAKE_'):
            del os.environ[k]

def set_snowflake_env(filter=""):
    for k,v in snowflake_params.items():
        if k != filter:
            os.environ[k]=v

def get_snowflake_env():
    return {k:v for k,v in os.environ.items() if k.startswith('SNOWFLAKE_')}


@pytest.fixture
def snowflake_env_pk():
    clean_snowflake_env()
    set_snowflake_env(filter='SNOWFLAKE_PWD')
    os.environ['SNOWFLAKE_USER'] = 'recs'


@pytest.fixture
def snowflake_env_pw():
    clean_snowflake_env()
    set_snowflake_env(filter='SNOWFLAKE_PRIVATE_KEY')


@pytest.fixture
def snowflake_env_missing():
    clean_snowflake_env()


def test_client_methods(snowflake_env_pk):

    assert 'SNOWFLAKE_PRIVATE_KEY' in get_snowflake_env()
    
    try:
        from chm_utils.clients import Snowflake
        snowflake = Snowflake()
        snowflake.execute("drop table chmedia.public.chm_utils_test")
    except:
        pass
    
    snowflake.execute("create table chmedia.public.chm_utils_test (id string, ts timestamp_ntz, val int)")
    snowflake.execute("insert into chmedia.public.chm_utils_test (id, ts, val) values ('a',current_timestamp(),1),('b',current_timestamp(),2)")
    df = snowflake.get_query_df("select * from chmedia.public.chm_utils_test")
    assert len(df) == 2
    assert isinstance(df, pd.DataFrame)
    snowflake.execute("drop table chmedia.public.chm_utils_test")


def test_pw_mfa_credential(snowflake_env_pw):

    if os.environ.get('SKIP_PW_MFA_CREDENTIAL_TEST','').lower()=='true':
        return

    if 'SNOWFLAKE_PWD' not in snowflake_params:
        pytest.skip('no SNOWFLAKE_PWD in environment')

    assert 'SNOWFLAKE_PWD' in get_snowflake_env()
    from chm_utils.clients import Snowflake
    snowflake = Snowflake()
    snowflake.execute('select current_date')


def test_pk_path_credential(snowflake_env_pk, tmp_path):

    key_path = tmp_path / 'private_key.pem'
    key_path.write_text(os.environ.pop('SNOWFLAKE_PRIVATE_KEY'))
    os.environ['SNOWFLAKE_PRIVATE_KEY_PATH'] = str(key_path)

    from chm_utils.clients import Snowflake
    snowflake = Snowflake()
    snowflake.execute('select current_date')


def test_empty_pk_path_credential(snowflake_env_missing):

    os.environ['SNOWFLAKE_PRIVATE_KEY_PATH'] = ''

    error = None
    try:
        from chm_utils.clients import Snowflake
        Snowflake()
        pytest.fail('no exception thrown')
    except EnvironmentError as e:
        error = e

    assert isinstance(error,EnvironmentError)
    assert 'credentials' in str(error)


def test_missing_credential(snowflake_env_missing):

    assert os.environ.get('SNOWFLAKE_PRIVATE_KEY') is None
    assert os.environ.get('SNOWFLAKE_PWD') is None
    
    error = None
    try:
        from chm_utils.clients import Snowflake
        snowflake = Snowflake()
        pytest.fail('no exception thrown')
    except EnvironmentError as e:
        error = e
    
    assert isinstance(error,EnvironmentError)
    assert 'credentials' in str(error)
    