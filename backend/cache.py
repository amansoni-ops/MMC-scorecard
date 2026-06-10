"""
Score cache — wraps score_engine.calculate_scores with SQLite caching.
APScheduler refreshes the current month every 4 hours automatically.
"""
import json
import threading
from datetime import datetime
import local_db
import score_engine

_lock = threading.Lock()

def load(month: int, year: int) -> list:
    """Load scores — from cache if available, else compute and store."""
    cached = local_db.get_cached_scores(month, year)
    if cached:
        print(f'[Cache] HIT {month}/{year}')
        return json.loads(cached)
    with _lock:
        # Double-check after acquiring lock
        cached = local_db.get_cached_scores(month, year)
        if cached:
            return json.loads(cached)
        print(f'[Cache] MISS {month}/{year} — computing…')
        data = score_engine.calculate_scores(month, year)
        local_db.set_cached_scores(month, year, json.dumps(data))
        print(f'[Cache] Stored {month}/{year} ({len(data)} employees)')
        return data

def invalidate(month: int = None, year: int = None):
    local_db.delete_cached_scores(month, year)
    if month and year:
        print(f'[Cache] Invalidated {month}/{year}')
    else:
        print('[Cache] Invalidated ALL')

def preload_async(month: int, year: int):
    """Trigger a background recompute without blocking the request."""
    def _run():
        try:
            invalidate(month, year)
            load(month, year)
        except Exception as e:
            print(f'[Cache] Preload error {month}/{year}: {e}')
    threading.Thread(target=_run, daemon=True, name=f'preload-{month}-{year}').start()

def status() -> dict:
    entries = local_db.get_cache_entries()
    return {'entries': entries, 'count': len(entries)}

def start_scheduler():
    """Refresh current month cache every 4 hours."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        def refresh():
            now = datetime.now()
            print(f'[Cache] Scheduled refresh {now.month}/{now.year}')
            preload_async(now.month, now.year)
        scheduler.add_job(refresh, 'interval', hours=4, id='cache_refresh')
        scheduler.start()
        print('[Cache] Scheduler started (4h interval)')
    except ImportError:
        print('[Cache] APScheduler not installed — no auto-refresh')
    except Exception as e:
        print(f'[Cache] Scheduler error: {e}')
