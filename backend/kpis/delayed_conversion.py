from kpis.base import BaseKPI
from db import execute_query

class DelayedConversionKPI(BaseKPI):
    def fetch(self, month, year):
        sql = f"""
DECLARE @Month INT={month}
DECLARE @Year  INT={year}
;WITH
LastAllocated AS (
    SELECT OrderID, AssignedTo_UserID,
        ROW_NUMBER() OVER (PARTITION BY OrderID ORDER BY Date_Ctreated DESC) AS rn
    FROM Table_OrderStatushistory
    WHERE StatusID=11 AND AssignedTo_UserID IS NOT NULL AND AssignedTo_UserID>0
      AND Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
),
BaseData AS (
    SELECT m.ID_OrderDetailsMisc, m.OrderID, m.PickedUpBy, m.Summary_AssignUserID,
        COALESCE(m.ETA_Date, m.Summary_ETADate) AS ResolvedETA,
        CASE
            WHEN m.Date_OrderReviewStatus IS NOT NULL THEN CAST(m.Date_OrderReviewStatus AS DATE)
            WHEN m.ConversionEndDate_1    IS NOT NULL THEN CAST(m.ConversionEndDate_1    AS DATE)
            WHEN m.Retail_CompletionDate  IS NOT NULL THEN CAST(m.Retail_CompletionDate  AS DATE)
            WHEN m.Jaz_CompletionDate     IS NOT NULL THEN CAST(m.Jaz_CompletionDate     AS DATE)
            ELSE                                           CAST(m.ConversionEndDate_2    AS DATE)
        END AS FinalCompletionDate
    FROM Table_OrderDetailsMisc m WHERE m.Flag_OrderCompleted=1
)
SELECT
    COALESCE(m.PickedUpBy, m.Summary_AssignUserID, la.AssignedTo_UserID) AS AdminID,
    COALESCE(a1.Admin_FirstName+' '+a1.Admin_LastName,
             a2.Admin_FirstName+' '+a2.Admin_LastName,
             a3.Admin_FirstName+' '+a3.Admin_LastName)                   AS EmployeeName,
    b.OrderID, od.Order_Number AS OrderNumber, od.CompanyName,
    b.FinalCompletionDate, b.ResolvedETA,
    CASE
        WHEN b.ResolvedETA IS NOT NULL
         AND b.FinalCompletionDate<=CAST(b.ResolvedETA AS DATE) THEN 1
        ELSE 0
    END AS IsOnTime,
    CASE
        WHEN b.ResolvedETA IS NULL                              THEN 'No ETA'
        WHEN b.FinalCompletionDate>CAST(b.ResolvedETA AS DATE) THEN 'Delayed'
        ELSE 'On Time'
    END AS DelayStatus,
    CASE WHEN b.ResolvedETA IS NOT NULL
         THEN DATEDIFF(DAY, b.ResolvedETA, b.FinalCompletionDate) ELSE NULL
    END AS DaysDelayed
FROM BaseData b
INNER JOIN Table_OrderDetailsMisc m ON m.ID_OrderDetailsMisc=b.ID_OrderDetailsMisc
INNER JOIN OrderDetails od           ON od.ID=b.OrderID
LEFT  JOIN Admin a1                  ON a1.ID_Admin=m.PickedUpBy
LEFT  JOIN Admin a2                  ON a2.ID_Admin=m.Summary_AssignUserID
LEFT  JOIN LastAllocated la          ON la.OrderID=b.OrderID AND la.rn=1
LEFT  JOIN Admin a3                  ON a3.ID_Admin=la.AssignedTo_UserID
WHERE MONTH(b.FinalCompletionDate)=@Month AND YEAR(b.FinalCompletionDate)=@Year
  AND COALESCE(m.PickedUpBy, m.Summary_AssignUserID, la.AssignedTo_UserID) IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM Admin ax
      WHERE ax.ID_Admin = COALESCE(m.PickedUpBy, m.Summary_AssignUserID, la.AssignedTo_UserID)
        AND ax.Flag_Active=1 AND (ax.Flag_Delete=0 OR ax.Flag_Delete IS NULL)
  )
ORDER BY EmployeeName, b.FinalCompletionDate"""
        return execute_query(sql)

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
        total   = len(rows)
        on_time = sum(1 for r in rows if r.get('IsOnTime')==1)
        ratio   = round(on_time/total*100, 2) if total else None
        orders  = [{'order_id':r.get('OrderID'),'order_number':r.get('OrderNumber'),
                    'company':r.get('CompanyName'),'completed':str(r.get('FinalCompletionDate','')),
                    'eta':str(r.get('ResolvedETA','')) if r.get('ResolvedETA') else None,
                    'status':r.get('DelayStatus'),'days_delayed':r.get('DaysDelayed')} for r in rows]
        return {'numerator':on_time,'denominator':total,'success_ratio':ratio,'orders':orders}

