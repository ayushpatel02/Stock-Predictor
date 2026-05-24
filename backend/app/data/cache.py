"""
In-memory cache layer with optional Redis backend.
Falls back to a simple dict cache when Redis is unavailable.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Simple in-process cache: key -> (value, expiry_timestamp)
_MEMORY_CACHE: dict[str, tuple[Any, float]] = {}

_redis_client = None


def _get_redis():
    """Lazy-initialise Redis client if REDIS_URL is configured."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        from app.config import settings

        if not settings.redis_url:
            return None
        # redis-py is optional — import only if configured
        import redis  # type: ignore

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis cache connected")
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable, using in-memory cache: %s", exc)
        return None


def get(key: str) -> Any | None:
    """Retrieve a cached value; returns None on miss or expiry."""
    r = _get_redis()
    if r:
        try:
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception:
            pass

    entry = _MEMORY_CACHE.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        del _MEMORY_CACHE[key]
        return None
    return value


def set(key: str, value: Any, ttl_seconds: int = 300) -> None:  # noqa: A001
    """Store a value with a TTL (default 5 minutes)."""
    r = _get_redis()
    if r:
        try:
            r.setex(key, ttl_seconds, json.dumps(value, default=str))
            return
        except Exception:
            pass

    _MEMORY_CACHE[key] = (value, time.time() + ttl_seconds)


def invalidate(key: str) -> None:
    """Remove a cache entry."""
    r = _get_redis()
    if r:
        try:
            r.delete(key)
        except Exception:
            pass
    _MEMORY_CACHE.pop(key, None)
