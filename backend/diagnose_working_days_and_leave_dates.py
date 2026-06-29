"""
diagnose_working_days_and_leave_dates.py
============================================
Two bugs to nail down with real data:
  1. Working days showing 24 instead of 26 for May 2026 (most people are
     Sunday-only off — should be 26, not 24)
  2. leave_dates list length doesn't match unrecorded_absent_days count
     (Anchal Patidar: count=2, but only 1 date listed)

This recomputes BOTH numbers by hand, with full visibility into every
date in the range, for a person showing the bug — so the exact day(s)
being wrongly excluded/missed are visible directly.
"""

import sys
sys.path.insert(0, '.')
from datetime import datetime, timedelta
from kpis.keka_attendance import (
    get_month_data, DEFAULT_OFF_DAYS, WEEKLY_OFF_DAYS, _fetch_all, TBL_DETAILS
)

MONTH, YEAR = 5, 2026

print('Fetching computed May 2026 data (will use cache if present)...')
data = get_month_data(MONTH, YEAR)

print(f'\nSystemic days excluded company-wide: {data["systemic_days_excluded"]}')

# ── Hand-verify May 2026's calendar, Sunday-only assumption ────────────────
month_start = datetime(YEAR, MONTH, 1).date()
month_end = (datetime(YEAR, MONTH + 1, 1) - timedelta(days=1)).date()
print(f'\nMay 2026 full calendar: {month_start} to {month_end}')

all_days = []
d = month_start
while d <= month_end:
    all_days.append(d)
    d += timedelta(days=1)

sundays = [d for d in all_days if d.weekday() == 6]
print(f'Total days in May: {len(all_days)}')
print(f'Sundays in May 2026: {len(sundays)}  -> {sundays}')
print(f'Expected working days (31 - {len(sundays)} Sundays) = {31 - len(sundays)}')

systemic_set = set()
for s in data['systemic_days_excluded']:
    systemic_set.add(datetime.strptime(s, '%Y-%m-%d').date())
print(f'\nSystemic days as date objects: {systemic_set}')
systemic_that_are_sunday = [d for d in systemic_set if d.weekday() == 6]
systemic_that_are_NOT_sunday = [d for d in systemic_set if d.weekday() != 6]
print(f'Of those systemic days, how many are ALSO Sundays (double-excluded)? {len(systemic_that_are_sunday)}')
print(f'Of those systemic days, how many are NOT Sundays (genuinely extra exclusions)? {len(systemic_that_are_NOT_sunday)} -> {systemic_that_are_NOT_sunday}')

expected_with_systemic = 31 - len(sundays) - len(systemic_that_are_NOT_sunday)
print(f'\nSo expected working days SHOULD be: 31 - {len(sundays)}(Sundays) - '
      f'{len(systemic_that_are_NOT_sunday)}(non-Sunday systemic) = {expected_with_systemic}')

# ── Find Anchal Patidar specifically and recompute her leave_dates by hand ──
print('\n' + '=' * 78)
print('ANCHAL PATIDAR — full trace')
print('=' * 78)
target = None
for emp in data['employees']:
    if 'anchal' in emp['name'].lower() and 'patidar' in emp['name'].lower():
        target = emp
        break

if not target:
    print('Not found in this month\'s computed data.')
else:
    print(f'Name: {target["name"]}')
    print(f'expected_working_days: {target["expected_working_days"]}')
    print(f'present_days: {target["present_days"]}')
    print(f'unrecorded_absent_days: {target["unrecorded_absent_days"]}')
    print(f'absent_dates: {target["absent_dates"]}  (length={len(target["absent_dates"])})')
    print(f'joining_date: {target["joining_date"]}')
    print(f'exit_date: {target["exit_date"]}')

    # Check her actual off-days policy
    details = _fetch_all(TBL_DETAILS)
    her_detail = next((d for d in details if d.get('keka_id') == target['keka_id']), None)
    if her_detail:
        policy_id = her_detail.get('weekly_off_policy_id')
        off_days = WEEKLY_OFF_DAYS.get(policy_id, DEFAULT_OFF_DAYS)
        print(f'weekly_off_policy_id: {policy_id}')
        print(f'resolved off_days (weekday numbers, 6=Sunday): {off_days}')

print('\nDONE. Compare expected_working_days above against the by-hand')
print('31 - Sundays - nonSundaySystemic calculation to confirm the exact cause.')