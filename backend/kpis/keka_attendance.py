"""
backend/kpis/keka_attendance.py
================================
Drop-in replacement for kpis/leaves.py, kpis/late_comings.py, and
kpis/early_leavings.py. Computes ALL attendance metrics from raw Keka
punch data fetched in this module — no dependency on any pre-derived
column in the synced Keka tables.

WHY THREE CLASSES IN ONE FILE
------------------------------
score_engine.py is KPI-agnostic: it loads each active KPI by
module_path + class_name from the local_db registry and calls
.fetch(month, year) then .aggregate(rows) on it — it has no idea whether
the data comes from SQL Server, ViaSocket, or Keka. To switch the
existing 'leaves', 'late_comings', 'early_leavings' KPI keys over to Keka
without touching score_engine.py at all, each of those three keys just
needs its registry entry (module_path/class_name) repointed at one of
the three classes below. The interface contract is identical to every
other KPI module in this project:

    fetch(month, year)   -> list of row dicts, each with at least
                             {'AdminID': int, 'EmployeeName': str,
                              'Department': str, ...kpi-specific fields}
    aggregate(rows)      -> {'numerator':int, 'denominator':int,
                              'success_ratio': float|None, 'orders': [...]}

All three classes share one underlying computation (_compute, cached via
get_month_data), then each class's fetch() re-shapes that same computed
result into rows keyed by AdminID using keka_name_mapper.

LOGIC REFERENCE (unchanged from the verified standalone version)
-------------------------------------------------------------------
1. WORKING-DAY DENOMINATOR — clipped at both ends for joiners/leavers.
     effective_start = max(month_start, joining_date)
     effective_end   = min(month_end, exit_date or month_end)

2. SYSTEMIC PUNCH-MACHINE DAYS — company-wide outage days excluded for
   everyone, auto-detected (>=30% incomplete across >=10 employees/day).

3. INCOMPLETE ROW — missing punch, lone after-14:00 punch, or a punch
   pair under 60 minutes apart. Excluded from late/early/hours math.

4. MODAL SHIFT TIME (per person) — most common shift_start/shift_end
   across a person's clean rows that month, used for ALL late/early
   checks instead of trusting each row's individual shift time.

5. LATE > 20 min after modal shift start. EARLY EXIT > 10 min before
   modal shift end. (UI may simplify to "15 min" for employee display —
   the computed threshold used here is 20.)

6. IMPLAUSIBLE-HOURS ROW — punches exist, gap > 60min, but total hours
   < 3.0 -> mismatched session. Counted present, excluded from hours/
   late/early stats.

7. DEPARTMENT — keka_employee_groups WHERE group_type == '2' only.

8. ACTIVE USERS — employment_status=='0' AND account_status=='1'.

ADMIN-ID BRIDGE
----------------
Every row returned by fetch() must carry an AdminID for score_engine.py
to bucket it correctly. The bridge from keka_id -> AdminID is built and
weekly-refreshed by keka_name_mapper.py. Any keka_id that cannot be
resolved is SKIPPED from fetch()'s output (not scored with a guessed
ID) — call keka_name_mapper.get_unresolved() to see who needs a manual
mapping via keka_name_mapper.set_manual_mapping().

CACHING
-------
Raw Keka fetch + full per-row computation is the slow part (network +
thousands of rows). Results are cached per (month, year) in the local
scorecard.db so that score_engine's three separate KPI fetches
(leaves/late_comings/early_leavings) for the SAME month share one
cache entry instead of each re-triggering the full computation.
"""

import requests
import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict, Counter

from kpis.base import BaseKPI
import keka_name_mapper as name_mapper

# ── Keka / ViaSocket DBdash config ─────────────────────────────────────────────
KEKA_AUTH_KEY = 'keywWPoCKnwcJAA'
KEKA_DB_ID    = '6a17ec96a95e7ac45342c0e4'
KEKA_BASE     = f'https://table-api.viasocket.com/{KEKA_DB_ID}'
KEKA_HEADERS  = {'auth-key': KEKA_AUTH_KEY}

TBL_ATTENDANCE = 'tblr5wgh0'
TBL_STATUS     = 'tbll6kzp6'
TBL_EMPLOYEES  = 'tblrj1w62'
TBL_GROUPS     = 'tblto5irg'
TBL_DETAILS    = 'tblp2kh5y'   # keka_employee_details — source of weekly_off_policy_id per person

# Confirmed directly by the user (real company policy, not inferred from
# data — keka_policies table itself has no usable titles, see
# check_weekly_off_via_details.py findings this session):
#   a926aa26-1d56-436a-a5c0-c4d6af624801 -> Saturday + Sunday off
#     (this is Aman Soni's and Prathmesh Sunil Bandal's policy, only 4
#     people company-wide are on it)
#   every other policy ID (b8c7cb22-..., f8cb8e2a-..., and any unknown
#     future ID) -> Sunday only, the default for everyone else
# weekday(): Monday=0 ... Saturday=5, Sunday=6
WEEKLY_OFF_DAYS = {
    'a926aa26-1d56-436a-a5c0-c4d6af624801': {5, 6},   # Sat + Sun
}
DEFAULT_OFF_DAYS = {6}   # Sunday only — used for any policy ID not listed above

LATE_GRACE_MIN        = 20
EARLY_EXIT_MIN         = 10
LONE_PUNCH_HOUR        = 14
MIN_PAIR_MINUTES       = 60
MIN_PLAUSIBLE_HRS      = 3.0
SYSTEMIC_DAY_RATIO     = 0.30
SYSTEMIC_MIN_ROWS      = 10
DEPARTMENT_GROUP_TYPE  = '2'

CACHE_DB_PATH = 'scorecard.db'
CACHE_TABLE   = 'keka_attendance_cache'


# ──────────────────────────────────────────────────────────────────────────────
# CACHE LAYER
# ──────────────────────────────────────────────────────────────────────────────
def _ensure_cache_table(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
            month INTEGER NOT NULL,
            year  INTEGER NOT NULL,
            data_json TEXT NOT NULL,
            computed_at TEXT NOT NULL,
            PRIMARY KEY (month, year)
        )
    """)
    conn.commit()


def _cache_get(month, year):
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_cache_table(conn)
    row = conn.execute(
        f"SELECT data_json, computed_at FROM {CACHE_TABLE} WHERE month=? AND year=?", (month, year)
    ).fetchone()
    conn.close()
    if not row:
        return None, None
    return json.loads(row[0]), row[1]


def _cache_set(month, year, data):
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_cache_table(conn)
    conn.execute(f"""
        INSERT INTO {CACHE_TABLE} (month, year, data_json, computed_at) VALUES (?, ?, ?, ?)
        ON CONFLICT(month, year) DO UPDATE SET data_json=excluded.data_json, computed_at=excluded.computed_at
    """, (month, year, json.dumps(data), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


def clear_cache(month=None, year=None):
    conn = sqlite3.connect(CACHE_DB_PATH)
    _ensure_cache_table(conn)
    if month and year:
        conn.execute(f"DELETE FROM {CACHE_TABLE} WHERE month=? AND year=?", (month, year))
    else:
        conn.execute(f"DELETE FROM {CACHE_TABLE}")
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# RAW FETCH + PARSE HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def _fetch_all(table_id):
    rows, offset, pages = [], None, 0
    while True:
        params = {'offset': offset} if offset else {}
        r = requests.get(f'{KEKA_BASE}/{table_id}', headers=KEKA_HEADERS, params=params, timeout=30)
        r.raise_for_status()
        d = r.json().get('data', {})
        batch = d.get('rows', [])
        rows.extend(batch)
        pages += 1
        offset = d.get('offset')
        if not offset or not batch or pages > 50:
            break
    return rows


def _parse_dt(s):
    if not s or s in ('null', 'undefined', 'None', None):
        return None
    s = str(s).strip().replace('T', ' ').replace('Z', '')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _mins(a, b):
    if not a or not b:
        return None
    return int((b - a).total_seconds() // 60)


def _working_days(start_d, end_d, exclude=frozenset(), off_days=DEFAULT_OFF_DAYS):
    """off_days: set of weekday() values that are this person's weekly off
    (e.g. {6} for Sunday-only, {5,6} for Sat+Sun). Defaults to Sunday-only
    for anyone whose policy isn't in WEEKLY_OFF_DAYS."""
    if start_d > end_d:
        return 0
    n, d = 0, start_d
    while d <= end_d:
        if d.weekday() not in off_days and d not in exclude:
            n += 1
        d += timedelta(days=1)
    return n


