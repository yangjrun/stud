"""Historical data loader: batch load past N months of data into the database."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from loguru import logger
from tqdm import tqdm

from src.config.settings import settings
from src.data.collector import DataCollector
from src.data.database import get_session, init_db
from src.data.models import (
    DailyBurst,
    DailyLimitDown,
    DailyLimitUp,
    DragonTiger,
    KnownPlayer,
)
from src.data.repository import (
    BurstRepository,
    DragonTigerRepository,
    KnownPlayerRepository,
    LimitDownRepository,
    LimitUpRepository,
)


def _trading_dates(start: date, end: date) -> list[date]:
    """Generate weekday dates (rough filter, holidays will return empty data)."""
    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            dates.append(current)
        current += timedelta(days=1)
    return dates


def load_known_players() -> None:
    """Load seed known_players.json into database."""
    seed_file = settings.seed_dir / "known_players.json"
    if not seed_file.exists():
        logger.warning(f"Seed file not found: {seed_file}")
        return

    with open(seed_file, encoding="utf-8") as f:
        players = json.load(f)

    with get_session() as session:
        repo = KnownPlayerRepository(session)
        for p in players:
            repo.upsert(KnownPlayer(**p))
        session.commit()
    logger.info(f"Loaded {len(players)} known players")


def load_limit_up_history(
    collector: DataCollector, start: date, end: date
) -> None:
    """Load daily limit-up pool data."""
    dates = _trading_dates(start, end)
    logger.info(f"Loading limit-up data: {start} to {end} ({len(dates)} dates)")

    for d in tqdm(dates, desc="涨停股池"):
        df = collector.fetch_limit_up_pool(d)
        if df is None:
            continue

        with get_session() as session:
            repo = LimitUpRepository(session)
            for _, row in df.iterrows():
                repo.upsert(DailyLimitUp(
                    trade_date=d,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("最新价"),
                    change_pct=row.get("涨跌幅"),
                    turnover_rate=row.get("换手率"),
                    amount=row.get("成交额"),
                    circulating_mv=row.get("流通市值"),
                    seal_amount=row.get("封板资金"),
                    first_seal_time=str(row.get("首次封板时间", "")),
                    last_seal_time=str(row.get("最后封板时间", "")),
                    open_count=int(row.get("炸板次数", 0)),
                    continuous_count=int(row.get("连板数", 1)),
                ))
            session.commit()


def load_burst_history(
    collector: DataCollector, start: date, end: date
) -> None:
    """Load daily burst (炸板) pool data.

    Note: AKShare ``stock_zt_pool_zbgc_em`` only supports the last 30 trading
    days (~45 calendar days).  Dates outside that window are silently skipped.
    """
    earliest_allowed = end - timedelta(days=45)
    effective_start = max(start, earliest_allowed)
    if effective_start > start:
        logger.info(
            f"Burst pool API limited to ~30 trading days; "
            f"clamping start from {start} to {effective_start}"
        )
    dates = _trading_dates(effective_start, end)
    logger.info(f"Loading burst data: {effective_start} to {end}")

    for d in tqdm(dates, desc="炸板股池"):
        df = collector.fetch_burst_pool(d)
        if df is None:
            continue

        with get_session() as session:
            repo = BurstRepository(session)
            for _, row in df.iterrows():
                repo.upsert(DailyBurst(
                    trade_date=d,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("最新价"),
                    change_pct=row.get("涨跌幅"),
                    turnover_rate=row.get("换手率"),
                    amount=row.get("成交额"),
                    first_seal_time=str(row.get("首次封板时间", "")),
                    burst_time=None,  # API doesn't provide exact burst time
                ))
            session.commit()


def load_limit_down_history(
    collector: DataCollector, start: date, end: date
) -> None:
    """Load daily limit-down pool data.

    Note: AKShare ``stock_zt_pool_dtgc_em`` only supports the last 30 trading
    days (~45 calendar days).  Dates outside that window are silently skipped.
    """
    earliest_allowed = end - timedelta(days=45)
    effective_start = max(start, earliest_allowed)
    if effective_start > start:
        logger.info(
            f"Limit-down pool API limited to ~30 trading days; "
            f"clamping start from {start} to {effective_start}"
        )
    dates = _trading_dates(effective_start, end)
    logger.info(f"Loading limit-down data: {effective_start} to {end}")

    for d in tqdm(dates, desc="跌停股池"):
        df = collector.fetch_limit_down_pool(d)
        if df is None:
            continue

        with get_session() as session:
            repo = LimitDownRepository(session)
            for _, row in df.iterrows():
                repo.upsert(DailyLimitDown(
                    trade_date=d,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("最新价"),
                    change_pct=row.get("涨跌幅"),
                    amount=row.get("成交额"),
                ))
            session.commit()


def load_dragon_tiger_history(
    collector: DataCollector, start: date, end: date
) -> None:
    """Load dragon-tiger list data (monthly batches to avoid large responses)."""
    logger.info(f"Loading dragon-tiger data: {start} to {end}")

    # Fetch in monthly chunks
    current = start
    chunks = []
    while current <= end:
        chunk_end = min(current + timedelta(days=30), end)
        chunks.append((current, chunk_end))
        current = chunk_end + timedelta(days=1)

    for chunk_start, chunk_end in tqdm(chunks, desc="龙虎榜"):
        df = collector.fetch_dragon_tiger(chunk_start, chunk_end)
        if df is None:
            continue

        with get_session() as session:
            repo = DragonTigerRepository(session)
            for _, row in df.iterrows():
                trade_date_val = row.get("上榜日")
                if trade_date_val is None:
                    continue
                if hasattr(trade_date_val, "date"):
                    trade_date_val = trade_date_val.date()
                elif isinstance(trade_date_val, str):
                    from datetime import datetime as _dt
                    trade_date_val = _dt.strptime(trade_date_val, "%Y-%m-%d").date()

                repo.upsert(DragonTiger(
                    trade_date=trade_date_val,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("收盘价"),
                    change_pct=row.get("涨跌幅"),
                    turnover_rate=row.get("换手率"),
                    amount=row.get("龙虎榜成交额"),
                    reason=row.get("上榜原因"),
                ))
            session.commit()


def main() -> None:
    logger.info("Initializing database...")
    init_db()

    end = date.today()
    start = end - timedelta(days=settings.history_months * 30)

    collector = DataCollector(
        request_interval=settings.akshare_request_interval,
        max_retries=settings.akshare_max_retries,
    )

    logger.info(f"Loading history from {start} to {end} ({settings.history_months} months)")

    # 1. Load seed data
    load_known_players()

    # 2. Load market data (sequential, each type is independent)
    load_limit_up_history(collector, start, end)
    load_burst_history(collector, start, end)
    load_limit_down_history(collector, start, end)
    load_dragon_tiger_history(collector, start, end)

    logger.info("Historical data loading complete!")


if __name__ == "__main__":
    main()
