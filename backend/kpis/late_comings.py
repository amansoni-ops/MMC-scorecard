from kpis.base import BaseKPI
from viasocket   import get_working_days
from name_mapper import resolve, init_name_map_table
import requests, json

ACCOUNT_ID = '6a17ec96a95e7ac45342c0e4'
TABLE_ID   = 'tbluntos9'
AUTH_KEY   = 'keywWPoCKnwcJAA'
URL        = f'https://table-api.viasocket.com/{ACCOUNT_ID}/{TABLE_ID}'
GRACE_UTC  = (4, 30)   # 04:30 UTC = 10:00 IST — no grace period

def _parse(raw):
    if not raw: return []
    if isinstance(raw, list): return raw
    try: return json.loads(raw)
    except: return []

def _is_late(e):
    p = e.get('actualPunchIn','')
    if not p: return True
    try:
        t=p.split('T')[1]; h,m=int(t[:2]),int(t[3:5])
        return (h,m) > GRACE_UTC
    except: return True

class LateComingsKPI(BaseKPI):
    def fetch(self, month, year):
        init_name_map_table()
        try:
            r=requests.get(URL,headers={'auth-key':AUTH_KEY},timeout=30); r.raise_for_status()
            rows=r.json().get('data',{}).get('rows',[])
        except Exception as e:
            print(f'[LateComings] API error: {e}'); return []
        if not rows: return []
        prefix=f'{year:04d}-{month:02d}'; wdays=get_working_days(year,month); result=[]
        for row in rows:
            name=(row.get('name') or '').strip()
            if not name: continue
            entries=[e for e in _parse(row.get('late_date','[]')) if str(e.get('date','')).startswith(prefix)]
            late=sum(1 for e in entries if _is_late(e))
            if not entries and int(row.get('count',0) or 0)>0: continue
            mapped=resolve(name)
            result.append({'AdminID':mapped['admin_id'],'EmployeeName':name,
                'Department':row.get('department'),'WorkingDays':wdays,
                'PresentDays':int(row.get('present_day',wdays) or wdays),
                'LateDays':min(late,wdays),'LateEntries':entries,'Month':month,'Year':year})
        print(f'[LateComings] {month}/{year} → {len(result)} employees')
        return result

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
        row=rows[0]; wdays=row.get('WorkingDays',0); late=row.get('LateDays',0); ontime=max(0,wdays-late)
        ratio=round(ontime/wdays*100,2) if wdays else None
        detail=[{'date':e.get('date'),
                 'shift_start':e.get('shiftStart','').replace('T',' ').replace('Z',' UTC'),
                 'punch_in':e.get('actualPunchIn','').replace('T',' ').replace('Z',' UTC')}
                for e in row.get('LateEntries',[])]
        return {'numerator':ontime,'denominator':wdays,'success_ratio':ratio,
                'orders':[{'working_days':wdays,'present_days':row.get('PresentDays',wdays),
                           'late_days':late,'on_time_days':ontime,'late_entries':detail}]}


# from kpis.base import BaseKPI
# from viasocket   import get_working_days
# from name_mapper import resolve, init_name_map_table
# import requests, json

# ACCOUNT_ID = '6a17ec96a95e7ac45342c0e4'
# TABLE_ID   = 'tbluntos9'
# AUTH_KEY   = 'keywWPoCKnwcJAA'
# URL        = f'https://table-api.viasocket.com/{ACCOUNT_ID}/{TABLE_ID}'
# GRACE_UTC  = (4, 45)   # 04:45 UTC = 10:15 IST

# def _parse(raw):
#     if not raw: return []
#     if isinstance(raw, list): return raw
#     try: return json.loads(raw)
#     except: return []

# def _is_late(e):
#     p = e.get('actualPunchIn','')
#     if not p: return True
#     try:
#         t=p.split('T')[1]; h,m=int(t[:2]),int(t[3:5])
#         return (h,m) > GRACE_UTC
#     except: return True

# class LateComingsKPI(BaseKPI):
#     def fetch(self, month, year):
#         init_name_map_table()
#         try:
#             r=requests.get(URL,headers={'auth-key':AUTH_KEY},timeout=30); r.raise_for_status()
#             rows=r.json().get('data',{}).get('rows',[])
#         except Exception as e:
#             print(f'[LateComings] API error: {e}'); return []
#         if not rows: return []
#         prefix=f'{year:04d}-{month:02d}'; wdays=get_working_days(year,month); result=[]
#         for row in rows:
#             name=(row.get('name') or '').strip()
#             if not name: continue
#             entries=[e for e in _parse(row.get('late_date','[]')) if str(e.get('date','')).startswith(prefix)]
#             late=sum(1 for e in entries if _is_late(e))
#             if not entries and int(row.get('count',0) or 0)>0: continue
#             mapped=resolve(name)
#             result.append({'AdminID':mapped['admin_id'],'EmployeeName':name,
#                 'Department':row.get('department'),'WorkingDays':wdays,
#                 'PresentDays':int(row.get('present_day',wdays) or wdays),
#                 'LateDays':min(late,wdays),'LateEntries':entries,'Month':month,'Year':year})
#         print(f'[LateComings] {month}/{year} → {len(result)} employees')
#         return result

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
#         row=rows[0]; wdays=row.get('WorkingDays',0); late=row.get('LateDays',0); ontime=max(0,wdays-late)
#         ratio=round(ontime/wdays*100,2) if wdays else None
#         detail=[{'date':e.get('date'),
#                  'shift_start':e.get('shiftStart','').replace('T',' ').replace('Z',' UTC'),
#                  'punch_in':e.get('actualPunchIn','').replace('T',' ').replace('Z',' UTC')}
#                 for e in row.get('LateEntries',[])]
#         return {'numerator':ontime,'denominator':wdays,'success_ratio':ratio,
#                 'orders':[{'working_days':wdays,'present_days':row.get('PresentDays',wdays),
#                            'late_days':late,'on_time_days':ontime,'late_entries':detail}]}