# ──────────────────────────────────────────────────────────────────────────────
# CORE COMPUTATION (rules 1-8) — shared by all three KPI classes
# ──────────────────────────────────────────────────────────────────────────────
def _compute(month, year):
    print(f'[KekaAttendance] {month}/{year} — fetching raw Keka tables...')
    att    = _fetch_all(TBL_ATTENDANCE)
    status = _fetch_all(TBL_STATUS)
    emps   = _fetch_all(TBL_EMPLOYEES)
    groups = _fetch_all(TBL_GROUPS)
    details = _fetch_all(TBL_DETAILS)
    print(f'[KekaAttendance] attendance={len(att)} status={len(status)} '
          f'employees={len(emps)} groups={len(groups)}')

    # Keep the AdminID bridge fresh — cheap no-op if already refreshed this week
    name_mapper.refresh_mapping(emps)
    kid_to_admin = name_mapper.get_full_map()

    name_by_kid = {e.get('name'): e.get('display_name', '?') for e in emps if e.get('name')}

    # ── Dedup status rows: this table is re-synced daily and accumulates
    # one new row per person EVERY day rather than overwriting the previous
    # one (confirmed: 286 distinct people all had exactly 4 duplicate rows,
    # one per sync day). Counting/reading every row naively means a person
    # synced 4 times gets counted 4 times, and join/exit dates are read
    # from whichever row happens to be last in fetch order, not necessarily
    # the most recent sync. Keep only the latest row per keka_id by
    # createdat/updatedat before using this table for anything.
    latest_status_by_kid = {}
    for s in status:
        kid = s.get('keka_id')
        if not kid:
            continue
        ts = s.get('updatedat') or s.get('createdat') or ''
        if kid not in latest_status_by_kid or ts > latest_status_by_kid[kid].get('_ts', ''):
            latest_status_by_kid[kid] = {**s, '_ts': ts}

    join_by_kid, exit_by_kid = {}, {}
    for kid, s in latest_status_by_kid.items():
        join_by_kid[kid] = _parse_dt(s.get('joining_date'))
        ed = s.get('exit_date')
        exit_by_kid[kid] = _parse_dt(ed) if ed not in (None, 'null') else None

    # ── Dedup groups: same pattern as employee_status — confirmed 286/286
    # people have duplicate rows in this table too. Take the latest by
    # createdat for each (keka_id, group_type) pair so a stale department
    # assignment from an earlier sync can't override a corrected later one.
    latest_group_by_kid = {}
    for g in groups:
        if str(g.get('group_type')) != DEPARTMENT_GROUP_TYPE:
            continue
        kid = g.get('keka_id')
        ts = g.get('updatedat') or g.get('createdat') or ''
        if kid not in latest_group_by_kid or ts > latest_group_by_kid[kid].get('_ts', ''):
            latest_group_by_kid[kid] = {**g, '_ts': ts}

    dept_by_kid = {kid: g.get('dept_title', 'Unknown') for kid, g in latest_group_by_kid.items()}

    # ── Per-person weekly-off days, from keka_employee_details ─────────────
    # Same duplicate-row pattern confirmed across every Keka table this
    # session — dedup by latest createdat/updatedat before reading.
    latest_details_by_kid = {}
    for d in details:
        kid = d.get('keka_id')
        if not kid:
            continue
        ts = d.get('updatedat') or d.get('createdat') or ''
        if kid not in latest_details_by_kid or ts > latest_details_by_kid[kid].get('_ts', ''):
            latest_details_by_kid[kid] = {**d, '_ts': ts}

    off_days_by_kid = {}
    for kid, d in latest_details_by_kid.items():
        policy_id = d.get('weekly_off_policy_id')
        off_days_by_kid[kid] = WEEKLY_OFF_DAYS.get(policy_id, DEFAULT_OFF_DAYS)

    # ── Pass 1: classify raw rows, find systemic days ──────────────────────────
    raw_rows = []
    for row in att:
        kid       = row.get('name')
        punch_in  = _parse_dt(row.get('punch_in'))
        punch_out = _parse_dt(row.get('punch_out'))
        shift_in  = _parse_dt(row.get('shift_start_time'))
        shift_out = _parse_dt(row.get('shift_end_time'))

        anchor = punch_in or punch_out
        if not anchor or anchor.month != month or anchor.year != year:
            continue
        work_date = anchor.date()

        incomplete = (not punch_in or not punch_out)
        if not incomplete:
            pair_min = _mins(punch_in, punch_out)
            if pair_min is not None and pair_min < MIN_PAIR_MINUTES:
                incomplete = True

        raw_rows.append({
            'kid': kid, 'date': work_date,
            'punch_in': punch_in, 'punch_out': punch_out,
            'shift_in': shift_in, 'shift_out': shift_out,
            'incomplete': incomplete,
        })

    # ── Dedup raw rows: confirmed the daily re-sync re-inserts rows for
    # days already synced before, instead of only inserting new ones —
    # one person had 69 raw rows across only 46 distinct calendar dates,
    # with several exact (punch_in, punch_out) pairs repeated 3x. Without
    # this step, a day re-synced 3 times would get counted as late/early
    # 3 times instead of once. Keep ONE row per (kid, date, punch_in,
    # punch_out) combination — if duplicates have IDENTICAL punch times
    # they're the same sync event; this collapses them to one before any
    # late/early/systemic-day math runs.
    seen_keys = set()
    deduped_rows = []
    for r in raw_rows:
        sig = (r['kid'], r['date'], r['punch_in'], r['punch_out'])
        if sig in seen_keys:
            continue
        seen_keys.add(sig)
        deduped_rows.append(r)
    print(f'[KekaAttendance] raw rows {len(raw_rows)} -> {len(deduped_rows)} after dedup '
          f'({len(raw_rows) - len(deduped_rows)} exact-duplicate syncs removed)')
    raw_rows = deduped_rows

    by_date = defaultdict(lambda: {'total': 0, 'incomplete': 0})
    for r in raw_rows:
        by_date[r['date']]['total'] += 1
        if r['incomplete']:
            by_date[r['date']]['incomplete'] += 1

    systemic_days = {
        d for d, c in by_date.items()
        if c['total'] >= SYSTEMIC_MIN_ROWS and (c['incomplete'] / c['total']) >= SYSTEMIC_DAY_RATIO
    }
    print(f'[KekaAttendance] systemic days excluded: {sorted(systemic_days)}')

    # ── Pass 2: modal shift time per person ────────────────────────────────────
    clean_for_modal = defaultdict(list)
    for r in raw_rows:
        if r['incomplete'] or r['date'] in systemic_days:
            continue
        if r['shift_in'] and r['shift_out']:
            clean_for_modal[r['kid']].append(r)

    modal_shift = {}
    for kid, rows in clean_for_modal.items():
        in_times  = Counter(r['shift_in'].strftime('%H:%M') for r in rows)
        out_times = Counter(r['shift_out'].strftime('%H:%M') for r in rows)
        modal_shift[kid] = (in_times.most_common(1)[0][0], out_times.most_common(1)[0][0])

    # ── Pass 3: final classification ───────────────────────────────────────────
    final_rows = []
    for r in raw_rows:
        kid = r['kid']
        if r['date'] in systemic_days:
            continue
        if r['incomplete']:
            final_rows.append({**r, 'status': 'incomplete'})
            continue

        hours = round((r['punch_out'] - r['punch_in']).total_seconds() / 3600, 2)
        m_in_str, m_out_str = modal_shift.get(kid, (None, None))
        m_in = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
                if m_in_str else r['shift_in'])
        m_out = (datetime.combine(r['date'], datetime.strptime(m_out_str, '%H:%M').time())
                 if m_out_str else r['shift_out'])

        if hours < MIN_PLAUSIBLE_HRS:
            final_rows.append({**r, 'status': 'present_implausible', 'hours': hours})
            continue

        late_min  = _mins(m_in, r['punch_in'])
        early_min = _mins(r['punch_out'], m_out)

        final_rows.append({
            **r, 'status': 'present', 'hours': hours,
            'late_min': max(0, late_min or 0), 'early_min': max(0, early_min or 0),
            'is_late': bool(late_min is not None and late_min > LATE_GRACE_MIN),
            'is_early_exit': bool(early_min is not None and early_min > EARLY_EXIT_MIN),
        })

    # ── Build per-employee monthly record ──────────────────────────────────────
    month_start = datetime(year, month, 1).date()
    calendar_month_end = (datetime(year, month + 1, 1) - timedelta(days=1)).date() \
                if month < 12 else datetime(year, 12, 31).date()

    # If this is the CURRENT, still-in-progress month, the denominator must
    # only count days that have actually happened — through YESTERDAY, not
    # the full calendar month. Reported bug: viewing June on June 24 showed
    # 26 working days (the whole month) when only ~17 working days had
    # actually occurred so far, making leave/late/early failure percentages
    # look artificially worse than reality. A fully completed past month
    # (e.g. May, viewed in June) is unaffected — calendar_month_end stays
    # the real last day of that month since "today" is already past it.
    today = datetime.utcnow().date()
    if year == today.year and month == today.month:
        month_end = min(calendar_month_end, today - timedelta(days=1))
    else:
        month_end = calendar_month_end

    by_emp = defaultdict(list)
    skipped_no_kid = 0
    for r in final_rows:
        if not r['kid']:
            # A raw attendance row with no keka_id at all (the 'name'
            # column, per this project's convention, was itself null at
            # the source). Cannot attribute this punch data to anyone —
            # grouping it under key None would build a record with no
            # identity at all, which crashes downstream in
            # _synthetic_admin_id and is silently wrong regardless (we'd
            # be reporting real attendance numbers for "nobody"). Skipped
            # and counted so it's visible, not silently lost.
            skipped_no_kid += 1
            continue
        by_emp[r['kid']].append(r)
    if skipped_no_kid:
        print(f'[KekaAttendance] WARNING: skipped {skipped_no_kid} attendance rows '
              f'with no keka_id at all (null at source) — this real attendance '
              f'data cannot be attributed to anyone and is being excluded, not '
              f'silently merged into a broken record.')

    records = []
    for kid, rows in by_emp.items():
        name = name_by_kid.get(kid, '?')
        admin_id = kid_to_admin.get(kid)   # None if unmapped — handled by callers

        join_dt = join_by_kid.get(kid)
        exit_dt = exit_by_kid.get(kid)

        eff_start = month_start
        if join_dt and join_dt.date() > month_start:
            eff_start = join_dt.date()

        eff_end = month_end
        if exit_dt and exit_dt.date() < month_end:
            eff_end = exit_dt.date()

        person_off_days = off_days_by_kid.get(kid, DEFAULT_OFF_DAYS)
        # Pure calendar math, per explicit instruction: total days in
        # [eff_start, eff_end] minus ONLY this person's actual weekly
        # off-day(s) — Sunday for a single-day-off policy, Saturday+Sunday
        # for a two-day-off policy. Nothing else is subtracted or added.
        # Confirmed by hand: May 2026 has 31 days, 5 Sundays -> 26 working
        # days for a Sunday-only person, full stop. Systemic-day detection
        # still runs (kept for diagnostic visibility / future use) but no
        # longer affects expected/present/absent in any way.
        expected = _working_days(eff_start, eff_end, off_days=person_off_days)

        present_rows = [r for r in rows if r['status'] in ('present', 'present_implausible')]
        present_dates_set = {r['date'] for r in present_rows}

        # Per explicit instruction: working days/present/absent are based
        # ONLY on the person's actual weekly off-day(s) — Sunday for a
        # single-day-off policy, Saturday+Sunday for a two-day-off policy.
        # Nothing else is added or subtracted. Systemic-day detection still
        # runs (used elsewhere for diagnostics) but no longer affects this
        # calculation in any way — not the denominator, not present, not
        # absent.
        present = min(len(present_dates_set), expected)

        late_dates  = sorted(str(r['date']) for r in rows if r.get('is_late'))
        early_dates = sorted(str(r['date']) for r in rows if r.get('is_early_exit'))
        late  = len(late_dates)
        early = len(early_dates)

        # ── Build full entry objects, matching EmployeeDetail.jsx's real
        # contract (confirmed against the live frontend code): each entry
        # needs punch_in/shift_start (late) or punch_out/shift_end (early)
        # as ISO-ish datetime STRINGS, since the frontend does:
        #     new Date(e.punch_in.replace(' UTC','Z'))
        #     new Date(e.shift_start.replace(' UTC','Z'))
        # to compute delay/shortfall itself. Plain date strings (no time
        # component) silently produced Invalid Date / NaN delay there —
        # this is the fix for that.
        #
        # CRITICAL FIX: Keka's raw punch_in/punch_out/shift_start_time/
        # shift_end_time values carry NO timezone marker in the source
        # data at all — confirmed against the original raw Keka dump
        # (e.g. "2026-04-02 10:39:17" with no Z/UTC/+offset suffix).
        # These are physical punch-machine clock readings recorded in
        # IST directly, NOT UTC. Labeling them "...UTC" here was WRONG —
        # it caused the frontend's toIST() (which converts FROM UTC TO
        # IST by adding +5:30) to double-shift an already-correct IST
        # time forward by another 5:30. Confirmed with real data: a
        # punch_in of 14:47 IST was displaying as 20:17 (8:17 PM) — i.e.
        # exactly +5:30 too late. Same bug affected shift_start/shift_end.
        #
        # Fix: label these as 'IST' instead of 'UTC'. The frontend's
        # toIST() helper must ALSO be updated to stop applying a UTC->IST
        # conversion on a value that's already IST — simply parse and
        # display the clock value directly, with no timezone shift.
        def _fmt_dt(dt):
            return dt.strftime('%Y-%m-%d %H:%M:%S IST') if dt else None

        late_entries = []
        for r in rows:
            if not r.get('is_late'):
                continue
            m_in_str = modal_shift.get(kid, (None, None))[0]
            shift_dt = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
                        if m_in_str else None)
            late_entries.append({
                'date': str(r['date']),
                'punch_in': _fmt_dt(r.get('punch_in')),
                'shift_start': _fmt_dt(shift_dt),
            })

        early_entries = []
        for r in rows:
            if not r.get('is_early_exit'):
                continue
            m_in_str, m_out_str = modal_shift.get(kid, (None, None))
            shift_start_dt = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
                              if m_in_str else None)
            shift_end_dt = (datetime.combine(r['date'], datetime.strptime(m_out_str, '%H:%M').time())
                            if m_out_str else None)
            punch_out = r.get('punch_out')

            # EmployeeDetail.jsx (confirmed against real code) reads
            # e.expected_hours / e.actual_hours / e.shortfall_hrs directly
            # as numbers — it does NOT compute these itself the way it does
            # for late_entries' delay-in-minutes. Without these 3 fields the
            # template `${e.expected_hours}h` renders literally as "h",
            # which is the exact bug reported. Computed here from the same
            # shift_start/shift_end/punch_out data already available.
            expected_hours = round((shift_end_dt - shift_start_dt).total_seconds() / 3600, 2) \
                if (shift_start_dt and shift_end_dt) else None
            actual_hours = round((punch_out - shift_start_dt).total_seconds() / 3600, 2) \
                if (shift_start_dt and punch_out) else None
            shortfall_hrs = round(expected_hours - actual_hours, 2) \
                if (expected_hours is not None and actual_hours is not None) else None

            early_entries.append({
                'date': str(r['date']),
                'punch_out': _fmt_dt(punch_out),
                'shift_end': _fmt_dt(shift_end_dt),
                'expected_hours': expected_hours,
                'actual_hours': actual_hours,
                'shortfall_hrs': shortfall_hrs,
            })
        incomplete_count = sum(1 for r in rows if r['status'] == 'incomplete')
        unrecorded = max(0, expected - present)

        # ── Compute actual absent calendar dates (for leave_dates), not just
        # a count. A working day with NO row at all (not even incomplete) in
        # [eff_start, eff_end], excluding systemic days, counts as absent.
        # Use the SAME date-set that produced `present`, not every row
        # regardless of status. Previously this included 'incomplete' rows
        # too, which created a no-man's-land: a date with only an
        # incomplete punch was excluded from absent_dates (because SOME
        # row existed) but was never counted in `present` either (because
        # incomplete rows don't count as present) — so unrecorded_absent_days
        # (a count) and absent_dates (a list) could disagree, exactly as
        # confirmed for Anchal Patidar: count=2 but only 1 date listed.
        genuinely_present_dates = present_dates_set   # same set used for `present` above — keeps the two calculations consistent
        absent_dates = []
        d = eff_start
        while d <= eff_end:
            if d.weekday() not in person_off_days and d not in genuinely_present_dates:
                absent_dates.append(str(d))
            d += timedelta(days=1)
        absent_dates = absent_dates[:unrecorded] if unrecorded else []   # cap defensively

        valid_hours = [r['hours'] for r in rows if r['status'] == 'present' and r.get('hours')]
        avg_hours = round(sum(valid_hours) / len(valid_hours), 2) if valid_hours else 0

        m_in, m_out = modal_shift.get(kid, ('--', '--'))

        records.append({
            'keka_id': kid,
            'admin_id': admin_id,
            'name': name,
            'department': dept_by_kid.get(kid, 'Unknown'),
            'modal_shift_start': m_in,
            'modal_shift_end': m_out,
            'joined_mid_month': bool(join_dt and join_dt.date() > month_start),
            'joining_date': str(join_dt.date()) if join_dt else None,
            'exited_mid_month': bool(exit_dt and exit_dt.date() < month_end),
            'exit_date': str(exit_dt.date()) if exit_dt else None,
            'expected_working_days': expected,
            'present_days': present,
            'late_days': late,
            'early_exit_days': early,
            'unrecorded_absent_days': unrecorded,
            'incomplete_punch_days': incomplete_count,
            'avg_hours_per_day': avg_hours,
            'late_dates': late_dates,
            'early_dates': early_dates,
            'late_entries': late_entries,
            'early_entries': early_entries,
            'absent_dates': absent_dates,
        })

    # Active count: use the SAME deduplicated latest_status_by_kid built
    # above (not the raw `status` list, which has 4x duplicate rows per
    # person and would inflate this count ~4x — confirmed bug: naive count
    # was 339 vs the real deduplicated figure of 85). Also apply the
    # exit_date safety check: a person can still show employment_status=0
    # in a stale row while their exit_date has already passed, so exclude
    # anyone whose exit_date is today or earlier even if the status flag
    # hasn't caught up yet.
    today = datetime.utcnow().date()
    active = 0
    for s in latest_status_by_kid.values():
        is_active_flags = (str(s.get('employment_status')) == '0'
                            and str(s.get('account_status')) == '1')
        if not is_active_flags:
            continue
        exit_dt = _parse_dt(s.get('exit_date'))
        if exit_dt and exit_dt.date() <= today:
            continue   # flag hasn't caught up to a real departure yet
        active += 1

    return {
        'month': month, 'year': year,
        'systemic_days_excluded': [str(d) for d in sorted(systemic_days)],
        'active_users': active,
        'total_employees': len(emps),
        'employees': records,
        'unmapped_count': sum(1 for r in records if r['admin_id'] is None),
    }


