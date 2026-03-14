"""交易日志相关 Repository。"""

from datetime import date
from typing import Optional, Sequence

from sqlmodel import Session, col, func, select

from src.data.models_journal import Position, TradeRecord


class TradeRecordRepository:
    def __init__(self, session: Session):
        self._s = session

    def add(self, record: TradeRecord) -> TradeRecord:
        self._s.add(record)
        return record

    def get_by_id(self, record_id: int) -> Optional[TradeRecord]:
        return self._s.get(TradeRecord, record_id)

    def delete(self, record_id: int) -> bool:
        record = self._s.get(TradeRecord, record_id)
        if record:
            self._s.delete(record)
            return True
        return False

    def get_by_date(self, trade_date: date) -> Sequence[TradeRecord]:
        return self._s.exec(
            select(TradeRecord)
            .where(TradeRecord.trade_date == trade_date)
            .order_by(TradeRecord.created_at.desc())
        ).all()

    def get_by_range(self, start: date, end: date) -> Sequence[TradeRecord]:
        return self._s.exec(
            select(TradeRecord)
            .where(TradeRecord.trade_date >= start, TradeRecord.trade_date <= end)
            .order_by(TradeRecord.trade_date.desc(), TradeRecord.created_at.desc())
        ).all()

    def get_by_code(self, code: str) -> Sequence[TradeRecord]:
        return self._s.exec(
            select(TradeRecord)
            .where(TradeRecord.code == code)
            .order_by(TradeRecord.trade_date.desc())
        ).all()

    def get_all(self) -> Sequence[TradeRecord]:
        return self._s.exec(
            select(TradeRecord).order_by(TradeRecord.trade_date.desc())
        ).all()


class PositionRepository:
    def __init__(self, session: Session):
        self._s = session

    def get_by_code(self, code: str) -> Optional[Position]:
        return self._s.exec(
            select(Position).where(Position.code == code)
        ).first()

    def get_all_open(self) -> Sequence[Position]:
        return self._s.exec(
            select(Position).where(col(Position.quantity) > 0)
        ).all()

    def get_all(self) -> Sequence[Position]:
        return self._s.exec(select(Position)).all()

    def upsert(self, record: Position) -> Position:
        existing = self._s.exec(
            select(Position).where(Position.code == record.code)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def recalculate_from_trades(self, code: str, trades: Sequence[TradeRecord]) -> Position:
        """根据全部交易记录重算持仓。"""
        pos = self.get_by_code(code)
        if not pos:
            pos = Position(code=code)

        quantity = 0
        total_cost = 0.0
        realized_pnl = 0.0
        first_buy: Optional[date] = None
        last_trade: Optional[date] = None
        name: Optional[str] = None

        for t in sorted(trades, key=lambda x: (x.trade_date, x.created_at or x.trade_date)):
            name = t.name or name
            last_trade = t.trade_date
            if t.direction == "BUY":
                if first_buy is None:
                    first_buy = t.trade_date
                total_cost += t.amount
                quantity += t.quantity
            elif t.direction == "SELL":
                if quantity > 0:
                    avg = total_cost / quantity
                    sell_cost = avg * t.quantity
                    realized_pnl += t.amount - sell_cost
                    total_cost -= sell_cost
                quantity -= t.quantity

        quantity = max(0, quantity)
        if quantity == 0:
            total_cost = 0.0

        pos.name = name
        pos.quantity = quantity
        pos.total_cost = round(total_cost, 2)
        pos.avg_cost = round(total_cost / quantity, 4) if quantity > 0 else 0.0
        pos.first_buy_date = first_buy
        pos.last_trade_date = last_trade
        pos.realized_pnl = round(realized_pnl, 2)

        return self.upsert(pos)
