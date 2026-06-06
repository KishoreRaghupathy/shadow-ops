from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from src.auth.dependencies import require_role, Role
from src.graph.builder_agent import build_graph
from src.graph.lineage_agent import get_lineage
from src.graph.impact_agent import compute_impact
from src.graph.root_cause_agent import get_root_causes

router = APIRouter(prefix="/graph", tags=["Graph"])

@router.post("/build", status_code=status.HTTP_200_OK)
async def build(metadata: Dict, user=Depends(require_role(Role.ADMIN)):
    """Build/refresh the knowledge graph from supplied metadata."""
    try:
        build_graph(metadata)
        return {"message": "Graph built/updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/lineage/{node_id}")
async def lineage(node_id: str, direction: str = "upstream", user=Depends(require_role(Role.DATA_ENGINEER)):
    """Return upstream or downstream lineage for a node."""
    try:
        result = await get_lineage(node_id, direction)
        return {"node_id": node_id, "direction": direction, "lineage": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/impact/{node_id}")
async def impact(node_id: str, user=Depends(require_role(Role.DATA_STEWARD)):
    """Compute impact score for a node."""
    try:
        return await compute_impact(node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/root_cause/{node_id}")
async def root_cause(node_id: str, user=Depends(require_role(Role.ADMIN)):
    """Find possible upstream root‑cause nodes for a given node."""
    try:
        return await get_root_causes(node_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
