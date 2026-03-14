"""游资管理 API routes (CRUD)。"""

import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from src.data.database import get_session
from src.data.models import KnownPlayer, RecapTemplate
from src.data.repository import KnownPlayerRepository, RecapTemplateRepository

router = APIRouter()


# ─── 游资 CRUD ───


class PlayerCreate(BaseModel):
    seat_name: str
    player_alias: Optional[str] = None
    style: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class PlayerUpdate(BaseModel):
    player_alias: Optional[str] = None
    style: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/")
def list_all_players():
    """获取全部游资 (含已停用)。"""
    with get_session() as s:
        repo = KnownPlayerRepository(s)
        players = repo.get_all()
        return {
            "count": len(players),
            "players": [
                {
                    "id": p.id,
                    "seat_name": p.seat_name,
                    "player_alias": p.player_alias,
                    "style": p.style,
                    "notes": p.notes,
                    "is_active": p.is_active,
                }
                for p in players
            ],
        }


@router.post("/")
def create_player(body: PlayerCreate):
    """添加新游资。"""
    with get_session() as s:
        repo = KnownPlayerRepository(s)
        record = KnownPlayer(
            seat_name=body.seat_name,
            player_alias=body.player_alias,
            style=body.style,
            notes=body.notes,
            is_active=body.is_active,
        )
        repo.upsert(record)
        s.commit()
        return {"status": "created", "seat_name": body.seat_name}


@router.put("/{player_id}")
def update_player(player_id: int, body: PlayerUpdate):
    """更新游资信息。"""
    with get_session() as s:
        repo = KnownPlayerRepository(s)
        player = repo.get_by_id(player_id)
        if not player:
            return {"error": f"游资 ID {player_id} 不存在"}

        if body.player_alias is not None:
            player.player_alias = body.player_alias
        if body.style is not None:
            player.style = body.style
        if body.notes is not None:
            player.notes = body.notes
        if body.is_active is not None:
            player.is_active = body.is_active
        s.add(player)
        s.commit()
        return {"status": "updated", "id": player_id}


@router.delete("/{player_id}")
def delete_player(player_id: int):
    """删除游资。"""
    with get_session() as s:
        repo = KnownPlayerRepository(s)
        deleted = repo.delete(player_id)
        s.commit()
        if deleted:
            return {"status": "deleted", "id": player_id}
        return {"error": f"游资 ID {player_id} 不存在"}


# ─── 复盘模板 ───

DEFAULT_SECTIONS = ["emotion", "ladder", "theme", "dragon_tiger", "strategy"]


class TemplateCreate(BaseModel):
    name: str
    sections: list[str] = DEFAULT_SECTIONS
    is_default: bool = False


@router.get("/templates")
def list_templates():
    """获取全部复盘模板。"""
    with get_session() as s:
        repo = RecapTemplateRepository(s)
        templates = repo.get_all()
        return {
            "count": len(templates),
            "available_sections": [
                "emotion", "ladder", "theme", "dragon_tiger", "strategy", "user_notes",
            ],
            "templates": [
                {
                    "name": t.name,
                    "sections": json.loads(t.sections),
                    "is_default": t.is_default,
                }
                for t in templates
            ],
        }


@router.post("/templates")
def create_template(body: TemplateCreate):
    """创建复盘模板。"""
    with get_session() as s:
        repo = RecapTemplateRepository(s)
        record = RecapTemplate(
            name=body.name,
            sections=json.dumps(body.sections),
            is_default=body.is_default,
        )
        repo.upsert(record)
        s.commit()
        return {"status": "created", "name": body.name}


@router.delete("/templates/{name}")
def delete_template(name: str):
    """删除复盘模板。"""
    with get_session() as s:
        repo = RecapTemplateRepository(s)
        deleted = repo.delete(name)
        s.commit()
        if deleted:
            return {"status": "deleted", "name": name}
        return {"error": f"模板 '{name}' 不存在"}
