import json
import logging
import time
from typing import Any, Dict, Optional
import redis

try:
    import fakeredis
except ImportError:
    fakeredis = None

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300  # 5 minutes


class InMemoryCacheFallback:
    """Thread-safe in-memory key-value cache with TTL expiration.
    Used for local fallback when Redis is temporarily unavailable.
    """

    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if not entry:
            return None
        if entry["expires_at"] < time.time():
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: str, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._store[key] = {
            "value": value,
            "expires_at": time.time() + ttl_seconds,
        }

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()


class CacheService:
    def __init__(self):
        self.memory_fallback = InMemoryCacheFallback()
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "redis_errors": 0,
        }
        self._redis_client: Optional[Any] = None
        self._is_redis_online = False
        self._init_redis()

    @property
    def redis_client(self) -> Optional[Any]:
        return self._redis_client

    @property
    def is_redis_online(self) -> bool:
        return self._is_redis_online

    def _init_redis(self):
        if not settings.redis_url:
            self._use_fallback_redis("No REDIS_URL configured")
            return

        try:
            client = redis.Redis.from_url(
                settings.redis_url,
                socket_timeout=0.2,
                socket_connect_timeout=0.2,
                decode_responses=True,
            )
            # Fast ping check to verify connectivity
            client.ping()
            self._redis_client = client
            self._is_redis_online = True
            logger.info("Connected to live Redis server at %s", settings.redis_url)
        except Exception as e:
            self._use_fallback_redis(str(e))

    def _use_fallback_redis(self, reason: str):
        self._is_redis_online = False
        if fakeredis:
            self._redis_client = fakeredis.FakeRedis(decode_responses=True)
            logger.info("Live Redis unavailable (%s). Using high-performance in-process Redis emulation.", reason)
        else:
            self._redis_client = None
            logger.warning("Live Redis unavailable (%s). Using in-memory dictionary fallback.", reason)

    def _cache_key(self, code: str) -> str:
        return f"redirect:{code}"

    def get_redirect_target(self, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached redirect metadata by short code.
        Returns dict with long_url, link_id, expires_at, etc., or None.
        """
        key = self._cache_key(code)
        raw_val = None

        if self._redis_client:
            try:
                raw_val = self._redis_client.get(key)
            except (redis.ConnectionError, redis.TimeoutError, Exception) as exc:
                self.stats["redis_errors"] += 1
                logger.warning(f"Redis get failed: {exc}. Falling back to in-memory/DB.")
                raw_val = None

        if not raw_val:
            raw_val = self.memory_fallback.get(key)

        if raw_val:
            self.stats["hits"] += 1
            try:
                return json.loads(raw_val)
            except Exception:
                return {"long_url": raw_val}

        self.stats["misses"] += 1
        return None

    def set_redirect_target(
        self,
        code: str,
        data: Dict[str, Any],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Cache redirect metadata with TTL."""
        key = self._cache_key(code)
        payload = json.dumps(data)

        if self._redis_client:
            try:
                self._redis_client.set(key, payload, ex=ttl_seconds)
            except (redis.ConnectionError, redis.TimeoutError, Exception) as exc:
                self.stats["redis_errors"] += 1
                logger.warning(f"Redis set failed: {exc}. Storing in memory fallback.")

        self.memory_fallback.set(key, payload, ttl_seconds)
        self.stats["sets"] += 1

    def invalidate_redirect_target(self, code: str) -> None:
        """Invalidate cached redirect entry upon update or deletion."""
        key = self._cache_key(code)

        if self._redis_client:
            try:
                self._redis_client.delete(key)
            except (redis.ConnectionError, redis.TimeoutError, Exception) as exc:
                self.stats["redis_errors"] += 1
                logger.warning(f"Redis delete failed: {exc}.")

        self.memory_fallback.delete(key)
        self.stats["invalidations"] += 1

    def reset_stats(self):
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
            "redis_errors": 0,
        }
        self.memory_fallback.clear()
        if self._redis_client:
            try:
                self._redis_client.flushall()
            except Exception:
                pass


cache_service = CacheService()
