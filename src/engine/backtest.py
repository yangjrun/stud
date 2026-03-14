"""历史回测引擎: 各情绪阶段买入胜率与收益统计。"""

from dataclasses import dataclass
from typing import Optional, Sequence

from src.data.models import DailyEmotion


@dataclass(frozen=True)
class PhaseStats:
    """单个情绪阶段的回测统计。"""

    phase: str
    sample_count: int  # 出现天数
    # 次日涨停溢价 (买涨停股的直接回报指标)
    avg_next1_premium: Optional[float]
    avg_next3_premium: Optional[float]
    avg_next5_premium: Optional[float]
    # 胜率 (溢价 > 0 的概率)
    win_rate_next1: Optional[float]  # 0-1
    win_rate_next3: Optional[float]
    win_rate_next5: Optional[float]
    # 情绪分变化趋势
    avg_score_change_3d: Optional[float]
    avg_score_change_5d: Optional[float]
    # 样本详情 (按日期倒序, 最近的在前)
    details: list[dict]


@dataclass(frozen=True)
class BacktestResult:
    """完整回测结果。"""

    total_days: int
    phase_stats: dict[str, PhaseStats]
    conclusion: str  # 文字总结


class BacktestEngine:
    """情绪周期回测引擎。"""

    PHASES = ("冰点", "修复", "发酵", "高潮", "分歧", "退潮")

    def run(self, records: Sequence[DailyEmotion]) -> BacktestResult:
        """对全部历史情绪数据进行回测分析。

        records 必须按 trade_date 升序排列。
        """
        sorted_records = sorted(records, key=lambda r: r.trade_date)
        n = len(sorted_records)

        # 建立日期索引方便前向查找
        date_index: dict[int, DailyEmotion] = {}
        for i, r in enumerate(sorted_records):
            date_index[i] = r

        phase_stats: dict[str, PhaseStats] = {}

        for phase in self.PHASES:
            stats = self._calc_phase_stats(sorted_records, date_index, n, phase)
            phase_stats[phase] = stats

        conclusion = self._build_conclusion(phase_stats)

        return BacktestResult(
            total_days=n,
            phase_stats=phase_stats,
            conclusion=conclusion,
        )

    def run_single_phase(
        self, records: Sequence[DailyEmotion], phase: str
    ) -> PhaseStats:
        """对单个情绪阶段进行回测。"""
        sorted_records = sorted(records, key=lambda r: r.trade_date)
        n = len(sorted_records)
        date_index = {i: r for i, r in enumerate(sorted_records)}
        return self._calc_phase_stats(sorted_records, date_index, n, phase)

    def _calc_phase_stats(
        self,
        sorted_records: list[DailyEmotion],
        date_index: dict[int, DailyEmotion],
        n: int,
        phase: str,
    ) -> PhaseStats:
        """统计某个阶段的回测数据。"""

        # 收集该阶段出现的所有位置索引
        phase_indices = [
            i
            for i, r in enumerate(sorted_records)
            if r.emotion_phase == phase
        ]

        if not phase_indices:
            return PhaseStats(
                phase=phase,
                sample_count=0,
                avg_next1_premium=None,
                avg_next3_premium=None,
                avg_next5_premium=None,
                win_rate_next1=None,
                win_rate_next3=None,
                win_rate_next5=None,
                avg_score_change_3d=None,
                avg_score_change_5d=None,
                details=[],
            )

        # 对每个出现日, 收集后续 N 日的溢价和情绪分
        next1_premiums: list[float] = []
        next3_premiums: list[float] = []
        next5_premiums: list[float] = []
        score_changes_3d: list[float] = []
        score_changes_5d: list[float] = []
        details: list[dict] = []

        for idx in phase_indices:
            record = date_index[idx]
            today_score = record.emotion_score or 0

            # 次日溢价 (next day's yesterday_premium_avg)
            next1_prem = _get_forward_premium(date_index, idx, 1, n)
            next3_prems = _get_forward_premiums(date_index, idx, 3, n)
            next5_prems = _get_forward_premiums(date_index, idx, 5, n)

            # 情绪分变化
            sc_3d = _get_score_change(date_index, idx, 3, n, today_score)
            sc_5d = _get_score_change(date_index, idx, 5, n, today_score)

            if next1_prem is not None:
                next1_premiums.append(next1_prem)
            if next3_prems:
                next3_premiums.append(sum(next3_prems) / len(next3_prems))
            if next5_prems:
                next5_premiums.append(sum(next5_prems) / len(next5_prems))
            if sc_3d is not None:
                score_changes_3d.append(sc_3d)
            if sc_5d is not None:
                score_changes_5d.append(sc_5d)

            detail = {
                "trade_date": str(record.trade_date),
                "score": today_score,
                "next1_premium": _round_opt(next1_prem),
                "next3_avg_premium": (
                    round(sum(next3_prems) / len(next3_prems), 2) if next3_prems else None
                ),
                "next5_avg_premium": (
                    round(sum(next5_prems) / len(next5_prems), 2) if next5_prems else None
                ),
            }
            details.append(detail)

        # 倒序: 最近的在前
        details.reverse()

        return PhaseStats(
            phase=phase,
            sample_count=len(phase_indices),
            avg_next1_premium=_safe_avg(next1_premiums),
            avg_next3_premium=_safe_avg(next3_premiums),
            avg_next5_premium=_safe_avg(next5_premiums),
            win_rate_next1=_win_rate(next1_premiums),
            win_rate_next3=_win_rate(next3_premiums),
            win_rate_next5=_win_rate(next5_premiums),
            avg_score_change_3d=_safe_avg(score_changes_3d),
            avg_score_change_5d=_safe_avg(score_changes_5d),
            details=details[:50],  # 最多保留50条
        )

    def _build_conclusion(self, stats: dict[str, PhaseStats]) -> str:
        """生成回测结论文字。"""
        lines = ["═══ 情绪周期回测结论 ═══\n"]

        for phase in self.PHASES:
            ps = stats.get(phase)
            if not ps or ps.sample_count == 0:
                continue

            wr = ps.win_rate_next1
            prem = ps.avg_next1_premium
            wr_str = f"{wr * 100:.1f}%" if wr is not None else "N/A"
            prem_str = f"{prem:+.2f}%" if prem is not None else "N/A"

            lines.append(
                f"【{phase}】出现 {ps.sample_count} 次 | "
                f"次日溢价均值 {prem_str} | 胜率 {wr_str}"
            )

        # 对比冰点 vs 高潮
        ice = stats.get("冰点")
        peak = stats.get("高潮")
        if ice and peak and ice.sample_count > 0 and peak.sample_count > 0:
            lines.append("")
            ice_wr = (ice.win_rate_next1 or 0) * 100
            peak_wr = (peak.win_rate_next1 or 0) * 100
            if ice_wr > peak_wr:
                lines.append(
                    f"✦ 冰点买入胜率 ({ice_wr:.1f}%) 高于 高潮买入 ({peak_wr:.1f}%), "
                    "验证「别人恐惧时贪婪」"
                )
            else:
                lines.append(
                    f"✦ 高潮买入胜率 ({peak_wr:.1f}%) ≥ 冰点买入 ({ice_wr:.1f}%), "
                    "当前数据样本可能不足或处于牛市行情"
                )

        return "\n".join(lines)


