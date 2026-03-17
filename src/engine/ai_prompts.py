"""Prompt 模板层: 将原始市场数据组装为结构化 prompt 供 AI 分析。"""

from typing import Sequence

from src.data.models import DailyEmotion, DailyLimitUp
from src.data.models_journal import Position
from src.engine.signal import EchelonInfo

SYSTEM_PROMPT = """\
你是A股超短线情绪周期分析师，专注于涨停板生态和情绪周期研判。

## 你的任务
根据提供的当日市场数据，预测明日走势并给出结构化分析结果。

## 情绪周期阶段定义（7个阶段）
- **冰点**: 市场极度低迷，涨停数极少，炸板率高，无主线题材。评分通常 0-20。
- **修复**: 从冰点回暖，涨停数回升，开始出现领涨题材。评分通常 20-40。
- **发酵**: 主线明确，梯队成型，赚钱效应扩散。评分通常 40-60。
- **高潮**: 涨停潮，多题材共振，龙头高位加速。评分通常 60-85。
- **分歧**: 高潮后分化，龙头分歧，部分跟风崩塌。评分通常 35-55。
- **退潮**: 赚钱效应消退，高位股补跌，连板梯队断裂。评分通常 15-35。
- **震荡**: 多空均衡，无明确方向，题材轮动快。评分通常 30-50。

## 策略类型（5种）
- **进攻型**: 发酵/高潮期，龙头二龙三龙均可参与
- **试探型**: 修复期，仅龙头和强势二龙
- **防守型**: 分歧期，仅关注龙头换手转一致
- **观望型**: 震荡期，仅最强龙头极低仓位
- **空仓**: 冰点/退潮期，不推荐任何买入

## 门控结果规则
- PASS: 发酵/高潮期，或修复期评分>=35
- FAIL: 冰点/退潮期
- CAUTION: 分歧/震荡期，或修复期评分<35

## 买入候选评估规则
- **tier**: A(高确定性) / B(中等) / C(低确定性)
- **market_role**: 龙头(题材最强) / 二龙(第二强) / 三龙(第三) / 跟风(其余)
- **forecast_type**: promotion(晋级) / continuation(延续) / new_leader(新龙头)
- 只能从今日涨停板数据中选择候选，不得编造不存在的股票代码
- 门控 FAIL 时不应有买入候选

## 卖出预警规则
- **URGENT**: 门控 FAIL 或个股有重大利空
- **WARN**: 题材龙头疲劳、梯队断裂等

## 一致性约束
- 如果 predicted_gate_result 是 FAIL，strategy_name 必须是 空仓
- 如果 predicted_gate_result 是 FAIL，buy_candidates 应为空列表
- predicted_score 和 predicted_phase 应匹配：冰点<30, 修复 20-45, 发酵 35-65, 高潮 55-90, 分歧 30-55, 退潮 10-35, 震荡 25-50
- gate_confidence 表示你对门控判断的确信度，0-100

你必须严格按照要求的 JSON 格式返回结果，不要添加任何额外文字。\
"""


def build_forecast_prompt(
    emotion: DailyEmotion,
    emotion_history: Sequence[DailyEmotion],
    echelons: list[EchelonInfo],
    limit_ups: Sequence[DailyLimitUp],
    positions: Sequence[Position],
    dt_seats_map: dict[str, list] | None = None,
    burst_codes: set[str] | None = None,
) -> tuple[str, str]:
    """构建 system prompt 和 user prompt。"""
    sections: list[str] = []

    # ── 当日情绪快照 ──
    sections.append(_format_emotion_snapshot(emotion))

    # ── 近期情绪历史 ──
    sections.append(_format_emotion_history(emotion_history))

    # ── 涨停梯队分布 ──
    sections.append(_format_echelons(echelons))

    # ── 今日涨停板详情 ──
    sections.append(_format_limit_ups(limit_ups, dt_seats_map, burst_codes))

    # ── 持仓列表 ──
    sections.append(_format_positions(positions))

    user_prompt = "\n\n".join(s for s in sections if s)
    user_prompt += "\n\n请根据以上数据，预测明日走势并按 JSON Schema 返回结构化结果。"

    return SYSTEM_PROMPT, user_prompt


def _format_emotion_snapshot(emotion: DailyEmotion) -> str:
    """格式化当日情绪快照。"""
    lines = [
        f"## 当日情绪快照 ({emotion.trade_date})",
        f"- 情绪阶段: {emotion.emotion_phase or '未知'}",
        f"- 情绪评分: {emotion.emotion_score or 0}/100",
        f"- 涨停数: {emotion.limit_up_count} (实际: {emotion.limit_up_count_real})",
        f"- 跌停数: {emotion.limit_down_count}",
        f"- 炸板数: {emotion.burst_count}",
        f"- 封板成功率: {_pct(emotion.seal_success_rate)}",
        f"- 涨跌比: {emotion.advance_count}:{emotion.decline_count}"
        f" (比值: {_fmt(emotion.advance_decline_ratio)})",
        f"- 最高连板: {emotion.max_continuous}板"
        f" ({emotion.max_continuous_name or emotion.max_continuous_code or ''})",
        f"- 昨日溢价: 均{_fmt(emotion.yesterday_premium_avg)}%"
        f" 高{_fmt(emotion.yesterday_premium_high)}%"
        f" 低{_fmt(emotion.yesterday_premium_low)}%",
        f"- 成交额: {_fmt_amount(emotion.total_amount)}",
        "",
        "板块分布:",
        f"  首板: {emotion.board_1_count}",
        f"  2板: {emotion.board_2_count}",
        f"  3板: {emotion.board_3_count}",
        f"  4板: {emotion.board_4_count}",
        f"  5板+: {emotion.board_5_plus_count}",
        "",
        "晋级率:",
        f"  1进2: {_pct(emotion.promote_1to2_rate)}",
        f"  2进3: {_pct(emotion.promote_2to3_rate)}",
        f"  3进4: {_pct(emotion.promote_3to4_rate)}",
    ]
    return "\n".join(lines)


