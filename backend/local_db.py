"""
SQLite local database — stores KPI config, users, notes, and caches.
"""
import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'scorecard.db')

def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role     TEXT NOT NULL DEFAULT 'viewer'
        );

        CREATE TABLE IF NOT EXISTS kpis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            key         TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            module_path TEXT NOT NULL,
            class_name  TEXT NOT NULL,
            raw_weight  REAL NOT NULL DEFAULT 10,
            is_active   INTEGER NOT NULL DEFAULT 1,
            sort_order  INTEGER NOT NULL DEFAULT 99,
            updated_by  TEXT,
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id   INTEGER NOT NULL,
            month      INTEGER NOT NULL,
            year       INTEGER NOT NULL,
            note_text  TEXT NOT NULL DEFAULT '',
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(admin_id, month, year)
        );

        CREATE TABLE IF NOT EXISTS score_cache (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            month      INTEGER NOT NULL,
            year       INTEGER NOT NULL,
            data_json  TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(month, year)
        );

        CREATE TABLE IF NOT EXISTS viasocket_name_map (
            viasocket_name TEXT PRIMARY KEY,
            admin_id       INTEGER NOT NULL,
            department     TEXT,
            match_method   TEXT NOT NULL DEFAULT 'synthetic',
            confidence     REAL NOT NULL DEFAULT 0.0,
            sql_admin_name TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS independence_ratings (
            admin_id  INTEGER NOT NULL,
            month     INTEGER NOT NULL,
            year      INTEGER NOT NULL,
            rating    TEXT NOT NULL CHECK(rating IN ('Low','Medium','Good','High')),
            score_pct REAL NOT NULL,
            rated_by  TEXT,
            rated_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(admin_id, month, year)
        );
        """)
        # Seed admin user if not exists
        pw = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute("INSERT OR IGNORE INTO users (username,password,role) VALUES (?,?,?)",
                  ('admin', pw, 'admin'))

def verify_user(username: str, password: str) -> dict | None:
    pw = hashlib.sha256(password.encode()).hexdigest()
    with _conn() as c:
        row = c.execute(
            'SELECT id,username,role FROM users WHERE username=? AND password=?',
            (username, pw)).fetchone()
    return dict(row) if row else None

# ── KPI CRUD ─────────────────────────────────────────────────────────────
def get_all_kpis() -> list[dict]:
    with _conn() as c:
        rows = c.execute('SELECT * FROM kpis ORDER BY sort_order, id').fetchall()
    return [dict(r) for r in rows]

def get_active_kpis() -> list[dict]:
    with _conn() as c:
        rows = c.execute('SELECT * FROM kpis WHERE is_active=1 ORDER BY sort_order, id').fetchall()
    return [dict(r) for r in rows]

def update_kpi_weight(key: str, weight: float, updated_by: str = 'system'):
    with _conn() as c:
        c.execute("UPDATE kpis SET raw_weight=?, updated_by=?, updated_at=datetime('now') WHERE key=?",
                  (weight, updated_by, key))

def toggle_kpi(key: str, is_active: int, updated_by: str = 'system'):
    with _conn() as c:
        c.execute("UPDATE kpis SET is_active=?, updated_by=?, updated_at=datetime('now') WHERE key=?",
                  (is_active, updated_by, key))

def add_kpi(data: dict) -> int:
    with _conn() as c:
        cur = c.execute("""
            INSERT INTO kpis (key,name,description,module_path,class_name,raw_weight,is_active,sort_order)
            VALUES (:key,:name,:description,:module_path,:class_name,:raw_weight,:is_active,:sort_order)""", data)
        return cur.lastrowid

# ── Notes ─────────────────────────────────────────────────────────────────
def get_note(admin_id: int, month: int, year: int) -> str:
    with _conn() as c:
        row = c.execute('SELECT note_text FROM notes WHERE admin_id=? AND month=? AND year=?',
                        (admin_id, month, year)).fetchone()
    return row['note_text'] if row else ''

def upsert_note(admin_id: int, month: int, year: int, text: str, created_by: str):
    with _conn() as c:
        c.execute("""INSERT INTO notes (admin_id,month,year,note_text,created_by,created_at)
            VALUES (?,?,?,?,?,datetime('now'))
            ON CONFLICT(admin_id,month,year) DO UPDATE SET note_text=excluded.note_text,
            created_by=excluded.created_by, created_at=datetime('now')""",
            (admin_id, month, year, text, created_by))

# ── Score cache ────────────────────────────────────────────────────────────
def get_cached_scores(month: int, year: int) -> str | None:
    with _conn() as c:
        row = c.execute('SELECT data_json FROM score_cache WHERE month=? AND year=?',
                        (month, year)).fetchone()
    return row['data_json'] if row else None

def set_cached_scores(month: int, year: int, data_json: str):
    with _conn() as c:
        c.execute("""INSERT INTO score_cache (month,year,data_json,created_at)
            VALUES (?,?,?,datetime('now'))
            ON CONFLICT(month,year) DO UPDATE SET data_json=excluded.data_json, created_at=datetime('now')""",
            (month, year, data_json))

def delete_cached_scores(month: int = None, year: int = None):
    with _conn() as c:
        if month and year:
            c.execute('DELETE FROM score_cache WHERE month=? AND year=?', (month, year))
        else:
            c.execute('DELETE FROM score_cache')

def get_cache_entries() -> list[dict]:
    with _conn() as c:
        rows = c.execute('SELECT month,year,created_at,length(data_json) AS size FROM score_cache ORDER BY year,month').fetchall()
    return [dict(r) for r in rows]
