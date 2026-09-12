from a_stock_platform.models import User, get_engine, init_database


def test_database_creates_schema(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'schema.db'}"
    init_database(database_url)
    engine = get_engine(database_url)
    with engine.connect() as connection:
        names = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "users" in names
    assert "daily_prices" in names
