import json, calendar, requests
from datetime import date

ACCOUNT_ID = '6a17ec96a95e7ac45342c0e4'
AUTH_KEY   = 'keywWPoCKnwcJAA'
HEADERS    = {'auth-key': AUTH_KEY}
BASE       = f'https://table-api.viasocket.com/{ACCOUNT_ID}'

TABLES = {
    'leaves':         'tbl3mum9c',
    'late_comings':   'tbluntos9',
    'early_leavings': 'tblnetzkl',
}

_DEPT_MAP = {
    'conversion':'Conversion','convert':'Conversion',
    'it':'IT','it department':'IT',
    'email team':'Email','email communication':'Email',
    'client communication':'Communication',
    'accounting':'Account','account':'Account',
    'human resources':'HR','rnd':'RND',
}

def normalize_dept(raw):
    if not raw: return None
    return _DEPT_MAP.get(raw.strip().lower(), raw.strip())

def is_conversion(dept):
    return normalize_dept(dept) in {'Conversion'}

def get_working_days(year, month):
    _, days = calendar.monthrange(year, month)
    return sum(1 for d in range(1, days+1) if date(year,month,d).weekday() != 6)

def parse_leave_dates(raw):
    if not raw: return []
    if isinstance(raw, list): return raw
    try:
        data = json.loads(raw)
        if not data: return []
        if isinstance(data[0], str): return data
        return [e.get('date','') for e in data if e.get('date')]
    except: return []

def fetch_table(table_id):
    r = requests.get(f'{BASE}/{table_id}', headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get('data',{}).get('rows',[])

def get_leaves_for_month(month, year):
    prefix = f'{year:04d}-{month:02d}'
    rows   = fetch_table(TABLES['leaves'])
    result = []
    for row in rows:
        all_dates   = parse_leave_dates(row.get('leave_dates','[]'))
        month_dates = [d for d in all_dates if d.startswith(prefix)]
        if not month_dates and int(row.get('leave_count',0) or 0) > 0:
            continue
        result.append({**row,
            'month_leave_dates': month_dates,
            'month_leave_count': len(month_dates),
            'dept_normalized':   normalize_dept(row.get('department')),
            'WorkingDays':       get_working_days(year, month),
        })
    print(f'[ViaSocket] Leaves {month}/{year} → {len(result)} rows')
    return result
