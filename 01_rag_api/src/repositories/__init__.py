from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.environment import DATABASE_URL

# SQLAlchemy 2.1 cambio el driver por defecto de postgresql:// a psycopg (v3).
# El proyecto instala psycopg2-binary, asi que se fija el driver explicitamente.
_url = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1) if DATABASE_URL.startswith("postgresql://") else DATABASE_URL
engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
