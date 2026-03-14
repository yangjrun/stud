"""涨停分析引擎: 连板梯队、晋级率、涨停质量评估。"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from src.data.models import DailyBurst, DailyLimitUp


@dataclass(frozen=True)
class LimitUpQuality:
    """单只涨停股的质量评估。"""

    code: str
    name: str
    continuous_count: int
    seal_strength: str  # "强封" / "中等" / "弱封"
    seal_ratio: float  # 封单金额 / 成交额
    first_seal_grade: str  # "早盘强封" / "午前" / "午后" / "尾盘"
    open_count: int
    score: int  # 0-100


@dataclass(frozen=True)
class BoardLadder:
    """连板梯队快照。"""

    trade_date: date
    board_counts: dict[int, int]  # {连板数: 家数}, e.g. {1: 45, 2: 8, 3: 3}
    max_height: int
    max_height_stocks: list[tuple[str, str]]  # [(code, name), ...]
    total_limit_up: int
    total_burst: int


@dataclass(frozen=True)
class PromotionRates:
    """各高度晋级率。"""

    trade_date: date
    rates: dict[str, Optional[float]]  # {"1to2": 0.26, "2to3": 0.38, ...}
    yesterday_counts: dict[int, int]
    today_counts: dict[int, int]


class LimitUpEngine:
    """涨停分析引擎。"""

    # ─── 连板梯队 ───

    def build_ladder(
        self,
        limit_ups: Sequence[DailyLimitUp],
        bursts: Sequence[DailyBurst],
        trade_date: date,
    ) -> BoardLadder:
        board_counts: dict[int, int] = {}
        max_height = 0
        max_height_stocks: list[tuple[str, str]] = []

        for lu in limit_ups:
            n = lu.continuous_count
            board_counts[n] = board_counts.get(n, 0) + 1
            if n > max_height:
                max_height = n
                max_height_stocks = [(lu.code, lu.name or "")]
            elif n == max_height:
                max_height_stocks.append((lu.code, lu.name or ""))

        return BoardLadder(
            trade_date=trade_date,
            board_counts=dict(sorted(board_counts.items())),
            max_height=max_height,
            max_height_stocks=max_height_stocks,
            total_limit_up=len(limit_ups),
            total_burst=len(bursts),
        )

    # ─── 晋级率 ───

    def calc_promotion_rates(
        self,
        yesterday_limit_ups: Sequence[DailyLimitUp],
        today_limit_ups: Sequence[DailyLimitUp],
        trade_date: date,
    ) -> PromotionRates:
        y_counts = _count_by_board(yesterday_limit_ups)
        t_counts = _count_by_board(today_limit_ups)

        rates: dict[str, Optional[float]] = {}
        # 今日 N+1 板 = 昨日 N 板中晋级的
        for n in range(1, max(y_counts.keys(), default=0) + 1):
            key = f"{n}to{n + 1}"
            y_n = y_counts.get(n, 0)
            t_next = t_counts.get(n + 1, 0)
            rates[key] = round(t_next / y_n, 4) if y_n > 0 else None

        return PromotionRates(
            trade_date=trade_date,
            rates=rates,
            yesterday_counts=y_counts,
            today_counts=t_counts,
        )

    # ─── 涨停质量评估 ───

    def evaluate_quality(self, lu: DailyLimitUp) -> LimitUpQuality:
        # 封单强度
        seal_ratio = 0.0
        if lu.seal_amount and lu.amount and lu.amount > 0:
            seal_ratio = lu.seal_amount / lu.amount
        seal_strength = _grade_seal(seal_ratio)

        # 首封时间
        first_seal_grade = _grade_first_seal_time(lu.first_seal_time)

        # 综合评分 (0-100)
        score = _calc_quality_score(
            seal_ratio=seal_ratio,
            first_seal_time=lu.first_seal_time,
            open_count=lu.open_count,
            continuous_count=lu.continuous_count,
            turnover_rate=lu.turnover_rate,
        )

        return LimitUpQuality(
            code=lu.code,
            name=lu.name or "",
            continuous_count=lu.continuous_count,
            seal_strength=seal_strength,
            seal_ratio=round(seal_ratio, 2),
            first_seal_grade=first_seal_grade,
            open_count=lu.open_count,
            score=score,
        )

    def evaluate_all(
        self, limit_ups: Sequence[DailyLimitUp]
    ) -> list[LimitUpQuality]:
        qualities = [self.evaluate_quality(lu) for lu in limit_ups]
        return sorted(qualities, key=lambda q: q.score, reverse=True)

    # ─── 按题材归类 ───

    def group_by_concept(
        self, limit_ups: Sequence[DailyLimitUp]
    ) -> dict[str, list[DailyLimitUp]]:
        groups: dict[str, list[DailyLimitUp]] = {}
        for lu in limit_ups:
            concept = lu.concept or "未知"
            groups.setdefault(concept, []).append(lu)
        # Sort each group by continuous_count desc
        for stocks in groups.values():
            stocks.sort(key=lambda x: x.continuous_count, reverse=True)
        return dict(sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True))


# ─── Private helpers ───


def _count_by_board(limit_ups: Sequence[DailyLimitUp]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for lu in limit_ups:
        n = lu.continuous_count
        counts[n] = counts.get(n, 0) + 1
    return counts


def _grade_seal(seal_ratio: float) -> str:
    if seal_ratio >= 2.0:
        return "强封"
    elif seal_ratio >= 0.5:
        return "中等"
    return "弱封"


def _parse_time_minutes(time_str: Optional[str]) -> Optional[int]:
    """将 HH:MM:SS 或 HHMMSS 转为从 09:30 开始的分钟数。"""
    if not time_str or time_str == "None":
        return None
    clean = time_str.replace(":", "")
    if len(clean) < 4:
        return None
    try:
        h, m = int(clean[:2]), int(clean[2:4])
        return (h - 9) * 60 + (m - 30)
    except ValueError:
        return None


def _grade_first_seal_time(time_str: Optional[str]) -> str:
    minutes = _parse_time_minutes(time_str)
    if minutes is None:
        return "未知"
    if minutes <= 5:  # 09:35 前
        return "秒封"
    if minutes <= 30:  # 10:00 前
        return "早盘强封"
    if minutes <= 120:  # 11:30 前
        return "午前"
    if minutes <= 270:  # 14:00 前
        return "午后"
    return "尾盘"


def _calc_quality_score(
    seal_ratio: float,
    first_seal_time: Optional[str],
    open_count: int,
    continuous_count: int,
    turnover_rate: Optional[float],
) -> int:
    score = 0

    # 封单强度 (0-30)
    if seal_ratio >= 3.0:
        score += 30
    elif seal_ratio >= 2.0:
        score += 25
    elif seal_ratio >= 1.0:
        score += 18
    elif seal_ratio >= 0.5:
        score += 10
    else:
        score += 3

    # 首封时间 (0-30)
    minutes = _parse_time_minutes(first_seal_time)
    if minutes is not None:
        if minutes <= 1:  # 秒封
            score += 30
        elif minutes <= 5:
            score += 25
        elif minutes <= 30:
            score += 20
        elif minutes <= 120:
            score += 12
        elif minutes <= 270:
            score += 5
        else:
            score += 2

    # 炸板次数 (0-20, 越少越好)
    if open_count == 0:
        score += 20
    elif open_count == 1:
        score += 12
    elif open_count == 2:
        score += 5
    # 3+ 次不加分

    # 连板加成 (0-15)
    score += min(15, continuous_count * 3)

    # 换手率 (0-5, 适中最佳)
    if turnover_rate is not None:
        if 3 <= turnover_rate <= 15:
            score += 5
        elif turnover_rate < 3 or turnover_rate <= 25:
            score += 3

    return min(100, score)
