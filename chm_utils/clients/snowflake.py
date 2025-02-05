ARE_DEPS_AVAILABLE = True
try:
    import os
    from decimal import Decimal
    import snowflake.connector
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except ImportError:
    ARE_DEPS_AVAILABLE = False

from chm_utils import __logger__


class Snowflake:

    def __init__(self):

        self.db = None

        if not ARE_DEPS_AVAILABLE:
            raise ImportError("required packages are not available: `pip install chm_utils[snowflake]`")
        
        has_pw = not os.environ.get("SNOWFLAKE_PWD") is None
        has_pk = not os.environ.get("SNOWFLAKE_PRIVATE_KEY") is None
        if not has_pk and not has_pw:
            raise EnvironmentError("no snowflake credentials found in environment")
        
        __logger__.debug(f'init (has_pw: {has_pw}, pk: {has_pk})')


    def _db(self):

        if self.db:
            return self.db

        else:
            if os.environ.get('SNOWFLAKE_PWD'):
                __logger__.debug(f'connect with pw')
                self.db = snowflake.connector.connect(
                    account = os.environ.get("SNOWFLAKE_ACCOUNT"),
                    user = os.environ.get("SNOWFLAKE_USER"),
                    password = os.environ.get("SNOWFLAKE_PWD"),
                    role = os.environ.get("SNOWFLAKE_ROLE"),
                    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE"),
                    authenticator = os.environ.get("SNOWFLAKE_AUTHENTICATOR")
                )

            elif os.environ.get('SNOWFLAKE_PRIVATE_KEY'):
                __logger__.debug(f'snowflake connect with pk')
                private_key_pwd = os.environ.get('SNOWFLAKE_PRIVATE_KEY_PWD')
                self.db = snowflake.connector.connect(
                    account = os.environ.get("SNOWFLAKE_ACCOUNT"),
                    user = os.environ.get("SNOWFLAKE_USER"),
                    private_key = load_pem_private_key(
                        os.environ['SNOWFLAKE_PRIVATE_KEY'].encode(), 
                        password = private_key_pwd.encode() if private_key_pwd else None
                    ),
                    role = os.environ.get("SNOWFLAKE_ROLE"),
                    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE")
                )
                
            else:
                raise Exception("no authorization variables found in environment")
        
        return self._db

    def _cursor(self):
        return self._db().cursor()

    def get_query_df(self,query,use_warehouse=None):

        cursor = self._cursor()

        if use_warehouse:
            cursor.execute(f"use warehouse {use_warehouse}")

        cursor.execute(query)
        df = cursor.fetch_pandas_all()
        df.columns = [i.lower() for i in df.columns]

        for col in df.columns:
            non_null_values = df.loc[~df[col].isnull(),col].values
            if len(non_null_values) > 0 and isinstance(non_null_values[0],Decimal):
                df[col] = df[col].astype(float)

        if use_warehouse:
            cursor.execute(f"use warehouse {os.environ.get('SNOWFLAKE_WAREHOUSE')}")

        cursor.close()

        return df
    
    def execute(self,query):
        cursor = self._cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return rows
        
    def close(self):
        if not self.db is None:
            self.db.close()
