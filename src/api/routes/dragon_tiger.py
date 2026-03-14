"""龙虎榜 API routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.repository import (
    DragonTigerRepository,
    DragonTigerSeatRepository,
    KnownPlayerRepository,
)
from src.engine.dragon_tiger import DragonTigerEngine

router = APIRouter()


@router.get("/today")
def get_dragon_tiger_today(trade_date: date = Depends(parse_date)):
    """获取当日龙虎榜分析。"""
    with get_session() as s:
        dt_repo = DragonTigerRepository(s)
        seat_repo = DragonTigerSeatRepository(s)
        kp_repo = KnownPlayerRepository(s)

        dragons = dt_repo.get_by_date(trade_date)
        known_players = kp_repo.get_all_active()

        if not dragons:
            return {"trade_date": str(trade_date), "stocks": [], "message": "暂无龙虎榜数据"}

        # Gather all seats
        all_seats = []
        for dt in dragons:
            seats = seat_repo.get_seats_for_stock(trade_date, dt.code)
            all_seats.extend(seats)

        engine = DragonTigerEngine(known_players)
        summary = engine.analyze_day(trade_date, dragons, all_seats)

        return {
            "trade_date": str(trade_date),
            "total_stocks": len(summary.stocks),
            "top_known_players": [
                {"alias": alias, "count": count}
                for alias, count in summary.top_known_players
            ],
            "stocks": [
                {
                    "code": st.code,
                    "name": st.name,
                    "change_pct": st.change_pct,
                    "reason": st.reason,
                    "total_buy": st.total_buy,
                    "total_sell": st.total_sell,
                    "net_amount": st.net_amount,
                    "known_player_count": st.known_player_count,
                    "has_institution": st.has_institution,
                    "buy_seats": [
                        {
                            "rank": seat.rank,
                            "seat_name": seat.seat_name,
                            "buy_amount": seat.buy_amount,
                            "is_known": seat.is_known,
                            "player_alias": seat.player_alias,
                        }
                        for seat in st.buy_seats
                    ],
                    "sell_seats": [
                        {
                            "rank": seat.rank,
                            "seat_name": seat.seat_name,
                            "sell_amount": seat.sell_amount,
                            "is_known": seat.is_known,
                            "player_alias": seat.player_alias,
                        }
                        for seat in st.sell_seats
                    ],
                }
                for st in summary.stocks
            ],
            "player_activities": [
                {
                    "player_alias": act.player_alias,
                    "code": act.code,
                    "name": act.name,
                    "direction": act.direction,
                    "amount": act.amount,
                }
                for act in summary.player_activities
            ],
        }


@router.get("/player/{player_name}")
def get_player_history(
    player_name: str,
    limit: int = Query(30, ge=1, le=100),
):
    """获取知名游资近期动向。"""
    with get_session() as s:
        seat_repo = DragonTigerSeatRepository(s)
        records = seat_repo.get_by_player(player_name, limit=limit)

        return {
            "player_name": player_name,
            "count": len(records),
            "records": [
                {
                    "trade_date": str(r.trade_date),
                    "code": r.code,
                    "direction": r.direction,
                    "seat_name": r.seat_name,
                    "buy_amount": r.buy_amount,
                    "sell_amount": r.sell_amount,
                    "net_amount": r.net_amount,
                }
                for r in records
            ],
        }


@router.get("/players")
def list_players():
    """获取知名游资列表。"""
    with get_session() as s:
        repo = KnownPlayerRepository(s)
        players = repo.get_all_active()
        return {
            "count": len(players),
            "players": [
                {
                    "id": p.id,
                    "seat_name": p.seat_name,
                    "player_alias": p.player_alias,
                    "style": p.style,
                }
                for p in players
            ],
        }
