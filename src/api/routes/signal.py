"""信号引擎 API routes."""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.models import DailyBurst, DailyLimitUp, DailyTheme
from src.data.repository import (
    BurstRepository,
    DragonTigerRepository,
    DragonTigerSeatRepository,
    EmotionRepository,
    LimitUpRepository,
    ThemeRepository,
)
from src.data.repo_journal import PositionRepository
from src.data.repo_forecast import ForecastCandidateRepository, ForecastSignalRepository
from src.data.repo_signal import CandidateRepository, SellSignalRepository, SignalRepository
from src.data.repo_backtest import ForecastBacktestRepository
from src.engine.forecast import ForecastEngine, check_accuracy
from src.engine.forecast_backtest import ForecastBacktestEngine
from src.engine.signal import SignalEngine, evaluate_echelons

router = APIRouter()


@router.get("/today")
def get_signal_today(trade_date: date = Depends(parse_date)):
    """获取完整信号 (gate + echelons + candidates + sell_signals)。"""
    with get_session() as s:
        sig_repo = SignalRepository(s)
        cand_repo = CandidateRepository(s)
        sell_repo = SellSignalRepository(s)

        signal = sig_repo.get_by_date(trade_date)
        if not signal:
            return {"error": "当日无信号数据", "trade_date": str(trade_date)}

        candidates = cand_repo.get_by_date(trade_date)
        sell_signals = sell_repo.get_by_date(trade_date)

        return {
            "trade_date": str(trade_date),
            "gate": {
                "result": signal.gate_result,
                "phase": signal.gate_phase,
                "score": signal.gate_score,
                "trend": signal.gate_trend,
                "max_height": signal.gate_max_height,
                "reason": signal.gate_reason,
            },
            "echelons": {
                "count": signal.echelon_count,
                "top_name": signal.top_echelon_name,
                "top_formation": signal.top_echelon_formation,
                "top_completeness": signal.top_echelon_completeness,
            },
            "candidates": [
                {
                    "code": c.code,
                    "name": c.name,
                    "signal_type": c.signal_type,
                    "board_position": c.board_position,
                    "theme_name": c.theme_name,
                    "confidence": c.confidence,
                    "continuous_count": c.continuous_count,
                    "open_count": c.open_count,
                    "seal_strength": c.seal_strength,
                    "turnover_rate": c.turnover_rate,
                    "theme_formation": c.theme_formation,
                    "theme_completeness": c.theme_completeness,
                    "has_known_player": c.has_known_player,
                    "player_names": c.player_names,
                    "source": c.source,
                }
                for c in candidates
            ],
            "sell_signals": [
                {
                    "code": ss.code,
                    "name": ss.name,
                    "trigger_type": ss.trigger_type,
                    "severity": ss.severity,
                    "reason": ss.reason,
                    "confidence": ss.confidence,
                }
                for ss in sell_signals
            ],
            "candidate_count": signal.candidate_count,
            "has_dragon_tiger_supplement": signal.has_dragon_tiger_supplement,
        }


@router.get("/gate")
def get_gate(trade_date: date = Depends(parse_date)):
    """仅门控状态。"""
    with get_session() as s:
        signal = SignalRepository(s).get_by_date(trade_date)
        if not signal:
            return {"error": "当日无信号数据", "trade_date": str(trade_date)}
        return {
            "trade_date": str(trade_date),
            "result": signal.gate_result,
            "phase": signal.gate_phase,
            "score": signal.gate_score,
            "trend": signal.gate_trend,
            "max_height": signal.gate_max_height,
            "reason": signal.gate_reason,
        }


@router.get("/echelons")
def get_echelons(trade_date: date = Depends(parse_date)):
    """题材梯队。"""
    with get_session() as s:
        signal = SignalRepository(s).get_by_date(trade_date)
        if not signal:
            return {"error": "当日无信号数据", "trade_date": str(trade_date)}
        return {
            "trade_date": str(trade_date),
            "count": signal.echelon_count,
            "top_name": signal.top_echelon_name,
            "top_formation": signal.top_echelon_formation,
            "top_completeness": signal.top_echelon_completeness,
        }


