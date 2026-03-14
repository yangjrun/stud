"""Tests for emotion engine."""

from datetime import date, timedelta

import pytest

from src.engine.emotion import EmotionEngine, _classify_phase, _score_limit_up_count

from tests.conftest import make_emotion


class TestScoreLimitUpCount:
    def test_extreme_low(self):
        assert _score_limit_up_count(5) == 2

    def test_low(self):
        assert _score_limit_up_count(25) == 6

    def test_mid(self):
        assert _score_limit_up_count(50) == 14

    def test_high(self):
        assert _score_limit_up_count(80) == 22

    def test_extreme_high(self):
        assert _score_limit_up_count(120) == 25


class TestClassifyPhase:
    def test_freezing(self):
        assert _classify_phase(15, 0) == "冰点"

    def test_recovery(self):
        assert _classify_phase(30, 1) == "修复"

    def test_ferment(self):
        assert _classify_phase(50, 1) == "发酵"

    def test_climax(self):
        assert _classify_phase(85, 1) == "高潮"

    def test_divergence(self):
        assert _classify_phase(55, -1) == "分歧"

    def test_retreat(self):
        assert _classify_phase(35, -1) == "退潮"

    def test_oscillation(self):
        assert _classify_phase(50, 0) == "震荡"


class TestEmotionEngine:
    def test_analyze_returns_snapshot(self):
        engine = EmotionEngine()
        base = date(2025, 10, 1)
        today = make_emotion(base, limit_up_count_real=60, seal_success_rate=75.0, max_continuous=4, yesterday_premium_avg=2.0)
        history = [
            make_emotion(base - timedelta(days=i), emotion_score=50 + i)
            for i in range(1, 6)
        ]

        snap = engine.analyze(today, history)

        assert snap.trade_date == base
        assert 0 <= snap.score <= 100
        assert snap.phase in ("冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡")
        assert snap.trend_direction in (-1, 0, 1)
        assert snap.phase_days >= 1
        assert len(snap.sub_scores) == 4

    def test_score_clamped_to_100(self):
        engine = EmotionEngine()
        base = date(2025, 10, 1)
        today = make_emotion(base, limit_up_count_real=200, seal_success_rate=95.0, max_continuous=10, yesterday_premium_avg=10.0)
        snap = engine.analyze(today, [])
        assert snap.score <= 100

    def test_score_clamped_to_0(self):
        engine = EmotionEngine()
        base = date(2025, 10, 1)
        today = make_emotion(base, limit_up_count_real=0, seal_success_rate=0.0, max_continuous=0, yesterday_premium_avg=-10.0)
        snap = engine.analyze(today, [])
        assert snap.score >= 0

    def test_build_emotion_record(self):
        engine = EmotionEngine()
        record = engine.build_emotion_record(
            trade_date=date(2025, 10, 1),
            limit_up_count=55,
            limit_up_count_real=50,
            limit_down_count=10,
            burst_count=8,
            advance_count=2000,
            decline_count=1500,
            max_continuous=3,
            max_continuous_code="000001",
            max_continuous_name="测试",
            yesterday_premium_avg=1.5,
            yesterday_premium_high=5.0,
            yesterday_premium_low=-2.0,
            total_amount=1e12,
            board_counts={1: 40, 2: 8, 3: 2},
            promotion_rates={"1to2": 0.2, "2to3": 0.25},
        )
        assert record.limit_up_count == 55
        assert record.board_1_count == 40
        assert record.promote_1to2_rate == 0.2
        # seal_success_rate = 55/(55+8)*100
        assert record.seal_success_rate == pytest.approx(87.30, abs=0.1)
