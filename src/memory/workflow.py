# src/memory/workflow.py
"""LangGraph workflow for Phase 5 Adaptive Learning Memory.
It wires together the following nodes (in order):
1. memory_search – retrieve similar incidents via RecommendationAgent.
2. pattern_detection – run PatternDetector to update risk patterns.
3. recommendation – call RecommendationAgent to get a fix suggestion.
4. decision – decide whether to auto‑recover or request human review.
5. recovery – placeholder for invoking the existing recovery workflow (e.g., incident_worker).
6. scoring – compute performance metrics via ScoringEngine.
7. memory_update – store the outcome back into IncidentMemory.
"""

import os
from typing import Dict, Any

from langgraph.graph import StateGraph, END

# Import agents we implemented earlier.
from src.agents.recommendation_agent import RecommendationAgent
from src.agents.pattern_detector import run_pattern_detection
from src.agents.decision_engine import make_decision
from src.agents.scoring_engine import compute_metrics

# Placeholder for the actual recovery execution – we will just simulate.
def execute_recovery(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate recovery execution.
    In a real system this would trigger the existing incident recovery agents.
    Here we just mark the outcome as SUCCESS for demonstration.
    """
    state["outcome"] = "SUCCESS"
    state["mttr_seconds"] = 42  # dummy value
    return state

# Define the graph nodes.

def memory_search(state: Dict[str, Any]) -> Dict[str, Any]:
    # Use RecommendationAgent to get similar incidents (no fix yet).
    agent = RecommendationAgent()
    # Expect incident_type and optional root_cause in the state.
    incident_type = state.get("incident_type", "unknown")
    root_cause = state.get("root_cause", "")
    # Perform similarity search – we reuse the same method for consistency.
    # The agent's recommend method expects an incident_id; we simulate by passing type/cause.
    # For now we just store placeholder similar count.
    similar = agent.recommend(incident_id="placeholder", top_k=5)
    state.update(similar)
    return state


def recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    # Real recommendation based on similarity results.
    agent = RecommendationAgent()
    # In a full implementation we would have an incident_id; here we use placeholder.
    rec = agent.recommend(incident_id="placeholder", top_k=5)
    state.update(rec)
    return state


def scoring(state: Dict[str, Any]) -> Dict[str, Any]:
    # Compute metrics for the incident that just completed.
    # Assume we have a DB session available via env var or dependency injection.
    # For now we skip DB interaction and just add dummy metrics.
    state["metrics"] = {"success_rate": 1.0, "patch_effectiveness": 1.0, "mttr_seconds": state.get("mttr_seconds", 0)}
    return state

# Build the graph.
graph = StateGraph(dict)  # state is a simple dict

graph.add_node("memory_search", memory_search)
graph.add_node("pattern_detection", lambda s: {**s, **{"patterns": run_pattern_detection(os.getenv("DB_SESSION") or "")}})
graph.add_node("recommendation", recommendation)
graph.add_node("decision", make_decision)
graph.add_node("recovery", execute_recovery)
graph.add_node("scoring", scoring)

graph.add_edge("memory_search", "pattern_detection")
graph.add_edge("pattern_detection", "recommendation")
graph.add_edge("recommendation", "decision")
graph.add_edge("decision", "recovery")
graph.add_edge("recovery", "scoring")
graph.add_edge("scoring", END)

# Compile the graph for execution.
workflow = graph.compile()

if __name__ == "__main__":
    # Simple manual run for debugging.
    initial_state = {"incident_type": "API Failure", "root_cause": None}
    result = workflow.invoke(initial_state)
    print("Workflow result:", result)