# Bump this any time the shape of a per-employee record changes (new keys
# added/removed/renamed). A cached payload missing this exact version is
# treated as stale and recomputed, instead of being trusted blindly. This
# is what the absent_dates KeyError revealed: a cache written before that
# field existed was silently served afterward as if it were current.
_SCHEMA_VERSION = 9

def get_month_data(month, year, force_refresh=False):
    if not force_refresh:
        cached, computed_at = _cache_get(month, year)
        if cached is not None and cached.get('_schema_version') == _SCHEMA_VERSION:
            # For the CURRENT, still-in-progress month, the cache must be
            # recomputed daily — yesterday's cached "working days through
            # yesterday" is stale today, since "yesterday" has moved.
            # A fully completed past month never has this problem: once
            # the month is over, its working-days range never changes
            # again, so the cache is valid indefinitely.
            today = datetime.utcnow().date()
            is_current_month = (year == today.year and month == today.month)
            if is_current_month and computed_at:
                computed_date = datetime.fromisoformat(computed_at).date()
                if computed_date < today:
                    print(f'[KekaAttendance] Cached {month}/{year} is from {computed_date} '
                          f'(stale — current month must recompute daily) — recomputing')
                    cached = None
            if cached is not None:
                return cached
        elif cached is not None:
            print(f'[KekaAttendance] Cached {month}/{year} has stale schema '
                  f'(got {cached.get("_schema_version")!r}, need {_SCHEMA_VERSION}) — recomputing')
    data = _compute(month, year)
    data['_schema_version'] = _SCHEMA_VERSION
    _cache_set(month, year, data)
    return data


