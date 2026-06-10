import importlib, time
from config import TIERS
import local_db

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
            # Keep: most KPI rows, prefer positive AdminID, prefer smaller ID (older = main account)
            keep = max(ids, key=lambda a: (kpi_counts[a], a > 0, -abs(a)))
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
            # No ViaSocket row = employee had zero issues = 100% perfect for that KPI
            if agg['success_ratio'] is None and kpi_key in {'leaves','late_comings','early_leavings'}:
                from viasocket import get_working_days as _gwd
                wdays=_gwd(year,month)
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
                from viasocket import get_working_days as _gwd
                wdays=_gwd(year,month)
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


