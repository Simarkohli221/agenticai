import json
import os

from dotenv import load_dotenv
from groq import Groq

from app.agent.planner import VALID_INTENTS, DEFAULT_INTENT

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

MODEL = "openai/gpt-oss-120b"

# "report" is a valid requested-information item even though it is
# not a data-retrieval tool - it means the user wants a synthesized
# summary, not just raw data.
VALID_INFORMATION_ITEMS = {"customer", "transactions", "risk", "policy", "report"}
DEFAULT_REQUESTED_INFORMATION = [
    "customer", "transactions", "risk", "policy", "report",
]


def parse_investigation_request(user_request: str) -> dict:
    """
    Uses the LLM only for natural-language understanding: extracting
    the account number and classifying the request's intent/desired
    information. The LLM's output is never trusted as-is - every
    field is validated against a fixed allowlist in Python below
    before being returned. This function makes no authorization,
    risk, or approval decisions.
    """

    prompt = f"""
You are the request parser for a banking transaction investigation system.

Extract structured information from the user's natural-language request.

Return ONLY valid JSON in this exact format:

{{
    "account_number": "string or null",
    "intent": "INVESTIGATE" or "POLICY_QUESTION" or "TRANSACTION_QUESTION",
    "requested_information": ["customer", "transactions", "risk", "policy", "report"]
}}

Guidance:
- "account_number": the account number mentioned in the request. Do
  not invent one. If none is present, use null.
- "intent":
  - "POLICY_QUESTION" - the user is asking which policy/rule applies,
    or asking a compliance question, without asking for a full risk
    investigation.
  - "TRANSACTION_QUESTION" - the user specifically asks to review or
    explain recent transactions/activity and their risk.
  - "INVESTIGATE" - a general investigation request, or if intent is
    unclear.
- "requested_information": which of customer, transactions, risk,
  policy, report the user is asking about. Include "report" whenever
  a summary or explanation is requested. If unsure, include all of
  them.

Do not fabricate information that is not present in the request.

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

    raw_result = json.loads(response.choices[0].message.content)

    return _validate_parsed_request(raw_result)


def _validate_parsed_request(raw_result: dict) -> dict:
    """
    Deterministically sanitizes the LLM's raw JSON output. Any value
    outside the fixed allowlists below is discarded in favor of a
    safe default - the LLM's text can influence which of these
    pre-approved values is picked, never introduce a new one.
    """
    account_number = raw_result.get("account_number")

    intent = raw_result.get("intent")
    if intent not in VALID_INTENTS:
        intent = DEFAULT_INTENT

    requested_information = raw_result.get("requested_information")

    if isinstance(requested_information, list):
        requested_information = [
            item for item in requested_information
            if item in VALID_INFORMATION_ITEMS
        ]

    if not requested_information:
        requested_information = list(DEFAULT_REQUESTED_INFORMATION)

    return {
        "account_number": account_number,
        "intent": intent,
        "requested_information": requested_information,
    }