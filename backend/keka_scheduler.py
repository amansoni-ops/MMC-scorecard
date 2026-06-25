"""
backend/keka_scheduler.py
============================
Makes keka_sync_job.run_sync_job() run automatically in the background,
once a day, for as long as the Flask app process is alive. No manual
script-running, no cron setup required on the server — this starts
itself when the app starts, the same way score_cache.start_scheduler()
already does for the existing score cache (per app.py's existing call
to that function).

WIRING — add to app.py
-------------------------
Near the top, alongside the existing:
    score_cache.start_scheduler()

add:
    import keka_scheduler
    keka_scheduler.start_scheduler()

That's the only change needed in app.py. Everything else runs itself.

WHY A SEPARATE THREAD, NOT BLOCKING STARTUP
----------------------------------------------
The sync job does live network calls to Keka + SQL Server and can take
real time on a large employee list. Running it on app startup, in the
main thread, would delay Flask actually becoming ready to serve
requests. Instead: fire it once shortly after startup in a background
thread, then again every INTERVAL_HOURS, forever, without blocking
anything else the app is doing.
"""

import threading
import time
import traceback
from datetime import datetime

INTERVAL_HOURS = 24       # how often the sync job re-runs
STARTUP_DELAY_SECONDS = 30  # wait a bit after app start before first run,
                             # so the app is fully up before doing network work

_scheduler_thread = None
_stop_flag = threading.Event()


def _run_loop():
    # Wait a bit before the very first run, so this doesn't compete with
    # the app's own startup work (DB connections, other schedulers, etc.)
    time.sleep(STARTUP_DELAY_SECONDS)

    while not _stop_flag.is_set():
        try:
            print(f'[KekaScheduler] Running scheduled sync at {datetime.utcnow().isoformat()}')
            import keka_sync_job
            result = keka_sync_job.run_sync_job()
            print(f'[KekaScheduler] Run complete: {result}')
        except Exception as e:
            # A failed run should NEVER crash the scheduler thread or the
            # app — log it and try again next interval.
            print(f'[KekaScheduler] ERROR during scheduled run: {e}')
            traceback.print_exc()

        # Sleep in small increments so _stop_flag is checked periodically,
        # rather than one long uninterruptible sleep.
        slept = 0
        interval_seconds = INTERVAL_HOURS * 3600
        while slept < interval_seconds and not _stop_flag.is_set():
            time.sleep(min(60, interval_seconds - slept))
            slept += 60


def start_scheduler():
    """Call once, at app startup. Safe to call multiple times — only
    starts one thread."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        print('[KekaScheduler] Already running, skipping duplicate start.')
        return

    _stop_flag.clear()
    _scheduler_thread = threading.Thread(target=_run_loop, daemon=True, name='keka-sync-scheduler')
    _scheduler_thread.start()
    print(f'[KekaScheduler] Started — first run in {STARTUP_DELAY_SECONDS}s, '
          f'then every {INTERVAL_HOURS}h thereafter.')


def stop_scheduler():
    """For clean shutdown / testing — not required for normal operation
    since the thread is a daemon and will not block process exit."""
    _stop_flag.set()


def run_now():
    """Manual trigger — for an admin 'sync now' button, or testing,
    without waiting for the scheduled interval. Runs in the CURRENT
    thread (blocking) so callers know when it's actually done."""
    import keka_sync_job
    return keka_sync_job.run_sync_job()


if __name__ == '__main__':
    # Test mode: run once immediately, don't wait for the schedule
    print('[KekaScheduler] Test mode — running once immediately (no 24h wait)')
    run_now()