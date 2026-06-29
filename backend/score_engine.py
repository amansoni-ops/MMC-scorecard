###

import importlib, time
from config import TIERS
import local_db

from employee_kpi_cache import get_employee_kpi_rows, get_employee_trend

# ── Fallback working-days helper (replaces old viasocket.get_working_days)
# Used only when a person has ZERO rows in leaves/late_comings/early_leavings
# (i.e. they don't exist in keka_attendance.py's output at all). The old
# viasocket function did pure full-calendar-month math with no awareness of
# the current in-progress month, which produced a stale "26" for June while
# everyone with real Keka data correctly showed "20" (capped at yesterday).
from kpis.keka_attendance import _working_days as _keka_working_days, DEFAULT_OFF_DAYS
from datetime import date as _date, timedelta as _timedelta
import calendar as _calendar

def _fallback_working_days(year, month):
    """
    Last-resort working-days estimate for a person with no Keka data at
    all this month. Caps at YESTERDAY if year/month is the current,
    in-progress month (matching keka_attendance.py's own logic exactly).
    Uses Sunday-only (DEFAULT_OFF_DAYS) since there's no specific person
    here to look up a real weekly_off_policy for.
    """
    month_start = _date(year, month, 1)
    _, days_in_month = _calendar.monthrange(year, month)
    calendar_month_end = _date(year, month, days_in_month)

    today = _date.today()
    if year == today.year and month == today.month:
        month_end = min(calendar_month_end, today - _timedelta(days=1))
    else:
        month_end = calendar_month_end

    return _keka_working_days(month_start, month_end, off_days=DEFAULT_OFF_DAYS)


CONVERSION_KPI_KEYS = frozenset({'post_conversion','delayed_conversion','missing_status','reviews'})
ATTENDANCE_KPI_KEYS = frozenset({'leaves','late_comings','early_leavings','independence'})
_CONV_DEPTS         = {'Conversion','Convert'}

def _nd(dept):
    if not dept: return None
    m={'conversion':'Conversion','convert':'Conversion','it':'IT','it department':'IT',
       'email team':'Email','email communication':'Email','client communication':'Communication',
       'accounting':'Account','account':'Account','human resources':'HR','rnd':'RND'}
    return m.get(dept.strip().lower(), dept.strip())

def _get_tier(score):
    for t in TIERS:
        if t['min'] <= score <= t['max']:
            return {'grade':t['grade'],'label':t['label'],'color':t['color']}
    return {'grade':'C','label':'Needs Improvement','color':'#EF4444'}

def _load(kpi):
    return getattr(importlib.import_module(kpi['module_path']), kpi['class_name'])()

def _norm_weights(kpi_list):
    total = sum(k['raw_weight'] for k in kpi_list)
    return {k['key']: (k['raw_weight']/total*100) if total else 0 for k in kpi_list}

