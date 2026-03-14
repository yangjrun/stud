"""Tests for API routes (using FastAPI TestClient).

Patches get_session at the module level in each route to use an in-memory SQLite.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from src.data.models import KnownPlayer

from tests.conftest import make_emotion, make_theme

# ─── Test engine ───
# StaticPool reuses the same connection so in-memory tables are shared across threads

_test_engine = create_engine(
    "sqlite://",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def _get_test_session():
    return Session(_test_engine)


# Build a minimal test app without lifespan/scheduler
# Patch get_session in EVERY route module at module-level
_ROUTE_MODULES = [
    "src.api.routes.emotion",
    "src.api.routes.limit_up",
    "src.api.routes.theme",
    "src.api.routes.dragon_tiger",
    "src.api.routes.recap",
    "src.api.routes.backtest",
    "src.api.routes.watchlist",
    "src.api.routes.players",
    "src.api.routes.export",
]


# ─── Fixtures ───


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.create_all(_test_engine)
    yield
    SQLModel.metadata.drop_all(_test_engine)


@pytest.fixture()
def client():
    """TestClient with get_session patched in all route modules."""
    from src.api.routes.backtest import router as backtest_router
    from src.api.routes.dragon_tiger import router as dt_router
    from src.api.routes.emotion import router as emotion_router
    from src.api.routes.export import router as export_router
    from src.api.routes.limit_up import router as lu_router
    from src.api.routes.players import router as players_router
    from src.api.routes.recap import router as recap_router
    from src.api.routes.theme import router as theme_router
    from src.api.routes.watchlist import router as watchlist_router

    app = FastAPI()
    app.include_router(emotion_router, prefix="/api/emotion")
    app.include_router(lu_router, prefix="/api/limit-up")
    app.include_router(theme_router, prefix="/api/themes")
    app.include_router(dt_router, prefix="/api/dragon-tiger")
    app.include_router(recap_router, prefix="/api/recap")
    app.include_router(backtest_router, prefix="/api/backtest")
    app.include_router(watchlist_router, prefix="/api/watchlist")
    app.include_router(players_router, prefix="/api/players")
    app.include_router(export_router, prefix="/api/export")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    patches = [
        patch(f"{mod}.get_session", _get_test_session)
        for mod in _ROUTE_MODULES
    ]
    for p in patches:
        p.start()

    yield TestClient(app)

    for p in patches:
        p.stop()


@pytest.fixture()
def db():
    with Session(_test_engine) as s:
        yield s


# ─── Tests ───


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestEmotionAPI:
    def test_today_no_data(self, client):
        resp = client.get("/api/emotion/today")
        data = resp.json()
        assert "error" in data

    def test_today_with_data(self, client, db):
        today = date.today()
        db.add(make_emotion(today, emotion_phase="发酵", emotion_score=55))
        db.commit()

        resp = client.get("/api/emotion/today")
        data = resp.json()
        assert data["score"] >= 0
        assert data["phase"] in ("冰点", "修复", "发酵", "高潮", "分歧", "退潮", "震荡")

    def test_history(self, client, db):
        base = date.today()
        for i in range(5):
            db.add(make_emotion(base - timedelta(days=i)))
        db.commit()

        resp = client.get("/api/emotion/history", params={"days": 10})
        data = resp.json()
        assert data["count"] >= 4


class TestThemeAPI:
    def test_today_empty(self, client):
        resp = client.get("/api/themes/today")
        data = resp.json()
        assert data["total"] == 0

    def test_keyword_filter(self, client, db):
        today = date.today()
        db.add(make_theme(today, "人工智能"))
        db.add(make_theme(today, "机器人"))
        db.add(make_theme(today, "人工智能芯片"))
        db.commit()

        resp = client.get("/api/themes/today", params={"keyword": "人工"})
        data = resp.json()
        assert data["total"] == 2
        assert data["keyword"] == "人工"

    def test_leader_endpoint(self, client, db):
        today = date.today()
        db.add(make_theme(today, "AI", leader_code="000001", leader_name="龙头"))
        db.commit()

        resp = client.get("/api/themes/AI/leader")
        data = resp.json()
        assert data["leader_name"] == "龙头"
        assert data["leader_code"] == "000001"

    def test_leader_not_found(self, client):
        resp = client.get("/api/themes/不存在/leader")
        data = resp.json()
        assert "error" in data

    def test_search(self, client, db):
        today = date.today()
        db.add(make_theme(today, "低空经济"))
        db.add(make_theme(today, "高空探测"))
        db.commit()

        resp = client.get("/api/themes/search", params={"keyword": "空"})
        data = resp.json()
        assert data["count"] == 2


class TestWatchlistAPI:
    def test_add_and_list(self, client):
        resp = client.post("/api/watchlist/", json={"code": "000001", "name": "平安银行"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "added"

        resp = client.get("/api/watchlist/")
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["code"] == "000001"

    def test_update(self, client):
        client.post("/api/watchlist/", json={"code": "000001"})
        resp = client.put("/api/watchlist/000001", json={"reason": "关注理由"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    def test_update_nonexistent(self, client):
        resp = client.put("/api/watchlist/999999", json={"reason": "test"})
        assert "error" in resp.json()

    def test_delete(self, client):
        client.post("/api/watchlist/", json={"code": "000001"})
        resp = client.delete("/api/watchlist/000001")
        assert resp.json()["status"] == "deleted"

        resp = client.get("/api/watchlist/")
        assert resp.json()["count"] == 0

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/watchlist/999999")
        assert "error" in resp.json()


class TestPlayersAPI:
    def test_create_and_list(self, client):
        resp = client.post("/api/players/", json={
            "seat_name": "华泰证券测试",
            "player_alias": "测试游资",
            "style": "打板",
        })
        assert resp.json()["status"] == "created"

        resp = client.get("/api/players/")
        data = resp.json()
        assert data["count"] == 1

    def test_update_player(self, client, db):
        p = KnownPlayer(seat_name="测试席位", player_alias="旧名")
        db.add(p)
        db.commit()
        db.refresh(p)

        resp = client.put(f"/api/players/{p.id}", json={"player_alias": "新名"})
        assert resp.json()["status"] == "updated"

    def test_delete_player(self, client, db):
        p = KnownPlayer(seat_name="待删席位")
        db.add(p)
        db.commit()
        db.refresh(p)

        resp = client.delete(f"/api/players/{p.id}")
        assert resp.json()["status"] == "deleted"


class TestBacktestAPI:
    def test_phase_returns_insufficient_data(self, client):
        resp = client.get("/api/backtest/phase-returns", params={"days": 30})
        data = resp.json()
        assert "error" in data

    def test_phase_returns_with_data(self, client, db):
        base = date.today()
        phases = ["冰点", "修复", "发酵", "高潮", "分歧", "退潮"]
        for i in range(30):
            db.add(make_emotion(
                base - timedelta(days=30 - i),
                emotion_phase=phases[i % 6],
                emotion_score=30 + i * 2,
                yesterday_premium_avg=1.0 + (i % 3) - 1,
            ))
        db.commit()

        resp = client.get("/api/backtest/phase-returns", params={"days": 60})
        data = resp.json()
        assert "phases" in data
        assert "冰点" in data["phases"]

    def test_phase_detail_invalid(self, client):
        resp = client.get("/api/backtest/phase/无效阶段")
        data = resp.json()
        assert "error" in data


class TestExportAPI:
    def test_emotion_csv(self, client, db):
        today = date.today()
        db.add(make_emotion(today))
        db.commit()

        resp = client.get("/api/export/emotion/csv", params={"days": 30})
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

    def test_recap_markdown_no_data(self, client):
        resp = client.get("/api/export/recap/markdown")
        data = resp.json()
        assert "error" in data
