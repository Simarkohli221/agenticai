from app.db.database import SessionLocal
from app.tools.case_tool import get_case


if __name__ == "__main__":
    db = SessionLocal()

    try:
        case_id = 7

        case = get_case(db, case_id)

        print("=== Case Status ===")
        print(case)

    finally:
        db.close()