@router.get("/candidates")
def get_candidates(trade_date: date = Depends(parse_date)):
    """买入候选。"""
    with get_session() as s:
        candidates = CandidateRepository(s).get_by_date(trade_date)
        return {
            "trade_date": str(trade_date),
            "count": len(candidates),
            "data": [
                {
                    "code": c.code,
                    "name": c.name,
                    "signal_type": c.signal_type,
                    "board_position": c.board_position,
                    "theme_name": c.theme_name,
                    "confidence": c.confidence,
                    "continuous_count": c.continuous_count,
                    "open_count": c.open_count,
                    "seal_strength": c.seal_strength,
                    "turnover_rate": c.turnover_rate,
                    "theme_formation": c.theme_formation,
                    "theme_completeness": c.theme_completeness,
                    "has_known_player": c.has_known_player,
                    "player_names": c.player_names,
                    "source": c.source,
                }
                for c in candidates
            ],
        }


@router.get("/sell")
def get_sell_signals(trade_date: date = Depends(parse_date)):
    """卖出信号。"""
    with get_session() as s:
        signals = SellSignalRepository(s).get_by_date(trade_date)
        return {
            "trade_date": str(trade_date),
            "count": len(signals),
            "data": [
                {
                    "code": ss.code,
                    "name": ss.name,
                    "trigger_type": ss.trigger_type,
                    "severity": ss.severity,
                    "reason": ss.reason,
                    "confidence": ss.confidence,
                }
                for ss in signals
            ],
        }


@router.get("/history")
def get_signal_history(days: int = Query(30, ge=1, le=180)):
    """历史信号。"""
    with get_session() as s:
        history = SignalRepository(s).get_history(days)
        return {
            "count": len(history),
            "data": [
                {
                    "trade_date": str(h.trade_date),
                    "gate_result": h.gate_result,
                    "gate_phase": h.gate_phase,
                    "gate_score": h.gate_score,
                    "candidate_count": h.candidate_count,
                    "top_echelon_name": h.top_echelon_name,
                    "top_echelon_formation": h.top_echelon_formation,
                }
                for h in history
            ],
        }


@router.post("/run")
def run_signals(trade_date: date = Depends(parse_date)):
    """手动触发信号生成。"""
    with get_session() as s:
        emo_repo = EmotionRepository(s)
        emotion = emo_repo.get_by_date(trade_date)
        if not emotion:
            return {"error": "当日无情绪数据, 请先运行分析", "trade_date": str(trade_date)}

        lu_repo = LimitUpRepository(s)
        burst_repo = BurstRepository(s)
        theme_repo = ThemeRepository(s)
        pos_repo = PositionRepository(s)
        sig_repo = SignalRepository(s)
        cand_repo = CandidateRepository(s)
        sell_repo = SellSignalRepository(s)

        limit_ups = lu_repo.get_by_date(trade_date)
        bursts = burst_repo.get_by_date(trade_date)
        themes = theme_repo.get_by_date(trade_date)
        positions = pos_repo.get_all_open()

        engine = SignalEngine()
        output = engine.run(trade_date, emotion, limit_ups, bursts, themes, positions)

        # 持久化
        sig_repo.upsert(engine.to_daily_signal(output))
        for rec in engine.to_candidate_records(trade_date, output.candidates):
            cand_repo.upsert(rec)
        for rec in engine.to_sell_records(trade_date, output.sell_signals):
            sell_repo.upsert(rec)
        s.commit()

        return {
            "trade_date": str(trade_date),
            "gate_result": output.gate.result,
            "candidate_count": len(output.candidates),
            "sell_signal_count": len(output.sell_signals),
            "message": "信号生成完成",
        }


# ─── 明日预测 ───


