"""情绪周期引擎: 评分(0-100) + 六阶段判定。"""

from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from src.data.models import DailyEmotion


# ─── 情绪阶段定义 ───
PHASES = ("冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡")


@dataclass(frozen=True)
class EmotionSnapshot:
    """单日情绪分析结果。"""

    trade_date: date
    score: int  # 0-100
    phase: str  # 冰点/修复/发酵/高潮/分歧/退潮/震荡
    sub_scores: dict[str, int]  # 各维度分项
    trend_direction: int  # 1=上升, -1=下降, 0=横盘
    phase_days: int  # 当前阶段已持续天数


class EmotionEngine:
    """情绪周期判定引擎。"""

    def analyze(
        self,
        today: DailyEmotion,
        history: Sequence[DailyEmotion],
    ) -> EmotionSnapshot:
        sub_scores = {
            "涨停家数": _score_limit_up_count(today.limit_up_count_real),
            "封板成功率": _score_seal_rate(today.seal_success_rate),
            "连板高度": _score_max_continuous(today.max_continuous),
            "昨涨停溢价": _score_premium(today.yesterday_premium_avg),
        }
        score = sum(sub_scores.values())
        score = max(0, min(100, score))

        recent_scores = _extract_recent_scores(history, n=5)
        trend = _calc_trend(recent_scores, score)
        phase = _classify_phase(score, trend)
        phase_days = _count_phase_days(history, phase)

        return EmotionSnapshot(
            trade_date=today.trade_date,
            score=score,
            phase=phase,
            sub_scores=sub_scores,
            trend_direction=trend,
            phase_days=phase_days + 1,
        )

    def build_emotion_record(
        self,
        trade_date: date,
        limit_up_count: int,
        limit_up_count_real: int,
        limit_down_count: int,
        burst_count: int,
        advance_count: int,
        decline_count: int,
        max_continuous: int,
        max_continuous_code: Optional[str],
        max_continuous_name: Optional[str],
        yesterday_premium_avg: Optional[float],
        yesterday_premium_high: Optional[float],
        yesterday_premium_low: Optional[float],
        total_amount: Optional[float],
        board_counts: dict[int, int],
        promotion_rates: dict[str, Optional[float]],
    ) -> DailyEmotion:
        """从各数据源构建 DailyEmotion 记录。"""
        total_seal = limit_up_count + burst_count
        seal_rate = (limit_up_count / total_seal * 100) if total_seal > 0 else None
        adv_dec = (advance_count / decline_count) if decline_count > 0 else None

        return DailyEmotion(
            trade_date=trade_date,
            limit_up_count=limit_up_count,
            limit_up_count_real=limit_up_count_real,
            limit_down_count=limit_down_count,
            burst_count=burst_count,
            seal_success_rate=round(seal_rate, 2) if seal_rate else None,
            advance_count=advance_count,
            decline_count=decline_count,
            advance_decline_ratio=round(adv_dec, 2) if adv_dec else None,
            max_continuous=max_continuous,
            max_continuous_code=max_continuous_code,
            max_continuous_name=max_continuous_name,
            yesterday_premium_avg=yesterday_premium_avg,
            yesterday_premium_high=yesterday_premium_high,
            yesterday_premium_low=yesterday_premium_low,
            total_amount=total_amount,
            board_1_count=board_counts.get(1, 0),
            board_2_count=board_counts.get(2, 0),
            board_3_count=board_counts.get(3, 0),
            board_4_count=board_counts.get(4, 0),
            board_5_plus_count=sum(v for k, v in board_counts.items() if k >= 5),
            promote_1to2_rate=promotion_rates.get("1to2"),
            promote_2to3_rate=promotion_rates.get("2to3"),
            promote_3to4_rate=promotion_rates.get("3to4"),
        )


# ─── 评分子函数 (各 0-25, 总计 0-100) ───


def _score_limit_up_count(count: int) -> int:
    """涨停家数评分 (0-25)。"""
    if count >= 100:
        return 25
    if count >= 80:
        return 22
    if count >= 60:
        return 18
    if count >= 40:
        return 14
    if count >= 30:
        return 10
    if count >= 20:
        return 6
    return 2


def _score_seal_rate(rate: Optional[float]) -> int:
    """封板成功率评分 (0-25), rate 单位 %。"""
    if rate is None:
        return 10  # 中性默认
    if rate >= 85:
        return 25
    if rate >= 75:
        return 20
    if rate >= 65:
        return 15
    if rate >= 55:
        return 10
    if rate >= 45:
        return 5
    return 2


def _score_max_continuous(height: int) -> int:
    """连板高度评分 (0-25)。"""
    if height >= 8:
        return 25
    if height >= 6:
        return 20
    if height >= 5:
        return 17
    if height >= 4:
        return 14
    if height >= 3:
        return 10
    if height >= 2:
        return 6
    return 2


def _score_premium(avg: Optional[float]) -> int:
    """昨日涨停溢价评分 (0-25), avg 单位 %。"""
    if avg is None:
        return 10
    if avg >= 6:
        return 25
    if avg >= 3:
        return 20
    if avg >= 1:
        return 15
    if avg >= 0:
        return 10
    if avg >= -3:
        return 5
    return 2


# ─── 趋势与阶段 ───


def _extract_recent_scores(history: Sequence[DailyEmotion], n: int) -> list[int]:
    """从近N条历史记录提取 emotion_score (按日期升序)。"""
    recent = sorted(history, key=lambda e: e.trade_date)[-n:]
    return [e.emotion_score for e in recent if e.emotion_score is not None]


def _calc_trend(recent_scores: list[int], today_score: int) -> int:
    """计算趋势方向: 1=上升, -1=下降, 0=横盘。"""
    if len(recent_scores) < 2:
        return 0
    avg_prev = sum(recent_scores) / len(recent_scores)
    diff = today_score - avg_prev
    if diff > 5:
        return 1
    if diff < -5:
        return -1
    return 0


def _classify_phase(score: int, trend: int) -> str:
    """根据评分和趋势判定阶段。"""
    if score <= 20:
        return "冰点"
    if score <= 35 and trend >= 0:
        return "修复"
    if score <= 60 and trend > 0:
        return "发酵"
    if score > 75:
        return "高潮"
    if score > 40 and trend < 0:
        return "分歧"
    if score <= 40 and trend < 0:
        return "退潮"
    return "震荡"


def _count_phase_days(history: Sequence[DailyEmotion], current_phase: str) -> int:
    """统计当前阶段已持续多少天 (从最近一条往回数)。"""
    sorted_hist = sorted(history, key=lambda e: e.trade_date, reverse=True)
    days = 0
    for e in sorted_hist:
        if e.emotion_phase == current_phase:
            days += 1
        else:
            break
    return days
