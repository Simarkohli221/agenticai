import os
import json
from dotenv import load_dotenv
from google import genai

from app.agent.llm_tools import get_customer

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

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Get the customer information for account 8000EBD30.",
    tools=[get_customer_tool]
)

for step in interaction.steps:
    if step.type == "function_call":
        print("Gemini requested:")
        print("Tool:", step.name)
        print("Arguments:", step.arguments)

        result = get_customer(**step.arguments)

        print("\nTool result:")
        print(result)