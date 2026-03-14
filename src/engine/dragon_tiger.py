"""龙虎榜分析引擎: 游资识别、买卖统计、协同分析。"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from src.data.models import DragonTiger, DragonTigerSeat, KnownPlayer


@dataclass(frozen=True)
class SeatInfo:
    """单个席位信息。"""

    rank: int
    seat_name: str
    buy_amount: float
    sell_amount: float
    net_amount: float
    is_known: bool
    player_alias: Optional[str]


@dataclass(frozen=True)
class StockDragonTiger:
    """单只上榜股票的龙虎榜分析。"""

    code: str
    name: str
    change_pct: Optional[float]
    reason: Optional[str]
    buy_seats: list[SeatInfo]
    sell_seats: list[SeatInfo]
    total_buy: float
    total_sell: float
    net_amount: float
    known_player_count: int
    has_institution: bool  # 有机构席位


@dataclass(frozen=True)
class PlayerActivity:
    """知名游资近期活动。"""

    player_alias: str
    trade_date: date
    code: str
    name: str
    direction: str  # "BUY" / "SELL"
    amount: float


@dataclass(frozen=True)
class DragonTigerSummary:
    """当日龙虎榜总览。"""

    trade_date: date
    stocks: list[StockDragonTiger]
    top_known_players: list[tuple[str, int]]  # [(游资别名, 出现次数)]
    player_activities: list[PlayerActivity]


class DragonTigerEngine:
    """龙虎榜分析引擎。"""

    def __init__(self, known_players: Sequence[KnownPlayer]):
        self._players = list(known_players)

    def match_player(self, seat_name: str) -> Optional[KnownPlayer]:
        """模糊匹配营业部 → 知名游资。"""
        for p in self._players:
            if p.seat_name in seat_name or seat_name in p.seat_name:
                return p
        return None

    def analyze_stock(
        self,
        dt: DragonTiger,
        seats: Sequence[DragonTigerSeat],
    ) -> StockDragonTiger:
        buy_seats: list[SeatInfo] = []
        sell_seats: list[SeatInfo] = []
        known_count = 0
        has_institution = False

        for s in seats:
            player = self.match_player(s.seat_name or "")
            is_known = player is not None
            alias = player.player_alias if player else None

            if is_known:
                known_count += 1
            if s.seat_name and "机构" in s.seat_name:
                has_institution = True

            info = SeatInfo(
                rank=s.rank,
                seat_name=s.seat_name or "",
                buy_amount=s.buy_amount or 0,
                sell_amount=s.sell_amount or 0,
                net_amount=s.net_amount or 0,
                is_known=is_known,
                player_alias=alias,
            )
            if s.direction == "BUY":
                buy_seats.append(info)
            else:
                sell_seats.append(info)

        total_buy = sum(s.buy_amount for s in buy_seats)
        total_sell = sum(s.sell_amount for s in sell_seats)

        return StockDragonTiger(
            code=dt.code,
            name=dt.name or "",
            change_pct=dt.change_pct,
            reason=dt.reason,
            buy_seats=buy_seats,
            sell_seats=sell_seats,
            total_buy=total_buy,
            total_sell=total_sell,
            net_amount=total_buy - total_sell,
            known_player_count=known_count,
            has_institution=has_institution,
        )

    def analyze_day(
        self,
        trade_date: date,
        dragons: Sequence[DragonTiger],
        all_seats: Sequence[DragonTigerSeat],
    ) -> DragonTigerSummary:
        seats_by_code: dict[str, list[DragonTigerSeat]] = {}
        for s in all_seats:
            seats_by_code.setdefault(s.code, []).append(s)

        stocks = []
        for dt in dragons:
            seats = seats_by_code.get(dt.code, [])
            stocks.append(self.analyze_stock(dt, seats))

        # 知名游资出现频次
        player_freq: dict[str, int] = {}
        activities: list[PlayerActivity] = []
        for stock in stocks:
            for seat in stock.buy_seats + stock.sell_seats:
                if seat.is_known and seat.player_alias:
                    player_freq[seat.player_alias] = player_freq.get(seat.player_alias, 0) + 1
                    direction = "BUY" if seat in stock.buy_seats else "SELL"
                    amount = seat.buy_amount if direction == "BUY" else seat.sell_amount
                    activities.append(PlayerActivity(
                        player_alias=seat.player_alias,
                        trade_date=trade_date,
                        code=stock.code,
                        name=stock.name,
                        direction=direction,
                        amount=amount,
                    ))

        top_players = sorted(player_freq.items(), key=lambda x: x[1], reverse=True)

        return DragonTigerSummary(
            trade_date=trade_date,
            stocks=stocks,
            top_known_players=top_players,
            player_activities=activities,
        )
