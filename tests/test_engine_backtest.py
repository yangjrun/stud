"""Tests for backtest engine."""

from datetime import date, timedelta

from src.engine.backtest import BacktestEngine

from tests.conftest import make_emotion


def _build_cycle_records(n: int = 30) -> list:
    """构造 N 天循环情绪数据。"""
    phases = ["冰点", "修复", "发酵", "高潮", "分歧", "退潮"]
    premiums = [-2.0, 0.5, 1.5, 3.0, 0.0, -1.5]
    scores = [15, 30, 50, 80, 55, 25]
    records = []
    base = date(2025, 7, 1)
    for i in range(n):
        idx = i % 6
        records.append(make_emotion(
            base + timedelta(days=i),
            emotion_phase=phases[idx],
            emotion_score=scores[idx],
            yesterday_premium_avg=premiums[idx],
        ))
    return records


class TestBacktestEngine:
    def test_run_returns_all_phases(self):
        engine = BacktestEngine()
        records = _build_cycle_records(36)
        result = engine.run(records)

        assert result.total_days == 36
        for phase in ("冰点", "修复", "发酵", "高潮", "分歧", "退潮"):
            assert phase in result.phase_stats
            assert result.phase_stats[phase].sample_count == 6

    def test_empty_records(self):
        engine = BacktestEngine()
        result = engine.run([])
        assert result.total_days == 0
        for ps in result.phase_stats.values():
            assert ps.sample_count == 0
            assert ps.avg_next1_premium is None

    def test_single_phase(self):
        engine = BacktestEngine()
        records = _build_cycle_records(18)
        ps = engine.run_single_phase(records, "冰点")

        assert ps.phase == "冰点"
        assert ps.sample_count == 3
        # 冰点 at index 0,6,12 → next day premium is premiums[1]=0.5
        assert ps.avg_next1_premium == 0.5
        assert ps.win_rate_next1 == 1.0  # 0.5 > 0

    def test_climax_premium(self):
        engine = BacktestEngine()
        records = _build_cycle_records(18)
        ps = engine.run_single_phase(records, "高潮")

        # 高潮 at index 3,9,15 → next day premium is premiums[4]=0.0
        assert ps.avg_next1_premium == 0.0
        assert ps.win_rate_next1 == 0.0  # 0.0 not > 0

    def test_conclusion_contains_phases(self):
        engine = BacktestEngine()
        records = _build_cycle_records(36)
        result = engine.run(records)
        assert "冰点" in result.conclusion
        assert "高潮" in result.conclusion

    def test_details_limited_to_50(self):
        engine = BacktestEngine()
        # 300 days, ~50 occurrences per phase
        records = _build_cycle_records(300)
        result = engine.run(records)
        for ps in result.phase_stats.values():
            assert len(ps.details) <= 50

    def test_details_reverse_chronological(self):
        engine = BacktestEngine()
        records = _build_cycle_records(36)
        result = engine.run(records)
        ps = result.phase_stats["冰点"]
        if len(ps.details) >= 2:
            assert ps.details[0]["trade_date"] > ps.details[1]["trade_date"]

    def test_score_change_3d(self):
        engine = BacktestEngine()
        records = _build_cycle_records(18)
        ps = engine.run_single_phase(records, "冰点")
        # 冰点 score=15, 3 days later score=scores[3]=80 → change=65
        assert ps.avg_score_change_3d == 65.0
