"""Database wiring for SQLAlchemy sessions and model metadata."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class used by every ORM model."""

    pass


settings = get_settings()
# SQLite needs this flag because FastAPI handles requests in different threads.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and close it afterwards."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
