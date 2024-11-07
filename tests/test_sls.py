import os, pytest
from chm_utils import sls


def test_set_env():

    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless.yml'
    os.environ['SLS_ENV_PATH'] = 'functions.test_function.environment'
    os.environ['STAGE'] = 'test'
    sls.set_env()

    expectations = [{
        'key': 'TEST_REMOTE_VAR',
        'value': 'remote_param'
    },{
        'key': 'TEST_OPT_VAR',
        'value': 'test'
    },{
        'key': 'TEST_CONFIG_VAR',
        'value': 'config_value'
    },{
        'key': 'TEST_HARDCODED_VAR',
        'value': 'hardcoded'
    }]

    failed_keys = []
    for i in expectations:
        if not os.environ[i['key']] == i['value']:
            failed_keys.append(i['key'])
        
    if len(failed_keys) > 0:
        pytest.fail("")


    