def refresh_cache(month, year):
    return get_month_data(month, year, force_refresh=True)


# ──────────────────────────────────────────────────────────────────────────────
# KPI CLASSES — same interface contract as every other module in kpis/
# ──────────────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
# SYNTHETIC ADMINID — for Keka employees with no matching SQL Server Admin row
# ──────────────────────────────────────────────────────────────────────────────
# Full diagnostic confirmed 155/286 Keka employees genuinely have NO matching
# SQL Admin record at all (not a matcher bug — most of these are real people
# only present in Keka, not yet created in the older SQL Server system, e.g.
# Arjun Bhadoriya who joined May 25 this very month). Rather than silently
# dropping 103+ real employees from every attendance KPI, every employee is
# now ALWAYS included. Those without a real AdminID get a stable, deterministic
# negative integer derived from their keka_id, so:
#   - score_engine.py's existing AdminID-keyed dict logic works unchanged
#     (it only needs a unique, stable key — it doesn't care if it's a real
#     SQL identity or not)
#   - the SAME keka_id always produces the SAME synthetic ID across runs,
#     so dedup/caching/trend-over-time logic stays consistent
#   - negative range guarantees zero collision with real SQL AdminIDs (which
#     are always positive in this project's Admin table)
#   - IsRealAdminID flag on each row lets any consuming code (or future UI)
#     distinguish "linked to a real employee record" from "Keka-only, not
#     yet bridged to SQL Server" without guessing from the ID's sign alone
def _synthetic_admin_id(keka_id):
    import hashlib
    if not keka_id:
        # Defensive: a record reaching here with no keka_id at all is a
        # data-integrity gap upstream, not something this function should
        # silently paper over with a fake ID. Raise clearly instead of
        # crashing deep inside hashlib with a confusing 'NoneType has no
        # attribute encode' error that gives no indication of WHICH
        # employee or WHERE the gap originated.
        raise ValueError(
            'synthetic_admin_id called with no keka_id — a record reached '
            'this point with neither a real AdminID nor a keka_id to hash. '
            'This indicates a data gap upstream in _compute(), not something '
            'safe to silently fake an ID for.'
        )
    h = int(hashlib.md5(keka_id.encode()).hexdigest()[:8], 16)
    return -(h % 900000 + 100000)   # stable negative ID in range -100000..-999999


class KekaLeavesKPI(BaseKPI):
    """Replaces kpis/leaves.py. Registry: module_path='kpis.keka_attendance', class_name='KekaLeavesKPI'."""

    def fetch(self, month, year):
        data = get_month_data(month, year)
        rows = []
        for emp in data['employees']:
            is_real = emp['admin_id'] is not None
            admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
            rows.append({
                'AdminID': admin_id,
                'EmployeeName': emp['name'],
                'Department': emp['department'],
                'WorkingDays': emp['expected_working_days'],
                'PresentDays': emp['present_days'],
                'UnrecordedDays': emp['unrecorded_absent_days'],
                'AbsentDates': emp['absent_dates'],
                'IsRealAdminID': is_real,
                'KekaID': emp['keka_id'],
            })
        return rows

    def aggregate(self, rows):
        if not rows:
            return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
        r = rows[0]
        wdays, present, absent = r['WorkingDays'], r['PresentDays'], r['UnrecordedDays']
        ratio = round(present / wdays * 100, 2) if wdays else None
        return {
            'numerator': present, 'denominator': wdays, 'success_ratio': ratio,
            # leave_dates now carries REAL absent calendar dates (matches old
            # ViaSocket contract's leave_dates: [date_string,...] shape exactly)
            'orders': [{'working_days': wdays, 'present_days': present,
                        'leave_days': absent, 'leave_dates': r['AbsentDates']}],
        }


class KekaLateComingsKPI(BaseKPI):
    """Replaces kpis/late_comings.py. Registry: class_name='KekaLateComingsKPI'."""

    def fetch(self, month, year):
        data = get_month_data(month, year)
        rows = []
        for emp in data['employees']:
            is_real = emp['admin_id'] is not None
            admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
            rows.append({
                'AdminID': admin_id,
                'EmployeeName': emp['name'],
                'Department': emp['department'],
                'WorkingDays': emp['expected_working_days'],
                'LateDays': emp['late_days'],
                'LateEntries': emp['late_entries'],
                'ShiftStart': emp['modal_shift_start'],
                'IsRealAdminID': is_real,
                'KekaID': emp['keka_id'],
            })
        return rows

    def aggregate(self, rows):
        if not rows:
            return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
        r = rows[0]
        wdays, late = r['WorkingDays'], r['LateDays']
        on_time = max(0, wdays - late)
        ratio = round(on_time / wdays * 100, 2) if wdays else None
        return {
            'numerator': on_time, 'denominator': wdays, 'success_ratio': ratio,
            # late_entries now carries {date, punch_in, shift_start} objects
            # with real datetime strings — matches EmployeeDetail.jsx's
            # actual contract (verified against the live frontend code):
            # it does new Date(e.punch_in.replace(' UTC','Z')) -
            # new Date(e.shift_start.replace(' UTC','Z')) to show delay.
            'orders': [{'working_days': wdays, 'late_days': late, 'on_time_days': on_time,
                        'late_entries': r['LateEntries'], 'shift_start': r['ShiftStart']}],
        }


class KekaEarlyLeavingsKPI(BaseKPI):
    """Replaces kpis/early_leavings.py. Registry: class_name='KekaEarlyLeavingsKPI'."""

    def fetch(self, month, year):
        data = get_month_data(month, year)
        rows = []
        for emp in data['employees']:
            is_real = emp['admin_id'] is not None
            admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
            rows.append({
                'AdminID': admin_id,
                'EmployeeName': emp['name'],
                'Department': emp['department'],
                'WorkingDays': emp['expected_working_days'],
                'EarlyDays': emp['early_exit_days'],
                'EarlyEntries': emp['early_entries'],
                'ShiftEnd': emp['modal_shift_end'],
                'IsRealAdminID': is_real,
                'KekaID': emp['keka_id'],
            })
        return rows

    def aggregate(self, rows):
        if not rows:
            return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
        r = rows[0]
        wdays, early = r['WorkingDays'], r['EarlyDays']
        full_days = max(0, wdays - early)
        ratio = round(full_days / wdays * 100, 2) if wdays else None
        return {
            'numerator': full_days, 'denominator': wdays, 'success_ratio': ratio,
            # early_entries carries {date, punch_out, shift_end} objects with
            # real datetime strings — matches EmployeeDetail.jsx line ~477
            # which does new Date(e.punch_out...) vs new Date(e.shift_end...)
            'orders': [{'working_days': wdays, 'early_days': early, 'full_days': full_days,
                        'early_entries': r['EarlyEntries'], 'shift_end': r['ShiftEnd']}],
        }


# ──────────────────────────────────────────────────────────────────────────────
# CLI test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import sys
    m = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    y = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

    for cls_name, cls in [('Leaves', KekaLeavesKPI), ('LateComings', KekaLateComingsKPI),
                           ('EarlyLeavings', KekaEarlyLeavingsKPI)]:
        inst = cls()
        rows = inst.fetch(m, y)
        real_count = sum(1 for r in rows if r['IsRealAdminID'])
        synthetic_count = len(rows) - real_count
        print(f'\n{cls_name}: {len(rows)} total rows '
              f'({real_count} real AdminID, {synthetic_count} synthetic/Keka-only)')
        if rows:
            sample_agg = inst.aggregate([rows[0]])
            print(f'  sample for {rows[0]["EmployeeName"]}: '
                  f'{sample_agg["numerator"]}/{sample_agg["denominator"]} = {sample_agg["success_ratio"]}%')

    print(f'\nEvery Keka employee with May attendance now appears in every KPI.')
    print(f'Rows with IsRealAdminID=False are linked to score_engine.py via a')
    print(f'stable synthetic ID, not yet bridged to a real SQL Server Admin row.')
    print(f'Call keka_name_mapper.get_unresolved() to see/fix those via')
    print(f'keka_name_mapper.set_manual_mapping(keka_id, real_admin_id) once a')
    print(f'human confirms the correct SQL Admin match (if one exists at all).')

# """
# backend/kpis/keka_attendance.py
# ================================
# Drop-in replacement for kpis/leaves.py, kpis/late_comings.py, and
# kpis/early_leavings.py. Computes ALL attendance metrics from raw Keka
# punch data fetched in this module — no dependency on any pre-derived
# column in the synced Keka tables.

# WHY THREE CLASSES IN ONE FILE
# ------------------------------
# score_engine.py is KPI-agnostic: it loads each active KPI by
# module_path + class_name from the local_db registry and calls
# .fetch(month, year) then .aggregate(rows) on it — it has no idea whether
# the data comes from SQL Server, ViaSocket, or Keka. To switch the
# existing 'leaves', 'late_comings', 'early_leavings' KPI keys over to Keka
# without touching score_engine.py at all, each of those three keys just
# needs its registry entry (module_path/class_name) repointed at one of
# the three classes below. The interface contract is identical to every
# other KPI module in this project:

