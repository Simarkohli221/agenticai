from app.db.database import engine
from app.db.base import Base

from app.models.entity import Entity
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.case import InvestigationCase
from app.models.audit import AuditLog
from app.models.user import User


Base.metadata.create_all(bind=engine)

print("Tables created successfully.")