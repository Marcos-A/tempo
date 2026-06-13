"""Database wiring for SQLAlchemy sessions and model metadata."""

from collections.abc import Generator
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class used by every ORM model."""

    pass


def _configure_sqlite_connection(dbapi_connection: sqlite3.Connection, _: object) -> None:
    """Apply pragmatic SQLite settings for light concurrent web traffic."""

    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


settings = get_settings()
# SQLite needs this flag because FastAPI handles requests in different threads.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
if settings.database_url.startswith("sqlite"):
    event.listen(engine, "connect", _configure_sqlite_connection)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and close it afterwards."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
