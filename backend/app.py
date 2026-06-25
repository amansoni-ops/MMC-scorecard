from flask import Flask, request, jsonify, session
from flask_cors import CORS
from datetime import datetime
import threading
import local_db
import cache as score_cache
import score_engine
import keka_scheduler

local_db.init_db()

from config import FLASK_SECRET
app = Flask(__name__)
app.secret_key = FLASK_SECRET
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE']   = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_PATH']     = '/'

CORS(app, supports_credentials=True,
     origins=['http://localhost:5173','http://127.0.0.1:5173',
               'http://localhost:3000','http://127.0.0.1:5000'])

score_cache.start_scheduler()
keka_scheduler.start_scheduler()
_preview_tasks = {}
_preview_lock  = threading.Lock()

def _auth_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a,**k):
        if not session.get('user'): return jsonify({'error':'Unauthorized'}),401
        return f(*a,**k)
    return w

def _admin_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a,**k):
        if session.get('user',{}).get('role')!='admin': return jsonify({'error':'Admin only'}),403
        return f(*a,**k)
    return w

# ── Auth ───────────────────────────────────────────────────────────────────
@app.post('/api/login')
def login_route():
    body=request.get_json() or {}
    user=local_db.verify_user(body.get('username',''),body.get('password',''))
    if not user: return jsonify({'error':'Invalid credentials'}),401
    session['user']=user; session.permanent=True
    return jsonify({'user':user})

@app.post('/api/logout')
def logout_route():
    session.clear(); return jsonify({'ok':True})

@app.get('/api/me')
@_auth_required
def me(): return jsonify({'user':session['user']})

# ── Scores ─────────────────────────────────────────────────────────────────
@app.get('/api/scores')
@_auth_required
def scores():
    now=datetime.now()
    month=int(request.args.get('month',now.month))
    year =int(request.args.get('year', now.year))
    data=score_cache.load(month,year)
    return jsonify({'month':month,'year':year,'employees':data})

@app.get('/api/scores/<int:admin_id>')
@_auth_required
def employee_score(admin_id):
    now=datetime.now()
    month=int(request.args.get('month',now.month))
    year =int(request.args.get('year', now.year))
    detail=score_engine.get_employee_detail(admin_id,month,year)
    if not detail: return jsonify({'error':'Not found'}),404
    detail['note']=local_db.get_note(admin_id,month,year)
    return jsonify(detail)

@app.get('/api/scores/<int:admin_id>/trend')
@_auth_required
def employee_trend(admin_id):
    now=datetime.now()
    year=int(request.args.get('year',now.year))
    trend=[]
    for m in range(1,13):
        if year==now.year and m>now.month: break
        try:
            data=score_cache.load(m,year)
            emp=next((e for e in data if e['admin_id']==admin_id),None)
            kpi_map={k:{'score':v['score'],'success_ratio':v['success_ratio']}
                     for k,v in (emp['kpi_breakdown'].items() if emp else {})}
            trend.append({'month':m,'year':year,
                'total_score':emp['total_score'] if emp else None,
                'tier':emp['tier']['grade'] if emp else None,'kpis':kpi_map})
        except:
            trend.append({'month':m,'year':year,'total_score':None,'tier':None,'kpis':{}})
    return jsonify({'admin_id':admin_id,'year':year,'trend':trend})

# ── Preview ─────────────────────────────────────────────────────────────────
@app.post('/api/preview/start')
@_auth_required
def preview_start():
    year=int(request.args.get('year',2026)); now=datetime.now()
    months=[m for m in range(1,13) if not (year==now.year and m>now.month)]
    with _preview_lock:
        if _preview_tasks.get(year,{}).get('running'):
            return jsonify({'ok':True,'already_running':True,'months':months})
        _preview_tasks[year]={'running':True,'months':months,'done':[],'errors':[],'current':None}
    def _compute():
        for month in months:
            with _preview_lock:
                if not _preview_tasks[year].get('running'): break
                _preview_tasks[year]['current']=month
            try:
                score_cache.load(month,year)
                with _preview_lock: _preview_tasks[year]['done'].append(month)
            except:
                with _preview_lock: _preview_tasks[year]['errors'].append(month)
        with _preview_lock: _preview_tasks[year]['running']=False; _preview_tasks[year]['current']=None
    threading.Thread(target=_compute,daemon=True,name=f'preview-{year}').start()
    return jsonify({'ok':True,'months':months,'year':year})

@app.get('/api/preview/status')
@_auth_required
def preview_status():
    year=int(request.args.get('year',2026))
    with _preview_lock:
        t=_preview_tasks.get(year)
        if not t: return jsonify({'running':False,'months':[],'done':[],'errors':[],'current':None,'year':year})
        return jsonify({'year':year,'running':t['running'],'months':t['months'],
            'done':t['done'][:],'errors':t['errors'][:],'current':t['current']})

