"""预测回测 Repository。"""

from typing import Optional, Sequence

from sqlmodel import Session, select

from src.data.models_backtest import ForecastBacktestDay, ForecastBacktestRun


class ForecastBacktestRepository:
    def __init__(self, session: Session):
        self._s = session

    def save(
        self, run: ForecastBacktestRun, days: list[ForecastBacktestDay],
    ) -> ForecastBacktestRun:
        self._s.add(run)
        self._s.flush()  # get auto-generated id
        for day in days:
            day.run_id = run.id  # type: ignore[assignment]
            self._s.add(day)
        return run

    def get_by_id(self, run_id: int) -> Optional[ForecastBacktestRun]:
        return self._s.get(ForecastBacktestRun, run_id)

    def get_days(self, run_id: int) -> Sequence[ForecastBacktestDay]:
        return self._s.exec(
            select(ForecastBacktestDay)
            .where(ForecastBacktestDay.run_id == run_id)
            .order_by(ForecastBacktestDay.source_date)
        ).all()

    def get_recent(self, limit: int = 10) -> Sequence[ForecastBacktestRun]:
        return self._s.exec(
            select(ForecastBacktestRun)
            .order_by(ForecastBacktestRun.created_at.desc())
            .limit(limit)
        ).all()

    def delete(self, run_id: int) -> None:
        days = self._s.exec(
            select(ForecastBacktestDay)
            .where(ForecastBacktestDay.run_id == run_id)
        ).all()
        for d in days:
            self._s.delete(d)
        run = self.get_by_id(run_id)
        if run:
            self._s.delete(run)
