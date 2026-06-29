"""
investigate_ambiguous_names.py
==================================
For every Keka employee whose full_diagnostic.py verdict was
AMBIGUOUS_EXACT (name matched 2+ SQL Admin rows), pull up the FULL Admin
record for every candidate -- not just name, but every column that might
disambiguate: email, department-ish fields if present, Flag_Active,
Flag_Delete, created/joining info if available -- so we can see whether
ANY field would let us safely auto-pick the right one, or whether this
genuinely needs a human/manual mapping.
"""

import sys
sys.path.insert(0, '.')
from db import execute_query
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

# The known ambiguous names from full_diagnostic.py's actual output
AMBIGUOUS_NAMES = [
    'Prachi Borde', 'Sunny Singh', 'Rajat Mehra', 'Khushi Yadav',
    'Ritik Hiwade', 'Pranjal Chourasiya', 'Sakshi Jatav', 'Pragya Mangal',
    'Shanu Mehta', 'Urmi Dubey', 'Aastha Sadhwani', 'Archita Neema',
    'Avani Jhinjoria', 'Ishika Sharma', 'Himanshu Patel', 'Osheen Khan',
    'Nandini Rayak', 'Abhishek Chowdhary', 'Preeti Shinde',
    'Shubhangi Ranade', 'Aarti Jagtap', 'Rahul Gour', 'Pratibha Tomar',
    'Bharti Bhavsar',
]

print('Checking what columns the Admin table actually has (full schema)...')
cols = execute_query("SELECT TOP 1 * FROM Admin")
if cols:
    print(f'Available columns: {list(cols[0].keys())}\n')

print('=' * 78)
for name in AMBIGUOUS_NAMES:
    # Find candidates by loose LIKE match on first/last name parts
    parts = name.split()
    first, last = parts[0], parts[-1]
    sql = f"""
        SELECT ID_Admin, Admin_FirstName, Admin_LastName, Admin_Email,
               Flag_Active, Flag_Delete
        FROM Admin
        WHERE Admin_FirstName LIKE '%{first}%' AND Admin_LastName LIKE '%{last}%'
    """
    try:
        candidates = execute_query(sql)
    except Exception as e:
        print(f'{name}: QUERY ERROR — {e}')
        continue

    print(f'\n{name}  ->  {len(candidates)} SQL Admin candidate(s):')
    for c in candidates:
        print(f'   ID_Admin={c.get("ID_Admin"):<6} '
              f'Name="{c.get("Admin_FirstName")} {c.get("Admin_LastName")}"  '
              f'Email={c.get("Admin_Email")}  '
              f'Active={c.get("Flag_Active")}  Delete={c.get("Flag_Delete")}')

print('\n' + '=' * 78)
print('Now checking the KEKA side email for these same people, for comparison')
print('=' * 78)
emps = fetch_all('tblrj1w62')
name_to_keka = {}
for e in emps:
    dn = e.get('display_name', '')
    if dn.strip() in AMBIGUOUS_NAMES:
        name_to_keka[dn.strip()] = e.get('email')

for name in AMBIGUOUS_NAMES:
    keka_email = name_to_keka.get(name, 'NOT FOUND IN KEKA DUMP')
    print(f'   {name:<25} Keka email: {keka_email}')