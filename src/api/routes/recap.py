"""每日复盘 API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.repository import RecapRepository

router = APIRouter()


@router.get("/today")
def get_recap_today(trade_date: date = Depends(parse_date)):
    """获取当日复盘报告。"""
    with get_session() as s:
        repo = RecapRepository(s)
        recap = repo.get_by_date(trade_date)

        if not recap:
            return {"trade_date": str(trade_date), "error": "暂无复盘数据"}

        return {
            "trade_date": str(recap.trade_date),
            "emotion_summary": recap.emotion_summary,
            "theme_summary": recap.theme_summary,
            "dragon_tiger_summary": recap.dragon_tiger_summary,
            "tomorrow_strategy": recap.tomorrow_strategy,
            "user_notes": recap.user_notes,
        }


@router.get("/{date_str}")
def get_recap_by_date(date_str: str):
    """获取指定日期复盘报告。"""
    from datetime import datetime

    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    with get_session() as s:
        repo = RecapRepository(s)
        recap = repo.get_by_date(trade_date)

        if not recap:
            return {"trade_date": date_str, "error": "暂无复盘数据"}

        return {
            "trade_date": str(recap.trade_date),
            "emotion_summary": recap.emotion_summary,
            "theme_summary": recap.theme_summary,
            "dragon_tiger_summary": recap.dragon_tiger_summary,
            "tomorrow_strategy": recap.tomorrow_strategy,
            "user_notes": recap.user_notes,
        }


class NotesInput(BaseModel):
    notes: str


@router.post("/{date_str}/notes")
def update_recap_notes(date_str: str, body: NotesInput):
    """添加/更新用户笔记。"""
    from datetime import datetime

    from src.data.models import DailyRecap

    trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    with get_session() as s:
        repo = RecapRepository(s)
        repo.upsert(DailyRecap(trade_date=trade_date, user_notes=body.notes))
        s.commit()

    return {"trade_date": date_str, "user_notes": body.notes, "status": "saved"}
