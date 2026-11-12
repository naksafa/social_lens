"""Engine and session management.

The analytics workload is CPU-bound pandas code, so the app uses the synchronous
SQLAlchemy engine; FastAPI runs sync endpoints in its threadpool.
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(url: str, echo: bool = False) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, echo=echo, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_conn, _record):  # type: ignore[no-untyped-def]
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, echo=echo, pool_pre_ping=True, pool_size=5, max_overflow=10)


_settings = get_settings()
engine = build_engine(_settings.database_url, _settings.db_echo)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
