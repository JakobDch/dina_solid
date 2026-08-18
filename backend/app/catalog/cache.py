"""
Model Cache - three-level cache for retrieved semantic models

L1: in-memory LRU cache (fast, bounded)
L2: disk cache (persistent, TTL-based)
L3: remote fetch (through CatalogClient)
"""

import hashlib
import json
import time
import logging
import aiofiles
import aiofiles.os
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

from .client import CatalogClient, ModelFetchError

logger = logging.getLogger(__name__)


# =============================================================================
# CACHE ENTRY
# =============================================================================
@dataclass
class CacheEntry:
    """A single cache entry along with its metadata."""
    identifier: str
    model_name: str
    content: str
    fetched_at: float  # Unix timestamp
    source: str  # "memory", "disk", "remote"

    def is_expired(self, ttl_seconds: int) -> bool:
        """Return True once the entry has outlived the given TTL."""
        return (time.time() - self.fetched_at) > ttl_seconds


# =============================================================================
# CACHE STATS
# =============================================================================
@dataclass
class CacheStats:
    """Usage statistics for the cache."""
    memory_hits: int = 0
    disk_hits: int = 0
    remote_fetches: int = 0
    memory_size: int = 0
    disk_size: int = 0

    def hit_rate(self) -> float:
        """Compute the ratio of hits to total lookups."""
        total = self.memory_hits + self.disk_hits + self.remote_fetches
        if total == 0:
            return 0.0
        return (self.memory_hits + self.disk_hits) / total


