import logging
from typing import List, Dict, Any

from src.graph.neo4j_driver import run_query
from src.cache.redis_cache import get_cache, set_key

logger = logging.getLogger(__name__)

CACHE_TTL = 1800  # 30 minutes

async def get_root_causes(node_id: str) -> List[Dict[str, Any]]:
    """Return upstream nodes that may be the root cause of the given node.

    Steps:
    1. Check Redis cache (key: ``root_cause:{node_id}``).
    2. If cache miss, run a Cypher query that finds all distinct upstream nodes (any depth).
    3. Cache the result for ``CACHE_TTL`` seconds.
    """
    cache_key = f"root_cause:{node_id}"
    cache = await get_cache()
    cached = await cache.get(cache_key)
    if cached:
        logger.debug("Root cause cache hit for %s", node_id)
        return cached

    cypher = """
    MATCH (upstream)-[*]->(target)
    WHERE target.id = $node_id
    RETURN DISTINCT upstream { .*, id: id(upstream) } AS node
    """
    result = run_query(cypher, parameters={"node_id": node_id})
    causes = [record["node"] for record in result]
    await set_key(cache_key, causes, ttl=CACHE_TTL)
    logger.info("Root cause cache set for %s (size=%d)", node_id, len(causes))
    return causes
