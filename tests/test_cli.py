import os
from unittest.mock import patch
from chm_utils import cli


def test_get_env(capsys):

    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless_small.yml'
    os.environ['STAGE'] = 'test'
    os.environ['TEST_NOT_OVERWRITE'] = 'not_overwritten'

    with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep','functions.test_function.environment']):
        cli.main()

    sysout = capsys.readouterr().out.strip()
    assert sysout == "TEST_OPT_VAR=test TEST_HARDCODED=hardcoded TEST_SPECIAL_CHARS='---- rsa begin ----\nasdfasdfasdf\n---- rsa end ----\n'"
    assert capsys.readouterr().out.strip() == "TEST_OPT_VAR=test TEST_HARDCODED=hardcoded"


def test_version(capsys):

    with patch('sys.argv', ['cli.py', 'version']):
        cli.main()
    
    assert "version" in capsys.readouterr().out.strip()
