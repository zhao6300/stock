import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import a_stock_platform.app as app_module
from a_stock_platform.models import SavedFilter, User, get_db, get_engine, init_database


@pytest.fixture()
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'filters.db'}"
    init_database(database_url)
    engine = get_engine(database_url)

    def override_get_db():
        database = sessionmaker(bind=engine)()
        try:
            yield database
        finally:
            database.close()

    def override_current_user():
        return User(id=1, username="filter_user", password_hash="unused")

    app_module.app.dependency_overrides[get_db] = override_get_db
    app_module.app.dependency_overrides[app_module.get_current_user] = override_current_user
    try:
        yield TestClient(app_module.app)
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        app_module.app.dependency_overrides.pop(app_module.get_current_user, None)


def test_saved_filter_page(client):
    response = client.get("/filters")
    assert response.status_code == 200
    assert "保存筛选" in response.text


def test_create_and_delete_saved_filter(client):
    created = client.post(
        "/filters",
        data={
            "name": "涨势优先",
            "symbols": "600519.SH,000001.SZ",
            "symbol_type": "stock",
            "min_annualized_return_pct": 0,
            "max_annualized_volatility_pct": 100,
            "min_sharpe": 0,
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    listed = client.get("/filters")
    assert listed.status_code == 200
    assert "涨势优先" in listed.text

    deleted = client.post("/filters/1/delete", follow_redirects=False)
    assert deleted.status_code == 303
    assert client.get("/filters").text.find("涨势优先") == -1
