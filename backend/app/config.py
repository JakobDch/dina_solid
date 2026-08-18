from pathlib import Path
import logging
import os
from dotenv import load_dotenv
from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger("uvicorn.error")

# Lade Umgebungsvariablen aus .env
load_dotenv()

# Pfade und Verzeichnisse
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent.parent / "storage"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SEMANTIC_MODELS_DIR_NAME = "semantic_models"
EMBEDDINGS_DIR_NAME = "embeddings"
FAISS_INDEX_DIRECTORY_NAME = "vector_store_semantic_models"

# Zentrale Settings/Umgebungsvariablen
REMOTE_OLLAMA_LLAMA31_70B_BASE_URL = os.getenv("REMOTE_OLLAMA_LLAMA31_70B_BASE_URL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
SEMANTIC_DATA_CATALOG_URL = os.getenv("SEMANTIC_DATA_CATALOG_URL", "http://localhost:8000")

# Browser origins allowed to call the API. The frontend dev server and the API
# run on different ports, so at least one entry is always required.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "DINA_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:5174",
    ).split(",")
    if origin.strip()
]

# =============================================================================
# Solid dataspace configuration
#
# To point this application at a different dataspace you normally only need to
# set SOLID_POD_BASE_URL and DATASPACE_SLUG. Every catalog URL below is derived
# from those two values. The full-URL variables remain available as an escape
# hatch for pods that use a non-standard container layout.
#
# Three distinct concepts are kept separate on purpose:
#   * the pod server   - stores the RDF data and the catalog containers
#   * the OIDC issuer  - authenticates the user (may be a different host)
#   * the dataspace UI - the human-facing web application (serves HTML, not RDF)
# =============================================================================

def _join_url(base: str, *segments: str) -> str:
    """Join URL segments into a container URL with a trailing slash.

    The trailing slash is required: urljoin("https://host/dace", "catalog/ds/")
    resolves to "https://host/catalog/ds/" and silently drops the slug.
    """
    parts = [base.rstrip("/")] + [segment.strip("/") for segment in segments if segment]
    return "/".join(parts) + "/"


# Pod / storage server holding the RDF data and catalog containers.
SOLID_POD_BASE_URL = os.getenv(
    "SOLID_POD_BASE_URL",
    os.getenv("CATALOG_BASE_URL", "https://solid-community-server.tmdt.info"),
).rstrip("/")

# Dataspace slug. Appears as a path segment in both the catalog container and
# the federation registry, which is why it is configured separately.
DATASPACE_SLUG = os.getenv("DATASPACE_SLUG", "dace").strip("/")

# Solid OIDC issuer used for login. Defaults to the pod server, but a user may
# authenticate with a pod hosted somewhere else entirely.
SOLID_OIDC_ISSUER = os.getenv("SOLID_OIDC_ISSUER", SOLID_POD_BASE_URL).rstrip("/")

# Human-facing dataspace web application. Used only for outbound links; it
# serves HTML and is never fetched as RDF.
DATASPACE_UI_URL = os.getenv(
    "DATASPACE_UI_URL", "https://solid-dataspace-dace.tmdt.info"
).rstrip("/")

# Seed DCAT catalog container: {pod}/{slug}/catalog/ds/
CATALOG_API_URL = os.getenv(
    "CATALOG_API_URL", _join_url(SOLID_POD_BASE_URL, DATASPACE_SLUG, "catalog/ds")
)

# Federation registry listing every pod in the dataspace:
# {pod}/semanticdatacatalog/public/{slug}/
FEDERATION_REGISTRY_URL = os.getenv(
    "FEDERATION_REGISTRY_URL",
    _join_url(SOLID_POD_BASE_URL, "semanticdatacatalog/public", DATASPACE_SLUG),
)

# Path appended to each pod base discovered through the federation registry.
CATALOG_CONTAINER_PATH = os.getenv("CATALOG_CONTAINER_PATH", "catalog/ds/")

# Set to false to query only the seed catalog instead of the whole federation.
CATALOG_USE_FEDERATION = os.getenv("CATALOG_USE_FEDERATION", "true").lower() in (
    "1", "true", "yes",
)

# Timeout for per-pod requests during federation discovery. Kept well below the
# general catalog timeout so a single unreachable pod cannot stall a request:
# the registry lists pods that may have been decommissioned.
FEDERATION_TIMEOUT_SECONDS = float(os.getenv("FEDERATION_TIMEOUT_SECONDS", "5.0"))

