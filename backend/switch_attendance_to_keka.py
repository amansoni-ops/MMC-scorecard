"""
switch_attendance_to_keka.py
==============================
Flips the 'leaves', 'late_comings', 'early_leavings' KPI registry entries
from their ViaSocket-backed module_path/class_name to the new Keka-backed
classes in kpis/keka_attendance.py.

score_engine.py is NOT modified by this script — it already loads
whatever module_path/class_name the local_db registry says for each
active KPI key. This script only updates those registry rows in
scorecard.db's `kpis` table.

SAFE TO RUN MULTIPLE TIMES — idempotent UPDATEs.

USAGE:
    python switch_attendance_to_keka.py --show       # just show current state, no changes
    python switch_attendance_to_keka.py               # switch to Keka-backed
    python switch_attendance_to_keka.py --rollback    # revert to ViaSocket-backed

PRE-FLIGHT — confirmed against your real scorecard.db schema this session:
    kpis table columns: id, key, name, description, module_path,
                         class_name, raw_weight, is_active, sort_order,
                         updated_by, updated_at
    Confirmed current values before any switch:
        leaves          -> module_path=kpis.leaves          class_name=LeavesKPI
        late_comings     -> module_path=kpis.late_comings     class_name=LateComingsKPI
        early_leavings   -> module_path=kpis.early_leavings   class_name=EarlyLeavingsKPI
"""

import sqlite3
import sys

DB_PATH = 'scorecard.db'

# Old (ViaSocket-backed) -> New (Keka-backed)
SWITCH_MAP = {
    'leaves':         {'module_path': 'kpis.keka_attendance', 'class_name': 'KekaLeavesKPI'},
    'late_comings':   {'module_path': 'kpis.keka_attendance', 'class_name': 'KekaLateComingsKPI'},
    'early_leavings': {'module_path': 'kpis.keka_attendance', 'class_name': 'KekaEarlyLeavingsKPI'},
}

# Confirmed real original values from this session's pre-flight verification
ROLLBACK_MAP = {
    'leaves':         {'module_path': 'kpis.leaves',         'class_name': 'LeavesKPI'},
    'late_comings':   {'module_path': 'kpis.late_comings',   'class_name': 'LateComingsKPI'},
    'early_leavings': {'module_path': 'kpis.early_leavings', 'class_name': 'EarlyLeavingsKPI'},
}


def show_current():
    conn = sqlite3.connect(DB_PATH)
    print('Current registry values for the 3 attendance KPIs:\n')
    for key in SWITCH_MAP:
        row = conn.execute(
            "SELECT key, module_path, class_name, is_active FROM kpis WHERE key=?", (key,)
        ).fetchone()
        if row:
            print(f'  {row[0]:<16} module_path={row[1]:<25} class_name={row[2]:<20} active={row[3]}')
        else:
            print(f'  {key:<16} NOT FOUND in registry — check exact key spelling in your kpis table')
    conn.close()


def apply(target_map, label):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for key, vals in target_map.items():
        cur.execute(
            "UPDATE kpis SET module_path=?, class_name=? WHERE key=?",
            (vals['module_path'], vals['class_name'], key)
        )
        print(f'  {key:<16} -> module_path={vals["module_path"]}, class_name={vals["class_name"]} '
              f'({cur.rowcount} row updated)')
    conn.commit()
    conn.close()
    print(f'\n{label} complete. Now clear the score cache and restart the app:')
    print("  python -c \"import sqlite3; c=sqlite3.connect('scorecard.db'); "
          "c.execute('DELETE FROM score_cache'); c.commit()\"")
    print('  python app.py')


if __name__ == '__main__':
    print('=' * 70)
    print('BEFORE:')
    show_current()
    print('=' * 70)

    if '--rollback' in sys.argv:
        print('\nRolling back to ViaSocket-backed KPI modules...\n')
        apply(ROLLBACK_MAP, 'Rollback')
    elif '--show' in sys.argv:
        pass   # already shown above, nothing else to do
    else:
        print('\nSwitching to Keka-backed KPI modules...\n')
        apply(SWITCH_MAP, 'Switch')

    print('\n' + '=' * 70)
    print('AFTER:')
    show_current()