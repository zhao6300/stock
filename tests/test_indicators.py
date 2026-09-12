import pytest

from a_stock_platform.indicators import compute_metrics


def test_compute_metrics() -> None:
    candles = [
        {"trade_date": "2024-01-02", "close": 100.0},
        {"trade_date": "2024-01-03", "close": 105.0},
        {"trade_date": "2024-01-04", "close": 102.0},
    ]
    metrics = compute_metrics(candles)
    assert metrics["count"] == 3
    assert metrics["latest"] == 102.0
    assert metrics["ma5"] == pytest.approx(102.33333333333333)
    assert metrics["ma20"] == pytest.approx(102.33333333333333)
    assert metrics["ma60"] == pytest.approx(102.33333333333333)
    assert metrics["trend"] == "downward"
    assert metrics["max_drawdown_pct"] == pytest.approx(-2.857142857142849)
    assert metrics["total_return_pct"] == pytest.approx(2.0)
