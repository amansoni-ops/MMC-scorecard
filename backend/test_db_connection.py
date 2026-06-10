"""
Run this to diagnose your SQL Server connection.
cd backend
python test_db_connection.py
"""
import pyodbc

SERVER   = r'3.226.227.21,1433\SQLEXPRESS2016'
DATABASE = 'mmcconvert_Data'
USER     = 'mmc_user'
PASSWORD = 'Mmc@123456'

print('=' * 60)
print('STEP 1: Available ODBC Drivers on this machine')
print('=' * 60)
drivers = pyodbc.drivers()
for d in drivers:
    print(f'  {d}')

sql_drivers = [d for d in drivers if 'SQL Server' in d]
print(f'\nSQL Server drivers found: {sql_drivers}')

print('\n' + '=' * 60)
print('STEP 2: Trying each driver...')
print('=' * 60)

for driver in sql_drivers:
    conn_str = (
        f'DRIVER={{{driver}}};'
        f'SERVER={SERVER};'
        f'DATABASE={DATABASE};'
        f'UID={USER};'
        f'PWD={PASSWORD};'
        f'TrustServerCertificate=yes;'
        f'Encrypt=no;'
        f'Connection Timeout=30;'
    )
    print(f'\nTrying: {driver}')
    try:
        conn = pyodbc.connect(conn_str, timeout=30)
        conn.execute('SET ARITHABORT ON')
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION AS ver")
        row = cursor.fetchone()
        print(f'  ✅ SUCCESS! SQL Server version: {row[0][:60]}')
        conn.close()
    except Exception as e:
        print(f'  ❌ FAILED: {e}')

print('\n' + '=' * 60)
print('STEP 3: Test with "SQL Server" native driver (always available)')
print('=' * 60)
conn_str = (
    f'DRIVER={{SQL Server}};'
    f'SERVER={SERVER};'
    f'DATABASE={DATABASE};'
    f'UID={USER};'
    f'PWD={PASSWORD};'
    f'Connection Timeout=30;'
)
try:
    conn = pyodbc.connect(conn_str, timeout=30)
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    print('✅ Native SQL Server driver works!')
    conn.close()
except Exception as e:
    print(f'❌ FAILED: {e}')