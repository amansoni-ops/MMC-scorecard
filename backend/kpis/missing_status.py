from kpis.base import BaseKPI
from db import execute_query

class MissingStatusKPI(BaseKPI):
    def fetch(self, month, year):
        # ── Aggregate query — Option A scoring (days updated / working days) ──
        agg_sql = f"""
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
INNER JOIN Admin a ON a.ID_Admin=ae.AdminID
    AND a.Flag_Active=1 AND (a.Flag_Delete=0 OR a.Flag_Delete IS NULL)
ORDER BY EmployeeName"""

        try:
            agg_rows = execute_query(agg_sql)
        except Exception as e:
            print(f'[MissingStatus] Aggregate error: {e}')
            return []

        if not agg_rows:
            return []

        # ── Per-file query (display only) — same date logic as post_conversion ──
        file_sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
;WITH
LastAllocated AS (
    SELECT h.OrderID, h.AssignedTo_UserID,
        ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
    FROM Table_OrderStatushistory h
    WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
),
LastAlloc AS (SELECT OrderID, AssignedTo_UserID FROM LastAllocated WHERE rn=1),
FirstAllocDate AS (
    SELECT h.OrderID, h.AssignedTo_UserID,
        CAST(MIN(h.Date_Ctreated) AS DATE) AS FirstDate
    FROM Table_OrderStatushistory h
    WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
    GROUP BY h.OrderID, h.AssignedTo_UserID
),
WorkingDays AS (
    SELECT CAST(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)) AS DATE) AS WorkDay
    FROM (SELECT TOP 31 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
          FROM master..spt_values) nums
    WHERE MONTH(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))=@Month
      AND DATEPART(WEEKDAY,DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))<>1
),
FilesCompleted AS (
    SELECT
        la.AssignedTo_UserID                                              AS AdminID,
        od.ID                                                             AS OrderID,
        od.Order_Number                                                   AS OrderNumber,
        od.CompanyName,
        CAST(od.CompletionOn AS DATE)                                      AS CompletedDate,
        -- Fix: if FirstAllocDate > CompletedDate (data inconsistency), use month start
        CASE
            WHEN CAST(fad.FirstDate AS DATE) >= DATEFROMPARTS(@Year,@Month,1)
             AND CAST(fad.FirstDate AS DATE) <=
                 CAST(COALESCE(m.Retail_CompletionDate, od.CompletionOn) AS DATE)
            THEN CAST(fad.FirstDate AS DATE)
            ELSE DATEFROMPARTS(@Year,@Month,1)
        END                                                               AS ActiveFrom
    FROM OrderDetails od
    INNER JOIN LastAlloc      la  ON la.OrderID=od.ID
    LEFT  JOIN FirstAllocDate fad ON fad.OrderID=od.ID
                                 AND fad.AssignedTo_UserID=la.AssignedTo_UserID
    LEFT  JOIN Table_OrderDetailsMisc m ON m.OrderID=od.ID
    INNER JOIN Admin af ON af.ID_Admin=la.AssignedTo_UserID
                       AND af.Flag_Active=1
                       AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
    WHERE od.Flag_Deleted=0
      AND MONTH(od.CompletionOn)=@Month
      AND YEAR(od.CompletionOn) =@Year
),
FileActiveDays AS (
    SELECT
        fc.AdminID, fc.OrderID, fc.OrderNumber,
        fc.CompanyName, fc.CompletedDate, fc.ActiveFrom,
        COUNT(wd.WorkDay) AS ActiveWorkingDays
    FROM FilesCompleted fc
    INNER JOIN WorkingDays wd
           ON wd.WorkDay >= fc.ActiveFrom
          AND wd.WorkDay <= fc.CompletedDate
    GROUP BY fc.AdminID, fc.OrderID, fc.OrderNumber,
             fc.CompanyName, fc.CompletedDate, fc.ActiveFrom
),
FileUpdateDays AS (
    SELECT h.OrderID, h.AssignedTo_UserID AS AdminID,
        COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysUpdated
    FROM Table_OrderStatushistory h
    INNER JOIN WorkingDays wd ON CAST(h.Date_Ctreated AS DATE)=wd.WorkDay
    WHERE MONTH(h.Date_Ctreated)=@Month AND YEAR(h.Date_Ctreated)=@Year
      AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
    GROUP BY h.OrderID, h.AssignedTo_UserID
)
SELECT
    fad.AdminID,
    fad.OrderID,
    fad.OrderNumber,
    fad.CompanyName,
    fad.CompletedDate,
    fad.ActiveFrom,
    fad.ActiveWorkingDays                                AS ActiveDays,
    ISNULL(fud.DaysUpdated, 0)                           AS DaysUpdated,
    fad.ActiveWorkingDays - ISNULL(fud.DaysUpdated, 0)  AS DaysMissed
