"""APScheduler 定时任务: 盘后自动采集 + 分析 + 复盘。"""

from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from src.data.collector import DataCollector
from src.data.database import get_session, init_db
from src.data.models import DailyEmotion
from src.data.repository import (
    BurstRepository,
    EmotionRepository,
    KnownPlayerRepository,
    LimitDownRepository,
    LimitUpRepository,
    RecapRepository,
    ThemeRepository,
)
from src.data.repo_journal import PositionRepository
from src.data.repo_signal import CandidateRepository, SellSignalRepository, SignalRepository
from src.engine.emotion import EmotionEngine
from src.engine.limit_up import LimitUpEngine
from src.engine.recap import RecapEngine
from src.engine.signal import SignalEngine
from src.engine.theme import ThemeEngine


def _prev_trading_day(d: date) -> date:
    prev = d - timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= timedelta(days=1)
    return prev


def _fetch_concept_boards(collector: DataCollector) -> list[dict]:
    """获取概念板块行情, 转为 ThemeEngine 所需的 dict 列表。"""
    df = collector.fetch_concept_board_names()
    if df is None or df.empty:
        return []
    boards = []
    for _, row in df.iterrows():
        boards.append({
            "concept_name": row.get("板块名称", ""),
            "change_pct": row.get("涨跌幅"),
            "total_stocks": row.get("总家数") or row.get("成份股数量"),
        })
    return boards


def job_collect_market_data() -> None:
    """15:05 - 采集涨停/炸板/跌停数据。"""
    today = date.today()
    if today.weekday() >= 5:
        logger.info("Weekend, skipping collection")
        return

    logger.info(f"[Job] Collecting market data for {today}")
    collector = DataCollector()

    with get_session() as s:
        # 涨停
        df = collector.fetch_limit_up_pool(today)
        if df is not None:
            from src.data.models import DailyLimitUp

            repo = LimitUpRepository(s)
            for _, row in df.iterrows():
                repo.upsert(DailyLimitUp(
                    trade_date=today,
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
                    concept=row.get("所属行业"),
                ))
            s.commit()
            logger.info(f"  涨停: {len(df)} records")

        # 炸板
        df = collector.fetch_burst_pool(today)
        if df is not None:
            from src.data.models import DailyBurst

            repo = BurstRepository(s)
            for _, row in df.iterrows():
                repo.upsert(DailyBurst(
                    trade_date=today,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("最新价"),
                    change_pct=row.get("涨跌幅"),
                    turnover_rate=row.get("换手率"),
                    amount=row.get("成交额"),
                    first_seal_time=str(row.get("首次封板时间", "")),
                ))
            s.commit()
            logger.info(f"  炸板: {len(df)} records")

        # 跌停
        df = collector.fetch_limit_down_pool(today)
        if df is not None:
            from src.data.models import DailyLimitDown

            repo = LimitDownRepository(s)
            for _, row in df.iterrows():
                repo.upsert(DailyLimitDown(
                    trade_date=today,
                    code=str(row.get("代码", "")),
                    name=row.get("名称"),
                    close_price=row.get("最新价"),
                    change_pct=row.get("涨跌幅"),
                    amount=row.get("成交额"),
                ))
            s.commit()
            logger.info(f"  跌停: {len(df)} records")


