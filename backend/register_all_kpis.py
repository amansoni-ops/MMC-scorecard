"""
Run once: cd scorecard/backend && python register_all_kpis.py
"""
import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), 'scorecard.db')

KPIS = [
    ('post_conversion',    'Post Conversion Issues',        'Files completed without post-conversion query raised',         'kpis.post_conversion',    'PostConversionKPI',    30, 1, 1),
    ('delayed_conversion', 'Delayed Conversions',           'Files completed on or before expected turnaround time',        'kpis.delayed_conversion', 'DelayedConversionKPI', 20, 1, 2),
    ('missing_status',     'Missing Status Updates',        'Working days with at least one status update sent to client',  'kpis.missing_status',     'MissingStatusKPI',     15, 1, 3),
    ('reviews',            'Client Reviews',                'Positive reviews received out of files completed',             'kpis.reviews',            'ReviewsKPI',           10, 0, 4),
    ('leaves',             'Leaves / Attendance',           'Days present out of total working days',                       'kpis.leaves',             'LeavesKPI',             5, 1, 5),
    ('late_comings',       'Late Comings',                  'Days arrived on time within 15-min grace period',              'kpis.late_comings',       'LateComingsKPI',        5, 1, 6),
    ('early_leavings',     'Early Leavings',                'Days with full working hours completed',                       'kpis.early_leavings',     'EarlyLeavingsKPI',      5, 1, 7),
    ('independence',       'Ability to Work Independently', 'Manager rating: Low=25% Medium=50% Good=75% High=100%',        'kpis.independence',       'IndependenceKPI',       10, 1, 8),
]

def run():
    # Step 1: create all base tables (users, kpis, notes, score_cache, etc.)
    import local_db
    local_db.init_db()
    print('[Setup] Base tables created.')

    # Step 2: run extra migrations (viasocket_name_map, independence_ratings, etc.)
    try:
        from local_db_additions import run_migrations
        run_migrations(DB_PATH)
    except ImportError: pass

    with sqlite3.connect(DB_PATH) as conn:
        for key,name,desc,module,cls,weight,active,order in KPIS:
            conn.execute("""INSERT INTO kpis (key,name,description,module_path,class_name,raw_weight,is_active,sort_order)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                name=excluded.name,description=excluded.description,
                module_path=excluded.module_path,class_name=excluded.class_name,
                raw_weight=excluded.raw_weight,sort_order=excluded.sort_order""",
                (key,name,desc,module,cls,weight,active,order))
            print(f'  {"✅" if active else "⏸ "}  {name:<38} {weight}%')
        conn.commit()

    active_kpis=[(k,w) for k,_,_,_,_,w,a,_ in KPIS if a]
    total=sum(w for _,w in active_kpis)
    print(f'\nActive KPIs (total raw={total}, normalised to 100%):')
    for k,w in active_kpis:
        print(f'  {k:<25} raw={w}%  normalised={w/total*100:.1f}%')

    try:
        from kpis.independence import init_independence_table
        init_independence_table()
        print('\nindependence_ratings table ready.')
    except Exception as e: print(f'independence table: {e}')

    try:
        from name_mapper import init_name_map_table
        init_name_map_table()
        print('viasocket_name_map table ready.')
    except Exception as e: print(f'name_map table: {e}')

    print('\nDone. Restart Flask.')

if __name__=='__main__': run()