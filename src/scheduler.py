"""Background scheduler for periodic OHLCV refresh of universe symbols."""

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, Callable, Optional

from src.data.cache import write_ohlcv_cache
from src.data.universe import get_universe_yahoo_symbols, pre_seed_ohlcv

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: Optional["BackgroundScheduler"] = None


def run_refresh(
    cache_dir: str,
    fetcher: Callable[[str, date, date], object],
    lookback_days: int = 5,
) -> tuple[int, int]:
    """
    Fetch OHLCV for last lookback_days for each universe symbol and upsert to cache.
    fetcher(symbol, start, end) -> DataFrame.
    Returns (success_count, fail_count).
    """
    symbols = get_universe_yahoo_symbols(cache_dir)
    if not symbols:
        return 0, 0
    end = date.today()
    start = end - timedelta(days=lookback_days)

    def write_cache(cd: str, sym: str, df) -> None:
        write_ohlcv_cache(cd, sym, df)

    # pre_seed_ohlcv expects list of dicts with yahoo_symbol/symbol
    symbol_dicts = [{"yahoo_symbol": s, "symbol": s} for s in symbols]
    ok, err = pre_seed_ohlcv(
        cache_dir,
        fetcher,
        lookback_days=lookback_days,
        write_cache=write_cache,
        symbols=symbol_dicts,
    )
    logger.info("Refresh completed: %d ok, %d failed", ok, err)
    return ok, err


def start_scheduler(
    cache_dir: str,
    get_fetcher: Callable[[], Callable[[str, date, date], object]],
    interval_minutes: int = 360,
    lookback_days: int = 5,
    enabled: bool = True,
) -> Optional["BackgroundScheduler"]:
    """
    Start APScheduler BackgroundScheduler; add a job that runs run_refresh every interval_minutes.
    get_fetcher() is called at job run time to get the current data provider fetcher.
    """
    if not enabled:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed; refresh scheduler disabled")
        return None

    def job():
        try:
            fetcher = get_fetcher()
            if fetcher:
                run_refresh(cache_dir, fetcher, lookback_days=lookback_days)
        except Exception as e:
            logger.exception("Refresh job failed: %s", e)

    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(job, "interval", minutes=interval_minutes, id="ohlcv_refresh")
    _scheduler.start()
    logger.info("Scheduler started: OHLCV refresh every %s minutes", interval_minutes)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
        logger.info("Scheduler stopped")
