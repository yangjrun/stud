"""三步法信号引擎: 生态门控 → 题材梯队 → 分歧转一致检测。"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from src.data.models import (
    DailyBurst,
    DailyEmotion,
    DailyLimitUp,
    DailyTheme,
    DragonTiger,
    DragonTigerSeat,
)
from src.data.models_journal import Position
from src.data.models_signal import DailySignal, SellSignal, SignalCandidate


# ─── Step 1: 生态门控 ───


@dataclass(frozen=True)
class GateResult:
    """门控输出。"""

    result: str  # PASS / FAIL / CAUTION
    phase: str
    score: int
    trend: int
    max_height: int
    reason: str


def evaluate_gate(emotion: DailyEmotion) -> GateResult:
    """根据情绪快照判断市场环境是否可操作。"""
    phase = emotion.emotion_phase or "震荡"
    score = emotion.emotion_score or 0
    max_height = emotion.max_continuous or 0

    # 计算趋势: 使用当前 score
    trend = 0  # 需要由外部传入或从 history 计算, 这里简化
    # 从 promote_1to2_rate 辅助判断
    promo = emotion.promote_1to2_rate or 0

    # FAIL 条件
    if phase in ("冰点", "退潮"):
        return GateResult(
            result="FAIL", phase=phase, score=score, trend=-1,
            max_height=max_height,
            reason=f"情绪阶段={phase}, 不适合操作",
        )
    if max_height <= 2 and score < 35:
        return GateResult(
            result="FAIL", phase=phase, score=score, trend=-1,
            max_height=max_height,
            reason=f"连板高度仅{max_height}, 评分{score}偏低",
        )

    # PASS 条件
    if phase in ("发酵", "高潮"):
        return GateResult(
            result="PASS", phase=phase, score=score, trend=1,
            max_height=max_height,
            reason=f"情绪阶段={phase}, 适合进攻",
        )
    if phase == "修复" and score >= 35:
        return GateResult(
            result="PASS", phase=phase, score=score, trend=0,
            max_height=max_height,
            reason=f"修复阶段, 评分{score}回暖",
        )

    # CAUTION 条件
    if phase == "分歧" and max_height >= 4:
        return GateResult(
            result="CAUTION", phase=phase, score=score, trend=-1,
            max_height=max_height,
            reason=f"分歧阶段但高度{max_height}仍在, 谨慎操作",
        )
    if phase == "震荡" and promo > 20:
        return GateResult(
            result="CAUTION", phase=phase, score=score, trend=0,
            max_height=max_height,
            reason=f"震荡阶段, 晋级率{promo:.0f}%尚可",
        )

    # 默认 CAUTION
    return GateResult(
        result="CAUTION", phase=phase, score=score, trend=0,
        max_height=max_height,
        reason=f"阶段={phase}, 评分={score}, 中性偏谨慎",
    )


# ─── Step 2: 题材梯队评分 ───


@dataclass(frozen=True)
class EchelonInfo:
    """单个题材梯队信息。"""

    theme_name: str
    formation: str  # 4321 / 321 / 21 / scattered
    completeness: int  # 0-100
    board_distribution: dict  # {1: N, 2: N, 3: N, ...}
    leader_code: Optional[str]
    leader_name: Optional[str]
    leader_continuous: int
    limit_up_count: int
    consecutive_days: int


@dataclass(frozen=True)
class EchelonResult:
    """梯队评估总结果。"""

    echelons: list  # list[EchelonInfo]
    qualified_count: int  # completeness >= 40 的数量


def evaluate_echelons(
    limit_ups: Sequence[DailyLimitUp],
    themes: Sequence[DailyTheme],
) -> EchelonResult:
    """按题材分组涨停股, 评估梯队完整度。"""
    # 按概念分组涨停股
    theme_stocks: dict[str, list[DailyLimitUp]] = {}
    for lu in limit_ups:
        concept = lu.concept or ""
        for theme in themes:
            if theme.concept_name and theme.concept_name in concept:
                stocks = theme_stocks.setdefault(theme.concept_name, [])
                if not any(s.code == lu.code for s in stocks):
                    stocks.append(lu)

    echelons = []
    for theme in themes:
        name = theme.concept_name
        stocks = theme_stocks.get(name, [])
        if not stocks and theme.limit_up_count < 2:
            continue

        # 构建板位分布
        dist: dict[int, int] = {}
        for s in stocks:
            h = s.continuous_count
            dist[h] = dist.get(h, 0) + 1

        # 如果没有直接匹配的 stocks 但 theme 有 limit_up_count, 用 theme 数据
        if not dist and theme.limit_up_count >= 2:
            dist = {1: theme.limit_up_count}

        formation = _classify_formation(dist)
        completeness = _calc_completeness(formation, dist)

        echelons.append(EchelonInfo(
            theme_name=name,
            formation=formation,
            completeness=completeness,
            board_distribution=dist,
            leader_code=theme.leader_code,
            leader_name=theme.leader_name,
            leader_continuous=theme.leader_continuous,
            limit_up_count=theme.limit_up_count or len(stocks),
            consecutive_days=theme.consecutive_days,
        ))

    # 按 completeness 排序
    echelons.sort(key=lambda e: e.completeness, reverse=True)
    qualified = [e for e in echelons if e.completeness >= 40]

    return EchelonResult(echelons=echelons, qualified_count=len(qualified))


def _classify_formation(dist: dict[int, int]) -> str:
    """判断梯队阵型。"""
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


_FORMATION_BASE = {"4321": 80, "321": 55, "21": 25, "scattered": 5}


def _calc_completeness(formation: str, dist: dict[int, int]) -> int:
    """计算梯队完整度评分。"""
    base = _FORMATION_BASE.get(formation, 5)
    bonus = 0

    # 每层多一只 +3
    for h, count in dist.items():
        if count > 1:
            bonus += (count - 1) * 3

    # 高度 >= 5 额外 +5
    if any(h >= 5 for h in dist):
        bonus += 5

    return min(100, base + bonus)


# ─── Step 3: 分歧转一致检测 ───


@dataclass(frozen=True)
class CandidateInfo:
    """候选标的信息。"""

    code: str
    name: str
    signal_type: str  # 分歧转一致 / 梯队确认 / 龙头换手
    board_position: str  # 首板 / 1进2 / 2进3 / 3进4+
    theme_name: str
    confidence: int  # 0-100
    continuous_count: int
    open_count: int
    seal_strength: Optional[str]
    turnover_rate: Optional[float]
    theme_formation: str
    theme_completeness: int
    theme_consecutive_days: int


def detect_candidates(
    gate: GateResult,
    echelons: list,  # list[EchelonInfo]
    limit_ups: Sequence[DailyLimitUp],
    bursts: Sequence[DailyBurst],
) -> list[CandidateInfo]:
    """从合格梯队中检测买入候选。"""
    burst_codes = {b.code for b in bursts}
    candidates = []

    for ech in echelons:
        if ech.completeness < 40:
            continue

        # 找到该题材的涨停股
        theme_limit_ups = [
            lu for lu in limit_ups
            if lu.concept and ech.theme_name in lu.concept
        ]

        # 题材级分歧指标
        theme_divergence_count = 0
        leader_opened = any(
            lu.code == ech.leader_code and lu.open_count > 0
            for lu in theme_limit_ups
        )
        if leader_opened:
            theme_divergence_count += 1

        theme_has_burst = any(lu.code in burst_codes for lu in theme_limit_ups)
        if theme_has_burst:
            theme_divergence_count += 1

        late_seal = any(
            lu.first_seal_time and lu.first_seal_time > "14:00"
            for lu in theme_limit_ups
        )
        if late_seal:
            theme_divergence_count += 1

        seal_weakened = any(
            lu.seal_ratio is not None and lu.seal_ratio < 0.5
            for lu in theme_limit_ups
        )
        if seal_weakened:
            theme_divergence_count += 1

        is_divergent = theme_divergence_count >= 2

        for lu in theme_limit_ups:
            # 个股级确认
            stock_confirmed = lu.open_count > 0 or (lu.turnover_rate or 0) > 8

            # 信号类型
            if is_divergent and stock_confirmed:
                signal_type = "分歧转一致"
            elif not is_divergent and ech.completeness >= 60:
                signal_type = "梯队确认"
            elif lu.code == ech.leader_code and (lu.turnover_rate or 0) > 5:
                signal_type = "龙头换手"
            else:
                continue

            board_pos = _board_position(lu.continuous_count)
            confidence = _calc_confidence(gate, ech, lu, is_divergent)

            candidates.append(CandidateInfo(
                code=lu.code,
                name=lu.name or "",
                signal_type=signal_type,
                board_position=board_pos,
                theme_name=ech.theme_name,
                confidence=confidence,
                continuous_count=lu.continuous_count,
                open_count=lu.open_count,
                seal_strength=_seal_grade(lu.seal_ratio),
                turnover_rate=lu.turnover_rate,
                theme_formation=ech.formation,
                theme_completeness=ech.completeness,
                theme_consecutive_days=ech.consecutive_days,
            ))

    # 去重 (同一只股可能出现在多个题材)
    seen = set()
    unique = []
    for c in sorted(candidates, key=lambda x: x.confidence, reverse=True):
        if c.code not in seen:
            seen.add(c.code)
            unique.append(c)

    return unique


def _board_position(continuous: int) -> str:
    if continuous <= 1:
        return "首板"
    if continuous == 2:
        return "1进2"
    if continuous == 3:
        return "2进3"
    return "3进4+"


def _seal_grade(ratio: Optional[float]) -> Optional[str]:
    if ratio is None:
        return None
    if ratio >= 2.0:
        return "强封"
    if ratio >= 0.5:
        return "中等"
    return "弱封"


def _calc_confidence(
    gate: GateResult,
    ech: EchelonInfo,
    lu: DailyLimitUp,
    is_divergent: bool,
) -> int:
    """计算信号置信度 (0-100)。"""
    # 门控 25 分
    gate_score = {"PASS": 25, "CAUTION": 15, "FAIL": 0}[gate.result]

    # 梯队 30 分
    echelon_score = min(30, int(ech.completeness * 0.3))

    # 个股质量 25 分
    quality = 0
    if lu.seal_ratio is not None and lu.seal_ratio >= 2.0:
        quality += 10
    elif lu.seal_ratio is not None and lu.seal_ratio >= 0.5:
        quality += 5
    if lu.first_seal_time and lu.first_seal_time < "10:00":
        quality += 8
    elif lu.first_seal_time and lu.first_seal_time < "11:30":
        quality += 4
    if lu.turnover_rate and lu.turnover_rate < 15:
        quality += 7
    elif lu.turnover_rate and lu.turnover_rate < 25:
        quality += 3
    quality = min(25, quality)

    # 分歧转一致 20 分
    div_score = 0
    if is_divergent and lu.open_count > 0:
        div_score = 20
    elif is_divergent:
        div_score = 12
    elif ech.consecutive_days >= 3:
        div_score = 8

    return min(100, gate_score + echelon_score + quality + div_score)


# ─── 卖出信号引擎 ───


@dataclass(frozen=True)
class SellInfo:
    """卖出信号信息。"""

    code: str
    name: str
    trigger_type: str  # gate_fail / stock_burst / leader_fall / theme_weaken
    severity: str  # URGENT / WARN
    reason: str
    confidence: int


def detect_sell_signals(
    gate: GateResult,
    positions: Sequence[Position],
    bursts: Sequence[DailyBurst],
    themes: Sequence[DailyTheme],
    limit_ups: Sequence[DailyLimitUp],
) -> list[SellInfo]:
    """检查持仓股的卖出触发条件。"""
    if not positions:
        return []

    burst_codes = {b.code for b in bursts}
    theme_map = {t.concept_name: t for t in themes}
    lu_codes = {lu.code for lu in limit_ups}
    signals = []

    for pos in positions:
        if pos.quantity <= 0:
            continue

        # gate_fail: 门控 FAIL 时所有持仓建议卖出
        if gate.result == "FAIL":
            signals.append(SellInfo(
                code=pos.code, name=pos.name or "",
                trigger_type="gate_fail", severity="URGENT",
                reason=f"生态门控FAIL: {gate.reason}",
                confidence=85,
            ))
            continue  # gate_fail 优先级最高

        # stock_burst: 持仓出现在炸板池
        if pos.code in burst_codes:
            signals.append(SellInfo(
                code=pos.code, name=pos.name or "",
                trigger_type="stock_burst", severity="URGENT",
                reason="持仓股炸板",
                confidence=90,
            ))

        # leader_fall: 所属题材龙头炸板或跌停
        # 需要根据 Position 关联题材 (这里简化为检查所有题材龙头)
        for theme in themes:
            if theme.leader_code and theme.leader_code in burst_codes:
                signals.append(SellInfo(
                    code=pos.code, name=pos.name or "",
                    trigger_type="leader_fall", severity="URGENT",
                    reason=f"题材[{theme.concept_name}]龙头{theme.leader_name}炸板",
                    confidence=75,
                ))
                break

        # theme_weaken: 题材强度显著下降 (没有对应涨停股)
        if pos.code not in lu_codes:
            signals.append(SellInfo(
                code=pos.code, name=pos.name or "",
                trigger_type="theme_weaken", severity="WARN",
                reason="持仓股今日未涨停, 关注题材走弱风险",
                confidence=50,
            ))

    return signals


# ─── 主流程 ───


@dataclass
class SignalOutput:
    """信号引擎完整输出。"""

    trade_date: date
    gate: GateResult
    echelons: list  # list[EchelonInfo]
    candidates: list[CandidateInfo]
    sell_signals: list[SellInfo]


class SignalEngine:
    """三步法信号引擎。"""

    def run(
        self,
        trade_date: date,
        emotion: DailyEmotion,
        limit_ups: Sequence[DailyLimitUp],
        bursts: Sequence[DailyBurst],
        themes: Sequence[DailyTheme],
        positions: Sequence[Position],
    ) -> SignalOutput:
        # Step 1: 门控
        gate = evaluate_gate(emotion)

        # Step 2: 梯队评估 (FAIL 时仍评估, 但不产生买入信号)
        echelon_result = evaluate_echelons(limit_ups, themes)

        # Step 3: 候选检测 (仅 PASS / CAUTION)
        candidates = []
        if gate.result != "FAIL":
            qualified = [e for e in echelon_result.echelons if e.completeness >= 40]
            candidates = detect_candidates(gate, qualified, limit_ups, bursts)

        # 卖出信号
        sell_signals = detect_sell_signals(gate, positions, bursts, themes, limit_ups)

        return SignalOutput(
            trade_date=trade_date,
            gate=gate,
            echelons=echelon_result.echelons,
            candidates=candidates,
            sell_signals=sell_signals,
        )

    def to_daily_signal(self, output: SignalOutput) -> DailySignal:
        """转为 DailySignal ORM 记录。"""
        top = output.echelons[0] if output.echelons else None
        return DailySignal(
            trade_date=output.trade_date,
            gate_result=output.gate.result,
            gate_phase=output.gate.phase,
            gate_score=output.gate.score,
            gate_trend=output.gate.trend,
            gate_max_height=output.gate.max_height,
            gate_reason=output.gate.reason,
            echelon_count=len(output.echelons),
            top_echelon_name=top.theme_name if top else None,
            top_echelon_formation=top.formation if top else None,
            top_echelon_completeness=top.completeness if top else None,
            candidate_count=len(output.candidates),
            has_dragon_tiger_supplement=False,
        )

    def to_candidate_records(
        self, trade_date: date, candidates: list[CandidateInfo],
    ) -> list[SignalCandidate]:
        return [
            SignalCandidate(
                trade_date=trade_date,
                code=c.code,
                name=c.name,
                signal_type=c.signal_type,
                board_position=c.board_position,
                theme_name=c.theme_name,
                confidence=c.confidence,
                continuous_count=c.continuous_count,
                open_count=c.open_count,
                seal_strength=c.seal_strength,
                turnover_rate=c.turnover_rate,
                theme_formation=c.theme_formation,
                theme_completeness=c.theme_completeness,
                theme_consecutive_days=c.theme_consecutive_days,
                source="analysis",
            )
            for c in candidates
        ]

    def to_sell_records(
        self, trade_date: date, sell_signals: list[SellInfo],
    ) -> list[SellSignal]:
        return [
            SellSignal(
                trade_date=trade_date,
                code=s.code,
                name=s.name,
                trigger_type=s.trigger_type,
                severity=s.severity,
                reason=s.reason,
                confidence=s.confidence,
            )
            for s in sell_signals
        ]
