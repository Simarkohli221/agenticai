import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=api_key)


def parse_investigation_request(user_request: str) -> dict:
    prompt = f"""
You are the request parser for a banking transaction investigation system.

Extract the account number from the user's request.

Return ONLY valid JSON in this exact format:

{{
    "account_number": "string or null"
}}

Do not invent an account number.
If no account number is present, return null.

User request:
{user_request}
"""

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    result = interaction.output_text.strip()

    return json.loads(result)