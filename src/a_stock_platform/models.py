from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from a_stock_platform.config import settings


class Base(DeclarativeBase):
    pass


class User(Base):
    """A login session owner."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Watchlist(Base):
    """Symbols saved by a user for quick analysis access."""

    __tablename__ = "watchlist_entries"
    __table_args__ = (UniqueConstraint("user_id", "symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String(20))
    symbol_type: Mapped[str] = mapped_column(String(10))
    added_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class DailyPrice(Base):
    """A single daily row for a stock or fund."""

    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("symbol", "symbol_type", "trade_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    symbol_type: Mapped[str] = mapped_column(String(10))
    trade_date: Mapped[str] = mapped_column(String(10))
    open_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    high_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    low_value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    close_value: Mapped[float] = mapped_column(Numeric)
    volume: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    source: Mapped[str] = mapped_column(String(30))


def get_engine(database_url: str | None = None):
    """Create a SQLite ready SQLAlchemy engine."""
    url = database_url or settings.database_url
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///").split("?", 1)[0]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


def init_database(database_url: str | None = None) -> None:
    """Create all data store schema objects."""
    engine = get_engine(database_url)
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """Yield a request-scoped database session."""
    engine = get_engine()
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def get_user_by_username(username: str, database: Session) -> User | None:
    """Return a user by lowercase username."""
    statement = select(User).where(User.username == username.strip().lower())
    return database.execute(statement).scalar_one_or_none()