# Retained for backwards compatibility with existing deployment .env files.
CATALOG_BASE_URL = SOLID_POD_BASE_URL

CATALOG_SPARQL_ENDPOINT = os.getenv("CATALOG_SPARQL_ENDPOINT", None)  # Not available

# Model Cache Configuration
MODEL_CACHE_PATH = DATA_DIR / "model_cache"
MODEL_CACHE_PATH.mkdir(parents=True, exist_ok=True)
MEMORY_CACHE_SIZE = int(os.getenv("MEMORY_CACHE_SIZE", "50"))
DISK_CACHE_TTL_SECONDS = int(os.getenv("DISK_CACHE_TTL_SECONDS", "86400"))  # 24 Stunden
DISK_CACHE_MAX_SIZE_MB = int(os.getenv("DISK_CACHE_MAX_SIZE_MB", "500"))

# Catalog Agent Configuration
CATALOG_SEARCH_TOP_K = int(os.getenv("CATALOG_SEARCH_TOP_K", "20"))
CATALOG_AGENT_MAX_STEPS = int(os.getenv("CATALOG_AGENT_MAX_STEPS", "15"))

logger.info(f"Storage directory: {DATA_DIR.resolve()}")
logger.info(f"Solid pod base URL: {SOLID_POD_BASE_URL}")
logger.info(f"Dataspace slug: {DATASPACE_SLUG}")
logger.info(f"Catalog API URL: {CATALOG_API_URL}")
logger.info(
    f"Federation registry: {FEDERATION_REGISTRY_URL} "
    f"(federation={'on' if CATALOG_USE_FEDERATION else 'off'})"
)
logger.debug(f"API Keys loaded: DEEPSEEK={bool(DEEPSEEK_API_KEY)}, OPENAI={bool(OPENAI_API_KEY)}, FIREWORKS={bool(FIREWORKS_API_KEY)}")

LLM_PROFILES = {
    "deepseek_chat": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "requires_api_key": True,
    },
    "fireworks_deepseek_chat": {
        "provider": "openai",
        "model": "accounts/fireworks/models/deepseek-v3p2",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "requires_api_key": True,
        "api_key_env": "FIREWORKS_API_KEY"
    },
    "fireworks_qwen3_30b": {
        "provider": "openai",
        "model": "accounts/fireworks/models/qwen3-30b-a3b",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "requires_api_key": True,
        "api_key_env": "FIREWORKS_API_KEY"
    },
    "ollama_local_gemma3": {
        "provider": "ollama",
        "model": "gemma3:4b",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        "requires_api_key": False,
    },
    "ollama_local_phi3mini": {
        "provider": "ollama",
        "model": "phi3-mini:3.8b",
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        "requires_api_key": False,
    },
    "openai_gpt4o": {
        "provider": "openai",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "requires_api_key": True,
    },

    "ollama_remote_llama31_70b": {
        "provider": "ollama",
        "model": "llama3.1:70b",
        "base_url": REMOTE_OLLAMA_LLAMA31_70B_BASE_URL,
        "requires_api_key": False,
    }
}


