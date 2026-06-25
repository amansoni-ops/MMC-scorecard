"""
backend/keka_name_mapper.py
=============================
Bridges Keka's keka_id (UUID) to SQL Server's AdminID (int) by matching
employee names. Mirrors the existing name_mapper.py pattern used for
ViaSocket: a persistent SQLite table, manual-override support, and a
weekly self-refresh so name drift (typos, new hires, exits) gets re-resolved
without a manual re-run every time.

WHY THIS IS NEEDED
------------------
keka_attendance.py returns records keyed by keka_id + display_name.
score_engine.py (and every existing KPI) keys everything by AdminID (int)
from SQL Server's Admin table. There is no shared ID between the two
systems — the only common field is the human name, which is unreliable
on its own (spacing, capitalization, middle names, duplicate names across
different people). This module builds and maintains that bridge.

MATCH STRATEGY (in priority order)
-----------------------------------
1. EXACT match — normalized name (lowercase, trimmed, collapsed whitespace)
   matches exactly one Admin record.
2. FUZZY match — normalized name is a close match (difflib ratio >= 0.92)
   to exactly one Admin record. Anything below that ratio, or matching
   more than one Admin record equally well, is left UNRESOLVED rather
   than guessed — ambiguous matches must be confirmed manually.
3. MANUAL override — always checked first, before steps 1-2. Once a
   mapping is set manually, it is never overwritten by the automatic
   matcher, even if a "better" automatic match appears later.

REFRESH SCHEDULE
-----------------
Re-resolves automatically once per 7 days (168 hours) for any keka_id
not already manually overridden, OR immediately if a keka_id appears
that has never been seen before (new hire). This mirrors the same
should_sync()-style logic used for the Keka master tables.
"""

import sqlite3
import difflib
import time
from datetime import datetime

CACHE_DB_PATH = 'scorecard.db'
REFRESH_INTERVAL_HOURS = 168   # weekly
FUZZY_MATCH_THRESHOLD = 0.92

TABLE = 'keka_admin_map'


def _ensure_table(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            keka_id        TEXT PRIMARY KEY,
            keka_name      TEXT NOT NULL,
            admin_id       INTEGER,
            admin_name     TEXT,
            match_method   TEXT,
            is_manual      INTEGER DEFAULT 0,
            last_resolved  TEXT NOT NULL
        )
    """)
    conn.commit()


def _normalize(name):
    """Lowercase, trim, collapse internal whitespace, strip trailing/leading spaces."""
    if not name:
        return ''
    return ' '.join(name.strip().lower().split())


def _fetch_sql_admins():
    """
    Pull the live Admin list from SQL Server for matching.
    Uses the project's existing db connection helper.

    IMPORTANT — NO Flag_Active / Flag_Delete filter here, by design.
    Verified directly against AdminID 344 (Ekta Hirke, a confirmed real,
    currently-working employee from earlier session work) that she has
    Flag_Active=False in this table. Flag_Active on Admin does NOT mean
    "currently employed" the way it does on order-history tables — it
    tracks something else (e.g. login/portal access), and using it here
    silently dropped 547-of-934 valid match candidates, which is exactly
    why ~83% of Keka employees came back "unresolved" on first run.

    Name matching does not need an employment-status filter at all — a
    wrong match is already prevented by the exact/fuzzy + ambiguity
    logic below, not by this flag. Filtering on it only removes correct
    candidates, it adds no protection.
    """
    from db import execute_query
    sql = """
        SELECT ID_Admin AS AdminID,
               Admin_FirstName + ' ' + Admin_LastName AS AdminName
        FROM Admin
    """
    return execute_query(sql)


def _match_one(keka_name, admin_rows):
    """
    Returns (admin_id, admin_name, method) or (None, None, 'unresolved').
    admin_rows: list of {'AdminID':..., 'AdminName':...}
    """
    norm_keka = _normalize(keka_name)
    if not norm_keka:
        return None, None, 'unresolved'

    # Exact match
    exact = [a for a in admin_rows if _normalize(a['AdminName']) == norm_keka]
    if len(exact) == 1:
        return exact[0]['AdminID'], exact[0]['AdminName'], 'exact'
    if len(exact) > 1:
        return None, None, 'ambiguous_exact'   # same name, multiple admins — don't guess

    # Fuzzy match
    scored = []
    for a in admin_rows:
        ratio = difflib.SequenceMatcher(None, norm_keka, _normalize(a['AdminName'])).ratio()
        if ratio >= FUZZY_MATCH_THRESHOLD:
            scored.append((ratio, a))
    if len(scored) == 1:
        ratio, a = scored[0]
        return a['AdminID'], a['AdminName'], f'fuzzy_{ratio:.2f}'
    if len(scored) > 1:
        scored.sort(key=lambda x: -x[0])
        # only accept if the top match is clearly better than the runner-up
        if scored[0][0] - scored[1][0] >= 0.05:
            return scored[0][1]['AdminID'], scored[0][1]['AdminName'], f'fuzzy_{scored[0][0]:.2f}'
        return None, None, 'ambiguous_fuzzy'

    return None, None, 'unresolved'


def refresh_mapping(keka_employees, force=False):
    """
    keka_employees: list of {'keka_id':..., 'display_name':...} — typically
    the output of fetching keka_employees table, or derived from attendance
    data's name_by_kid lookup.

    Resolves any keka_id that is new, was previously unresolved (always
    eligible for retry regardless of elapsed time), or whose last automatic
    resolution is older than REFRESH_INTERVAL_HOURS, and is not manually
    overridden.

    Confirmed via diagnosis: keka_employees as fetched directly from the
    table contains ~2x duplicate rows per person (daily re-sync re-inserts
    rather than upserts). Deduplicating here — keep latest by
    updatedat/createdat — avoids matching the same person twice per run,
    which was producing resolved counts that looked inconsistent across
    different call sites even though the underlying match logic was correct.
    """
    # Dedup input by keka_id, keep latest row per person
    latest_by_kid = {}
    for emp in keka_employees:
        kid = emp.get('keka_id') or emp.get('name')
        if not kid:
            continue
        ts = emp.get('updatedat') or emp.get('createdat') or ''
        if kid not in latest_by_kid or ts > latest_by_kid[kid].get('_ts', ''):
            latest_by_kid[kid] = {**emp, '_ts': ts}
    keka_employees = list(latest_by_kid.values())

    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)

    existing = {row[0]: row for row in conn.execute(
        f"SELECT keka_id, keka_name, admin_id, admin_name, match_method, is_manual, last_resolved FROM {TABLE}"
    )}

    admin_rows = _fetch_sql_admins()
    now_iso = datetime.utcnow().isoformat()
    resolved_count = 0
    unresolved = []

    for emp in keka_employees:
        kid = emp.get('keka_id') or emp.get('name')   # 'name' col holds keka_id in raw Keka rows
        kname = emp.get('display_name') or emp.get('name', '')
        if not kid:
            continue

        row = existing.get(kid)
        if row and row[5] == 1:   # is_manual — never auto-touch
            continue

        # row layout: (keka_id, keka_name, admin_id, admin_name, match_method, is_manual, last_resolved)
        previously_unresolved = bool(row) and row[2] is None   # admin_id is None = failed last time

        needs_refresh = force or row is None or previously_unresolved
        if not needs_refresh and row:
            last_resolved = datetime.fromisoformat(row[6])
            hours_since = (datetime.utcnow() - last_resolved).total_seconds() / 3600
            needs_refresh = hours_since >= REFRESH_INTERVAL_HOURS

        if not needs_refresh:
            continue

        admin_id, admin_name, method = _match_one(kname, admin_rows)
        conn.execute(f"""
            INSERT INTO {TABLE} (keka_id, keka_name, admin_id, admin_name, match_method, is_manual, last_resolved)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(keka_id) DO UPDATE SET
                keka_name=excluded.keka_name,
                admin_id=excluded.admin_id,
                admin_name=excluded.admin_name,
                match_method=excluded.match_method,
                last_resolved=excluded.last_resolved
            WHERE is_manual = 0
        """, (kid, kname, admin_id, admin_name, method, now_iso))

        if admin_id is not None:
            resolved_count += 1
        else:
            unresolved.append({'keka_id': kid, 'keka_name': kname, 'reason': method})

    conn.commit()
    conn.close()

    print(f'[KekaAdminMap] Refreshed: {resolved_count} resolved, {len(unresolved)} unresolved')
    return {'resolved': resolved_count, 'unresolved': unresolved}


def get_admin_id(keka_id):
    """Look up a single keka_id -> AdminID. Returns None if unmapped."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    row = conn.execute(f"SELECT admin_id FROM {TABLE} WHERE keka_id=?", (keka_id,)).fetchone()
    conn.close()
    return row[0] if row else None


