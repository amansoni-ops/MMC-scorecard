"""
Run this AFTER replacing the 4 backend files.
cd backend && python clear_and_fix.py
"""
import sqlite3, os, sys

DB = os.path.join(os.path.dirname(__file__), 'scorecard.db')

print("="*50)
print("1. Clearing score cache...")
with sqlite3.connect(DB) as c:
    c.execute("DELETE FROM score_cache")
print("   Done.")

print("2. Verifying SQL Server connection...")
try:
    from db import execute_query
    r = execute_query("SELECT COUNT(*) AS cnt FROM Admin WHERE Flag_Active=1 AND Flag_Delete=0")
    print(f"   OK — {r[0]['cnt']} active employees")
except Exception as e:
    print(f"   ERROR: {e}"); sys.exit(1)

print("3. Checking for duplicates in missing_status query...")
try:
    from db import execute_query
    import datetime
    now = datetime.datetime.now()
    rows = execute_query(f"""
        SELECT a.Admin_FirstName+' '+a.Admin_LastName AS Name, COUNT(*) AS cnt
        FROM (
            SELECT DISTINCT h.AssignedTo_UserID AS AdminID
            FROM Table_OrderStatushistory h
            INNER JOIN Admin a2 ON a2.ID_Admin=h.AssignedTo_UserID
                AND a2.Flag_Active=1 AND (a2.Flag_Delete=0 OR a2.Flag_Delete IS NULL)
            WHERE h.StatusID=11
              AND MONTH(h.Date_Ctreated)={now.month}
              AND YEAR(h.Date_Ctreated)={now.year}
        ) ids
        INNER JOIN Admin a ON a.ID_Admin=ids.AdminID
        GROUP BY a.Admin_FirstName, a.Admin_LastName
        HAVING COUNT(*) > 1
    """)
    if rows:
        print(f"   Found {len(rows)} duplicate names:")
        for r in rows: print(f"     - {r['Name']} ({r['cnt']} records)")
    else:
        print("   No duplicates found. SQL fix working correctly.")
except Exception as e:
    print(f"   Could not verify: {e}")

print("\n✅ Cache cleared. Restart Flask: python app.py")
print("="*50)