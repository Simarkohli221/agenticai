from app.db.database import SessionLocal
from app.tools.case_tool import (
    get_case,
    update_case_status,
)


if __name__ == "__main__":
    db = SessionLocal()

    try:
        case_id = 4

        print("=== Existing Case ===")
        case = get_case(db, case_id)
        print(case)

        print("\n=== Updating Status ===")
        updated = update_case_status(
            db,
            case_id,
            "UNDER_REVIEW"
        )
        print(updated)

        print("\n=== Updated Case ===")
        case = get_case(db, case_id)
        print(case)

    finally:
        db.close()