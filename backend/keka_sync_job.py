"""
backend/keka_sync_job.py
===========================
Runs independently of any report view, on its own clock. This is what
makes new-joiner detection and synthetic-to-real ID upgrades ACTUALLY
automatic — not "automatic until someone forgets to view a report for
that month," which is what relying on _compute()'s lazy refresh would
mean in practice.

WHAT THIS JOB DOES, EVERY TIME IT RUNS
----------------------------------------
1. Fetches the live Keka employees list (fresh, no cache).
2. For anyone NOT YET in keka_admin_map at all -> brand new to us.
   They get an entry immediately: matched against SQL Admin if possible,
   else marked unresolved (synthetic ID is computed on-the-fly later by
   keka_attendance.py, not stored here — it's deterministic from keka_id
   so it doesn't need to be).
3. For anyone CURRENTLY unresolved (admin_id IS NULL) -> retried against
   the SQL Admin table every run, regardless of how long it's been. A
   new joiner might get created in SQL Server at any time; we don't want
   to wait out an arbitrary "weekly" window once they're eligible.
4. For anyone who WAS unresolved and just became resolved this run (i.e.
   SQL Server finally caught up with their record) -> this is the
   "upgrade" case. Logged explicitly via keka_upgrade_log so historical
   continuity can be reasoned about: any score data computed under their
   old synthetic ID is now associated with this keka_id's upgrade event,
   so a future reconciliation step (or a human) can find and merge it
   with the new real AdminID if needed. This script does NOT attempt to
   silently rewrite historical score_cache rows — that's a decision with
   real consequences (could double-count, could lose data) that belongs
   to a human decision, not a background job.

HOW TO RUN THIS AUTOMATICALLY, NOT MANUALLY
----------------------------------------------
See keka_scheduler.py (companion file) for the actual "run forever in
the background" wiring to add to app.py. This file itself is just the
one-shot job logic — call run_sync_job() from anywhere: a scheduler
loop, a cron-style call, or manually for testing. It does the same work
regardless of what calls it.
"""

import sys
sys.path.insert(0, '.')
import sqlite3
import requests
from datetime import datetime

import keka_name_mapper as name_mapper

AUTH_KEY = 'keywWPoCKnwcJAA'
DB_ID    = '6a17ec96a95e7ac45342c0e4'
BASE     = f'https://table-api.viasocket.com/{DB_ID}'
HEADERS  = {'auth-key': AUTH_KEY}
TBL_EMPLOYEES = 'tblrj1w62'

CACHE_DB_PATH = 'scorecard.db'
UPGRADE_LOG_TABLE = 'keka_upgrade_log'


def _ensure_upgrade_log(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {UPGRADE_LOG_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keka_id TEXT NOT NULL,
            keka_name TEXT,
            old_synthetic_id INTEGER,
            new_admin_id INTEGER NOT NULL,
            new_admin_name TEXT,
            upgraded_at TEXT NOT NULL,
            reconciled INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def _fetch_all(table_id):
    rows, offset, pages = [], None, 0
    while True:
        params = {'offset': offset} if offset else {}
        r = requests.get(f'{BASE}/{table_id}', headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        d = r.json().get('data', {})
        batch = d.get('rows', [])
        rows.extend(batch)
        pages += 1
        offset = d.get('offset')
        if not offset or not batch or pages > 50:
            break
    return rows


def _synthetic_admin_id(keka_id):
    """Same deterministic formula as kpis/keka_attendance.py — must match
    exactly, or the upgrade-detection step below can't recognize which
    synthetic ID a person used to have."""
    import hashlib
    h = int(hashlib.md5(keka_id.encode()).hexdigest()[:8], 16)
    return -(h % 900000 + 100000)


def run_sync_job():
    print(f'[KekaSyncJob] Starting run at {datetime.utcnow().isoformat()}')

    print('[KekaSyncJob] Fetching live Keka employees...')
    raw_emps = _fetch_all(TBL_EMPLOYEES)

    # Dedup by keka_id, keep latest (same pattern as keka_name_mapper now uses)
    latest_emp = {}
    for e in raw_emps:
        kid = e.get('name')
        if not kid:
            continue
        ts = e.get('updatedat') or e.get('createdat') or ''
        if kid not in latest_emp or ts > latest_emp[kid].get('_ts', ''):
            latest_emp[kid] = {**e, '_ts': ts}
    print(f'[KekaSyncJob] {len(raw_emps)} raw rows -> {len(latest_emp)} distinct employees')

    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_upgrade_log(conn)

    # Snapshot WHO is currently unresolved, BEFORE refresh_mapping runs,
    # so we can detect upgrades by comparing before/after.
    before_unresolved = {
        row[0]: row for row in conn.execute(
            "SELECT keka_id, keka_name FROM keka_admin_map WHERE admin_id IS NULL"
        )
    }
    before_known_kids = {row[0] for row in conn.execute("SELECT keka_id FROM keka_admin_map")}
    conn.close()

    new_kids = [kid for kid in latest_emp if kid not in before_known_kids]
    print(f'[KekaSyncJob] New employees never seen before: {len(new_kids)}')
    for kid in new_kids[:10]:
        print(f'    NEW: {latest_emp[kid].get("display_name", "?")}  (keka_id={kid})')

    # This call resolves new employees AND retries every currently-unresolved
    # person against SQL Server, every single run — no time-based waiting
    # for the unresolved case (see keka_name_mapper.py's previously_unresolved
    # check, which always retries regardless of elapsed time).
    result = name_mapper.refresh_mapping(list(latest_emp.values()))

    # ── Detect upgrades: was unresolved before, has a real admin_id now ───────
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_upgrade_log(conn)
    upgrades = []
    for kid in before_unresolved:
        row = conn.execute(
            "SELECT admin_id, admin_name FROM keka_admin_map WHERE keka_id=?", (kid,)
        ).fetchone()
        if row and row[0] is not None:
            old_synthetic = _synthetic_admin_id(kid)
            upgrades.append({
                'keka_id': kid,
                'keka_name': before_unresolved[kid][1],
                'old_synthetic_id': old_synthetic,
                'new_admin_id': row[0],
                'new_admin_name': row[1],
            })

    if upgrades:
        print(f'\n[KekaSyncJob] {len(upgrades)} employee(s) UPGRADED from synthetic to real AdminID:')
        for u in upgrades:
            print(f'    {u["keka_name"]:<30} synthetic={u["old_synthetic_id"]}  -> real AdminID={u["new_admin_id"]}')
            conn.execute(f"""
                INSERT INTO {UPGRADE_LOG_TABLE}
                    (keka_id, keka_name, old_synthetic_id, new_admin_id, new_admin_name, upgraded_at, reconciled)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (u['keka_id'], u['keka_name'], u['old_synthetic_id'],
                  u['new_admin_id'], u['new_admin_name'], datetime.utcnow().isoformat()))
        conn.commit()
        print(f'[KekaSyncJob] Logged to {UPGRADE_LOG_TABLE} — NOT auto-reconciling historical')
        print(f'                score_cache rows. Run keka_reconcile_upgrades.py to review and')
        print(f'                merge history for these {len(upgrades)} people if needed.')
    else:
        print('\n[KekaSyncJob] No upgrades this run.')

    conn.close()

    print(f'\n[KekaSyncJob] Done. {result["resolved"]} resolved this run, '
          f'{len(result["unresolved"])} still unresolved.')
    return {
        'new_employees': len(new_kids),
        'resolved_this_run': result['resolved'],
        'still_unresolved': len(result['unresolved']),
        'upgrades': upgrades,
    }


if __name__ == '__main__':
    run_sync_job()