import os, pytest, builtins, logging
import pandas as pd

from chm_utils.sls import resolve_ssm_params

os.environ['SNOWFLAKE_USER'] = 'recs'
os.environ['SNOWFLAKE_WAREHOUSE'] = 'compute_wh'
os.environ['SNOWFLAKE_ROLE'] = 'chm_developer'

ssm_params = [{
    'ssm_path': '/snowflake/chmd_account_id',
    'key': 'SNOWFLAKE_ACCOUNT'
},{
    'ssm_path': '/snowflake/recs_private_key',
    'key': 'SNOWFLAKE_PRIVATE_KEY'
}]

env = resolve_ssm_params(ssm_params)
for k,v in env.items():
    os.environ[k]=v


def test_query_df():

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


def test_missing_creds(caplog):
    caplog.set_level(logging.DEBUG)
    private_key = os.environ['SNOWFLAKE_PRIVATE_KEY']
    del os.environ['SNOWFLAKE_PRIVATE_KEY']

    assert os.environ.get('SNOWFLAKE_PRIVATE_KEY') is None
    
    error = None
    try:
        from chm_utils.clients import Snowflake
        snowflake = Snowflake()
        pytest.fail('no exception thrown')
    except EnvironmentError as e:
        error = e
    
    assert isinstance(error,EnvironmentError)
    assert 'credentials' in str(error)
    
    os.environ['SNOWFLAKE_PRIVATE_KEY'] = private_key
    