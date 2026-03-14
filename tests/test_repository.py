"""Tests for repository layer."""

from datetime import date, timedelta

import pytest
from sqlmodel import Session

from src.data.models import (
    DailyEmotion,
    DailyLimitUp,
    DailyTheme,
    KnownPlayer,
    Watchlist,
    RecapTemplate,
)
from src.data.repository import (
    EmotionRepository,
    KnownPlayerRepository,
    LimitUpRepository,
    ThemeRepository,
    WatchlistRepository,
    RecapTemplateRepository,
)

from tests.conftest import make_emotion, make_limit_up, make_theme


class TestEmotionRepository:
    def test_upsert_insert(self, session):
        repo = EmotionRepository(session)
        record = make_emotion(date(2025, 10, 1))
        repo.upsert(record)
        session.commit()

        result = repo.get_by_date(date(2025, 10, 1))
        assert result is not None
        assert result.limit_up_count_real == 50

    def test_upsert_update(self, session):
        repo = EmotionRepository(session)
        repo.upsert(make_emotion(date(2025, 10, 1), limit_up_count_real=50))
        session.commit()

        repo.upsert(make_emotion(date(2025, 10, 1), limit_up_count_real=80))
        session.commit()

        result = repo.get_by_date(date(2025, 10, 1))
        assert result.limit_up_count_real == 80

    def test_get_recent(self, session):
        repo = EmotionRepository(session)
        base = date(2025, 10, 10)
        for i in range(5):
            repo.upsert(make_emotion(base - timedelta(days=i)))
        session.commit()

        recent = repo.get_recent(base, limit=3)
        assert len(recent) == 3

    def test_get_range(self, session):
        repo = EmotionRepository(session)
        base = date(2025, 10, 1)
        for i in range(10):
            repo.upsert(make_emotion(base + timedelta(days=i)))
        session.commit()

        result = list(repo.get_range(base + timedelta(days=2), base + timedelta(days=7)))
        assert len(result) == 6
        # Should be ascending
        assert result[0].trade_date < result[-1].trade_date


class TestLimitUpRepository:
    def test_upsert_and_get(self, session):
        repo = LimitUpRepository(session)
        repo.upsert(make_limit_up(date(2025, 10, 1), "000001"))
        repo.upsert(make_limit_up(date(2025, 10, 1), "000002"))
        session.commit()

        results = repo.get_by_date(date(2025, 10, 1))
        assert len(results) == 2

    def test_get_by_date_empty(self, session):
        repo = LimitUpRepository(session)
        assert len(repo.get_by_date(date(2025, 1, 1))) == 0


class TestThemeRepository:
    def test_get_theme_on_date(self, session):
        repo = ThemeRepository(session)
        t = make_theme(date(2025, 10, 1), "AI")
        repo.upsert(t)
        session.commit()

        result = repo.get_theme_on_date("AI", date(2025, 10, 1))
        assert result is not None
        assert result.concept_name == "AI"

    def test_get_theme_on_date_not_found(self, session):
        repo = ThemeRepository(session)
        result = repo.get_theme_on_date("不存在", date(2025, 10, 1))
        assert result is None

    def test_search_by_keyword(self, session):
        repo = ThemeRepository(session)
        base = date(2025, 10, 1)
        repo.upsert(make_theme(base, "人工智能"))
        repo.upsert(make_theme(base, "机器人"))
        repo.upsert(make_theme(base, "人工智能芯片"))
        session.commit()

        results = repo.search_by_keyword("人工", base - timedelta(days=1), base + timedelta(days=1))
        assert len(results) == 2
        names = {r.concept_name for r in results}
        assert "人工智能" in names
        assert "人工智能芯片" in names

    def test_theme_history(self, session):
        repo = ThemeRepository(session)
        for i in range(5):
            repo.upsert(make_theme(date(2025, 10, 1) + timedelta(days=i), "AI"))
        session.commit()

        history = repo.get_theme_history("AI", limit=10)
        assert len(history) == 5


class TestKnownPlayerRepository:
    def test_crud(self, session):
        repo = KnownPlayerRepository(session)
        player = KnownPlayer(seat_name="华泰证券上海武定路", player_alias="佛山无影脚", style="打板")
        repo.upsert(player)
        session.commit()

        all_players = repo.get_all()
        assert len(all_players) == 1

        # Update
        updated = KnownPlayer(seat_name="华泰证券上海武定路", player_alias="佛山无影脚2", style="低吸")
        repo.upsert(updated)
        session.commit()

        result = repo.get_all_active()
        assert len(result) == 1
        assert result[0].player_alias == "佛山无影脚2"

    def test_match_seat(self, session):
        repo = KnownPlayerRepository(session)
        repo.upsert(KnownPlayer(seat_name="华泰证券上海武定路", player_alias="佛山无影脚"))
        session.commit()

        assert repo.match_seat("华泰证券上海武定路证券营业部") is not None
        assert repo.match_seat("完全不相关的名字") is None

    def test_delete(self, session):
        repo = KnownPlayerRepository(session)
        p = KnownPlayer(seat_name="测试席位", player_alias="测试")
        repo.upsert(p)
        session.commit()

        player = repo.get_all()[0]
        assert repo.delete(player.id)
        session.commit()
        assert len(repo.get_all()) == 0

    def test_delete_nonexistent(self, session):
        repo = KnownPlayerRepository(session)
        assert not repo.delete(9999)


class TestWatchlistRepository:
    def test_add_and_list(self, session):
        repo = WatchlistRepository(session)
        repo.add(Watchlist(code="000001", name="平安银行"))
        repo.add(Watchlist(code="000002", name="万科A"))
        session.commit()

        items = repo.get_all()
        assert len(items) == 2

    def test_add_duplicate_updates(self, session):
        repo = WatchlistRepository(session)
        repo.add(Watchlist(code="000001", name="平安银行", reason="测试"))
        session.commit()
        repo.add(Watchlist(code="000001", name="平安银行", reason="更新原因"))
        session.commit()

        items = repo.get_all()
        assert len(items) == 1
        assert items[0].reason == "更新原因"

    def test_delete(self, session):
        repo = WatchlistRepository(session)
        repo.add(Watchlist(code="000001"))
        session.commit()

        assert repo.delete("000001")
        session.commit()
        assert len(repo.get_all()) == 0

    def test_get_codes(self, session):
        repo = WatchlistRepository(session)
        repo.add(Watchlist(code="000001"))
        repo.add(Watchlist(code="000002"))
        session.commit()

        codes = repo.get_codes()
        assert set(codes) == {"000001", "000002"}


class TestRecapTemplateRepository:
    def test_crud(self, session):
        repo = RecapTemplateRepository(session)
        t = RecapTemplate(name="默认", sections='["emotion","theme"]', is_default=True)
        repo.upsert(t)
        session.commit()

        assert len(repo.get_all()) == 1
        assert repo.get_default().name == "默认"

    def test_delete(self, session):
        repo = RecapTemplateRepository(session)
        repo.upsert(RecapTemplate(name="临时", sections='["emotion"]'))
        session.commit()

        assert repo.delete("临时")
        session.commit()
        assert len(repo.get_all()) == 0

    def test_delete_nonexistent(self, session):
        repo = RecapTemplateRepository(session)
        assert not repo.delete("不存在")
