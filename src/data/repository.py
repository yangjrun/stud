"""Repository layer: UPSERT-based data access for all tables."""

from datetime import date
from typing import Optional, Sequence

from sqlmodel import Session, select

from src.data.models import (
    DailyBurst,
    DailyEmotion,
    DailyLimitDown,
    DailyLimitUp,
    DailyRecap,
    DailyTheme,
    DragonTiger,
    DragonTigerSeat,
    KnownPlayer,
    Watchlist,
    RecapTemplate,
)


class LimitUpRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyLimitUp) -> DailyLimitUp:
        existing = self._s.exec(
            select(DailyLimitUp).where(
                DailyLimitUp.trade_date == record.trade_date,
                DailyLimitUp.code == record.code,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[DailyLimitUp]:
        return self._s.exec(
            select(DailyLimitUp)
            .where(DailyLimitUp.trade_date == trade_date)
            .order_by(DailyLimitUp.continuous_count.desc())
        ).all()

    def get_by_date_range(
        self, start: date, end: date
    ) -> Sequence[DailyLimitUp]:
        return self._s.exec(
            select(DailyLimitUp).where(
                DailyLimitUp.trade_date >= start,
                DailyLimitUp.trade_date <= end,
            )
        ).all()


class BurstRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyBurst) -> DailyBurst:
        existing = self._s.exec(
            select(DailyBurst).where(
                DailyBurst.trade_date == record.trade_date,
                DailyBurst.code == record.code,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[DailyBurst]:
        return self._s.exec(
            select(DailyBurst).where(DailyBurst.trade_date == trade_date)
        ).all()


class LimitDownRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyLimitDown) -> DailyLimitDown:
        existing = self._s.exec(
            select(DailyLimitDown).where(
                DailyLimitDown.trade_date == record.trade_date,
                DailyLimitDown.code == record.code,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[DailyLimitDown]:
        return self._s.exec(
            select(DailyLimitDown).where(DailyLimitDown.trade_date == trade_date)
        ).all()


class EmotionRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyEmotion) -> DailyEmotion:
        existing = self._s.exec(
            select(DailyEmotion).where(DailyEmotion.trade_date == record.trade_date)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Optional[DailyEmotion]:
        return self._s.exec(
            select(DailyEmotion).where(DailyEmotion.trade_date == trade_date)
        ).first()

    def get_recent(self, before_date: date, limit: int = 60) -> Sequence[DailyEmotion]:
        return self._s.exec(
            select(DailyEmotion)
            .where(DailyEmotion.trade_date < before_date)
            .order_by(DailyEmotion.trade_date.desc())
            .limit(limit)
        ).all()

    def get_range(self, start: date, end: date) -> Sequence[DailyEmotion]:
        return self._s.exec(
            select(DailyEmotion)
            .where(DailyEmotion.trade_date >= start, DailyEmotion.trade_date <= end)
            .order_by(DailyEmotion.trade_date.asc())
        ).all()


class ThemeRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyTheme) -> DailyTheme:
        existing = self._s.exec(
            select(DailyTheme).where(
                DailyTheme.trade_date == record.trade_date,
                DailyTheme.concept_name == record.concept_name,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[DailyTheme]:
        return self._s.exec(
            select(DailyTheme)
            .where(DailyTheme.trade_date == trade_date)
            .order_by(DailyTheme.limit_up_count.desc())
        ).all()

    def get_theme_history(
        self, concept_name: str, limit: int = 30
    ) -> Sequence[DailyTheme]:
        return self._s.exec(
            select(DailyTheme)
            .where(DailyTheme.concept_name == concept_name)
            .order_by(DailyTheme.trade_date.desc())
            .limit(limit)
        ).all()

    def get_theme_on_date(
        self, concept_name: str, trade_date: date
    ) -> Optional[DailyTheme]:
        return self._s.exec(
            select(DailyTheme).where(
                DailyTheme.concept_name == concept_name,
                DailyTheme.trade_date == trade_date,
            )
        ).first()

    def search_by_keyword(
        self, keyword: str, start: date, end: date
    ) -> Sequence[DailyTheme]:
        return self._s.exec(
            select(DailyTheme)
            .where(
                DailyTheme.concept_name.contains(keyword),
                DailyTheme.trade_date >= start,
                DailyTheme.trade_date <= end,
            )
            .order_by(DailyTheme.trade_date.desc(), DailyTheme.limit_up_count.desc())
            .limit(100)
        ).all()


class DragonTigerRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DragonTiger) -> DragonTiger:
        existing = self._s.exec(
            select(DragonTiger).where(
                DragonTiger.trade_date == record.trade_date,
                DragonTiger.code == record.code,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Sequence[DragonTiger]:
        return self._s.exec(
            select(DragonTiger).where(DragonTiger.trade_date == trade_date)
        ).all()


class DragonTigerSeatRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DragonTigerSeat) -> DragonTigerSeat:
        existing = self._s.exec(
            select(DragonTigerSeat).where(
                DragonTigerSeat.trade_date == record.trade_date,
                DragonTigerSeat.code == record.code,
                DragonTigerSeat.direction == record.direction,
                DragonTigerSeat.rank == record.rank,
            )
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_seats_for_stock(
        self, trade_date: date, code: str
    ) -> Sequence[DragonTigerSeat]:
        return self._s.exec(
            select(DragonTigerSeat).where(
                DragonTigerSeat.trade_date == trade_date,
                DragonTigerSeat.code == code,
            )
        ).all()

    def get_by_player(
        self, player_name: str, limit: int = 30
    ) -> Sequence[DragonTigerSeat]:
        return self._s.exec(
            select(DragonTigerSeat)
            .where(
                DragonTigerSeat.is_known_player == True,  # noqa: E712
                DragonTigerSeat.player_name == player_name,
            )
            .order_by(DragonTigerSeat.trade_date.desc())
            .limit(limit)
        ).all()


class KnownPlayerRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: KnownPlayer) -> KnownPlayer:
        existing = self._s.exec(
            select(KnownPlayer).where(KnownPlayer.seat_name == record.seat_name)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_id(self, player_id: int) -> Optional[KnownPlayer]:
        return self._s.get(KnownPlayer, player_id)

    def get_all(self) -> Sequence[KnownPlayer]:
        return self._s.exec(select(KnownPlayer)).all()

    def get_all_active(self) -> Sequence[KnownPlayer]:
        return self._s.exec(
            select(KnownPlayer).where(KnownPlayer.is_active == True)  # noqa: E712
        ).all()

    def delete(self, player_id: int) -> bool:
        player = self._s.get(KnownPlayer, player_id)
        if player:
            self._s.delete(player)
            return True
        return False

    def match_seat(self, seat_name: str) -> Optional[KnownPlayer]:
        """模糊匹配营业部名称"""
        players = self.get_all_active()
        for p in players:
            if p.seat_name in seat_name or seat_name in p.seat_name:
                return p
        return None


class RecapRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: DailyRecap) -> DailyRecap:
        existing = self._s.exec(
            select(DailyRecap).where(DailyRecap.trade_date == record.trade_date)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id"}).items():
                if val is not None:
                    setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_by_date(self, trade_date: date) -> Optional[DailyRecap]:
        return self._s.exec(
            select(DailyRecap).where(DailyRecap.trade_date == trade_date)
        ).first()


class WatchlistRepository:
    def __init__(self, session: Session):
        self._s = session

    def add(self, record: Watchlist) -> Watchlist:
        existing = self._s.exec(
            select(Watchlist).where(Watchlist.code == record.code)
        ).first()
        if existing:
            for key, val in record.model_dump(exclude={"id", "created_at"}).items():
                if val is not None:
                    setattr(existing, key, val)
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_all(self) -> Sequence[Watchlist]:
        return self._s.exec(
            select(Watchlist).order_by(Watchlist.created_at.desc())
        ).all()

    def get_by_code(self, code: str) -> Optional[Watchlist]:
        return self._s.exec(
            select(Watchlist).where(Watchlist.code == code)
        ).first()

    def delete(self, code: str) -> bool:
        record = self.get_by_code(code)
        if record:
            self._s.delete(record)
            return True
        return False

    def get_codes(self) -> list[str]:
        items = self.get_all()
        return [w.code for w in items]


class RecapTemplateRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert(self, record: RecapTemplate) -> RecapTemplate:
        existing = self._s.exec(
            select(RecapTemplate).where(RecapTemplate.name == record.name)
        ).first()
        if existing:
            existing.sections = record.sections
            existing.is_default = record.is_default
            self._s.add(existing)
            return existing
        self._s.add(record)
        return record

    def get_all(self) -> Sequence[RecapTemplate]:
        return self._s.exec(select(RecapTemplate)).all()

    def get_default(self) -> Optional[RecapTemplate]:
        return self._s.exec(
            select(RecapTemplate).where(RecapTemplate.is_default == True)  # noqa: E712
        ).first()

    def delete(self, name: str) -> bool:
        record = self._s.exec(
            select(RecapTemplate).where(RecapTemplate.name == name)
        ).first()
        if record:
            self._s.delete(record)
            return True
        return False
