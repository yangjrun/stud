"""历史回测 API routes."""

from fastapi import APIRouter, Query

from src.data.database import get_session
from src.data.repository import EmotionRepository
from src.engine.backtest import BacktestEngine

router = APIRouter()


@router.get("/phase-returns")
def get_phase_returns(
    days: int = Query(120, ge=30, le=500, description="回测天数"),
):
    """全部情绪阶段的历史胜率与溢价统计。"""
    with get_session() as s:
        repo = EmotionRepository(s)
        # 获取最近 N 天数据 (get_recent 返回降序, 需全量)
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=days * 2)  # 留余量 (非交易日)
        records = list(repo.get_range(start, end))

        if len(records) < 10:
            return {"error": "历史数据不足, 至少需要10个交易日", "count": len(records)}

        engine = BacktestEngine()
        result = engine.run(records)

        return {
            "total_days": result.total_days,
            "conclusion": result.conclusion,
            "phases": {
                phase: {
                    "sample_count": ps.sample_count,
                    "avg_next1_premium": ps.avg_next1_premium,
                    "avg_next3_premium": ps.avg_next3_premium,
                    "avg_next5_premium": ps.avg_next5_premium,
                    "win_rate_next1": ps.win_rate_next1,
                    "win_rate_next3": ps.win_rate_next3,
                    "win_rate_next5": ps.win_rate_next5,
                    "avg_score_change_3d": ps.avg_score_change_3d,
                    "avg_score_change_5d": ps.avg_score_change_5d,
                }
                for phase, ps in result.phase_stats.items()
            },
        }


@router.get("/phase/{phase}")
def get_phase_detail(
    phase: str,
    days: int = Query(120, ge=30, le=500, description="回测天数"),
    detail_limit: int = Query(30, ge=1, le=50, description="返回详情条数"),
):
    """单个情绪阶段的详细回测数据。"""
    valid_phases = ("冰点", "修复", "发酵", "高潮", "分歧", "退潮")
    if phase not in valid_phases:
        return {"error": f"无效阶段, 可选: {', '.join(valid_phases)}"}

    with get_session() as s:
        repo = EmotionRepository(s)
        from datetime import date, timedelta

        end = date.today()
        start = end - timedelta(days=days * 2)
        records = list(repo.get_range(start, end))

        if len(records) < 10:
            return {"error": "历史数据不足"}

        engine = BacktestEngine()
        ps = engine.run_single_phase(records, phase)

        return {
            "phase": ps.phase,
            "sample_count": ps.sample_count,
            "avg_next1_premium": ps.avg_next1_premium,
            "avg_next3_premium": ps.avg_next3_premium,
            "avg_next5_premium": ps.avg_next5_premium,
            "win_rate_next1": ps.win_rate_next1,
            "win_rate_next3": ps.win_rate_next3,
            "win_rate_next5": ps.win_rate_next5,
            "avg_score_change_3d": ps.avg_score_change_3d,
            "avg_score_change_5d": ps.avg_score_change_5d,
            "details": ps.details[:detail_limit],
        }