@router.get("/forecast")
def get_forecast(trade_date: date = Depends(parse_date)):
    """获取明日预测 (source_date = trade_date)。"""
    with get_session() as s:
        fc_repo = ForecastSignalRepository(s)
        fc_cand_repo = ForecastCandidateRepository(s)

        forecast = fc_repo.get_by_source_date(trade_date)
        if not forecast:
            return {"error": "当日无预测数据", "trade_date": str(trade_date)}

        candidates = fc_cand_repo.get_by_date(forecast.trade_date)
        buy_list = [c for c in candidates if c.forecast_type != "sell_warning"]
        sell_list = [c for c in candidates if c.forecast_type == "sell_warning"]

        # 重新计算门控因子和策略 (含强弱分级)
        emo_repo = EmotionRepository(s)
        emotion = emo_repo.get_by_date(forecast.source_date)
        factors = {}
        intensity = "normal"

        if emotion:
            history = list(emo_repo.get_recent(forecast.source_date, limit=20))
            from src.engine.forecast import (
                GateForecast,
                _calc_multi_factor_trend,
                _determine_emotion_strategy,
            )
            _, factors = _calc_multi_factor_trend(emotion, history)
            gate_for_strategy = GateForecast(
                predicted_phase=forecast.predicted_gate_phase or "震荡",
                predicted_score=forecast.predicted_gate_score or 0,
                predicted_result=forecast.predicted_gate_result,
                transition=forecast.phase_transition or "",
                confidence=forecast.phase_transition_confidence or 0,
                rationale="",
                factors=factors,
            )
            strategy_ctx = _determine_emotion_strategy(gate_for_strategy, emotion)
            intensity = strategy_ctx.intensity
        else:
            from src.engine.forecast import (
                GateForecast,
                _determine_emotion_strategy,
            )
            gate_for_strategy = GateForecast(
                predicted_phase=forecast.predicted_gate_phase or "震荡",
                predicted_score=forecast.predicted_gate_score or 0,
                predicted_result=forecast.predicted_gate_result,
                transition=forecast.phase_transition or "",
                confidence=forecast.phase_transition_confidence or 0,
                rationale="",
            )
            strategy_ctx = _determine_emotion_strategy(gate_for_strategy)

        # 龙虎榜标记
        dt_repo = DragonTigerRepository(s)
        dts_repo = DragonTigerSeatRepository(s)
        dragon_tigers = dt_repo.get_by_date(forecast.source_date)
        dt_codes = {dt.code for dt in dragon_tigers}
        dt_known_map: dict[str, bool] = {}
        for dt in dragon_tigers:
            seats = dts_repo.get_seats_for_stock(forecast.source_date, dt.code)
            dt_known_map[dt.code] = any(
                s.is_known_player and s.direction == "BUY" for s in seats
            )

        return {
            "source_date": str(forecast.source_date),
            "target_date": str(forecast.trade_date),
            "gate": {
                "predicted_result": forecast.predicted_gate_result,
                "predicted_phase": forecast.predicted_gate_phase,
                "predicted_score": forecast.predicted_gate_score,
                "phase_transition": forecast.phase_transition,
                "transition_confidence": forecast.phase_transition_confidence,
                "factors": factors,
            },
            "echelons": {
                "count": forecast.predicted_echelon_count,
                "top_name": forecast.predicted_top_echelon_name,
                "continuation_score": forecast.echelon_continuation_score,
            },
            "strategy": {
                "name": strategy_ctx.strategy_name,
                "phase": strategy_ctx.phase,
                "intensity": strategy_ctx.intensity,
                "summary": strategy_ctx.summary,
                "allow_roles": list(strategy_ctx.allow_roles),
            },
            "buy_candidates": [
                {
                    "code": c.code,
                    "name": c.name,
                    "forecast_type": c.forecast_type,
                    "predicted_board": c.predicted_board_position,
                    "theme_name": c.theme_name,
                    "confidence": c.confidence,
                    "today_continuous": c.today_continuous_count,
                    "predicted_continuous": c.predicted_continuous_count,
                    "historical_rate": c.historical_promotion_rate,
                    "theme_formation": c.theme_formation,
                    "theme_completeness": c.theme_completeness,
                    "rationale": c.rationale,
                    "market_role": c.market_role,
                    "tier": c.tier,
                    "has_dragon_tiger": c.code in dt_codes,
                    "has_known_player": dt_known_map.get(c.code, False),
                }
                for c in buy_list
            ],
            "sell_warnings": [
                {
                    "code": c.code,
                    "name": c.name,
                    "confidence": c.confidence,
                    "reason": c.rationale,
                }
                for c in sell_list
            ],
            "accuracy": {
                "gate": forecast.accuracy_gate,
                "candidates": forecast.accuracy_candidates,
            },
        }


