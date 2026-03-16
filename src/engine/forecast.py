"""明日预测引擎: 基于今日确认数据推算明日买入/卖出机会。"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, Sequence

from src.data.models import DailyEmotion, DailyLimitUp, DailyTheme
from src.data.models_journal import Position
from src.data.models_signal import ForecastCandidate, ForecastSignal
from src.engine.signal import EchelonInfo, GateResult, SignalOutput


# ─── 数据结构 ───


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


def _assign_tier(confidence: int) -> str:
    """根据置信度分配档位: A(>=70), B(>=50), C(<50)。"""
    if confidence >= 70:
        return "A"
    if confidence >= 50:
        return "B"
    return "C"


# ─── 阶段转换矩阵 ───

# {(当前阶段, 趋势方向): [(目标阶段, 概率), ...]}
# 趋势: 1=上升, 0=横盘, -1=下降
_TRANSITION_MATRIX: dict[tuple[str, int], list[tuple[str, int]]] = {
    ("冰点", 1): [("修复", 70), ("冰点", 30)],
    ("冰点", 0): [("修复", 50), ("冰点", 50)],
    ("冰点", -1): [("冰点", 80), ("修复", 20)],
    ("修复", 1): [("发酵", 60), ("修复", 40)],
    ("修复", 0): [("修复", 60), ("发酵", 30), ("震荡", 10)],
    ("修复", -1): [("冰点", 40), ("修复", 40), ("退潮", 20)],
    ("发酵", 1): [("高潮", 40), ("发酵", 50), ("分歧", 10)],
    ("发酵", 0): [("发酵", 50), ("高潮", 25), ("分歧", 25)],
    ("发酵", -1): [("分歧", 50), ("发酵", 30), ("退潮", 20)],
    ("高潮", 1): [("高潮", 50), ("分歧", 50)],
    ("高潮", 0): [("分歧", 50), ("高潮", 30), ("退潮", 20)],
    ("高潮", -1): [("分歧", 50), ("退潮", 30), ("高潮", 20)],
    ("分歧", 1): [("修复", 40), ("震荡", 40), ("发酵", 20)],
    ("分歧", 0): [("震荡", 40), ("退潮", 40), ("修复", 20)],
    ("分歧", -1): [("退潮", 60), ("冰点", 30), ("震荡", 10)],
    ("退潮", 1): [("修复", 50), ("退潮", 30), ("冰点", 20)],
    ("退潮", 0): [("冰点", 50), ("退潮", 30), ("修复", 20)],
    ("退潮", -1): [("冰点", 70), ("退潮", 30)],
    ("震荡", 1): [("修复", 40), ("发酵", 35), ("震荡", 25)],
    ("震荡", 0): [("震荡", 50), ("修复", 25), ("退潮", 25)],
    ("震荡", -1): [("退潮", 45), ("冰点", 30), ("震荡", 25)],
}


# ─── 策略表 ───

# {阶段: (策略名, 允许角色, 角色加分, 策略摘要)}
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


# ─── 多因子趋势 ───


def _calc_multi_factor_trend(
    emotion: DailyEmotion,
    history: Sequence[DailyEmotion],
) -> tuple[float, dict[str, float]]:
    """从 DailyEmotion 提取 5 个因子, 输出连续趋势值 (-1.0 ~ +1.0) 和因子明细。"""
    recent = sorted(
        [e for e in history if e.emotion_score is not None],
        key=lambda x: x.trade_date,
    )[-5:]

    # 因子1: 涨停动量 — 今日 vs 5日均值变化率 (权重 25%)
    recent_lu = [e.limit_up_count for e in recent if e.limit_up_count]
    avg_lu = sum(recent_lu) / len(recent_lu) if recent_lu else max(emotion.limit_up_count, 1)
    lu_momentum = (emotion.limit_up_count - avg_lu) / max(avg_lu, 1)
    lu_momentum = max(-1.0, min(1.0, lu_momentum))

    # 因子2: 炸板率 — 当日值, 高=负向 (权重 20%)
    burst_rate = emotion.burst_count / max(emotion.limit_up_count, 1)
    burst_factor = -min(1.0, burst_rate)

    # 因子3: 封板成功率 — 今日 vs 5日均值 (权重 15%)
    recent_seal = [e.seal_success_rate for e in recent if e.seal_success_rate is not None]
    if emotion.seal_success_rate is not None:
        avg_seal = sum(recent_seal) / len(recent_seal) if recent_seal else emotion.seal_success_rate
        seal_factor = (emotion.seal_success_rate - avg_seal) / max(avg_seal, 0.01)
        seal_factor = max(-1.0, min(1.0, seal_factor))
    else:
        seal_factor = 0.0

    # 因子4: 昨日溢价 — 直接值+方向 (权重 25%)
    premium = emotion.yesterday_premium_avg or 0
    premium_factor = max(-1.0, min(1.0, premium / 10))

    # 因子5: 涨跌比 — 当日值映射到 -1~1 (权重 15%)
    adr = emotion.advance_decline_ratio
    if adr is not None:
        adr_factor = max(-1.0, min(1.0, (adr - 1.0) / 1.0))
    else:
        adr_factor = 0.0

    # 加权趋势
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


# ─── 预测函数 ───


def _next_trading_day(d: date) -> date:
    """简易计算下一个工作日。"""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def predict_gate(
    emotion: DailyEmotion,
    history: Sequence[DailyEmotion],
) -> GateForecast:
    """基于多因子趋势 + 阶段转换矩阵预测明日门控状态。"""
    current_phase = emotion.emotion_phase or "震荡"
    current_score = emotion.emotion_score or 0

    # 多因子趋势
    multi_trend, factors = _calc_multi_factor_trend(emotion, history)

    # 趋势离散化用于查转换矩阵
    if multi_trend >= 0.3:
        trend = 1
    elif multi_trend <= -0.3:
        trend = -1
    else:
        trend = 0

    # 查找转换概率
    key = (current_phase, trend)
    transitions = _TRANSITION_MATRIX.get(key, [("震荡", 100)])
    predicted_phase = transitions[0][0]
    transition_prob = transitions[0][1]

    # 多因子加权评分
    burst_rate = factors["burst_rate"]
    lu_momentum = factors["limit_up_momentum"]
    premium = factors["premium_avg"]

    momentum_push = lu_momentum * 10
    premium_push = premium * 5
    burst_penalty = -burst_rate * 15
    trend_push = multi_trend * 8

    predicted_score = int(
        current_score + momentum_push + premium_push + burst_penalty + trend_push,
    )
    predicted_score = max(0, min(100, predicted_score))

    predicted_result = _phase_to_gate_result(predicted_phase, predicted_score)
    transition_str = f"{current_phase}->{predicted_phase}"

    rationale_parts = [
        f"当前阶段={current_phase}(评分{current_score})",
        f"多因子趋势={multi_trend:+.2f}"
        f"({'上升' if trend > 0 else '下降' if trend < 0 else '横盘'})",
        f"涨停动量{lu_momentum:+.0%} 炸板率{burst_rate:.0%} 溢价{premium:.1f}%",
        f"转换概率{transition_prob}%",
        f"预测评分{predicted_score}",
    ]

    return GateForecast(
        predicted_phase=predicted_phase,
        predicted_score=predicted_score,
        predicted_result=predicted_result,
        transition=transition_str,
        confidence=transition_prob,
        rationale=", ".join(rationale_parts),
        factors=factors,
    )


def _phase_to_gate_result(phase: str, score: int) -> str:
    """从阶段和分数推导门控结果。"""
    if phase in ("冰点", "退潮"):
        return "FAIL"
    if phase in ("发酵", "高潮"):
        return "PASS"
    if phase == "修复" and score >= 35:
        return "PASS"
    if phase == "分歧":
        return "CAUTION"
    return "CAUTION"


def project_echelons(
    echelons: list[EchelonInfo],
    emotion: DailyEmotion,
) -> list[EchelonProjection]:
    """投射明日题材梯队状态。"""
    # 从情绪数据获取晋级率
    rate_1to2 = (emotion.promote_1to2_rate or 20) / 100
    rate_2to3 = (emotion.promote_2to3_rate or 15) / 100
    rate_3to4 = (emotion.promote_3to4_rate or 10) / 100

    projections = []
    for ech in echelons:
        if ech.completeness < 30:
            continue

        dist = ech.board_distribution
        projected: dict[int, int] = {}

        # 每层应用晋级率
        for height, count in sorted(dist.items()):
            if height == 1:
                rate = rate_1to2
            elif height == 2:
                rate = rate_2to3
            elif height == 3:
                rate = rate_3to4
            else:
                rate = rate_3to4 * 0.8  # 高板递减

            promoted = max(0, round(count * rate))
            remaining = count - promoted

            if remaining > 0:
                projected[height] = projected.get(height, 0) + remaining
            if promoted > 0:
                projected[height + 1] = projected.get(height + 1, 0) + promoted

        # 龙头疲劳检测
        leader_fatigue = _detect_leader_fatigue(ech)

        # 延续评分
        cont_score = _calc_continuation_score(ech, leader_fatigue)

        # 投射完整度
        proj_completeness = _project_completeness(projected)

        projections.append(EchelonProjection(
            theme_name=ech.theme_name,
            projected_distribution=projected,
            continuation_score=cont_score,
            leader_fatigue=leader_fatigue,
            projected_completeness=proj_completeness,
            consecutive_days=ech.consecutive_days,
        ))

    projections.sort(key=lambda p: p.continuation_score, reverse=True)
    return projections


def _detect_leader_fatigue(ech: EchelonInfo) -> bool:
    """检测龙头是否疲劳。"""
    if ech.consecutive_days >= 5 and ech.completeness < 50:
        return True
    if ech.formation == "scattered":
        return True
    return False


def _calc_continuation_score(ech: EchelonInfo, leader_fatigue: bool) -> int:
    """计算梯队延续评分 (0-100)。"""
    score = 0

    # 基础: 完整度
    score += int(ech.completeness * 0.4)

    # 连续天数 (2-5天最好, 过长反而衰减)
    days = ech.consecutive_days
    if 2 <= days <= 3:
        score += 20
    elif days == 4:
        score += 15
    elif days >= 5:
        score += 8
    else:
        score += 5

    # 阵型加分
    formation_bonus = {"4321": 15, "321": 10, "21": 5, "scattered": 0}
    score += formation_bonus.get(ech.formation, 0)

    # 涨停数量
    if ech.limit_up_count >= 5:
        score += 10
    elif ech.limit_up_count >= 3:
        score += 5

    # 龙头疲劳扣分
    if leader_fatigue:
        score -= 15

    return max(0, min(100, score))


def _project_completeness(dist: dict[int, int]) -> int:
    """根据投射分布计算预估完整度。"""
    if not dist:
        return 0
    heights = sorted(dist.keys(), reverse=True)
    max_h = heights[0]

    if max_h >= 4 and len(heights) >= 3:
        base = 80
    elif max_h >= 3 and len(heights) >= 2:
        base = 55
    elif max_h >= 2:
        base = 25
    else:
        base = 5

    bonus = sum((count - 1) * 3 for count in dist.values() if count > 1)
    if any(h >= 5 for h in dist):
        bonus += 5

    return min(100, base + bonus)


# ─── 角色分类 + 策略分化 ───


def _rank_stocks_in_theme(
    theme_stocks: list[DailyLimitUp],
    echelon: EchelonInfo,
    dt_seats_map: dict[str, list] | None = None,
) -> dict[str, str]:
    """在题材内按强弱排序, 分配角色: 龙头/二龙/三龙/跟风。"""
    if not theme_stocks:
        return {}

    def _effective_amount(s: DailyLimitUp) -> float:
        """成交额, 有知名游资买入则加权1.5倍。"""
        base = s.amount or 0
        if dt_seats_map:
            seats = dt_seats_map.get(s.code, [])
            if any(
                getattr(seat, "is_known_player", False)
                and getattr(seat, "direction", "") == "BUY"
                for seat in seats
            ):
                return base * 1.5
        return base

    # 6维排序: 连板数 > 成交额(含游资加权) > 封单金额 > 封单比 > 首封时间 > 换手率
    ranked = sorted(
        theme_stocks,
        key=lambda s: (
            -s.continuous_count,
            -_effective_amount(s),
            -(s.seal_amount or 0),
            -(s.seal_ratio or 0),
            s.first_seal_time or "15:00",
            (s.turnover_rate or 100),
        ),
    )

    role_map: dict[str, str] = {}
    for i, stock in enumerate(ranked):
        if echelon.leader_code and stock.code == echelon.leader_code:
            role_map[stock.code] = "龙头"
        elif i == 0:
            role_map[stock.code] = "龙头"
        elif i == 1:
            role_map[stock.code] = "二龙"
        elif i == 2:
            role_map[stock.code] = "三龙"
        else:
            role_map[stock.code] = "跟风"

    # 如果 leader_code 存在但不在排名第一, 需要调整
    if echelon.leader_code and echelon.leader_code in role_map:
        leader_code = echelon.leader_code
        if role_map[leader_code] != "龙头":
            for code, role in role_map.items():
                if role == "龙头" and code != leader_code:
                    old_leader = code
                    old_second = next(
                        (c for c, r in role_map.items() if r == "二龙"),
                        None,
                    )
                    role_map[leader_code] = "龙头"
                    role_map[old_leader] = "二龙"
                    if old_second and old_second != leader_code:
                        role_map[old_second] = "三龙"
                    break

    return role_map


def _determine_emotion_strategy(
    gate: GateForecast,
    emotion: Optional[DailyEmotion] = None,
) -> StrategyContext:
    """根据预测情绪阶段 + 门控详情确定操作策略, 含强弱分级和炸板降级。"""
    predicted_phase = gate.predicted_phase
    score = gate.predicted_score
    confidence = gate.confidence
    burst_rate = (
        emotion.burst_count / max(emotion.limit_up_count, 1) if emotion else 0
    )

    # 查基础策略表
    entry = _STRATEGY_TABLE.get(predicted_phase, _STRATEGY_TABLE["震荡"])
    strategy_name, allow_roles, bonus, summary = entry
    bonus = dict(bonus)  # 复制以便修改

    # 强弱分级
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

    # 炸板率降级: >30% 进攻→试探, 试探→防守
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


# ─── 候选生成 ───


def forecast_buy_candidates(
    limit_ups: Sequence[DailyLimitUp],
    projections: list[EchelonProjection],
    gate_forecast: GateForecast,
    emotion: DailyEmotion,
    echelons: list[EchelonInfo],
    strategy: StrategyContext,
    dt_seats_map: dict[str, list] | None = None,
    burst_codes: set[str] | None = None,
) -> list[BuyCandidateForecast]:
    """从强势梯队中筛选明日买入候选 (带角色分层 + 策略过滤 + 龙虎榜 + 炸板过滤)。"""
    if gate_forecast.predicted_result == "FAIL":
        return []

    rate_1to2 = emotion.promote_1to2_rate or 20
    rate_2to3 = emotion.promote_2to3_rate or 15
    rate_3to4 = emotion.promote_3to4_rate or 10

    echelon_map = {ech.theme_name: ech for ech in echelons}

    candidates = []

    for proj in projections:
        if proj.continuation_score < 30:
            continue

        theme_stocks = [
            lu for lu in limit_ups
            if lu.concept and proj.theme_name in lu.concept
        ]

        if not theme_stocks:
            continue

        ech = echelon_map.get(proj.theme_name)
        if not ech:
            continue

        # 角色分类 (含龙虎榜加权)
        role_map = _rank_stocks_in_theme(theme_stocks, ech, dt_seats_map)

        for lu in theme_stocks:
            cont = lu.continuous_count
            role = role_map.get(lu.code, "跟风")

            # 策略过滤
            if role not in strategy.allow_roles:
                continue

            # 炸板过滤: 跟风直接跳过
            if burst_codes and lu.code in burst_codes and role == "跟风":
                continue

            # 晋级率
            if cont == 1:
                hist_rate = rate_1to2
            elif cont == 2:
                hist_rate = rate_2to3
            elif cont == 3:
                hist_rate = rate_3to4
            else:
                hist_rate = rate_3to4 * 0.7

            # 信号类型判定
            forecast_type, predicted_board = _classify_forecast_type(
                lu, proj, theme_stocks, role, strategy,
            )
            if forecast_type is None:
                continue

            # 置信度计算 (含龙虎榜维度)
            confidence = _calc_forecast_confidence(
                gate_forecast, proj, lu, hist_rate, role, strategy,
                dt_seats_map=dt_seats_map,
            )

            # 炸板扣分 (龙头不扣)
            if burst_codes and lu.code in burst_codes:
                if role == "三龙":
                    confidence -= 10
                elif role == "二龙":
                    confidence -= 5

            if confidence < 30:
                continue

            # 龙虎榜标记
            has_dt = bool(dt_seats_map and dt_seats_map.get(lu.code))
            has_known = False
            if dt_seats_map:
                seats = dt_seats_map.get(lu.code, [])
                has_known = any(
                    getattr(s, "is_known_player", False)
                    and getattr(s, "direction", "") == "BUY"
                    for s in seats
                )

            dt_seats = (
                dt_seats_map.get(lu.code, []) if dt_seats_map else None
            )
            rationale = _build_rationale(
                lu, proj, forecast_type, hist_rate, role, strategy, ech,
                dt_seats=dt_seats,
            )

            candidates.append(BuyCandidateForecast(
                code=lu.code,
                name=lu.name or "",
                forecast_type=forecast_type,
                predicted_board=predicted_board,
                theme_name=proj.theme_name,
                confidence=confidence,
                today_continuous=cont,
                predicted_continuous=cont + 1,
                historical_rate=hist_rate,
                theme_formation=_formation_from_dist(proj.projected_distribution),
                theme_completeness=proj.projected_completeness,
                theme_consecutive_days=proj.consecutive_days,
                rationale=rationale,
                market_role=role,
                tier=_assign_tier(confidence),
                has_dragon_tiger=has_dt,
                has_known_player=has_known,
            ))

    # 去重, 保留置信度最高的
    seen: set[str] = set()
    unique = []
    for c in sorted(candidates, key=lambda x: x.confidence, reverse=True):
        if c.code not in seen:
            seen.add(c.code)
            unique.append(c)

    return unique[:20]


def _classify_forecast_type(
    lu: DailyLimitUp,
    proj: EchelonProjection,
    theme_stocks: list[DailyLimitUp],
    role: str,
    strategy: StrategyContext,
) -> tuple[Optional[str], str]:
    """判定预测信号类型和预测板位 (带角色 + 策略)。返回 (None, ...) 表示跳过。"""
    cont = lu.continuous_count
    predicted_board = f"{cont}->{cont + 1}"
    is_offensive = strategy.strategy_name in ("进攻型",)
    is_probing = strategy.strategy_name in ("试探型",)

    if role == "龙头":
        if is_offensive:
            return "leader_confirm", predicted_board
        return "leader_promote", predicted_board

    if role == "二龙":
        if is_offensive or is_probing:
            return "second_follow", predicted_board
        return None, predicted_board

    if role == "三龙":
        if is_offensive:
            return "third_follow", predicted_board
        return None, predicted_board

    # 跟风
    if is_offensive and proj.continuation_score >= 60:
        return "theme_spread", predicted_board
    return None, predicted_board


def _calc_forecast_confidence(
    gate: GateForecast,
    proj: EchelonProjection,
    lu: DailyLimitUp,
    hist_rate: float,
    role: str,
    strategy: StrategyContext,
    dt_seats_map: dict[str, list] | None = None,
) -> int:
    """计算预测置信度 (0-100), 含角色权重 + 龙虎榜修正。"""
    # 门控预测 15%
    gate_part = {"PASS": 15, "CAUTION": 9, "FAIL": 0}[gate.predicted_result]

    # 梯队延续 25%
    echelon_part = int(proj.continuation_score * 0.25)

    # 个股质量 25%
    quality = 0
    if lu.seal_ratio is not None and lu.seal_ratio >= 2.0:
        quality += 10
    elif lu.seal_ratio is not None and lu.seal_ratio >= 0.5:
        quality += 5
    if lu.first_seal_time and lu.first_seal_time < "10:00":
        quality += 8
    elif lu.first_seal_time and lu.first_seal_time < "11:30":
        quality += 4
    if lu.open_count == 0:
        quality += 7
    elif lu.open_count == 1:
        quality += 3
    quality = min(20, quality)

    # 历史晋级率 20%
    rate_part = min(20, int(hist_rate * 0.5))

    # 龙虎榜 20%
    dt_bonus = 0
    if dt_seats_map:
        seats = dt_seats_map.get(lu.code, [])
        buy_seats = [s for s in seats if getattr(s, "direction", "") == "BUY"]
        known_buyers = [
            s for s in buy_seats if getattr(s, "is_known_player", False)
        ]
        if known_buyers:
            dt_bonus += 12
            net = sum(getattr(s, "net_amount", 0) or 0 for s in buy_seats)
            if net > 50_000_000:
                dt_bonus += 5
        elif buy_seats:
            dt_bonus += 3
    dt_bonus = min(20, dt_bonus)

    base = gate_part + echelon_part + quality + rate_part + dt_bonus

    # 板高惩罚: 高板连板风险递增
    cont = lu.continuous_count
    if cont == 3:
        base -= 5
    elif cont == 4:
        base -= 10
    elif cont >= 5:
        base -= 15

    # 角色权重修正
    role_bonus = strategy.role_confidence_bonus.get(role, 0)

    return max(0, min(100, base + role_bonus))


def _build_rationale(
    lu: DailyLimitUp,
    proj: EchelonProjection,
    forecast_type: str,
    hist_rate: float,
    role: str,
    strategy: StrategyContext,
    ech: EchelonInfo,
    dt_seats: list | None = None,
) -> str:
    """生成结构化多段预测理由。"""
    sections = []

    # 第一段: 角色定位
    seal_info = f"封单比{lu.seal_ratio:.1f}" if lu.seal_ratio else "封单未知"
    role_line = (
        f"[{role}] {lu.name or lu.code}"
        f'为"{proj.theme_name}"题材{role}，'
        f"{lu.continuous_count}连板，{seal_info}"
    )
    sections.append(role_line)

    # 第二段: 策略逻辑
    type_labels = {
        "leader_confirm": "龙头确认强势，预测继续走强",
        "leader_promote": f"{lu.continuous_count}板晋级(历史率{hist_rate:.0f}%)",
        "second_follow": f"龙头确认后二龙有望跟随晋级，历史晋级率{hist_rate:.0f}%",
        "third_follow": f"题材普涨中三龙跟随，历史晋级率{hist_rate:.0f}%",
        "theme_spread": f"题材延续分{proj.continuation_score}，跟风受益",
    }
    strategy_line = (
        f"当前情绪{strategy.phase}({strategy.strategy_name}"
        f"{'/' + strategy.intensity if strategy.intensity != 'normal' else ''})，"
        f"{type_labels.get(forecast_type, f'晋级率{hist_rate:.0f}%')}"
    )
    sections.append(strategy_line)

    # 第三段: 龙虎榜信息
    if dt_seats:
        buy_known = [
            s for s in dt_seats
            if getattr(s, "direction", "") == "BUY"
            and getattr(s, "is_known_player", False)
        ]
        if buy_known:
            names = []
            for s in buy_known:
                pname = getattr(s, "player_name", None)
                net = getattr(s, "net_amount", 0) or 0
                if pname and net:
                    names.append(f"{pname}净买入{net / 10000:.0f}万")
                elif pname:
                    names.append(pname)
            if names:
                sections.append("游资: " + ", ".join(names))

    # 第四段: 风险提示
    risks = []
    if proj.consecutive_days >= 4:
        risks.append(f"题材已连续{proj.consecutive_days}天，龙头疲劳风险上升")
    if proj.projected_completeness < 60:
        risks.append(f"梯队完整度仅{proj.projected_completeness}%，跟风需谨慎")
    if lu.open_count >= 2:
        risks.append(f"炸板{lu.open_count}次，封板质量偏弱")

    if risks:
        sections.append("注意：" + "；".join(risks))

    return "\n".join(sections)


def _formation_from_dist(dist: dict[int, int]) -> str:
    """从分布推断阵型。"""
    heights = sorted(dist.keys(), reverse=True)
    if not heights:
        return "scattered"
    max_h = heights[0]
    if max_h >= 4 and len(heights) >= 3:
        return "4321"
    if max_h >= 3 and len(heights) >= 2:
        return "321"
    if max_h >= 2:
        return "21"
    return "scattered"


def forecast_sell_signals(
    gate_forecast: GateForecast,
    projections: list[EchelonProjection],
    positions: Sequence[Position],
) -> list[SellForecast]:
    """预测明日卖出信号。"""
    if not positions:
        return []

    proj_map = {p.theme_name: p for p in projections}
    signals = []

    for pos in positions:
        if pos.quantity <= 0:
            continue

        if gate_forecast.predicted_result == "FAIL":
            signals.append(SellForecast(
                code=pos.code,
                name=pos.name or "",
                severity="URGENT",
                reason=f"明日门控预测FAIL: {gate_forecast.rationale}",
                confidence=gate_forecast.confidence,
            ))
            continue

        weakening = False
        for proj in projections:
            if proj.leader_fatigue and proj.continuation_score < 30:
                weakening = True
                signals.append(SellForecast(
                    code=pos.code,
                    name=pos.name or "",
                    severity="WARN",
                    reason=f"题材[{proj.theme_name}]龙头疲劳, 延续分仅{proj.continuation_score}",
                    confidence=55,
                ))
                break

        if not weakening and gate_forecast.predicted_result == "CAUTION":
            strong_echelons = [p for p in projections if p.continuation_score >= 50]
            if not strong_echelons:
                signals.append(SellForecast(
                    code=pos.code,
                    name=pos.name or "",
                    severity="WARN",
                    reason="明日门控CAUTION且无强势梯队, 注意风险",
                    confidence=40,
                ))

    return signals


# ─── 准确率检查 ───


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


_PHASE_ORDER = ["冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡"]


def _phases_adjacent(a: str, b: str) -> bool:
    """判断两个阶段是否相邻。"""
    if a not in _PHASE_ORDER or b not in _PHASE_ORDER:
        return False
    ia = _PHASE_ORDER.index(a)
    ib = _PHASE_ORDER.index(b)
    return abs(ia - ib) == 1


# ─── 主引擎 ───


class ForecastEngine:
    """明日预测引擎。"""

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
        target_date = _next_trading_day(trade_date)

        # Step 1: 门控预测 (多因子)
        gate = predict_gate(emotion, emotion_history)

        # Step 2: 情绪策略 (含强弱分级 + 炸板降级)
        strategy = _determine_emotion_strategy(gate, emotion)

        # Step 3: 梯队投射
        proj = project_echelons(echelons, emotion)

        # Step 4: 买入候选预测 (角色 + 策略 + 龙虎榜 + 炸板过滤)
        buy_cands = forecast_buy_candidates(
            limit_ups, proj, gate, emotion, echelons, strategy,
            dt_seats_map=dt_seats_map,
            burst_codes=burst_codes,
        )

        # Step 5: 卖出预警预测
        sell_fcs = forecast_sell_signals(gate, proj, positions)

        return ForecastOutput(
            source_date=trade_date,
            target_date=target_date,
            gate=gate,
            echelon_projections=proj,
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
