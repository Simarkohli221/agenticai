from sqlalchemy import inspect

from app.db.database import engine


if __name__ == "__main__":
    inspector = inspect(engine)

    tables = inspector.get_table_names()

    print("Database tables:")
    for table in tables:
        print("-", table)

    print("\nTransaction indexes:")
    indexes = inspector.get_indexes("transactions")

    for index in indexes:
        print("-", index["name"], "->", index["column_names"])