FROM FileActiveDays fad
LEFT JOIN FileUpdateDays fud
       ON fud.OrderID=fad.OrderID AND fud.AdminID=fad.AdminID
ORDER BY fad.AdminID, fad.CompletedDate"""

        file_rows = []
        try:
            file_rows = execute_query(file_sql)
            print(f'[MissingStatus] Per-file: {len(file_rows)} rows')
        except Exception as e:
            print(f'[MissingStatus] Per-file failed (non-critical): {e}')

        from collections import defaultdict
        files_by_admin = defaultdict(list)
        for fr in file_rows:
            files_by_admin[fr['AdminID']].append(fr)

        for row in agg_rows:
            row['FileBreakdown'] = files_by_admin.get(row['AdminID'], [])

        return agg_rows

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}

        row   = rows[0]
        wdays = row.get('WorkingDaysInMonth', 0)
        upd   = row.get('DaysWithUpdate', 0)
        miss  = row.get('MissedDays', 0)
        # ── Option A scoring: days updated / working days in month ──────────
        ratio = round(upd/wdays*100, 2) if wdays else None

        # Per-file display data
        file_breakdown = []
        file_orders    = []

        for fb in row.get('FileBreakdown', []):
            days_updated  = fb.get('DaysUpdated', 0)
            active_days   = fb.get('ActiveDays', 0)
            days_missed   = fb.get('DaysMissed', 0)

            file_breakdown.append({
                'order_id':     fb.get('OrderID'),
                'order_number': fb.get('OrderNumber', '—'),
                'company':      fb.get('CompanyName', '—'),
                'completed':    str(fb.get('CompletedDate', '—')),
                'active_from':  str(fb.get('ActiveFrom', '—')),
                'active_days':  active_days,
                'days_updated': days_updated,
                'days_missed':  days_missed,
            })

            # For fileMap linking in EmployeeDetail
            file_orders.append({
                'order_id':       fb.get('OrderID'),
                'order_number':   fb.get('OrderNumber', '—'),
                'company':        fb.get('CompanyName', '—'),
                'completed':      str(fb.get('CompletedDate', '—')),
                'DaysUpdated':    days_updated,
                'ActiveDays':     active_days,
                'DaysMissed':     days_missed,
                '_is_file_entry': True,
            })

        primary = {
            'TotalActiveDays': wdays,
            'working_days':    wdays,
            'DaysWithUpdate':  upd,
            'MissedDays':      miss,
            'file_breakdown':  file_breakdown,
        }

        return {
            'numerator':     upd,
            'denominator':   wdays,
            'success_ratio': ratio,
            'orders':        [primary] + file_orders,
        }

# from kpis.base import BaseKPI
# from db import execute_query

# class MissingStatusKPI(BaseKPI):
#     def fetch(self, month, year):
#         # ── Aggregate query — Option A scoring (days updated / working days) ──
#         agg_sql = f"""
# DECLARE @Month INT={month}
# DECLARE @Year  INT={year}
# ;WITH
# LastAllocated AS (
#     SELECT h.OrderID, h.AssignedTo_UserID,
#         ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
#     FROM Table_OrderStatushistory h
#     WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
#       AND h.Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
# ),
# LastAlloc AS (SELECT OrderID, AssignedTo_UserID FROM LastAllocated WHERE rn=1),
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
#     FROM LastAlloc la
#     INNER JOIN OrderDetails od ON od.ID=la.OrderID
#     INNER JOIN Admin af ON af.ID_Admin=la.AssignedTo_UserID
#                        AND af.Flag_Active=1 AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
#     WHERE od.Flag_Deleted=0
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
# INNER JOIN Admin a ON a.ID_Admin=ae.AdminID
#     AND a.Flag_Active=1 AND (a.Flag_Delete=0 OR a.Flag_Delete IS NULL)
# ORDER BY EmployeeName"""

