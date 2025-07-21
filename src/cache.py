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


def serialize_model_with_relationships(obj):
    """Serialize SQLAlchemy model with its relationships"""
    if not hasattr(obj, '__dict__'):
        return obj

    result = {}
    for key, value in obj.__dict__.items():
        if key.startswith('_'):
            continue
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Handle relationships (lists)
            result[key] = [serialize_model_with_relationships(item) for item in value]
        elif hasattr(value, '__dict__'):
            # Handle single relationship
            result[key] = serialize_model_with_relationships(value)
        else:
            result[key] = value
    return result


def reconstruct_model_with_relationships(model_class, data_dict):
    """Reconstruct SQLAlchemy model with relationships from dict"""
    # Import zone model to handle relationship reconstruction
    from src.entities.zone import Zone

    # Separate main model data from relationship data
    main_data = {}
    relationship_data = {}

    # Get relationship names from the model
    if hasattr(model_class, '__mapper__'):
        relationship_names = [rel.key for rel in model_class.__mapper__.relationships]
    else:
        relationship_names = []

    for key, value in data_dict.items():
        if key in relationship_names:
            relationship_data[key] = value
        else:
            main_data[key] = value

    # Create main model instance
    instance = model_class(**main_data)

    # Set relationships - reconstruct as proper model instances
    for rel_name, rel_data in relationship_data.items():
        if isinstance(rel_data, list):
            # Handle one-to-many relationships (like zones)
            if rel_name == 'zones':
                # Convert dict data back to Zone instances
                zone_instances = []
                for zone_dict in rel_data:
                    zone_instance = Zone(**zone_dict)
                    zone_instances.append(zone_instance)
                setattr(instance, rel_name, zone_instances)
            else:
                setattr(instance, rel_name, rel_data)
        else:
            # Handle one-to-one relationships
            setattr(instance, rel_name, rel_data)

    return instance


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
            repo_instance = args[0] if args and hasattr(args[0], 'model') else None

            if use_result_id:
                if inspect.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if result and hasattr(result, 'id'):
                    cache_key = f"{result.id}"
                else:
                    return result

                print(f"Cache key (from result): {cache_key}")

                try:
                    # Handle both Pydantic models and SQLAlchemy models
                    if hasattr(result, 'dict'):  # Pydantic model
                        cache_data = result.dict()
                        cache_data['_cached_type'] = 'TicketDetail'
                    else:  # SQLAlchemy model
                        cache_data = serialize_model_with_relationships(result)
                        cache_data['_cached_type'] = type(result).__name__

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

            cached_data = redis_client.get(cache_key)
            if cached_data:
                print(f"Cache hit for key: {cache_key}")
                try:
                    data_dict = json.loads(cached_data)
                    cached_type = data_dict.pop('_cached_type', None)

                    if cached_type == 'TicketDetail':
                        from src.dto.ticket import TicketDetail
                        return TicketDetail(**data_dict)
                    elif repo_instance and hasattr(repo_instance, 'model'):
                        return reconstruct_model_with_relationships(repo_instance.model, data_dict)
                    return data_dict
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"Failed to decode cached data: {e}")
                    redis_client.delete(cache_key)  # Clear corrupted cache

            print(f"Cache miss for key: {cache_key}")

            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            if result:
                try:
                    # Handle both Pydantic models and SQLAlchemy models
                    if hasattr(result, 'dict'):  # Pydantic model
                        cache_data = result.dict()
                        cache_data['_cached_type'] = 'TicketDetail'
                    else:  # SQLAlchemy model
                        cache_data = serialize_model_with_relationships(result)
                        cache_data['_cached_type'] = type(result).__name__

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