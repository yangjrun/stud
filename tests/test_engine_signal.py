"""信号引擎单元测试。"""

from datetime import date

import pytest

from src.data.models import DailyBurst, DailyEmotion, DailyLimitUp, DailyTheme
from src.data.models_journal import Position
from src.engine.signal import (
    CandidateInfo,
    EchelonInfo,
    GateResult,
    SellInfo,
    SignalEngine,
    _board_position,
    _calc_completeness,
    _calc_confidence,
    _classify_formation,
    _seal_grade,
    detect_candidates,
    detect_sell_signals,
    evaluate_echelons,
    evaluate_gate,
)

TODAY = date(2026, 3, 13)


def _make_emotion(
    phase: str = "发酵",
    score: int = 60,
    max_continuous: int = 5,
    promote_1to2_rate: float = 30.0,
) -> DailyEmotion:
    return DailyEmotion(
        trade_date=TODAY,
        limit_up_count=50,
        limit_up_count_real=45,
        limit_down_count=3,
        burst_count=5,
        seal_success_rate=85.0,
        max_continuous=max_continuous,
        emotion_phase=phase,
        emotion_score=score,
        promote_1to2_rate=promote_1to2_rate,
    )


def _make_limit_up(
    code: str = "000001",
    name: str = "测试A",
    continuous: int = 1,
    concept: str = "人工智能",
    open_count: int = 0,
    seal_ratio: float = 1.5,
    turnover_rate: float = 10.0,
    first_seal_time: str = "09:35",
) -> DailyLimitUp:
    return DailyLimitUp(
        trade_date=TODAY,
        code=code,
        name=name,
        continuous_count=continuous,
        concept=concept,
        open_count=open_count,
        seal_ratio=seal_ratio,
        turnover_rate=turnover_rate,
        first_seal_time=first_seal_time,
    )


def _make_theme(
    name: str = "人工智能",
    limit_up_count: int = 5,
    leader_code: str = "000001",
    leader_name: str = "测试A",
    leader_continuous: int = 3,
    consecutive_days: int = 3,
) -> DailyTheme:
    return DailyTheme(
        trade_date=TODAY,
        concept_name=name,
        limit_up_count=limit_up_count,
        leader_code=leader_code,
        leader_name=leader_name,
        leader_continuous=leader_continuous,
        consecutive_days=consecutive_days,
    )


# ─── Gate Tests ───


class TestGate:
    def test_fail_on_ice(self):
        emo = _make_emotion(phase="冰点", score=15)
        result = evaluate_gate(emo)
        assert result.result == "FAIL"

    def test_fail_on_retreat(self):
        emo = _make_emotion(phase="退潮", score=30)
        result = evaluate_gate(emo)
        assert result.result == "FAIL"

    def test_fail_low_height_low_score(self):
        emo = _make_emotion(phase="震荡", score=25, max_continuous=2)
        result = evaluate_gate(emo)
        assert result.result == "FAIL"

    def test_pass_on_ferment(self):
        emo = _make_emotion(phase="发酵", score=55)
        result = evaluate_gate(emo)
        assert result.result == "PASS"

    def test_pass_on_climax(self):
        emo = _make_emotion(phase="高潮", score=80)
        result = evaluate_gate(emo)
        assert result.result == "PASS"

    def test_pass_on_repair(self):
        emo = _make_emotion(phase="修复", score=40)
        result = evaluate_gate(emo)
        assert result.result == "PASS"

    def test_caution_divergence_high(self):
        emo = _make_emotion(phase="分歧", score=50, max_continuous=5)
        result = evaluate_gate(emo)
        assert result.result == "CAUTION"

    def test_caution_oscillation(self):
        emo = _make_emotion(phase="震荡", score=45, max_continuous=3, promote_1to2_rate=25.0)
        result = evaluate_gate(emo)
        assert result.result == "CAUTION"


# ─── Formation Tests ───


class TestFormation:
    def test_4321(self):
        assert _classify_formation({4: 1, 3: 2, 2: 3, 1: 10}) == "4321"

    def test_321(self):
        assert _classify_formation({3: 1, 2: 2, 1: 5}) == "321"

    def test_21(self):
        assert _classify_formation({2: 3, 1: 8}) == "21"

    def test_scattered(self):
        assert _classify_formation({1: 5}) == "scattered"

    def test_empty(self):
        assert _classify_formation({}) == "scattered"


class TestCompleteness:
    def test_4321_base(self):
        score = _calc_completeness("4321", {4: 1, 3: 1, 2: 1, 1: 1})
        assert score == 80  # base only, no bonus

    def test_4321_with_bonus(self):
        score = _calc_completeness("4321", {5: 1, 4: 1, 3: 2, 2: 3, 1: 5})
        # base=80, layer bonus: 3×(3-1)+2×(2-1)+4×(1-1) = 6+3+0 =9 actually:
        # heights: 5(1), 4(1), 3(2), 2(3), 1(5)
        # bonus per layer: 5→0, 4→0, 3→3, 2→6, 1→12 = 21
        # height>=5 bonus: +5
        # total: 80+21+5 = 106 → capped at 100
        assert score == 100

    def test_scattered_low(self):
        score = _calc_completeness("scattered", {1: 3})
        # base=5, bonus=6
        assert score == 11


# ─── Helper Tests ───


