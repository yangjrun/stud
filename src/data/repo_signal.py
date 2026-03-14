"""信号相关 Repository。"""

from datetime import date, timedelta
from typing import Optional, Sequence

from sqlmodel import Session, select

from src.data.models_signal import DailySignal, SellSignal, SignalCandidate


class SignalRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailySignal) -> DailySignal:
        existing = self._s.exec(
            select(DailySignal).where(DailySignal.trade_date == record.trade_date)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Optional[DailySignal]:
        return self._s.exec(
            select(DailySignal).where(DailySignal.trade_date == trade_date)
        ).first()

    def get_history(self, days: int = 30) -> Sequence[DailySignal]:
        cutoff = date.today() - timedelta(days=days)
        return self._s.exec(
            select(DailySignal)
            .where(DailySignal.trade_date >= cutoff)
            .order_by(DailySignal.trade_date.desc())
        ).all()


class CandidateRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: SignalCandidate) -> SignalCandidate:
        existing = self._s.exec(
            select(SignalCandidate).where(
                SignalCandidate.trade_date == record.trade_date,
                SignalCandidate.code == record.code,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[SignalCandidate]:
        return self._s.exec(
            select(SignalCandidate)
            .where(SignalCandidate.trade_date == trade_date)
            .order_by(SignalCandidate.confidence.desc())
        ).all()

    def get_by_code(self, trade_date: date, code: str) -> Optional[SignalCandidate]:
        return self._s.exec(
            select(SignalCandidate).where(
                SignalCandidate.trade_date == trade_date,
                SignalCandidate.code == code,
            )
        ).first()


class SellSignalRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: SellSignal) -> SellSignal:
        existing = self._s.exec(
            select(SellSignal).where(
                SellSignal.trade_date == record.trade_date,
                SellSignal.code == record.code,
                SellSignal.trigger_type == record.trigger_type,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[SellSignal]:
        return self._s.exec(
            select(SellSignal)
            .where(SellSignal.trade_date == trade_date)
            .order_by(SellSignal.severity.asc())  # URGENT first
        ).all()