def get_full_map():
    """Returns {keka_id: admin_id} for all resolved mappings."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    rows = conn.execute(f"SELECT keka_id, admin_id FROM {TABLE} WHERE admin_id IS NOT NULL").fetchall()
    conn.close()
    return {kid: aid for kid, aid in rows}


def get_unresolved():
    """Returns list of mappings that need manual attention."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    rows = conn.execute(
        f"SELECT keka_id, keka_name, match_method FROM {TABLE} WHERE admin_id IS NULL"
    ).fetchall()
    conn.close()
    return [{'keka_id': r[0], 'keka_name': r[1], 'reason': r[2]} for r in rows]


def set_manual_mapping(keka_id, admin_id, admin_name=None):
    """
    Manually pin a keka_id -> AdminID mapping. Once set, the weekly
    auto-refresh will never overwrite it (is_manual=1 is checked first).
    """
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    conn.execute(f"""
        INSERT INTO {TABLE} (keka_id, keka_name, admin_id, admin_name, match_method, is_manual, last_resolved)
        VALUES (?, '', ?, ?, 'manual', 1, ?)
        ON CONFLICT(keka_id) DO UPDATE SET
            admin_id=excluded.admin_id,
            admin_name=excluded.admin_name,
            match_method='manual',
            is_manual=1,
            last_resolved=excluded.last_resolved
    """, (keka_id, admin_id, admin_name, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def get_all_mappings():
    """Full dump for an admin review UI, if one is built later."""
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_table(conn)
    cols = ['keka_id', 'keka_name', 'admin_id', 'admin_name', 'match_method', 'is_manual', 'last_resolved']
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM {TABLE}").fetchall()
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


if __name__ == '__main__':
    # Manual test — fetches keka_employees fresh and runs the mapper
    import requests
    AUTH_KEY = 'keywWPoCKnwcJAA'
    DB_ID    = '6a17ec96a95e7ac45342c0e4'
    r = requests.get(f'https://table-api.viasocket.com/{DB_ID}/tblrj1w62',
                      headers={'auth-key': AUTH_KEY}, timeout=30)
    emps = r.json().get('data', {}).get('rows', [])
    result = refresh_mapping(emps, force=True)
    print(f'\nResolved: {result["resolved"]}')
    print(f'Unresolved: {len(result["unresolved"])}')
    for u in result['unresolved'][:20]:
        print(f'  {u["keka_name"]:<30} reason={u["reason"]}')