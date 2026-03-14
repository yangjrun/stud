"""Shared test fixtures."""

from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine

from src.data.models import (
    DailyBurst,
    DailyEmotion,
    DailyLimitUp,
    DailyRecap,
    DailyTheme,
    DragonTiger,
    DragonTigerSeat,
    KnownPlayer,
    Watchlist,
)


@pytest.fixture()
def engine():
    """In-memory SQLite engine for tests."""
    eng = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Fresh session per test."""
    with Session(engine) as s:
        yield s


# ─── Factory helpers ───


def make_emotion(
    trade_date: date,
    *,
    limit_up_count_real: int = 50,
    seal_success_rate: float = 70.0,
    max_continuous: int = 3,
    yesterday_premium_avg: float = 1.5,
    emotion_phase: str = "发酵",
    emotion_score: int = 55,
    **kwargs,
) -> DailyEmotion:
    defaults = dict(
        trade_date=trade_date,
        limit_up_count=limit_up_count_real + 5,
        limit_up_count_real=limit_up_count_real,
        limit_down_count=10,
        burst_count=8,
        seal_success_rate=seal_success_rate,
        advance_count=2000,
        decline_count=1500,
        advance_decline_ratio=1.33,
        max_continuous=max_continuous,
        max_continuous_code="000001",
        max_continuous_name="测试股",
        yesterday_premium_avg=yesterday_premium_avg,
        yesterday_premium_high=5.0,
        yesterday_premium_low=-2.0,
        total_amount=1_000_000_000_000,
        emotion_phase=emotion_phase,
        emotion_score=emotion_score,
    )
    defaults.update(kwargs)
    return DailyEmotion(**defaults)


def make_limit_up(
    trade_date: date,
    code: str = "000001",
    *,
    name: str = "测试股",
    continuous_count: int = 1,
    seal_amount: float = 500_000_000,
    amount: float = 200_000_000,
    first_seal_time: str = "09:35:00",
    open_count: int = 0,
    concept: str = "人工智能",
    **kwargs,
) -> DailyLimitUp:
    defaults = dict(
        trade_date=trade_date,
        code=code,
        name=name,
        close_price=10.0,
        change_pct=10.0,
        turnover_rate=5.0,
        amount=amount,
        circulating_mv=5_000_000_000,
        seal_amount=seal_amount,
        seal_ratio=seal_amount / amount if amount else 0,
        first_seal_time=first_seal_time,
        last_seal_time=first_seal_time,
        open_count=open_count,
        continuous_count=continuous_count,
        concept=concept,
    )
    defaults.update(kwargs)
    return DailyLimitUp(**defaults)


def make_theme(
    trade_date: date,
    concept_name: str = "人工智能",
    *,
    limit_up_count: int = 5,
    leader_code: str = "000001",
    leader_name: str = "测试股",
    leader_continuous: int = 2,
    consecutive_days: int = 3,
    **kwargs,
) -> DailyTheme:
    defaults = dict(
        trade_date=trade_date,
        concept_name=concept_name,
        change_pct=3.5,
        limit_up_count=limit_up_count,
        total_stocks=100,
        leader_code=leader_code,
        leader_name=leader_name,
        leader_continuous=leader_continuous,
        consecutive_days=consecutive_days,
        is_new_theme=consecutive_days == 1,
    )
    defaults.update(kwargs)
    return DailyTheme(**defaults)
