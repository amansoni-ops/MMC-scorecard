import difflib, sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'scorecard.db')

def init_name_map_table():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS viasocket_name_map (
                viasocket_name TEXT PRIMARY KEY,
                admin_id       INTEGER NOT NULL,
                department     TEXT,
                match_method   TEXT NOT NULL DEFAULT 'synthetic',
                confidence     REAL NOT NULL DEFAULT 0.0,
                sql_admin_name TEXT,
                created_at     TEXT DEFAULT (datetime('now'))
            )""")

def _get_sql_admins():
    try:
        from db import execute_query
        rows = execute_query("""
            SELECT ID_Admin,
                   LTRIM(RTRIM(ISNULL(Admin_FirstName,'')))
                   +' '+LTRIM(RTRIM(ISNULL(Admin_LastName,''))) AS FullName
            FROM Admin WHERE Flag_Active=1 AND Admin_FirstName IS NOT NULL""")
        return {r['FullName'].strip().lower(): r['ID_Admin']
                for r in rows if (r.get('FullName') or '').strip()}
    except Exception as e:
        print(f'[NameMapper] SQL error: {e}'); return {}

def _synthetic_id(name):
    return -(abs(hash(name.strip().lower())) % 900000 + 100000)

def resolve(name):
    key = name.strip()
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            'SELECT admin_id,match_method,sql_admin_name FROM viasocket_name_map WHERE viasocket_name=?',
            (key,)).fetchone()
    if row:
        return {'admin_id':row[0],'match_method':row[1],'sql_admin_name':row[2]}
    sql = _get_sql_admins()
    nl  = key.lower()
    if nl in sql:
        _store(key, sql[nl], 'exact', 1.0, key.title())
        return {'admin_id':sql[nl],'match_method':'exact','sql_admin_name':key.title()}
    matches = difflib.get_close_matches(nl, list(sql.keys()), n=1, cutoff=0.82)
    if matches:
        best  = matches[0]
        score = difflib.SequenceMatcher(None, nl, best).ratio()
        aid   = sql[best]
        _store(key, aid, 'fuzzy', round(score,3), best.title())
        print(f'[NameMapper] Fuzzy: "{key}" → "{best.title()}" ({score:.2f})')
        return {'admin_id':aid,'match_method':'fuzzy','sql_admin_name':best.title()}
    syn = _synthetic_id(key)
    _store(key, syn, 'synthetic', 0.0, None)
    print(f'[NameMapper] Unmatched: "{key}" → synthetic {syn}')
    return {'admin_id':syn,'match_method':'synthetic','sql_admin_name':None}

def _store(name, admin_id, method, confidence, sql_name):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""INSERT OR REPLACE INTO viasocket_name_map
            (viasocket_name,admin_id,match_method,confidence,sql_admin_name)
            VALUES (?,?,?,?,?)""", (name, admin_id, method, confidence, sql_name))

def set_manual_mapping(name, admin_id, dept=None):
    _store(name.strip(), admin_id, 'manual', 1.0, None)

def get_all_mappings():
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            'SELECT viasocket_name,admin_id,department,match_method,confidence,sql_admin_name '
            'FROM viasocket_name_map ORDER BY match_method,viasocket_name').fetchall()
    return [dict(zip(['viasocket_name','admin_id','department','match_method','confidence','sql_admin_name'],r))
            for r in rows]