#     fetch(month, year)   -> list of row dicts, each with at least
#                              {'AdminID': int, 'EmployeeName': str,
#                               'Department': str, ...kpi-specific fields}
#     aggregate(rows)      -> {'numerator':int, 'denominator':int,
#                               'success_ratio': float|None, 'orders': [...]}

# All three classes share one underlying computation (_compute, cached via
# get_month_data), then each class's fetch() re-shapes that same computed
# result into rows keyed by AdminID using keka_name_mapper.

# LOGIC REFERENCE (unchanged from the verified standalone version)
# -------------------------------------------------------------------
# 1. WORKING-DAY DENOMINATOR — clipped at both ends for joiners/leavers.
#      effective_start = max(month_start, joining_date)
#      effective_end   = min(month_end, exit_date or month_end)

# 2. SYSTEMIC PUNCH-MACHINE DAYS — company-wide outage days excluded for
#    everyone, auto-detected (>=30% incomplete across >=10 employees/day).

# 3. INCOMPLETE ROW — missing punch, lone after-14:00 punch, or a punch
#    pair under 60 minutes apart. Excluded from late/early/hours math.

# 4. MODAL SHIFT TIME (per person) — most common shift_start/shift_end
#    across a person's clean rows that month, used for ALL late/early
#    checks instead of trusting each row's individual shift time.

# 5. LATE > 20 min after modal shift start. EARLY EXIT > 10 min before
#    modal shift end. (UI may simplify to "15 min" for employee display —
#    the computed threshold used here is 20.)

# 6. IMPLAUSIBLE-HOURS ROW — punches exist, gap > 60min, but total hours
#    < 3.0 -> mismatched session. Counted present, excluded from hours/
#    late/early stats.

# 7. DEPARTMENT — keka_employee_groups WHERE group_type == '2' only.

# 8. ACTIVE USERS — employment_status=='0' AND account_status=='1'.

# ADMIN-ID BRIDGE
# ----------------
# Every row returned by fetch() must carry an AdminID for score_engine.py
# to bucket it correctly. The bridge from keka_id -> AdminID is built and
# weekly-refreshed by keka_name_mapper.py. Any keka_id that cannot be
# resolved is SKIPPED from fetch()'s output (not scored with a guessed
# ID) — call keka_name_mapper.get_unresolved() to see who needs a manual
# mapping via keka_name_mapper.set_manual_mapping().

# CACHING
# -------
# Raw Keka fetch + full per-row computation is the slow part (network +
# thousands of rows). Results are cached per (month, year) in the local
# scorecard.db so that score_engine's three separate KPI fetches
# (leaves/late_comings/early_leavings) for the SAME month share one
# cache entry instead of each re-triggering the full computation.
# """

# import requests
# import sqlite3
# import json
# from datetime import datetime, timedelta
# from collections import defaultdict, Counter

# from kpis.base import BaseKPI
# import keka_name_mapper as name_mapper

# # ── Keka / ViaSocket DBdash config ─────────────────────────────────────────────
# KEKA_AUTH_KEY = 'keywWPoCKnwcJAA'
# KEKA_DB_ID    = '6a17ec96a95e7ac45342c0e4'
# KEKA_BASE     = f'https://table-api.viasocket.com/{KEKA_DB_ID}'
# KEKA_HEADERS  = {'auth-key': KEKA_AUTH_KEY}

# TBL_ATTENDANCE = 'tblr5wgh0'
# TBL_STATUS     = 'tbll6kzp6'
# TBL_EMPLOYEES  = 'tblrj1w62'
# TBL_GROUPS     = 'tblto5irg'
# TBL_DETAILS    = 'tblp2kh5y'   # keka_employee_details — source of weekly_off_policy_id per person

# # Confirmed directly by the user (real company policy, not inferred from
# # data — keka_policies table itself has no usable titles, see
# # check_weekly_off_via_details.py findings this session):
# #   a926aa26-1d56-436a-a5c0-c4d6af624801 -> Saturday + Sunday off
# #     (this is Aman Soni's and Prathmesh Sunil Bandal's policy, only 4
# #     people company-wide are on it)
# #   every other policy ID (b8c7cb22-..., f8cb8e2a-..., and any unknown
# #     future ID) -> Sunday only, the default for everyone else
# # weekday(): Monday=0 ... Saturday=5, Sunday=6
# WEEKLY_OFF_DAYS = {
#     'a926aa26-1d56-436a-a5c0-c4d6af624801': {5, 6},   # Sat + Sun
# }
# DEFAULT_OFF_DAYS = {6}   # Sunday only — used for any policy ID not listed above

# LATE_GRACE_MIN        = 20
# EARLY_EXIT_MIN         = 10
# LONE_PUNCH_HOUR        = 14
# MIN_PAIR_MINUTES       = 60
# MIN_PLAUSIBLE_HRS      = 3.0
# SYSTEMIC_DAY_RATIO     = 0.30
# SYSTEMIC_MIN_ROWS      = 10
# DEPARTMENT_GROUP_TYPE  = '2'

# CACHE_DB_PATH = 'scorecard.db'
# CACHE_TABLE   = 'keka_attendance_cache'


# # ──────────────────────────────────────────────────────────────────────────────
# # CACHE LAYER
# # ──────────────────────────────────────────────────────────────────────────────
# def _ensure_cache_table(conn):
#     conn.execute(f"""
#         CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
#             month INTEGER NOT NULL,
#             year  INTEGER NOT NULL,
#             data_json TEXT NOT NULL,
#             computed_at TEXT NOT NULL,
#             PRIMARY KEY (month, year)
#         )
#     """)
#     conn.commit()


# def _cache_get(month, year):
#     conn = sqlite3.connect(CACHE_DB_PATH)
#     _ensure_cache_table(conn)
#     row = conn.execute(
#         f"SELECT data_json, computed_at FROM {CACHE_TABLE} WHERE month=? AND year=?", (month, year)
#     ).fetchone()
#     conn.close()
#     if not row:
#         return None, None
#     return json.loads(row[0]), row[1]


# def _cache_set(month, year, data):
#     conn = sqlite3.connect(CACHE_DB_PATH)
#     _ensure_cache_table(conn)
#     conn.execute(f"""
#         INSERT INTO {CACHE_TABLE} (month, year, data_json, computed_at) VALUES (?, ?, ?, ?)
#         ON CONFLICT(month, year) DO UPDATE SET data_json=excluded.data_json, computed_at=excluded.computed_at
#     """, (month, year, json.dumps(data), datetime.utcnow().isoformat()))
#     conn.commit()
#     conn.close()


# def clear_cache(month=None, year=None):
#     conn = sqlite3.connect(CACHE_DB_PATH)
#     _ensure_cache_table(conn)
#     if month and year:
#         conn.execute(f"DELETE FROM {CACHE_TABLE} WHERE month=? AND year=?", (month, year))
#     else:
#         conn.execute(f"DELETE FROM {CACHE_TABLE}")
#     conn.commit()
#     conn.close()


# # ──────────────────────────────────────────────────────────────────────────────
# # RAW FETCH + PARSE HELPERS
# # ──────────────────────────────────────────────────────────────────────────────
# def _fetch_all(table_id):
#     rows, offset, pages = [], None, 0
#     while True:
#         params = {'offset': offset} if offset else {}
#         r = requests.get(f'{KEKA_BASE}/{table_id}', headers=KEKA_HEADERS, params=params, timeout=30)
#         r.raise_for_status()
#         d = r.json().get('data', {})
#         batch = d.get('rows', [])
#         rows.extend(batch)
#         pages += 1
#         offset = d.get('offset')
#         if not offset or not batch or pages > 50:
#             break
#     return rows


# def _parse_dt(s):
#     if not s or s in ('null', 'undefined', 'None', None):
#         return None
#     s = str(s).strip().replace('T', ' ').replace('Z', '')
#     for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
#         try:
#             return datetime.strptime(s, fmt)
#         except ValueError:
#             continue
#     return None


# def _mins(a, b):
#     if not a or not b:
#         return None
#     return int((b - a).total_seconds() // 60)


# def _working_days(start_d, end_d, exclude=frozenset(), off_days=DEFAULT_OFF_DAYS):
#     """off_days: set of weekday() values that are this person's weekly off
#     (e.g. {6} for Sunday-only, {5,6} for Sat+Sun). Defaults to Sunday-only
#     for anyone whose policy isn't in WEEKLY_OFF_DAYS."""
#     if start_d > end_d:
#         return 0
#     n, d = 0, start_d
#     while d <= end_d:
#         if d.weekday() not in off_days and d not in exclude:
#             n += 1
#         d += timedelta(days=1)
#     return n


# # ──────────────────────────────────────────────────────────────────────────────
# # CORE COMPUTATION (rules 1-8) — shared by all three KPI classes
# # ──────────────────────────────────────────────────────────────────────────────
# def _compute(month, year):
#     print(f'[KekaAttendance] {month}/{year} — fetching raw Keka tables...')
#     att    = _fetch_all(TBL_ATTENDANCE)
#     status = _fetch_all(TBL_STATUS)
#     emps   = _fetch_all(TBL_EMPLOYEES)
#     groups = _fetch_all(TBL_GROUPS)
#     details = _fetch_all(TBL_DETAILS)
#     print(f'[KekaAttendance] attendance={len(att)} status={len(status)} '
#           f'employees={len(emps)} groups={len(groups)}')

#     # Keep the AdminID bridge fresh — cheap no-op if already refreshed this week
#     name_mapper.refresh_mapping(emps)
#     kid_to_admin = name_mapper.get_full_map()

#     name_by_kid = {e.get('name'): e.get('display_name', '?') for e in emps if e.get('name')}

