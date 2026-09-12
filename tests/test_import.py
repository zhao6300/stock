import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import a_stock_platform.app as app_module
from a_stock_platform.importer import parse_csv_rows
from a_stock_platform.models import User, Watchlist, get_db, get_engine, init_database


@pytest.fixture()
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'import.db'}"
    init_database(database_url)
    engine = get_engine(database_url)
    database = sessionmaker(bind=engine)()
    database.add(
        Watchlist(user_id=1, symbol="600519", symbol_type="stock")
    )
    database.commit()
    database.close()

    def override_get_db():
        database = sessionmaker(bind=engine)()
        try:
            yield database
        finally:
            database.close()

    def override_current_user():
        return User(id=1, username="import_user", password_hash="unused")

    app_module.app.dependency_overrides[get_db] = override_get_db
    app_module.app.dependency_overrides[app_module.get_current_user] = override_current_user
    try:
        yield TestClient(app_module.app)
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        app_module.app.dependency_overrides.pop(app_module.get_current_user, None)


def test_parse_csv_rows() -> None:
    rows = parse_csv_rows(io.BytesIO(b"trade_date,open,high,low,close,volume\n2024-01-02,100,101,99,100.5,1000\n"))
    assert rows == [
        {
            "trade_date": "2024-01-02",
            "close": "100.5",
            "open": "100",
            "high": "101",
            "low": "99",
            "volume": "1000",
        }
    ]


def test_parse_csv_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="trade_date and close"):
        parse_csv_rows(io.BytesIO(b"symbol,close\n600519,100\n"))


def test_import_watchlist_csv(client) -> None:
    csv_bytes = (
        b"trade_date,close\n2024-01-02,100.0\n2024-01-03,101.0\n"
    )
    response = client.post(
        "/dashboard/watchlist/1/import",
        files={"csv_file": ("prices.csv", csv_bytes, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    analysis = client.get("/api/analysis/stock/600519", params={"days": 5})
    assert analysis.status_code == 200
    assert analysis.json()["metrics"]["count"] == 2


def test_import_watchlist_csv_rejects_bad_file(client) -> None:
    response = client.post(
        "/dashboard/watchlist/1/import",
        files={"csv_file": ("prices.csv", b"symbol,close\n600519,100\n", "text/csv")},
    )
    assert response.status_code == 422
    assert "trade_date and close" in response.text
