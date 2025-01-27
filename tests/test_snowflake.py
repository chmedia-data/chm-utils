import os, pytest
import pandas as pd
from chm_utils.ext import snowflake as sf
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


@pytest.fixture()
def snowflake():
    yield sf.Snowflake()


def test_query_df(snowflake):

    try:
        snowflake.execute("drop table chmedia.public.chm_utils_test")
    except:
        pass
    
    snowflake.execute("create table chmedia.public.chm_utils_test (id string, ts timestamp_ntz, val int)")
    snowflake.execute("insert into chmedia.public.chm_utils_test (id, ts, val) values ('a',current_timestamp(),1),('b',current_timestamp(),2)")
    df = snowflake.get_query_df("select * from chmedia.public.chm_utils_test")
    assert len(df) == 2
    assert isinstance(df, pd.DataFrame)
    snowflake.execute("drop table chmedia.public.chm_utils_test")