"""
SQL Server connection — READ ONLY access to mmcconvert_Data.
Auto-detects the best available ODBC driver on the machine.
Always sets ARITHABORT ON (required for SQL Server 2016 query optimizer).
"""
import pyodbc
from config import SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD

def _best_driver() -> str:
    available = pyodbc.drivers()
    preference = [
        'ODBC Driver 18 for SQL Server',
        'ODBC Driver 17 for SQL Server',
        'ODBC Driver 13 for SQL Server',
        'ODBC Driver 11 for SQL Server',
        'SQL Server Native Client 11.0',
        'SQL Server Native Client 10.0',
        'SQL Server',
    ]
    for drv in preference:
        if drv in available:
            print(f'[DB] Using driver: {drv}')
            return drv
    sql_drivers = [d for d in available if 'SQL' in d]
    if sql_drivers:
        print(f'[DB] Fallback driver: {sql_drivers[0]}')
        return sql_drivers[0]
    raise RuntimeError(
        f'No SQL Server ODBC driver found. Available: {available}\n'
        f'Download: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server'
    )

_DRIVER = _best_driver()

def get_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        f"TrustServerCertificate=yes;"
        f"Encrypt=no;"
    )
    conn = pyodbc.connect(conn_str, timeout=300)
    conn.execute('SET ARITHABORT ON')
    return conn

def execute_query(sql: str, params=None) -> list[dict]:
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params or [])
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()