def calculate_scores(month, year):
    print(f'\n[ScoreEngine] {month}/{year} starting…')
    t0   = time.time()
    kpis = local_db.get_active_kpis()
    if not kpis: return []

    kpi_data = {}; by_emp_index = {}
    for kpi in kpis:
        print(f'[ScoreEngine] Fetching {kpi["key"]}…')
        t1 = time.time()
        try:
            inst = _load(kpi); rows = inst.fetch(month, year)
            print(f'[ScoreEngine] {kpi["key"]} → {len(rows)} rows ({round(time.time()-t1,2)}s)')
        except Exception as e:
            print(f'[ScoreEngine] {kpi["key"]} FAILED: {e}'); rows=[]; inst=_load(kpi)
        kpi_data[kpi['key']] = {'kpi':kpi,'instance':inst,'rows':rows}
        by_emp = {}
        for row in rows:
            aid = row.get('AdminID')
            if aid is not None: by_emp.setdefault(aid,[]).append(row)
        by_emp_index[kpi['key']] = by_emp

    employees = {}
    for kpi_key, data in kpi_data.items():
        for row in data['rows']:
            aid=row.get('AdminID'); name=row.get('EmployeeName') or 'Unknown'; dept=_nd(row.get('Department'))
            if aid is None: continue
            if aid not in employees:
                employees[aid]={'admin_id':aid,'employee_name':name,'department':dept,'kpi_breakdown':{}}
            if dept and not employees[aid].get('department'):
                employees[aid]['department']=dept
    if not employees: print('[ScoreEngine] No employees.'); return []

    # ── Deduplicate: same name but multiple AdminIDs = inactive duplicate accounts
    # Keep the ID with the most KPI data (the real active account)
    name_to_ids = {}
    for aid, emp in employees.items():
        name = (emp.get('employee_name') or '').strip().lower()
        if name:
            name_to_ids.setdefault(name, []).append(aid)
    for name, ids in name_to_ids.items():
        if len(ids) > 1:
            kpi_counts = {aid: sum(len(by_emp_index.get(k,{}).get(aid,[])) for k in by_emp_index) for aid in ids}
            # Keep: ALWAYS prefer a real (positive) AdminID over a synthetic
            # (negative) one, regardless of row count — a synthetic ID is a
            # Keka-only employee not yet linked to SQL Server, and should
            # never be allowed to "outvote" a real SQL Server identity just
            # because it happens to have more attendance rows this month.
            # Only when BOTH candidates are the same type does row count,
            # then ID value, break the tie. Confirmed via
            # trace_dedup_collision.py against real May 2026 data.
            keep = max(ids, key=lambda a: (a > 0, kpi_counts[a], -abs(a)))
            for aid in ids:
                if aid != keep:
                    print(f'[ScoreEngine] Dedup: drop AdminID={aid} ({employees[aid]["employee_name"]}) keep {keep}')
                    del employees[aid]

    # Build conversion set GLOBALLY
    conversion_ids = set()
    for kpi_key in CONVERSION_KPI_KEYS:
        for aid in by_emp_index.get(kpi_key,{}): conversion_ids.add(aid)
    for aid,emp in employees.items():
        if _nd(emp.get('department')) in _CONV_DEPTS: conversion_ids.add(aid)
    print(f'[ScoreEngine] Conversion:{len(conversion_ids)} | Attendance-only:{len(employees)-len(conversion_ids)}')

    conv_kpis=kpis; att_kpis=[k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]
    conv_w=_norm_weights(conv_kpis); att_w=_norm_weights(att_kpis)

    for aid,emp in employees.items():
        is_conv=aid in conversion_ids; active_kpis=conv_kpis if is_conv else att_kpis
        weights=conv_w if is_conv else att_w; emp['is_conversion']=is_conv
        for kpi in active_kpis:
            kpi_key=kpi['key']; emp_rows=by_emp_index.get(kpi_key,{}).get(aid,[])
            agg=kpi_data[kpi_key]['instance'].aggregate(emp_rows)
            # No data for this person in this KPI = fall back to a neutral
            # "100% perfect" placeholder rather than showing blank, but use
            # the current-month-aware working-days helper, not the stale
            # full-calendar-month one.
            if agg['success_ratio'] is None and kpi_key in {'leaves','late_comings','early_leavings'}:
                wdays=_fallback_working_days(year,month)
                agg={'numerator':wdays,'denominator':wdays,'success_ratio':100.0,
                     'orders':[{'working_days':wdays,'leave_days':0,'present_days':wdays,
                                'late_days':0,'on_time_days':wdays,'early_days':0,
                                'full_days':wdays,'leave_dates':[],'late_entries':[],'early_entries':[]}]}
            w=weights[kpi_key]
            score=round(agg['success_ratio']*w/100,4) if agg['success_ratio'] is not None else None
            emp['kpi_breakdown'][kpi_key]={'name':kpi['name'],'description':kpi.get('description',''),
                'raw_weight':kpi['raw_weight'],'weight':round(w,2),'numerator':agg['numerator'],
                'denominator':agg['denominator'],'success_ratio':agg['success_ratio'],
                'score':score,'orders':agg.get('orders',[])[:30]}

    result=[]
    for aid,emp in employees.items():
        sc=[kb['score'] for kb in emp['kpi_breakdown'].values() if kb['score'] is not None]
        emp['total_score']=round(sum(sc),2) if sc else 0.0; emp['tier']=_get_tier(emp['total_score'])
        result.append(emp)
    result.sort(key=lambda e:e['total_score'],reverse=True)
    print(f'[ScoreEngine] Done — {len(result)} employees in {round(time.time()-t0,2)}s\n')
    return result

