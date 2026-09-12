from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

import a_stock_platform.app as app_module
from a_stock_platform.models import get_db, get_engine, init_database


@pytest.fixture()
def client(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'auth.db'}"
    init_database(database_url)

    def override_get_db():
        engine = get_engine(database_url)
        database = Session(bind=engine)
        try:
            yield database
        finally:
            database.close()

    app_module.app.dependency_overrides[get_db] = override_get_db
    original_init_database = app_module.init_database
    app_module.init_database = lambda: None
    try:
        with TestClient(app_module.app) as test_client:
            yield test_client
    finally:
        app_module.app.dependency_overrides.pop(get_db, None)
        app_module.init_database = original_init_database


def test_register_login_and_dashboard(client):
    username = "trader_one"
    response = client.post(
        "/register",
        data={"username": username, "password": "max-secret-1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    response = client.post(
        "/login",
        data={"username": username, "password": "max-secret-1"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "自选列表" in response.text


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_rejects_weak_password(client):
    response = client.post(
        "/register",
        data={"username": "tiny_user", "password": "short"},
    )
    assert response.status_code == 422
    assert "密码至少 8 个字符" in response.text
