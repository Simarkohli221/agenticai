import os
from dotenv import load_dotenv
from google import genai

from app.agent.llm_tools import (
    get_customer,
    get_transactions_for_account,
    search_aml_policy,
    analyze_account_risk,
)

load_dotenv()

client = genai.Client(
    api_key=os.environ["GEMINI_API_KEY"]
)


get_customer_tool = {
    "type": "function",
    "name": "get_customer",
    "description": "Gets customer and account information for a given account number.",
    "parameters": {
        "type": "object",
        "properties": {
            "account_number": {
                "type": "string",
                "description": "The bank account number to look up."
            }
        },
        "required": ["account_number"]
    }
}


get_transactions_tool = {
    "type": "function",
    "name": "get_transactions_for_account",
    "description": "Gets recent transactions for a given bank account.",
    "parameters": {
        "type": "object",
        "properties": {
            "account_number": {
                "type": "string",
                "description": "The bank account number."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent transactions to return."
            }
        },
        "required": ["account_number"]
    }
}


search_policy_tool = {
    "type": "function",
    "name": "search_aml_policy",
    "description": "Searches AML policies relevant to an investigation question.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The investigation or AML policy question."
            }
        },
        "required": ["query"]
    }
}


analyze_risk_tool = {
    "type": "function",
    "name": "analyze_account_risk",
    "description": "Analyzes account transactions using the deterministic risk engine.",
    "parameters": {
        "type": "object",
        "properties": {
            "transactions": {
                "type": "array",
                "description": "Transaction records to analyze."
            }
        },
        "required": ["transactions"]
    }
}


interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input=(
        "Investigate account 8000EBD30. "
        "Get the customer information, review its recent transactions, "
        "analyze the risk, and identify the relevant AML policy."
    ),
    tools=[
        get_customer_tool,
        get_transactions_tool,
        search_policy_tool,
        analyze_risk_tool,
    ],
)


print("=== Gemini Tool Selection ===")

for step in interaction.steps:

    if step.type == "function_call":

        print(f"\nTool: {step.name}")
        print(f"Arguments: {step.arguments}")

        if step.name == "get_customer":
            result = get_customer(**step.arguments)

        elif step.name == "get_transactions_for_account":
            result = get_transactions_for_account(**step.arguments)

        elif step.name == "search_aml_policy":
            result = search_aml_policy(**step.arguments)

        elif step.name == "analyze_account_risk":
            result = analyze_account_risk(**step.arguments)

        else:
            result = {"error": "Unknown tool"}

        print("Result:")
        print(result)