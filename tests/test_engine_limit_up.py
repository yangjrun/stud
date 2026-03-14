"""Tests for limit-up analysis engine."""

from datetime import date

from src.engine.limit_up import LimitUpEngine

from tests.conftest import make_limit_up


class TestBoardLadder:
    def test_basic_ladder(self):
        engine = LimitUpEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "000001", continuous_count=1),
            make_limit_up(d, "000002", continuous_count=1),
            make_limit_up(d, "000003", continuous_count=2),
            make_limit_up(d, "000004", continuous_count=3),
        ]
        ladder = engine.build_ladder(limit_ups, [], d)

        assert ladder.total_limit_up == 4
        assert ladder.total_burst == 0
        assert ladder.max_height == 3
        assert ladder.board_counts == {1: 2, 2: 1, 3: 1}
        assert ("000004", "测试股") in ladder.max_height_stocks

    def test_empty_input(self):
        engine = LimitUpEngine()
        ladder = engine.build_ladder([], [], date(2025, 10, 1))
        assert ladder.max_height == 0
        assert ladder.total_limit_up == 0


class TestPromotionRates:
    def test_basic_promotion(self):
        engine = LimitUpEngine()
        d = date(2025, 10, 2)
        yesterday = [
            make_limit_up(d, f"Y{i:03d}", continuous_count=1) for i in range(10)
        ] + [
            make_limit_up(d, f"Y2{i:02d}", continuous_count=2) for i in range(4)
        ]
        today = [
            make_limit_up(d, f"T{i:03d}", continuous_count=1) for i in range(8)
        ] + [
            make_limit_up(d, f"T2{i:02d}", continuous_count=2) for i in range(3)
        ] + [
            make_limit_up(d, "T301", continuous_count=3),
        ]

        rates = engine.calc_promotion_rates(yesterday, today, d)

        # 1→2: 今日2板(3只) / 昨日1板(10只) = 0.3
        assert rates.rates["1to2"] == 0.3
        # 2→3: 今日3板(1只) / 昨日2板(4只) = 0.25
        assert rates.rates["2to3"] == 0.25

    def test_no_yesterday_data(self):
        engine = LimitUpEngine()
        d = date(2025, 10, 2)
        rates = engine.calc_promotion_rates([], [make_limit_up(d)], d)
        assert rates.rates == {}


class TestQualityEvaluation:
    def test_strong_seal(self):
        engine = LimitUpEngine()
        lu = make_limit_up(
            date(2025, 10, 1),
            seal_amount=800_000_000,
            amount=200_000_000,
            first_seal_time="09:31:00",
            open_count=0,
            continuous_count=3,
        )
        quality = engine.evaluate_quality(lu)
        assert quality.seal_strength == "强封"
        assert quality.seal_ratio == 4.0
        assert quality.first_seal_grade == "秒封"
        assert quality.score >= 70

    def test_weak_seal(self):
        engine = LimitUpEngine()
        lu = make_limit_up(
            date(2025, 10, 1),
            seal_amount=50_000_000,
            amount=200_000_000,
            first_seal_time="14:30:00",
            open_count=4,
            continuous_count=1,
        )
        quality = engine.evaluate_quality(lu)
        assert quality.seal_strength == "弱封"
        assert quality.first_seal_grade == "尾盘"
        assert quality.score < 40

    def test_evaluate_all_sorted(self):
        engine = LimitUpEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "WEAK", seal_amount=10_000_000, first_seal_time="14:50:00", open_count=5),
            make_limit_up(d, "STRONG", seal_amount=1_000_000_000, first_seal_time="09:30:30", open_count=0),
        ]
        results = engine.evaluate_all(limit_ups)
        assert results[0].code == "STRONG"
        assert results[-1].code == "WEAK"


class TestGroupByConcept:
    def test_grouping(self):
        engine = LimitUpEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "A1", concept="AI"),
            make_limit_up(d, "A2", concept="AI"),
            make_limit_up(d, "R1", concept="机器人"),
        ]
        groups = engine.group_by_concept(limit_ups)
        assert "AI" in groups
        assert len(groups["AI"]) == 2
        assert "机器人" in groups
        assert len(groups["机器人"]) == 1

    def test_multi_concept_stock(self):
        """group_by_concept uses raw concept string as key (no splitting)."""
        engine = LimitUpEngine()
        d = date(2025, 10, 1)
        limit_ups = [
            make_limit_up(d, "M1", concept="AI, 机器人"),
        ]
        groups = engine.group_by_concept(limit_ups)
        # Raw string is the key (splitting is done in _count_limit_ups_by_concept, not here)
        assert "AI, 机器人" in groups
        assert len(groups["AI, 机器人"]) == 1
