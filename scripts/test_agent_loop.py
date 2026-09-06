import os
import json

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


tools = [
    {
        "type": "function",
        "name": "get_customer",
        "description": "Gets customer and account information for a given account number.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string"
                }
            },
            "required": ["account_number"]
        }
    },
    {
        "type": "function",
        "name": "get_transactions_for_account",
        "description": "Gets recent transactions for a given bank account.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string"
                },
                "limit": {
                    "type": "integer"
                }
            },
            "required": ["account_number"]
        }
    },
    {
        "type": "function",
        "name": "search_aml_policy",
        "description": "Searches AML policies relevant to an investigation.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "analyze_account_risk",
        "description": "Analyzes recent transactions for an account using the deterministic risk engine.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string"
                }
            },
            "required": ["account_number"]
        }
    }
]


def execute_tool(name, arguments):

    if name == "get_customer":
        return get_customer(**arguments)

    elif name == "get_transactions_for_account":
        return get_transactions_for_account(**arguments)

    elif name == "search_aml_policy":
        return search_aml_policy(**arguments)

    elif name == "analyze_account_risk":
        return analyze_account_risk(**arguments)

    return {"error": f"Unknown tool: {name}"}


user_request = (
    "Investigate account 8000EBD30. "
    "Find the customer information, review recent transactions, "
    "analyze the risk, and identify the relevant AML policy. "
    "Then give me a concise investigation summary."
)


# First request
interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input=user_request,
    tools=tools,
)


for _ in range(10):

    function_calls = [
        step
        for step in interaction.steps
        if step.type == "function_call"
    ]

    # No more tools needed
    if not function_calls:
        print("\n=== FINAL ANSWER ===")
        print(interaction.output_text)
        break

    # Execute the requested tool calls
    tool_results = []

    for call in function_calls:

        print("\nGemini requested:")
        print("Tool:", call.name)
        print("Arguments:", call.arguments)

        result = execute_tool(
            call.name,
            call.arguments
        )

        print("Tool result:")
        print(result)

        tool_results.append({
            "type": "function_result",
            "name": call.name,
            "call_id": call.id,
            "result": json.dumps(result)
        })

    # Continue the SAME interaction
    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        previous_interaction_id=interaction.id,
        input=tool_results,
        tools=tools,
    )