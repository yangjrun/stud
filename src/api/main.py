"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.data.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from src.scheduler.jobs import create_scheduler
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="A股超短线复盘系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from src.api.routes.emotion import router as emotion_router
from src.api.routes.limit_up import router as limit_up_router
from src.api.routes.theme import router as theme_router
from src.api.routes.dragon_tiger import router as dragon_tiger_router
from src.api.routes.recap import router as recap_router
from src.api.routes.backtest import router as backtest_router
from src.api.routes.watchlist import router as watchlist_router
from src.api.routes.players import router as players_router
from src.api.routes.export import router as export_router
from src.api.routes.signal import router as signal_router
from src.api.routes.journal import router as journal_router

app.include_router(emotion_router, prefix="/api/emotion", tags=["情绪周期"])
app.include_router(limit_up_router, prefix="/api/limit-up", tags=["涨停分析"])
app.include_router(theme_router, prefix="/api/themes", tags=["题材追踪"])
app.include_router(dragon_tiger_router, prefix="/api/dragon-tiger", tags=["龙虎榜"])
app.include_router(recap_router, prefix="/api/recap", tags=["每日复盘"])
app.include_router(backtest_router, prefix="/api/backtest", tags=["历史回测"])
app.include_router(watchlist_router, prefix="/api/watchlist", tags=["自选股"])
app.include_router(players_router, prefix="/api/players", tags=["游资管理"])
app.include_router(export_router, prefix="/api/export", tags=["数据导出"])
app.include_router(signal_router, prefix="/api/signals", tags=["信号引擎"])
app.include_router(journal_router, prefix="/api/journal", tags=["交易日志"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
