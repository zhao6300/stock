from types import SimpleNamespace

import pytest

from a_stock_platform.data import (
    fetch_fund_daily,
    fetch_stock_daily,
    get_market_history,
    import_daily_prices,
    validate_symbol,
)
from a_stock_platform.models import init_database


def test_validate_symbols() -> None:
    assert validate_symbol("600519.SH", "stock") == "600519"
    assert validate_symbol("SZ000001", "stock") == "000001"
    assert validate_symbol("012345", "fund") == "012345"
    with pytest.raises(ValueError):
        validate_symbol("AAPL", "stock")


class FakeResponse:
    def __init__(self, payload=None, text="") -> None:
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self):
        if self.payload is None:
            raise AssertionError("json payload is required")
        return self.payload


def test_fetch_stock_daily_parses_klines(monkeypatch) -> None:
    payload = {
        "data": {
            "klines": [
                "2024-01-02,100.0,101.0,102.0,99.0,1000.0",
                "2024-01-03,101.0,103.0,104.0,100.5,1100.0",
            ]
        }
    }
    monkeypatch.setattr("a_stock_platform.data.httpx.get", lambda *args, **kwargs: FakeResponse(payload))
    rows = fetch_stock_daily("600519.SH")
    assert [row["trade_date"] for row in rows] == ["2024-01-02", "2024-01-03"]
    assert rows[-1]["close"] == 103.0


def test_fetch_fund_daily_parses_points(monkeypatch) -> None:
    text = 'var Data_netWorthTrend = [{"x":1704153600000,"y":1.234}];'
    monkeypatch.setattr("a_stock_platform.data.httpx.get", lambda *args, **kwargs: FakeResponse(text=text))
    rows = fetch_fund_daily("001594")
    assert rows == [
        {
            "trade_date": "2024-01-02",
            "open": None,
            "high": None,
            "low": None,
            "close": 1.234,
            "volume": None,
            "source": "eastmoney_fund",
        }
    ]


def test_import_and_fetch_stored_history(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'market.db'}"
    init_database(database_url)
    from sqlalchemy.orm import sessionmaker

    from a_stock_platform.models import get_engine

    engine = get_engine(database_url)
    database = sessionmaker(bind=engine)()
    rows = [
        {"trade_date": "2024-01-02", "close": "100.1", "volume": 100},
        {"trade_date": "2024-01-03", "close": "101.2", "volume": 120},
    ]
    assert import_daily_prices(database, "600519.SH", "stock", rows) == 2
    history = get_market_history(database, "600519.SH", "stock", allow_live=False)
    assert [row["close"] for row in history] == [100.1, 101.2]
    assert all(row["source"] == "csv" for row in history)