#         try:
#             agg_rows = execute_query(agg_sql)
#         except Exception as e:
#             print(f'[MissingStatus] Aggregate error: {e}')
#             return []

#         if not agg_rows:
#             return []

#         # ── Per-file query (display only) — same date logic as post_conversion ──
#         file_sql = f"""
# DECLARE @Month INT={month}
# DECLARE @Year  INT={year}
# ;WITH
# LastAllocated AS (
#     SELECT h.OrderID, h.AssignedTo_UserID,
#         ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
#     FROM Table_OrderStatushistory h
#     WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
# ),
# LastAlloc AS (SELECT OrderID, AssignedTo_UserID FROM LastAllocated WHERE rn=1),
# FirstAllocDate AS (
#     SELECT h.OrderID, h.AssignedTo_UserID,
#         CAST(MIN(h.Date_Ctreated) AS DATE) AS FirstDate
#     FROM Table_OrderStatushistory h
#     WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
#     GROUP BY h.OrderID, h.AssignedTo_UserID
# ),
# WorkingDays AS (
#     SELECT CAST(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)) AS DATE) AS WorkDay
#     FROM (SELECT TOP 31 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
#           FROM master..spt_values) nums
#     WHERE MONTH(DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))=@Month
#       AND DATEPART(WEEKDAY,DATEADD(DAY,n,DATEFROMPARTS(@Year,@Month,1)))<>1
# ),
# FilesCompleted AS (
#     SELECT
#         la.AssignedTo_UserID                                              AS AdminID,
#         od.ID                                                             AS OrderID,
#         od.Order_Number                                                   AS OrderNumber,
#         od.CompanyName,
#         CAST(COALESCE(m.Retail_CompletionDate, od.CompletionOn) AS DATE)  AS CompletedDate,
#         -- Fix: if FirstAllocDate > CompletedDate (data inconsistency), use month start
#         CASE
#             WHEN CAST(fad.FirstDate AS DATE) >= DATEFROMPARTS(@Year,@Month,1)
#              AND CAST(fad.FirstDate AS DATE) <=
#                  CAST(COALESCE(m.Retail_CompletionDate, od.CompletionOn) AS DATE)
#             THEN CAST(fad.FirstDate AS DATE)
#             ELSE DATEFROMPARTS(@Year,@Month,1)
#         END                                                               AS ActiveFrom
#     FROM OrderDetails od
#     INNER JOIN LastAlloc      la  ON la.OrderID=od.ID
#     LEFT  JOIN FirstAllocDate fad ON fad.OrderID=od.ID
#                                  AND fad.AssignedTo_UserID=la.AssignedTo_UserID
#     LEFT  JOIN Table_OrderDetailsMisc m ON m.OrderID=od.ID
#     INNER JOIN Admin af ON af.ID_Admin=la.AssignedTo_UserID
#                        AND af.Flag_Active=1
#                        AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
#     WHERE od.Flag_Deleted=0
#       AND MONTH(COALESCE(m.Retail_CompletionDate, od.CompletionOn))=@Month
#       AND YEAR(COALESCE(m.Retail_CompletionDate,  od.CompletionOn))=@Year
# ),
# FileActiveDays AS (
#     SELECT
#         fc.AdminID, fc.OrderID, fc.OrderNumber,
#         fc.CompanyName, fc.CompletedDate, fc.ActiveFrom,
#         COUNT(wd.WorkDay) AS ActiveWorkingDays
#     FROM FilesCompleted fc
#     INNER JOIN WorkingDays wd
#            ON wd.WorkDay >= fc.ActiveFrom
#           AND wd.WorkDay <= fc.CompletedDate
#     GROUP BY fc.AdminID, fc.OrderID, fc.OrderNumber,
#              fc.CompanyName, fc.CompletedDate, fc.ActiveFrom
# ),
# FileUpdateDays AS (
#     SELECT h.OrderID, h.AssignedTo_UserID AS AdminID,
#         COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysUpdated
#     FROM Table_OrderStatushistory h
#     INNER JOIN WorkingDays wd ON CAST(h.Date_Ctreated AS DATE)=wd.WorkDay
#     WHERE MONTH(h.Date_Ctreated)=@Month AND YEAR(h.Date_Ctreated)=@Year
#       AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
#     GROUP BY h.OrderID, h.AssignedTo_UserID
# )
# SELECT
#     fad.AdminID,
#     fad.OrderID,
#     fad.OrderNumber,
#     fad.CompanyName,
#     fad.CompletedDate,
#     fad.ActiveFrom,
#     fad.ActiveWorkingDays                                AS ActiveDays,
#     ISNULL(fud.DaysUpdated, 0)                           AS DaysUpdated,
#     fad.ActiveWorkingDays - ISNULL(fud.DaysUpdated, 0)  AS DaysMissed
# FROM FileActiveDays fad
# LEFT JOIN FileUpdateDays fud
#        ON fud.OrderID=fad.OrderID AND fud.AdminID=fad.AdminID
# ORDER BY fad.AdminID, fad.CompletedDate"""

