import os
from dotenv import load_dotenv
from google import genai

from app.agent.llm_tools import (
    get_customer,
    get_transactions_for_account,
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
                "description": "The bank account number.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of recent transactions to return.",
            }
        },
        "required": ["account_number"]
    }
}

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Show me the recent transactions for account 8000EBD30.",
    tools=[
        get_customer_tool,
        get_transactions_tool,
    ],
)

for step in interaction.steps:

    if step.type == "function_call":

        print("Gemini selected:")
        print(f"Tool: {step.name}")
        print(f"Arguments: {step.arguments}")

        if step.name == "get_customer":
            result = get_customer(**step.arguments)

        elif step.name == "get_transactions_for_account":
            result = get_transactions_for_account(**step.arguments)

        else:
            result = {"error": "Unknown tool"}

        print("\nTool result:")
        print(result)