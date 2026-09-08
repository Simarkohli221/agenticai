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
8. The "policy_evidence" list is the ONLY policy text you may reference.
   Never quote, summarize, or reference any AML/compliance rule not
   present verbatim in that list. Never invent page numbers - these
   are plain text files, not paginated documents.
9. Every policy statement you make MUST be immediately followed by a
   citation in the exact form "(policy_filename, chunk chunk_id)",
   using only the policy/chunk_id pairs given in "policy_evidence".
10. If "policy_evidence_found" is false (the list is empty), you MUST
    explicitly state that no relevant policy evidence was found for
    this investigation, in the "Policy Evidence" section, and you
    must not describe, paraphrase, or imply any policy content in
    that case.
11. The "score" field on each policy_evidence item is a semantic
    similarity score for retrieval ranking only - never describe it
    as a probability, confidence level, or compliance/approval score.
12. If "policy_retrieval_unavailable" is true, policy retrieval
    itself failed (a system/retrieval error) - this is different
    from finding no relevant evidence. State plainly that policy
    evidence could not be retrieved due to a system error, and do
    not discuss policy content at all in that case.

Provide a concise investigation summary with:

1. Customer/Account Context
2. Relevant Transaction Activity
3. Risk Indicators
4. Policy Evidence (cite every claim as described in rule 9, or state
   plainly that none was found per rule 10)
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


def generate_policy_answer(evidence: dict) -> str:
    """
    Answers a policy-only question (no risk analysis was run for
    this request - see app/agent/nodes.py:answer_policy_question_node).
    Grounding rules mirror generate_investigation_summary's policy
    rules, plus an explicit ban on implying any risk/approval
    conclusion, since none was computed here.
    """
    prompt = f"""
You are an AI assistant answering a policy question about a banking
account, using ONLY the retrieved policy evidence below.

STRICT RULES:
1. This is a policy-evidence lookup, NOT a risk assessment. Do not
   state, imply, or guess any risk level, risk score, or
   investigation conclusion - none was computed for this request.
2. The "policy_evidence" list is the ONLY policy text you may
   reference. Never invent or paraphrase any AML/compliance rule not
   present verbatim in that list. Never invent page numbers - these
   are plain text files, not paginated documents.
3. Every policy statement you make MUST be immediately followed by a
   citation in the exact form "(policy_filename, chunk chunk_id)",
   using only the policy/chunk_id pairs given in "policy_evidence".
4. If "policy_retrieval_unavailable" is true, policy retrieval itself
   failed (a system/retrieval error). State plainly that policy
   evidence could not be retrieved due to a system error, and say
   nothing else about policy content.
5. Otherwise, if "policy_evidence_found" is false, state plainly that
   no relevant policy evidence was found for this question.
6. Do not recommend or imply any account action (for example,
   freezing or closing an account) - that is outside the scope of
   this answer and is never decided by an LLM in this system.

Use the following evidence:

{evidence}
"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer policy questions strictly from the "
                    "provided policy evidence. Never invent policy "
                    "text, risk conclusions, or account-action "
                    "recommendations."
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