"""预测信号 Repository。"""

from datetime import date, timedelta
from typing import Optional, Sequence

from sqlmodel import Session, select

from src.data.models_signal import ForecastCandidate, ForecastSignal


class ForecastSignalRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: ForecastSignal) -> ForecastSignal:
        existing = self._s.exec(
            select(ForecastSignal).where(
                ForecastSignal.trade_date == record.trade_date,
                ForecastSignal.source_date == record.source_date,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Optional[ForecastSignal]:
        """获取针对某日的预测 (trade_date = 被预测的日期)。"""
        return self._s.exec(
            select(ForecastSignal).where(ForecastSignal.trade_date == trade_date)
        ).first()

    def get_by_source_date(self, source_date: date) -> Optional[ForecastSignal]:
        """获取某日生成的预测。"""
        return self._s.exec(
            select(ForecastSignal).where(ForecastSignal.source_date == source_date)
        ).first()

    def get_history(self, days: int = 30) -> Sequence[ForecastSignal]:
        cutoff = date.today() - timedelta(days=days)
        return self._s.exec(
            select(ForecastSignal)
            .where(ForecastSignal.source_date >= cutoff)
            .order_by(ForecastSignal.source_date.desc())
        ).all()

    def update_accuracy(
        self, trade_date: date, accuracy_gate: int, accuracy_candidates: float,
    ) -> Optional[ForecastSignal]:
        record = self.get_by_date(trade_date)
        if record:
            record.accuracy_gate = accuracy_gate
            record.accuracy_candidates = accuracy_candidates
            self._s.add(record)
        return record


class ForecastCandidateRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: ForecastCandidate) -> ForecastCandidate:
        existing = self._s.exec(
            select(ForecastCandidate).where(
                ForecastCandidate.trade_date == record.trade_date,
                ForecastCandidate.code == record.code,
                ForecastCandidate.forecast_type == record.forecast_type,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[ForecastCandidate]:
        return self._s.exec(
            select(ForecastCandidate)
            .where(ForecastCandidate.trade_date == trade_date)
            .order_by(ForecastCandidate.confidence.desc())
        ).all()

    def get_buy_forecasts(self, trade_date: date) -> Sequence[ForecastCandidate]:
        return self._s.exec(
            select(ForecastCandidate)
            .where(
                ForecastCandidate.trade_date == trade_date,
                ForecastCandidate.forecast_type != "sell_warning",
            )
            .order_by(ForecastCandidate.confidence.desc())
        ).all()

    def get_sell_forecasts(self, trade_date: date) -> Sequence[ForecastCandidate]:
        return self._s.exec(
            select(ForecastCandidate)
            .where(
                ForecastCandidate.trade_date == trade_date,
                ForecastCandidate.forecast_type == "sell_warning",
            )
            .order_by(ForecastCandidate.confidence.desc())
        ).all()

    def update_actual_result(
        self, trade_date: date, code: str, actual_result: str,
    ) -> None:
        records = self._s.exec(
            select(ForecastCandidate).where(
                ForecastCandidate.trade_date == trade_date,
                ForecastCandidate.code == code,
            )
        ).all()
        for r in records:
            r.actual_result = actual_result
            self._s.add(r)