# =============================================================================
# MODEL CACHE
# =============================================================================
class ModelCache:
    """
    Three-level cache for semantic models.

    L1 (memory): fast lookups, LRU eviction
    L2 (disk): persistent cache with a TTL
    L3 (remote): fetched from the catalog / Solid Pod
    """

    def __init__(
        self,
        catalog_client: CatalogClient,
        cache_path: Path = None,
        memory_size: int = 50,
        disk_ttl_seconds: int = 86400,  # 24 hours
        max_disk_size_mb: int = 500,
    ):
        """
        Initialise the cache.

        Args:
            catalog_client: client used for remote fetches
            cache_path: directory backing the disk cache
            memory_size: maximum number of entries kept in memory
            disk_ttl_seconds: TTL of disk cache entries, in seconds
            max_disk_size_mb: upper bound on the disk cache size, in MB
        """
        self.catalog_client = catalog_client
        self.memory_size = memory_size
        self.disk_ttl = disk_ttl_seconds
        self.max_disk_size = max_disk_size_mb * 1024 * 1024  # Bytes

        # L1: memory cache (an OrderedDict gives us LRU ordering)
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # L2: Disk Cache
        self.cache_path = cache_path or Path(__file__).parent.parent.parent / "storage" / "model_cache"
        self.cache_path.mkdir(parents=True, exist_ok=True)

        # Usage counters
        self.stats = CacheStats()

    def get(self, identifier: str) -> CacheEntry:
        """
        Return a model from the cache, falling back to a remote fetch (sync).

        Args:
            identifier: the model's catalog ID

        Returns:
            A CacheEntry holding the model content

        Raises:
            ModelFetchError: if the model cannot be retrieved
        """
        # L1: Memory Cache
        entry = self._get_from_memory(identifier)
        if entry:
            self.stats.memory_hits += 1
            logger.debug(f"Cache hit (memory): {identifier}")
            return entry

        # L2: Disk Cache
        entry = self._get_from_disk(identifier)
        if entry:
            self.stats.disk_hits += 1
            logger.debug(f"Cache hit (disk): {identifier}")
            # Promote to L1
            self._put_to_memory(entry)
            return entry

        # L3: Remote Fetch
        logger.info(f"Cache miss, fetching from remote: {identifier}")
        entry = self._fetch_remote(identifier)
        self.stats.remote_fetches += 1

        # Populate L1 and L2
        self._put_to_memory(entry)
        self._put_to_disk(entry)

        return entry

    async def get_async(self, identifier: str) -> CacheEntry:
        """
        Return a model from the cache, falling back to a remote fetch (async).
        """
        # L1: Memory Cache
        entry = self._get_from_memory(identifier)
        if entry:
            self.stats.memory_hits += 1
            logger.debug(f"Cache hit (memory): {identifier}")
            return entry

        # L2: Disk Cache (async)
        entry = await self._get_from_disk_async(identifier)
        if entry:
            self.stats.disk_hits += 1
            logger.debug(f"Cache hit (disk): {identifier}")
            self._put_to_memory(entry)
            return entry

        # L3: Remote Fetch (async)
        logger.info(f"Cache miss, fetching from remote: {identifier}")
        entry = await self._fetch_remote_async(identifier)
        self.stats.remote_fetches += 1

        # Populate L1 and L2
        self._put_to_memory(entry)
        await self._put_to_disk_async(entry)

        return entry

    def get_content(self, identifier: str) -> str:
        """
        Convenience wrapper that returns just the model content.
        """
        return self.get(identifier).content

    async def get_content_async(self, identifier: str) -> str:
        """Async version of get_content."""
        entry = await self.get_async(identifier)
        return entry.content

    def prefetch(self, identifiers: list) -> Dict[str, bool]:
        """
        Warm the cache with several models up front.
        """
        results = {}
        for identifier in identifiers:
            try:
                self.get(identifier)
                results[identifier] = True
            except Exception as e:
                logger.warning(f"Prefetch failed for {identifier}: {e}")
                results[identifier] = False
        return results

    async def prefetch_async(self, identifiers: list) -> Dict[str, bool]:
        """Async version of prefetch."""
        results = {}
        for identifier in identifiers:
            try:
                await self.get_async(identifier)
                results[identifier] = True
            except Exception as e:
                logger.warning(f"Prefetch failed for {identifier}: {e}")
                results[identifier] = False
        return results

    def invalidate(self, identifier: str):
        """Drop a model from every cache level."""
        # L1
        if identifier in self._memory_cache:
            del self._memory_cache[identifier]

        # L2
        cache_file = self._get_disk_path(identifier)
        if cache_file.exists():
            cache_file.unlink()

    def clear(self):
        """Wipe the cache entirely."""
        self._memory_cache.clear()

        for cache_file in self.cache_path.glob("*.json"):
            cache_file.unlink()

        self.stats = CacheStats()

    def get_stats(self) -> CacheStats:
        """Return the current cache statistics."""
        self.stats.memory_size = len(self._memory_cache)
        self.stats.disk_size = len(list(self.cache_path.glob("*.json")))
        return self.stats

    # =========================================================================
    # L1: MEMORY CACHE
    # =========================================================================

    def _get_from_memory(self, identifier: str) -> Optional[CacheEntry]:
        """Look up an entry in the memory cache, refreshing its LRU position."""
        if identifier in self._memory_cache:
            # Move to end (most recently used)
            entry = self._memory_cache.pop(identifier)
            self._memory_cache[identifier] = entry
            return entry
        return None

    def _put_to_memory(self, entry: CacheEntry):
        """Store an entry in the memory cache, evicting the least recent if full."""
        # Evict if full
        while len(self._memory_cache) >= self.memory_size:
            self._memory_cache.popitem(last=False)  # Remove oldest

        entry.source = "memory"
        self._memory_cache[entry.identifier] = entry

    # =========================================================================
    # L2: DISK CACHE (sync)
    # =========================================================================

    def _get_disk_path(self, identifier: str) -> Path:
        """Build the file path backing a given cache entry."""
        # Hash the identifier so the filename is always filesystem-safe
        safe_name = hashlib.md5(identifier.encode()).hexdigest()
        return self.cache_path / f"{safe_name}.json"

    def _get_from_disk(self, identifier: str) -> Optional[CacheEntry]:
        """Read an entry from the disk cache, honouring the TTL."""
        cache_file = self._get_disk_path(identifier)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            entry = CacheEntry(
                identifier=data["identifier"],
                model_name=data["model_name"],
                content=data["content"],
                fetched_at=data["fetched_at"],
                source="disk",
            )

            # Expired entries are removed rather than returned
            if entry.is_expired(self.disk_ttl):
                cache_file.unlink()
                return None

            return entry

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Corrupt cache file {cache_file}: {e}")
            cache_file.unlink()
            return None

    def _put_to_disk(self, entry: CacheEntry):
        """Write an entry to the disk cache, respecting the size limit."""
        # Make room first if we are over budget
        self._enforce_disk_limit()

        cache_file = self._get_disk_path(entry.identifier)

        data = {
            "identifier": entry.identifier,
            "model_name": entry.model_name,
            "content": entry.content,
            "fetched_at": entry.fetched_at,
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def _enforce_disk_limit(self):
        """Evict the oldest entries once the disk budget is exceeded."""
        cache_files = list(self.cache_path.glob("*.json"))

        # Current total footprint on disk
        total_size = sum(f.stat().st_size for f in cache_files)

        if total_size <= self.max_disk_size:
            return

        # Oldest modification time first
        cache_files.sort(key=lambda f: f.stat().st_mtime)

        # Delete until we are comfortably below the limit (target: 80%)
        while total_size > self.max_disk_size * 0.8 and cache_files:
            oldest = cache_files.pop(0)
            total_size -= oldest.stat().st_size
            oldest.unlink()

    # =========================================================================
    # L2: DISK CACHE (Async)
    # =========================================================================

    async def _get_from_disk_async(self, identifier: str) -> Optional[CacheEntry]:
        """Async version of _get_from_disk."""
        cache_file = self._get_disk_path(identifier)

        if not cache_file.exists():
            return None

        try:
            async with aiofiles.open(cache_file, "r", encoding="utf-8") as f:
                content = await f.read()
                data = json.loads(content)

            entry = CacheEntry(
                identifier=data["identifier"],
                model_name=data["model_name"],
                content=data["content"],
                fetched_at=data["fetched_at"],
                source="disk",
            )

            if entry.is_expired(self.disk_ttl):
                await aiofiles.os.remove(cache_file)
                return None

            return entry

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Corrupt cache file {cache_file}: {e}")
            await aiofiles.os.remove(cache_file)
            return None

    async def _put_to_disk_async(self, entry: CacheEntry):
        """Async version of _put_to_disk."""
        self._enforce_disk_limit()  # Sync operation is fine here

        cache_file = self._get_disk_path(entry.identifier)

        data = {
            "identifier": entry.identifier,
            "model_name": entry.model_name,
            "content": entry.content,
            "fetched_at": entry.fetched_at,
        }

        async with aiofiles.open(cache_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False))

    # =========================================================================
    # L3: REMOTE FETCH
    # =========================================================================

    def _fetch_remote(self, identifier: str) -> CacheEntry:
        """
        Fetch a model from the catalog / Solid Pod (sync).
        """
        # Metadata first
        catalog_entry = self.catalog_client.get_dataset(identifier)

        # Then the actual content
        content = self.catalog_client.fetch_model_content(identifier)

        return CacheEntry(
            identifier=identifier,
            model_name=catalog_entry.model_name,
            content=content,
            fetched_at=time.time(),
            source="remote",
        )

    async def _fetch_remote_async(self, identifier: str) -> CacheEntry:
        """
        Fetch a model from the catalog / Solid Pod (async).
        """
        # Metadata first
        catalog_entry = await self.catalog_client.get_dataset_async(identifier)

        # Then the actual content
        content = await self.catalog_client.fetch_model_content_async(identifier)

        return CacheEntry(
            identifier=identifier,
            model_name=catalog_entry.model_name,
            content=content,
            fetched_at=time.time(),
            source="remote",
        )
