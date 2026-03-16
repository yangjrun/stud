"""预测回测 ORM 模型。"""

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ForecastBacktestRun(SQLModel, table=True):
    """预测回测运行记录 (每次回测一行)"""

    __tablename__ = "forecast_backtest_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    start_date: date = Field(index=True)
    end_date: date = Field(index=True)
    total_days: int = Field(default=0)
    skipped_days: int = Field(default=0)
    avg_gate_accuracy: Optional[float] = None
    avg_candidate_hit_rate: Optional[float] = None
    gate_exact_match_rate: Optional[float] = None
    total_buy_candidates: int = Field(default=0)
    total_hits: int = Field(default=0)
    avg_tier_a_hit_rate: Optional[float] = None
    avg_tier_b_hit_rate: Optional[float] = None
    avg_tier_c_hit_rate: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.now)


class ForecastBacktestDay(SQLModel, table=True):
    """预测回测逐日明细"""

    __tablename__ = "forecast_backtest_day"

    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    source_date: date
    target_date: date
    predicted_gate_result: Optional[str] = Field(default=None, max_length=10)
    predicted_gate_phase: Optional[str] = Field(default=None, max_length=10)
    predicted_gate_score: Optional[int] = None
    actual_gate_phase: Optional[str] = Field(default=None, max_length=10)
    gate_accuracy: Optional[int] = None  # 0/50/100
    buy_candidate_count: int = Field(default=0)
    hit_count: int = Field(default=0)
    candidate_hit_rate: Optional[float] = None
    predicted_top_echelon: Optional[str] = Field(default=None, max_length=50)
    strategy_name: Optional[str] = Field(default=None, max_length=20)
    tier_a_count: int = Field(default=0)
    tier_a_hits: int = Field(default=0)
    tier_b_count: int = Field(default=0)
    tier_b_hits: int = Field(default=0)
    tier_c_count: int = Field(default=0)
    tier_c_hits: int = Field(default=0)
    skip_reason: Optional[str] = Field(default=None, max_length=200)
