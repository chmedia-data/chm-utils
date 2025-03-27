import os
import tempfile
from unittest.mock import patch
from chm_utils import cli


def test_get_env(capsys):

    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless_small.yml'
    os.environ['STAGE'] = 'test'
    os.environ['TEST_NOT_OVERWRITE'] = 'not_overwritten'

    with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep','functions.test_function.environment']):
        cli.main()

    output = capsys.readouterr().out.strip()
    assert "export TEST_OPT_VAR=test" in output
    assert "export TEST_HARDCODED=hardcoded" in output
    assert "export TEST_SPECIAL_CHARS='---- rsa begin ----\nasdfasdfasdf\n---- rsa end ----\n'" in output


def test_get_env_to_file():
    os.environ['SLS_CONFIG_PATH'] = 'tests/fixtures/serverless_small.yml'
    os.environ['STAGE'] = 'test'
    os.environ['TEST_NOT_OVERWRITE'] = 'not_overwritten'

    with tempfile.NamedTemporaryFile(mode='w+') as temp_file:
        with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep', 'functions.test_function.environment', 
                                '-of', temp_file.name]):
            cli.main()
        
        temp_file.seek(0)
        content = temp_file.read()
        assert "export TEST_OPT_VAR=test" in content
        assert "export TEST_HARDCODED=hardcoded" in content
        assert "export TEST_SPECIAL_CHARS='---- rsa begin ----\nasdfasdfasdf\n---- rsa end ----\n'" in content


def test_version(capsys):

    with patch('sys.argv', ['cli.py', 'version']):
        cli.main()
    
    assert "version" in capsys.readouterr().out.strip()
