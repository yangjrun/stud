"""预测回测引擎: 对历史日期范围批量运行预测并验证准确率。"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, Sequence

from sqlmodel import Session

from src.data.models import DailyLimitUp
from src.data.models_backtest import ForecastBacktestDay, ForecastBacktestRun
from src.data.repository import (
    BurstRepository,
    DragonTigerRepository,
    DragonTigerSeatRepository,
    EmotionRepository,
    LimitUpRepository,
    ThemeRepository,
)
from src.engine.forecast import ForecastEngine, check_accuracy, _next_trading_day
from src.engine.signal import evaluate_echelons


@dataclass(frozen=True)
class BacktestDayResult:
    """单日回测结果。"""

    source_date: date
    target_date: date
    predicted_gate_result: Optional[str] = None
    predicted_gate_phase: Optional[str] = None
    predicted_gate_score: Optional[int] = None
    actual_gate_phase: Optional[str] = None
    gate_accuracy: Optional[int] = None
    buy_candidate_count: int = 0
    hit_count: int = 0
    candidate_hit_rate: Optional[float] = None
    predicted_top_echelon: Optional[str] = None
    strategy_name: Optional[str] = None
    tier_a_count: int = 0
    tier_a_hits: int = 0
    tier_b_count: int = 0
    tier_b_hits: int = 0
    tier_c_count: int = 0
    tier_c_hits: int = 0
    skip_reason: Optional[str] = None


@dataclass
class BacktestSummary:
    """回测汇总结果。"""

    start_date: date
    end_date: date
    total_days: int = 0
    skipped_days: int = 0
    days: list[BacktestDayResult] = field(default_factory=list)
    avg_gate_accuracy: Optional[float] = None
    avg_candidate_hit_rate: Optional[float] = None
    gate_exact_match_rate: Optional[float] = None
    total_buy_candidates: int = 0
    total_hits: int = 0
    avg_tier_a_hit_rate: Optional[float] = None
    avg_tier_b_hit_rate: Optional[float] = None
    avg_tier_c_hit_rate: Optional[float] = None


class ForecastBacktestEngine:
    """预测回测引擎。"""

    def run(self, start_date: date, end_date: date, session: Session) -> BacktestSummary:
        emo_repo = EmotionRepository(session)
        lu_repo = LimitUpRepository(session)
        theme_repo = ThemeRepository(session)
        burst_repo = BurstRepository(session)
        dt_repo = DragonTigerRepository(session)
        dts_repo = DragonTigerSeatRepository(session)

        forecast_engine = ForecastEngine()
        results: list[BacktestDayResult] = []

        current = start_date
        while current <= end_date:
            # 跳过周末
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue

            target = _next_trading_day(current)
            day_result = self._run_single_day(
                current, target,
                emo_repo, lu_repo, theme_repo, burst_repo,
                dt_repo, dts_repo,
                forecast_engine,
            )
            results.append(day_result)
            current += timedelta(days=1)

        return self._build_summary(start_date, end_date, results)

    def _run_single_day(
        self,
        source_date: date,
        target_date: date,
        emo_repo: EmotionRepository,
        lu_repo: LimitUpRepository,
        theme_repo: ThemeRepository,
        burst_repo: BurstRepository,
        dt_repo: DragonTigerRepository,
        dts_repo: DragonTigerSeatRepository,
        forecast_engine: ForecastEngine,
    ) -> BacktestDayResult:
        # 加载源日数据
        emotion = emo_repo.get_by_date(source_date)
        if not emotion:
            return BacktestDayResult(
                source_date=source_date, target_date=target_date,
                skip_reason="无情绪数据",
            )

        limit_ups = lu_repo.get_by_date(source_date)
        if not limit_ups:
            return BacktestDayResult(
                source_date=source_date, target_date=target_date,
                skip_reason="无涨停数据",
            )

        themes = theme_repo.get_by_date(source_date)
        emotion_history = list(emo_repo.get_recent(source_date, limit=20))

        # 龙虎榜
        dragon_tigers = dt_repo.get_by_date(source_date)
        dt_seats_map: dict[str, list] = {}
        for dt in dragon_tigers:
            dt_seats_map[dt.code] = list(
                dts_repo.get_seats_for_stock(source_date, dt.code),
            )

        # 炸板
        bursts = burst_repo.get_by_date(source_date)
        burst_codes = {b.code for b in bursts}

        # 梯队
        echelon_result = evaluate_echelons(limit_ups, themes)

        # 持仓 (回测时不用真实持仓，传空)
        positions: Sequence = []

        # 运行预测
        output = forecast_engine.run(
            trade_date=source_date,
            emotion=emotion,
            emotion_history=emotion_history,
            echelons=echelon_result.echelons,
            limit_ups=limit_ups,
            positions=positions,
            dt_seats_map=dt_seats_map,
            burst_codes=burst_codes,
        )

        # 加载目标日实际数据
        actual_emotion = emo_repo.get_by_date(target_date)
        if not actual_emotion:
            return BacktestDayResult(
                source_date=source_date,
                target_date=target_date,
                predicted_gate_result=output.gate.predicted_result,
                predicted_gate_phase=output.gate.predicted_phase,
                predicted_gate_score=output.gate.predicted_score,
                predicted_top_echelon=(
                    output.echelon_projections[0].theme_name
                    if output.echelon_projections else None
                ),
                strategy_name=output.strategy.strategy_name,
                buy_candidate_count=len(output.buy_candidates),
                skip_reason="目标日期无实际数据",
            )

        actual_phase = actual_emotion.emotion_phase
        actual_limit_ups: Sequence[DailyLimitUp] = lu_repo.get_by_date(target_date)
        actual_codes = {lu.code for lu in actual_limit_ups}

        # 构造临时 ForecastSignal 和 ForecastCandidate 用于 check_accuracy
        fc_signal = forecast_engine.to_forecast_signal(output)
        fc_candidates = forecast_engine.to_forecast_candidates(output)

        gate_acc, cand_rate = check_accuracy(
            fc_signal, actual_phase, actual_codes, fc_candidates,
        )

        buy_cands = [c for c in fc_candidates if c.forecast_type != "sell_warning"]
        hits = sum(1 for c in buy_cands if c.code in actual_codes)

        # 按档位统计命中
        tier_stats: dict[str, list[int]] = {"A": [0, 0], "B": [0, 0], "C": [0, 0]}
        for bc in output.buy_candidates:
            tier = bc.tier or "C"
            if tier in tier_stats:
                tier_stats[tier][0] += 1
                if bc.code in actual_codes:
                    tier_stats[tier][1] += 1

        return BacktestDayResult(
            source_date=source_date,
            target_date=target_date,
            predicted_gate_result=output.gate.predicted_result,
            predicted_gate_phase=output.gate.predicted_phase,
            predicted_gate_score=output.gate.predicted_score,
            actual_gate_phase=actual_phase,
            gate_accuracy=gate_acc,
            buy_candidate_count=len(buy_cands),
            hit_count=hits,
            candidate_hit_rate=cand_rate,
            predicted_top_echelon=(
                output.echelon_projections[0].theme_name
                if output.echelon_projections else None
            ),
            strategy_name=output.strategy.strategy_name,
            tier_a_count=tier_stats["A"][0],
            tier_a_hits=tier_stats["A"][1],
            tier_b_count=tier_stats["B"][0],
            tier_b_hits=tier_stats["B"][1],
            tier_c_count=tier_stats["C"][0],
            tier_c_hits=tier_stats["C"][1],
        )

    def _build_summary(
        self, start_date: date, end_date: date, results: list[BacktestDayResult],
    ) -> BacktestSummary:
        valid = [r for r in results if r.skip_reason is None]
        skipped = len(results) - len(valid)

        gate_scores = [r.gate_accuracy for r in valid if r.gate_accuracy is not None]
        cand_rates = [r.candidate_hit_rate for r in valid if r.candidate_hit_rate is not None]
        exact_matches = sum(1 for g in gate_scores if g == 100)

        total_buy = sum(r.buy_candidate_count for r in valid)
        total_hits = sum(r.hit_count for r in valid)

        # 各档位汇总命中率
        total_a = sum(r.tier_a_count for r in valid)
        hits_a = sum(r.tier_a_hits for r in valid)
        total_b = sum(r.tier_b_count for r in valid)
        hits_b = sum(r.tier_b_hits for r in valid)
        total_c = sum(r.tier_c_count for r in valid)
        hits_c = sum(r.tier_c_hits for r in valid)

        return BacktestSummary(
            start_date=start_date,
            end_date=end_date,
            total_days=len(valid),
            skipped_days=skipped,
            days=results,
            avg_gate_accuracy=(
                round(sum(gate_scores) / len(gate_scores), 1) if gate_scores else None
            ),
            avg_candidate_hit_rate=(
                round(sum(cand_rates) / len(cand_rates), 1) if cand_rates else None
            ),
            gate_exact_match_rate=(
                round(exact_matches / len(gate_scores) * 100, 1) if gate_scores else None
            ),
            total_buy_candidates=total_buy,
            total_hits=total_hits,
            avg_tier_a_hit_rate=round(hits_a / total_a * 100, 1) if total_a else None,
            avg_tier_b_hit_rate=round(hits_b / total_b * 100, 1) if total_b else None,
            avg_tier_c_hit_rate=round(hits_c / total_c * 100, 1) if total_c else None,
        )

    @staticmethod
    def to_run_record(summary: BacktestSummary) -> ForecastBacktestRun:
        return ForecastBacktestRun(
            start_date=summary.start_date,
            end_date=summary.end_date,
            total_days=summary.total_days,
            skipped_days=summary.skipped_days,
            avg_gate_accuracy=summary.avg_gate_accuracy,
            avg_candidate_hit_rate=summary.avg_candidate_hit_rate,
            gate_exact_match_rate=summary.gate_exact_match_rate,
            total_buy_candidates=summary.total_buy_candidates,
            total_hits=summary.total_hits,
            avg_tier_a_hit_rate=summary.avg_tier_a_hit_rate,
            avg_tier_b_hit_rate=summary.avg_tier_b_hit_rate,
            avg_tier_c_hit_rate=summary.avg_tier_c_hit_rate,
        )

    @staticmethod
    def to_day_records(summary: BacktestSummary) -> list[ForecastBacktestDay]:
        return [
            ForecastBacktestDay(
                run_id=0,  # will be set by repository
                source_date=d.source_date,
                target_date=d.target_date,
                predicted_gate_result=d.predicted_gate_result,
                predicted_gate_phase=d.predicted_gate_phase,
                predicted_gate_score=d.predicted_gate_score,
                actual_gate_phase=d.actual_gate_phase,
                gate_accuracy=d.gate_accuracy,
                buy_candidate_count=d.buy_candidate_count,
                hit_count=d.hit_count,
                candidate_hit_rate=d.candidate_hit_rate,
                predicted_top_echelon=d.predicted_top_echelon,
                strategy_name=d.strategy_name,
                tier_a_count=d.tier_a_count,
                tier_a_hits=d.tier_a_hits,
                tier_b_count=d.tier_b_count,
                tier_b_hits=d.tier_b_hits,
                tier_c_count=d.tier_c_count,
                tier_c_hits=d.tier_c_hits,
                skip_reason=d.skip_reason,
            )
            for d in summary.days
        ]
