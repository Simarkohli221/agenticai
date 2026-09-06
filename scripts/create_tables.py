from app.db.base import Base
from app.db.database import engine

# Import models so SQLAlchemy knows about them
from app.models import Entity, Account, Transaction


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully.")
    print("Database:", engine.url)