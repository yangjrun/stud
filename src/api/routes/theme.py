"""题材追踪 API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.repository import ThemeRepository

router = APIRouter()


@router.get("/today")
def get_themes_today(
    limit: int = Query(15, ge=1, le=50),
    keyword: Optional[str] = Query(None, description="关键词过滤题材名称"),
    trade_date: date = Depends(parse_date),
):
    """获取当日热门题材排名, 支持关键词过滤。"""
    with get_session() as s:
        repo = ThemeRepository(s)
        themes = repo.get_by_date(trade_date)

        if keyword:
            themes = [t for t in themes if keyword in t.concept_name]

        return {
            "trade_date": str(trade_date),
            "total": len(themes),
            "keyword": keyword,
            "themes": [
                {
                    "concept_name": t.concept_name,
                    "change_pct": t.change_pct,
                    "limit_up_count": t.limit_up_count,
                    "total_stocks": t.total_stocks,
                    "leader_code": t.leader_code,
                    "leader_name": t.leader_name,
                    "leader_continuous": t.leader_continuous,
                    "consecutive_days": t.consecutive_days,
                    "is_new_theme": t.is_new_theme,
                }
                for t in themes[:limit]
            ],
        }


@router.get("/search")
def search_themes(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    days: int = Query(30, ge=1, le=120, description="回溯天数"),
):
    """按关键词搜索历史题材 (跨日期)。"""
    from datetime import timedelta

    end = date.today()
    start = end - timedelta(days=days * 2)

    with get_session() as s:
        repo = ThemeRepository(s)
        results = repo.search_by_keyword(keyword, start, end)

        return {
            "keyword": keyword,
            "count": len(results),
            "themes": [
                {
                    "trade_date": str(t.trade_date),
                    "concept_name": t.concept_name,
                    "change_pct": t.change_pct,
                    "limit_up_count": t.limit_up_count,
                    "leader_name": t.leader_name,
                    "leader_continuous": t.leader_continuous,
                    "consecutive_days": t.consecutive_days,
                }
                for t in results
            ],
        }


@router.get("/{concept_name}/leader")
def get_theme_leader(
    concept_name: str,
    trade_date: date = Depends(parse_date),
):
    """获取指定题材的龙头股信息。"""
    with get_session() as s:
        repo = ThemeRepository(s)
        # 当日数据
        today = repo.get_theme_on_date(concept_name, trade_date)
        if not today:
            return {"error": f"题材 '{concept_name}' 在 {trade_date} 无数据"}

        # 龙头历史轨迹 (近30日该题材的龙头变化)
        history = repo.get_theme_history(concept_name, limit=30)
        leader_timeline = [
            {
                "trade_date": str(t.trade_date),
                "leader_code": t.leader_code,
                "leader_name": t.leader_name,
                "leader_continuous": t.leader_continuous,
            }
            for t in sorted(history, key=lambda x: x.trade_date)
            if t.leader_code
        ]

        return {
            "trade_date": str(trade_date),
            "concept_name": concept_name,
            "leader_code": today.leader_code,
            "leader_name": today.leader_name,
            "leader_continuous": today.leader_continuous,
            "theme_change_pct": today.change_pct,
            "theme_limit_up_count": today.limit_up_count,
            "theme_consecutive_days": today.consecutive_days,
            "leader_timeline": leader_timeline,
        }


@router.get("/{concept_name}/history")
def get_theme_history(
    concept_name: str,
    days: int = Query(30, ge=1, le=120),
):
    """获取单个题材的历史走势。"""
    with get_session() as s:
        repo = ThemeRepository(s)
        history = repo.get_theme_history(concept_name, limit=days)

        return {
            "concept_name": concept_name,
            "count": len(history),
            "data": [
                {
                    "trade_date": str(t.trade_date),
                    "change_pct": t.change_pct,
                    "limit_up_count": t.limit_up_count,
                    "leader_name": t.leader_name,
                    "leader_continuous": t.leader_continuous,
                    "consecutive_days": t.consecutive_days,
                }
                for t in sorted(history, key=lambda x: x.trade_date)
            ],
        }
