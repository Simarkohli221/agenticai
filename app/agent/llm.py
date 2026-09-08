import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

MODEL = "openai/gpt-oss-120b"


def generate_investigation_summary(evidence: dict) -> str:
    prompt = f"""
You are an AI assistant supporting a banking transaction investigation.

Your job is to summarize ONLY the evidence provided below.

STRICT RULES:
1. Do not invent facts, transactions, policies, thresholds, regulations,
   or customer information.
2. Do not refer to "typical alert thresholds", regulatory thresholds,
   industry thresholds, or external standards.
3. The risk score and risk level come from the project's risk engine.
   Treat them as project-generated classifications, NOT regulatory thresholds.
4. Do not claim that a policy requires or does not require escalation unless
   that requirement is explicitly stated in the provided policy evidence.
5. Do not add recommendations that are not supported by the evidence.
6. Clearly distinguish between:
   - observed transaction facts
   - risk-engine findings
   - policy evidence
   - recommended next step
7. If the evidence does not establish something, say that it is not established
   by the available evidence.

Provide a concise investigation summary with:

1. Customer/Account Context
2. Relevant Transaction Activity
3. Risk Indicators
4. Relevant Policy
5. Recommended Next Step

Use the following evidence:

{evidence}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful banking investigation assistant. "
                    "Ground every statement in the supplied evidence. "
                    "Never invent facts or external thresholds."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
    )

    return response.choices[0].message.content