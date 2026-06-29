"""
backend/employee_kpi_cache.py
================================
Per-employee, per-month, per-KPI score cache. Replaces the slow path
where opening one employee's detail page triggered a full re-fetch of
EVERY KPI for ALL employees (the 4-5 minute load time bug).

SCHEMA
------
One row per (admin_id, month, year, kpi_key) — NOT one blob per month,
NOT one row per employee. Toggling a KPI on/off never touches this
table at all: numerator/denominator/success_ratio/failure_ratio are
facts about that KPI for that person that month, independent of
whether the KPI is currently enabled. Only the WEIGHT NORMALIZATION
and SUMMATION into a total_score happens at read time, using whichever
KPIs are currently active in local_db's registry — this is the same
live-toggle-respecting behavior score_engine.py already has, just
reading from a fast indexed table instead of recomputing from scratch.

success_ratio drives the actual SCORE MATH (score = success_ratio *
weight / 100) — left untouched so the real scoring formula used
throughout the rest of this project doesn't need to change.

failure_ratio (= 100 - success_ratio) is precomputed and stored
separately, since EVERY display surface in this project shows failure
percentages, not success — precomputing it once here means every UI
component just reads the field directly, instead of each one
separately computing `100 - success_ratio` inline (which is how
EmployeeDetail.jsx/Dashboard.jsx currently do it, in several different
places, risking one of them getting the flip wrong).

score is NOT stored — it depends on weight, and weight depends on
which KPIs are currently active (toggling a KPI off re-normalizes
everyone else's weights). Storing it would go stale the instant
someone flips a toggle. It's cheap to compute at read time from the
handful of rows for one employee.
"""

import sqlite3
import json
from datetime import datetime

CACHE_DB_PATH = 'scorecard.db'
TABLE = 'employee_kpi_cache'


def _ensure_table(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            admin_id      INTEGER NOT NULL,
            month         INTEGER NOT NULL,
            year          INTEGER NOT NULL,
            kpi_key       TEXT    NOT NULL,
            employee_name TEXT,
            department    TEXT,
            is_conversion INTEGER,
            numerator     REAL,
            denominator   REAL,
            success_ratio REAL,
            failure_ratio REAL,
            orders_json   TEXT,
            computed_at   TEXT NOT NULL,
            PRIMARY KEY (admin_id, month, year, kpi_key)
        )
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{TABLE}_lookup
        ON {TABLE} (admin_id, month, year)
    """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_{TABLE}_month
        ON {TABLE} (month, year)
    """)
    conn.commit()


def write_employee_kpi_row(admin_id, month, year, kpi_key, employee_name,
                            department, is_conversion, numerator, denominator,
                            success_ratio, orders):
    """
    Writes/updates ONE (employee, month, year, KPI) row. Called by the
    population job once per employee per KPI. Also used by the single-
    employee refresh path, where only this person's rows get rewritten
    without touching anyone else's cached data for that month.
    """
    failure_ratio = round(100 - success_ratio, 2) if success_ratio is not None else None

    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    conn.execute(f"""
        INSERT INTO {TABLE}
            (admin_id, month, year, kpi_key, employee_name, department,
             is_conversion, numerator, denominator, success_ratio,
             failure_ratio, orders_json, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(admin_id, month, year, kpi_key) DO UPDATE SET
            employee_name = excluded.employee_name,
            department    = excluded.department,
            is_conversion = excluded.is_conversion,
            numerator     = excluded.numerator,
            denominator   = excluded.denominator,
            success_ratio = excluded.success_ratio,
            failure_ratio = excluded.failure_ratio,
            orders_json   = excluded.orders_json,
            computed_at   = excluded.computed_at
    """, (
        admin_id, month, year, kpi_key, employee_name, department,
        int(bool(is_conversion)), numerator, denominator, success_ratio,
        failure_ratio, json.dumps(orders or []), datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def get_employee_kpi_rows(admin_id, month, year):
    """
    Fast read path for the employee detail page. Returns all cached KPI
    rows for one employee/month — typically 5-7 rows, indexed lookup,
    milliseconds.
    """
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    rows = conn.execute(f"""
        SELECT kpi_key, employee_name, department, is_conversion,
               numerator, denominator, success_ratio, failure_ratio, orders_json
        FROM {TABLE}
        WHERE admin_id=? AND month=? AND year=?
    """, (admin_id, month, year)).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append({
            'kpi_key': r[0],
            'employee_name': r[1],
            'department': r[2],
            'is_conversion': bool(r[3]),
            'numerator': r[4],
            'denominator': r[5],
            'success_ratio': r[6],
            'failure_ratio': r[7],
            'orders': json.loads(r[8]) if r[8] else [],
        })
    return result


def get_employee_trend(admin_id, year):
    """
    Fast read path for the year-trend chart. Returns one row per month
    that has cached data, with enough info to recompute total_score
    using CURRENT kpi weights (passed in by the caller, since weights
    can change and this module doesn't know about local_db's registry).
    """
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    rows = conn.execute(f"""
        SELECT month, kpi_key, success_ratio
        FROM {TABLE}
        WHERE admin_id=? AND year=?
    """, (admin_id, year)).fetchall()
    conn.close()

    by_month = {}
    for month, kpi_key, success_ratio in rows:
        by_month.setdefault(month, {})[kpi_key] = success_ratio
    return by_month


def has_cached_month(month, year):
    """Check if the population job has already run for this month —
    used to decide whether a request needs to trigger a fresh compute
    or can read straight from cache."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    row = conn.execute(f"""
        SELECT COUNT(*) FROM {TABLE} WHERE month=? AND year=?
    """, (month, year)).fetchone()
    conn.close()
    return row[0] > 0


def get_all_employees_for_month(month, year):
    """
    Fast read path for the MAIN DASHBOARD list — same table, same
    pattern, so the dashboard and the employee-detail page share one
    source of truth instead of two separate cache systems that can
    drift out of sync.
    """
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    rows = conn.execute(f"""
        SELECT admin_id, kpi_key, employee_name, department, is_conversion,
               numerator, denominator, success_ratio, failure_ratio, orders_json
        FROM {TABLE}
        WHERE month=? AND year=?
    """, (month, year)).fetchall()
    conn.close()

    by_admin = {}
    for r in rows:
        aid = r[0]
        if aid not in by_admin:
            by_admin[aid] = {
                'admin_id': aid,
                'employee_name': r[2],
                'department': r[3],
                'is_conversion': bool(r[4]),
                'kpi_breakdown_raw': {},
            }
        by_admin[aid]['kpi_breakdown_raw'][r[1]] = {
            'numerator': r[5], 'denominator': r[6],
            'success_ratio': r[7], 'failure_ratio': r[8],
            'orders': json.loads(r[9]) if r[9] else [],
        }
    return list(by_admin.values())


def clear_month(month, year):
    """Force a clean recompute for one month — used after KPI weight
    changes if you want a fresh population run, or for debugging."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    conn.execute(f"DELETE FROM {TABLE} WHERE month=? AND year=?", (month, year))
    conn.commit()
    conn.close()


def clear_employee(admin_id, month=None, year=None):
    """Clear just one employee's rows — paired with the refresh-one-
    employee population function below."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    if month and year:
        conn.execute(f"DELETE FROM {TABLE} WHERE admin_id=? AND month=? AND year=?",
                     (admin_id, month, year))
    else:
        conn.execute(f"DELETE FROM {TABLE} WHERE admin_id=?", (admin_id,))
    conn.commit()
    conn.close()