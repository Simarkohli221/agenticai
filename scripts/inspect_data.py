import csv

TRANS_FILE = r"D:\Banking_Data\raw\HI-Small_Trans.csv"
ACCOUNTS_FILE = r"D:\Banking_Data\raw\HI-Small_accounts.csv"


def inspect_transactions():
    total = 0
    laundering = 0
    from_accounts = set()
    to_accounts = set()

    with open(TRANS_FILE, "r", encoding="utf-8") as file:
        reader = csv.reader(file)

        header = next(reader)

        print("Transaction columns:")
        for i, column in enumerate(header):
            print(f"{i}: {column}")

        for row in reader:
            total += 1

            # Column positions based on the actual CSV
            from_account = row[2]
            to_account = row[4]
            is_laundering = row[10]

            if is_laundering == "1":
                laundering += 1

            from_accounts.add(from_account)
            to_accounts.add(to_account)

    print("\n--- Transaction Statistics ---")
    print("Total transactions:", total)
    print("Laundering transactions:", laundering)
    print("Non-laundering transactions:", total - laundering)
    print("Unique sender accounts:", len(from_accounts))
    print("Unique receiver accounts:", len(to_accounts))
    print("Unique accounts involved:", len(from_accounts | to_accounts))


def inspect_accounts():
    total = 0
    entities = set()
    accounts = set()

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        print("\nAccount columns:")
        print(reader.fieldnames)

        for row in reader:
            total += 1
            accounts.add(row["Account Number"])
            entities.add(row["Entity ID"])

    print("\n--- Account Statistics ---")
    print("Total account records:", total)
    print("Unique accounts:", len(accounts))
    print("Unique entities:", len(entities))


if __name__ == "__main__":
    inspect_transactions()
    inspect_accounts()