# from kpis.base import BaseKPI
# from db import execute_query

# class DelayedConversionKPI(BaseKPI):
#     def fetch(self, month, year):
#         sql = f"""
# DECLARE @Month INT={month}
# DECLARE @Year  INT={year}
# ;WITH
# LastAllocated AS (
#     SELECT OrderID, AssignedTo_UserID,
#         ROW_NUMBER() OVER (PARTITION BY OrderID ORDER BY Date_Ctreated DESC) AS rn
#     FROM Table_OrderStatushistory
#     WHERE StatusID=11 AND AssignedTo_UserID IS NOT NULL AND AssignedTo_UserID>0
#       AND Date_Ctreated<=EOMONTH(DATEFROMPARTS(@Year,@Month,1))
# ),
# BaseData AS (
#     SELECT m.ID_OrderDetailsMisc, m.OrderID, m.PickedUpBy, m.Summary_AssignUserID,
#         COALESCE(m.ETA_Date, m.Summary_ETADate) AS ResolvedETA,
#         CASE
#             WHEN m.Date_OrderReviewStatus IS NOT NULL THEN CAST(m.Date_OrderReviewStatus AS DATE)
#             WHEN m.ConversionEndDate_1    IS NOT NULL THEN CAST(m.ConversionEndDate_1    AS DATE)
#             WHEN m.Retail_CompletionDate  IS NOT NULL THEN CAST(m.Retail_CompletionDate  AS DATE)
#             WHEN m.Jaz_CompletionDate     IS NOT NULL THEN CAST(m.Jaz_CompletionDate     AS DATE)
#             ELSE                                           CAST(m.ConversionEndDate_2    AS DATE)
#         END AS FinalCompletionDate
#     FROM Table_OrderDetailsMisc m WHERE m.Flag_OrderCompleted=1
# )
# SELECT
#     COALESCE(m.PickedUpBy, m.Summary_AssignUserID, la.AssignedTo_UserID) AS AdminID,
#     COALESCE(a1.Admin_FirstName+' '+a1.Admin_LastName,
#              a2.Admin_FirstName+' '+a2.Admin_LastName,
#              a3.Admin_FirstName+' '+a3.Admin_LastName)                   AS EmployeeName,
#     b.OrderID, od.Order_Number AS OrderNumber, od.CompanyName,
#     b.FinalCompletionDate, b.ResolvedETA,
#     CASE
#         WHEN b.ResolvedETA IS NOT NULL
#          AND b.FinalCompletionDate<=CAST(b.ResolvedETA AS DATE) THEN 1
#         ELSE 0
#     END AS IsOnTime,
#     CASE
#         WHEN b.ResolvedETA IS NULL                              THEN 'No ETA'
#         WHEN b.FinalCompletionDate>CAST(b.ResolvedETA AS DATE) THEN 'Delayed'
#         ELSE 'On Time'
#     END AS DelayStatus,
#     CASE WHEN b.ResolvedETA IS NOT NULL
#          THEN DATEDIFF(DAY, b.ResolvedETA, b.FinalCompletionDate) ELSE NULL
#     END AS DaysDelayed
# FROM BaseData b
# INNER JOIN Table_OrderDetailsMisc m ON m.ID_OrderDetailsMisc=b.ID_OrderDetailsMisc
# INNER JOIN OrderDetails od           ON od.ID=b.OrderID
# LEFT  JOIN Admin a1                  ON a1.ID_Admin=m.PickedUpBy
# LEFT  JOIN Admin a2                  ON a2.ID_Admin=m.Summary_AssignUserID
# LEFT  JOIN LastAllocated la          ON la.OrderID=b.OrderID AND la.rn=1
# LEFT  JOIN Admin a3                  ON a3.ID_Admin=la.AssignedTo_UserID
# WHERE MONTH(b.FinalCompletionDate)=@Month AND YEAR(b.FinalCompletionDate)=@Year
#   AND COALESCE(m.PickedUpBy, m.Summary_AssignUserID, la.AssignedTo_UserID) IS NOT NULL
# ORDER BY EmployeeName, b.FinalCompletionDate"""
#         return execute_query(sql)

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
#         total   = len(rows)
#         on_time = sum(1 for r in rows if r.get('IsOnTime')==1)
#         ratio   = round(on_time/total*100, 2) if total else None
#         orders  = [{'order_id':r.get('OrderID'),'order_number':r.get('OrderNumber'),
#                     'company':r.get('CompanyName'),'completed':str(r.get('FinalCompletionDate','')),
#                     'eta':str(r.get('ResolvedETA','')) if r.get('ResolvedETA') else None,
#                     'status':r.get('DelayStatus'),'days_delayed':r.get('DaysDelayed')} for r in rows]
#         return {'numerator':on_time,'denominator':total,'success_ratio':ratio,'orders':orders}
