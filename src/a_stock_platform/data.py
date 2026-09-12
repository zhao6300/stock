from __future__ import annotations

import re
import json
from datetime import date, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from a_stock_platform.config import settings
from a_stock_platform.models import DailyPrice


def normalize_symbol(symbol: str, symbol_type: str) -> str:
    """Return a canonical trading symbol without exchange suffixes."""
    code = symbol.strip().upper()
    code = re.sub(r"(?:^|\.)(?:SH|SZ)$", "", code)
    code = re.sub(r"^(?:SH|SZ)[. ]", "", code)
    code = re.sub(r"^(?:SH|SZ)(?=\d)", "", code)
    return code


def _stock_secid(symbol: str) -> str:
    code = normalize_symbol(symbol, "stock")
    if re.fullmatch(r"\d{6}", code):
        market = "1" if code.startswith(("6", "9")) else "0"
        return f"{market}.{code}"
    raise ValueError(f"Invalid A-share symbol: {symbol}")


def _validate_fund(symbol: str) -> str:
    code = normalize_symbol(symbol, "fund")
    if re.fullmatch(r"\d{5,6}", code):
        return code


def validate_symbol(symbol: str, symbol_type: str) -> str:
    """Validate and normalize a supported stock/fund code."""
    if symbol_type == "stock":
        return _stock_secid(symbol).split(".", 1)[1]
    if symbol_type == "fund":
        return _validate_fund(symbol)
    raise ValueError("symbol_type must be stock or fund")


def fetch_stock_daily(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    """Fetch Eastmoney daily OHLCV records, oldest row first."""
    secid = _stock_secid(symbol)
    parameters = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "1",
        "beg": "0",
        "end": "20500101",
        "lmt": str(days),
    }
    response = httpx.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params=parameters,
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()
    klines = payload.get("data", {}).get("klines", [])
    rows = []
    for line in klines:
        fields = line.split(",")
        if len(fields) < 6:
            continue
        rows.append(
            {
                "trade_date": fields[0],
                "open": float(fields[1]),
                "close": float(fields[2]),
                "high": float(fields[3]),
                "low": float(fields[4]),
                "volume": float(fields[5]),
                "source": "eastmoney",
            }
        )
    if not rows:
        raise ValueError("No stock data returned")
    return rows


def fetch_fund_daily(symbol: str, days: int = 250) -> list[dict[str, Any]]:
    """Fetch Eastmoney fund net-asset-value history, oldest row first."""
    code = _validate_fund(symbol)
    url = f"https://fund.eastmoney.com/pingzhongdata/{code}.js"
    response = httpx.get(
        url,
        headers={"Referer": "https://fund.eastmoney.com/"},
        timeout=settings.request_timeout_seconds,
    )
    response.raise_for_status()
    match = re.search(
        r"Data_netWorthTrend\s*=\s*(\[[^\]]+\])",
        response.text,
    )
    if not match:
        raise ValueError("No fund data returned")
    points = json.loads(match.group(1))
    rows = []
    for point in points[-days:]:
        trade_date = datetime.fromtimestamp(point["x"] / 1000).strftime("%Y-%m-%d")
        rows.append(
            {
                "trade_date": trade_date,
                "open": None,
                "high": None,
                "low": None,
                "close": float(point["y"]),
                "volume": None,
                "source": "eastmoney_fund",
            }
        )
    if not rows:
        raise ValueError("No fund data returned")
    return rows


def get_market_history(
    database: Session,
    symbol: str,
    symbol_type: str,
    days: int = 250,
    allow_live: bool | None = None,
) -> list[dict[str, Any]]:
    """Read imported rows first, then fall back to a live provider if allowed."""
    code = normalize_symbol(symbol, symbol_type)
    if symbol_type not in {"stock", "fund"}:
        raise ValueError("symbol_type must be stock or fund")
    statement = (
        select(DailyPrice)
        .where(DailyPrice.symbol == code, DailyPrice.symbol_type == symbol_type)
        .order_by(DailyPrice.trade_date.desc())
        .limit(days)
    )
    stored = database.execute(statement).scalars().all()
    if stored:
        return [
            {
                "trade_date": row.trade_date,
                "open": float(row.open_value) if row.open_value is not None else None,
                "high": float(row.high_value) if row.high_value is not None else None,
                "low": float(row.low_value) if row.low_value is not None else None,
                "close": float(row.close_value),
                "volume": float(row.volume) if row.volume is not None else None,
                "source": row.source,
            }
            for row in reversed(stored)
        ]
    should_try_live = allow_live if allow_live is not None else settings.live_data_enabled
    if not should_try_live:
        return []
    fetcher = fetch_fund_daily if symbol_type == "fund" else fetch_stock_daily
    return fetcher(code, days)


def import_daily_prices(
    database: Session,
    symbol: str,
    symbol_type: str,
    rows: list[dict[str, Any]],
    source: str = "csv",
) -> int:
    """Import rows, replacing duplicate dates in the segment."""
    code = normalize_symbol(symbol, symbol_type)
    imported = 0
    already = set()
    for row in rows:
        try:
            trade_date = datetime.strptime(str(row["trade_date"]), "%Y-%m-%d").date().isoformat()
            close = float(row["close"])
        except (KeyError, ValueError, TypeError) as error:
            raise ValueError("Rows must include YYYY-MM-DD trade_date and close") from error
        if trade_date in already:
            continue
        already.add(trade_date)
        existing = database.execute(
            select(DailyPrice).where(
                DailyPrice.symbol == code,
                DailyPrice.symbol_type == symbol_type,
                DailyPrice.trade_date == trade_date,
            )
        ).scalar_one_or_none()
        if existing:
            existing.open_value = row.get("open")
            existing.high_value = row.get("high")
            existing.low_value = row.get("low")
            existing.close_value = close
            existing.volume = row.get("volume")
            existing.source = source
        else:
            database.add(
                DailyPrice(
                    symbol=code,
                    symbol_type=symbol_type,
                    trade_date=trade_date,
                    open_value=row.get("open"),
                    high_value=row.get("high"),
                    low_value=row.get("low"),
                    close_value=close,
                    volume=row.get("volume"),
                    source=source,
                )
            )
        imported += 1
    database.commit()
    return imported
