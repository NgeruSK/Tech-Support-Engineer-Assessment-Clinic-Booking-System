import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinic.db")

connect_args = {}
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    # Needed so FastAPI's request-per-thread model can share one SQLite file.
    connect_args = {"check_same_thread": False}
    if ":memory:" in DATABASE_URL:
        # Without StaticPool, each new connection would get its own blank
        # in-memory database — fine for prod (file-based), fatal for tests.
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