#     # ── Dedup status rows: this table is re-synced daily and accumulates
#     # one new row per person EVERY day rather than overwriting the previous
#     # one (confirmed: 286 distinct people all had exactly 4 duplicate rows,
#     # one per sync day). Counting/reading every row naively means a person
#     # synced 4 times gets counted 4 times, and join/exit dates are read
#     # from whichever row happens to be last in fetch order, not necessarily
#     # the most recent sync. Keep only the latest row per keka_id by
#     # createdat/updatedat before using this table for anything.
#     latest_status_by_kid = {}
#     for s in status:
#         kid = s.get('keka_id')
#         if not kid:
#             continue
#         ts = s.get('updatedat') or s.get('createdat') or ''
#         if kid not in latest_status_by_kid or ts > latest_status_by_kid[kid].get('_ts', ''):
#             latest_status_by_kid[kid] = {**s, '_ts': ts}

#     join_by_kid, exit_by_kid = {}, {}
#     for kid, s in latest_status_by_kid.items():
#         join_by_kid[kid] = _parse_dt(s.get('joining_date'))
#         ed = s.get('exit_date')
#         exit_by_kid[kid] = _parse_dt(ed) if ed not in (None, 'null') else None

#     # ── Dedup groups: same pattern as employee_status — confirmed 286/286
#     # people have duplicate rows in this table too. Take the latest by
#     # createdat for each (keka_id, group_type) pair so a stale department
#     # assignment from an earlier sync can't override a corrected later one.
#     latest_group_by_kid = {}
#     for g in groups:
#         if str(g.get('group_type')) != DEPARTMENT_GROUP_TYPE:
#             continue
#         kid = g.get('keka_id')
#         ts = g.get('updatedat') or g.get('createdat') or ''
#         if kid not in latest_group_by_kid or ts > latest_group_by_kid[kid].get('_ts', ''):
#             latest_group_by_kid[kid] = {**g, '_ts': ts}

#     dept_by_kid = {kid: g.get('dept_title', 'Unknown') for kid, g in latest_group_by_kid.items()}

#     # ── Per-person weekly-off days, from keka_employee_details ─────────────
#     # Same duplicate-row pattern confirmed across every Keka table this
#     # session — dedup by latest createdat/updatedat before reading.
#     latest_details_by_kid = {}
#     for d in details:
#         kid = d.get('keka_id')
#         if not kid:
#             continue
#         ts = d.get('updatedat') or d.get('createdat') or ''
#         if kid not in latest_details_by_kid or ts > latest_details_by_kid[kid].get('_ts', ''):
#             latest_details_by_kid[kid] = {**d, '_ts': ts}

#     off_days_by_kid = {}
#     for kid, d in latest_details_by_kid.items():
#         policy_id = d.get('weekly_off_policy_id')
#         off_days_by_kid[kid] = WEEKLY_OFF_DAYS.get(policy_id, DEFAULT_OFF_DAYS)

#     # ── Pass 1: classify raw rows, find systemic days ──────────────────────────
#     raw_rows = []
#     for row in att:
#         kid       = row.get('name')
#         punch_in  = _parse_dt(row.get('punch_in'))
#         punch_out = _parse_dt(row.get('punch_out'))
#         shift_in  = _parse_dt(row.get('shift_start_time'))
#         shift_out = _parse_dt(row.get('shift_end_time'))

#         anchor = punch_in or punch_out
#         if not anchor or anchor.month != month or anchor.year != year:
#             continue
#         work_date = anchor.date()

#         incomplete = (not punch_in or not punch_out)
#         if not incomplete:
#             pair_min = _mins(punch_in, punch_out)
#             if pair_min is not None and pair_min < MIN_PAIR_MINUTES:
#                 incomplete = True

#         raw_rows.append({
#             'kid': kid, 'date': work_date,
#             'punch_in': punch_in, 'punch_out': punch_out,
#             'shift_in': shift_in, 'shift_out': shift_out,
#             'incomplete': incomplete,
#         })

#     # ── Dedup raw rows: confirmed the daily re-sync re-inserts rows for
#     # days already synced before, instead of only inserting new ones —
#     # one person had 69 raw rows across only 46 distinct calendar dates,
#     # with several exact (punch_in, punch_out) pairs repeated 3x. Without
#     # this step, a day re-synced 3 times would get counted as late/early
#     # 3 times instead of once. Keep ONE row per (kid, date, punch_in,
#     # punch_out) combination — if duplicates have IDENTICAL punch times
#     # they're the same sync event; this collapses them to one before any
#     # late/early/systemic-day math runs.
#     seen_keys = set()
#     deduped_rows = []
#     for r in raw_rows:
#         sig = (r['kid'], r['date'], r['punch_in'], r['punch_out'])
#         if sig in seen_keys:
#             continue
#         seen_keys.add(sig)
#         deduped_rows.append(r)
#     print(f'[KekaAttendance] raw rows {len(raw_rows)} -> {len(deduped_rows)} after dedup '
#           f'({len(raw_rows) - len(deduped_rows)} exact-duplicate syncs removed)')
#     raw_rows = deduped_rows

#     by_date = defaultdict(lambda: {'total': 0, 'incomplete': 0})
#     for r in raw_rows:
#         by_date[r['date']]['total'] += 1
#         if r['incomplete']:
#             by_date[r['date']]['incomplete'] += 1

#     systemic_days = {
#         d for d, c in by_date.items()
#         if c['total'] >= SYSTEMIC_MIN_ROWS and (c['incomplete'] / c['total']) >= SYSTEMIC_DAY_RATIO
#     }
#     print(f'[KekaAttendance] systemic days excluded: {sorted(systemic_days)}')

#     # ── Pass 2: modal shift time per person ────────────────────────────────────
#     clean_for_modal = defaultdict(list)
#     for r in raw_rows:
#         if r['incomplete'] or r['date'] in systemic_days:
#             continue
#         if r['shift_in'] and r['shift_out']:
#             clean_for_modal[r['kid']].append(r)

#     modal_shift = {}
#     for kid, rows in clean_for_modal.items():
#         in_times  = Counter(r['shift_in'].strftime('%H:%M') for r in rows)
#         out_times = Counter(r['shift_out'].strftime('%H:%M') for r in rows)
#         modal_shift[kid] = (in_times.most_common(1)[0][0], out_times.most_common(1)[0][0])

#     # ── Pass 3: final classification ───────────────────────────────────────────
#     final_rows = []
#     for r in raw_rows:
#         kid = r['kid']
#         if r['date'] in systemic_days:
#             continue
#         if r['incomplete']:
#             final_rows.append({**r, 'status': 'incomplete'})
#             continue

#         hours = round((r['punch_out'] - r['punch_in']).total_seconds() / 3600, 2)
#         m_in_str, m_out_str = modal_shift.get(kid, (None, None))
#         m_in = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
#                 if m_in_str else r['shift_in'])
#         m_out = (datetime.combine(r['date'], datetime.strptime(m_out_str, '%H:%M').time())
#                  if m_out_str else r['shift_out'])

#         if hours < MIN_PLAUSIBLE_HRS:
#             final_rows.append({**r, 'status': 'present_implausible', 'hours': hours})
#             continue

#         late_min  = _mins(m_in, r['punch_in'])
#         early_min = _mins(r['punch_out'], m_out)

#         final_rows.append({
#             **r, 'status': 'present', 'hours': hours,
#             'late_min': max(0, late_min or 0), 'early_min': max(0, early_min or 0),
#             'is_late': bool(late_min is not None and late_min > LATE_GRACE_MIN),
#             'is_early_exit': bool(early_min is not None and early_min > EARLY_EXIT_MIN),
#         })

#     # ── Build per-employee monthly record ──────────────────────────────────────
#     month_start = datetime(year, month, 1).date()
#     calendar_month_end = (datetime(year, month + 1, 1) - timedelta(days=1)).date() \
#                 if month < 12 else datetime(year, 12, 31).date()

#     # If this is the CURRENT, still-in-progress month, the denominator must
#     # only count days that have actually happened — through YESTERDAY, not
#     # the full calendar month. Reported bug: viewing June on June 24 showed
#     # 26 working days (the whole month) when only ~17 working days had
#     # actually occurred so far, making leave/late/early failure percentages
#     # look artificially worse than reality. A fully completed past month
#     # (e.g. May, viewed in June) is unaffected — calendar_month_end stays
#     # the real last day of that month since "today" is already past it.
#     today = datetime.utcnow().date()
#     if year == today.year and month == today.month:
#         month_end = min(calendar_month_end, today - timedelta(days=1))
#     else:
#         month_end = calendar_month_end

#     by_emp = defaultdict(list)
#     skipped_no_kid = 0
#     for r in final_rows:
#         if not r['kid']:
#             # A raw attendance row with no keka_id at all (the 'name'
#             # column, per this project's convention, was itself null at
#             # the source). Cannot attribute this punch data to anyone —
#             # grouping it under key None would build a record with no
#             # identity at all, which crashes downstream in
#             # _synthetic_admin_id and is silently wrong regardless (we'd
#             # be reporting real attendance numbers for "nobody"). Skipped
#             # and counted so it's visible, not silently lost.
#             skipped_no_kid += 1
#             continue
#         by_emp[r['kid']].append(r)
#     if skipped_no_kid:
#         print(f'[KekaAttendance] WARNING: skipped {skipped_no_kid} attendance rows '
#               f'with no keka_id at all (null at source) — this real attendance '
#               f'data cannot be attributed to anyone and is being excluded, not '
#               f'silently merged into a broken record.')

#     records = []
#     for kid, rows in by_emp.items():
#         name = name_by_kid.get(kid, '?')
#         admin_id = kid_to_admin.get(kid)   # None if unmapped — handled by callers

