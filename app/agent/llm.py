import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=api_key)


def generate_investigation_summary(evidence: dict) -> str:

    prompt = f"""
You are an AI assistant supporting a banking transaction investigation.

Analyze ONLY the evidence provided below.

Do not invent facts.
Do not create additional transactions.
Do not claim that activity is suspicious unless the provided risk analysis
supports that conclusion.

Provide a concise investigation summary explaining:
1. Customer/account context
2. Relevant transaction activity
3. Risk indicators
4. Relevant policy
5. Recommended next step

This is a synthetic dataset used for a software project.

Evidence:
{evidence}
"""

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input=prompt
    )

    return interaction.output_text