# ─── Private helpers ───


def _get_forward_premium(
    index: dict[int, DailyEmotion], start: int, offset: int, n: int
) -> Optional[float]:
    """获取 start + offset 位置的 yesterday_premium_avg。"""
    pos = start + offset
    if pos >= n:
        return None
    return index[pos].yesterday_premium_avg


def _get_forward_premiums(
    index: dict[int, DailyEmotion], start: int, days: int, n: int
) -> list[float]:
    """获取 start+1 到 start+days 的所有 premium 值 (跳过 None)。"""
    result = []
    for d in range(1, days + 1):
        pos = start + d
        if pos >= n:
            break
        val = index[pos].yesterday_premium_avg
        if val is not None:
            result.append(val)
    return result


def _get_score_change(
    index: dict[int, DailyEmotion],
    start: int,
    days: int,
    n: int,
    today_score: int,
) -> Optional[float]:
    """获取 start + days 位置与当日的 emotion_score 差值。"""
    pos = start + days
    if pos >= n:
        return None
    future_score = index[pos].emotion_score
    if future_score is None:
        return None
    return float(future_score - today_score)


def _safe_avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _win_rate(values: list[float]) -> Optional[float]:
    if not values:
        return None
    wins = sum(1 for v in values if v > 0)
    return round(wins / len(values), 4)


def _round_opt(v: Optional[float]) -> Optional[float]:
    return round(v, 2) if v is not None else None
