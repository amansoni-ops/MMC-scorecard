"""
find_unknown_department_person.py
=====================================
Identifies exactly which employee(s) have no resolvable department --
i.e. keka_employee_groups has no group_type='2' row for their keka_id,
which is why they'd show as 'Unknown' in keka_attendance.py's dept_by_kid.
"""

import requests

AUTH_KEY = 'keywWPoCKnwcJAA'
DB_ID    = '6a17ec96a95e7ac45342c0e4'
BASE     = f'https://table-api.viasocket.com/{DB_ID}'
HEADERS  = {'auth-key': AUTH_KEY}

def fetch_all(table_id):
    rows, offset, pages = [], None, 0
    while True:
        params = {'offset': offset} if offset else {}
        r = requests.get(f'{BASE}/{table_id}', headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        d = r.json().get('data', {})
        batch = d.get('rows', [])
        rows.extend(batch)
        pages += 1
        offset = d.get('offset')
        if not offset or not batch or pages > 50:
            break
    return rows

print('Fetching employees and groups...')
emps = fetch_all('tblrj1w62')
groups = fetch_all('tblto5irg')

name_by_kid = {}
for e in emps:
    kid = e.get('name')
    if kid:
        name_by_kid[kid] = e.get('display_name', '?')

dept_kids = {g.get('keka_id') for g in groups if str(g.get('group_type')) == '2'}

missing = [kid for kid in name_by_kid if kid not in dept_kids]

print(f'\nTotal distinct employees: {len(name_by_kid)}')
print(f'Employees WITH a department (group_type=2) row: {len(dept_kids)}')
print(f'Employees with NO department row at all: {len(missing)}')
print()
for kid in missing:
    print(f'  {name_by_kid.get(kid, "?")}  (keka_id={kid})')