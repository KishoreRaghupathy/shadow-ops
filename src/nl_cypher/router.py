from fastapi import APIRouter, Depends, HTTPException, status
from src.auth.dependencies import require_role, Role
from src.nl_cypher.provider import get_provider

router = APIRouter(prefix="/nl_query", tags=["NL‑Cypher"])

@router.post("/", response_model=dict)
async def nl_query(prompt: str, user=Depends(require_role(Role.ADMIN)):
    """Accept a natural‑language prompt and return a generated Cypher query and its execution result.
    The endpoint is protected – only ADMIN role can use it for now.
    """
    try:
        provider = get_provider()
        cypher = await provider.to_cypher(prompt)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"NL‑to‑Cypher generation failed: {str(e)}")
    # Execute the generated Cypher against Neo4j
    from src.graph.neo4j_driver import run_query
    try:
        results = run_query(cypher)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Cypher execution failed: {str(e)}")
    return {"cypher": cypher, "results": results}
