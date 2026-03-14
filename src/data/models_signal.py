"""信号引擎相关 ORM 模型。"""

from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class DailySignal(SQLModel, table=True):
    """每日信号总览 (市场级, 每天一行)"""

    __tablename__ = "daily_signal"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(unique=True, index=True)
    # 门控
    gate_result: str = Field(max_length=10)  # PASS / FAIL / CAUTION
    gate_phase: Optional[str] = Field(default=None, max_length=10)
    gate_score: Optional[int] = None
    gate_trend: Optional[int] = None  # 1 / 0 / -1
    gate_max_height: Optional[int] = None
    gate_reason: Optional[str] = Field(default=None, max_length=500)
    # 梯队
    echelon_count: int = Field(default=0)
    top_echelon_name: Optional[str] = Field(default=None, max_length=50)
    top_echelon_formation: Optional[str] = Field(default=None, max_length=20)
    top_echelon_completeness: Optional[int] = None  # 0-100
    # 候选
    candidate_count: int = Field(default=0)
    has_dragon_tiger_supplement: bool = Field(default=False)


class SignalCandidate(SQLModel, table=True):
    """信号候选标的 (每只信号股一行)"""

    __tablename__ = "signal_candidate"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    signal_type: str = Field(max_length=20)  # 分歧转一致 / 梯队确认 / 龙头换手
    board_position: Optional[str] = Field(default=None, max_length=10)  # 首板/1进2/2进3/3进4+
    theme_name: Optional[str] = Field(default=None, max_length=50)
    confidence: int = Field(default=0)  # 0-100
    # 个股指标
    continuous_count: int = Field(default=1)
    open_count: int = Field(default=0)
    seal_strength: Optional[str] = Field(default=None, max_length=10)
    turnover_rate: Optional[float] = None
    # 题材指标
    theme_formation: Optional[str] = Field(default=None, max_length=20)
    theme_completeness: Optional[int] = None
    theme_consecutive_days: Optional[int] = None
    # 游资
    has_known_player: bool = Field(default=False)
    player_names: Optional[str] = Field(default=None, max_length=200)
    source: str = Field(default="analysis", max_length=20)  # analysis / dragon_tiger


class SellSignal(SQLModel, table=True):
    """卖出信号 (每只持仓股一行)"""

    __tablename__ = "sell_signal"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    trigger_type: str = Field(max_length=20)  # gate_fail / stock_burst / leader_fall / theme_weaken
    severity: str = Field(max_length=10)  # URGENT / WARN
    reason: Optional[str] = Field(default=None, max_length=500)
    confidence: int = Field(default=0)
