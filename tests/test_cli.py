import os
from unittest.mock import patch
from chm_utils import cli


def test_get_env(capsys):

    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless_small.yml'
    os.environ['STAGE'] = 'test'
    os.environ['TEST_NOT_OVERWRITE'] = 'not_overwritten'

    with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep','functions.test_function.environment']):
        cli.main()

    assert capsys.readouterr().out.strip() == "TEST_OPT_VAR=test TEST_HARDCODED=hardcoded"