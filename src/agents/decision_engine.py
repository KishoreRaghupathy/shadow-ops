# src/agents/decision_engine.py
"""Decision Engine Agent for Phase 5.
Decides whether to auto‑recover or request human approval based on the
confidence returned by the Recommendation Agent and configurable thresholds.
"""

import os
from typing import Literal, Dict, Any

# Default thresholds – can be overridden via environment variables.
AUTO_THRESHOLD = float(os.getenv("DECISION_AUTO_THRESHOLD", "0.85"))
MANUAL_THRESHOLD = float(os.getenv("DECISION_MANUAL_THRESHOLD", "0.6"))

DecisionOutcome = Literal["AUTO_RECOVER", "HUMAN_REVIEW", "NO_ACTION"]

def decide(confidence: float) -> DecisionOutcome:
    """Return the decision based on confidence.

    * confidence >= AUTO_THRESHOLD -> AUTO_RECOVER
    * confidence <= MANUAL_THRESHOLD -> HUMAN_REVIEW
    * otherwise -> NO_ACTION (e.g., wait for more data)
    """
    if confidence >= AUTO_THRESHOLD:
        return "AUTO_RECOVER"
    if confidence <= MANUAL_THRESHOLD:
        return "HUMAN_REVIEW"
    return "NO_ACTION"

def make_decision(payload: Dict[str, Any]) -> Dict[str, Any]:
    """High‑level helper used in the LangGraph node.
    Expects ``payload`` to contain a ``confidence`` key.
    Returns the original payload augmented with ``decision``.
    """
    confidence = payload.get("confidence", 0.0)
    decision = decide(confidence)
    payload["decision"] = decision
    return payload
