import csv
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.account import Account
from app.models.transaction import Transaction


TRANS_FILE = r"D:\Banking_Data\raw\HI-Small_Trans.csv"

BATCH_SIZE = 5000


def load_transactions():
    db = SessionLocal()

    try:
        print("Loading account numbers for validation...")

        account_numbers = set(
            db.scalars(
                select(Account.account_number)
            ).all()
        )

        print("Accounts available:", len(account_numbers))
        print("Starting transaction import...\n")

        batch = []
        total = 0
        skipped = 0
        laundering = 0

        with open(TRANS_FILE, "r", encoding="utf-8") as file:
            reader = csv.reader(file)

            # Skip header
            next(reader)

            for row in reader:

                timestamp = datetime.strptime(
                    row[0],
                    "%Y/%m/%d %H:%M"
                )

                from_account = row[2]
                to_account = row[4]

                # Make sure referenced accounts exist
                if (
                    from_account not in account_numbers
                    or to_account not in account_numbers
                ):
                    skipped += 1
                    continue

                is_laundering = row[10] == "1"

                if is_laundering:
                    laundering += 1

                transaction = Transaction(
                    timestamp=timestamp,
                    from_bank=row[1],
                    from_account=from_account,
                    to_bank=row[3],
                    to_account=to_account,
                    amount_received=Decimal(row[5]),
                    receiving_currency=row[6],
                    amount_paid=Decimal(row[7]),
                    payment_currency=row[8],
                    payment_format=row[9],
                    is_laundering=is_laundering,
                )

                batch.append(transaction)
                total += 1

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    db.commit()

                    print(
                        f"Loaded {total:,} transactions | "
                        f"Laundering: {laundering:,}"
                    )

                    batch.clear()

            # Insert remaining records
            if batch:
                db.add_all(batch)
                db.commit()

        print("\n--- Import Complete ---")
        print("Transactions loaded:", total)
        print("Laundering transactions:", laundering)
        print("Skipped transactions:", skipped)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    load_transactions()