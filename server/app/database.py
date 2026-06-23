"""Silnik bazy + sesja + Base. Sync SQLAlchemy 2.0 (prosto i pewnie; FastAPI
uruchamia sync-endpointy w puli wątków)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


# SQLite (tryb dev z README) wymaga check_same_thread=False — FastAPI obsługuje
# sync-endpointy w wielu wątkach. Dla Postgresa connect_args zostaje puste.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """Zależność FastAPI — jedna sesja na request, zawsze zamykana."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
