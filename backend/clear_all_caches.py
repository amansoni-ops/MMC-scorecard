"""
backend/clear_all_caches.py
==============================
Clears EVERY cache touched by this session's changes, before a fresh
restart:
  - score_cache          (main dashboard blob cache)
  - keka_attendance_cache (per-month Keka computation cache)
  - employee_kpi_cache    (new per-employee/month/KPI cache — detail
                            page + trend chart)

Run this ONCE before starting app.py, any time you've changed KPI
logic (post_conversion's Reckon fix, missing_status's completion-day
fix, etc.) and want every cache layer to recompute fresh rather than
serve stale data from before the fix.

Note: this does NOT delete keka_admin_map, keka_upgrade_log, or
keka_sync_job's bookkeeping tables — those are identity/mapping data,
not score caches, and clearing them would lose real progress (name
resolutions, upgrade history) for no benefit.
"""
import sqlite3

DB_PATH = 'scorecard.db'

TABLES_TO_CLEAR = [
    'score_cache',
    'keka_attendance_cache',
    'employee_kpi_cache',
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

for table in TABLES_TO_CLEAR:
    try:
        cur.execute(f"DELETE FROM {table}")
        print(f'[ClearCache] Cleared {table} ({cur.rowcount} rows removed)')
    except sqlite3.OperationalError as e:
        # Table doesn't exist yet — fine, it'll be created fresh on
        # first use, nothing to clear.
        print(f'[ClearCache] {table} does not exist yet (will be created on first use) — skipped')

conn.commit()
conn.close()

print('\n[ClearCache] Done. All score-related caches cleared.')
print('[ClearCache] Identity/mapping tables (keka_admin_map, keka_upgrade_log)')
print('[ClearCache] were intentionally left untouched.')