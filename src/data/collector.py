"""AKShare data collector with rate limiting and retry logic."""

import time
from datetime import date, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger


class DataCollector:
    """Wraps AKShare API calls with rate limiting and error handling."""

    def __init__(self, request_interval: float = 0.6, max_retries: int = 3):
        self._interval = request_interval
        self._max_retries = max_retries
        self._last_request_time: float = 0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_request_time = time.monotonic()

    def _call(self, func, *args, **kwargs) -> Optional[pd.DataFrame]:
        for attempt in range(1, self._max_retries + 1):
            try:
                self._throttle()
                df = func(*args, **kwargs)
                if df is None or df.empty:
                    logger.debug(f"{func.__name__} returned empty data")
                    return None
                return df
            except ValueError as e:
                # ValueError indicates invalid parameters (e.g. date out of
                # supported range) — retrying won't help.
                logger.warning(f"{func.__name__} rejected input: {e}")
                return None
            except Exception as e:
                wait = self._interval * (2 ** (attempt - 1))
                logger.warning(
                    f"{func.__name__} attempt {attempt}/{self._max_retries} failed: {e}, "
                    f"retrying in {wait:.1f}s"
                )
                if attempt < self._max_retries:
                    time.sleep(wait)
        logger.error(f"{func.__name__} failed after {self._max_retries} attempts")
        return None

    # ─── 涨停相关 ───

    def fetch_limit_up_pool(self, trade_date: date) -> Optional[pd.DataFrame]:
        """涨停股池: 代码/名称/涨停价/封单额/首封时间/连板数等"""
        date_str = trade_date.strftime("%Y%m%d")
        return self._call(ak.stock_zt_pool_em, date=date_str)

    def fetch_limit_up_previous(self, trade_date: date) -> Optional[pd.DataFrame]:
        """昨日涨停股今日表现: 溢价率"""
        date_str = trade_date.strftime("%Y%m%d")
        return self._call(ak.stock_zt_pool_previous_em, date=date_str)

    def fetch_burst_pool(self, trade_date: date) -> Optional[pd.DataFrame]:
        """炸板股池: 曾封涨停但收盘未封住"""
        date_str = trade_date.strftime("%Y%m%d")
        return self._call(ak.stock_zt_pool_zbgc_em, date=date_str)

    def fetch_limit_down_pool(self, trade_date: date) -> Optional[pd.DataFrame]:
        """跌停股池"""
        date_str = trade_date.strftime("%Y%m%d")
        return self._call(ak.stock_zt_pool_dtgc_em, date=date_str)

    def fetch_strong_pool(self, trade_date: date) -> Optional[pd.DataFrame]:
        """强势股池"""
        date_str = trade_date.strftime("%Y%m%d")
        return self._call(ak.stock_zt_pool_strong_em, date=date_str)

    # ─── 龙虎榜 ───

    def fetch_dragon_tiger(
        self, start_date: date, end_date: Optional[date] = None
    ) -> Optional[pd.DataFrame]:
        """龙虎榜详情 (东方财富)"""
        start_str = start_date.strftime("%Y%m%d")
        end_str = (end_date or start_date).strftime("%Y%m%d")
        return self._call(
            ak.stock_lhb_detail_em, start_date=start_str, end_date=end_str
        )

    # ─── 概念板块 ───

    def fetch_concept_board_names(self) -> Optional[pd.DataFrame]:
        """概念板块列表"""
        return self._call(ak.stock_board_concept_name_em)

    def fetch_concept_board_detail(self, symbol: str) -> Optional[pd.DataFrame]:
        """概念板块成分股"""
        return self._call(ak.stock_board_concept_cons_em, symbol=symbol)

    # ─── 市场总览 ───

    def fetch_market_overview(self) -> Optional[pd.DataFrame]:
        """全A股实时行情 (用于计算涨跌家数)"""
        return self._call(ak.stock_zh_a_spot_em)
