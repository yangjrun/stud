"""信号引擎 API routes."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import parse_date
from src.data.database import get_session
from src.data.models import DailyBurst, DailyLimitUp, DailyTheme
from src.data.repository import (
    BurstRepository,
    EmotionRepository,
    LimitUpRepository,
    ThemeRepository,
)
from src.data.repo_journal import PositionRepository
from src.data.repo_signal import CandidateRepository, SellSignalRepository, SignalRepository
from src.engine.signal import SignalEngine

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
