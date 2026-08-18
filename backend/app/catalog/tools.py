"""
Catalog Tools - the toolbox for the catalog-first retrieval agent

Draws a clear line between the free metadata tools and the expensive model
fetch, and adds tools for SPARQL execution, visualisation and calculation.
"""

import logging
import io
import base64
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Union

from .client import (
    CatalogClient,
    CatalogEntry,
    CatalogError,
    CatalogUnavailableError,
)
from .cache import ModelCache, CacheStats

logger = logging.getLogger(__name__)

# Catalog endpoint is derived from the dataspace configuration; see app/config.py.
from ..config import CATALOG_API_URL as DEFAULT_CATALOG_API_URL

CATALOG_SEARCH_TOP_K = 20  # How many candidates to surface to the agent

# =============================================================================
# MODULE-LEVEL CATALOG CACHE - survives between requests
# =============================================================================
_CATALOG_ENTRIES_CACHE: Dict[str, List["CatalogEntry"]] = {}

def get_cached_catalog_entries(catalog_url: str) -> Optional[List["CatalogEntry"]]:
    """Get cached catalog entries for a URL."""
    entries = _CATALOG_ENTRIES_CACHE.get(catalog_url)
    if entries:
        logger.info(f"[CatalogCache] Using cached {len(entries)} entries for {catalog_url[:50]}...")
    return entries

def set_cached_catalog_entries(catalog_url: str, entries: List["CatalogEntry"]) -> None:
    """Cache catalog entries for a URL."""
    _CATALOG_ENTRIES_CACHE[catalog_url] = entries
    logger.info(f"[CatalogCache] Cached {len(entries)} entries for {catalog_url[:50]}...")


# =============================================================================
# TOOL RESULT
# =============================================================================
@dataclass
class ToolResult:
    """The outcome of a single tool call."""
    success: bool
    data: Any
    message: str


