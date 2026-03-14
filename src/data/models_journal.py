"""交易日志相关 ORM 模型。"""

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TradeRecord(SQLModel, table=True):
    """交易记录 (每笔交易一行, 只追加)"""

    __tablename__ = "trade_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    direction: str = Field(max_length=4)  # BUY / SELL
    price: float
    quantity: int
    amount: float  # price * quantity
    # 信号关联 (软引用)
    signal_id: Optional[int] = None
    signal_type: Optional[str] = Field(default=None, max_length=20)
    strategy: Optional[str] = Field(default=None, max_length=20)
    reason: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Position(SQLModel, table=True):
    """持仓 (每只股票一行, 交易时自动更新)"""

    __tablename__ = "position"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=10, unique=True, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    quantity: int = Field(default=0)
    avg_cost: float = Field(default=0.0)
    total_cost: float = Field(default=0.0)
    first_buy_date: Optional[date] = None
    last_trade_date: Optional[date] = None
    realized_pnl: float = Field(default=0.0)
