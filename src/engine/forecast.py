"""明日预测引擎: 基于 AI API 分析今日确认数据推算明日买入/卖出机会。"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, Sequence

from src.config.settings import settings

logger = logging.getLogger(__name__)
from src.data.models import DailyEmotion, DailyLimitUp
from src.data.models_journal import Position
from src.data.models_signal import ForecastCandidate, ForecastSignal
from src.engine.ai_client import AIForecastClient, AIForecastResponse
from src.engine.ai_prompts import build_forecast_prompt
from src.engine.signal import EchelonInfo


# ─── 数据结构 (保持下游接口不变) ───


@dataclass(frozen=True)
class StrategyContext:
    """情绪策略上下文。"""

    phase: str
    strategy_name: str  # 进攻型/试探型/防守型/观望型/空仓
    allow_roles: tuple[str, ...]  # 本策略允许的角色
    role_confidence_bonus: dict[str, int]  # {龙头: 10, 二龙: 5, ...}
    summary: str  # 策略一句话总结给前端
    intensity: str = "normal"  # "strong" / "normal" / "weak"


@dataclass(frozen=True)
class GateForecast:
    """门控预测结果。"""

    predicted_phase: str
    predicted_score: int
    predicted_result: str  # PASS / FAIL / CAUTION
    transition: str  # e.g. "修复->发酵"
    confidence: int  # 0-100
    rationale: str
    factors: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EchelonProjection:
    """单个题材梯队的明日投射。"""

    theme_name: str
    projected_distribution: dict[int, int]  # {板高: 预测数量}
    continuation_score: int  # 0-100
    leader_fatigue: bool
    projected_completeness: int
    consecutive_days: int


@dataclass(frozen=True)
class BuyCandidateForecast:
    """明日买入候选预测。"""

    code: str
    name: str
    forecast_type: str
    predicted_board: str  # e.g. "1->2"
    theme_name: str
    confidence: int
    today_continuous: int
    predicted_continuous: int
    historical_rate: Optional[float]
    theme_formation: str
    theme_completeness: int
    theme_consecutive_days: int
    rationale: str
    market_role: str  # 龙头/二龙/三龙/跟风
    tier: str = "C"  # A/B/C 档位
    has_dragon_tiger: bool = False
    has_known_player: bool = False


@dataclass(frozen=True)
class SellForecast:
    """明日卖出预警。"""

    code: str
    name: str
    severity: str  # URGENT / WARN
    reason: str
    confidence: int


@dataclass
class ForecastOutput:
    """预测引擎完整输出。"""

    source_date: date  # 今天
    target_date: date  # 明天
    gate: GateForecast
    echelon_projections: list[EchelonProjection]
    buy_candidates: list[BuyCandidateForecast]
    sell_forecasts: list[SellForecast]
    strategy: StrategyContext


# ─── 辅助函数 ───


def _next_trading_day(d: date) -> date:
    """简易计算下一个工作日。"""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


# ─── AI 响应转换 ───


def _ai_to_gate(ai: AIForecastResponse) -> GateForecast:
    """将 AI 响应转为 GateForecast。"""
    return GateForecast(
        predicted_phase=ai.predicted_phase,
        predicted_score=ai.predicted_score,
        predicted_result=ai.predicted_gate_result,
        transition=ai.phase_transition,
        confidence=ai.gate_confidence,
        rationale=ai.gate_rationale,
    )


def _ai_to_strategy(ai: AIForecastResponse) -> StrategyContext:
    """将 AI 响应转为 StrategyContext。"""
    # 根据 AI 返回的策略名动态生成角色加分
    role_bonus = _build_role_bonus(ai.strategy_name)
    return StrategyContext(
        phase=ai.predicted_phase,
        strategy_name=ai.strategy_name,
        allow_roles=tuple(ai.allow_roles),
        role_confidence_bonus=role_bonus,
        summary=ai.strategy_summary,
        intensity=ai.strategy_intensity,
    )


def _build_role_bonus(strategy_name: str) -> dict[str, int]:
    """根据策略名生成角色加分表。"""
    bonuses: dict[str, dict[str, int]] = {
        "进攻型": {"龙头": 10, "二龙": 5, "三龙": 0, "跟风": -15},
        "试探型": {"龙头": 10, "二龙": 5, "三龙": 0, "跟风": -5},
        "防守型": {"龙头": 10, "二龙": 0, "三龙": -5, "跟风": -10},
        "观望型": {"龙头": 5, "二龙": 0, "三龙": -5, "跟风": -10},
        "空仓": {"龙头": 0, "二龙": -5, "三龙": -10, "跟风": -15},
    }
    return bonuses.get(strategy_name, bonuses["观望型"])


def _ai_to_buy_candidates(
    ai: AIForecastResponse,
    limit_ups: Sequence[DailyLimitUp],
    echelons: list[EchelonInfo],
    dt_seats_map: dict[str, list] | None,
) -> list[BuyCandidateForecast]:
    """将 AI 买入候选转为 BuyCandidateForecast 列表。"""
    lu_map = {lu.code: lu for lu in limit_ups}
    ech_map = {ech.theme_name: ech for ech in echelons}

    candidates = []
    for cand in ai.buy_candidates:
        lu = lu_map.get(cand.code)
        ech = ech_map.get(cand.theme_name)

        today_cont = lu.continuous_count if lu else 0
        has_dt = bool(dt_seats_map and dt_seats_map.get(cand.code))
        has_known = False
        if dt_seats_map:
            seats = dt_seats_map.get(cand.code, [])
            has_known = any(
                getattr(s, "is_known_player", False)
                and getattr(s, "direction", "") == "BUY"
                for s in seats
            )

        candidates.append(BuyCandidateForecast(
            code=cand.code,
            name=cand.name,
            forecast_type=cand.forecast_type,
            predicted_board=cand.predicted_board,
            theme_name=cand.theme_name,
            confidence=cand.ai_score,
            today_continuous=today_cont,
            predicted_continuous=today_cont + 1,
            historical_rate=None,
            theme_formation=ech.formation if ech else "scattered",
            theme_completeness=ech.completeness if ech else 0,
            theme_consecutive_days=ech.consecutive_days if ech else 0,
            rationale=cand.rationale,
            market_role=cand.market_role,
            tier=cand.tier,
            has_dragon_tiger=has_dt,
            has_known_player=has_known,
        ))
    return candidates


def _ai_to_sell_forecasts(ai: AIForecastResponse) -> list[SellForecast]:
    """将 AI 卖出预警转为 SellForecast 列表。"""
    return [
        SellForecast(
            code=s.code,
            name=s.name,
            severity=s.severity,
            reason=s.reason,
            confidence=s.confidence,
        )
        for s in ai.sell_forecasts
    ]


# ─── 向后兼容: signal.py 路由需要从存储的 forecast 重建策略 ───

_STRATEGY_TABLE: dict[str, tuple[str, tuple[str, ...], dict[str, int], str]] = {
    "发酵": (
        "进攻型",
        ("龙头", "二龙", "三龙", "跟风"),
        {"龙头": 10, "二龙": 5, "三龙": 0, "跟风": -15},
        "情绪发酵中，龙头确认强势，可跟随二龙三龙参与",
    ),
    "高潮": (
        "进攻型",
        ("龙头", "二龙", "三龙", "跟风"),
        {"龙头": 10, "二龙": 5, "三龙": 0, "跟风": -15},
        "情绪高潮期，龙头确认后二龙三龙普涨，注意高位风险",
    ),
    "修复": (
        "试探型",
        ("龙头", "二龙"),
        {"龙头": 10, "二龙": 5, "三龙": 0, "跟风": -5},
        "情绪修复中，仅跟随龙头和强势二龙，不追跟风",
    ),
    "分歧": (
        "防守型",
        ("龙头",),
        {"龙头": 10, "二龙": 0, "三龙": -5, "跟风": -10},
        "情绪分歧，仅关注龙头换手转一致，不推荐二龙以下",
    ),
    "震荡": (
        "观望型",
        ("龙头",),
        {"龙头": 5, "二龙": 0, "三龙": -5, "跟风": -10},
        "情绪震荡，仅推荐最强龙头，极低仓位参与",
    ),
    "冰点": (
        "空仓",
        (),
        {"龙头": 0, "二龙": -5, "三龙": -10, "跟风": -15},
        "情绪冰点，不推荐任何买入操作",
    ),
    "退潮": (
        "空仓",
        (),
        {"龙头": 0, "二龙": -5, "三龙": -10, "跟风": -15},
        "情绪退潮，不推荐任何买入操作",
    ),
}


def _calc_multi_factor_trend(
    emotion: DailyEmotion,
    history: Sequence[DailyEmotion],
) -> tuple[float, dict[str, float]]:
    """从 DailyEmotion 提取 5 个因子, 输出连续趋势值 (-1.0 ~ +1.0) 和因子明细。

    保留供 signal.py 路由在读取已存储 forecast 时重建策略使用。
    """
    recent = sorted(
        [e for e in history if e.emotion_score is not None],
        key=lambda x: x.trade_date,
    )[-5:]

    recent_lu = [e.limit_up_count for e in recent if e.limit_up_count]
    avg_lu = sum(recent_lu) / len(recent_lu) if recent_lu else max(emotion.limit_up_count, 1)
    lu_momentum = max(-1.0, min(1.0, (emotion.limit_up_count - avg_lu) / max(avg_lu, 1)))

    burst_rate = emotion.burst_count / max(emotion.limit_up_count, 1)
    burst_factor = -min(1.0, burst_rate)

    recent_seal = [e.seal_success_rate for e in recent if e.seal_success_rate is not None]
    if emotion.seal_success_rate is not None:
        avg_seal = sum(recent_seal) / len(recent_seal) if recent_seal else emotion.seal_success_rate
        seal_factor = max(-1.0, min(1.0, (emotion.seal_success_rate - avg_seal) / max(avg_seal, 0.01)))
    else:
        seal_factor = 0.0

    premium = emotion.yesterday_premium_avg or 0
    premium_factor = max(-1.0, min(1.0, premium / 10))

    adr = emotion.advance_decline_ratio
    adr_factor = max(-1.0, min(1.0, (adr - 1.0) / 1.0)) if adr is not None else 0.0

    trend = (
        lu_momentum * 0.25
        + burst_factor * 0.20
        + seal_factor * 0.15
        + premium_factor * 0.25
        + adr_factor * 0.15
    )
    trend = max(-1.0, min(1.0, trend))

    factors = {
        "limit_up_momentum": round(lu_momentum, 3),
        "burst_rate": round(burst_rate, 3),
        "seal_success_rate": round(emotion.seal_success_rate or 0, 3),
        "premium_avg": round(premium, 2),
        "trend_score": round(trend, 3),
    }
    return trend, factors


def _determine_emotion_strategy(
    gate: GateForecast,
    emotion: Optional[DailyEmotion] = None,
) -> StrategyContext:
    """根据预测情绪阶段确定操作策略。

    保留供 signal.py 路由在读取已存储 forecast 时重建策略使用。
    """
    predicted_phase = gate.predicted_phase
    score = gate.predicted_score
    confidence = gate.confidence
    burst_rate = (
        emotion.burst_count / max(emotion.limit_up_count, 1) if emotion else 0
    )

    entry = _STRATEGY_TABLE.get(predicted_phase, _STRATEGY_TABLE["震荡"])
    strategy_name, allow_roles, bonus, summary = entry
    bonus = dict(bonus)

    intensity = "normal"
    if predicted_phase in ("发酵", "高潮"):
        if score >= 60 and confidence >= 55:
            intensity = "strong"
            bonus = {k: v + 3 for k, v in bonus.items()}
            summary = f"[强]{summary}"
        elif score < 40:
            intensity = "weak"
    elif predicted_phase == "修复":
        if score >= 50 and confidence >= 50:
            intensity = "strong"
            summary = f"[强]{summary}"

    if burst_rate > 0.3:
        if strategy_name == "进攻型":
            strategy_name = "试探型"
            allow_roles = ("龙头", "二龙")
            summary += "(炸板率高,降级试探)"
        elif strategy_name == "试探型":
            strategy_name = "防守型"
            allow_roles = ("龙头",)
            summary += "(炸板率高,降级防守)"

    return StrategyContext(
        phase=predicted_phase,
        strategy_name=strategy_name,
        allow_roles=allow_roles,
        role_confidence_bonus=bonus,
        summary=summary,
        intensity=intensity,
    )


# ─── 准确率检查 ───


_PHASE_ORDER = ["冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡"]


def _phases_adjacent(a: str, b: str) -> bool:
    """判断两个阶段是否相邻。"""
    if a not in _PHASE_ORDER or b not in _PHASE_ORDER:
        return False
    ia = _PHASE_ORDER.index(a)
    ib = _PHASE_ORDER.index(b)
    return abs(ia - ib) == 1


def check_accuracy(
    forecast: ForecastSignal,
    actual_phase: Optional[str],
    actual_limit_up_codes: set[str],
    forecast_candidates: Sequence[ForecastCandidate],
) -> tuple[int, float]:
    """对比预测与实际结果, 返回 (gate_accuracy, candidate_hit_rate)。"""
    if actual_phase is None:
        gate_accuracy = 0
    elif forecast.predicted_gate_phase == actual_phase:
        gate_accuracy = 100
    elif _phases_adjacent(forecast.predicted_gate_phase or "", actual_phase):
        gate_accuracy = 50
    else:
        gate_accuracy = 0

    buy_candidates = [c for c in forecast_candidates if c.forecast_type != "sell_warning"]
    if not buy_candidates:
        return gate_accuracy, 0.0

    hits = sum(1 for c in buy_candidates if c.code in actual_limit_up_codes)
    hit_rate = (hits / len(buy_candidates)) * 100

    return gate_accuracy, round(hit_rate, 1)


# ─── 主引擎 ───


class ForecastEngine:
    """明日预测引擎 — AI 驱动。"""

    def __init__(self) -> None:
        self._ai_client = AIForecastClient(settings)

    def run(
        self,
        trade_date: date,
        emotion: DailyEmotion,
        emotion_history: Sequence[DailyEmotion],
        echelons: list[EchelonInfo],
        limit_ups: Sequence[DailyLimitUp],
        positions: Sequence[Position],
        dt_seats_map: dict[str, list] | None = None,
        burst_codes: set[str] | None = None,
    ) -> ForecastOutput:
        logger.info("ForecastEngine.run() started for trade_date=%s", trade_date)
        target_date = _next_trading_day(trade_date)

        # 1. 构建 prompt
        logger.info("Building forecast prompt...")
        system_prompt, user_prompt = build_forecast_prompt(
            emotion, emotion_history, echelons, limit_ups,
            positions, dt_seats_map, burst_codes,
        )
        logger.info("Forecast prompt built successfully")

        # 2. 调用 AI（带校验和重试）
        valid_codes = {lu.code for lu in limit_ups}
        logger.info("Calling AI client with %d limit_ups, %d positions, %d echelons",
                    len(limit_ups), len(positions), len(echelons))
        ai_response = self._ai_client.forecast(system_prompt, user_prompt, valid_codes)
        logger.info("AI response received: phase=%s, gate=%s",
                    ai_response.predicted_phase, ai_response.predicted_gate_result)

        # 3. 转换为下游数据结构
        gate = _ai_to_gate(ai_response)
        strategy = _ai_to_strategy(ai_response)
        buy_cands = _ai_to_buy_candidates(ai_response, limit_ups, echelons, dt_seats_map)
        sell_fcs = _ai_to_sell_forecasts(ai_response)

        return ForecastOutput(
            source_date=trade_date,
            target_date=target_date,
            gate=gate,
            echelon_projections=[],
            buy_candidates=buy_cands,
            sell_forecasts=sell_fcs,
            strategy=strategy,
        )

    def to_forecast_signal(self, output: ForecastOutput) -> ForecastSignal:
        """转为 ForecastSignal ORM 记录。"""
        top = output.echelon_projections[0] if output.echelon_projections else None
        return ForecastSignal(
            trade_date=output.target_date,
            source_date=output.source_date,
            predicted_gate_result=output.gate.predicted_result,
            predicted_gate_phase=output.gate.predicted_phase,
            predicted_gate_score=output.gate.predicted_score,
            phase_transition=output.gate.transition,
            phase_transition_confidence=output.gate.confidence,
            predicted_echelon_count=len(output.echelon_projections),
            predicted_top_echelon_name=top.theme_name if top else None,
            echelon_continuation_score=top.continuation_score if top else None,
            buy_candidate_count=len(output.buy_candidates),
            sell_candidate_count=len(output.sell_forecasts),
        )

    def to_forecast_candidates(
        self, output: ForecastOutput,
    ) -> list[ForecastCandidate]:
        """转为 ForecastCandidate ORM 记录列表。"""
        records = []

        for c in output.buy_candidates:
            records.append(ForecastCandidate(
                trade_date=output.target_date,
                source_date=output.source_date,
                code=c.code,
                name=c.name,
                forecast_type=c.forecast_type,
                predicted_board_position=c.predicted_board,
                theme_name=c.theme_name,
                confidence=c.confidence,
                today_continuous_count=c.today_continuous,
                predicted_continuous_count=c.predicted_continuous,
                historical_promotion_rate=c.historical_rate,
                theme_formation=c.theme_formation,
                theme_completeness=c.theme_completeness,
                theme_consecutive_days=c.theme_consecutive_days,
                rationale=c.rationale,
                market_role=c.market_role,
                tier=c.tier,
            ))

        for s in output.sell_forecasts:
            records.append(ForecastCandidate(
                trade_date=output.target_date,
                source_date=output.source_date,
                code=s.code,
                name=s.name,
                forecast_type="sell_warning",
                confidence=s.confidence,
                rationale=s.reason,
            ))

        return records
