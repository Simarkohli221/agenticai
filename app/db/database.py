import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Overridable for test isolation (see scripts/test_e2e.py) - the
# default is unchanged for every existing caller that doesn't set
# this environment variable.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:///D:/Banking_Data/banking_system.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()