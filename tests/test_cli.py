import os
from unittest.mock import patch
from chm_utils import cli


def test_get_env(capsys):

    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless.yml'
    os.environ['STAGE'] = 'test'

    with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep','functions.test_function.environment']):
        cli.main()

    assert capsys.readouterr().out.strip() == "TEST_OPT_VAR=test TEST_CONFIG_VAR=config_value TEST_CONFIG_VAR_WITH_SUFFIX=config_value/with_suffix TEST_HARDCODED_VAR=hardcoded TEST_REMOTE_VAR=remote_param"