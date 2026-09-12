"""Reusable portfolio analytics."""

from __future__ import annotations

import math
from typing import Any


_TRADING_DAYS_PER_YEAR = 252


def compute_metrics(candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute return, risk and trend indicators for daily close prices."""
    if not candles:
        raise ValueError("At least one close price is required")
    closes = [float(row["close"]) for row in candles]
    if any(value <= 0 for value in closes):
        raise ValueError("Close prices must be positive")
    total_return = closes[-1] / closes[0] - 1
    returns = [
        closes[index] / closes[index - 1] - 1
        for index in range(1, len(closes))
    ]
    mean_return = sum(returns) / len(returns) if returns else 0.0
    variance = (
        sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        if len(returns) > 1
        else 0.0
    )
    annual_volatility = math.sqrt(max(0.0, variance) * _TRADING_DAYS_PER_YEAR)
    running_peak = math.inf
    max_drawdown = 0.0
    for close in closes:
        running_peak = max(close if math.isinf(running_peak) else running_peak, close)
        max_drawdown = min(max_drawdown, close / running_peak - 1)
    annualized_return = total_return * _TRADING_DAYS_PER_YEAR / max(1, len(candles) - 1)
    average_price = sum(closes) / len(closes)
    recent = closes[-min(20, len(closes)) :]
    perception = recent
    return {
        "count": len(closes),
        "start": closes[0],
        "latest": closes[-1],
        "start_date": candles[0]["trade_date"],
        "end_date": candles[-1]["trade_date"],
        "total_return_pct": total_return * 100,
        "annualized_return_pct": annualized_return * 100,
        "annualized_volatility_pct": annual_volatility * 100,
        "sharpe": (annualized_return / (annual_volatility or math.inf) if annual_volatility else None),
        "max_drawdown_pct": max_drawdown * 100,
        "ma5": sum(closes[-5:]) / min(5, len(closes)),
        "ma20": sum(closes[-20:]) / min(20, len(closes)),
        "ma60": sum(closes[-60:]) / min(60, len(closes)),
        "average_price": average_price,
        "trend": "upward" if closes[-1] > sum(recent) / len(recent) else "downward",
        "per_bars": len(perception),
    }
