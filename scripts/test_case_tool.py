from app.db.database import SessionLocal
from app.tools.case_tool import create_investigation_case


if __name__ == "__main__":

    db = SessionLocal()

    try:
        result = create_investigation_case(
            db=db,
            account_number="8000EBD30",
            risk_level="LOW",
            risk_score=20,
        )

        print("=== Case Created ===")
        print(result)

    finally:
        db.close()