# =============================================================================
# CATALOG TOOLS
# =============================================================================
class CatalogTools:
    """
    The toolbox for the catalog-first retrieval agent.

    Free metadata tools are kept distinct from the expensive model fetch.

    Token-based authentication for Solid-protected resources is optional.
    """

    def __init__(
        self,
        catalog_api_url: str = None,
        cache_path=None,
        memory_cache_size: int = 50,
        disk_cache_ttl: int = 86400,
        auth_token: Optional[str] = None,
        pre_loaded_catalog_entries: Optional[List["CatalogEntry"]] = None,
    ):
        self._catalog_client: Optional[CatalogClient] = None
        self._model_cache: Optional[ModelCache] = None
        self._catalog_entries: List[CatalogEntry] = pre_loaded_catalog_entries or []
        self._api_url = catalog_api_url or DEFAULT_CATALOG_API_URL
        self._cache_path = cache_path
        self._memory_cache_size = memory_cache_size
        self._disk_cache_ttl = disk_cache_ttl
        self._auth_token = auth_token
        self._fetch_count = 0  # Counts the expensive fetches

        if pre_loaded_catalog_entries:
            logger.info(f"[CatalogTools] Using {len(pre_loaded_catalog_entries)} pre-loaded catalog entries (no reload needed)")

    def set_auth_token(self, token: str) -> None:
        """Set the auth token used for authenticated requests."""
        self._auth_token = token
        # Reset client to apply new token
        if self._catalog_client:
            self._catalog_client.set_auth_token(token)

    def _get_catalog_client(self) -> CatalogClient:
        """Lazily create the catalog client, passing along the auth token if set."""
        if self._catalog_client is None:
            self._catalog_client = CatalogClient(
                api_url=self._api_url,
                auth_token=self._auth_token,
            )

            # Only probe availability when the seed catalog is all we have.
            # Under federation an unreachable seed pod must not sink the whole
            # request as long as other registered pods answer - that call is
            # made in _load_dataset_urls.
            if not self._catalog_client.uses_federation:
                if not self._catalog_client.is_available():
                    raise CatalogUnavailableError(
                        f"Catalog unreachable at {self._api_url}. "
                        "Check the network connection and authentication."
                    )

        return self._catalog_client

    def _get_model_cache(self) -> ModelCache:
        """Lazily create the model cache."""
        if self._model_cache is None:
            self._model_cache = ModelCache(
                catalog_client=self._get_catalog_client(),
                cache_path=self._cache_path,
                memory_size=self._memory_cache_size,
                disk_ttl_seconds=self._disk_cache_ttl,
            )
        return self._model_cache

    def _ensure_catalog_loaded(self):
        """Make sure the catalog entries have been loaded."""
        if not self._catalog_entries:
            # Check module-level cache first
            cached = get_cached_catalog_entries(self._api_url)
            if cached:
                self._catalog_entries = cached
            else:
                client = self._get_catalog_client()
                self._catalog_entries = client.get_all_datasets()
                logger.info(f"Loaded {len(self._catalog_entries)} catalog entries")
                # Save to module-level cache
                set_cached_catalog_entries(self._api_url, self._catalog_entries)

    async def _ensure_catalog_loaded_async(self):
        """Async version of _ensure_catalog_loaded."""
        if not self._catalog_entries:
            # Check module-level cache first
            cached = get_cached_catalog_entries(self._api_url)
            if cached:
                self._catalog_entries = cached
            else:
                client = self._get_catalog_client()
                self._catalog_entries = await client.get_all_datasets_async()
                logger.info(f"Loaded {len(self._catalog_entries)} catalog entries")
                # Save to module-level cache
                set_cached_catalog_entries(self._api_url, self._catalog_entries)

    def get_fetch_count(self) -> int:
        """Return how many expensive fetches have been made."""
        return self._fetch_count

    def get_catalog_entries(self) -> List[CatalogEntry]:
        """Return the loaded catalog entries so callers can cache them."""
        return self._catalog_entries

    def get_cache_stats(self) -> CacheStats:
        """Return the model cache statistics."""
        return self._get_model_cache().get_stats()

    # =========================================================================
    # TOOL 1: list_catalog_datasets (FREE)
    # =========================================================================
    def list_catalog_datasets(self) -> ToolResult:
        """
        List every dataset available in the catalog.
        FREE - metadata only, no model is fetched.
        """
        try:
            self._ensure_catalog_loaded()

            datasets = []
            for entry in self._catalog_entries:
                datasets.append({
                    "identifier": entry.identifier,
                    "title": entry.title,
                    "model_name": entry.model_name,
                    "theme": entry.theme,
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "count": len(datasets),
                    "datasets": datasets,
                },
                message=f"The catalog holds {len(datasets)} datasets"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in list_catalog_datasets: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    async def list_catalog_datasets_async(self) -> ToolResult:
        """Async version of list_catalog_datasets."""
        try:
            await self._ensure_catalog_loaded_async()

            datasets = []
            for entry in self._catalog_entries:
                datasets.append({
                    "identifier": entry.identifier,
                    "title": entry.title,
                    "model_name": entry.model_name,
                    "theme": entry.theme,
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "count": len(datasets),
                    "datasets": datasets,
                },
                message=f"The catalog holds {len(datasets)} datasets"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in list_catalog_datasets_async: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    # =========================================================================
    # TOOL 2: search_catalog (FREE)
    # =========================================================================
    def search_catalog(
        self,
        query: str,
        top_k: int = CATALOG_SEARCH_TOP_K,
    ) -> ToolResult:
        """
        Search the catalog metadata for relevant models.
        FREE - metadata only, no model is fetched.

        Searches across title, description, theme, classes and properties.
        """
        try:
            self._ensure_catalog_loaded()

            query_lower = query.lower()
            query_terms = [t for t in query_lower.split() if len(t) > 2]

            # Collect every entry with at least one match
            matching_entries = []

            for entry in self._catalog_entries:
                # Track which terms matched where
                matches = {
                    "in_title": [],
                    "in_description": [],
                    "in_classes": [],
                    "in_properties": [],
                }

                title_lower = entry.title.lower()
                desc_lower = (entry.description or "").lower()

                for term in query_terms:
                    if term in title_lower:
                        matches["in_title"].append(term)
                    if term in desc_lower:
                        matches["in_description"].append(term)
                    for cls in entry.classes:
                        if term in cls.lower():
                            matches["in_classes"].append(cls)
                    for prop in entry.properties:
                        if term in prop.lower():
                            matches["in_properties"].append(prop)

                # Keep the entry only if something matched
                has_match = any(len(v) > 0 for v in matches.values())
                if has_match:
                    matching_entries.append({
                        "entry": entry,
                        "matches": matches,
                        "match_count": sum(len(v) for v in matches.values()),
                    })

            # Best-matching entries first
            matching_entries.sort(key=lambda x: x["match_count"], reverse=True)

            # Shape the results for the agent
            results = []
            for item in matching_entries[:top_k]:
                entry = item["entry"]
                matches = item["matches"]
                results.append({
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title,
                    "description": entry.description[:200] if entry.description else "",
                    "theme": entry.theme,
                    "classes": entry.classes[:10],
                    "properties": entry.properties[:10],
                    "matches": {k: v for k, v in matches.items() if v},
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "search_terms": query_terms,
                    "total_found": len(matching_entries),
                    "showing": len(results),
                    "results": results,
                },
                message=f"Found {len(matching_entries)} entries with at least one match for '{query}'"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in search_catalog: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    async def search_catalog_async(
        self,
        query: str,
        top_k: int = CATALOG_SEARCH_TOP_K,
    ) -> ToolResult:
        """Async version of search_catalog."""
        try:
            await self._ensure_catalog_loaded_async()

            # Same logic as sync version
            query_lower = query.lower()
            query_terms = [t for t in query_lower.split() if len(t) > 2]

            matching_entries = []

            for entry in self._catalog_entries:
                matches = {
                    "in_title": [],
                    "in_description": [],
                    "in_classes": [],
                    "in_properties": [],
                }

                title_lower = entry.title.lower()
                desc_lower = (entry.description or "").lower()

                for term in query_terms:
                    if term in title_lower:
                        matches["in_title"].append(term)
                    if term in desc_lower:
                        matches["in_description"].append(term)
                    for cls in entry.classes:
                        if term in cls.lower():
                            matches["in_classes"].append(cls)
                    for prop in entry.properties:
                        if term in prop.lower():
                            matches["in_properties"].append(prop)

                has_match = any(len(v) > 0 for v in matches.values())
                if has_match:
                    matching_entries.append({
                        "entry": entry,
                        "matches": matches,
                        "match_count": sum(len(v) for v in matches.values()),
                    })

            matching_entries.sort(key=lambda x: x["match_count"], reverse=True)

            results = []
            for item in matching_entries[:top_k]:
                entry = item["entry"]
                matches = item["matches"]
                results.append({
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title,
                    "description": entry.description[:200] if entry.description else "",
                    "theme": entry.theme,
                    "classes": entry.classes[:10],
                    "properties": entry.properties[:10],
                    "matches": {k: v for k, v in matches.items() if v},
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "search_terms": query_terms,
                    "total_found": len(matching_entries),
                    "showing": len(results),
                    "results": results,
                },
                message=f"Found {len(matching_entries)} entries with at least one match for '{query}'"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in search_catalog_async: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    # =========================================================================
    # TOOL 3: get_catalog_entry (FREE)
    # =========================================================================
    def get_catalog_entry(self, identifier: str) -> ToolResult:
        """
        Show the detailed metadata of a single catalog entry.
        FREE - metadata only, no model is fetched.
        """
        try:
            self._ensure_catalog_loaded()

            # Search the entries already loaded
            entry = None
            for e in self._catalog_entries:
                if e.identifier == identifier or e.model_name == identifier:
                    entry = e
                    break

            if entry is None:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Dataset '{identifier}' not found"
                )

            return ToolResult(
                success=True,
                data={
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title,
                    "description": entry.description,
                    "theme": entry.theme,
                    "classes": entry.classes,
                    "properties": entry.properties,
                    "has_content": entry.has_content,
                    "access_url": entry.access_url,
                },
                message=f"Details for '{entry.model_name}'"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in get_catalog_entry: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    async def get_catalog_entry_async(self, identifier: str) -> ToolResult:
        """Async version of get_catalog_entry."""
        try:
            await self._ensure_catalog_loaded_async()

            entry = None
            for e in self._catalog_entries:
                if e.identifier == identifier or e.model_name == identifier:
                    entry = e
                    break

            if entry is None:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Dataset '{identifier}' not found"
                )

            return ToolResult(
                success=True,
                data={
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title,
                    "description": entry.description,
                    "theme": entry.theme,
                    "classes": entry.classes,
                    "properties": entry.properties,
                    "has_content": entry.has_content,
                    "access_url": entry.access_url,
                },
                message=f"Details for '{entry.model_name}'"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in get_catalog_entry_async: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    # =========================================================================
    # TOOL 4: fetch_model (EXPENSIVE!)
    # =========================================================================
    def fetch_model(self, identifier: str) -> ToolResult:
        """
        Retrieve the full content of a model.
        EXPENSIVE - this hits the network (results are cached).
        """
        try:
            self._ensure_catalog_loaded()

            # Find the matching entry
            entry = None
            for e in self._catalog_entries:
                if e.identifier == identifier or e.model_name == identifier:
                    entry = e
                    break

            if entry is None:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Dataset '{identifier}' not found"
                )

            # Record the fetch
            self._fetch_count += 1

            # Content comes through the cache
            cache = self._get_model_cache()
            cache_entry = cache.get(entry.identifier)

            return ToolResult(
                success=True,
                data={
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title or entry.model_name,
                    "data_url": entry.data_url,
                    "content": cache_entry.content,
                    "source": cache_entry.source,
                    "fetch_number": self._fetch_count,
                },
                message=f"Loaded model '{entry.model_name}' (fetch #{self._fetch_count}, source: {cache_entry.source})"
            )

        except CatalogError as e:
            logger.error(f"Fetch error: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Fetch error: {str(e)}"
            )

    async def fetch_model_async(self, identifier: str) -> ToolResult:
        """Async version of fetch_model."""
        try:
            await self._ensure_catalog_loaded_async()

            entry = None
            for e in self._catalog_entries:
                if e.identifier == identifier or e.model_name == identifier:
                    entry = e
                    break

            if entry is None:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Dataset '{identifier}' not found"
                )

            self._fetch_count += 1

            cache = self._get_model_cache()
            cache_entry = await cache.get_async(entry.identifier)

            return ToolResult(
                success=True,
                data={
                    "identifier": entry.identifier,
                    "model_name": entry.model_name,
                    "title": entry.title or entry.model_name,
                    "data_url": entry.data_url,
                    "content": cache_entry.content,
                    "source": cache_entry.source,
                    "fetch_number": self._fetch_count,
                },
                message=f"Loaded model '{entry.model_name}' (fetch #{self._fetch_count}, source: {cache_entry.source})"
            )

        except CatalogError as e:
            logger.error(f"Fetch error: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Fetch error: {str(e)}"
            )

    # =========================================================================
    # TOOL 5: get_corpus_overview (FREE) - replaces the old CORPUS_INFO handler
    # =========================================================================
    def get_corpus_overview(self) -> ToolResult:
        """
        Return an overview of every available dataset, plus some statistics.
        Replaces the old CORPUS_INFO handler and reads the remote catalog
        instead of local data.
        FREE - metadata only.
        """
        try:
            self._ensure_catalog_loaded()

            # Roll up the statistics
            themes: Dict[str, int] = {}
            total_with_content = 0

            for entry in self._catalog_entries:
                theme = entry.theme or "Uncategorised"
                themes[theme] = themes.get(theme, 0) + 1
                if entry.has_content:
                    total_with_content += 1

            # Shape the dataset list
            datasets = []
            for entry in self._catalog_entries:
                datasets.append({
                    "identifier": entry.identifier,
                    "title": entry.title,
                    "model_name": entry.model_name,
                    "theme": entry.theme,
                    "description": entry.description[:150] if entry.description else "",
                    "classes_count": len(entry.classes),
                    "properties_count": len(entry.properties),
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "total_datasets": len(datasets),
                    "datasets_with_content": total_with_content,
                    "themes": themes,
                    "datasets": datasets,
                },
                message=f"The catalog holds {len(datasets)} datasets across {len(themes)} categories"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in get_corpus_overview: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    async def get_corpus_overview_async(self) -> ToolResult:
        """Async version of get_corpus_overview."""
        try:
            await self._ensure_catalog_loaded_async()

            themes: Dict[str, int] = {}
            total_with_content = 0

            for entry in self._catalog_entries:
                theme = entry.theme or "Uncategorised"
                themes[theme] = themes.get(theme, 0) + 1
                if entry.has_content:
                    total_with_content += 1

            datasets = []
            for entry in self._catalog_entries:
                datasets.append({
                    "identifier": entry.identifier,
                    "title": entry.title,
                    "model_name": entry.model_name,
                    "theme": entry.theme,
                    "description": entry.description[:150] if entry.description else "",
                    "classes_count": len(entry.classes),
                    "properties_count": len(entry.properties),
                    "has_content": entry.has_content,
                })

            return ToolResult(
                success=True,
                data={
                    "total_datasets": len(datasets),
                    "datasets_with_content": total_with_content,
                    "themes": themes,
                    "datasets": datasets,
                },
                message=f"The catalog holds {len(datasets)} datasets across {len(themes)} categories"
            )

        except CatalogError as e:
            logger.error(f"Catalog error in get_corpus_overview_async: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Catalog error: {str(e)}"
            )

    # =========================================================================
    # TOOL 6: create_visualization (result tool)
    # =========================================================================
    def create_visualization(
        self,
        results: List[Dict[str, Any]],
        chart_type: str,
        x_column: str,
        y_column: str,
        title: str = ""
    ) -> ToolResult:
        """
        Build a chart from a set of results.

        Args:
            results: the result rows, as a list of dicts
            chart_type: which chart to draw ("bar", "line", "pie", "scatter")
            x_column: column to plot on the x axis
            y_column: column to plot on the y axis
            title: optional chart title

        Returns:
            A ToolResult carrying the base64-encoded image
        """
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt

            if not results:
                return ToolResult(
                    success=False,
                    data=None,
                    message="No data available to visualise"
                )

            # Pull the two series out of the results
            x_data = []
            y_data = []
            for r in results:
                x_val = r.get(x_column, "")
                y_val = r.get(y_column, 0)

                # Coerce the y value to a number where possible
                try:
                    y_val = float(y_val) if y_val else 0
                except (ValueError, TypeError):
                    y_val = 0

                x_data.append(str(x_val))
                y_data.append(y_val)

            # Draw the chart
            fig, ax = plt.subplots(figsize=(10, 6))

            if chart_type == "bar":
                ax.bar(x_data, y_data, color='steelblue')
                ax.set_xlabel(x_column)
                ax.set_ylabel(y_column)
            elif chart_type == "line":
                ax.plot(x_data, y_data, marker='o', color='steelblue')
                ax.set_xlabel(x_column)
                ax.set_ylabel(y_column)
            elif chart_type == "pie":
                ax.pie(y_data, labels=x_data, autopct='%1.1f%%')
            elif chart_type == "scatter":
                ax.scatter(range(len(x_data)), y_data, color='steelblue')
                ax.set_xticks(range(len(x_data)))
                ax.set_xticklabels(x_data, rotation=45, ha='right')
                ax.set_xlabel(x_column)
                ax.set_ylabel(y_column)
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Unknown chart type: {chart_type}"
                )

            if title:
                ax.set_title(title)
            plt.tight_layout()

            # Encode as base64 for transport
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=100)
            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)

            return ToolResult(
                success=True,
                data={
                    "image": image_base64,
                    "chart_type": chart_type,
                    "data_points": len(results),
                    "x_column": x_column,
                    "y_column": y_column
                },
                message=f"Created a {chart_type} chart from {len(results)} data points"
            )

        except ImportError:
            return ToolResult(
                success=False,
                data=None,
                message="matplotlib is not installed"
            )
        except Exception as e:
            logger.error(f"Visualization error: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Visualisation error: {str(e)}"
            )

    async def create_visualization_async(
        self,
        results: List[Dict[str, Any]],
        chart_type: str,
        x_column: str,
        y_column: str,
        title: str = ""
    ) -> ToolResult:
        """Async version of create_visualization."""
        import asyncio
        return await asyncio.to_thread(
            self.create_visualization,
            results, chart_type, x_column, y_column, title
        )

    # =========================================================================
    # TOOL 7: perform_calculation (result tool)
    # =========================================================================
    def perform_calculation(
        self,
        results: List[Dict[str, Any]],
        operation: str,
        column: str
    ) -> ToolResult:
        """
        Run an aggregation over a set of results.

        Args:
            results: the result rows, as a list of dicts
            operation: which aggregation to apply ("sum", "avg", "min", "max",
                "count", "median")
            column: the column to aggregate

        Returns:
            A ToolResult carrying the computed value
        """
        try:
            if not results:
                return ToolResult(
                    success=False,
                    data=None,
                    message="No data available to compute on"
                )

            # Collect the column's values, coerced to numbers
            values = []
            for r in results:
                val = r.get(column)
                if val is not None:
                    try:
                        values.append(float(val))
                    except (ValueError, TypeError):
                        pass

            if not values:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"No numeric values found in column '{column}'"
                )

            # Apply the requested aggregation
            result_value: Union[float, int]
            if operation == "sum":
                result_value = sum(values)
            elif operation == "avg":
                result_value = sum(values) / len(values)
            elif operation == "min":
                result_value = min(values)
            elif operation == "max":
                result_value = max(values)
            elif operation == "count":
                result_value = len(values)
            elif operation == "median":
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                mid = n // 2
                if n % 2 == 0:
                    result_value = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
                else:
                    result_value = sorted_vals[mid]
            else:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Unknown operation: {operation}"
                )

            return ToolResult(
                success=True,
                data={
                    "operation": operation,
                    "column": column,
                    "result": result_value,
                    "input_count": len(values),
                    "values_sample": values[:5]
                },
                message=f"{operation}({column}) = {result_value:.4f}" if isinstance(result_value, float) else f"{operation}({column}) = {result_value}"
            )

        except Exception as e:
            logger.error(f"Calculation error: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Calculation error: {str(e)}"
            )

    async def perform_calculation_async(
        self,
        results: List[Dict[str, Any]],
        operation: str,
        column: str
    ) -> ToolResult:
        """Async version of perform_calculation."""
        import asyncio
        return await asyncio.to_thread(
            self.perform_calculation,
            results, operation, column
        )

    def close(self):
        """Release the underlying resources."""
        if self._catalog_client:
            self._catalog_client.close()

    async def aclose(self):
        """Async close."""
        if self._catalog_client:
            await self._catalog_client.aclose()


