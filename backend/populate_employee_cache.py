"""
backend/populate_employee_cache.py
=====================================
The population job. Does the FULL computation (every KPI, every
employee) ONCE per month/year, then writes one row per (employee, KPI)
into employee_kpi_cache.py's table — instead of leaving that full
computation to happen on-demand every time someone clicks into an
employee's detail page (the 4-5 minute bug).

This reuses the EXACT same fetch()/aggregate() calls score_engine.py
already makes — same KPI classes, same SQL queries, same Keka
computation. Nothing about HOW scores are computed changes; only WHEN
(proactively, in the background) and WHERE THE RESULT IS STORED
(structured per-KPI rows instead of one big blob) changes.

USAGE:
    python populate_employee_cache.py                  # current month, current year
    python populate_employee_cache.py 5 2026            # specific month/year
    python populate_employee_cache.py --all-months 2026 # all 12 months of a year
    python populate_employee_cache.py --refresh-employee 303 5 2026  # one person only
"""

import sys
import time
sys.path.insert(0, '.')

import importlib
import local_db
from employee_kpi_cache import write_employee_kpi_row, clear_month, clear_employee

CONVERSION_KPI_KEYS = frozenset({'post_conversion', 'delayed_conversion', 'missing_status', 'reviews'})
ATTENDANCE_KPI_KEYS = frozenset({'leaves', 'late_comings', 'early_leavings', 'independence'})
_CONV_DEPTS = {'Conversion', 'Convert'}


def _nd(dept):
    if not dept:
        return None
    m = {'conversion': 'Conversion', 'convert': 'Conversion', 'it': 'IT', 'it department': 'IT',
         'email team': 'Email', 'email communication': 'Email', 'client communication': 'Communication',
         'accounting': 'Account', 'account': 'Account', 'human resources': 'HR', 'rnd': 'RND'}
    return m.get(dept.strip().lower(), dept.strip())


def _load(kpi):
    return getattr(importlib.import_module(kpi['module_path']), kpi['class_name'])()


def populate_month(month, year, clear_first=True):
    """
    Full population for one month: fetch every active KPI (same calls
    score_engine.calculate_scores() makes), then write one row per
    (employee, KPI) into employee_kpi_cache instead of returning a
    single combined blob.
    """
    print(f'\n[PopulateCache] {month}/{year} starting...')
    t0 = time.time()

    if clear_first:
        clear_month(month, year)
        print(f'[PopulateCache] Cleared existing rows for {month}/{year}')

    kpis = local_db.get_active_kpis()
    if not kpis:
        print('[PopulateCache] No active KPIs configured — nothing to do.')
        return

    kpi_data = {}
    by_emp_index = {}
    for kpi in kpis:
        t1 = time.time()
        try:
            inst = _load(kpi)
            rows = inst.fetch(month, year)
            print(f'[PopulateCache] {kpi["key"]} -> {len(rows)} rows ({round(time.time()-t1,2)}s)')
        except Exception as e:
            print(f'[PopulateCache] {kpi["key"]} FAILED: {e}')
            rows = []
            inst = _load(kpi)
        kpi_data[kpi['key']] = {'kpi': kpi, 'instance': inst, 'rows': rows}
        by_emp = {}
        for row in rows:
            aid = row.get('AdminID')
            if aid is not None:
                by_emp.setdefault(aid, []).append(row)
        by_emp_index[kpi['key']] = by_emp

    # Build the employee set + names/departments, same as score_engine.py
    employees = {}
    for kpi_key, data in kpi_data.items():
        for row in data['rows']:
            aid = row.get('AdminID')
            name = row.get('EmployeeName') or 'Unknown'
            dept = _nd(row.get('Department'))
            if aid is None:
                continue
            if aid not in employees:
                employees[aid] = {'admin_id': aid, 'employee_name': name, 'department': dept}
            if dept and not employees[aid].get('department'):
                employees[aid]['department'] = dept

    # Dedup: SAME logic as score_engine.py (confirmed fix: real AdminID
    # always preferred over synthetic, regardless of row count)
    name_to_ids = {}
    for aid, emp in employees.items():
        name = (emp.get('employee_name') or '').strip().lower()
        if name:
            name_to_ids.setdefault(name, []).append(aid)
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            kpi_counts = {aid: sum(len(by_emp_index.get(k, {}).get(aid, [])) for k in by_emp_index) for aid in ids}
            keep = max(ids, key=lambda a: (a > 0, kpi_counts[a], -abs(a)))
            for aid in ids:
                if aid != keep:
                    print(f'[PopulateCache] Dedup: drop AdminID={aid} ({employees[aid]["employee_name"]}) keep {keep}')
                    del employees[aid]

    # Conversion membership, same as score_engine.py
    conversion_ids = set()
    for kpi_key in CONVERSION_KPI_KEYS:
        for aid in by_emp_index.get(kpi_key, {}):
            conversion_ids.add(aid)
    for aid, emp in employees.items():
        if _nd(emp.get('department')) in _CONV_DEPTS:
            conversion_ids.add(aid)

    print(f'[PopulateCache] {len(employees)} employees '
          f'({len(conversion_ids)} conversion, {len(employees)-len(conversion_ids)} attendance-only)')

    # Write one row per (employee, KPI) — the actual point of this whole job
    written = 0
    for aid, emp in employees.items():
        is_conv = aid in conversion_ids
        active_kpis_for_person = kpis if is_conv else [k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]
        for kpi in active_kpis_for_person:
            kpi_key = kpi['key']
            emp_rows = by_emp_index.get(kpi_key, {}).get(aid, [])
            agg = kpi_data[kpi_key]['instance'].aggregate(emp_rows)

            if agg['success_ratio'] is None and kpi_key in {'leaves', 'late_comings', 'early_leavings'}:
                # Same fallback as score_engine.py
                from score_engine import _fallback_working_days
                wdays = _fallback_working_days(year, month)
                agg = {'numerator': wdays, 'denominator': wdays, 'success_ratio': 100.0,
                       'orders': [{'working_days': wdays, 'leave_days': 0, 'present_days': wdays,
                                   'late_days': 0, 'on_time_days': wdays, 'early_days': 0,
                                   'full_days': wdays, 'leave_dates': [], 'late_entries': [], 'early_entries': []}]}

            write_employee_kpi_row(
                admin_id=aid, month=month, year=year, kpi_key=kpi_key,
                employee_name=emp['employee_name'], department=emp.get('department'),
                is_conversion=is_conv, numerator=agg['numerator'], denominator=agg['denominator'],
                success_ratio=agg['success_ratio'], orders=agg.get('orders', [])[:30]
            )
            written += 1

    print(f'[PopulateCache] {month}/{year} done — {written} (employee, KPI) rows written '
          f'in {round(time.time()-t0,2)}s')


