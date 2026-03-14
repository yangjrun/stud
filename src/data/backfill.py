"""Backfill script: run analysis engines on existing historical data.

Processes all dates in daily_limit_up that lack emotion/theme/recap records.
Fetches 所属行业 from AKShare to fill the concept field, then runs
EmotionEngine, ThemeEngine, RecapEngine for each date.

Usage:
    uv run python -m src.data.backfill
"""

from datetime import date, timedelta

from loguru import logger

from src.data.collector import DataCollector
from src.data.database import engine, init_db
from src.data.models import DailyEmotion, DailyLimitUp, DailyTheme
from src.data.repository import (
    BurstRepository,
    EmotionRepository,
    LimitDownRepository,
    LimitUpRepository,
    RecapRepository,
    ThemeRepository,
)
from src.engine.emotion import EmotionEngine
from src.engine.limit_up import LimitUpEngine
from src.engine.recap import RecapEngine
from src.engine.theme import ThemeEngine

from sqlmodel import Session, select, text


def _prev_trading_day(d: date) -> date:
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def _get_all_trading_dates(session: Session) -> list[date]:
    """Get all distinct dates from daily_limit_up, sorted ascending."""
    rows = session.exec(
        text("SELECT DISTINCT trade_date FROM daily_limit_up ORDER BY trade_date ASC")
    ).all()
    return [row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0])) for row in rows]


def _update_concept_field(session: Session, collector: DataCollector, trade_date: date) -> int:
    """Re-fetch limit-up data for a date and update the concept field."""
    df = collector.fetch_limit_up_pool(trade_date)
    if df is None or df.empty:
        return 0

    updated = 0
    for _, row in df.iterrows():
        code = str(row.get("代码", ""))
        concept = row.get("所属行业")
        if not code or not concept:
            continue

        existing = session.exec(
            select(DailyLimitUp).where(
                DailyLimitUp.trade_date == trade_date,
                DailyLimitUp.code == code,
            )
        ).first()
        if existing and not existing.concept:
            existing.concept = str(concept)
            session.add(existing)
            updated += 1

    session.commit()
    return updated


def _build_concept_boards_from_limit_ups(
    limit_ups: list[DailyLimitUp],
) -> list[dict]:
    """Build concept_boards from limit-up industry data (for historical backfill)."""
    concept_counts: dict[str, int] = {}
    for lu in limit_ups:
        concept = lu.concept or ""
        for c in concept.split(","):
            c = c.strip()
            if c:
                concept_counts[c] = concept_counts.get(c, 0) + 1

    return [
        {
            "concept_name": name,
            "change_pct": None,
            "total_stocks": None,
        }
        for name, count in concept_counts.items()
        if count >= 1
    ]


def backfill_all() -> None:
    """Main backfill entry point."""
    init_db()
    collector = DataCollector(request_interval=0.8)
    lu_engine = LimitUpEngine()
    emo_engine = EmotionEngine()
    theme_engine = ThemeEngine()
    recap_engine = RecapEngine()

    with Session(engine) as s:
        dates = _get_all_trading_dates(s)
        logger.info(f"Found {len(dates)} trading dates to process: {dates[0]} ~ {dates[-1]}")

        for i, trade_date in enumerate(dates):
            logger.info(f"\n[{i+1}/{len(dates)}] Processing {trade_date}")

            lu_repo = LimitUpRepository(s)
            burst_repo = BurstRepository(s)
            ld_repo = LimitDownRepository(s)
            emo_repo = EmotionRepository(s)
            theme_repo = ThemeRepository(s)
            recap_repo = RecapRepository(s)

            # Step 1: Update concept field from AKShare
            updated = _update_concept_field(s, collector, trade_date)
            logger.info(f"  concept field updated: {updated} records")

            # Reload limit-ups with updated concept
            limit_ups = list(lu_repo.get_by_date(trade_date))
            bursts = list(burst_repo.get_by_date(trade_date))
            limit_downs = list(ld_repo.get_by_date(trade_date))

            if not limit_ups:
                logger.warning(f"  No limit-up data for {trade_date}, skipping")
                continue

            # Step 2: Emotion analysis
            ladder = lu_engine.build_ladder(limit_ups, bursts, trade_date)

            prev = _prev_trading_day(trade_date)
            yesterday_ups = list(lu_repo.get_by_date(prev))
            promotion = lu_engine.calc_promotion_rates(yesterday_ups, limit_ups, trade_date)

            # Fetch yesterday premium (from AKShare)
            prev_df = collector.fetch_limit_up_previous(trade_date)
            premium_avg, premium_high, premium_low = None, None, None
            if prev_df is not None and not prev_df.empty:
                pct_col = "涨跌幅"
                if pct_col in prev_df.columns:
                    premium_avg = float(prev_df[pct_col].mean())
                    premium_high = float(prev_df[pct_col].max())
                    premium_low = float(prev_df[pct_col].min())

            real_count = len([lu for lu in limit_ups if "ST" not in (lu.name or "")])
            emotion_record = emo_engine.build_emotion_record(
                trade_date=trade_date,
                limit_up_count=len(limit_ups),
                limit_up_count_real=real_count,
                limit_down_count=len(limit_downs),
                burst_count=len(bursts),
                advance_count=0,
                decline_count=0,
                max_continuous=ladder.max_height,
                max_continuous_code=ladder.max_height_stocks[0][0] if ladder.max_height_stocks else None,
                max_continuous_name=ladder.max_height_stocks[0][1] if ladder.max_height_stocks else None,
                yesterday_premium_avg=premium_avg,
                yesterday_premium_high=premium_high,
                yesterday_premium_low=premium_low,
                total_amount=None,
                board_counts=ladder.board_counts,
                promotion_rates=promotion.rates,
            )

            history = list(emo_repo.get_recent(trade_date, limit=10))
            snapshot = emo_engine.analyze(emotion_record, history)
            emotion_record.emotion_phase = snapshot.phase
            emotion_record.emotion_score = snapshot.score

            emo_repo.upsert(emotion_record)
            s.commit()
            logger.info(f"  emotion: {snapshot.phase} ({snapshot.score})")

            # Step 3: Theme analysis
            concept_boards = _build_concept_boards_from_limit_ups(limit_ups)
            prev_themes = list(theme_repo.get_by_date(prev))
            theme_summary = theme_engine.analyze_themes(
                trade_date=trade_date,
                limit_ups=limit_ups,
                concept_boards=concept_boards,
                yesterday_themes=prev_themes,
            )
            for rec in theme_engine.to_records(theme_summary):
                theme_repo.upsert(rec)
            s.commit()
            logger.info(f"  themes: {theme_summary.active_theme_count} active, {theme_summary.new_theme_count} new")

            # Step 4: Recap
            report = recap_engine.generate(
                trade_date=trade_date,
                emotion=snapshot,
                ladder=ladder,
                promotion=promotion,
                theme_summary=theme_summary,
                dt_summary=None,
            )
            recap_repo.upsert(recap_engine.to_record(report))
            s.commit()
            logger.info(f"  recap generated")

    logger.info("\nBackfill complete!")


if __name__ == "__main__":
    backfill_all()
