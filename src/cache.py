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


def cache_data(expire_time: int = 3600, use_result_id: bool = False):
    """
    Decorator for caching function results in Redis

    Args:
        expire_time: Time in seconds before cache expires
        use_result_id: If True, use the result's ID field for cache key (for create operations)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get the model class from the repository instance
            repo_instance = args[0] if args and hasattr(args[0], 'model') else None
            # Execute function first if use_result_id is True
            if use_result_id:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Generate cache key from result's ID
                if result and hasattr(result, 'id'):
                    cache_key = f"{result.id}"
                else:
                    return result

                print(f"Cache key (from result): {cache_key}")

                # Cache the result
                try:
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

            # Original caching logic for get operations
            key_parts = []
            start_idx = 1 if args and hasattr(args[0], '__class__') else 0
            for arg in args[start_idx:]:
                if not isinstance(arg, Session):
                    key_parts.append(str(arg))

            for k, v in sorted(kwargs.items()):
                if not isinstance(v, Session):
                    key_parts.append(f"{k}={v}")

            cache_key = f"{''.join(key_parts)}"
            print(f"Cache key: {cache_key}")

            # Try to get from cache
            cached_data = redis_client.get(cache_key)
            if cached_data:
                print(f"Cache hit for key: {cache_key}")
                try:
                    data_dict = json.loads(cached_data)
                    # Reconstruct the model object if we have a repository instance
                    if repo_instance and hasattr(repo_instance, 'model'):
                        return repo_instance.model(**data_dict)
                    return data_dict
                except (json.JSONDecodeError, TypeError):
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
    # Use SCAN instead of KEYS for better performance
    cursor = 0
    keys_to_delete = []
    while True:
        cursor, keys = redis_client.scan(cursor, match=key_pattern, count=100)
        keys_to_delete.extend(keys)
        if cursor == 0:
            break

    if keys_to_delete:
        redis_client.delete(*keys_to_delete)
        print(f"Invalidated {len(keys_to_delete)} cache entries")


def update_cache(key: str, data: Any, expire_time: int = 3600):
    """Update cache with new data"""
    try:
        if hasattr(data, '__dict__'):
            cache_data = {}
            for k, v in data.__dict__.items():
                if not k.startswith('_'):
                    cache_data[k] = v
        else:
            cache_data = data

        serialized = json.dumps(cache_data, default=str)
        redis_client.setex(key, expire_time, serialized)
        print(f"Updated cache for key: {key}")
    except Exception as e:
        print(f"Failed to update cache: {e}")