def _format_emotion_history(history: Sequence[DailyEmotion]) -> str:
    """格式化近期情绪历史。"""
    recent = sorted(
        [e for e in history if e.emotion_score is not None],
        key=lambda x: x.trade_date,
    )[-10:]

    if not recent:
        return "## 近期情绪历史\n无数据"

    lines = ["## 近期情绪历史 (近10日)"]
    for e in recent:
        lines.append(
            f"- {e.trade_date}: {e.emotion_phase or '?'}"
            f" 评分{e.emotion_score}"
            f" 涨停{e.limit_up_count} 炸板{e.burst_count}"
            f" 最高{e.max_continuous}板"
            f" 溢价{_fmt(e.yesterday_premium_avg)}%"
        )
    return "\n".join(lines)


def _format_echelons(echelons: list[EchelonInfo]) -> str:
    """格式化题材梯队信息。"""
    if not echelons:
        return "## 题材梯队\n无活跃梯队"

    lines = ["## 题材梯队"]
    for ech in echelons:
        dist_str = " ".join(f"{h}板:{c}只" for h, c in sorted(ech.board_distribution.items()))
        lines.append(
            f"### {ech.theme_name}"
            f" (阵型:{ech.formation} 完整度:{ech.completeness}%"
            f" 连续{ech.consecutive_days}天)"
        )
        lines.append(f"  龙头: {ech.leader_name or ech.leader_code or '未知'}"
                      f" {ech.leader_continuous}连板")
        lines.append(f"  涨停数: {ech.limit_up_count}")
        lines.append(f"  分布: {dist_str}")
    return "\n".join(lines)


def _format_limit_ups(
    limit_ups: Sequence[DailyLimitUp],
    dt_seats_map: dict[str, list] | None,
    burst_codes: set[str] | None,
) -> str:
    """格式化今日涨停板详情。"""
    if not limit_ups:
        return "## 今日涨停板\n无涨停"

    lines = ["## 今日涨停板"]

    # 按连板数降序排列
    sorted_ups = sorted(limit_ups, key=lambda x: (-x.continuous_count, x.code))

    for lu in sorted_ups:
        is_burst = burst_codes and lu.code in burst_codes
        burst_tag = " [炸板]" if is_burst else ""

        dt_info = ""
        if dt_seats_map and lu.code in dt_seats_map:
            seats = dt_seats_map[lu.code]
            buy_known = [
                s for s in seats
                if getattr(s, "direction", "") == "BUY"
                and getattr(s, "is_known_player", False)
            ]
            if buy_known:
                names = [getattr(s, "player_name", "游资") or "游资" for s in buy_known]
                dt_info = f" [龙虎榜: {','.join(names)}]"
            elif seats:
                dt_info = " [有龙虎榜]"

        lines.append(
            f"- {lu.code} {lu.name or ''}"
            f" | {lu.continuous_count}连板"
            f" | 封单比:{_fmt(lu.seal_ratio)}"
            f" | 换手:{_pct(lu.turnover_rate)}"
            f" | 成交:{_fmt_amount(lu.amount)}"
            f" | 首封:{lu.first_seal_time or '?'}"
            f" | 开板:{lu.open_count}次"
            f" | 题材:{lu.concept or '无'}"
            f"{burst_tag}{dt_info}"
        )
    return "\n".join(lines)


def _format_positions(positions: Sequence[Position]) -> str:
    """格式化持仓列表。"""
    active = [p for p in positions if p.quantity > 0]
    if not active:
        return "## 当前持仓\n无持仓"

    lines = ["## 当前持仓"]
    for p in active:
        lines.append(
            f"- {p.code} {p.name or ''}"
            f" | 数量:{p.quantity}"
            f" | 成本:{p.avg_cost:.2f}"
            f" | 买入日:{p.first_buy_date or '?'}"
        )
    return "\n".join(lines)


# ── 格式化辅助 ──

def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "N/A"


def _pct(v: float | None) -> str:
    return f"{v:.1f}%" if v is not None else "N/A"


def _fmt_amount(v: float | None) -> str:
    if v is None:
        return "N/A"
    if v >= 1e8:
        return f"{v / 1e8:.1f}亿"
    if v >= 1e4:
        return f"{v / 1e4:.0f}万"
    return f"{v:.0f}"
