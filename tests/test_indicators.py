from a_stock_platform.indicators import compute_metrics


def test_compute_metrics() -> None:
    metrics = compute_metrics([{"close": 100.0}, {"close": 105.0}])
    assert metrics["count"] == 2
    assert metrics["latest"] == 105.0