#         file_rows = []
#         try:
#             file_rows = execute_query(file_sql)
#             print(f'[MissingStatus] Per-file: {len(file_rows)} rows')
#         except Exception as e:
#             print(f'[MissingStatus] Per-file failed (non-critical): {e}')

#         from collections import defaultdict
#         files_by_admin = defaultdict(list)
#         for fr in file_rows:
#             files_by_admin[fr['AdminID']].append(fr)

#         for row in agg_rows:
#             row['FileBreakdown'] = files_by_admin.get(row['AdminID'], [])

#         return agg_rows

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}

#         row   = rows[0]
#         wdays = row.get('WorkingDaysInMonth', 0)
#         upd   = row.get('DaysWithUpdate', 0)
#         miss  = row.get('MissedDays', 0)
#         # ── Option A scoring: days updated / working days in month ──────────
#         ratio = round(upd/wdays*100, 2) if wdays else None

#         # Per-file display data
#         file_breakdown = []
#         file_orders    = []

#         for fb in row.get('FileBreakdown', []):
#             days_updated  = fb.get('DaysUpdated', 0)
#             active_days   = fb.get('ActiveDays', 0)
#             days_missed   = fb.get('DaysMissed', 0)

#             file_breakdown.append({
#                 'order_id':     fb.get('OrderID'),
#                 'order_number': fb.get('OrderNumber', '—'),
#                 'company':      fb.get('CompanyName', '—'),
#                 'completed':    str(fb.get('CompletedDate', '—')),
#                 'active_from':  str(fb.get('ActiveFrom', '—')),
#                 'active_days':  active_days,
#                 'days_updated': days_updated,
#                 'days_missed':  days_missed,
#             })

#             # For fileMap linking in EmployeeDetail
#             file_orders.append({
#                 'order_id':       fb.get('OrderID'),
#                 'order_number':   fb.get('OrderNumber', '—'),
#                 'company':        fb.get('CompanyName', '—'),
#                 'DaysUpdated':    days_updated,
#                 'ActiveDays':     active_days,
#                 'DaysMissed':     days_missed,
#                 '_is_file_entry': True,
#             })

#         primary = {
#             'TotalActiveDays': wdays,
#             'working_days':    wdays,
#             'DaysWithUpdate':  upd,
#             'MissedDays':      miss,
#             'file_breakdown':  file_breakdown,
#         }

#         return {
#             'numerator':     upd,
#             'denominator':   wdays,
#             'success_ratio': ratio,
#             'orders':        [primary] + file_orders,
#         }

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
#     FROM LastAlloc la
#     INNER JOIN OrderDetails od ON od.ID=la.OrderID
#     INNER JOIN Admin af ON af.ID_Admin=la.AssignedTo_UserID
#                        AND af.Flag_Active=1 AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
#     WHERE od.Flag_Deleted=0
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
#               AND a.Flag_Active=1 AND (a.Flag_Delete=0 OR a.Flag_Delete IS NULL)
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