class AppSettings(BaseSettings):
    cors_origins: List[str] = CORS_ORIGINS
    # Add other settings loaded from .env or defaults as needed
    remote_ollama_llama31_70b_base_url: Optional[str] = REMOTE_OLLAMA_LLAMA31_70B_BASE_URL
    deepseek_api_key: Optional[str] = DEEPSEEK_API_KEY
    openai_api_key: Optional[str] = OPENAI_API_KEY
    ollama_base_url: str = OLLAMA_BASE_URL
    fireworks_api_key: Optional[str] = FIREWORKS_API_KEY
    semantic_data_catalog_url: str = SEMANTIC_DATA_CATALOG_URL
    data_dir: Path = DATA_DIR
    app_dir: Path = APP_DIR
    semantic_models_dir_name: str = SEMANTIC_MODELS_DIR_NAME
    embeddings_dir_name: str = EMBEDDINGS_DIR_NAME
    faiss_index_directory_name: str = FAISS_INDEX_DIRECTORY_NAME

    # Solid dataspace settings.
    #
    # Note on precedence: BaseSettings populates each field from the
    # identically-named environment variable, so an explicit CATALOG_API_URL in
    # the environment overrides the value derived from SOLID_POD_BASE_URL and
    # DATASPACE_SLUG above. That is the intended behaviour - the explicit
    # override wins - but it means the derivation only applies when the
    # specific variable is absent.
    solid_pod_base_url: str = SOLID_POD_BASE_URL
    dataspace_slug: str = DATASPACE_SLUG
    solid_oidc_issuer: str = SOLID_OIDC_ISSUER
    dataspace_ui_url: str = DATASPACE_UI_URL
    federation_registry_url: str = FEDERATION_REGISTRY_URL
    catalog_container_path: str = CATALOG_CONTAINER_PATH
    catalog_use_federation: bool = CATALOG_USE_FEDERATION
    federation_timeout_seconds: float = FEDERATION_TIMEOUT_SECONDS

    # Catalog-First Retrieval Settings
    catalog_base_url: str = CATALOG_BASE_URL
    catalog_api_url: str = CATALOG_API_URL
    catalog_sparql_endpoint: Optional[str] = CATALOG_SPARQL_ENDPOINT
    model_cache_path: Path = MODEL_CACHE_PATH
    memory_cache_size: int = MEMORY_CACHE_SIZE
    disk_cache_ttl_seconds: int = DISK_CACHE_TTL_SECONDS
    disk_cache_max_size_mb: int = DISK_CACHE_MAX_SIZE_MB
    catalog_search_top_k: int = CATALOG_SEARCH_TOP_K
    catalog_agent_max_steps: int = CATALOG_AGENT_MAX_STEPS

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore' # Ignore extra fields from .env if any

@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()

def get_available_llm_profiles():
    """Gibt eine Liste der verfügbaren LLM-Profile zurück"""
    return LLM_PROFILES.keys()

class MissingApiKeyError(ValueError):
    """No API key is available for the selected profile.

    Carries the provider so the interface can point the user at the right
    field in its settings.
    """

    def __init__(self, profile_key: str, provider: str):
        self.profile_key = profile_key
        self.provider = provider
        super().__init__(
            f"No API key available for '{profile_key}'. Add a {provider} key in "
            "the settings, or set one in the environment."
        )


def get_profile_provider(profile_key: str) -> str:
    """Return the credential provider a profile draws on.

    Several profiles share one provider - the Fireworks-hosted models all use
    the same key - so this is what the interface groups its fields by.
    """
    profile = LLM_PROFILES.get(profile_key)
    if not profile:
        raise ValueError(f"Unknown LLM profile: {profile_key}")
    if profile.get("api_key_env") == "FIREWORKS_API_KEY":
        return "fireworks"
    return profile.get("provider")


def describe_llm_profiles() -> list:
    """Describe the available profiles for the settings interface."""
    return [
        {
            "key": key,
            "model": profile.get("model"),
            "provider": get_profile_provider(key),
            "requires_api_key": profile.get("requires_api_key", False),
        }
        for key, profile in LLM_PROFILES.items()
    ]


def get_llm_for_profile(profile_key: str, settings: AppSettings, api_key: Optional[str] = None):
    """Build an LLM client for the given profile.

    A key passed by the caller wins over the environment: it comes from the
    user's own settings, which is the whole point of letting them supply one.
    The environment is the fallback so a single-user deployment can keep
    configuring the key once in .env.
    """
    from .llm_services import OllamaLLM, DeepSeekLLM, OpenAILLM

    if profile_key not in LLM_PROFILES:
        raise ValueError(f"Unknown LLM profile: {profile_key}")

    profile = LLM_PROFILES[profile_key]
    provider = profile.get("provider")
    model = profile.get("model")
    base_url = profile.get("base_url")
    requires_api_key = profile.get("requires_api_key", False)

    if provider == "ollama":
        # Runs locally and needs no credentials.
        return OllamaLLM(model=model, base_url=base_url or settings.ollama_base_url)

    if provider == "deepseek":
        resolved = api_key or settings.deepseek_api_key
        if requires_api_key and not resolved:
            raise MissingApiKeyError(profile_key, "DeepSeek")
        return DeepSeekLLM(api_key=resolved, model=model, base_url=base_url)

    if provider == "openai":
        if profile.get("api_key_env") == "FIREWORKS_API_KEY":
            resolved = api_key or settings.fireworks_api_key
            label = "Fireworks"
        else:
            resolved = api_key or settings.openai_api_key
            label = "OpenAI"

        if requires_api_key and not resolved:
            raise MissingApiKeyError(profile_key, label)
        return OpenAILLM(api_key=resolved, model=model, base_url=base_url)

    raise ValueError(f"Unknown provider: {provider} for profile {profile_key}")