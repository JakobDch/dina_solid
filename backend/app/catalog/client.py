"""
Catalog Client - HTTP client for the Solid Pod DCAT data catalog

Talks to the Solid Pod directly and reads DCAT metadata out of LDP containers.

Token-based authentication is supported for Solid-protected resources; the
token comes from the frontend (via @inrupt/solid-client-authn-browser).
"""

import asyncio
import httpx
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, unquote

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, DCTERMS, XSD

logger = logging.getLogger(__name__)

# Namespaces
DCAT = Namespace("http://www.w3.org/ns/dcat#")
LDP = Namespace("http://www.w3.org/ns/ldp#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

# Content types accepted when fetching RDF from a pod.
#
# Turtle is preferred, but a pod serves a file with the content type it was
# uploaded under and will not convert it: asking only for text/turtle makes it
# answer 501 for anything stored as application/octet-stream. The body is
# parsed with rdflib regardless, so stating a preference without insisting on
# it costs nothing and keeps such files readable.
RDF_ACCEPT = "text/turtle;q=1.0, application/ld+json;q=0.8, */*;q=0.5"

# Catalog endpoints are derived from the dataspace configuration; see
# app/config.py for the environment variables that control them. The module
# level names are kept so existing call sites and imports stay valid.
from ..config import (
    CATALOG_API_URL as DEFAULT_SOLID_POD_CATALOG_URL,
    FEDERATION_REGISTRY_URL,
    CATALOG_CONTAINER_PATH,
    CATALOG_USE_FEDERATION,
    FEDERATION_TIMEOUT_SECONDS,
    POD_HOST_REWRITES,
)


def _apply_host_rewrites(url: str) -> str:
    """Map a pod URL onto its current host, if a substitution is configured.

    Registry entries are written when a pod registers and are not revised when
    the server is later renamed, so without this every pod of a migrated
    dataspace looks unreachable. See POD_HOST_REWRITES in app/config.py.
    """
    for old_host, new_host in POD_HOST_REWRITES.items():
        if f"//{old_host}/" in url:
            rewritten = url.replace(f"//{old_host}/", f"//{new_host}/", 1)
            logger.info(f"Rewrote registry host: {old_host} -> {new_host}")
            return rewritten
    return url


# =============================================================================
# EXCEPTIONS - transparent error handling
# =============================================================================
class CatalogError(Exception):
    """Base class for all catalog errors."""
    pass


class CatalogUnavailableError(CatalogError):
    """The catalog could not be reached."""
    pass


class CatalogEntryNotFoundError(CatalogError):
    """No such entry exists in the catalog."""
    pass


class ModelFetchError(CatalogError):
    """A model could not be retrieved."""
    pass


# =============================================================================
# DATA MODEL
# =============================================================================
@dataclass
class CatalogEntry:
    """
    A single dataset entry in the DCAT catalog.
    """
    # Identification
    identifier: str                  # Unique catalog ID (UUID)
    model_name: str                  # File name (e.g. "0092.ttl")

    # DCAT metadata
    title: str                       # dct:title
    description: str                 # dct:description
    theme: str                       # dcat:theme

    # Access
    access_url: Optional[str]        # URL of the semantic model (TTL)
    data_url: Optional[str] = None   # URL of the data itself (CSV)
    catalog_entry_url: Optional[str] = None  # URL of the DCAT description

    # Content, once loaded
    has_content: bool = False        # True if a semantic_model_file is present
    content: Optional[str] = None    # Raw TTL content

    # Schema information extracted from the TTL
    classes: List[str] = field(default_factory=list)
    properties: List[str] = field(default_factory=list)

    # Further metadata
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    publisher: Optional[str] = None
    access_rights: Optional[str] = None

    def get_content(self) -> Optional[str]:
        """Return the TTL content if it has been loaded."""
        return self.content

    def to_search_text(self) -> str:
        """Flatten the metadata into a single searchable string."""
        parts = [
            self.title,
            self.description,
            self.theme,
            " ".join(self.classes),
            " ".join(self.properties),
        ]
        return " ".join(p for p in parts if p)


# =============================================================================
# CATALOG CLIENT - Solid Pod LDP Implementation
# =============================================================================
class CatalogClient:
    """
    HTTP client for the Solid Pod DCAT data catalog.

    Datasets are read straight from the Solid Pod LDP container. Token-based
    authentication is optional.

    With use_federation=True every Solid Pod listed in the central registry is
    queried and the resulting datasets are aggregated.
    """

    def __init__(
        self,
        api_url: str = DEFAULT_SOLID_POD_CATALOG_URL,
        timeout: float = 30.0,
        auth_token: Optional[str] = None,
        use_federation: bool = CATALOG_USE_FEDERATION,
        registry_url: str = FEDERATION_REGISTRY_URL,
        federation_timeout: float = FEDERATION_TIMEOUT_SECONDS,
    ):
        """
        Initialise the client.

        Args:
            api_url: base URL of the Solid Pod catalog container (used as a
                fallback when federation is disabled)
            timeout: request timeout in seconds
            auth_token: optional Solid/DPoP access token for authenticated requests
            use_federation: when True, every registered pod is queried
            registry_url: URL of the central federation registry
            federation_timeout: shorter per-pod timeout used during federation
                discovery. The registry also lists pods that are no longer
                reachable, and without this cap a single dead pod would stall
                the whole request.
        """
        self.catalog_url = api_url.rstrip('/') + '/'
        self.timeout = timeout
        self._auth_token = auth_token
        self._use_federation = use_federation
        self._registry_url = registry_url
        self._federation_timeout = federation_timeout
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        self._catalog_cache: Dict[str, CatalogEntry] = {}
        self._dataset_urls: List[str] = []  # Cache for dataset TTL URLs
        self._registered_pods: List[str] = []  # Cache for registered pod catalog URLs

    @property
    def uses_federation(self) -> bool:
        """True when every registered pod is being queried."""
        return self._use_federation

    async def list_catalog_urls_async(self) -> List[str]:
        """Return the dataspace's catalog container URLs.

        With federation enabled that means the configured catalog plus every
        pod listed in the registry; otherwise just the configured catalog.
        """
        if not self._use_federation:
            return [self.catalog_url]
        return await self._discover_registered_pods_async()

    def set_auth_token(self, token: str) -> None:
        """Set the auth token used for authenticated requests."""
        self._auth_token = token
        # Reset clients to apply new token
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            self._async_client = None

    def _get_auth_headers(self) -> Dict[str, str]:
        """Build the request headers, adding Authorization when a token is set."""
        headers = {"Accept": RDF_ACCEPT}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def _get_client(self) -> httpx.Client:
        """Lazily create the sync HTTP client, complete with auth headers."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers=self._get_auth_headers()
            )
        return self._client

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Lazily create the async HTTP client, complete with auth headers."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._get_auth_headers()
            )
        return self._async_client

    def close(self):
        """Close the HTTP clients."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_client.aclose())
                else:
                    loop.run_until_complete(self._async_client.aclose())
            except Exception:
                pass
            self._async_client = None

    async def aclose(self):
        """Async close for HTTP clients."""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    # =========================================================================
    # LDP CONTAINER PARSING
    # =========================================================================

    def _parse_ldp_container(self, turtle_content: str, base_url: Optional[str] = None) -> List[str]:
        """
        Parse an LDP container and pull out the URLs of the resources it holds.

        Args:
            turtle_content: the container's TTL content
            base_url: the container's base URL, used to resolve relative URLs

        Returns:
            A list of TTL file URLs
        """
        if base_url is None:
            base_url = self.catalog_url

        g = Graph()
        # Parse with base URI to resolve relative references
        g.parse(data=turtle_content, format="turtle", publicID=base_url)

        dataset_urls = []
        seen = set()

        for s, p, o in g:
            # Collect every resource whose name ends in .ttl
            s_str = str(s)
            if s_str.endswith('.ttl') and s_str not in seen:
                # Absolute HTTP URLs can be used as-is
                if s_str.startswith('http://') or s_str.startswith('https://'):
                    dataset_urls.append(s_str)
                    seen.add(s_str)
                elif not s_str.startswith('file://'):
                    # Relative URL - resolve it against the base
                    full_url = urljoin(base_url, s_str)
                    if full_url not in seen:
                        dataset_urls.append(full_url)
                        seen.add(full_url)

        # Drop the container URL itself if it slipped in
        dataset_urls = [url for url in dataset_urls if url.rstrip('/') != base_url.rstrip('/')]

        return dataset_urls

    # =========================================================================
    # FEDERATION REGISTRY PARSING
    # =========================================================================

    def _parse_registry_members(self, turtle_content: str, registry_url: str) -> List[str]:
        """
        Parse the federation registry (an LDP container) into registered pod URLs.

        The registry is an LDP container in Turtle format whose member URIs look
        like this:
        <member-https%253A%2F%2Fsolid-community-server.tmdt.info%2Fdace%2Fprofile%2Fcard%23me>

        The name is double URL-encoded and therefore has to be decoded twice. In
        practice both encoding depths occur in the wild; since unquote is
        idempotent on already-decoded text, calling it twice handles either case.

        Returns:
            A list of pod base URLs, e.g. ["https://solid-community-server.tmdt.info/dace/"]
        """
        pod_urls = []

        try:
            g = Graph()
            g.parse(data=turtle_content, format="turtle", publicID=registry_url)

            # Walk everything the container declares via ldp:contains
            for s, p, o in g.triples((None, LDP.contains, None)):
                member_uri = str(o)
                logger.debug(f"Found LDP member: {member_uri}")

                # Grab the local name (member-https%253A%2F%2F...). The URI has
                # been resolved relative to the registry, so take the last segment.
                member_name = member_uri.split('/')[-1]

                if not member_name.startswith('member-'):
                    continue

                # Strip the "member-" prefix
                encoded_webid = member_name.replace("member-", "")

                # Decode twice (see the docstring)
                decoded_once = unquote(encoded_webid)
                webid = unquote(decoded_once)

                logger.debug(f"Decoded WebID: {webid}")

                # Derive the pod base URL from the WebID
                # WebID:   https://solid-community-server.tmdt.info/dace/profile/card#me
                # Pod URL: https://solid-community-server.tmdt.info/dace/
                pod_base_match = re.match(r'(https?://[^/]+/[^/]+/).*', webid)
                if pod_base_match:
                    pod_base_url = _apply_host_rewrites(pod_base_match.group(1))
                    if pod_base_url not in pod_urls:
                        pod_urls.append(pod_base_url)
                        logger.info(f"Discovered pod from registry: {pod_base_url}")

        except Exception as e:
            logger.error(f"Error parsing registry TTL: {e}")

        return pod_urls

    def _discover_registered_pods(self) -> List[str]:
        """
        Load the list of registered pods from the federation registry.

        Returns:
            A list of catalog URLs, e.g. ["https://...tmdt.info/dace/catalog/ds/"]
        """
        if self._registered_pods:
            return self._registered_pods

        try:
            # Request Turtle format explicitly
            headers = self._get_auth_headers()
            headers["Accept"] = RDF_ACCEPT

            response = self._get_client().get(self._registry_url, headers=headers)
            response.raise_for_status()

            pod_base_urls = self._parse_registry_members(response.text, self._registry_url)

            # Turn the pod base URLs into catalog URLs.
            # The configured catalog is always queried first: the registry can
            # carry stale entries (for instance a pod that moved but is still
            # listed under its old host), and without this the catalog we
            # actually wanted would be skipped without a word.
            catalog_urls = [self.catalog_url]
            for pod_url in pod_base_urls:
                catalog_url = urljoin(pod_url, CATALOG_CONTAINER_PATH)
                if catalog_url.rstrip('/') == self.catalog_url.rstrip('/'):
                    continue
                catalog_urls.append(catalog_url)
                logger.info(f"Registered catalog: {catalog_url}")

            self._registered_pods = catalog_urls
            logger.info(f"Discovered {len(catalog_urls)} registered pods from federation registry")
            return catalog_urls

        except httpx.HTTPError as e:
            logger.warning(f"Could not load federation registry: {e}")
            # Fallback: Return only the default catalog URL
            return [self.catalog_url]

    async def _discover_registered_pods_async(self) -> List[str]:
        """
        Async variant of _discover_registered_pods.
        """
        if self._registered_pods:
            return self._registered_pods

        try:
            client = await self._get_async_client()
            # Request Turtle format explicitly
            headers = {"Accept": RDF_ACCEPT}
            if self._auth_token:
                headers["Authorization"] = f"Bearer {self._auth_token}"

            response = await client.get(self._registry_url, headers=headers)
            response.raise_for_status()

            pod_base_urls = self._parse_registry_members(response.text, self._registry_url)

            # Turn the pod base URLs into catalog URLs.
            # The configured catalog is always queried first: the registry can
            # carry stale entries (for instance a pod that moved but is still
            # listed under its old host), and without this the catalog we
            # actually wanted would be skipped without a word.
            catalog_urls = [self.catalog_url]
            for pod_url in pod_base_urls:
                catalog_url = urljoin(pod_url, CATALOG_CONTAINER_PATH)
                if catalog_url.rstrip('/') == self.catalog_url.rstrip('/'):
                    continue
                catalog_urls.append(catalog_url)
                logger.info(f"Registered catalog: {catalog_url}")

            self._registered_pods = catalog_urls
            logger.info(f"Discovered {len(catalog_urls)} registered pods from federation registry")
            return catalog_urls

        except httpx.HTTPError as e:
            logger.warning(f"Could not load federation registry: {e}")
            # Fallback: Return only the default catalog URL
            return [self.catalog_url]

    def _parse_dcat_dataset(self, turtle_content: str, dataset_url: str) -> Optional[CatalogEntry]:
        """
        Parse a DCAT dataset description out of TTL.

        Args:
            turtle_content: the TTL content
            dataset_url: URL of the TTL file

        Returns:
            A CatalogEntry, or None if parsing failed
        """
        try:
            g = Graph()
            g.parse(data=turtle_content, format="turtle")

            # Locate the dataset subject (the one typed as dcat:Dataset)
            dataset_subject = None
            for s in g.subjects(RDF.type, DCAT.Dataset):
                dataset_subject = s
                break

            if not dataset_subject:
                logger.warning(f"No dcat:Dataset found in {dataset_url}")
                return None

            # Pull out the metadata
            identifier = self._get_literal(g, dataset_subject, DCTERMS.identifier) or ""
            title = self._get_literal(g, dataset_subject, DCTERMS.title) or "Untitled"
            description = self._get_literal(g, dataset_subject, DCTERMS.description) or ""
            publisher = self._get_literal(g, dataset_subject, DCTERMS.publisher) or ""
            access_rights = self._get_literal(g, dataset_subject, DCTERMS.accessRights) or "public"

            # The theme may be either a URI or a plain literal
            theme = ""
            for theme_obj in g.objects(dataset_subject, DCAT.theme):
                if isinstance(theme_obj, URIRef):
                    # Use the last URI segment
                    theme = str(theme_obj).split('/')[-1]
                else:
                    theme = str(theme_obj)
                break

            # Date fields
            issued = self._get_datetime(g, dataset_subject, DCTERMS.issued)
            modified = self._get_datetime(g, dataset_subject, DCTERMS.modified)

            # Schema (the semantic model) via dct:conformsTo
            model_url = None
            model_name = "unknown.ttl"
            for conforms_to in g.objects(dataset_subject, DCTERMS.conformsTo):
                model_url = str(conforms_to)
                model_name = model_url.split('/')[-1]
                break

            # Data (RDF instances) and model via dcat:distribution.
            #
            # Not every catalog announces the semantic model through
            # dct:conformsTo; a dedicated distribution identified by a fragment
            # (#dist-model) or by file name is just as common. Both shapes are
            # handled here so the model never goes missing silently.
            data_url = None
            for dist in g.objects(dataset_subject, DCAT.distribution):
                dist_id = str(dist).rsplit('#', 1)[-1].lower()
                is_model_dist = 'model' in dist_id or 'schema' in dist_id

                for url in g.objects(dist, DCAT.downloadURL):
                    download_url = str(url)
                    # Accept TTL/RDF only, skip CSV
                    if not download_url.endswith('.ttl'):
                        continue
                    if is_model_dist:
                        if not model_url:
                            model_url = download_url
                            model_name = download_url.split('/')[-1]
                    elif not data_url:
                        data_url = download_url

            # Fallback: when model and data share one TTL file, the model
            # distribution doubles as the data source.
            if not data_url and model_url:
                data_url = model_url

            # No explicit identifier? Derive one from the URL
            if not identifier:
                # Pull the UUID out of a URL like ".../{uuid}.ttl"
                match = re.search(r'/([a-f0-9-]{36})\.ttl', dataset_url)
                if match:
                    identifier = match.group(1)
                else:
                    identifier = dataset_url.split('/')[-1].replace('.ttl', '')

            return CatalogEntry(
                identifier=identifier,
                model_name=model_name,
                title=title,
                description=description,
                theme=theme,
                access_url=model_url,
                data_url=data_url,
                catalog_entry_url=dataset_url,
                has_content=False,
                content=None,
                classes=[],
                properties=[],
                created_at=issued,
                modified_at=modified,
                publisher=publisher,
                access_rights=access_rights,
            )

        except Exception as e:
            logger.error(f"Error parsing DCAT dataset from {dataset_url}: {e}")
            return None

    def _get_literal(self, g: Graph, subject, predicate) -> Optional[str]:
        """Read a literal value from the graph."""
        for obj in g.objects(subject, predicate):
            return str(obj)
        return None

    def _get_datetime(self, g: Graph, subject, predicate) -> Optional[datetime]:
        """Read a datetime value from the graph."""
        for obj in g.objects(subject, predicate):
            try:
                dt_str = str(obj)
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except Exception:
                pass
        return None

    # =========================================================================
    # CATALOG OPERATIONS (sync)
    # =========================================================================

    def is_available(self) -> bool:
        """
        Check whether the catalog responds.

        Returns:
            True if the catalog is reachable
        """
        try:
            response = self._get_client().get(self.catalog_url)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Catalog availability check failed: {e}")
            return False

    def _load_dataset_urls(self) -> List[str]:
        """
        Load the dataset URLs from every LDP container.

        With use_federation=True all registered pods are queried and their
        datasets are aggregated.
        """
        if self._dataset_urls:
            return self._dataset_urls

        all_urls = []

        if self._use_federation:
            # Query every registered pod
            catalog_urls = self._discover_registered_pods()
            logger.info(f"Loading datasets from {len(catalog_urls)} federated catalogs")

            reachable = 0
            for catalog_url in catalog_urls:
                try:
                    response = self._get_client().get(
                        catalog_url, timeout=self._federation_timeout
                    )
                    if response.status_code == 200:
                        urls = self._parse_ldp_container(response.text, base_url=catalog_url)
                        all_urls.extend(urls)
                        reachable += 1
                        logger.info(f"Loaded {len(urls)} datasets from {catalog_url}")
                    else:
                        logger.warning(f"Catalog {catalog_url} returned status {response.status_code}")
                except httpx.HTTPError as e:
                    logger.warning(f"Could not load catalog {catalog_url}: {e}")
                    continue

            # A few unreachable pods is normal - the registry also lists pods
            # that have been shut down. Only a total blackout means the catalog
            # is genuinely broken.
            if reachable == 0:
                raise CatalogUnavailableError(
                    f"None of the {len(catalog_urls)} registered pods are "
                    f"reachable (registry: {self._registry_url})."
                )
        else:
            # Load the default catalog only
            try:
                response = self._get_client().get(self.catalog_url)
                response.raise_for_status()
                all_urls = self._parse_ldp_container(response.text)
            except httpx.HTTPError as e:
                raise CatalogUnavailableError(f"Catalog unreachable: {e}")

        self._dataset_urls = all_urls
        logger.info(f"Total: Loaded {len(all_urls)} dataset URLs from {'federated' if self._use_federation else 'single'} catalog")
        return self._dataset_urls

    def get_dataset_count(self) -> int:
        """
        Return how many datasets the catalog holds.
        """
        urls = self._load_dataset_urls()
        return len(urls)

    def list_datasets(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CatalogEntry]:
        """
        List the datasets in the catalog.
        """
        urls = self._load_dataset_urls()

        # Pagination
        paginated_urls = urls[skip:skip + limit]

        entries = []
        for url in paginated_urls:
            # Check cache first
            cache_key = url.split('/')[-1].replace('.ttl', '')
            if cache_key in self._catalog_cache:
                entries.append(self._catalog_cache[cache_key])
                continue

            try:
                response = self._get_client().get(url)
                response.raise_for_status()
                entry = self._parse_dcat_dataset(response.text, url)
                if entry:
                    entries.append(entry)
                    self._catalog_cache[entry.identifier] = entry
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch dataset from {url}: {e}")
                continue

        return entries

    def _find_dataset_url(self, identifier: str) -> Optional[str]:
        """
        Find a dataset's URL by ID among the already-loaded URLs.
        """
        # Make sure the URL list has been loaded
        urls = self._load_dataset_urls()

        # Look for the URL ending in this ID
        for url in urls:
            if url.endswith(f"{identifier}.ttl"):
                return url

        return None

    def get_dataset(self, identifier: str) -> CatalogEntry:
        """
        Retrieve a single dataset.

        Under federation every registered pod is searched.
        """
        # Cache first
        if identifier in self._catalog_cache:
            return self._catalog_cache[identifier]

        # Try to resolve the URL from the loaded dataset URLs
        dataset_url = self._find_dataset_url(identifier)

        if not dataset_url:
            # Fallback: build the URL from the default catalog
            dataset_url = urljoin(self.catalog_url, f"{identifier}.ttl")

        try:
            response = self._get_client().get(dataset_url)

            if response.status_code == 404:
                raise CatalogEntryNotFoundError(f"Dataset not found: {identifier}")

            response.raise_for_status()
            entry = self._parse_dcat_dataset(response.text, dataset_url)

            if not entry:
                raise CatalogEntryNotFoundError(f"Dataset could not be parsed: {identifier}")

            self._catalog_cache[entry.identifier] = entry
            return entry

        except httpx.HTTPError as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise CatalogEntryNotFoundError(f"Dataset not found: {identifier}")
            raise CatalogUnavailableError(f"Catalog unreachable: {e}")

    def get_all_datasets(self) -> List[CatalogEntry]:
        """
        Retrieve every dataset in the catalog.
        """
        urls = self._load_dataset_urls()
        return self.list_datasets(skip=0, limit=len(urls))

    # =========================================================================
    # CATALOG OPERATIONS (async)
    # =========================================================================

    async def is_available_async(self) -> bool:
        """Async version of is_available."""
        try:
            client = await self._get_async_client()
            response = await client.get(self.catalog_url)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Catalog availability check failed: {e}")
            return False

    async def _load_dataset_urls_async(self) -> List[str]:
        """
        Async variant of _load_dataset_urls.

        With use_federation=True all registered pods are queried and their
        datasets are aggregated.
        """
        if self._dataset_urls:
            return self._dataset_urls

        all_urls = []
        client = await self._get_async_client()

        if self._use_federation:
            # Query every registered pod
            catalog_urls = await self._discover_registered_pods_async()
            logger.info(f"Loading datasets from {len(catalog_urls)} federated catalogs")

            # Query the pods concurrently: the registry lists dozens of them,
            # and run serially even short timeouts add up to a noticeable wait.
            responses = await asyncio.gather(
                *(
                    client.get(catalog_url, timeout=self._federation_timeout)
                    for catalog_url in catalog_urls
                ),
                return_exceptions=True,
            )

            reachable = 0
            for catalog_url, response in zip(catalog_urls, responses):
                if isinstance(response, Exception):
                    logger.warning(f"Could not load catalog {catalog_url}: {response}")
                    continue
                if response.status_code == 200:
                    urls = self._parse_ldp_container(response.text, base_url=catalog_url)
                    all_urls.extend(urls)
                    reachable += 1
                    logger.info(f"Loaded {len(urls)} datasets from {catalog_url}")
                else:
                    logger.warning(f"Catalog {catalog_url} returned status {response.status_code}")

            # A few unreachable pods is normal - the registry also lists pods
            # that have been shut down. Only a total blackout means the catalog
            # is genuinely broken.
            if reachable == 0:
                raise CatalogUnavailableError(
                    f"None of the {len(catalog_urls)} registered pods are "
                    f"reachable (registry: {self._registry_url})."
                )
        else:
            # Load the default catalog only
            try:
                response = await client.get(self.catalog_url)
                response.raise_for_status()
                all_urls = self._parse_ldp_container(response.text)
            except httpx.HTTPError as e:
                raise CatalogUnavailableError(f"Catalog unreachable: {e}")

        self._dataset_urls = all_urls
        logger.info(f"Total: Loaded {len(all_urls)} dataset URLs from {'federated' if self._use_federation else 'single'} catalog")
        return self._dataset_urls

    async def get_dataset_count_async(self) -> int:
        """Async version of get_dataset_count."""
        urls = await self._load_dataset_urls_async()
        return len(urls)

    async def list_datasets_async(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CatalogEntry]:
        """Async version of list_datasets."""
        urls = await self._load_dataset_urls_async()

        # Pagination
        paginated_urls = urls[skip:skip + limit]

        entries = []
        client = await self._get_async_client()

        for url in paginated_urls:
            # Check cache first
            cache_key = url.split('/')[-1].replace('.ttl', '')
            if cache_key in self._catalog_cache:
                entries.append(self._catalog_cache[cache_key])
                continue

            try:
                response = await client.get(url)
                response.raise_for_status()
                entry = self._parse_dcat_dataset(response.text, url)
                if entry:
                    entries.append(entry)
                    self._catalog_cache[entry.identifier] = entry
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch dataset from {url}: {e}")
                continue

        return entries

    async def _find_dataset_url_async(self, identifier: str) -> Optional[str]:
        """
        Async variant of _find_dataset_url.
        """
        # Make sure the URL list has been loaded
        urls = await self._load_dataset_urls_async()

        # Look for the URL ending in this ID
        for url in urls:
            if url.endswith(f"{identifier}.ttl"):
                return url

        return None

    async def get_dataset_async(self, identifier: str) -> CatalogEntry:
        """
        Async version of get_dataset.

        Under federation every registered pod is searched.
        """
        if identifier in self._catalog_cache:
            return self._catalog_cache[identifier]

        # Try to resolve the URL from the loaded dataset URLs
        dataset_url = await self._find_dataset_url_async(identifier)

        if not dataset_url:
            # Fallback: build the URL from the default catalog
            dataset_url = urljoin(self.catalog_url, f"{identifier}.ttl")

        try:
            client = await self._get_async_client()
            response = await client.get(dataset_url)

            if response.status_code == 404:
                raise CatalogEntryNotFoundError(f"Dataset not found: {identifier}")

            response.raise_for_status()
            entry = self._parse_dcat_dataset(response.text, dataset_url)

            if not entry:
                raise CatalogEntryNotFoundError(f"Dataset could not be parsed: {identifier}")

            self._catalog_cache[entry.identifier] = entry
            return entry

        except httpx.HTTPError as e:
            if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 404:
                raise CatalogEntryNotFoundError(f"Dataset not found: {identifier}")
            raise CatalogUnavailableError(f"Catalog unreachable: {e}")

    async def get_all_datasets_async(self) -> List[CatalogEntry]:
        """Async version of get_all_datasets."""
        urls = await self._load_dataset_urls_async()
        return await self.list_datasets_async(skip=0, limit=len(urls))

    # =========================================================================
    # MODEL RETRIEVAL (backs the fetch_model tool)
    # =========================================================================

    def fetch_model_content(self, identifier: str) -> str:
        """
        Retrieve the full content of a semantic model.
        """
        entry = self.get_dataset(identifier)

        # Path 1: via access_url (the distribution URL)
        if entry.access_url:
            try:
                response = self._get_client().get(entry.access_url)
                response.raise_for_status()
                content = response.text

                # Cache content in entry
                entry.content = content
                entry.has_content = True

                # Extract classes and properties
                entry.classes, entry.properties = self._extract_schema_from_ttl(content)

                return content
            except httpx.HTTPError as e:
                raise ModelFetchError(
                    f"Model '{entry.model_name}' could not be fetched from {entry.access_url}: {e}"
                )

        # Path 2: content already stored on the entry
        if entry.has_content and entry.content:
            return entry.content

        raise ModelFetchError(
            f"Model '{entry.model_name}' has neither an access_url nor stored content"
        )

    async def fetch_model_content_async(self, identifier: str) -> str:
        """Async version of fetch_model_content."""
        entry = await self.get_dataset_async(identifier)

        if entry.access_url:
            try:
                client = await self._get_async_client()
                response = await client.get(entry.access_url)
                response.raise_for_status()
                content = response.text

                # Cache content in entry
                entry.content = content
                entry.has_content = True

                # Extract classes and properties
                entry.classes, entry.properties = self._extract_schema_from_ttl(content)

                return content
            except httpx.HTTPError as e:
                raise ModelFetchError(
                    f"Model '{entry.model_name}' could not be fetched from {entry.access_url}: {e}"
                )

        if entry.has_content and entry.content:
            return entry.content

        raise ModelFetchError(
            f"Model '{entry.model_name}' has neither an access_url nor stored content"
        )

    def _extract_schema_from_ttl(self, ttl_content: str) -> tuple:
        """
        Extract class and property names from TTL content.
        """
        classes = set()
        properties = set()

        for line in ttl_content.split('\n'):
            line = line.strip()

            # Skip prefixes, comments and blank lines
            if not line or line.startswith('@prefix') or line.startswith('#'):
                continue

            # Classes: lines that open with a subject (i.e. not indented)
            if not line.startswith(' ') and not line.startswith('\t'):
                parts = line.split()
                if parts and ':' in parts[0] and not parts[0].startswith('<'):
                    class_name = parts[0].split(':')[-1].rstrip(';.')
                    if class_name and not class_name.startswith('_'):
                        classes.add(class_name)

            # Properties: whatever sits in the predicate position of a triple
            if ':' in line:
                for part in line.replace(';', ' ').replace('.', ' ').split():
                    if ':' in part:
                        prefix, local = part.split(':', 1) if ':' in part else ('', part)
                        # Skip the standard prefixes
                        if prefix not in ('rdf', 'rdfs', 'xsd', 'owl', '@'):
                            local = local.rstrip(';.')
                            if local and local[0].islower():  # properties are lowercase by convention
                                properties.add(local)

        return sorted(list(classes))[:20], sorted(list(properties))[:30]
