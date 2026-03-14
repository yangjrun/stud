"""Tests for theme tracking engine."""

from datetime import date

from src.data.models import DailyTheme
from src.engine.theme import ThemeEngine, _calc_theme_strength

from tests.conftest import make_limit_up, make_theme


class TestThemeStrength:
    def test_high_strength(self):
        score = _calc_theme_strength(
            limit_up_count=10,
            total_stocks=50,
            change_pct=5.0,
            leader_continuous=4,
            consecutive_days=5,
            is_new=False,
        )
        assert score >= 60

    def test_zero_limit_ups(self):
        score = _calc_theme_strength(
            limit_up_count=0,
            total_stocks=100,
            change_pct=0.5,
            leader_continuous=0,
            consecutive_days=1,
            is_new=False,
        )
        assert score <= 20

    def test_new_theme_bonus(self):
        base = _calc_theme_strength(5, 100, 2.0, 1, 1, is_new=False)
        with_bonus = _calc_theme_strength(5, 100, 2.0, 1, 1, is_new=True)
        assert with_bonus > base

    def test_capped_at_100(self):
        score = _calc_theme_strength(30, 10, 10.0, 10, 10, is_new=True)
        assert score <= 100


class TestThemeEngine:
    def test_analyze_basic(self):
        engine = ThemeEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "A1", concept="AI", continuous_count=3),
            make_limit_up(d, "A2", concept="AI", continuous_count=1),
            make_limit_up(d, "R1", concept="机器人", continuous_count=2),
        ]
        boards = [
            {"concept_name": "AI", "change_pct": 4.0, "total_stocks": 50},
            {"concept_name": "机器人", "change_pct": 2.0, "total_stocks": 30},
            {"concept_name": "新能源", "change_pct": 0.3, "total_stocks": 80},  # will be filtered (no LU, <1%)
        ]
        summary = engine.analyze_themes(d, limit_ups, boards, [])

        assert summary.trade_date == d
        assert len(summary.themes) >= 2
        # AI should rank higher (more limit ups, higher leader)
        names = [t.concept_name for t in summary.themes]
        assert "AI" in names
        assert "机器人" in names
        assert "新能源" not in names

    def test_consecutive_days_from_yesterday(self):
        engine = ThemeEngine()
        d = date(2025, 10, 2)
        limit_ups = [make_limit_up(d, "A1", concept="AI")]
        boards = [{"concept_name": "AI", "change_pct": 3.0, "total_stocks": 50}]
        yesterday = [make_theme(date(2025, 10, 1), "AI", consecutive_days=3)]

        summary = engine.analyze_themes(d, limit_ups, boards, yesterday)
        ai_theme = next(t for t in summary.themes if t.concept_name == "AI")
        assert ai_theme.consecutive_days == 4
        assert not ai_theme.is_new_theme

    def test_new_theme_detected(self):
        engine = ThemeEngine()
        d = date(2025, 10, 1)
        limit_ups = [make_limit_up(d, "X1", concept="低空经济")]
        boards = [{"concept_name": "低空经济", "change_pct": 5.0, "total_stocks": 20}]

        summary = engine.analyze_themes(d, limit_ups, boards, [])
        theme = summary.themes[0]
        assert theme.is_new_theme
        assert summary.new_theme_count == 1

    def test_to_records(self):
        engine = ThemeEngine()
        d = date(2025, 10, 1)
        limit_ups = [make_limit_up(d, "A1", concept="AI", continuous_count=2)]
        boards = [{"concept_name": "AI", "change_pct": 3.0, "total_stocks": 50}]
        summary = engine.analyze_themes(d, limit_ups, boards, [])
        records = engine.to_records(summary)

        assert len(records) >= 1
        assert isinstance(records[0], DailyTheme)
        assert records[0].concept_name == "AI"

    def test_leader_is_highest_board(self):
        engine = ThemeEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "A1", name="低板", concept="AI", continuous_count=1),
            make_limit_up(d, "A2", name="高板", concept="AI", continuous_count=5),
        ]
        boards = [{"concept_name": "AI", "change_pct": 3.0, "total_stocks": 50}]
        summary = engine.analyze_themes(d, limit_ups, boards, [])
        ai = next(t for t in summary.themes if t.concept_name == "AI")
        assert ai.leader_name == "高板"
        assert ai.leader_continuous == 5
