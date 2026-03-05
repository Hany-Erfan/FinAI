from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base
engine = create_engine("postgresql://agentixBuddy:agentixsecret@postgres_db:5432/agentixBuddy", pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables (use Alembic in production for migrations). -> later for versioning """ 
    Base.metadata.create_all(bind=engine)


def get_db():
    """Context-manager compatible DB session helper."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
