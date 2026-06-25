from kpis.base import BaseKPI
from db import execute_query

class MissingStatusKPI(BaseKPI):
    def fetch(self, month, year):
        # ── Aggregate query — Option A scoring (days updated / working days) ──
        # Attribution: COALESCE(PickedUpBy, AssignedTo_UserID, Summary_AssignUserID)
        # — matches post_conversion.py / delayed_conversion.py exactly.
        agg_sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
DECLARE @MonthStart DATE = DATEFROMPARTS(@Year,@Month,1)
DECLARE @MonthEndExcl DATE = DATEADD(MONTH,1,@MonthStart)  -- exclusive upper bound
;WITH
LastAllocated AS (
    SELECT h.OrderID, h.AssignedTo_UserID,
        ROW_NUMBER() OVER (PARTITION BY h.OrderID ORDER BY h.Date_Ctreated DESC) AS rn
    FROM Table_OrderStatushistory h
    WHERE h.StatusID=11 AND h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND h.Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
),
LastAlloc AS (SELECT OrderID, AssignedTo_UserID FROM LastAllocated WHERE rn=1),
-- FIXED: this was the real bug — previously built from EVERY order in
-- OrderDetails regardless of month or completion status, meaning anyone
-- EVER referenced via Summary_AssignUserID (the weakest fallback in the
-- COALESCE chain) on ANY historical order — even ones not completed this
-- month, even ones they never actually worked — got pulled into
-- ActiveEmps and shown a Missing Status score with zero real files.
-- Now filtered to orders ACTUALLY COMPLETED in the target month only,
-- matching exactly what the per-file query already does. A person with
-- genuinely zero files completed this month no longer appears here at
-- all — correct, since there's nothing to measure.
ResolvedAttribution AS (
    SELECT
        od.ID AS OrderID,
        COALESCE(m.PickedUpBy, la.AssignedTo_UserID, m.Summary_AssignUserID) AS AdminID
    FROM OrderDetails od
    LEFT JOIN Table_OrderDetailsMisc m ON m.OrderID = od.ID
    LEFT JOIN LastAlloc la             ON la.OrderID = od.ID
    WHERE od.Flag_Deleted = 0
      -- FIXED: sargable range comparison instead of MONTH()/YEAR() function
      -- wrapping. Wrapping an indexed column (CompletionOn) in a function
      -- forces SQL Server to scan and evaluate every row instead of seeking
      -- via an index, which is the likely cause of this query hanging for
      -- 8+ minutes once od.CompletionOn started being filtered here.
      AND od.CompletionOn >= @MonthStart
      AND od.CompletionOn <  @MonthEndExcl
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
ORDER BY EmployeeName"""

        try:
            agg_rows = execute_query(agg_sql)
        except Exception as e:
            print(f'[MissingStatus] Aggregate error: {e}')
            return []

        if not agg_rows:
            return []

        # ── Per-file query (display only) ─────────────────────────────────
        # TWO FIXES applied here per explicit request:
        #
        # 1. ActiveTo = completion date MINUS ONE WORKING DAY (skips back
        #    over Sunday/off-days), not the completion date itself — no
        #    status update is expected ON the day the file gets completed,
        #    so that day should not count toward the active window at all.
        #
        # 2. ActiveFrom = the file's TRUE first-allocation date, even if it
        #    falls in a PRIOR calendar month — no longer clipped to the
        #    current month's start. A file allocated April 25 and completed
        #    May 5 now correctly counts its full real active span (including
        #    the April portion) under May's report, instead of only
        #    counting the May 1-4 slice and silently discarding April 25-30.
        #
        # This requires WorkingDays to span from a wide-enough EARLIER start
        # (90 days back covers any realistic cross-month case) through the
        # CURRENT month's end, not just the current month alone — since a
        # file's true ActiveFrom can now land in a prior month.
        file_sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
DECLARE @MonthStart DATE = DATEFROMPARTS(@Year,@Month,1)
DECLARE @MonthEnd   DATE = EOMONTH(@MonthStart)
DECLARE @MonthEndExcl DATE = DATEADD(MONTH,1,@MonthStart)
DECLARE @RangeStart DATE = DATEADD(DAY,-90,@MonthStart)  -- wide enough for any realistic cross-month span
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
-- WorkingDays now spans the WIDE range (RangeStart -> MonthEnd), not just
-- the current month — needed so a file's true ActiveFrom in a prior month
-- still has real working-day rows to count against.
WorkingDays AS (
    SELECT CAST(DATEADD(DAY,n,@RangeStart) AS DATE) AS WorkDay
    FROM (SELECT TOP 1000 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1 AS n
          FROM master..spt_values) nums
    WHERE DATEADD(DAY,n,@RangeStart) <= @MonthEnd
      AND DATEPART(WEEKDAY,DATEADD(DAY,n,@RangeStart))<>1
),
FilesCompleted AS (
    SELECT
        COALESCE(m.PickedUpBy, la.AssignedTo_UserID, m.Summary_AssignUserID) AS AdminID,
        od.ID                                                               AS OrderID,
        od.Order_Number                                                     AS OrderNumber,
        od.CompanyName,
        CAST(od.CompletionOn AS DATE)                                       AS CompletedDate,
        -- ActiveFrom: TRUE first allocation date, no longer clipped to
        -- month start. Falls back to month start only if FirstAllocDate is
        -- missing entirely, or is AFTER completion (existing data-
        -- inconsistency safeguard, unchanged).
        CASE
            WHEN fad.FirstDate IS NOT NULL
             AND CAST(fad.FirstDate AS DATE) <= CAST(od.CompletionOn AS DATE)
            THEN CAST(fad.FirstDate AS DATE)
            ELSE @MonthStart
        END                                                                 AS ActiveFromRaw
    FROM OrderDetails od
    LEFT  JOIN LastAlloc      la  ON la.OrderID=od.ID
    LEFT  JOIN FirstAllocDate fad ON fad.OrderID=od.ID
                                 AND fad.AssignedTo_UserID=la.AssignedTo_UserID
    LEFT  JOIN Table_OrderDetailsMisc m ON m.OrderID=od.ID
    INNER JOIN Admin af ON af.ID_Admin=COALESCE(m.PickedUpBy, la.AssignedTo_UserID, m.Summary_AssignUserID)
                       AND af.Flag_Active=1
                       AND (af.Flag_Delete=0 OR af.Flag_Delete IS NULL)
    WHERE od.Flag_Deleted=0
      -- Same sargable-range fix as the aggregate query above.
      AND od.CompletionOn >= @MonthStart
      AND od.CompletionOn <  @MonthEndExcl
),
-- Apply fix 1: ActiveTo = last WORKING DAY strictly before CompletedDate
-- (skips back over Sunday/off-days correctly), not CompletedDate itself.
FilesWithActiveTo AS (
    SELECT
        fc.*,
        (SELECT MAX(wd2.WorkDay) FROM WorkingDays wd2 WHERE wd2.WorkDay < fc.CompletedDate) AS ActiveTo
    FROM FilesCompleted fc
),
FileActiveDays AS (
    SELECT
        f.AdminID, f.OrderID, f.OrderNumber,
        f.CompanyName, f.CompletedDate, f.ActiveFromRaw AS ActiveFrom, f.ActiveTo,
        COUNT(wd.WorkDay) AS ActiveWorkingDays
    FROM FilesWithActiveTo f
    INNER JOIN WorkingDays wd
           ON wd.WorkDay >= f.ActiveFromRaw
          AND wd.WorkDay <= f.ActiveTo
    GROUP BY f.AdminID, f.OrderID, f.OrderNumber,
             f.CompanyName, f.CompletedDate, f.ActiveFromRaw, f.ActiveTo
),
-- Update-day counting now spans the SAME wide range as the active window,
-- not just the current month — so updates posted in the prior-month
-- portion of a cross-month file are correctly counted too.
FileUpdateDays AS (
    SELECT h.OrderID, fad.AdminID,
        COUNT(DISTINCT CAST(h.Date_Ctreated AS DATE)) AS DaysUpdated
    FROM Table_OrderStatushistory h
    INNER JOIN FileActiveDays fad ON fad.OrderID = h.OrderID
    INNER JOIN WorkingDays wd ON CAST(h.Date_Ctreated AS DATE)=wd.WorkDay
    WHERE h.AssignedTo_UserID IS NOT NULL AND h.AssignedTo_UserID>0
      AND CAST(h.Date_Ctreated AS DATE) >= fad.ActiveFrom
      AND CAST(h.Date_Ctreated AS DATE) <= fad.ActiveTo
    GROUP BY h.OrderID, fad.AdminID
)
SELECT
    fad.AdminID,
    fad.OrderID,
    fad.OrderNumber,
    fad.CompanyName,
    fad.CompletedDate,
    fad.ActiveFrom,
    fad.ActiveTo,
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
        # ── Option A scoring: days updated / working days in month ──────
        # NOTE: this top-level score is UNCHANGED — still based on the
        # employee's overall monthly update activity (Table_OrderStatushistory
        # across ALL their files that month), not on the per-file active-day
        # totals below. The two fixes in this update only affect the
        # PER-FILE BREAKDOWN table shown in the UI, not this aggregate score.
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
                'active_to':    str(fb.get('ActiveTo', '—')),
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


if __name__ == '__main__':
    import sys
    m = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    y = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
    test_admin_id = int(sys.argv[3]) if len(sys.argv) > 3 else None

    print(f'Running MissingStatusKPI for {m}/{y}...')
    inst = MissingStatusKPI()
    rows = inst.fetch(m, y)
    print(f'Total rows: {len(rows)}')

    if test_admin_id:
        emp_rows = [r for r in rows if r.get('AdminID') == test_admin_id]
        print(f'\nRows for AdminID={test_admin_id}: {len(emp_rows)}')
        if emp_rows:
            print(f'  EmployeeName: {emp_rows[0].get("EmployeeName")}')
            print(f'  WorkingDaysInMonth: {emp_rows[0].get("WorkingDaysInMonth")}')
            print(f'  DaysWithUpdate: {emp_rows[0].get("DaysWithUpdate")}')
            print(f'  MissedDays: {emp_rows[0].get("MissedDays")}')
            agg = inst.aggregate(emp_rows)
            print(f'\n  Aggregate: {agg["numerator"]}/{agg["denominator"]} = {agg["success_ratio"]}%')
            print(f'  File breakdown count: {len(agg["orders"][0]["file_breakdown"])}')
            for fb in agg['orders'][0]['file_breakdown'][:20]:
                print(f'    {fb["order_number"]:<22} {fb["company"]:<30} '
                      f'completed={fb["completed"]} active_from={fb["active_from"]} '
                      f'active_to={fb["active_to"]} active={fb["active_days"]} '
                      f'updated={fb["days_updated"]} missed={fb["days_missed"]}')
        else:
            print(f'  No rows found for this AdminID.')
    else:
        print('\nSample of first 10 employees:')
        for r in rows[:10]:
            print(f'  AdminID={r.get("AdminID"):<6} {r.get("EmployeeName"):<25} '
                  f'updated={r.get("DaysWithUpdate")}/{r.get("WorkingDaysInMonth")} '
                  f'missed={r.get("MissedDays")}')
        print('\nTip: pass an AdminID as 3rd argument for full per-file detail:')
        print(f'  python -m kpis.missing_status {m} {y} 303')
        


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
#         CAST(od.CompletionOn AS DATE)                                      AS CompletedDate,
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
#       AND MONTH(od.CompletionOn)=@Month
#       AND YEAR(od.CompletionOn) =@Year
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
#                 'completed':      str(fb.get('CompletedDate', '—')),
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