def job_run_analysis() -> None:
    """15:15 - 运行分析引擎, 生成情绪数据 + 复盘。"""
    today = date.today()
    if today.weekday() >= 5:
        return

    logger.info(f"[Job] Running analysis for {today}")

    with get_session() as s:
        lu_repo = LimitUpRepository(s)
        burst_repo = BurstRepository(s)
        ld_repo = LimitDownRepository(s)
        emo_repo = EmotionRepository(s)
        theme_repo = ThemeRepository(s)
        recap_repo = RecapRepository(s)

        limit_ups = lu_repo.get_by_date(today)
        bursts = burst_repo.get_by_date(today)
        limit_downs = ld_repo.get_by_date(today)

        if not limit_ups:
            logger.warning("No limit-up data, skipping analysis")
            return

        lu_engine = LimitUpEngine()
        emo_engine = EmotionEngine()
        recap_engine = RecapEngine()

        # 连板梯队
        ladder = lu_engine.build_ladder(limit_ups, bursts, today)

        # 晋级率
        prev = _prev_trading_day(today)
        yesterday_ups = lu_repo.get_by_date(prev)
        promotion = lu_engine.calc_promotion_rates(yesterday_ups, limit_ups, today)

        # 昨日涨停溢价 (from fetch_limit_up_previous)
        from src.data.collector import DataCollector

        collector = DataCollector()
        prev_df = collector.fetch_limit_up_previous(today)
        premium_avg, premium_high, premium_low = None, None, None
        if prev_df is not None and not prev_df.empty:
            pct_col = "涨跌幅"
            if pct_col in prev_df.columns:
                premium_avg = float(prev_df[pct_col].mean())
                premium_high = float(prev_df[pct_col].max())
                premium_low = float(prev_df[pct_col].min())

        # 构建情绪记录
        real_count = len([lu for lu in limit_ups if "ST" not in (lu.name or "")])
        emotion_record = emo_engine.build_emotion_record(
            trade_date=today,
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

        # 分析情绪
        history = list(emo_repo.get_recent(today, limit=10))
        snapshot = emo_engine.analyze(emotion_record, history)
        emotion_record.emotion_phase = snapshot.phase
        emotion_record.emotion_score = snapshot.score

        emo_repo.upsert(emotion_record)
        s.commit()
        logger.info(f"  情绪: {snapshot.phase} ({snapshot.score})")

        # 题材分析
        theme_engine = ThemeEngine()
        prev_themes = list(theme_repo.get_by_date(_prev_trading_day(today)))
        concept_boards = _fetch_concept_boards(collector)
        theme_summary = theme_engine.analyze_themes(
            trade_date=today,
            limit_ups=limit_ups,
            concept_boards=concept_boards,
            yesterday_themes=prev_themes,
        )
        for rec in theme_engine.to_records(theme_summary):
            theme_repo.upsert(rec)
        s.commit()
        logger.info(f"  题材: {theme_summary.active_theme_count} active, {theme_summary.new_theme_count} new")

        # 生成复盘
        report = recap_engine.generate(
            trade_date=today,
            emotion=snapshot,
            ladder=ladder,
            promotion=promotion,
            theme_summary=theme_summary,
            dt_summary=None,
        )
        recap_repo.upsert(recap_engine.to_record(report))
        s.commit()
        logger.info("  复盘报告已生成")


def job_collect_dragon_tiger() -> None:
    """18:30 - 采集龙虎榜数据。"""
    today = date.today()
    if today.weekday() >= 5:
        return

    logger.info(f"[Job] Collecting dragon-tiger for {today}")
    collector = DataCollector()
    df = collector.fetch_dragon_tiger(today)

    if df is not None and not df.empty:
        from src.data.models import DragonTiger

        with get_session() as s:
            from src.data.repository import DragonTigerRepository

            repo = DragonTigerRepository(s)
            for _, row in df.iterrows():
                trade_date_val = row.get("上榜日")
                if trade_date_val is None:
                    continue
                if hasattr(trade_date_val, "date"):
                    trade_date_val = trade_date_val.date()

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
            s.commit()
            logger.info(f"  龙虎榜: {len(df)} records")


def job_run_signals() -> None:
    """15:20 - 生成买入信号 + 卖出信号 (在 15:15 分析后)。"""
    today = date.today()
    if today.weekday() >= 5:
        return

    logger.info(f"[Job] Running signal engine for {today}")

    with get_session() as s:
        emo_repo = EmotionRepository(s)
        emotion = emo_repo.get_by_date(today)
        if not emotion:
            logger.warning("No emotion data, skipping signals")
            return

        limit_ups = LimitUpRepository(s).get_by_date(today)
        bursts = BurstRepository(s).get_by_date(today)
        themes = ThemeRepository(s).get_by_date(today)
        positions = PositionRepository(s).get_all_open()

        engine = SignalEngine()
        output = engine.run(today, emotion, limit_ups, bursts, themes, positions)

        sig_repo = SignalRepository(s)
        cand_repo = CandidateRepository(s)
        sell_repo = SellSignalRepository(s)

        sig_repo.upsert(engine.to_daily_signal(output))
        for rec in engine.to_candidate_records(today, output.candidates):
            cand_repo.upsert(rec)
        for rec in engine.to_sell_records(today, output.sell_signals):
            sell_repo.upsert(rec)
        s.commit()

        logger.info(
            f"  信号: gate={output.gate.result}, "
            f"candidates={len(output.candidates)}, "
            f"sells={len(output.sell_signals)}"
        )


def job_supplement_signals() -> None:
    """18:40 - 龙虎榜补充候选标的 + 更新置信度。"""
    today = date.today()
    if today.weekday() >= 5:
        return

    logger.info(f"[Job] Supplementing signals with dragon-tiger for {today}")

    with get_session() as s:
        from src.data.repository import DragonTigerRepository, DragonTigerSeatRepository

        dt_repo = DragonTigerRepository(s)
        seat_repo = DragonTigerSeatRepository(s)
        player_repo = KnownPlayerRepository(s)
        cand_repo = CandidateRepository(s)
        sig_repo = SignalRepository(s)

        signal = sig_repo.get_by_date(today)
        if not signal:
            logger.warning("No signal data, skipping supplement")
            return

        dt_stocks = dt_repo.get_by_date(today)
        existing_candidates = {c.code for c in cand_repo.get_by_date(today)}

        added = 0
        for dt in dt_stocks:
            if dt.code in existing_candidates:
                # 已有候选, 更新游资信息
                cand = cand_repo.get_by_code(today, dt.code)
                if cand:
                    seats = seat_repo.get_seats_for_stock(today, dt.code)
                    known = [
                        s.player_name for s in seats
                        if s.is_known_player and s.player_name
                    ]
                    if known:
                        cand.has_known_player = True
                        cand.player_names = ",".join(known)
                        cand.confidence = min(100, cand.confidence + 5)
                        s.add(cand)
                continue

            # 龙虎榜新增候选 (仅涨幅 > 5% 的)
            if dt.change_pct is not None and dt.change_pct > 5:
                seats = seat_repo.get_seats_for_stock(today, dt.code)
                known = [
                    s.player_name for s in seats
                    if s.is_known_player and s.player_name
                ]
                if known:
                    from src.data.models_signal import SignalCandidate

                    cand_repo.upsert(SignalCandidate(
                        trade_date=today,
                        code=dt.code,
                        name=dt.name,
                        signal_type="龙虎榜关注",
                        theme_name=None,
                        confidence=40,
                        continuous_count=1,
                        has_known_player=True,
                        player_names=",".join(known),
                        source="dragon_tiger",
                    ))
                    added += 1

        if added > 0:
            signal.has_dragon_tiger_supplement = True
            signal.candidate_count = len(cand_repo.get_by_date(today))
            s.add(signal)

        s.commit()
        logger.info(f"  龙虎榜补充: {added} new candidates")


def create_scheduler() -> BackgroundScheduler:
    """创建并配置定时任务调度器。"""
    scheduler = BackgroundScheduler()

    # 15:05 采集涨停/炸板/跌停
    scheduler.add_job(
        job_collect_market_data,
        "cron",
        hour=15,
        minute=5,
        day_of_week="mon-fri",
        id="collect_market",
    )

    # 15:15 运行分析 + 生成复盘
    scheduler.add_job(
        job_run_analysis,
        "cron",
        hour=15,
        minute=15,
        day_of_week="mon-fri",
        id="run_analysis",
    )

    # 15:20 生成信号
    scheduler.add_job(
        job_run_signals,
        "cron",
        hour=15,
        minute=20,
        day_of_week="mon-fri",
        id="run_signals",
    )

    # 18:30 采集龙虎榜
    scheduler.add_job(
        job_collect_dragon_tiger,
        "cron",
        hour=18,
        minute=30,
        day_of_week="mon-fri",
        id="collect_dragon_tiger",
    )

    # 18:40 龙虎榜补充信号
    scheduler.add_job(
        job_supplement_signals,
        "cron",
        hour=18,
        minute=40,
        day_of_week="mon-fri",
        id="supplement_signals",
    )

    return scheduler