def refresh_one_employee(admin_id, month, year):
    """
    Single-employee refresh. Still has to call fetch() for each KPI
    (the underlying data source returns everyone's rows in one call —
    there's no cheaper per-employee fetch at the SQL/Keka level), but
    only writes/overwrites THIS person's rows, leaving everyone else's
    cached data for this month untouched.
    """
    print(f'\n[PopulateCache] Refreshing AdminID={admin_id} for {month}/{year}...')
    t0 = time.time()

    kpis = local_db.get_active_kpis()
    clear_employee(admin_id, month, year)

    is_conv = False
    conv_check_kpis = [k for k in kpis if k['key'] in CONVERSION_KPI_KEYS]
    for kpi in conv_check_kpis:
        inst = _load(kpi)
        rows = inst.fetch(month, year)
        if any(r.get('AdminID') == admin_id for r in rows):
            is_conv = True
            break

    active_kpis = kpis if is_conv else [k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]

    employee_name = None
    department = None
    written = 0
    for kpi in active_kpis:
        kpi_key = kpi['key']
        inst = _load(kpi)
        rows = inst.fetch(month, year)
        emp_rows = [r for r in rows if r.get('AdminID') == admin_id]
        if emp_rows and not employee_name:
            employee_name = emp_rows[0].get('EmployeeName', 'Unknown')
            department = _nd(emp_rows[0].get('Department'))
        agg = inst.aggregate(emp_rows)

        if agg['success_ratio'] is None and kpi_key in {'leaves', 'late_comings', 'early_leavings'}:
            from score_engine import _fallback_working_days
            wdays = _fallback_working_days(year, month)
            agg = {'numerator': wdays, 'denominator': wdays, 'success_ratio': 100.0,
                   'orders': [{'working_days': wdays, 'leave_days': 0, 'present_days': wdays,
                               'late_days': 0, 'on_time_days': wdays, 'early_days': 0,
                               'full_days': wdays, 'leave_dates': [], 'late_entries': [], 'early_entries': []}]}

        write_employee_kpi_row(
            admin_id=admin_id, month=month, year=year, kpi_key=kpi_key,
            employee_name=employee_name or 'Unknown', department=department,
            is_conversion=is_conv, numerator=agg['numerator'], denominator=agg['denominator'],
            success_ratio=agg['success_ratio'], orders=agg.get('orders', [])[:30]
        )
        written += 1

    print(f'[PopulateCache] Refreshed AdminID={admin_id}: {written} KPI rows '
          f'in {round(time.time()-t0,2)}s')


if __name__ == '__main__':
    if '--all-months' in sys.argv:
        idx = sys.argv.index('--all-months')
        year = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 else 2026
        for m in range(1, 13):
            populate_month(m, year)
    elif '--refresh-employee' in sys.argv:
        idx = sys.argv.index('--refresh-employee')
        admin_id = int(sys.argv[idx + 1])
        month = int(sys.argv[idx + 2])
        year = int(sys.argv[idx + 3])
        refresh_one_employee(admin_id, month, year)
    else:
        from datetime import date
        today = date.today()
        month = int(sys.argv[1]) if len(sys.argv) > 1 else today.month
        year = int(sys.argv[2]) if len(sys.argv) > 2 else today.year
        populate_month(month, year)