class TestHelpers:
    def test_board_position(self):
        assert _board_position(1) == "首板"
        assert _board_position(2) == "1进2"
        assert _board_position(3) == "2进3"
        assert _board_position(5) == "3进4+"

    def test_seal_grade(self):
        assert _seal_grade(None) is None
        assert _seal_grade(3.0) == "强封"
        assert _seal_grade(1.0) == "中等"
        assert _seal_grade(0.2) == "弱封"


# ─── Echelon Tests ───


class TestEchelons:
    def test_basic_echelon(self):
        theme = _make_theme(name="人工智能", limit_up_count=5, leader_continuous=3)
        lus = [
            _make_limit_up(code="000001", continuous=3, concept="人工智能"),
            _make_limit_up(code="000002", name="测试B", continuous=2, concept="人工智能"),
            _make_limit_up(code="000003", name="测试C", continuous=1, concept="人工智能"),
        ]
        result = evaluate_echelons(lus, [theme])
        assert len(result.echelons) >= 1
        ech = result.echelons[0]
        assert ech.theme_name == "人工智能"
        assert ech.formation == "321"
        assert ech.completeness >= 55


# ─── Sell Signal Tests ───


class TestSellSignals:
    def test_gate_fail_urgent(self):
        gate = GateResult(result="FAIL", phase="冰点", score=15, trend=-1, max_height=1, reason="冰点")
        pos = [Position(code="000001", name="测试", quantity=1000)]
        signals = detect_sell_signals(gate, pos, [], [], [])
        assert len(signals) == 1
        assert signals[0].trigger_type == "gate_fail"
        assert signals[0].severity == "URGENT"

    def test_stock_burst(self):
        gate = GateResult(result="PASS", phase="发酵", score=60, trend=1, max_height=5, reason="ok")
        pos = [Position(code="000001", name="测试", quantity=1000)]
        bursts = [DailyBurst(trade_date=TODAY, code="000001", name="测试")]
        signals = detect_sell_signals(gate, pos, bursts, [], [])
        assert any(s.trigger_type == "stock_burst" for s in signals)

    def test_no_signals_for_empty_positions(self):
        gate = GateResult(result="PASS", phase="发酵", score=60, trend=1, max_height=5, reason="ok")
        signals = detect_sell_signals(gate, [], [], [], [])
        assert len(signals) == 0


# ─── Confidence Tests ───


class TestConfidence:
    def test_high_confidence(self):
        gate = GateResult(result="PASS", phase="发酵", score=60, trend=1, max_height=5, reason="ok")
        ech = EchelonInfo(
            theme_name="AI", formation="4321", completeness=90,
            board_distribution={4: 1, 3: 2, 2: 3, 1: 5},
            leader_code="000001", leader_name="测试", leader_continuous=4,
            limit_up_count=11, consecutive_days=4,
        )
        lu = _make_limit_up(seal_ratio=3.0, first_seal_time="09:30", turnover_rate=8.0, open_count=1)
        score = _calc_confidence(gate, ech, lu, is_divergent=True)
        # gate=25, echelon=27, quality=25, divergence=20
        assert score >= 70

    def test_low_confidence_caution(self):
        gate = GateResult(result="CAUTION", phase="震荡", score=45, trend=0, max_height=3, reason="ok")
        ech = EchelonInfo(
            theme_name="X", formation="21", completeness=45,
            board_distribution={2: 1, 1: 3},
            leader_code="000002", leader_name="测试B", leader_continuous=2,
            limit_up_count=4, consecutive_days=1,
        )
        lu = _make_limit_up(seal_ratio=0.3, first_seal_time="14:30", turnover_rate=20.0)
        score = _calc_confidence(gate, ech, lu, is_divergent=False)
        assert score < 50


# ─── Full Pipeline Tests ───


class TestSignalEngine:
    def test_full_pipeline_pass(self):
        engine = SignalEngine()
        emotion = _make_emotion(phase="发酵", score=60, max_continuous=5)
        lus = [
            _make_limit_up(code="000001", continuous=3, concept="人工智能", open_count=1),
            _make_limit_up(code="000002", name="测试B", continuous=2, concept="人工智能"),
            _make_limit_up(code="000003", name="测试C", continuous=1, concept="人工智能"),
        ]
        themes = [_make_theme(name="人工智能", limit_up_count=3, leader_continuous=3)]
        bursts = []
        positions = []

        output = engine.run(TODAY, emotion, lus, bursts, themes, positions)
        assert output.gate.result == "PASS"
        assert len(output.echelons) >= 1

    def test_full_pipeline_fail_no_candidates(self):
        engine = SignalEngine()
        emotion = _make_emotion(phase="冰点", score=15, max_continuous=1)
        lus = [_make_limit_up(code="000001", continuous=1, concept="人工智能")]
        themes = [_make_theme(name="人工智能", limit_up_count=1)]

        output = engine.run(TODAY, emotion, lus, [], themes, [])
        assert output.gate.result == "FAIL"
        assert len(output.candidates) == 0

    def test_to_daily_signal(self):
        engine = SignalEngine()
        emotion = _make_emotion(phase="发酵", score=60)
        output = engine.run(TODAY, emotion, [], [], [], [])
        record = engine.to_daily_signal(output)
        assert record.trade_date == TODAY
        assert record.gate_result == "PASS"
