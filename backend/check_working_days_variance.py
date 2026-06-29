"""
check_working_days_variance.py
=================================
The screenshot shows multiple different working-days totals in the same
June view: 17, 20, and 26. 20 is the correct baseline (confirmed by hand
for June 1-23). This checks WHY each variant exists:
  - 17  -> likely a mid-month joiner (legitimate, smaller window)
  - 26  -> likely the OLD viasocket.get_working_days() fallback firing
           for people with zero June attendance rows (a real bug)
"""

import sys
sys.path.insert(0, '.')
from kpis.keka_attendance import get_month_data

MONTH, YEAR = 6, 2026

data = get_month_data(MONTH, YEAR)

print(f'Total employees in June data: {len(data["employees"])}')
print()

from collections import Counter
wd_counts = Counter(e['expected_working_days'] for e in data['employees'])
print('Distribution of expected_working_days values (from keka_attendance.py itself):')
for wd, count in sorted(wd_counts.items()):
    print(f'  {wd} days: {count} people')

print('\n' + '=' * 78)
print('Anyone with expected_working_days != 20 — checking WHY (joiner? exit?)')
print('=' * 78)
for e in data['employees']:
    if e['expected_working_days'] != 20:
        print(f'  {e["name"]:<25} expected={e["expected_working_days"]:<4} '
              f'joined_mid_month={e["joined_mid_month"]:<6} joining_date={e["joining_date"]} '
              f'exited_mid_month={e["exited_mid_month"]}')

print('\n' + '=' * 78)
print('Anyone with ZERO attendance rows this month at all (these are the ones')
print('that would trigger the OLD viasocket fallback in score_engine.py)')
print('=' * 78)
zero_data_people = [e for e in data['employees'] if e['present_days'] == 0
                     and e['late_days'] == 0 and e['early_exit_days'] == 0
                     and e['unrecorded_absent_days'] == e['expected_working_days']]
print(f'Count: {len(zero_data_people)}')
for e in zero_data_people[:10]:
    print(f'  {e["name"]:<25} expected={e["expected_working_days"]}')