import logging
from typing import List, Dict, Any

from src.graph.neo4j_driver import get_session
from src.cache.redis_cache import get_cache
from config.settings import settings

logger = logging.getLogger(__name__)

async def _cache_set(key: str, value: Any, ttl: int = 1800):
    """Set a value in Redis cache with TTL (default 30 minutes)."""
    try:
        cache = await get_cache()
        await cache.set(key, value, ex=ttl)
    except Exception as e:
        logger.warning(f"Redis cache set failed for {key}: {e}")

async def _cache_get(key: str):
    """Retrieve a value from Redis cache; return None on miss or error."""
    try:
        cache = await get_cache()
        return await cache.get(key)
    except Exception as e:
        logger.warning(f"Redis cache get failed for {key}: {e}")
        return None

async def get_lineage(node_id: str, direction: str = "upstream") -> List[Dict[str, Any]]:
    """Return upstream or downstream lineage for a given node.

    Args:
        node_id: Unique identifier of the node (e.g., contract ID).
        direction: "upstream" to follow incoming relationships, "downstream" for outgoing.
    Returns:
        List of dictionaries representing related nodes and relationship types.
    """
    cache_key = f"lineage:{direction}:{node_id}"
    cached = await _cache_get(cache_key)
    if cached:
        return cached

    query = (
        "MATCH (n {id: $node_id})"
        " OPTIONAL MATCH (n)" + ("<-[:DEPENDS_ON*]" if direction == "upstream" else "-[:DEPENDS_ON*]->") + " (m)"
        " RETURN collect({id: m.id, labels: labels(m), rels: relationships((n)-[:DEPENDS_ON*]-(m))}) as lineage"
    )
    async with get_session() as session:
        result = await session.run(query, node_id=node_id)
        record = await result.single()
        lineage = record["lineage"] if record else []

    await _cache_set(cache_key, lineage)
    return lineage