@router.post("/forecast/run")
def run_forecast(trade_date: date = Depends(parse_date)):
    """手动触发明日预测生成。"""
    with get_session() as s:
        emo_repo = EmotionRepository(s)
        emotion = emo_repo.get_by_date(trade_date)
        if not emotion:
            return {"error": "当日无情绪数据, 请先运行分析", "trade_date": str(trade_date)}

        # 需要今日信号已生成
        sig_repo = SignalRepository(s)
        signal = sig_repo.get_by_date(trade_date)
        if not signal:
            return {"error": "当日信号未生成, 请先运行信号引擎", "trade_date": str(trade_date)}

        lu_repo = LimitUpRepository(s)
        theme_repo = ThemeRepository(s)
        pos_repo = PositionRepository(s)

        limit_ups = lu_repo.get_by_date(trade_date)
        themes = theme_repo.get_by_date(trade_date)
        positions = pos_repo.get_all_open()
        emotion_history = list(emo_repo.get_recent(trade_date, limit=20))

        # 龙虎榜数据
        dt_repo = DragonTigerRepository(s)
        dts_repo = DragonTigerSeatRepository(s)
        dragon_tigers = dt_repo.get_by_date(trade_date)
        dt_seats_map: dict[str, list] = {}
        for dt in dragon_tigers:
            dt_seats_map[dt.code] = list(
                dts_repo.get_seats_for_stock(trade_date, dt.code),
            )

        # 炸板数据
        burst_repo = BurstRepository(s)
        bursts = burst_repo.get_by_date(trade_date)
        burst_codes = {b.code for b in bursts}

        # 重建梯队信息
        echelon_result = evaluate_echelons(limit_ups, themes)

        # 运行预测引擎
        engine = ForecastEngine()
        output = engine.run(
            trade_date=trade_date,
            emotion=emotion,
            emotion_history=emotion_history,
            echelons=echelon_result.echelons,
            limit_ups=limit_ups,
            positions=positions,
            dt_seats_map=dt_seats_map,
            burst_codes=burst_codes,
        )

        # 持久化
        fc_repo = ForecastSignalRepository(s)
        fc_cand_repo = ForecastCandidateRepository(s)

        fc_repo.upsert(engine.to_forecast_signal(output))
        for rec in engine.to_forecast_candidates(output):
            fc_cand_repo.upsert(rec)

        # 检查昨日预测准确率
        _update_yesterday_accuracy(s, trade_date)

        s.commit()

        return {
            "source_date": str(trade_date),
            "target_date": str(output.target_date),
            "predicted_gate": output.gate.predicted_result,
            "predicted_phase": output.gate.predicted_phase,
            "factors": output.gate.factors,
            "strategy": {
                "name": output.strategy.strategy_name,
                "phase": output.strategy.phase,
                "intensity": output.strategy.intensity,
                "summary": output.strategy.summary,
                "allow_roles": list(output.strategy.allow_roles),
            },
            "buy_candidate_count": len(output.buy_candidates),
            "sell_forecast_count": len(output.sell_forecasts),
            "message": "预测生成完成",
        }