# =============================================================================
# TOOL DESCRIPTIONS HANDED TO THE LLM
# =============================================================================
CATALOG_TOOL_DESCRIPTIONS = """
AVAILABLE TOOLS:

=== PREFERRED TOOLS (keyword search) ===

search_catalog(query: str, top_k: int = 20)
   Searches the catalog metadata for models matching your keywords.
   -> ALWAYS START HERE! Pull the specific keywords out of the request.
   -> Shows: title, description, classes, properties
   -> Results come back sorted by relevance
   -> Best results come from 2-3 specific keywords (places, topics, objects)
   -> DROP filler words such as: what, for, are, there, which, show, me, files

   EXAMPLES of good keyword extraction:
   - "what files are there about Rostock?" -> query="Rostock"
   - "show me charging stations in Wuppertal" -> query="charging stations Wuppertal"
   - "which data covers accidents on motorways?" -> query="accidents motorways"
   - "are there any bus stops?" -> query="bus stops"

get_catalog_entry(identifier: str)
   Shows the detailed metadata of one entry.
   -> Use it to inspect the details BEFORE you fetch
   -> identifier can be either the ID or the model_name

=== FALLBACK TOOLS (only when keyword search comes up empty) ===

list_catalog_datasets()
   Lists every dataset in the catalog.
   -> ONLY as a FALLBACK when search_catalog returns nothing!
   -> Or when the user explicitly asks for the complete list

get_corpus_overview()
   Summarises all datasets together with some statistics.
   -> ONLY as a FALLBACK when you have no idea what to search for
   -> Or when the user explicitly asks "what is in the catalog?"

=== EXPENSIVE TOOL (network fetch) ===

fetch_model(identifier: str)
   Retrieves the COMPLETE content of a model.
   -> EXPENSIVE! Only once the metadata looks genuinely promising.
   -> After every fetch ask yourself: is this enough, or do I need more?
   -> The result is cached for later access

=== RESULT TOOLS (after data extraction) ===

create_visualization(results: List[Dict], chart_type: str, x_column: str, y_column: str, title: str = "")
   Builds a chart from a set of results.
   -> chart_type: "bar", "line", "pie", "scatter"
   -> results: the results of an earlier SPARQL query
   -> x_column: column name for the x axis
   -> y_column: column name for the y axis (must be numeric)

perform_calculation(results: List[Dict], operation: str, column: str)
   Aggregates a set of results.
   -> operation: "sum", "avg", "min", "max", "count", "median"
   -> results: the results of an earlier SPARQL query
   -> column: the column to aggregate (must hold numeric values)

=== WRAPPING UP ===

finish(selected_models: List[str], reasoning: str)
   Ends the search with your chosen models and the reasoning behind them.
"""
