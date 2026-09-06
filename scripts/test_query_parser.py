from app.agent.query_parser import parse_investigation_request


if __name__ == "__main__":

    queries = [
        "Investigate account 8000EBD30",
        "Check 8000EBD30 for unusual transaction activity",
        "Review account 8000EBD30 and tell me if it needs escalation",
        "Analyze this account for suspicious activity",
    ]

    for query in queries:

        print("\nUser:")
        print(query)

        result = parse_investigation_request(query)

        print("Parsed:")
        print(result)