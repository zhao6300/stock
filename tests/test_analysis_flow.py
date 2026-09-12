import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import a_stock_platform.app as app_module
from a_stock_platform.data import import_daily_prices
from a_stock_platform.models import User, get_db, get_engine, init_database


ROWS = [
    {"trade_date": "2024-01-02", "close": 100.0},
    {"trade_date": "2024-01-03", "close": 101.0},
    {"trade_date": "2024-01-04", "close": 102.0},
    {"trade_date": "2024-01-05", "close": 101.0},
    {"trade_date": "2024-01-08", "close": 103.0},
]

SECOND_ROWS = [
    {"trade_date": "2024-01-02", "close": 50.0},
    {"trade_date": "2024-01-03", "close": 52.0},
    {"trade_date": "2024-01-04", "close": 51.0},
    {"trade_date": "2024-01-05", "close": 55.0},
    {"trade_date": "2024-01-08", "close": 58.0},
]


@pytest.fixture()
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'analysis.db'}"
    init_database(database_url)
    engine = get_engine(database_url)
    database = sessionmaker(bind=engine)()
    import_daily_prices(database, "600519.SH", "stock", ROWS)
    import_daily_prices(database, "000001.SZ", "stock", SECOND_ROWS)
    database.close()

    def override_get_db():
        database = sessionmaker(bind=engine)()
        try:
            yield database
        finally:
            database.close()

    def override_current_user():
        return User(id=1, username="trading_user", password_hash="unused")

    app_module.app.dependency_overrides[get_db] = override_get_db
    app_module.app.dependency_overrides[app_module.get_current_user] = override_current_user
    try:
        yield TestClient(app_module.app)
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        app_module.app.dependency_overrides.pop(app_module.get_current_user, None)


def test_api_analysis(client):
    response = client.get("/api/analysis/stock/600519.SH", params={"days": 5})
    assert response.status_code == 200
    assert response.json()["symbol"] == "600519"
    assert response.json()["metrics"]["count"] == 5


def test_analysis_page(client):
    response = client.get("/analysis/stock/600519.SH", params={"days": 5})
    assert response.status_code == 200
    assert "最新价" in response.text
    assert "区间收益率" in response.text


def test_dashboard_watchlist(client):
    add_response = client.post(
        "/dashboard/watchlist",
        data={"symbol": "600519.SH", "symbol_type": "stock"},
        follow_redirects=False,
    )
    assert add_response.status_code == 303
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "600519" in dashboard.text


def test_compare_json(client):
    response = client.get(
        "/api/compare",
        params={"symbols": "600519.SH,000001.SZ", "symbol_type": "stock", "days": 5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert [row["symbol"] for row in payload["rows"]] == ["000001", "600519"]
    assert all("metrics" in row for row in payload["rows"])


def test_compare_page(client):
    response = client.get(
        "/compare",
        params={"symbols": "600519.SH,000001.SZ", "symbol_type": "stock", "days": 5},
    )
    assert response.status_code == 200
    assert "多资产对比" in response.text
    assert "600519" in response.text
    assert "000001" in response.text
