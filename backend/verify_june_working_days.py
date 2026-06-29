"""
verify_june_working_days.py
==============================
Hand-check: June 2026, today=June 24. Expected working days through
yesterday (June 23) for a Sunday-only person should be:
  June 1-23 = 23 calendar days, minus however many Sundays fall in that
  range, minus genuine systemic days (NOT just any day that happened to
  trip the 30%-incomplete threshold on thin data).

Also inspects the 6 flagged June systemic days directly -- how many
employees actually had attendance rows that day, and what the real
incomplete ratio was -- to judge whether 6 genuine outages is plausible
or whether the threshold is misfiring on smaller daily samples typical
of a still-accumulating month.
"""

import sys
sys.path.insert(0, '.')
from datetime import datetime, timedelta
from kpis.keka_attendance import get_month_data, _fetch_all, TBL_ATTENDANCE, _parse_dt

MONTH, YEAR = 6, 2026
today = datetime.utcnow().date()
print(f'Today: {today}')

data = get_month_data(MONTH, YEAR)
print(f'\nSystemic days flagged: {data["systemic_days_excluded"]}')

month_start = datetime(YEAR, MONTH, 1).date()
yesterday = today - timedelta(days=1)
print(f'\nJune range being evaluated: {month_start} to {yesterday} (today excluded)')

all_days = []
d = month_start
while d <= yesterday:
    all_days.append(d)
    d += timedelta(days=1)
sundays = [d for d in all_days if d.weekday() == 6]
print(f'Total days in range: {len(all_days)}')
print(f'Sundays in range: {len(sundays)} -> {sundays}')
print(f'Expected (Sunday-only person), BEFORE systemic exclusion: {len(all_days) - len(sundays)}')

systemic_set = set()
for s in data['systemic_days_excluded']:
    systemic_set.add(datetime.strptime(s, '%Y-%m-%d').date())
systemic_in_range = [d for d in systemic_set if d in all_days]
systemic_non_sunday = [d for d in systemic_in_range if d.weekday() != 6]
print(f'Systemic days actually within this range: {len(systemic_in_range)}')
print(f'Of those, non-Sunday (genuinely extra exclusions): {len(systemic_non_sunday)} -> {systemic_non_sunday}')

print(f'\nWith the current design (systemic days do NOT shrink the')
print(f'denominator, they count as present-by-default instead), the')
print(f'denominator should be: {len(all_days) - len(sundays)} regardless of')
print(f'systemic days. Sarita Jaiswal showed 20 -- does that match?')

print('\n' + '=' * 78)
print('RAW INSPECTION OF EACH FLAGGED SYSTEMIC DAY')
print('=' * 78)
att = _fetch_all(TBL_ATTENDANCE)
from collections import defaultdict
by_date = defaultdict(lambda: {'total': 0, 'incomplete': 0, 'kids': set()})

for row in att:
    pin = _parse_dt(row.get('punch_in'))
    pout = _parse_dt(row.get('punch_out'))
    anchor = pin or pout
    if not anchor or anchor.month != MONTH or anchor.year != YEAR:
        continue
    d = anchor.date()
    incomplete = (not pin or not pout)
    by_date[d]['total'] += 1
    by_date[d]['kids'].add(row.get('name'))
    if incomplete:
        by_date[d]['incomplete'] += 1

for d in sorted(systemic_in_range):
    c = by_date.get(d, {'total': 0, 'incomplete': 0, 'kids': set()})
    ratio = (c['incomplete'] / c['total'] * 100) if c['total'] else 0
    print(f'  {d}  total_rows={c["total"]:<4} distinct_people={len(c["kids"]):<4} '
          f'incomplete={c["incomplete"]:<4} ratio={ratio:.0f}%')

print('\nFor comparison, a NORMAL (non-flagged) recent June day:')
normal_days = sorted(d for d in by_date if d not in systemic_set and d <= yesterday)
for d in normal_days[-3:]:
    c = by_date[d]
    ratio = (c['incomplete'] / c['total'] * 100) if c['total'] else 0
    print(f'  {d}  total_rows={c["total"]:<4} distinct_people={len(c["kids"]):<4} '
          f'incomplete={c["incomplete"]:<4} ratio={ratio:.0f}%')