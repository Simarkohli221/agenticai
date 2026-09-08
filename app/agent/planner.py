"""
Deterministic tool-selection planning for the investigation graph.

Given the request intent classified by query_parser.py, this returns
the fixed, pre-vetted sequence of tools the graph should run. This
is NOT an LLM function-calling loop: the LLM only classifies intent
(free text -> one of a small closed set of labels); the mapping from
intent to tools below is ordinary Python the LLM cannot alter,
extend, or bypass. Tool execution is therefore always bounded (each
tool in a plan runs at most once, driven by LangGraph's static graph
structure - see app/agent/graph.py) and enumerable (only ALLOWED_TOOLS
ever run, from an explicit allowlist).

Account-status actions (app/services/account_service.py) are
deliberately absent from ALLOWED_TOOLS: the agent/LLM has no code
path to request one. They are reachable only through the
authenticated PATCH /accounts/{account_number}/status route, gated
by RBAC, resource authorization, HIGH-risk + APPROVED case state,
and the existing HITL workflow (see app/services/account_service.py).
"""

# The only tools the investigation graph is ever allowed to run.
# Adding a tool here does not, by itself, expose it to the LLM - the
# LLM never sees this list or calls these functions directly; nodes
# in app/agent/nodes.py call them, and only for the plans below.
ALLOWED_TOOLS = (
    "get_customer_account",
    "get_transactions",
    "search_policy",
    "analyze_risk",
    "get_account",
)

INVESTIGATE = "INVESTIGATE"
POLICY_QUESTION = "POLICY_QUESTION"
TRANSACTION_QUESTION = "TRANSACTION_QUESTION"

VALID_INTENTS = {INVESTIGATE, POLICY_QUESTION, TRANSACTION_QUESTION}
DEFAULT_INTENT = INVESTIGATE

# Every entry here must be a subset of ALLOWED_TOOLS.
INTENT_TOOL_PLANS = {
    POLICY_QUESTION: (
        "get_customer_account",
        "search_policy",
    ),
    TRANSACTION_QUESTION: (
        "get_customer_account",
        "get_transactions",
        "analyze_risk",
        "search_policy",
    ),
    INVESTIGATE: (
        "get_customer_account",
        "get_transactions",
        "analyze_risk",
        "search_policy",
    ),
}

assert all(
    tool in ALLOWED_TOOLS
    for plan in INTENT_TOOL_PLANS.values()
    for tool in plan
), "A tool plan references a tool outside ALLOWED_TOOLS."


def plan_tools(intent: str) -> tuple[str, ...]:
    """
    Returns the fixed tool plan for `intent`. Unknown/invalid intents
    deterministically fall back to the full INVESTIGATE plan (the
    most comprehensive, never a narrower one) rather than guessing.
    """
    return INTENT_TOOL_PLANS.get(intent, INTENT_TOOL_PLANS[DEFAULT_INTENT])
