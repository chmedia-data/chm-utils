import pytest
from unittest.mock import patch

def test_import_error():

    with patch.dict('sys.modules', {'snowflake.connector': None}):
        error = None
        try:
            from chm_utils.clients import Snowflake
            s = Snowflake()
            pytest.fail('no exception thrown!')
        except Exception as e:
            error = e
        
        assert isinstance(error,ImportError)
        assert 'not installed' in str(error)