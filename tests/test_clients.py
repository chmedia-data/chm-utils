import pytest
from unittest.mock import patch


def test_valid_import():

    with patch.dict('sys.modules', {'snowflake.connector': None}):
        error = None
        try:
            from chm_utils.clients import Snowflake
        except Exception as e:
            error = e
        
    assert error is None


def test_import_error_at_init():

    with patch.dict('sys.modules', {'snowflake.connector': None}):
        error = None
        try:
            from chm_utils.clients import Snowflake
            s = Snowflake()
            pytest.fail('no exception thrown!')
        except Exception as e:
            error = e
        
        assert isinstance(error,ImportError)
        assert 'not available' in str(error)