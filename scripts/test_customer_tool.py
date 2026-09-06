from app.db.database import SessionLocal
from app.tools.customer_tool import get_customer_account


if __name__ == "__main__":
    db = SessionLocal()

    try:
        account = get_customer_account(
            db,
            "80B779D80"
        )

        print("=== Account Information ===")
        print(account)

    finally:
        db.close()