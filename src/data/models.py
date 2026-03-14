"""SQLModel ORM definitions for all tables."""

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class DailyLimitUp(SQLModel, table=True):
    """每日涨停快照"""

    __tablename__ = "daily_limit_up"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    close_price: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    amount: Optional[float] = None  # 成交额(元)
    circulating_mv: Optional[float] = None  # 流通市值(元)
    seal_amount: Optional[float] = None  # 封单金额(元)
    seal_ratio: Optional[float] = None  # 封单金额/成交额
    first_seal_time: Optional[str] = Field(default=None, max_length=10)
    last_seal_time: Optional[str] = Field(default=None, max_length=10)
    open_count: int = Field(default=0)  # 打开涨停次数
    continuous_count: int = Field(default=1)  # 连板数
    concept: Optional[str] = Field(default=None, max_length=500)


class DailyBurst(SQLModel, table=True):
    """每日炸板记录"""

    __tablename__ = "daily_burst"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    close_price: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    amount: Optional[float] = None
    first_seal_time: Optional[str] = Field(default=None, max_length=10)
    burst_time: Optional[str] = Field(default=None, max_length=10)


class DailyLimitDown(SQLModel, table=True):
    """每日跌停记录"""

    __tablename__ = "daily_limit_down"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    close_price: Optional[float] = None
    change_pct: Optional[float] = None
    amount: Optional[float] = None


class DailyEmotion(SQLModel, table=True):
    """每日情绪快照 (市场级别, 每天一行)"""

    __tablename__ = "daily_emotion"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(unique=True, index=True)
    limit_up_count: int = Field(default=0)
    limit_up_count_real: int = Field(default=0)  # 不含ST/新股
    limit_down_count: int = Field(default=0)
    burst_count: int = Field(default=0)
    seal_success_rate: Optional[float] = None
    advance_count: int = Field(default=0)
    decline_count: int = Field(default=0)
    advance_decline_ratio: Optional[float] = None
    max_continuous: int = Field(default=0)
    max_continuous_code: Optional[str] = Field(default=None, max_length=10)
    max_continuous_name: Optional[str] = Field(default=None, max_length=20)
    yesterday_premium_avg: Optional[float] = None
    yesterday_premium_high: Optional[float] = None
    yesterday_premium_low: Optional[float] = None
    total_amount: Optional[float] = None  # 市场总成交额
    emotion_phase: Optional[str] = Field(default=None, max_length=10)
    emotion_score: Optional[int] = None  # 0-100
    # 连板梯队
    board_1_count: int = Field(default=0)
    board_2_count: int = Field(default=0)
    board_3_count: int = Field(default=0)
    board_4_count: int = Field(default=0)
    board_5_plus_count: int = Field(default=0)
    # 晋级率
    promote_1to2_rate: Optional[float] = None
    promote_2to3_rate: Optional[float] = None
    promote_3to4_rate: Optional[float] = None
    notes: Optional[str] = None


class DailyTheme(SQLModel, table=True):
    """每日热门题材"""

    __tablename__ = "daily_themes"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    concept_name: str = Field(max_length=50, index=True)
    change_pct: Optional[float] = None
    limit_up_count: int = Field(default=0)
    total_stocks: Optional[int] = None
    amount: Optional[float] = None
    leader_code: Optional[str] = Field(default=None, max_length=10)
    leader_name: Optional[str] = Field(default=None, max_length=20)
    leader_continuous: int = Field(default=0)
    consecutive_days: int = Field(default=1)
    is_new_theme: bool = Field(default=True)
    catalyst: Optional[str] = None


class DragonTiger(SQLModel, table=True):
    """龙虎榜每日明细"""

    __tablename__ = "dragon_tiger"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    close_price: Optional[float] = None
    change_pct: Optional[float] = None
    turnover_rate: Optional[float] = None
    amount: Optional[float] = None
    reason: Optional[str] = Field(default=None, max_length=200)


class DragonTigerSeat(SQLModel, table=True):
    """龙虎榜席位明细"""

    __tablename__ = "dragon_tiger_seats"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(index=True)
    code: str = Field(max_length=10, index=True)
    direction: str = Field(max_length=4)  # 'BUY' or 'SELL'
    rank: int
    seat_name: Optional[str] = Field(default=None, max_length=200)
    buy_amount: Optional[float] = None
    sell_amount: Optional[float] = None
    net_amount: Optional[float] = None
    is_known_player: bool = Field(default=False)
    player_name: Optional[str] = Field(default=None, max_length=50)


class KnownPlayer(SQLModel, table=True):
    """知名游资映射表"""

    __tablename__ = "known_players"

    id: Optional[int] = Field(default=None, primary_key=True)
    seat_name: str = Field(max_length=200, unique=True)
    player_alias: Optional[str] = Field(default=None, max_length=50)
    style: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = None
    is_active: bool = Field(default=True)


class DailyRecap(SQLModel, table=True):
    """每日复盘总结"""

    __tablename__ = "daily_recap"

    id: Optional[int] = Field(default=None, primary_key=True)
    trade_date: date = Field(unique=True, index=True)
    emotion_summary: Optional[str] = None
    theme_summary: Optional[str] = None
    dragon_tiger_summary: Optional[str] = None
    tomorrow_strategy: Optional[str] = None
    user_notes: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class Watchlist(SQLModel, table=True):
    """自选股列表"""

    __tablename__ = "watchlist"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(max_length=10, index=True)
    name: Optional[str] = Field(default=None, max_length=20)
    reason: Optional[str] = None  # 加入原因 / 备注
    alert_limit_up: bool = Field(default=True)  # 涨停提醒
    alert_dragon_tiger: bool = Field(default=False)  # 龙虎榜提醒
    tags: Optional[str] = None  # 自定义标签, 逗号分隔
    created_at: Optional[datetime] = Field(default_factory=datetime.now)


class RecapTemplate(SQLModel, table=True):
    """复盘模板"""

    __tablename__ = "recap_template"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    sections: str  # JSON string: ["emotion", "ladder", "theme", "dragon_tiger", "strategy"]
    is_default: bool = Field(default=False)
    created_at: Optional[datetime] = Field(default_factory=datetime.now)
