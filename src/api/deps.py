"""Shared API dependencies."""

from datetime import date, datetime
from typing import Optional

from fastapi import Query


def parse_date(
    date_str: Optional[str] = Query(None, alias="date", description="日期 YYYY-MM-DD"),
) -> date:
    """Parse date query parameter, default to today."""
    if date_str:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    return date.today()
