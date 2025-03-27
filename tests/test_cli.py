import os
import tempfile
from unittest.mock import patch, MagicMock
from chm_utils import cli
from chm_utils import sls


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


def test_get_ssm_params(capsys):
    mock_params = {'DB_PASSWORD': 'password123', 'API_KEY': 'key456'}
    
    with patch('chm_utils.sls.get_ssm_params', return_value=mock_params):
        with patch('sys.argv', ['cli.py', 'sls.get_env', '-ssm', '/app/production/DB_PASSWORD', '/app/production/API_KEY']):
            cli.main()
    
    output = capsys.readouterr().out.strip()
    assert "export DB_PASSWORD=password123" in output
    assert "export API_KEY=key456" in output


def test_get_both_sls_and_ssm_params(capsys):
    sls_params = {'TEST_OPT_VAR': 'test', 'TEST_HARDCODED': 'hardcoded'}
    ssm_params = {'DB_PASSWORD': 'password123'}
    
    with patch('chm_utils.sls.get_env', return_value=sls_params):
        with patch('chm_utils.sls.get_ssm_params', return_value=ssm_params):
            with patch('sys.argv', ['cli.py', 'sls.get_env', '-sep', 'functions.test_function.environment', 
                                    '-ssm', '/app/production/DB_PASSWORD']):
                cli.main()
    
    output = capsys.readouterr().out.strip()
    assert "export TEST_OPT_VAR=test" in output
    assert "export TEST_HARDCODED=hardcoded" in output
    assert "export DB_PASSWORD=password123" in output
