"""
trace_dedup_collision.py
============================
score_engine.py's dedup logic (from the actual file, confirmed earlier
this session):

    name_to_ids = {}
    for aid, emp in employees.items():
        name = (emp.get('employee_name') or '').strip().lower()
        if name:
            name_to_ids.setdefault(name, []).append(aid)
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            kpi_counts = {aid: sum(len(by_emp_index.get(k,{}).get(aid,[])) for k in by_emp_index) for aid in ids}
            keep = max(ids, key=lambda a: (kpi_counts[a], a > 0, -abs(a)))
            for aid in ids:
                if aid != keep:
                    del employees[aid]

This script finds a REAL person who currently has:
  - a real AdminID appearing in conversion KPI rows (post_conversion etc.)
  - a synthetic (negative) ID appearing in Keka attendance KPI rows
under the SAME normalized name, and traces exactly what `keep =
max(ids, key=...)` would select for them, using the REAL tie-break
formula: (kpi_counts[a], a > 0, -abs(a))

This does NOT modify score_engine.py or run the full engine — it
isolates and re-runs just the dedup decision logic against real data,
so the actual behavior can be seen before trusting it in production.
"""

import sys
sys.path.insert(0, '.')
from kpis.keka_attendance import KekaLeavesKPI, KekaLateComingsKPI, KekaEarlyLeavingsKPI
from kpis.post_conversion import PostConversionKPI

MONTH, YEAR = 5, 2026

print('Fetching real conversion KPI rows (post_conversion)...')
conv_rows = PostConversionKPI().fetch(MONTH, YEAR)
print(f'  {len(conv_rows)} rows')

print('Fetching ALL THREE Keka attendance KPIs together (the real post-switch scenario)...')
leaves_rows = KekaLeavesKPI().fetch(MONTH, YEAR)
late_rows   = KekaLateComingsKPI().fetch(MONTH, YEAR)
early_rows  = KekaEarlyLeavingsKPI().fetch(MONTH, YEAR)
print(f'  leaves={len(leaves_rows)}  late_comings={len(late_rows)}  early_leavings={len(early_rows)}')

# Build name -> set of AdminIDs seen, exactly like score_engine.py does,
# but across BOTH conversion and attendance sources
def norm(name):
    return (name or '').strip().lower()

name_to_ids = {}
admin_id_source = {}   # aid -> which KPI(s) it came from, for tracing

for r in conv_rows:
    aid = r.get('AdminID')
    name = norm(r.get('EmployeeName'))
    if aid is None or not name:
        continue
    name_to_ids.setdefault(name, set()).add(aid)
    admin_id_source.setdefault(aid, []).append('post_conversion')

for kpi_label, rows in [('keka_leaves', leaves_rows), ('keka_late_comings', late_rows),
                         ('keka_early_leavings', early_rows)]:
    for r in rows:
        aid = r.get('AdminID')
        name = norm(r.get('EmployeeName'))
        is_real = r.get('IsRealAdminID')
        if aid is None or not name:
            continue
        name_to_ids.setdefault(name, set()).add(aid)
        tag = f'{kpi_label}(real)' if is_real else f'{kpi_label}(SYNTHETIC)'
        admin_id_source.setdefault(aid, []).append(tag)

# Find names with MORE THAN ONE distinct AdminID across these two sources —
# this is exactly the collision scenario in question
collisions = {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}

print(f'\n{"="*78}')
print(f'COLLISION CASES — names with multiple AdminIDs across conversion + attendance')
print(f'{"="*78}')
print(f'Total collision names found: {len(collisions)}\n')

# Build kpi_counts the SAME way score_engine.py does: total row count
# across ALL kpi sources for that AdminID (here, just our 2 sources, but
# the principle is identical)
by_emp_index = {'post_conversion': {}, 'keka_leaves': {}, 'keka_late_comings': {}, 'keka_early_leavings': {}}
for r in conv_rows:
    aid = r.get('AdminID')
    if aid is not None:
        by_emp_index['post_conversion'].setdefault(aid, []).append(r)
for r in leaves_rows:
    aid = r.get('AdminID')
    if aid is not None:
        by_emp_index['keka_leaves'].setdefault(aid, []).append(r)
for r in late_rows:
    aid = r.get('AdminID')
    if aid is not None:
        by_emp_index['keka_late_comings'].setdefault(aid, []).append(r)
for r in early_rows:
    aid = r.get('AdminID')
    if aid is not None:
        by_emp_index['keka_early_leavings'].setdefault(aid, []).append(r)

for name, ids in list(collisions.items())[:15]:
    ids = list(ids)
    kpi_counts = {aid: sum(len(by_emp_index.get(k, {}).get(aid, [])) for k in by_emp_index) for aid in ids}

    # EXACT tie-break formula from score_engine.py
    keep = max(ids, key=lambda a: (kpi_counts[a], a > 0, -abs(a)))

    print(f'NAME: {name}')
    for aid in ids:
        marker = '  <-- KEPT' if aid == keep else '  <-- DROPPED'
        print(f'   AdminID={aid:<10} kpi_count={kpi_counts[aid]:<4} '
              f'sources={admin_id_source.get(aid, [])}{marker}')
    print()

if not collisions:
    print('No collisions found in this specific 2-KPI slice.')
    print('This does NOT mean no collision risk exists — it means none of')
    print('the people who currently have BOTH a post_conversion row AND a')
    print('keka_leaves row happen to share a normalized name across the two')
    print('different AdminIDs in this particular month\'s data. Re-run after')
    print('the full registry switch with ALL KPIs loaded for a complete check.')

# ── Specifically check: does the tie-break ever favor a SYNTHETIC id
#    over a REAL one? This is the actually dangerous case.
print(f'\n{"="*78}')
print('DANGEROUS CASE CHECK — would the formula ever KEEP a synthetic ID')
print('over a real one for the same person?')
print(f'{"="*78}')
dangerous = []
for name, ids in collisions.items():
    ids = list(ids)
    kpi_counts = {aid: sum(len(by_emp_index.get(k, {}).get(aid, [])) for k in by_emp_index) for aid in ids}
    keep = max(ids, key=lambda a: (kpi_counts[a], a > 0, -abs(a)))
    has_real = any(a > 0 for a in ids)
    has_synthetic = any(a < 0 for a in ids)
    if has_real and has_synthetic and keep < 0:
        dangerous.append((name, ids, keep, kpi_counts))

if dangerous:
    print(f'FOUND {len(dangerous)} case(s) where a synthetic ID would be KEPT')
    print('over a real one — this IS the collision bug, confirmed with real data:')
    for name, ids, keep, counts in dangerous:
        print(f'   {name}: ids={ids} kept={keep} counts={counts}')
else:
    print('None found in this data slice. The "a > 0" tie-break term means a')
    print('real (positive) AdminID is ALWAYS preferred over synthetic when kpi_counts')
    print('are tied — and only loses if the synthetic ID has a STRICTLY HIGHER')
    print('kpi_count. Check above whether any case had synthetic kpi_count >')
    print('real kpi_count even with zero dangerous cases — that gap is what to')
    print('watch once ALL KPIs (not just these 2) are loaded together.')