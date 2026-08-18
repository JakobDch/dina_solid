"""
Catalog Router

Exposes the Solid dataspace catalogs that the agent can query. The frontend
uses this to let the user pick a catalog before asking questions.

Catalogs are discovered through the federation registry configured in
app/config.py, so pointing the deployment at a different dataspace changes the
list here as well - no code change required.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from ..config import get_settings, AppSettings
from ..catalog.client import CatalogClient, CatalogError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/catalogs", tags=["Catalogs"])


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Extract a bearer token from an Authorization header, if present."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _label_for(catalog_url: str) -> tuple[str, str]:
    """Derive a human-readable title and pod name from a catalog container URL.

    "https://pod.example/sawmill/catalog/ds/" -> ("Sawmill", "pod.example")
    """
    from urllib.parse import urlparse

    parsed = urlparse(catalog_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    pod_name = segments[0] if segments else parsed.netloc
    title = pod_name.replace("-", " ").replace("_", " ").strip().title()
    return title or parsed.netloc, parsed.netloc


@router.get("")
async def list_catalogs(
    settings: AppSettings = Depends(get_settings),
    authorization: Optional[str] = Header(None),
) -> List[dict]:
    """List the catalogs available in the configured dataspace.

    Unreachable pods are omitted rather than failing the whole request: the
    federation registry also lists pods that have been decommissioned.
    """
    client = CatalogClient(
        api_url=settings.catalog_api_url,
        auth_token=_bearer_token(authorization),
    )

    try:
        catalog_urls = await client.list_catalog_urls_async()
    except CatalogError as exc:
        logger.warning(f"Could not discover catalogs: {exc}")
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error while discovering catalogs")
        raise HTTPException(status_code=503, detail=f"Catalog discovery failed: {exc}")

    catalogs = []
    for index, catalog_url in enumerate(catalog_urls):
        title, host = _label_for(catalog_url)
        catalogs.append(
            {
                # The frontend identifies the selected catalog by a numeric id.
                "id": index,
                "title": title,
                "description": f"Solid pod catalog on {host}",
                "catalog_url": catalog_url,
                "is_default": catalog_url.rstrip("/") == settings.catalog_api_url.rstrip("/"),
            }
        )

    logger.info(f"Listing {len(catalogs)} catalogs from the dataspace federation")
    return catalogs