@app.delete('/api/preview/stop')
@_auth_required
def preview_stop():
    year=int(request.args.get('year',2026))
    with _preview_lock:
        if year in _preview_tasks: _preview_tasks[year]['running']=False
    return jsonify({'ok':True})

# ── KPIs ───────────────────────────────────────────────────────────────────
@app.get('/api/kpis')
@_auth_required
def get_kpis():
    kpis=local_db.get_all_kpis(); active=[k for k in kpis if k['is_active']]
    total=sum(k['raw_weight'] for k in active)
    for k in kpis:
        k['normalized_weight']=round(k['raw_weight']/total*100,2) if total and k['is_active'] else 0
    return jsonify({'kpis':kpis})

@app.put('/api/kpis')
@_auth_required
@_admin_required
def update_kpis_bulk():
    kpis=(request.get_json() or {}).get('kpis',[])
    if not kpis: return jsonify({'error':'No KPIs provided'}),400
    username=session['user']['username']
    for k in kpis:
        key=k.get('key'); weight=float(k.get('raw_weight',0)); active=int(bool(k.get('is_active',False)))
        if not key: continue
        if weight>0: local_db.update_kpi_weight(key,weight,username)
        local_db.toggle_kpi(key,active,username)
    score_cache.invalidate()
    return jsonify({'ok':True,'updated':len(kpis)})

@app.put('/api/kpis/<key>/weight')
@_auth_required
@_admin_required
def update_weight(key):
    w=float((request.get_json() or {}).get('weight',0))
    if w<=0: return jsonify({'error':'Weight must be > 0'}),400
    local_db.update_kpi_weight(key,w,session['user']['username'])
    score_cache.invalidate(); return jsonify({'ok':True})

@app.put('/api/kpis/<key>/toggle')
@_auth_required
@_admin_required
def toggle_kpi(key):
    on=int(bool((request.get_json() or {}).get('is_active',True)))
    local_db.toggle_kpi(key,on,session['user']['username'])
    score_cache.invalidate(); return jsonify({'ok':True})

# ── Independence ─────────────────────────────────────────────────────────────
@app.get('/api/independence')
@_auth_required
def get_all_independence():
    now=datetime.now()
    month=int(request.args.get('month',now.month)); year=int(request.args.get('year',now.year))
    from kpis.independence import get_all_ratings,RATING_PCT
    return jsonify({'month':month,'year':year,'ratings':get_all_ratings(month,year),
        'options':list(RATING_PCT.keys()),'option_pcts':RATING_PCT})

@app.get('/api/independence/<int:admin_id>')
@_auth_required
def get_independence(admin_id):
    now=datetime.now()
    month=int(request.args.get('month',now.month)); year=int(request.args.get('year',now.year))
    from kpis.independence import get_rating
    return jsonify({'admin_id':admin_id,'month':month,'year':year,'rating':get_rating(admin_id,month,year)})

@app.put('/api/independence/<int:admin_id>')
@_auth_required
@_admin_required
def set_independence(admin_id):
    body=request.get_json() or {}; rating=body.get('rating','').strip()
    month=int(body.get('month',datetime.now().month)); year=int(body.get('year',datetime.now().year))
    if not rating: return jsonify({'error':'rating required'}),400
    try:
        from kpis.independence import set_rating
        set_rating(admin_id,month,year,rating,session['user']['username'])
        score_cache.invalidate(month,year)
        return jsonify({'ok':True,'admin_id':admin_id,'rating':rating})
    except ValueError as e: return jsonify({'error':str(e)}),400

# ── Attendance ─────────────────────────────────────────────────────────────
@app.get('/api/attendance/preview')
@_auth_required
def attendance_preview():
    now=datetime.now()
    month=int(request.args.get('month',now.month)); year=int(request.args.get('year',now.year))
    try:
        from viasocket import get_leaves_for_month
        from name_mapper import resolve,init_name_map_table
        init_name_map_table(); rows=get_leaves_for_month(month,year); result=[]
        for row in rows:
            name=(row.get('name') or '').strip(); mapped=resolve(name) if name else {}
            result.append({'viasocket_name':name,'admin_id':mapped.get('admin_id'),
                'sql_admin_name':mapped.get('sql_admin_name'),'match_method':mapped.get('match_method'),
                'department':row.get('dept_normalized'),'leave_count':row.get('month_leave_count',0),
                'leave_dates':row.get('month_leave_dates',[])})
        return jsonify({'month':month,'year':year,'count':len(result),'employees':result})
    except Exception as e: return jsonify({'error':str(e)}),500

@app.get('/api/attendance/name-map')
@_auth_required
@_admin_required
def get_name_map():
    from name_mapper import get_all_mappings
    return jsonify({'mappings':get_all_mappings()})

