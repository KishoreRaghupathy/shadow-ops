import logging
from typing import List, Dict, Any

from src.graph.neo4j_driver import get_session
from src.cache.redis_cache import get_cache

logger = logging.getLogger(__name__)

# Simple impact thresholds (configurable via env if needed)
LOW_THRESHOLD = 5
MEDIUM_THRESHOLD = 15

async def _cache_set(key: str, value: Any, ttl: int = 1800):
    try:
        cache = await get_cache()
        await cache.set(key, value, ex=ttl)
    except Exception as e:
        logger.warning(f"Redis cache set failed for {key}: {e}")

async def _cache_get(key: str):
    try:
        cache = await get_cache()
        return await cache.get(key)
    except Exception as e:
        logger.warning(f"Redis cache get failed for {key}: {e}")
        return None

async def compute_impact(node_id: str) -> Dict[str, Any]:
    """Compute impact score for a node based on downstream reach.
    Returns a dict with:
        - node_id
        - downstream_count
        - impact_level (LOW/MEDIUM/HIGH)
    """
    cache_key = f"impact:{node_id}"
    cached = await _cache_get(cache_key)
    if cached:
        return cached

    # Cypher to count downstream nodes reachable via any relationship type
    query = (
        "MATCH (n {id: $node_id})"
        " OPTIONAL MATCH (n)-[*]->(down)"
        " WITH collect(DISTINCT down.id) AS ids"
        " RETURN size(ids) AS downstream_count"
    )
    async with get_session() as session:
        result = await session.run(query, node_id=node_id)
        record = await result.single()
        downstream_count = record["downstream_count"] if record else 0

    if downstream_count <= LOW_THRESHOLD:
        level = "LOW"
    elif downstream_count <= MEDIUM_THRESHOLD:
        level = "MEDIUM"
    else:
        level = "HIGH"

    impact_info = {
        "node_id": node_id,
        "downstream_count": downstream_count,
        "impact_level": level,
    }
    await _cache_set(cache_key, impact_info)
    return impact_info
