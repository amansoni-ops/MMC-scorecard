from kpis.base import BaseKPI
import sqlite3, os

DB_PATH    = os.path.join(os.path.dirname(__file__),'..','scorecard.db')
RATING_PCT = {'Low':25.0,'Medium':50.0,'Good':75.0,'High':100.0}

def init_independence_table():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS independence_ratings (
            admin_id INTEGER NOT NULL, month INTEGER NOT NULL, year INTEGER NOT NULL,
            rating TEXT NOT NULL CHECK(rating IN ('Low','Medium','Good','High')),
            score_pct REAL NOT NULL, rated_by TEXT,
            rated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(admin_id,month,year))""")

def get_rating(admin_id, month, year):
    with sqlite3.connect(DB_PATH) as c:
        row=c.execute('SELECT rating,score_pct,rated_by FROM independence_ratings WHERE admin_id=? AND month=? AND year=?',
            (admin_id,month,year)).fetchone()
    return {'rating':row[0],'score_pct':row[1],'rated_by':row[2]} if row else None

def set_rating(admin_id, month, year, rating, rated_by='admin'):
    init_independence_table()
    if rating not in RATING_PCT: raise ValueError(f'Invalid rating "{rating}"')
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""INSERT INTO independence_ratings (admin_id,month,year,rating,score_pct,rated_by,rated_at)
            VALUES (?,?,?,?,?,?,datetime('now'))
            ON CONFLICT(admin_id,month,year) DO UPDATE SET
            rating=excluded.rating,score_pct=excluded.score_pct,
            rated_by=excluded.rated_by,rated_at=datetime('now')""",
            (admin_id,month,year,rating,RATING_PCT[rating],rated_by))

def get_all_ratings(month, year):
    with sqlite3.connect(DB_PATH) as c:
        rows=c.execute('SELECT admin_id,rating,score_pct,rated_by FROM independence_ratings WHERE month=? AND year=?',
            (month,year)).fetchall()
    return [{'admin_id':r[0],'rating':r[1],'score_pct':r[2],'rated_by':r[3]} for r in rows]

class IndependenceKPI(BaseKPI):
    def fetch(self, month, year):
        init_independence_table()
        result=[]
        for r in get_all_ratings(month,year):
            name=self._get_name(r['admin_id'])
            result.append({'AdminID':r['admin_id'],'EmployeeName':name or f'Employee {r["admin_id"]}',
                'Rating':r['rating'],'ScorePct':r['score_pct'],'RatedBy':r['rated_by'],'Month':month,'Year':year})
        return result

    def aggregate(self, rows):
        if not rows:
            return {'numerator':None,'denominator':100,'success_ratio':None,'orders':[]}
        row=rows[0]; pct=row.get('ScorePct',0)
        return {'numerator':pct,'denominator':100,'success_ratio':pct,
                'orders':[{'rating':row.get('Rating'),'score_pct':pct,'rated_by':row.get('RatedBy')}]}

    @staticmethod
    def _get_name(admin_id):
        try:
            from db import execute_query
            rows=execute_query(f"SELECT Admin_FirstName+' '+Admin_LastName AS N FROM Admin WHERE ID_Admin={admin_id}")
            return rows[0]['N'] if rows else None
        except: return None