@app.post('/api/attendance/name-map')
@_auth_required
@_admin_required
def set_name_mapping():
    body=request.get_json() or {}; vs_name=body.get('viasocket_name','').strip(); admin_id=body.get('admin_id')
    if not vs_name or not admin_id: return jsonify({'error':'viasocket_name and admin_id required'}),400
    from name_mapper import set_manual_mapping
    set_manual_mapping(vs_name,int(admin_id),body.get('department'))
    return jsonify({'ok':True,'viasocket_name':vs_name,'admin_id':admin_id})


# ── 1. Full monthly attendance data (cached) ───────────────────────────────────
@app.route('/api/keka/attendance', methods=['GET'])
def keka_attendance():
    month = request.args.get('month', type=int)
    year  = request.args.get('year', type=int)
    department = request.args.get('department')
 
    if not month or not year:
        return jsonify({'error': 'month and year are required'}), 400
 
    data = get_attendance_data(month, year)
 
    if department and department.lower() != 'all':
        data = {
            **data,
            'employees': [e for e in data['employees'] if e['department'] == department]
        }
 
    return jsonify(data)
 
 
# ── 2. Single employee attendance (for employee detail page) ──────────────────
@app.route('/api/keka/attendance/<keka_id>', methods=['GET'])
def keka_employee_attendance(keka_id):
    month = request.args.get('month', type=int)
    year  = request.args.get('year', type=int)
 
    if not month or not year:
        return jsonify({'error': 'month and year are required'}), 400
 
    record = get_employee_attendance(month, year, keka_id)
    if record is None:
        return jsonify({'error': 'employee not found for this month'}), 404
 
    return jsonify(record)
 
 
# ── 3. Active users headline number (for dashboard top card) ──────────────────
@app.route('/api/keka/active-users', methods=['GET'])
def keka_active_users():
    month = request.args.get('month', type=int)
    year  = request.args.get('year', type=int)
 
    active, total = get_active_users_count(month, year)
    return jsonify({'active': active, 'total': total})
 
 
# ── 4. Force-refresh one month's cache (manual trigger / admin button) ────────
@app.route('/api/keka/refresh', methods=['POST'])
def keka_refresh():
    month = request.json.get('month') if request.json else request.args.get('month', type=int)
    year  = request.json.get('year') if request.json else request.args.get('year', type=int)
 
    if not month or not year:
        return jsonify({'error': 'month and year are required'}), 400
 
    data = refresh_attendance_cache(month, year)
    return jsonify({
        'status': 'refreshed',
        'month': month,
        'year': year,
        'employee_count': len(data['employees']),
    })

# ── DB Health ─────────────────────────────────────────────────────────────
@app.get('/api/health/db')
@_auth_required
def db_health():
    import time as _t; result={'sqlite':False,'sqlserver':False,'detail':{}}
    t0=_t.time()
    try:
        import sqlite3,os; conn=sqlite3.connect(os.path.join(os.path.dirname(__file__),'scorecard.db'),timeout=3)
        conn.execute('SELECT 1'); conn.close(); result['sqlite']=True
        result['detail']['sqlite_ms']=round((_t.time()-t0)*1000)
    except Exception as e: result['detail']['sqlite_error']=str(e)
    t1=_t.time()
    try:
        from db import get_connection; conn=get_connection(); cur=conn.cursor()
        cur.execute('SELECT 1'); cur.fetchone(); conn.close(); result['sqlserver']=True
        result['detail']['sqlserver_ms']=round((_t.time()-t1)*1000)
    except Exception as e: result['detail']['sqlserver_error']=str(e)[:120]
    return jsonify(result)

# ── Notes & Cache ─────────────────────────────────────────────────────────
@app.get('/api/notes/<int:admin_id>')
@_auth_required
def get_note(admin_id):
    now=datetime.now()
    return jsonify({'note':local_db.get_note(admin_id,
        int(request.args.get('month',now.month)),int(request.args.get('year',now.year)))})

@app.post('/api/notes/<int:admin_id>')
@_auth_required
def save_note(admin_id):
    now=datetime.now(); body=request.get_json() or {}
    local_db.upsert_note(admin_id,int(request.args.get('month',now.month)),
        int(request.args.get('year',now.year)),body.get('note_text',''),session['user']['username'])
    return jsonify({'ok':True})

@app.get('/api/cache/status')
@_auth_required
def cache_status(): return jsonify(score_cache.status())

@app.post('/api/cache/refresh')
@_auth_required
def cache_refresh():
    now=datetime.now()
    m=int(request.args.get('month',now.month)); y=int(request.args.get('year',now.year))
    score_cache.invalidate(m,y); score_cache.preload_async(m,y)
    return jsonify({'ok':True})

@app.get('/api/health')
def health(): return jsonify({'status':'ok','ts':datetime.now().isoformat()})

if __name__=='__main__':
    app.run(debug=True,port=5000,host='127.0.0.1',use_reloader=False,threaded=True)
