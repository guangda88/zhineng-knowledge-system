"""智能缓存系统

最大化复用AI响应，节省30-50%的API调用和Token消耗
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SmartCache:
    """智能缓存系统"""

    def __init__(
        self,
        cache_dir: str = "data/cache",
        ttl_hours: int = 48,  # 缓存48小时
        enable_disk_cache: bool = True,
        enable_memory_cache: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

        self.enable_disk = enable_disk_cache
        self.enable_memory = enable_memory_cache

        # 内存缓存
        self.memory_cache: Dict[str, Dict[str, Any]] = {}

        # 统计
        self.stats = {"hits": 0, "misses": 0, "saves": 0, "evictions": 0}

    def _get_cache_key(self, content: str, model: str = None) -> str:
        """生成缓存键"""
        # 包含日期以确保每日缓存独立
        key_content = f"{content}_{model}_{datetime.now().date()}"
        return hashlib.md5(key_content.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def get(self, prompt: str, model: str = "default") -> Optional[str]:
        """获取缓存"""

        key = self._get_cache_key(prompt, model)

        # 1. 尝试内存缓存
        if self.enable_memory and key in self.memory_cache:
            entry = self.memory_cache[key]

            # 检查是否过期
            timestamp = entry["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)

            if datetime.now() - timestamp < self.ttl:
                self.stats["hits"] += 1
                logger.info(f"✅ 内存缓存命中: {prompt[:50]}...")
                return entry["result"]
            else:
                # 过期，删除
                del self.memory_cache[key]
                self.stats["evictions"] += 1

        # 2. 尝试磁盘缓存
        if self.enable_disk:
            cache_path = self._get_cache_path(key)

            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 检查是否过期
                    cache_time_str = data["timestamp"]
                    cache_time = datetime.fromisoformat(cache_time_str)
                    if datetime.now() - cache_time < self.ttl:
                        # 同时缓存到内存
                        if self.enable_memory:
                            self.memory_cache[key] = data

                        self.stats["hits"] += 1
                        logger.info(f"✅ 磁盘缓存命中: {prompt[:50]}...")
                        return data["result"]
                    else:
                        # 过期，删除
                        cache_path.unlink()
                        self.stats["evictions"] += 1

                except Exception as e:
                    logger.warning(f"读取缓存失败: {e}")

        # 未命中
        self.stats["misses"] += 1
        return None

    def set(self, prompt: str, result: str, model: str = "default") -> bool:
        """设置缓存"""

        key = self._get_cache_key(prompt, model)

        data = {
            "prompt": prompt[:500],  # 只保存前500字符
            "result": result,
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }

        success = False

        # 1. 保存到内存
        if self.enable_memory:
            self.memory_cache[key] = data

        # 2. 保存到磁盘
        if self.enable_disk:
            cache_path = self._get_cache_path(key)

            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                success = True
                self.stats["saves"] += 1
                logger.debug(f"💾 缓存已保存: {prompt[:50]}...")

            except Exception as e:
                logger.error(f"保存缓存失败: {e}")

        return success

    def clear(self):
        """清空所有缓存"""
        # 清空内存缓存
        self.memory_cache.clear()

        # 清空磁盘缓存
        if self.enable_disk:
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink()

        logger.info("🗑️  缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total if total > 0 else 0

        return {
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "saves": self.stats["saves"],
            "evictions": self.stats["evictions"],
            "hit_rate": hit_rate,
            "total_requests": total,
            "memory_cache_size": len(self.memory_cache),
            "disk_cache_files": len(list(self.cache_dir.glob("*.json"))) if self.enable_disk else 0,
        }

    def cleanup_expired(self):
        """清理过期缓存"""
        if not self.enable_disk:
            return

        now = datetime.now()
        cleaned = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                cache_time = datetime.fromisoformat(data["timestamp"])

                # 如果过期，删除
                if now - cache_time > self.ttl:
                    cache_file.unlink()
                    cleaned += 1
                    self.stats["evictions"] += 1

            except Exception as e:
                logger.warning(f"清理缓存文件失败 {cache_file}: {e}")

        if cleaned > 0:
            logger.info(f"🧹 清理了 {cleaned} 个过期缓存文件")

    def format_stats(self) -> str:
        """格式化统计信息"""
        stats = self.get_stats()

        lines = [
            "📊 缓存统计",
            "=" * 50,
            f"总请求数: {stats['total_requests']:,}",
            f"命中次数: {stats['hits']:,}",
            f"未命中: {stats['misses']:,}",
            f"命中率: {stats['hit_rate']:.1%}",
            f"保存次数: {stats['saves']:,}",
            f"过期清理: {stats['evictions']:,}",
            "",
            f"内存缓存: {stats['memory_cache_size']:,} 条",
            f"磁盘缓存: {stats['disk_cache_files']:,} 个文件",
            "=" * 50,
        ]

        return "\n".join(lines)


# 全局单例
_cache_instance: SmartCache = None


def get_cache(ttl_hours: int = 48) -> SmartCache:
    """获取缓存实例"""
    global _cache_instance

    if _cache_instance is None:
        _cache_instance = SmartCache(ttl_hours=ttl_hours)

    return _cache_instance


# 便捷函数
def cached(prompt: str, model: str = "default") -> Optional[str]:
    """获取缓存（同步）"""
    cache = get_cache()
    return cache.get(prompt, model)


def cache_save(prompt: str, result: str, model: str = "default"):
    """保存缓存（同步）"""
    cache = get_cache()
    return cache.set(prompt, result, model)


async def cached_call(
    func, prompt: str, *args, use_cache: bool = True, model: str = "default", **kwargs
):
    """带缓存的异步调用"""

    # 1. 尝试从缓存获取
    if use_cache:
        cache = get_cache()
        cached_result = cache.get(prompt, model)

        if cached_result is not None:
            return cached_result

    # 2. 调用实际函数
    try:
        result = await func(prompt, *args, **kwargs)

        # 3. 保存到缓存
        if result and use_cache:
            cache = get_cache()
            cache.set(prompt, result, model)

        return result

    except Exception as e:
        logger.error(f"调用失败: {e}")
        raise


def clear_cache():
    """清空缓存"""
    cache = get_cache()
    cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计"""
    cache = get_cache()
    return cache.get_stats()


def cleanup_cache():
    """清理过期缓存"""
    cache = get_cache()
    cache.cleanup_expired()
