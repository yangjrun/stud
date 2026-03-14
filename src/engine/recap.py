"""每日复盘生成器: 综合所有引擎输出，生成结构化复盘报告。"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.data.models import DailyRecap
from src.engine.dragon_tiger import DragonTigerSummary
from src.engine.emotion import EmotionSnapshot
from src.engine.limit_up import BoardLadder, PromotionRates
from src.engine.theme import ThemeSummary


@dataclass(frozen=True)
class RecapReport:
    """完整的每日复盘报告。"""

    trade_date: date
    text: str  # 完整文本
    emotion_summary: str
    theme_summary: str
    dragon_tiger_summary: str
    tomorrow_strategy: str


class RecapEngine:
    """每日复盘报告生成器。"""

    def generate(
        self,
        trade_date: date,
        emotion: Optional[EmotionSnapshot],
        ladder: Optional[BoardLadder],
        promotion: Optional[PromotionRates],
        theme_summary: Optional[ThemeSummary],
        dt_summary: Optional[DragonTigerSummary],
    ) -> RecapReport:
        emotion_text = _build_emotion_section(emotion, ladder, promotion)
        ladder_text = _build_ladder_section(ladder, promotion)
        theme_text = _build_theme_section(theme_summary)
        dt_text = _build_dragon_tiger_section(dt_summary)
        strategy_text = _build_strategy(emotion, ladder, theme_summary)

        full_text = f"""{'═' * 40}
{trade_date.strftime('%Y-%m-%d')} 复盘
{'═' * 40}

{emotion_text}

{ladder_text}

{theme_text}

{dt_text}

