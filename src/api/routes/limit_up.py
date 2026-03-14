"""涨停分析 API routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.repository import BurstRepository, LimitUpRepository
from src.engine.limit_up import LimitUpEngine

router = APIRouter()


@router.get("/today")
def get_limit_up_today(trade_date: date = Depends(parse_date)):
    """获取当日涨停列表 + 质量评分。"""
    with get_session() as s:
        lu_repo = LimitUpRepository(s)
        burst_repo = BurstRepository(s)
        limit_ups = lu_repo.get_by_date(trade_date)
        bursts = burst_repo.get_by_date(trade_date)

        engine = LimitUpEngine()
        qualities = engine.evaluate_all(limit_ups)

        return {
            "trade_date": str(trade_date),
            "total": len(limit_ups),
            "burst_total": len(bursts),
            "stocks": [
                {
                    "code": q.code,
                    "name": q.name,
                    "continuous_count": q.continuous_count,
                    "seal_strength": q.seal_strength,
                    "seal_ratio": q.seal_ratio,
                    "first_seal_grade": q.first_seal_grade,
                    "open_count": q.open_count,
                    "score": q.score,
                }
                for q in qualities
            ],
        }


@router.get("/ladder")
def get_ladder(trade_date: date = Depends(parse_date)):
    """获取连板梯队。"""
    with get_session() as s:
        lu_repo = LimitUpRepository(s)
        burst_repo = BurstRepository(s)
        limit_ups = lu_repo.get_by_date(trade_date)
        bursts = burst_repo.get_by_date(trade_date)

        engine = LimitUpEngine()
        ladder = engine.build_ladder(limit_ups, bursts, trade_date)

        return {
            "trade_date": str(trade_date),
            "board_counts": ladder.board_counts,
            "max_height": ladder.max_height,
            "max_height_stocks": [
                {"code": c, "name": n} for c, n in ladder.max_height_stocks
            ],
            "total_limit_up": ladder.total_limit_up,
            "total_burst": ladder.total_burst,
        }


@router.get("/promotion")
def get_promotion(trade_date: date = Depends(parse_date)):
    """获取连板晋级率。"""
    from datetime import timedelta

    with get_session() as s:
        lu_repo = LimitUpRepository(s)
        today_ups = lu_repo.get_by_date(trade_date)

        # 找前一个交易日 (简单回退, 跳过周末)
        prev = trade_date - timedelta(days=1)
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        yesterday_ups = lu_repo.get_by_date(prev)

        engine = LimitUpEngine()
        rates = engine.calc_promotion_rates(yesterday_ups, today_ups, trade_date)

        return {
            "trade_date": str(trade_date),
            "rates": rates.rates,
            "yesterday_counts": rates.yesterday_counts,
            "today_counts": rates.today_counts,
        }


@router.get("/quality/{code}")
def get_quality(code: str, trade_date: date = Depends(parse_date)):
    """获取单只涨停股质量评估。"""
    with get_session() as s:
        lu_repo = LimitUpRepository(s)
        limit_ups = lu_repo.get_by_date(trade_date)

        target = next((lu for lu in limit_ups if lu.code == code), None)
        if not target:
            return {"error": f"{code} 不在 {trade_date} 的涨停列表中"}

        engine = LimitUpEngine()
        q = engine.evaluate_quality(target)

        return {
            "code": q.code,
            "name": q.name,
            "continuous_count": q.continuous_count,
            "seal_strength": q.seal_strength,
            "seal_ratio": q.seal_ratio,
            "first_seal_grade": q.first_seal_grade,
            "open_count": q.open_count,
            "score": q.score,
        }
