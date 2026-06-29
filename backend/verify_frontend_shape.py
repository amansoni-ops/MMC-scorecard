"""
verify_frontend_shape.py
===========================
Before touching any frontend file, this confirms exactly what shape of
data the new Keka-backed KPIs will hand to score_engine.py -> the API ->
the frontend, for a REAL person, side-by-side with what the OLD
ViaSocket-backed KPIs currently hand over for the same person.

This is the actual contract the frontend renders against. Run this and
paste the output before any EmployeeDetail.jsx change is made — that
way the frontend fix is based on the real before/after diff, not a
guess at what changed.
"""

import sys
sys.path.insert(0, '.')

TEST_ADMIN_ID = 346   # Ayushi Modi — confirmed real AdminID throughout this session
TEST_MONTH, TEST_YEAR = 5, 2026

print('=' * 78)
print('OLD (current live) KPI output shape — what the frontend renders TODAY')
print('=' * 78)
try:
    from kpis.leaves import LeavesKPI
    from kpis.late_comings import LateComingsKPI
    from kpis.early_leavings import EarlyLeavingsKPI

    for name, cls in [('leaves', LeavesKPI), ('late_comings', LateComingsKPI),
                       ('early_leavings', EarlyLeavingsKPI)]:
        inst = cls()
        rows = inst.fetch(TEST_MONTH, TEST_YEAR)
        emp_rows = [r for r in rows if r.get('AdminID') == TEST_ADMIN_ID]
        agg = inst.aggregate(emp_rows)
        print(f'\n--- OLD {name} ---')
        print(f'  numerator={agg["numerator"]}  denominator={agg["denominator"]}  '
              f'success_ratio={agg["success_ratio"]}')
        print(f'  orders[0] keys: {list(agg["orders"][0].keys()) if agg.get("orders") else "NO ORDERS"}')
        if agg.get('orders'):
            print(f'  orders[0] full: {agg["orders"][0]}')
except Exception as e:
    print(f'  ERROR loading old KPIs: {e}')

print('\n' + '=' * 78)
print('NEW (Keka-backed) KPI output shape — what frontend WOULD render if switched')
print('=' * 78)
try:
    from kpis.keka_attendance import KekaLeavesKPI, KekaLateComingsKPI, KekaEarlyLeavingsKPI

    for name, cls in [('keka_leaves', KekaLeavesKPI), ('keka_late_comings', KekaLateComingsKPI),
                       ('keka_early_leavings', KekaEarlyLeavingsKPI)]:
        inst = cls()
        rows = inst.fetch(TEST_MONTH, TEST_YEAR)
        emp_rows = [r for r in rows if r.get('AdminID') == TEST_ADMIN_ID]
        if not emp_rows:
            print(f'\n--- NEW {name} --- NO ROW for AdminID {TEST_ADMIN_ID} this month')
            continue
        agg = inst.aggregate(emp_rows)
        print(f'\n--- NEW {name} ---')
        print(f'  numerator={agg["numerator"]}  denominator={agg["denominator"]}  '
              f'success_ratio={agg["success_ratio"]}')
        print(f'  orders[0] keys: {list(agg["orders"][0].keys()) if agg.get("orders") else "NO ORDERS"}')
        if agg.get('orders'):
            print(f'  orders[0] full: {agg["orders"][0]}')
except Exception as e:
    print(f'  ERROR loading new KPIs: {e}')

print('\n' + '=' * 78)
print('FIELD-LEVEL DIFF — what keys exist in OLD orders[0] but NOT in NEW, and vice versa')
print('=' * 78)
print('(Paste full output above back — the actual diff will be read from it,')
print(' not computed here, since old/new field availability depends on live data)')