{strategy_text}
"""
        return RecapReport(
            trade_date=trade_date,
            text=full_text,
            emotion_summary=emotion_text,
            theme_summary=theme_text,
            dragon_tiger_summary=dt_text,
            tomorrow_strategy=strategy_text,
        )

    def to_record(self, report: RecapReport) -> DailyRecap:
        return DailyRecap(
            trade_date=report.trade_date,
            emotion_summary=report.emotion_summary,
            theme_summary=report.theme_summary,
            dragon_tiger_summary=report.dragon_tiger_summary,
            tomorrow_strategy=report.tomorrow_strategy,
        )


# ─── 各段落生成 ───


def _build_emotion_section(
    emotion: Optional[EmotionSnapshot],
    ladder: Optional[BoardLadder],
    promotion: Optional[PromotionRates],
) -> str:
    if emotion is None:
        return "【情绪】数据暂无"

    arrow = {1: "↑", -1: "↓", 0: "→"}.get(emotion.trend_direction, "")
    lines = [
        f"【情绪】{emotion.phase} (评分: {emotion.score}/100) {arrow}  "
        f"已持续 {emotion.phase_days} 天",
    ]

    if ladder:
        seal_rate = ""
        if ladder.total_limit_up + ladder.total_burst > 0:
            rate = ladder.total_limit_up / (ladder.total_limit_up + ladder.total_burst) * 100
            seal_rate = f"封板率 {rate:.0f}%"
        lines.append(
            f"涨停 {ladder.total_limit_up} 家 | 炸板 {ladder.total_burst} 家 | {seal_rate}"
        )

    if ladder and ladder.max_height > 0:
        names = ", ".join(f"{n}({c})" for c, n in ladder.max_height_stocks[:3])
        lines.append(f"最高连板: {ladder.max_height} 板 → {names}")

    sub = " | ".join(f"{k}:{v}" for k, v in emotion.sub_scores.items())
    lines.append(f"分项: {sub}")

    return "\n".join(lines)


def _build_ladder_section(
    ladder: Optional[BoardLadder],
    promotion: Optional[PromotionRates],
) -> str:
    if ladder is None:
        return "【连板梯队】数据暂无"

    lines = ["【连板梯队】"]

    # 从高到低显示
    parts = []
    for height in sorted(ladder.board_counts.keys(), reverse=True):
        count = ladder.board_counts[height]
        parts.append(f"{height}板: {count}只")
    lines.append("  " + " | ".join(parts))

    if promotion:
        rate_parts = []
        for key, val in sorted(promotion.rates.items()):
            if val is not None:
                rate_parts.append(f"{key.replace('to', '→')}: {val:.0%}")
        if rate_parts:
            lines.append(f"  晋级率: {' | '.join(rate_parts)}")

    return "\n".join(lines)


def _build_theme_section(summary: Optional[ThemeSummary]) -> str:
    if summary is None or not summary.themes:
        return "【题材主线】数据暂无"

    lines = [f"【题材主线】活跃题材 {summary.active_theme_count} 个, 新题材 {summary.new_theme_count} 个"]

    for i, t in enumerate(summary.themes[:8], 1):
        leader = ""
        if t.leader_name:
            leader = f" 龙头: {t.leader_name}"
            if t.leader_continuous > 1:
                leader += f"({t.leader_continuous}板)"

        tag = " [新!]" if t.is_new_theme else ""
        days = f" 持续{t.consecutive_days}天" if t.consecutive_days > 1 else ""

        lines.append(
            f"  {i}. {t.concept_name} (涨停{t.limit_up_count}只{days}){leader}{tag}"
        )

    return "\n".join(lines)


def _build_dragon_tiger_section(summary: Optional[DragonTigerSummary]) -> str:
    if summary is None or not summary.stocks:
        return "【龙虎榜】数据暂无 (盘后发布, 约18:30更新)"

    lines = [f"【龙虎榜】上榜 {len(summary.stocks)} 只"]

    # 知名游资动向
    if summary.player_activities:
        lines.append("  游资动向:")
        shown = set()
        for act in summary.player_activities[:10]:
            key = (act.player_alias, act.code, act.direction)
            if key in shown:
                continue
            shown.add(key)
            action = "买入" if act.direction == "BUY" else "卖出"
            amt = act.amount / 1e4  # 万元
            lines.append(f"    · {act.player_alias} {action} {act.name}({act.code}) {amt:.0f}万")

    # 净买入 Top5
    by_net = sorted(summary.stocks, key=lambda s: s.net_amount, reverse=True)
    top_buy = [s for s in by_net[:5] if s.net_amount > 0]
    if top_buy:
        lines.append("  净买入 Top:")
        for s in top_buy:
            amt = s.net_amount / 1e4
            lines.append(f"    · {s.name}({s.code}) +{amt:.0f}万")

    return "\n".join(lines)


def _build_strategy(
    emotion: Optional[EmotionSnapshot],
    ladder: Optional[BoardLadder],
    theme: Optional[ThemeSummary],
) -> str:
    lines = ["【明日关注】"]

    if emotion:
        phase_advice = {
            "冰点": "极端低迷, 留意修复信号, 轻仓或观望",
            "修复": "情绪回暖中, 可关注率先走强的方向, 试探性参与",
            "发酵": "赚钱效应扩散, 可适度参与主线题材",
            "高潮": "情绪亢奋, 注意控制仓位, 高位股谨慎追涨",
            "分歧": "多空分歧加大, 关注分歧后是否能回封, 减少操作",
            "退潮": "亏钱效应扩大, 以防守为主, 等待情绪企稳",
            "震荡": "方向不明, 轻仓观望为主",
        }
        advice = phase_advice.get(emotion.phase, "")
        lines.append(f"  · 情绪 {emotion.phase} ({emotion.score}分): {advice}")

    if ladder and ladder.max_height >= 3:
        names = ", ".join(n for _, n in ladder.max_height_stocks[:2])
        lines.append(f"  · {ladder.max_height}板 {names} 能否晋级, 决定市场高度")

    if theme and theme.themes:
        top = theme.themes[0]
        lines.append(f"  · 关注 {top.concept_name} 方向是否持续发酵")
        if theme.new_theme_count > 0:
            new_names = [t.concept_name for t in theme.themes if t.is_new_theme][:3]
            lines.append(f"  · 新题材: {', '.join(new_names)}, 观察持续性")

    return "\n".join(lines)
