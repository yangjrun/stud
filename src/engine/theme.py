"""题材追踪引擎: 热门题材排名、龙头识别、持续性追踪。"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from src.data.models import DailyLimitUp, DailyTheme


@dataclass(frozen=True)
class ThemeSnapshot:
    """单个题材的当日分析。"""

    concept_name: str
    change_pct: Optional[float]
    limit_up_count: int
    total_stocks: Optional[int]
    leader_code: Optional[str]
    leader_name: Optional[str]
    leader_continuous: int
    consecutive_days: int
    is_new_theme: bool
    strength_score: int  # 0-100


@dataclass(frozen=True)
class ThemeSummary:
    """当日题材总览。"""

    trade_date: date
    themes: list[ThemeSnapshot]
    new_theme_count: int
    active_theme_count: int


class ThemeEngine:
    """题材追踪引擎。"""

    def analyze_themes(
        self,
        trade_date: date,
        limit_ups: Sequence[DailyLimitUp],
        concept_boards: list[dict],
        yesterday_themes: Sequence[DailyTheme],
    ) -> ThemeSummary:
        """
        分析当日题材.

        Args:
            limit_ups: 当日涨停列表
            concept_boards: 概念板块行情 [{"concept_name", "change_pct", "total_stocks", ...}]
            yesterday_themes: 昨日题材记录 (用于计算连续天数)
        """
        # 按所属行业/概念统计涨停家数
        concept_limit_ups = _count_limit_ups_by_concept(limit_ups)

        # 昨日题材 lookup
        yesterday_map = {t.concept_name: t for t in yesterday_themes}

        themes: list[ThemeSnapshot] = []
        for board in concept_boards:
            name = board.get("concept_name", "")
            if not name:
                continue

            lu_count = concept_limit_ups.get(name, 0)
            if lu_count == 0 and (board.get("change_pct") or 0) < 1.0:
                continue  # 跳过无涨停且涨幅不足1%的板块

            # 龙头: 板块内连板最高的
            leader = _find_leader(limit_ups, name)

            # 连续天数
            prev = yesterday_map.get(name)
            consecutive = (prev.consecutive_days + 1) if prev else 1
            is_new = prev is None

            strength = _calc_theme_strength(
                limit_up_count=lu_count,
                total_stocks=board.get("total_stocks"),
                change_pct=board.get("change_pct"),
                leader_continuous=leader[2] if leader else 0,
                consecutive_days=consecutive,
                is_new=is_new,
            )

            themes.append(ThemeSnapshot(
                concept_name=name,
                change_pct=board.get("change_pct"),
                limit_up_count=lu_count,
                total_stocks=board.get("total_stocks"),
                leader_code=leader[0] if leader else None,
                leader_name=leader[1] if leader else None,
                leader_continuous=leader[2] if leader else 0,
                consecutive_days=consecutive,
                is_new_theme=is_new,
                strength_score=strength,
            ))

        themes.sort(key=lambda t: t.strength_score, reverse=True)

        return ThemeSummary(
            trade_date=trade_date,
            themes=themes[:30],  # Top 30
            new_theme_count=sum(1 for t in themes if t.is_new_theme),
            active_theme_count=len(themes),
        )

    def to_records(self, summary: ThemeSummary) -> list[DailyTheme]:
        """转为数据库记录。"""
        return [
            DailyTheme(
                trade_date=summary.trade_date,
                concept_name=t.concept_name,
                change_pct=t.change_pct,
                limit_up_count=t.limit_up_count,
                total_stocks=t.total_stocks,
                leader_code=t.leader_code,
                leader_name=t.leader_name,
                leader_continuous=t.leader_continuous,
                consecutive_days=t.consecutive_days,
                is_new_theme=t.is_new_theme,
            )
            for t in summary.themes
        ]


# ─── Private helpers ───


def _count_limit_ups_by_concept(
    limit_ups: Sequence[DailyLimitUp],
) -> dict[str, int]:
    """统计各概念的涨停家数 (一只股可能属于多个概念)。"""
    counts: dict[str, int] = {}
    for lu in limit_ups:
        concept = lu.concept or ""
        # concept 字段可能是逗号分隔的多个概念
        for c in concept.split(","):
            c = c.strip()
            if c:
                counts[c] = counts.get(c, 0) + 1
    return counts


def _find_leader(
    limit_ups: Sequence[DailyLimitUp], concept_name: str
) -> Optional[tuple[str, str, int]]:
    """找板块内连板最高的股票 (code, name, continuous)。"""
    best: Optional[DailyLimitUp] = None
    for lu in limit_ups:
        concepts = (lu.concept or "").split(",")
        if concept_name not in [c.strip() for c in concepts]:
            continue
        if best is None or lu.continuous_count > best.continuous_count:
            best = lu
    if best is None:
        return None
    return (best.code, best.name or "", best.continuous_count)


def _calc_theme_strength(
    limit_up_count: int,
    total_stocks: Optional[int],
    change_pct: Optional[float],
    leader_continuous: int,
    consecutive_days: int,
    is_new: bool,
) -> int:
    """题材强度评分 (0-100)。"""
    score = 0

    # 涨停家数 (0-30)
    score += min(30, limit_up_count * 5)

    # 涨停占比 (0-15)
    if total_stocks and total_stocks > 0:
        ratio = limit_up_count / total_stocks
        score += min(15, int(ratio * 150))

    # 龙头连板 (0-25)
    score += min(25, leader_continuous * 5)

    # 持续天数 (0-15)
    score += min(15, consecutive_days * 3)

    # 板块涨幅 (0-10)
    if change_pct is not None:
        score += min(10, max(0, int(change_pct * 2)))

    # 新题材加分 (0-5)
    if is_new and limit_up_count >= 3:
        score += 5

    return min(100, score)
