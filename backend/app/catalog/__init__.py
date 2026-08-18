"""
Catalog-First Retrieval Module

Provides agent-driven retrieval over the DCAT data catalog.
The agent decides which semantic models to fetch based on metadata.

Includes the UnifiedCatalogAgent that handles all catalog operations:
- Dataset discovery (replaces CORPUS_INFO)
- Semantic model retrieval
- Visualization
- Calculations
"""

from .client import (
    CatalogClient,
    CatalogEntry,
    CatalogError,
    CatalogUnavailableError,
    CatalogEntryNotFoundError,
    ModelFetchError,
)
from .cache import ModelCache, CacheEntry, CacheStats
from .tools import CatalogTools, ToolResult, CATALOG_TOOL_DESCRIPTIONS
from .retriever import CatalogAgenticRetriever, AgentResult, AgentStep
from .unified_agent import UnifiedCatalogAgent, UnifiedAgentResult

__all__ = [
    # Client
    "CatalogClient",
    "CatalogEntry",
    "CatalogError",
    "CatalogUnavailableError",
    "CatalogEntryNotFoundError",
    "ModelFetchError",
    # Cache
    "ModelCache",
    "CacheEntry",
    "CacheStats",
    # Tools
    "CatalogTools",
    "ToolResult",
    "CATALOG_TOOL_DESCRIPTIONS",
    # Legacy Retriever (for backward compatibility)
    "CatalogAgenticRetriever",
    "AgentResult",
    "AgentStep",
    # Unified Agent (new)
    "UnifiedCatalogAgent",
    "UnifiedAgentResult",
]
