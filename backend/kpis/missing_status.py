from kpis.base import BaseKPI
from db import execute_query

class MissingStatusKPI(BaseKPI):
    def fetch(self, month, year):
        sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
;WITH
LastAllocated AS (
    SELECT h.OrderID, h.AssignedTo_UserID, h.Date_Ctreated AS AllocatedDate,
        ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
    FROM Table_OrderStatushistory h
    WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND h.Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
),
LastAlloc AS (SELECT OrderID, AssignedTo_UserID, AllocatedDate FROM LastAllocated WHERE rn=1),
WorkingDays AS (
    SELECT CAST(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)) AS DATE) AS WorkDay
    FROM (SELECT TOP 31 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
          FROM master..spt_values) nums
    WHERE MONTH(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))=@Month
      AND DATEPART(WEEKDAY,DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))<>1
),
TotalWD AS (SELECT COUNT(*) AS cnt FROM WorkingDays),
ActiveEmps AS (
    SELECT DISTINCT la.AssignedTo_UserID AS AdminID
    FROM LastAlloc la
    INNER JOIN OrderDetails od ON od.ID=la.OrderID
    INNER JOIN Admin af ON af.ID_Admin=la.AssignedTo_UserID
                       AND af.Flag_Active=1 AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
    WHERE od.Flag_Deleted=0
),
UpdateDays AS (
    SELECT h.AssignedTo_UserID AS AdminID,
        COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysWithUpdate
    FROM Table_OrderStatushistory h
    WHERE h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND MONTH(h.Date_Ctreated)=@Month AND YEAR(h.Date_Ctreated)=@Year
    GROUP BY h.AssignedTo_UserID
)
SELECT ae.AdminID, a.Admin_FirstName+' '+a.Admin_LastName AS EmployeeName,
    tw.cnt AS WorkingDaysInMonth,
    ISNULL(ud.DaysWithUpdate,0) AS DaysWithUpdate,
    tw.cnt - ISNULL(ud.DaysWithUpdate,0) AS MissedDays
FROM ActiveEmps ae
CROSS JOIN TotalWD tw
LEFT  JOIN UpdateDays ud ON ud.AdminID=ae.AdminID
INNER JOIN Admin a       ON a.ID_Admin=ae.AdminID
              AND a.Flag_Active=1 AND (a.Flag_Delete=0 OR a.Flag_Delete IS NULL)
ORDER BY EmployeeName"""
        return execute_query(sql)

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
        row   = rows[0]
        wdays = row.get('WorkingDaysInMonth',0)
        upd   = row.get('DaysWithUpdate',0)
        miss  = row.get('MissedDays',0)
        ratio = round(upd/wdays*100,2) if wdays else None
        return {'numerator':upd,'denominator':wdays,'success_ratio':ratio,
                'orders':[{'TotalActiveDays':wdays,'DaysWithUpdate':upd,'MissedDays':miss}]}

# from kpis.base import BaseKPI
# from db import execute_query

# class MissingStatusKPI(BaseKPI):
#     def fetch(self, month, year):
#         sql = f"""
# DECLARE @Month INT={month}
# DECLARE @Year  INT={year}
# ;WITH
# LastAllocated AS (
#     SELECT h.OrderID, h.AssignedTo_UserID, h.Date_Ctreated AS AllocatedDate,
#         ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
#     FROM Table_OrderStatushistory h
#     WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
#       AND h.Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
# ),
# LastAlloc AS (SELECT OrderID, AssignedTo_UserID, AllocatedDate FROM LastAllocated WHERE rn=1),
# WorkingDays AS (
#     SELECT CAST(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)) AS DATE) AS WorkDay
#     FROM (SELECT TOP 31 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
#           FROM master..spt_values) nums
#     WHERE MONTH(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))=@Month
#       AND DATEPART(WEEKDAY,DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))<>1
# ),
# TotalWD AS (SELECT COUNT(*) AS cnt FROM WorkingDays),
# ActiveEmps AS (
#     SELECT DISTINCT la.AssignedTo_UserID AS AdminID
#     FROM LastAlloc la INNER JOIN OrderDetails od ON od.ID=la.OrderID WHERE od.Flag_Deleted=0
# ),
# UpdateDays AS (
#     SELECT h.AssignedTo_UserID AS AdminID,
#         COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysWithUpdate
#     FROM Table_OrderStatushistory h
#     WHERE h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
#       AND MONTH(h.Date_Ctreated)=@Month AND YEAR(h.Date_Ctreated)=@Year
#     GROUP BY h.AssignedTo_UserID
# )
# SELECT ae.AdminID, a.Admin_FirstName+' '+a.Admin_LastName AS EmployeeName,
#     tw.cnt AS WorkingDaysInMonth,
#     ISNULL(ud.DaysWithUpdate,0) AS DaysWithUpdate,
#     tw.cnt - ISNULL(ud.DaysWithUpdate,0) AS MissedDays
# FROM ActiveEmps ae
# CROSS JOIN TotalWD tw
# LEFT  JOIN UpdateDays ud ON ud.AdminID=ae.AdminID
# INNER JOIN Admin a       ON a.ID_Admin=ae.AdminID
# ORDER BY EmployeeName"""
#         return execute_query(sql)

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
#         row   = rows[0]
#         wdays = row.get('WorkingDaysInMonth',0)
#         upd   = row.get('DaysWithUpdate',0)
#         miss  = row.get('MissedDays',0)
#         ratio = round(upd/wdays*100,2) if wdays else None
#         return {'numerator':upd,'denominator':wdays,'success_ratio':ratio,
#                 'orders':[{'TotalActiveDays':wdays,'DaysWithUpdate':upd,'MissedDays':miss}]}
