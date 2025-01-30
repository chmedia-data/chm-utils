has_required_packages = True
try:
    import os
    from decimal import Decimal
    import snowflake.connector
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
except ImportError:
    has_required_packages = False


class Snowflake:

    def __init__(self):

        if not has_required_packages:
            raise ImportError("required packages are not installed: `pip install chm_utils[snowflake]`")
        
        credentials = os.environ.get("SNOWFLAKE_PWD") or os.environ.get('SNOWFLAKE_PRIVATE_KEY')
        if credentials is None or len(credentials)==0:
            raise EnvironmentError("no snowflake credentials found in environment")

        self.db = None

    def _connect(self):

        if self.db is None:
            if os.environ.get('SNOWFLAKE_PWD'):
                self.db = snowflake.connector.connect(
                    account = os.environ.get("SNOWFLAKE_ACCOUNT"),
                    user = os.environ.get("SNOWFLAKE_USER"),
                    pwd = os.environ.get("SNOWFLAKE_PWD"),
                    role = os.environ.get("SNOWFLAKE_ROLE"),
                    warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE")
                )

            elif os.environ.get('SNOWFLAKE_PRIVATE_KEY'):
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

    def _get_cursor(self):
        self._connect()
        return self.db.cursor()

    def get_query_df(self,query,use_warehouse=None):

        cursor = self._get_cursor()

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
        cursor = self._get_cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return rows
        
    def close(self):
        if not self.db is None:
            self.db.close()
