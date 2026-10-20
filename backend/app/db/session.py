from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


# A dashboard opens ~20 requests at once; the default pool (5+10) made them queue.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True,
                       pool_size=20, max_overflow=20, pool_timeout=10)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,
                            future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
