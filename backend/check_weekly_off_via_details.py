"""
check_weekly_off_via_details.py
===================================
weekly_off_policy is empty in keka_attendance for everyone. The real
signal must come from keka_employee_details.weekly_off_policy_id,
joined to keka_policies for the policy's title. This checks:
  1. What weekly_off_policy_id values actually exist for Aman Soni and
     Prathmesh Bandal specifically
  2. What policy TITLE each id resolves to in keka_policies
  3. Whether the title text itself reveals which days (e.g. contains
     "Saturday" or "6 days" or similar), or whether it's just a generic
     label that doesn't actually encode the days at all
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

print('Fetching employee_details, policies, employees...')
details = fetch_all('tblp2kh5y')
policies = fetch_all('tbl0gobt2')
emps = fetch_all('tblrj1w62')

name_by_kid = {e.get('name'): e.get('display_name', '?') for e in emps if e.get('name')}
details_by_kid = {d.get('keka_id'): d for d in details if d.get('keka_id')}

print('\nAll weekly_off_policy_id values found, with counts:')
from collections import Counter
policy_id_counts = Counter(d.get('weekly_off_policy_id') for d in details)
for pid, count in policy_id_counts.most_common():
    print(f'  {repr(pid):<45} count={count}')

print('\n' + '=' * 70)
print('keka_policies table -- what TITLES exist for these IDs (and any others)')
print('=' * 70)
for p in policies:
    print(f'  policy_id={p.get("name")}  title={repr(p.get("title"))}  type={p.get("policy_type")}')
if not policies or all(p.get('title') is None for p in policies):
    print('  (keka_policies table is empty/unpopulated -- confirmed earlier this session,')
    print('   only 5 placeholder rows existed with all-null values)')

print('\n' + '=' * 70)
print('Aman Soni and Prathmesh Bandal -- their actual weekly_off_policy_id')
print('=' * 70)
for target in ['Aman Soni', 'Prathmesh']:
    for kid, name in name_by_kid.items():
        if target.lower() in name.lower():
            d = details_by_kid.get(kid)
            if d:
                print(f'\n{name}:')
                print(f'   weekly_off_policy_id = {repr(d.get("weekly_off_policy_id"))}')
                print(f'   shift_policy_id      = {repr(d.get("shift_policy_id"))}')
            else:
                print(f'\n{name}: no employee_details row found')