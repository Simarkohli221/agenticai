import csv

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.entity import Entity
from app.models.account import Account


ACCOUNTS_FILE = r"D:\Banking_Data\raw\HI-Small_accounts.csv"


def load_accounts():
    db = SessionLocal()

    try:
        entities = {}
        accounts = {}

        print("Reading accounts CSV...")

        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                entity_id = row["Entity ID"]
                entity_name = row["Entity Name"]

                account_number = row["Account Number"]
                bank_id = row["Bank ID"]
                bank_name = row["Bank Name"]

                # Keep only one record per entity
                if entity_id not in entities:
                    entities[entity_id] = Entity(
                        entity_id=entity_id,
                        entity_name=entity_name
                    )

                # Keep only one record per account
                if account_number not in accounts:
                    accounts[account_number] = Account(
                        account_number=account_number,
                        bank_id=bank_id,
                        bank_name=bank_name,
                        entity_id=entity_id
                    )

        print("Unique entities found:", len(entities))
        print("Unique accounts found:", len(accounts))

        print("\nInserting entities...")

        db.add_all(entities.values())
        db.commit()

        print("Entities inserted.")

        print("\nInserting accounts...")

        db.add_all(accounts.values())
        db.commit()

        print("Accounts inserted.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    load_accounts()