def get_employee_detail(admin_id, month, year):
    kpis=local_db.get_active_kpis()
    if not kpis: return None
    conversion_ids=set(); cache={}
    for kpi in kpis:
        if kpi['key'] in CONVERSION_KPI_KEYS:
            try:
                inst=_load(kpi); rows=inst.fetch(month,year)
                for r in rows:
                    if r.get('AdminID'): conversion_ids.add(r['AdminID'])
                cache[kpi['key']]=(inst,rows)
            except: pass
    is_conv=admin_id in conversion_ids
    active_kpis=kpis if is_conv else [k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]
    weights=_norm_weights(active_kpis)
    result={'admin_id':admin_id,'kpi_breakdown':{},'is_conversion':is_conv}
    for kpi in active_kpis:
        kpi_key=kpi['key']
        try:
            if kpi_key in cache: inst,rows=cache[kpi_key]
            else: inst=_load(kpi); rows=inst.fetch(month,year)
            emp_rows=[r for r in rows if r.get('AdminID')==admin_id]
            if emp_rows and not result.get('employee_name'):
                result['employee_name']=emp_rows[0].get('EmployeeName','Unknown')
                result['department']=_nd(emp_rows[0].get('Department'))
            agg=inst.aggregate(emp_rows)
            if agg['success_ratio'] is None and kpi_key in {'leaves','late_comings','early_leavings'}:
                wdays=_fallback_working_days(year,month)
                agg={'numerator':wdays,'denominator':wdays,'success_ratio':100.0,
                     'orders':[{'working_days':wdays,'leave_days':0,'present_days':wdays,
                                'late_days':0,'on_time_days':wdays,'early_days':0,
                                'full_days':wdays,'leave_dates':[],'late_entries':[],'early_entries':[]}]}
            w=weights[kpi_key]
            score=round(agg['success_ratio']*w/100,4) if agg['success_ratio'] is not None else None
            result['kpi_breakdown'][kpi_key]={'name':kpi['name'],'description':kpi.get('description',''),
                'weight':round(w,2),'numerator':agg['numerator'],'denominator':agg['denominator'],
                'success_ratio':agg['success_ratio'],'score':score,'orders':agg.get('orders',[])}
        except Exception as e: print(f'[ScoreEngine] detail {kpi_key}: {e}')
    sc=[kb['score'] for kb in result['kpi_breakdown'].values() if kb['score'] is not None]
    result['total_score']=round(sum(sc),2) if sc else 0.0; result['tier']=_get_tier(result['total_score'])
    return result if result.get('employee_name') else None

# SCORE_ENGINE.PY — ADD THESE NEW FUNCTIONS
# ================================================================
# These are ADDITIONS, not replacements of calculate_scores() (the main
# dashboard list still works the way it does today — only the SLOW
# single-employee path and the trend chart get rewritten). Add this near
# the bottom of score_engine.py, after the existing functions.

# ------------------------------------------------------------------------



def get_employee_detail_fast(admin_id, month, year):
    """
    FAST replacement for get_employee_detail(). Reads pre-computed
    per-KPI rows from employee_kpi_cache (populated by
    populate_employee_cache.py in the background) instead of calling
    fetch() on every KPI for every employee just to extract one row.

    Falls back to the OLD slow path automatically if this employee has
    no cached rows yet for this month (e.g. population job hasn't run
    yet, or this is a brand-new employee) — so nothing breaks, it's
    just slow on a true cache-miss, exactly like before.
    """
    cached_rows = get_employee_kpi_rows(admin_id, month, year)

    if not cached_rows:
        print(f'[ScoreEngine] No cached rows for AdminID={admin_id} {month}/{year} '
              f'— falling back to live computation (slow path)')
        return get_employee_detail(admin_id, month, year)   # old function, unchanged

    is_conv = cached_rows[0]['is_conversion']
    active_kpis = local_db.get_active_kpis()
    relevant_kpis = active_kpis if is_conv else [k for k in active_kpis if k['key'] in ATTENDANCE_KPI_KEYS]
    weights = _norm_weights(relevant_kpis)

    by_kpi_key = {r['kpi_key']: r for r in cached_rows}

    result = {
        'admin_id': admin_id,
        'employee_name': cached_rows[0]['employee_name'],
        'department': cached_rows[0]['department'],
        'is_conversion': is_conv,
        'kpi_breakdown': {},
    }

    kpi_meta = {k['key']: k for k in active_kpis}

    for kpi in relevant_kpis:
        kpi_key = kpi['key']
        row = by_kpi_key.get(kpi_key)
        if not row:
            continue   # this KPI has no cached row for this person (rare — KPI added after population ran)

        w = weights[kpi_key]
        score = round(row['success_ratio'] * w / 100, 4) if row['success_ratio'] is not None else None

        result['kpi_breakdown'][kpi_key] = {
            'name': kpi['name'],
            'description': kpi.get('description', ''),
            'weight': round(w, 2),
            'numerator': row['numerator'],
            'denominator': row['denominator'],
            'success_ratio': row['success_ratio'],
            'failure_ratio': row['failure_ratio'],   # NEW — precomputed, no inline 100-x needed in frontend
            'score': score,
            'orders': row['orders'],
        }

    sc = [kb['score'] for kb in result['kpi_breakdown'].values() if kb['score'] is not None]
    result['total_score'] = round(sum(sc), 2) if sc else 0.0
    result['tier'] = _get_tier(result['total_score'])
    return result


