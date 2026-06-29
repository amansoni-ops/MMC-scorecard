"""
backend/employee_cache_scheduler.py
=======================================
Runs populate_employee_cache.py's full-year population automatically in
the background, same pattern as keka_scheduler.py. Keeps the per-
employee fast-read table warm for all 12 months of the current year,
so the trend chart always has real data and employee detail pages
never hit a cold, slow path.

WIRING — add to app.py, alongside the existing schedulers:
    import employee_cache_scheduler
    employee_cache_scheduler.start_scheduler()
"""

import threading
import time
import traceback
from datetime import datetime

INTERVAL_HOURS = 6          # re-populate periodically to stay current
STARTUP_DELAY_SECONDS = 60  # let the app + other schedulers finish starting first

_scheduler_thread = None
_stop_flag = threading.Event()


def _run_loop():
    time.sleep(STARTUP_DELAY_SECONDS)

    while not _stop_flag.is_set():
        try:
            print(f'[EmployeeCacheScheduler] Run starting at {datetime.utcnow().isoformat()}')
            import populate_employee_cache as pec
            current_year = datetime.utcnow().year
            for month in range(1, 13):
                if _stop_flag.is_set():
                    break
                pec.populate_month(month, current_year)
            print(f'[EmployeeCacheScheduler] Run complete at {datetime.utcnow().isoformat()}')
        except Exception as e:
            print(f'[EmployeeCacheScheduler] ERROR during run: {e}')
            traceback.print_exc()

        slept = 0
        interval_seconds = INTERVAL_HOURS * 3600
        while slept < interval_seconds and not _stop_flag.is_set():
            time.sleep(min(60, interval_seconds - slept))
            slept += 60


def start_scheduler():
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        print('[EmployeeCacheScheduler] Already running, skipping duplicate start.')
        return
    _stop_flag.clear()
    _scheduler_thread = threading.Thread(target=_run_loop, daemon=True, name='employee-cache-scheduler')
    _scheduler_thread.start()
    print(f'[EmployeeCacheScheduler] Started — first run in {STARTUP_DELAY_SECONDS}s, '
          f'then every {INTERVAL_HOURS}h thereafter.')


def stop_scheduler():
    _stop_flag.set()


def run_now(year=None):
    """Manual trigger for an admin 'rebuild cache now' button, or testing."""
    import populate_employee_cache as pec
    year = year or datetime.utcnow().year
    for month in range(1, 13):
        pec.populate_month(month, year)


if __name__ == '__main__':
    print('[EmployeeCacheScheduler] Test mode — running once immediately')
    run_now()