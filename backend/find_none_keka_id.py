"""
find_none_keka_id.py
=======================
_synthetic_admin_id(None) is the crash. Find exactly which employee
record in keka_attendance.py's computed output has keka_id=None, so we
can fix the ROOT cause (why does this record exist with no keka_id at
all) rather than just paper over the crash site.
"""
import sys
sys.path.insert(0, '.')
from kpis.keka_attendance import get_month_data

MONTH, YEAR = 6, 2026

data = get_month_data(MONTH, YEAR, force_refresh=True)

print(f'Total employee records: {len(data["employees"])}')

none_kid = [e for e in data['employees'] if not e.get('keka_id')]
print(f'\nRecords with missing/None keka_id: {len(none_kid)}')
for e in none_kid:
    print(f'  {e}')

none_name = [e for e in data['employees'] if not e.get('name') or e.get('name') == '?']
print(f'\nRecords with missing/unknown name: {len(none_name)}')
for e in none_name[:10]:
    print(f'  keka_id={e.get("keka_id")}  name={e.get("name")}  admin_id={e.get("admin_id")}')