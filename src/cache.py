# src/cache.py
import json
import redis
from functools import wraps
import inspect
from typing import Any, Callable, Dict, Optional, TypeVar
from sqlalchemy.orm import Session
from src.config import settings

# Create Redis connection
redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=0,
    decode_responses=True
)

T = TypeVar('T')


def cache_data(key_prefix: str, expire_time: int = 3600):
    """
    Decorator for caching function results in Redis

    Args:
        key_prefix: Prefix for the cache key
        expire_time: Time in seconds before cache expires
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key - exclude database sessions and self
            key_parts = []

            # Handle args - skip self and database sessions
            start_idx = 1 if args and hasattr(args[0], '__class__') else 0
            for arg in args[start_idx:]:
                if not isinstance(arg, Session):  # Skip database sessions
                    key_parts.append(str(arg))

            # Handle kwargs - exclude database sessions
            for k, v in sorted(kwargs.items()):
                if not isinstance(v, Session):
                    key_parts.append(f"{k}={v}")

            cache_key = f"{key_prefix}:{':'.join(key_parts)}"
            print(f"Cache key: {cache_key}")

            # Try to get from cache
            cached_data = redis_client.get(cache_key)
            if cached_data:
                print(f"Cache hit for key: {cache_key}")
                try:
                    return json.loads(cached_data)
                except json.JSONDecodeError:
                    print("Failed to decode cached data")
                    pass

            print(f"Cache miss for key: {cache_key}")

            # Execute function
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Cache result
            if result:
                try:
                    # Convert SQLAlchemy model to dict
                    if hasattr(result, '__dict__'):
                        cache_data = {}
                        for key, value in result.__dict__.items():
                            if not key.startswith('_'):
                                cache_data[key] = value
                    else:
                        cache_data = result

                    serialized = json.dumps(cache_data, default=str)
                    redis_client.setex(cache_key, expire_time, serialized)
                    print(f"Cached data for key: {cache_key}")
                except Exception as e:
                    print(f"Failed to cache data: {e}")

            return result

        return async_wrapper

    return decorator


def invalidate_cache(key_pattern: str):
    """Clear cache entries matching the given pattern"""
    keys = redis_client.keys(key_pattern)
    if keys:
        redis_client.delete(*keys)