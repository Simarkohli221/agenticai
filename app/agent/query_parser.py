import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

MODEL = "openai/gpt-oss-120b"


def parse_investigation_request(user_request: str) -> dict:

    prompt = f"""
You are the request parser for a banking transaction investigation system.

Extract the account number from the user's request.

Return ONLY valid JSON in this exact format:

{{
    "account_number": "string or null"
}}

Do not invent an account number.

If no account number is present, return:

{{
    "account_number": null
}}

User request:
{user_request}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract structured information from banking "
                    "investigation requests. Return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    result = response.choices[0].message.content

    return json.loads(result)