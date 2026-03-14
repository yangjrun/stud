"""情绪周期 API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.repository import EmotionRepository
from src.engine.emotion import EmotionEngine

router = APIRouter()


@router.get("/today")
def get_emotion_today(trade_date: date = Depends(parse_date)):
    """获取当日情绪分析。"""
    with get_session() as s:
        repo = EmotionRepository(s)
        record = repo.get_by_date(trade_date)
        if not record:
            return {"error": "当日无数据", "trade_date": str(trade_date)}

        history = list(repo.get_recent(trade_date, limit=10))
        engine = EmotionEngine()
        snapshot = engine.analyze(record, history)

        return {
            "trade_date": str(snapshot.trade_date),
            "score": snapshot.score,
            "phase": snapshot.phase,
            "sub_scores": snapshot.sub_scores,
            "trend_direction": snapshot.trend_direction,
            "phase_days": snapshot.phase_days,
            "raw": {
                "limit_up_count": record.limit_up_count,
                "limit_up_count_real": record.limit_up_count_real,
                "limit_down_count": record.limit_down_count,
                "burst_count": record.burst_count,
                "seal_success_rate": record.seal_success_rate,
                "advance_decline_ratio": record.advance_decline_ratio,
                "max_continuous": record.max_continuous,
                "max_continuous_name": record.max_continuous_name,
                "yesterday_premium_avg": record.yesterday_premium_avg,
                "total_amount": record.total_amount,
            },
        }


@router.get("/history")
def get_emotion_history(
    days: int = Query(60, ge=1, le=250, description="天数"),
    trade_date: date = Depends(parse_date),
):
    """获取近 N 日情绪历史曲线。"""
    with get_session() as s:
        repo = EmotionRepository(s)
        # Include today + N-1 days before
        today_record = repo.get_by_date(trade_date)
        history = list(repo.get_recent(trade_date, limit=days))
        if today_record:
            history.insert(0, today_record)

        return {
            "count": len(history),
            "data": [
                {
                    "trade_date": str(e.trade_date),
                    "score": e.emotion_score,
                    "phase": e.emotion_phase,
                    "limit_up_count": e.limit_up_count_real,
                    "limit_down_count": e.limit_down_count,
                    "burst_count": e.burst_count,
                    "seal_success_rate": e.seal_success_rate,
                    "max_continuous": e.max_continuous,
                    "advance_decline_ratio": e.advance_decline_ratio,
                    "total_amount": e.total_amount,
                }
                for e in sorted(history, key=lambda x: x.trade_date)
            ],
        }
