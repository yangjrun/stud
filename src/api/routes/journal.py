"""交易日志 API routes."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.models_journal import TradeRecord
from src.data.repo_journal import PositionRepository, TradeRecordRepository

router = APIRouter()


class TradeInput(BaseModel):
    trade_date: str  # YYYY-MM-DD
    code: str
    name: Optional[str] = None
    direction: str  # BUY / SELL
    price: float
    quantity: int
    signal_id: Optional[int] = None
    signal_type: Optional[str] = None
    strategy: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None


@router.get("/trades")
def get_trades(trade_date: date = Depends(parse_date)):
    """某日交易。"""
    with get_session() as s:
        trades = TradeRecordRepository(s).get_by_date(trade_date)
        return {
            "trade_date": str(trade_date),
            "count": len(trades),
            "data": [_trade_dict(t) for t in trades],
        }


@router.get("/trades/range")
def get_trades_range(
    start: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """日期范围交易。"""
    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()
    with get_session() as s:
        trades = TradeRecordRepository(s).get_by_range(start_date, end_date)
        return {
            "start": start,
            "end": end,
            "count": len(trades),
            "data": [_trade_dict(t) for t in trades],
        }


@router.post("/trades")
def add_trade(body: TradeInput):
    """新增交易 (自动更新 Position)。"""
    trade_date = datetime.strptime(body.trade_date, "%Y-%m-%d").date()
    if body.direction not in ("BUY", "SELL"):
        raise HTTPException(400, "direction 必须为 BUY 或 SELL")
    if body.price <= 0 or body.quantity <= 0:
        raise HTTPException(400, "price 和 quantity 必须大于 0")

    amount = round(body.price * body.quantity, 2)

    with get_session() as s:
        trade_repo = TradeRecordRepository(s)
        pos_repo = PositionRepository(s)

        # 卖出校验: 不能卖超持仓
        if body.direction == "SELL":
            pos = pos_repo.get_by_code(body.code)
            if not pos or pos.quantity < body.quantity:
                raise HTTPException(400, "卖出数量超过持仓")

        record = TradeRecord(
            trade_date=trade_date,
            code=body.code,
            name=body.name,
            direction=body.direction,
            price=body.price,
            quantity=body.quantity,
            amount=amount,
            signal_id=body.signal_id,
            signal_type=body.signal_type,
            strategy=body.strategy,
            reason=body.reason,
            notes=body.notes,
        )
        trade_repo.add(record)
        s.flush()  # 确保 record 有 id

        # 重算持仓
        all_trades = trade_repo.get_by_code(body.code)
        pos_repo.recalculate_from_trades(body.code, all_trades)
        s.commit()

        return {"message": "交易已记录", "id": record.id, "amount": amount}


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int):
    """删除交易 (重算 Position)。"""
    with get_session() as s:
        trade_repo = TradeRecordRepository(s)
        record = trade_repo.get_by_id(trade_id)
        if not record:
            raise HTTPException(404, "交易记录不存在")

        code = record.code
        trade_repo.delete(trade_id)
        s.flush()

        # 重算持仓
        pos_repo = PositionRepository(s)
        remaining = trade_repo.get_by_code(code)
        if remaining:
            pos_repo.recalculate_from_trades(code, remaining)
        else:
            # 无交易记录, 清零持仓
            pos = pos_repo.get_by_code(code)
            if pos:
                pos.quantity = 0
                pos.total_cost = 0.0
                pos.avg_cost = 0.0
                pos.realized_pnl = 0.0
                s.add(pos)
        s.commit()

        return {"message": "交易已删除", "id": trade_id}


@router.get("/positions")
def get_positions():
    """当前持仓。"""
    with get_session() as s:
        positions = PositionRepository(s).get_all_open()
        return {
            "count": len(positions),
            "data": [
                {
                    "code": p.code,
                    "name": p.name,
                    "quantity": p.quantity,
                    "avg_cost": p.avg_cost,
                    "total_cost": p.total_cost,
                    "first_buy_date": str(p.first_buy_date) if p.first_buy_date else None,
                    "last_trade_date": str(p.last_trade_date) if p.last_trade_date else None,
                    "realized_pnl": p.realized_pnl,
                }
                for p in positions
            ],
        }


@router.get("/stats")
def get_stats():
    """交易统计 (胜率/收益/按策略)。"""
    with get_session() as s:
        trades = list(TradeRecordRepository(s).get_all())
        positions = list(PositionRepository(s).get_all())

        sells = [t for t in trades if t.direction == "SELL"]
        buys = [t for t in trades if t.direction == "BUY"]

        total_realized = sum(p.realized_pnl for p in positions)

        # 按代码分组计算胜率
        code_pnl: dict[str, float] = {}
        for p in positions:
            if p.realized_pnl != 0:
                code_pnl[p.code] = p.realized_pnl

        wins = sum(1 for v in code_pnl.values() if v > 0)
        losses = sum(1 for v in code_pnl.values() if v < 0)
        total_closed = wins + losses
        win_rate = round(wins / total_closed * 100, 1) if total_closed > 0 else 0

        # 按策略分组
        strategy_stats: dict[str, dict] = {}
        for t in sells:
            strat = t.strategy or "未分类"
            if strat not in strategy_stats:
                strategy_stats[strat] = {"count": 0, "total_amount": 0}
            strategy_stats[strat]["count"] += 1
            strategy_stats[strat]["total_amount"] += t.amount

        return {
            "total_buy_count": len(buys),
            "total_sell_count": len(sells),
            "total_realized_pnl": round(total_realized, 2),
            "win_rate": win_rate,
            "wins": wins,
            "losses": losses,
            "strategy_stats": strategy_stats,
        }


@router.get("/stats/monthly")
def get_monthly_stats():
    """月度 P&L。"""
    with get_session() as s:
        trades = list(TradeRecordRepository(s).get_all())

        # 按月统计买入/卖出金额
        monthly: dict[str, dict] = {}
        for t in trades:
            month_key = t.trade_date.strftime("%Y-%m")
            if month_key not in monthly:
                monthly[month_key] = {"buy_amount": 0, "sell_amount": 0, "trade_count": 0}
            entry = monthly[month_key]
            entry["trade_count"] += 1
            if t.direction == "BUY":
                entry["buy_amount"] += t.amount
            else:
                entry["sell_amount"] += t.amount

        for key, val in monthly.items():
            val["net"] = round(val["sell_amount"] - val["buy_amount"], 2)
            val["buy_amount"] = round(val["buy_amount"], 2)
            val["sell_amount"] = round(val["sell_amount"], 2)

        return {
            "data": [
                {"month": k, **v}
                for k, v in sorted(monthly.items(), reverse=True)
            ],
        }


def _trade_dict(t: TradeRecord) -> dict:
    return {
        "id": t.id,
        "trade_date": str(t.trade_date),
        "code": t.code,
        "name": t.name,
        "direction": t.direction,
        "price": t.price,
        "quantity": t.quantity,
        "amount": t.amount,
        "signal_type": t.signal_type,
        "strategy": t.strategy,
        "reason": t.reason,
        "notes": t.notes,
    }
