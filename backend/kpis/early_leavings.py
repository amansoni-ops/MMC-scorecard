from kpis.base import BaseKPI
from viasocket   import get_working_days
from name_mapper import resolve, init_name_map_table
import requests, json

ACCOUNT_ID = '6a17ec96a95e7ac45342c0e4'
TABLE_ID   = 'tblnetzkl'
AUTH_KEY   = 'keywWPoCKnwcJAA'
URL        = f'https://table-api.viasocket.com/{ACCOUNT_ID}/{TABLE_ID}'

def _parse(raw):
    if not raw: return []
    if isinstance(raw, list): return raw
    try: return json.loads(raw)
    except: return []

class EarlyLeavingsKPI(BaseKPI):
    def fetch(self, month, year):
        init_name_map_table()
        try:
            r=requests.get(URL,headers={'auth-key':AUTH_KEY},timeout=30); r.raise_for_status()
            rows=r.json().get('data',{}).get('rows',[])
        except Exception as e:
            print(f'[EarlyLeavings] API error: {e}'); return []
        if not rows: return []
        prefix=f'{year:04d}-{month:02d}'; wdays=get_working_days(year,month); result=[]
        for row in rows:
            name=(row.get('name') or '').strip()
            if not name: continue
            entries=[e for e in _parse(row.get('early_dates','[]')) if str(e.get('date','')).startswith(prefix)]
            if not entries and int(row.get('earlygoing',0) or 0)>0: continue
            mapped=resolve(name)
            result.append({'AdminID':mapped['admin_id'],'EmployeeName':name,
                'Department':row.get('department'),'WorkingDays':wdays,
                'EarlyDays':min(len(entries),wdays),'EarlyEntries':entries,'Month':month,'Year':year})
        print(f'[EarlyLeavings] {month}/{year} → {len(result)} employees')
        return result

    def aggregate(self, rows):
        if not rows:
            return {'numerator':0,'denominator':0,'success_ratio':None,'orders':[]}
        row=rows[0]; wdays=row.get('WorkingDays',0); early=row.get('EarlyDays',0); full=max(0,wdays-early)
        ratio=round(full/wdays*100,2) if wdays else None
        detail=[{'date':e.get('date'),'expected_hours':e.get('expectedHours'),
                 'actual_hours':float(e.get('actualHours',0) or 0),
                 'shortfall_hrs':round(float(e.get('expectedHours',0))-float(e.get('actualHours',0) or 0),2)}
                for e in row.get('EarlyEntries',[])]
        return {'numerator':full,'denominator':wdays,'success_ratio':ratio,
                'orders':[{'working_days':wdays,'early_days':early,
                           'full_days':full,'early_entries':detail}]}