@router.get("/forecast/accuracy")
def get_forecast_accuracy(days: int = Query(30, ge=1, le=180)):
    """获取预测准确率历史。"""
    with get_session() as s:
        fc_repo = ForecastSignalRepository(s)
        history = fc_repo.get_history(days)

        records = [
            {
                "source_date": str(h.source_date),
                "target_date": str(h.trade_date),
                "predicted_phase": h.predicted_gate_phase,
                "predicted_result": h.predicted_gate_result,
                "accuracy_gate": h.accuracy_gate,
                "accuracy_candidates": h.accuracy_candidates,
                "buy_count": h.buy_candidate_count,
                "sell_count": h.sell_candidate_count,
            }
            for h in history
        ]

        # 计算总体准确率
        gate_scores = [r["accuracy_gate"] for r in records if r["accuracy_gate"] is not None]
        cand_scores = [r["accuracy_candidates"] for r in records if r["accuracy_candidates"] is not None]

        return {
            "count": len(records),
            "avg_gate_accuracy": round(sum(gate_scores) / len(gate_scores), 1) if gate_scores else None,
            "avg_candidate_hit_rate": round(sum(cand_scores) / len(cand_scores), 1) if cand_scores else None,
            "data": records,
        }


def _update_yesterday_accuracy(s, today: date) -> None:
    """检查是否有针对今天的预测, 如有则更新准确率。"""
    fc_repo = ForecastSignalRepository(s)
    fc_cand_repo = ForecastCandidateRepository(s)
    emo_repo = EmotionRepository(s)
    lu_repo = LimitUpRepository(s)

    forecast = fc_repo.get_by_date(today)
    if not forecast or forecast.accuracy_gate is not None:
        return  # 没有预测或已经更新过

    emotion = emo_repo.get_by_date(today)
    actual_phase = emotion.emotion_phase if emotion else None

    limit_ups = lu_repo.get_by_date(today)
    actual_codes = {lu.code for lu in limit_ups}

    candidates = fc_cand_repo.get_by_date(today)

    gate_acc, cand_rate = check_accuracy(forecast, actual_phase, actual_codes, candidates)
    fc_repo.update_accuracy(today, gate_acc, cand_rate)

    # 更新每个候选的实际结果
    for c in candidates:
        if c.forecast_type == "sell_warning":
            continue
        result = "hit" if c.code in actual_codes else "miss"
        fc_cand_repo.update_actual_result(today, c.code, result)


# ─── 预测回测 ───


