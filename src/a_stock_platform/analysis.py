"""Domain analysis services for stocks and funds."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from a_stock_platform.data import get_market_history, validate_symbol
from a_stock_platform.indicators import compute_metrics
from a_stock_platform.presentation import sparkline


_MIN_DAYS = 5
_MAX_DAYS = 500
_MAX_COMPARE_SYMBOLS = 30


@dataclass(frozen=True)
class ComparisonFilter:
    """Reusable numeric conditions for a comparison query."""

    min_annualized_return_pct: float | None = None
    max_annualized_volatility_pct: float | None = None
    min_sharpe: float | None = None


def build_analysis_data(
    database: Session,
    symbol: str,
    symbol_type: str,
    days: int = 250,
) -> dict[str, Any]:
    """Return normalized symbol data, metrics and a view-ready sparkline."""
    normalized = validate_symbol(symbol, symbol_type)
    bounded_days = min(max(int(days), _MIN_DAYS), _MAX_DAYS)
    candles = get_market_history(database, normalized, symbol_type, bounded_days)
    if not candles:
        raise ValueError("暂无行情数据，请确认接口可用或导入数据")
    return {
        "symbol": normalized,
        "symbol_type": symbol_type,
        "candles": candles,
        "metrics": compute_metrics(candles),
        "source": str(candles[-1].get("source") or ""),
        "sparkline": sparkline(candles),
    }


def build_comparison_data(
    database: Session,
    symbols: str | list[str],
    symbol_type: str,
    days: int = 250,
    sort_by: str = "annualized_return_pct",
    direction: str = "desc",
    filter_: ComparisonFilter | None = None,
) -> dict[str, Any]:
    """Compare symbols after low-cardinality parsing, filtering and sorting."""
    if symbol_type not in {"stock", "fund"}:
        raise ValueError("symbol_type 只能是 stock 或 fund")
    if direction not in {"asc", "desc"}:
        raise ValueError("direction 只能是 asc 或 desc")
    if sort_by != "annualized_return_pct":
        raise ValueError("排序字段无效")

    if not isinstance(symbols, str):
        symbols = ",".join(symbols)
    requested = [item.strip() for item in symbols.replace("，", ",").split(",") if item.strip()]
    if not requested:
        raise ValueError("至少提供一个股票或基金代码")
    if len(requested) > _MAX_COMPARE_SYMBOLS:
        raise ValueError(f"一次最多比较 {_MAX_COMPARE_SYMBOLS} 个代码")

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for symbol in requested:
        try:
            result = build_analysis_data(database, symbol, symbol_type, days)
        except ValueError as error:
            warnings.append(f"{symbol}: {error}")
            continue
        rows.append(
            {
                "symbol": result["symbol"],
                "symbol_type": result["symbol_type"],
                "metrics": result["metrics"],
                "source": result["source"],
                "sparkline": result["sparkline"],
            }
        )
    rows = _apply_comparison_filter(rows, filter_)
    rows.sort(
        key=lambda row: float(row["metrics"].get(sort_by, 0.0) or 0.0),
        reverse=direction == "desc",
    )
    return {
        "symbol_type": symbol_type,
        "symbols": requested,
        "rows": rows,
        "warnings": warnings,
        "sort_by": sort_by,
        "direction": direction,
    }


def _apply_comparison_filter(
    rows: list[dict[str, Any]],
    filter_: ComparisonFilter | None,
) -> list[dict[str, Any]]:
    if filter_ is None:
        return rows
    filtered = rows
    if filter_.min_annualized_return_pct is not None:
        filtered = [
            row for row in filtered
            if float(row["metrics"].get("annualized_return_pct", 0.0))
            >= filter_.min_annualized_return_pct
        ]
    if filter_.max_annualized_volatility_pct is not None:
        filtered = [
            row for row in filtered
            if float(row["metrics"].get("annualized_volatility_pct", math.inf))
            <= filter_.max_annualized_volatility_pct
        ]
    if filter_.min_sharpe is not None:
        filtered = [
            row for row in filtered
            if row["metrics"].get("sharpe") is not None
            and float(row["metrics"]["sharpe"]) >= filter_.min_sharpe
        ]
    return filtered