def get_employee_trend_fast(admin_id, year):
    """
    FAST replacement for whatever currently powers the year-trend
    chart. Reads cached rows for every month of the year and computes
    each month's total_score using CURRENT kpi weights — so the trend
    line reflects live KPI toggle state, not whatever weights were
    active when each month was originally populated.
    """
    by_month = get_employee_trend(admin_id, year)   # {month: {kpi_key: success_ratio}}
    active_kpis = local_db.get_active_kpis()

    trend = []
    for month in range(1, 13):
        month_data = by_month.get(month)
        if not month_data:
            trend.append({'month': month, 'total_score': None})
            continue

        # Determine conversion membership for THIS month from cache,
        # since weight normalization differs for conversion vs
        # attendance-only employees.
        is_conv_kpis = {k for k in CONVERSION_KPI_KEYS if k in month_data}
        is_conv = len(is_conv_kpis) > 0
        relevant_kpis = active_kpis if is_conv else [k for k in active_kpis if k['key'] in ATTENDANCE_KPI_KEYS]
        weights = _norm_weights(relevant_kpis)

        total = 0.0
        any_score = False
        for kpi in relevant_kpis:
            kpi_key = kpi['key']
            if kpi_key in month_data and month_data[kpi_key] is not None:
                total += month_data[kpi_key] * weights[kpi_key] / 100
                any_score = True

        trend.append({'month': month, 'total_score': round(total, 2) if any_score else None})

    return trend

# import importlib, time
# from config import TIERS
# import local_db

# CONVERSION_KPI_KEYS = frozenset({'post_conversion','delayed_conversion','missing_status','reviews'})
# ATTENDANCE_KPI_KEYS = frozenset({'leaves','late_comings','early_leavings','independence'})
# _CONV_DEPTS         = {'Conversion','Convert'}

# def _nd(dept):
#     if not dept: return None
#     m={'conversion':'Conversion','convert':'Conversion','it':'IT','it department':'IT',
#        'email team':'Email','email communication':'Email','client communication':'Communication',
#        'accounting':'Account','account':'Account','human resources':'HR','rnd':'RND'}
#     return m.get(dept.strip().lower(), dept.strip())

# def _get_tier(score):
#     for t in TIERS:
#         if t['min'] <= score <= t['max']:
#             return {'grade':t['grade'],'label':t['label'],'color':t['color']}
#     return {'grade':'C','label':'Needs Improvement','color':'#EF4444'}

# def _load(kpi):
#     return getattr(importlib.import_module(kpi['module_path']), kpi['class_name'])()

# def _norm_weights(kpi_list):
#     total = sum(k['raw_weight'] for k in kpi_list)
#     return {k['key']: (k['raw_weight']/total*100) if total else 0 for k in kpi_list}

# def calculate_scores(month, year):
#     print(f'\n[ScoreEngine] {month}/{year} starting…')
#     t0   = time.time()
#     kpis = local_db.get_active_kpis()
#     if not kpis: return []

#     kpi_data = {}; by_emp_index = {}
#     for kpi in kpis:
#         print(f'[ScoreEngine] Fetching {kpi["key"]}…')
#         t1 = time.time()
#         try:
#             inst = _load(kpi); rows = inst.fetch(month, year)
#             print(f'[ScoreEngine] {kpi["key"]} → {len(rows)} rows ({round(time.time()-t1,2)}s)')
#         except Exception as e:
#             print(f'[ScoreEngine] {kpi["key"]} FAILED: {e}'); rows=[]; inst=_load(kpi)
#         kpi_data[kpi['key']] = {'kpi':kpi,'instance':inst,'rows':rows}
#         by_emp = {}
#         for row in rows:
#             aid = row.get('AdminID')
#             if aid is not None: by_emp.setdefault(aid,[]).append(row)
#         by_emp_index[kpi['key']] = by_emp

#     employees = {}
#     for kpi_key, data in kpi_data.items():
#         for row in data['rows']:
#             aid=row.get('AdminID'); name=row.get('EmployeeName') or 'Unknown'; dept=_nd(row.get('Department'))
#             if aid is None: continue
#             if aid not in employees:
#                 employees[aid]={'admin_id':aid,'employee_name':name,'department':dept,'kpi_breakdown':{}}
#             if dept and not employees[aid].get('department'):
#                 employees[aid]['department']=dept
#     if not employees: print('[ScoreEngine] No employees.'); return []

