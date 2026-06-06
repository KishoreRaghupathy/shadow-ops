import os
import logging
from typing import Any
import asyncio

from aioredis import from_url, Redis

logger = logging.getLogger(__name__)

_redis: Redis | None = None

async def _init_redis() -> Redis:
    global _redis
    if _redis is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            _redis = await from_url(redis_url, decode_responses=True)
            logger.info(f"Connected to Redis at {redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis at {redis_url}: {e}")
            raise e
    return _redis

async def get_cache() -> Redis:
    """Return a singleton Redis client (initializes on first call)."""
    return await _init_redis()

async def set_key(key: str, value: Any, ttl: int = 1800) -> bool:
    try:
        client = await get_cache()
        await client.set(key, value, ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"Redis set failed for {key}: {e}")
        return False

async def get_key(key: str) -> Any:
    try:
        client = await get_cache()
        return await client.get(key)
    except Exception as e:
        logger.warning(f"Redis get failed for {key}: {e}")
        return None
