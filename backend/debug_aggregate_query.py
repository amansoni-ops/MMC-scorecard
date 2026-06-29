"""
debug_aggregate_query.py
============================
Runs the EXACT aggregate SQL from missing_status.py directly via pyodbc,
with full traceback visible, to see the real underlying SQL Server error
that execute_query() is currently masking.
"""
import sys
sys.path.insert(0, '.')
import traceback
from db import get_connection

month, year = 5, 2026

sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
;WITH
LastAllocated AS (
    SELECT h.OrderID, h.AssignedTo_UserID,
        ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
    FROM Table_OrderStatushistory h
    WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND h.Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
),
LastAlloc AS (SELECT OrderID, AssignedTo_UserID FROM LastAllocated WHERE rn=1),
ResolvedAttribution AS (
    SELECT
        od.ID AS OrderID,
        COALESCE(m.PickedUpBy, la.AssignedTo_UserID, m.Summary_AssignUserID) AS AdminID
    FROM OrderDetails od
    LEFT JOIN Table_OrderDetailsMisc m ON m.OrderID = od.ID
    LEFT JOIN LastAlloc la             ON la.OrderID = od.ID
    WHERE od.Flag_Deleted = 0
      AND MONTH(od.CompletionOn) = @Month
      AND YEAR(od.CompletionOn)  = @Year
),
WorkingDays AS (
    SELECT CAST(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)) AS DATE) AS WorkDay
    FROM (SELECT TOP 31 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
          FROM master..spt_values) nums
    WHERE MONTH(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))=@Month
      AND DATEPART(WEEKDAY,DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))<>1
),
TotalWD AS (SELECT COUNT(*) AS cnt FROM WorkingDays),
ActiveEmps AS (
    SELECT DISTINCT ra.AdminID
    FROM ResolvedAttribution ra
    INNER JOIN Admin af ON af.ID_Admin=ra.AdminID
                       AND af.Flag_Active=1 AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
    WHERE ra.AdminID IS NOT NULL
),
UpdateDays AS (
    SELECT ra.AdminID,
        COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysWithUpdate
    FROM Table_OrderStatushistory h
    INNER JOIN ResolvedAttribution ra ON ra.OrderID = h.OrderID
    WHERE h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND MONTH(h.Date_Ctreated)=@Month AND YEAR(h.Date_Ctreated)=@Year
      AND ra.AdminID IS NOT NULL
    GROUP BY ra.AdminID
)
SELECT ae.AdminID, a.Admin_FirstName+' '+a.Admin_LastName AS EmployeeName,
    tw.cnt AS WorkingDaysInMonth,
    ISNULL(ud.DaysWithUpdate,0) AS DaysWithUpdate,
    tw.cnt - ISNULL(ud.DaysWithUpdate,0) AS MissedDays
FROM ActiveEmps ae
CROSS JOIN TotalWD tw
LEFT  JOIN UpdateDays ud ON ud.AdminID=ae.AdminID
INNER JOIN Admin a ON a.ID_Admin=ae.AdminID
    AND a.Flag_Active=1 AND (a.Flag_Delete=0 OR a.Flag_Delete IS NULL)
ORDER BY EmployeeName
"""

print("Connecting...")
conn = get_connection()
cur = conn.cursor()
print("Executing query directly (no wrapper)...")
try:
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"SUCCESS: {len(rows)} rows")
    for r in rows[:5]:
        print(r)
except Exception as e:
    print("REAL ERROR:")
    print(type(e))
    print(str(e))
    traceback.print_exc()
finally:
    conn.close()