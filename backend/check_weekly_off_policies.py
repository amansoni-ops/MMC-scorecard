"""
check_weekly_off_policies.py
===============================
Confirms exactly what weekly_off_policy values exist in keka_attendance,
and specifically checks Aman Soni and Prathmesh Bandal (reported as
Sat+Sun off) to see the real policy string Keka uses for that pattern --
so the fix can match real values, not a guessed format.
"""

import requests
from collections import Counter

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

print('Fetching attendance + employees...')
att = fetch_all('tblr5wgh0')
emps = fetch_all('tblrj1w62')

name_by_kid = {e.get('name'): e.get('display_name', '?') for e in emps if e.get('name')}

print('\nAll distinct weekly_off_policy values found in keka_attendance:')
policy_counts = Counter(r.get('weekly_off_policy') for r in att)
for policy, count in policy_counts.most_common():
    print(f'  {repr(policy):<40} count={count}')

print('\n' + '=' * 70)
print('Specific check: Aman Soni and Prathmesh Bandal')
print('=' * 70)
for target_name in ['Aman Soni', 'Prathmesh Sunil Bandal', 'Prathmesh Bandal']:
    target_kid = None
    for kid, name in name_by_kid.items():
        if target_name.lower() in name.lower():
            target_kid = kid
            target_full_name = name
            break
    if not target_kid:
        print(f'\n{target_name}: not found in employees table')
        continue

    rows = [r for r in att if r.get('name') == target_kid]
    print(f'\n{target_full_name} (keka_id={target_kid}): {len(rows)} attendance rows')
    sample_policies = Counter(r.get('weekly_off_policy') for r in rows)
    for policy, count in sample_policies.most_common():
        print(f'   weekly_off_policy={repr(policy)}  count={count}')

    # Show a sample row in full to see ALL fields related to off-days
    if rows:
        print(f'   Sample row keys: {list(rows[0].keys())}')
        print(f'   weekly_off_policy_id: {rows[0].get("weekly_off_policy_id")}')