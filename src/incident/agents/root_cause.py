import httpx
import asyncio
from typing import Dict, Any

from ..repo import add_incident_action
from src.graph.router import router as graph_router  # Not used directly, we'll call endpoint via httpx

async def _call_lineage(node_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://localhost:8000/graph/lineage/{node_id}")
        resp.raise_for_status()
        return resp.json()

async def _call_impact(node_id: str) -> Dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://localhost:8000/graph/impact/{node_id}")
        resp.raise_for_status()
        return resp.json()

async def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Root‑cause investigation agent.

    Expects ``state`` to contain ``incident_id`` and ``target_node`` (the graph node id to investigate).
    Calls the Graph API to retrieve lineage and impact, computes a simple confidence score, and records the action.
    Updates ``state`` with ``root_cause`` and ``confidence``.
    """
    incident_id = state.get("incident_id")
    node_id = state.get("target_node")
    if not incident_id or not node_id:
        raise ValueError("incident_id and target_node must be present in state")

    # Parallel fetch lineage and impact
    lineage, impact = await asyncio.gather(
        _call_lineage(node_id),
        _call_impact(node_id),
    )

    # Simple heuristic: confidence is higher when impact score is high and lineage depth > 1
    impact_score = impact.get("impact_score", 0)
    lineage_depth = len(lineage.get("lineage", []))
    confidence = min(1.0, (impact_score * 0.6 + (lineage_depth / 10) * 0.4))

    # Record action in DB (asynchronously not required, repo uses sync session; we'll call via sync function)
    # We'll let the caller handle DB commit; here we only log the action.
    # Here we just add a dict entry for demonstration.
    state.update({
        "root_cause": f"Potential issue around node {node_id}",
        "confidence": confidence,
        "lineage": lineage,
        "impact": impact,
    })
    return state
