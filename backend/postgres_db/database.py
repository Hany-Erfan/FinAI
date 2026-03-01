import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base
database_url = os.getenv('DATABASE_URL')
engine = create_engine('postgresql://agentixBuddy:secret@postgres_db:5432/agentixBuddy', pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables (use Alembic in production for migrations)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Context-manager compatible DB session helper."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