@router.post("/backtest/run")
def run_backtest(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """运行预测回测。"""
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(400, "日期格式错误, 请使用 YYYY-MM-DD")

    if sd > ed:
        raise HTTPException(400, "开始日期不能晚于结束日期")
    # 计算交易日数 (排除周末)
    trading_days = sum(
        1 for i in range((ed - sd).days + 1)
        if (sd + timedelta(days=i)).weekday() < 5
    )
    if trading_days > 30:
        raise HTTPException(400, "交易日数不能超过30天")

    with get_session() as s:
        engine = ForecastBacktestEngine()
        summary = engine.run(sd, ed, s)

        # 持久化
        bt_repo = ForecastBacktestRepository(s)
        run_record = engine.to_run_record(summary)
        day_records = engine.to_day_records(summary)
        bt_repo.save(run_record, day_records)
        s.commit()

        return {
            "id": run_record.id,
            "start_date": str(summary.start_date),
            "end_date": str(summary.end_date),
            "total_days": summary.total_days,
            "skipped_days": summary.skipped_days,
            "avg_gate_accuracy": summary.avg_gate_accuracy,
            "avg_candidate_hit_rate": summary.avg_candidate_hit_rate,
            "gate_exact_match_rate": summary.gate_exact_match_rate,
            "total_buy_candidates": summary.total_buy_candidates,
            "total_hits": summary.total_hits,
            "avg_tier_a_hit_rate": summary.avg_tier_a_hit_rate,
            "avg_tier_b_hit_rate": summary.avg_tier_b_hit_rate,
            "avg_tier_c_hit_rate": summary.avg_tier_c_hit_rate,
            "days": [
                {
                    "source_date": str(d.source_date),
                    "target_date": str(d.target_date),
                    "predicted_gate_result": d.predicted_gate_result,
                    "predicted_gate_phase": d.predicted_gate_phase,
                    "predicted_gate_score": d.predicted_gate_score,
                    "actual_gate_phase": d.actual_gate_phase,
                    "gate_accuracy": d.gate_accuracy,
                    "buy_candidate_count": d.buy_candidate_count,
                    "hit_count": d.hit_count,
                    "candidate_hit_rate": d.candidate_hit_rate,
                    "predicted_top_echelon": d.predicted_top_echelon,
                    "strategy_name": d.strategy_name,
                    "tier_a_count": d.tier_a_count,
                    "tier_a_hits": d.tier_a_hits,
                    "tier_b_count": d.tier_b_count,
                    "tier_b_hits": d.tier_b_hits,
                    "tier_c_count": d.tier_c_count,
                    "tier_c_hits": d.tier_c_hits,
                    "skip_reason": d.skip_reason,
                }
                for d in summary.days
            ],
        }


@router.get("/backtest/history")
def get_backtest_history(limit: int = Query(10, ge=1, le=50)):
    """获取回测历史记录。"""
    with get_session() as s:
        bt_repo = ForecastBacktestRepository(s)
        runs = bt_repo.get_recent(limit)
        return {
            "count": len(runs),
            "data": [
                {
                    "id": r.id,
                    "start_date": str(r.start_date),
                    "end_date": str(r.end_date),
                    "total_days": r.total_days,
                    "skipped_days": r.skipped_days,
                    "avg_gate_accuracy": r.avg_gate_accuracy,
                    "avg_candidate_hit_rate": r.avg_candidate_hit_rate,
                    "gate_exact_match_rate": r.gate_exact_match_rate,
                    "total_buy_candidates": r.total_buy_candidates,
                    "total_hits": r.total_hits,
                    "avg_tier_a_hit_rate": r.avg_tier_a_hit_rate,
                    "avg_tier_b_hit_rate": r.avg_tier_b_hit_rate,
                    "avg_tier_c_hit_rate": r.avg_tier_c_hit_rate,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in runs
            ],
        }


@router.get("/backtest/{run_id}")
def get_backtest_detail(run_id: int):
    """获取回测运行明细。"""
    with get_session() as s:
        bt_repo = ForecastBacktestRepository(s)
        run = bt_repo.get_by_id(run_id)
        if not run:
            raise HTTPException(404, "回测记录不存在")

        days = bt_repo.get_days(run_id)
        return {
            "id": run.id,
            "start_date": str(run.start_date),
            "end_date": str(run.end_date),
            "total_days": run.total_days,
            "skipped_days": run.skipped_days,
            "avg_gate_accuracy": run.avg_gate_accuracy,
            "avg_candidate_hit_rate": run.avg_candidate_hit_rate,
            "gate_exact_match_rate": run.gate_exact_match_rate,
            "total_buy_candidates": run.total_buy_candidates,
            "total_hits": run.total_hits,
            "avg_tier_a_hit_rate": run.avg_tier_a_hit_rate,
            "avg_tier_b_hit_rate": run.avg_tier_b_hit_rate,
            "avg_tier_c_hit_rate": run.avg_tier_c_hit_rate,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "days": [
                {
                    "source_date": str(d.source_date),
                    "target_date": str(d.target_date),
                    "predicted_gate_result": d.predicted_gate_result,
                    "predicted_gate_phase": d.predicted_gate_phase,
                    "predicted_gate_score": d.predicted_gate_score,
                    "actual_gate_phase": d.actual_gate_phase,
                    "gate_accuracy": d.gate_accuracy,
                    "buy_candidate_count": d.buy_candidate_count,
                    "hit_count": d.hit_count,
                    "candidate_hit_rate": d.candidate_hit_rate,
                    "predicted_top_echelon": d.predicted_top_echelon,
                    "strategy_name": d.strategy_name,
                    "tier_a_count": d.tier_a_count,
                    "tier_a_hits": d.tier_a_hits,
                    "tier_b_count": d.tier_b_count,
                    "tier_b_hits": d.tier_b_hits,
                    "tier_c_count": d.tier_c_count,
                    "tier_c_hits": d.tier_c_hits,
                    "skip_reason": d.skip_reason,
                }
                for d in days
            ],
        }