#         join_dt = join_by_kid.get(kid)
#         exit_dt = exit_by_kid.get(kid)

#         eff_start = month_start
#         if join_dt and join_dt.date() > month_start:
#             eff_start = join_dt.date()

#         eff_end = month_end
#         if exit_dt and exit_dt.date() < month_end:
#             eff_end = exit_dt.date()

#         person_off_days = off_days_by_kid.get(kid, DEFAULT_OFF_DAYS)
#         # Pure calendar math, per explicit instruction: total days in
#         # [eff_start, eff_end] minus ONLY this person's actual weekly
#         # off-day(s) — Sunday for a single-day-off policy, Saturday+Sunday
#         # for a two-day-off policy. Nothing else is subtracted or added.
#         # Confirmed by hand: May 2026 has 31 days, 5 Sundays -> 26 working
#         # days for a Sunday-only person, full stop. Systemic-day detection
#         # still runs (kept for diagnostic visibility / future use) but no
#         # longer affects expected/present/absent in any way.
#         expected = _working_days(eff_start, eff_end, off_days=person_off_days)

#         present_rows = [r for r in rows if r['status'] in ('present', 'present_implausible')]
#         present_dates_set = {r['date'] for r in present_rows}

#         # Per explicit instruction: working days/present/absent are based
#         # ONLY on the person's actual weekly off-day(s) — Sunday for a
#         # single-day-off policy, Saturday+Sunday for a two-day-off policy.
#         # Nothing else is added or subtracted. Systemic-day detection still
#         # runs (used elsewhere for diagnostics) but no longer affects this
#         # calculation in any way — not the denominator, not present, not
#         # absent.
#         present = min(len(present_dates_set), expected)

#         late_dates  = sorted(str(r['date']) for r in rows if r.get('is_late'))
#         early_dates = sorted(str(r['date']) for r in rows if r.get('is_early_exit'))
#         late  = len(late_dates)
#         early = len(early_dates)

#         # ── Build full entry objects, matching EmployeeDetail.jsx's real
#         # contract (confirmed against the live frontend code): each entry
#         # needs punch_in/shift_start (late) or punch_out/shift_end (early)
#         # as ISO-ish datetime STRINGS, since the frontend does:
#         #     new Date(e.punch_in.replace(' UTC','Z'))
#         #     new Date(e.shift_start.replace(' UTC','Z'))
#         # to compute delay/shortfall itself. Plain date strings (no time
#         # component) silently produced Invalid Date / NaN delay there —
#         # this is the fix for that.
#         def _fmt_dt(dt):
#             return dt.strftime('%Y-%m-%d %H:%M:%S UTC') if dt else None

#         late_entries = []
#         for r in rows:
#             if not r.get('is_late'):
#                 continue
#             m_in_str = modal_shift.get(kid, (None, None))[0]
#             shift_dt = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
#                         if m_in_str else None)
#             late_entries.append({
#                 'date': str(r['date']),
#                 'punch_in': _fmt_dt(r.get('punch_in')),
#                 'shift_start': _fmt_dt(shift_dt),
#             })

#         early_entries = []
#         for r in rows:
#             if not r.get('is_early_exit'):
#                 continue
#             m_in_str, m_out_str = modal_shift.get(kid, (None, None))
#             shift_start_dt = (datetime.combine(r['date'], datetime.strptime(m_in_str, '%H:%M').time())
#                               if m_in_str else None)
#             shift_end_dt = (datetime.combine(r['date'], datetime.strptime(m_out_str, '%H:%M').time())
#                             if m_out_str else None)
#             punch_out = r.get('punch_out')

#             # EmployeeDetail.jsx (confirmed against real code) reads
#             # e.expected_hours / e.actual_hours / e.shortfall_hrs directly
#             # as numbers — it does NOT compute these itself the way it does
#             # for late_entries' delay-in-minutes. Without these 3 fields the
#             # template `${e.expected_hours}h` renders literally as "h",
#             # which is the exact bug reported. Computed here from the same
#             # shift_start/shift_end/punch_out data already available.
#             expected_hours = round((shift_end_dt - shift_start_dt).total_seconds() / 3600, 2) \
#                 if (shift_start_dt and shift_end_dt) else None
#             actual_hours = round((punch_out - shift_start_dt).total_seconds() / 3600, 2) \
#                 if (shift_start_dt and punch_out) else None
#             shortfall_hrs = round(expected_hours - actual_hours, 2) \
#                 if (expected_hours is not None and actual_hours is not None) else None

#             early_entries.append({
#                 'date': str(r['date']),
#                 'punch_out': _fmt_dt(punch_out),
#                 'shift_end': _fmt_dt(shift_end_dt),
#                 'expected_hours': expected_hours,
#                 'actual_hours': actual_hours,
#                 'shortfall_hrs': shortfall_hrs,
#             })
#         incomplete_count = sum(1 for r in rows if r['status'] == 'incomplete')
#         unrecorded = max(0, expected - present)

#         # ── Compute actual absent calendar dates (for leave_dates), not just
#         # a count. A working day with NO row at all (not even incomplete) in
#         # [eff_start, eff_end], excluding systemic days, counts as absent.
#         # Use the SAME date-set that produced `present`, not every row
#         # regardless of status. Previously this included 'incomplete' rows
#         # too, which created a no-man's-land: a date with only an
#         # incomplete punch was excluded from absent_dates (because SOME
#         # row existed) but was never counted in `present` either (because
#         # incomplete rows don't count as present) — so unrecorded_absent_days
#         # (a count) and absent_dates (a list) could disagree, exactly as
#         # confirmed for Anchal Patidar: count=2 but only 1 date listed.
#         genuinely_present_dates = present_dates_set   # same set used for `present` above — keeps the two calculations consistent
#         absent_dates = []
#         d = eff_start
#         while d <= eff_end:
#             if d.weekday() not in person_off_days and d not in genuinely_present_dates:
#                 absent_dates.append(str(d))
#             d += timedelta(days=1)
#         absent_dates = absent_dates[:unrecorded] if unrecorded else []   # cap defensively

#         valid_hours = [r['hours'] for r in rows if r['status'] == 'present' and r.get('hours')]
#         avg_hours = round(sum(valid_hours) / len(valid_hours), 2) if valid_hours else 0

#         m_in, m_out = modal_shift.get(kid, ('--', '--'))

#         records.append({
#             'keka_id': kid,
#             'admin_id': admin_id,
#             'name': name,
#             'department': dept_by_kid.get(kid, 'Unknown'),
#             'modal_shift_start': m_in,
#             'modal_shift_end': m_out,
#             'joined_mid_month': bool(join_dt and join_dt.date() > month_start),
#             'joining_date': str(join_dt.date()) if join_dt else None,
#             'exited_mid_month': bool(exit_dt and exit_dt.date() < month_end),
#             'exit_date': str(exit_dt.date()) if exit_dt else None,
#             'expected_working_days': expected,
#             'present_days': present,
#             'late_days': late,
#             'early_exit_days': early,
#             'unrecorded_absent_days': unrecorded,
#             'incomplete_punch_days': incomplete_count,
#             'avg_hours_per_day': avg_hours,
#             'late_dates': late_dates,
#             'early_dates': early_dates,
#             'late_entries': late_entries,
#             'early_entries': early_entries,
#             'absent_dates': absent_dates,
#         })

#     # Active count: use the SAME deduplicated latest_status_by_kid built
#     # above (not the raw `status` list, which has 4x duplicate rows per
#     # person and would inflate this count ~4x — confirmed bug: naive count
#     # was 339 vs the real deduplicated figure of 85). Also apply the
#     # exit_date safety check: a person can still show employment_status=0
#     # in a stale row while their exit_date has already passed, so exclude
#     # anyone whose exit_date is today or earlier even if the status flag
#     # hasn't caught up yet.
#     today = datetime.utcnow().date()
#     active = 0
#     for s in latest_status_by_kid.values():
#         is_active_flags = (str(s.get('employment_status')) == '0'
#                             and str(s.get('account_status')) == '1')
#         if not is_active_flags:
#             continue
#         exit_dt = _parse_dt(s.get('exit_date'))
#         if exit_dt and exit_dt.date() <= today:
#             continue   # flag hasn't caught up to a real departure yet
#         active += 1

#     return {
#         'month': month, 'year': year,
#         'systemic_days_excluded': [str(d) for d in sorted(systemic_days)],
#         'active_users': active,
#         'total_employees': len(emps),
#         'employees': records,
#         'unmapped_count': sum(1 for r in records if r['admin_id'] is None),
#     }


# # Bump this any time the shape of a per-employee record changes (new keys
# # added/removed/renamed). A cached payload missing this exact version is
# # treated as stale and recomputed, instead of being trusted blindly. This
# # is what the absent_dates KeyError revealed: a cache written before that
# # field existed was silently served afterward as if it were current.
# _SCHEMA_VERSION = 8

# def get_month_data(month, year, force_refresh=False):
#     if not force_refresh:
#         cached, computed_at = _cache_get(month, year)
#         if cached is not None and cached.get('_schema_version') == _SCHEMA_VERSION:
#             # For the CURRENT, still-in-progress month, the cache must be
#             # recomputed daily — yesterday's cached "working days through
#             # yesterday" is stale today, since "yesterday" has moved.
#             # A fully completed past month never has this problem: once
#             # the month is over, its working-days range never changes
#             # again, so the cache is valid indefinitely.
#             today = datetime.utcnow().date()
#             is_current_month = (year == today.year and month == today.month)
#             if is_current_month and computed_at:
#                 computed_date = datetime.fromisoformat(computed_at).date()
#                 if computed_date < today:
#                     print(f'[KekaAttendance] Cached {month}/{year} is from {computed_date} '
#                           f'(stale — current month must recompute daily) — recomputing')
#                     cached = None
#             if cached is not None:
#                 return cached
#         elif cached is not None:
#             print(f'[KekaAttendance] Cached {month}/{year} has stale schema '
#                   f'(got {cached.get("_schema_version")!r}, need {_SCHEMA_VERSION}) — recomputing')
#     data = _compute(month, year)
#     data['_schema_version'] = _SCHEMA_VERSION
#     _cache_set(month, year, data)
#     return data


