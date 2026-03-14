"""自选股 API routes."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.data.database import get_session
from src.data.models import Watchlist
from src.data.repository import WatchlistRepository

router = APIRouter()


class WatchlistAdd(BaseModel):
    code: str
    name: Optional[str] = None
    reason: Optional[str] = None
    alert_limit_up: bool = True
    alert_dragon_tiger: bool = False
    tags: Optional[str] = None


class WatchlistUpdate(BaseModel):
    reason: Optional[str] = None
    alert_limit_up: Optional[bool] = None
    alert_dragon_tiger: Optional[bool] = None
    tags: Optional[str] = None


@router.get("/")
def list_watchlist():
    """获取全部自选股。"""
    with get_session() as s:
        repo = WatchlistRepository(s)
        items = repo.get_all()
        return {
            "count": len(items),
            "items": [
                {
                    "code": w.code,
                    "name": w.name,
                    "reason": w.reason,
                    "alert_limit_up": w.alert_limit_up,
                    "alert_dragon_tiger": w.alert_dragon_tiger,
                    "tags": w.tags,
                    "created_at": str(w.created_at) if w.created_at else None,
                }
                for w in items
            ],
        }


@router.post("/")
def add_to_watchlist(body: WatchlistAdd):
    """添加自选股。"""
    with get_session() as s:
        repo = WatchlistRepository(s)
        record = Watchlist(
            code=body.code,
            name=body.name,
            reason=body.reason,
            alert_limit_up=body.alert_limit_up,
            alert_dragon_tiger=body.alert_dragon_tiger,
            tags=body.tags,
        )
        repo.add(record)
        s.commit()
        return {"status": "added", "code": body.code}


@router.put("/{code}")
def update_watchlist(code: str, body: WatchlistUpdate):
    """更新自选股配置。"""
    with get_session() as s:
        repo = WatchlistRepository(s)
        existing = repo.get_by_code(code)
        if not existing:
            return {"error": f"自选股 {code} 不存在"}

        if body.reason is not None:
            existing.reason = body.reason
        if body.alert_limit_up is not None:
            existing.alert_limit_up = body.alert_limit_up
        if body.alert_dragon_tiger is not None:
            existing.alert_dragon_tiger = body.alert_dragon_tiger
        if body.tags is not None:
            existing.tags = body.tags
        s.add(existing)
        s.commit()
        return {"status": "updated", "code": code}


@router.delete("/{code}")
def remove_from_watchlist(code: str):
    """移除自选股。"""
    with get_session() as s:
        repo = WatchlistRepository(s)
        deleted = repo.delete(code)
        s.commit()
        if deleted:
            return {"status": "deleted", "code": code}
        return {"error": f"自选股 {code} 不存在"}


@router.get("/check-alerts")
def check_watchlist_alerts():
    """检查自选股是否在今日涨停/龙虎榜中。"""
    from datetime import date

    from src.data.repository import DragonTigerRepository, LimitUpRepository

    today = date.today()
    with get_session() as s:
        wl_repo = WatchlistRepository(s)
        lu_repo = LimitUpRepository(s)
        dt_repo = DragonTigerRepository(s)

        watch_codes = set(wl_repo.get_codes())
        if not watch_codes:
            return {"alerts": []}

        limit_ups = lu_repo.get_by_date(today)
        dragons = dt_repo.get_by_date(today)

        lu_codes = {lu.code for lu in limit_ups}
        dt_codes = {dt.code for dt in dragons}

        alerts = []
        items = wl_repo.get_all()
        for w in items:
            if w.alert_limit_up and w.code in lu_codes:
                alerts.append({
                    "code": w.code,
                    "name": w.name,
                    "type": "涨停",
                    "message": f"{w.name or w.code} 今日涨停!",
                })
            if w.alert_dragon_tiger and w.code in dt_codes:
                alerts.append({
                    "code": w.code,
                    "name": w.name,
                    "type": "龙虎榜",
                    "message": f"{w.name or w.code} 今日上龙虎榜!",
                })

        return {"trade_date": str(today), "alert_count": len(alerts), "alerts": alerts}
