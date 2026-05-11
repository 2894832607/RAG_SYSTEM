"""
Redis 缓存管理器

Spec: specs/001-model-api-config/spec.md §Redis 缓存扩展
提供统一的 get / set / delete / is_connected 接口，业务模块不直接依赖 redis 包。

配置读取（来自环境变量）：
  REDIS_HOST  — Redis 连接地址，默认 localhost
  REDIS_PORT  — Redis 端口，默认 6379
  REDIS_DB    — Redis DB 索引，默认 0
  REDIS_PASSWORD — Redis 密码（可选）

降级策略：
  若 Redis 不可用（未部署、连接超时），所有方法静默失败并返回 None / False，
  不影响主业务链路。
"""

import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis as redis_lib
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    logger.warning("redis 包未安装，缓存功能已禁用。运行 pip install redis>=4.5.0 以启用。")


class RedisCache:
    """轻量级 Redis 缓存客户端。

    所有方法均捕获异常并静默降级，确保 Redis 不可用时系统正常运行。
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
    ) -> None:
        self._host     = host     or os.getenv("REDIS_HOST", "localhost")
        self._port     = port     or int(os.getenv("REDIS_PORT", "6379"))
        self._db       = db       if db is not None else int(os.getenv("REDIS_DB", "0"))
        self._password = password or os.getenv("REDIS_PASSWORD") or None
        self._client: Any = None
        self._last_connected: bool = False
        self._last_checked_monotonic: float = 0.0
        self._connect()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        if not _REDIS_AVAILABLE:
            return
        try:
            self._client = redis_lib.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                socket_connect_timeout=0.5,
                socket_timeout=1,
                decode_responses=False,
                retry_on_timeout=False,
                retry_on_error=[],
            )
        except Exception as exc:
            logger.debug("Redis 初始化失败（将以无缓存模式运行）：%s", exc)
            self._client = None

    def is_connected(self) -> bool:
        """探测 Redis 连接是否可用。"""
        if self._client is None:
            return False
        try:
            self._client.ping()
            return True
        except KeyboardInterrupt:
            raise  # 透传中断信号，让进程正常退出
        except BaseException:
            return False

    def get_connection_state(self, max_age_sec: float = 30.0) -> bool:
        now = time.monotonic()
        if now - self._last_checked_monotonic <= max_age_sec:
            return self._last_connected
        connected = self.is_connected()
        self._last_connected = connected
        self._last_checked_monotonic = now
        return connected

    # ------------------------------------------------------------------
    # 核心操作
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """从缓存按 key 读取值，未命中或异常时返回 None。"""
        if self._client is None:
            return None
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.debug("缓存 GET 失败 key=%s: %s", key, exc)
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """将值序列化后写入缓存，ttl 单位为秒。ttl=-1 表示永不过期。

        Returns:
            True 表示成功，False 表示失败（降级）。
        """
        if self._client is None:
            return False
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl == -1:
                self._client.set(key, serialized)
            else:
                self._client.setex(key, ttl, serialized)
            return True
        except Exception as exc:
            logger.debug("缓存 SET 失败 key=%s: %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        """删除缓存 key。"""
        if self._client is None:
            return False
        try:
            return bool(self._client.delete(key))
        except Exception as exc:
            logger.debug("缓存 DELETE 失败 key=%s: %s", key, exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """按 glob 模式批量删除（慎用，O(N)）。返回删除数量。"""
        if self._client is None:
            return 0
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as exc:
            logger.debug("缓存 DELETE_PATTERN 失败 pattern=%s: %s", pattern, exc)
            return 0


# 全局单例（惰性初始化）
_cache_instance: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    """获取全局 RedisCache 单例（首次调用时初始化）。"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache()
    return _cache_instance