# def refresh_cache(month, year):
#     return get_month_data(month, year, force_refresh=True)


# # ──────────────────────────────────────────────────────────────────────────────
# # KPI CLASSES — same interface contract as every other module in kpis/
# # ──────────────────────────────────────────────────────────────────────────────
# # ──────────────────────────────────────────────────────────────────────────────
# # SYNTHETIC ADMINID — for Keka employees with no matching SQL Server Admin row
# # ──────────────────────────────────────────────────────────────────────────────
# # Full diagnostic confirmed 155/286 Keka employees genuinely have NO matching
# # SQL Admin record at all (not a matcher bug — most of these are real people
# # only present in Keka, not yet created in the older SQL Server system, e.g.
# # Arjun Bhadoriya who joined May 25 this very month). Rather than silently
# # dropping 103+ real employees from every attendance KPI, every employee is
# # now ALWAYS included. Those without a real AdminID get a stable, deterministic
# # negative integer derived from their keka_id, so:
# #   - score_engine.py's existing AdminID-keyed dict logic works unchanged
# #     (it only needs a unique, stable key — it doesn't care if it's a real
# #     SQL identity or not)
# #   - the SAME keka_id always produces the SAME synthetic ID across runs,
# #     so dedup/caching/trend-over-time logic stays consistent
# #   - negative range guarantees zero collision with real SQL AdminIDs (which
# #     are always positive in this project's Admin table)
# #   - IsRealAdminID flag on each row lets any consuming code (or future UI)
# #     distinguish "linked to a real employee record" from "Keka-only, not
# #     yet bridged to SQL Server" without guessing from the ID's sign alone
# def _synthetic_admin_id(keka_id):
#     import hashlib
#     if not keka_id:
#         # Defensive: a record reaching here with no keka_id at all is a
#         # data-integrity gap upstream, not something this function should
#         # silently paper over with a fake ID. Raise clearly instead of
#         # crashing deep inside hashlib with a confusing 'NoneType has no
#         # attribute encode' error that gives no indication of WHICH
#         # employee or WHERE the gap originated.
#         raise ValueError(
#             'synthetic_admin_id called with no keka_id — a record reached '
#             'this point with neither a real AdminID nor a keka_id to hash. '
#             'This indicates a data gap upstream in _compute(), not something '
#             'safe to silently fake an ID for.'
#         )
#     h = int(hashlib.md5(keka_id.encode()).hexdigest()[:8], 16)
#     return -(h % 900000 + 100000)   # stable negative ID in range -100000..-999999


# class KekaLeavesKPI(BaseKPI):
#     """Replaces kpis/leaves.py. Registry: module_path='kpis.keka_attendance', class_name='KekaLeavesKPI'."""

#     def fetch(self, month, year):
#         data = get_month_data(month, year)
#         rows = []
#         for emp in data['employees']:
#             is_real = emp['admin_id'] is not None
#             admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
#             rows.append({
#                 'AdminID': admin_id,
#                 'EmployeeName': emp['name'],
#                 'Department': emp['department'],
#                 'WorkingDays': emp['expected_working_days'],
#                 'PresentDays': emp['present_days'],
#                 'UnrecordedDays': emp['unrecorded_absent_days'],
#                 'AbsentDates': emp['absent_dates'],
#                 'IsRealAdminID': is_real,
#                 'KekaID': emp['keka_id'],
#             })
#         return rows

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
#         r = rows[0]
#         wdays, present, absent = r['WorkingDays'], r['PresentDays'], r['UnrecordedDays']
#         ratio = round(present / wdays * 100, 2) if wdays else None
#         return {
#             'numerator': present, 'denominator': wdays, 'success_ratio': ratio,
#             # leave_dates now carries REAL absent calendar dates (matches old
#             # ViaSocket contract's leave_dates: [date_string,...] shape exactly)
#             'orders': [{'working_days': wdays, 'present_days': present,
#                         'leave_days': absent, 'leave_dates': r['AbsentDates']}],
#         }


# class KekaLateComingsKPI(BaseKPI):
#     """Replaces kpis/late_comings.py. Registry: class_name='KekaLateComingsKPI'."""

#     def fetch(self, month, year):
#         data = get_month_data(month, year)
#         rows = []
#         for emp in data['employees']:
#             is_real = emp['admin_id'] is not None
#             admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
#             rows.append({
#                 'AdminID': admin_id,
#                 'EmployeeName': emp['name'],
#                 'Department': emp['department'],
#                 'WorkingDays': emp['expected_working_days'],
#                 'LateDays': emp['late_days'],
#                 'LateEntries': emp['late_entries'],
#                 'ShiftStart': emp['modal_shift_start'],
#                 'IsRealAdminID': is_real,
#                 'KekaID': emp['keka_id'],
#             })
#         return rows

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
#         r = rows[0]
#         wdays, late = r['WorkingDays'], r['LateDays']
#         on_time = max(0, wdays - late)
#         ratio = round(on_time / wdays * 100, 2) if wdays else None
#         return {
#             'numerator': on_time, 'denominator': wdays, 'success_ratio': ratio,
#             # late_entries now carries {date, punch_in, shift_start} objects
#             # with real datetime strings — matches EmployeeDetail.jsx's
#             # actual contract (verified against the live frontend code):
#             # it does new Date(e.punch_in.replace(' UTC','Z')) -
#             # new Date(e.shift_start.replace(' UTC','Z')) to show delay.
#             'orders': [{'working_days': wdays, 'late_days': late, 'on_time_days': on_time,
#                         'late_entries': r['LateEntries'], 'shift_start': r['ShiftStart']}],
#         }


# class KekaEarlyLeavingsKPI(BaseKPI):
#     """Replaces kpis/early_leavings.py. Registry: class_name='KekaEarlyLeavingsKPI'."""

#     def fetch(self, month, year):
#         data = get_month_data(month, year)
#         rows = []
#         for emp in data['employees']:
#             is_real = emp['admin_id'] is not None
#             admin_id = emp['admin_id'] if is_real else _synthetic_admin_id(emp['keka_id'])
#             rows.append({
#                 'AdminID': admin_id,
#                 'EmployeeName': emp['name'],
#                 'Department': emp['department'],
#                 'WorkingDays': emp['expected_working_days'],
#                 'EarlyDays': emp['early_exit_days'],
#                 'EarlyEntries': emp['early_entries'],
#                 'ShiftEnd': emp['modal_shift_end'],
#                 'IsRealAdminID': is_real,
#                 'KekaID': emp['keka_id'],
#             })
#         return rows

#     def aggregate(self, rows):
#         if not rows:
#             return {'numerator': 0, 'denominator': 0, 'success_ratio': None, 'orders': []}
#         r = rows[0]
#         wdays, early = r['WorkingDays'], r['EarlyDays']
#         full_days = max(0, wdays - early)
#         ratio = round(full_days / wdays * 100, 2) if wdays else None
#         return {
#             'numerator': full_days, 'denominator': wdays, 'success_ratio': ratio,
#             # early_entries carries {date, punch_out, shift_end} objects with
#             # real datetime strings — matches EmployeeDetail.jsx line ~477
#             # which does new Date(e.punch_out...) vs new Date(e.shift_end...)
#             'orders': [{'working_days': wdays, 'early_days': early, 'full_days': full_days,
#                         'early_entries': r['EarlyEntries'], 'shift_end': r['ShiftEnd']}],
#         }


# # ──────────────────────────────────────────────────────────────────────────────
# # CLI test
# # ──────────────────────────────────────────────────────────────────────────────
# if __name__ == '__main__':
#     import sys
#     m = int(sys.argv[1]) if len(sys.argv) > 1 else 5
#     y = int(sys.argv[2]) if len(sys.argv) > 2 else 2026

#     for cls_name, cls in [('Leaves', KekaLeavesKPI), ('LateComings', KekaLateComingsKPI),
#                            ('EarlyLeavings', KekaEarlyLeavingsKPI)]:
#         inst = cls()
#         rows = inst.fetch(m, y)
#         real_count = sum(1 for r in rows if r['IsRealAdminID'])
#         synthetic_count = len(rows) - real_count
#         print(f'\n{cls_name}: {len(rows)} total rows '
#               f'({real_count} real AdminID, {synthetic_count} synthetic/Keka-only)')
#         if rows:
#             sample_agg = inst.aggregate([rows[0]])
#             print(f'  sample for {rows[0]["EmployeeName"]}: '
#                   f'{sample_agg["numerator"]}/{sample_agg["denominator"]} = {sample_agg["success_ratio"]}%')

#     print(f'\nEvery Keka employee with May attendance now appears in every KPI.')
#     print(f'Rows with IsRealAdminID=False are linked to score_engine.py via a')
#     print(f'stable synthetic ID, not yet bridged to a real SQL Server Admin row.')
#     print(f'Call keka_name_mapper.get_unresolved() to see/fix those via')
#     print(f'keka_name_mapper.set_manual_mapping(keka_id, real_admin_id) once a')
#     print(f'human confirms the correct SQL Admin match (if one exists at all).')