#     # Build conversion set GLOBALLY
#     conversion_ids = set()
#     for kpi_key in CONVERSION_KPI_KEYS:
#         for aid in by_emp_index.get(kpi_key,{}): conversion_ids.add(aid)
#     for aid,emp in employees.items():
#         if _nd(emp.get('department')) in _CONV_DEPTS: conversion_ids.add(aid)
#     print(f'[ScoreEngine] Conversion:{len(conversion_ids)} | Attendance-only:{len(employees)-len(conversion_ids)}')

#     conv_kpis=kpis; att_kpis=[k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]
#     conv_w=_norm_weights(conv_kpis); att_w=_norm_weights(att_kpis)

#     for aid,emp in employees.items():
#         is_conv=aid in conversion_ids; active_kpis=conv_kpis if is_conv else att_kpis
#         weights=conv_w if is_conv else att_w; emp['is_conversion']=is_conv
#         for kpi in active_kpis:
#             kpi_key=kpi['key']; emp_rows=by_emp_index.get(kpi_key,{}).get(aid,[])
#             agg=kpi_data[kpi_key]['instance'].aggregate(emp_rows); w=weights[kpi_key]
#             score=round(agg['success_ratio']*w/100,4) if agg['success_ratio'] is not None else None
#             emp['kpi_breakdown'][kpi_key]={'name':kpi['name'],'description':kpi.get('description',''),
#                 'raw_weight':kpi['raw_weight'],'weight':round(w,2),'numerator':agg['numerator'],
#                 'denominator':agg['denominator'],'success_ratio':agg['success_ratio'],
#                 'score':score,'orders':agg.get('orders',[])[:30]}

#     result=[]
#     for aid,emp in employees.items():
#         sc=[kb['score'] for kb in emp['kpi_breakdown'].values() if kb['score'] is not None]
#         emp['total_score']=round(sum(sc),2) if sc else 0.0; emp['tier']=_get_tier(emp['total_score'])
#         result.append(emp)
#     result.sort(key=lambda e:e['total_score'],reverse=True)
#     print(f'[ScoreEngine] Done — {len(result)} employees in {round(time.time()-t0,2)}s\n')
#     return result

# def get_employee_detail(admin_id, month, year):
#     kpis=local_db.get_active_kpis()
#     if not kpis: return None
#     conversion_ids=set(); cache={}
#     for kpi in kpis:
#         if kpi['key'] in CONVERSION_KPI_KEYS:
#             try:
#                 inst=_load(kpi); rows=inst.fetch(month,year)
#                 for r in rows:
#                     if r.get('AdminID'): conversion_ids.add(r['AdminID'])
#                 cache[kpi['key']]=(inst,rows)
#             except: pass
#     is_conv=admin_id in conversion_ids
#     active_kpis=kpis if is_conv else [k for k in kpis if k['key'] in ATTENDANCE_KPI_KEYS]
#     weights=_norm_weights(active_kpis)
#     result={'admin_id':admin_id,'kpi_breakdown':{},'is_conversion':is_conv}
#     for kpi in active_kpis:
#         kpi_key=kpi['key']
#         try:
#             if kpi_key in cache: inst,rows=cache[kpi_key]
#             else: inst=_load(kpi); rows=inst.fetch(month,year)
#             emp_rows=[r for r in rows if r.get('AdminID')==admin_id]
#             if emp_rows and not result.get('employee_name'):
#                 result['employee_name']=emp_rows[0].get('EmployeeName','Unknown')
#                 result['department']=_nd(emp_rows[0].get('Department'))
#             agg=inst.aggregate(emp_rows); w=weights[kpi_key]
#             score=round(agg['success_ratio']*w/100,4) if agg['success_ratio'] is not None else None
#             result['kpi_breakdown'][kpi_key]={'name':kpi['name'],'description':kpi.get('description',''),
#                 'weight':round(w,2),'numerator':agg['numerator'],'denominator':agg['denominator'],
#                 'success_ratio':agg['success_ratio'],'score':score,'orders':agg.get('orders',[])}
#         except Exception as e: print(f'[ScoreEngine] detail {kpi_key}: {e}')
#     sc=[kb['score'] for kb in result['kpi_breakdown'].values() if kb['score'] is not None]
#     result['total_score']=round(sum(sc),2) if sc else 0.0; result['tier']=_get_tier(result['total_score'])
#     return result if result.get('employee_name') else None


