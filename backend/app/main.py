"""
DINa - a conversational interface to a Solid dataspace.

The application turns a natural-language question into a SPARQL query:

  1. an agent searches the DCAT catalog of the dataspace for relevant datasets,
  2. it fetches the semantic models of the most promising candidates,
  3. an LLM writes a SPARQL query against those models,
  4. the query and the dataset URLs are streamed to the browser, which runs the
     query with Comunica directly against the Solid pods and posts the results
     back.

The backend therefore never executes SPARQL itself and never holds a copy of
the data - it only ever sees metadata and the results the browser returns.
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from .catalog.client import CatalogClient
from .config import get_settings
from .db import engine
from .routers import (
    agent_router,
    catalog_router,
    corpus_router,
    sessions_router,
    workspaces_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the database schema on startup."""
    SQLModel.metadata.create_all(engine)
    logger.info("Database schema is up to date")
    yield


app = FastAPI(
    title="DINa Backend",
    description="Conversational access to a Solid dataspace via generated SPARQL queries.",
    lifespan=lifespan,
)

# Development servers run on a different origin than the API. Set
# DINA_CORS_ORIGINS to a comma-separated list to allow other origins.
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health", summary="Health check")
async def health_check():
    """Report whether the database and the configured catalog are reachable.

    The catalog check only probes the configured container; the agent can still
    work through the federation if a single pod is unavailable, so a degraded
    catalog is reported without marking the service as not ready.
    """
    services = {}

    try:
        with engine.connect():
            services["database"] = "ok"
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        services["database"] = "unavailable"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                settings.catalog_api_url, headers={"Accept": "text/turtle"}
            )
        services["catalog"] = "ok" if response.status_code < 400 else "degraded"
    except Exception as exc:
        logger.warning(f"Catalog health check failed: {exc}")
        services["catalog"] = "unavailable"

    return {
        "status": "ok",
        "ready": services["database"] == "ok",
        "services": services,
        "dataspace": {
            "pod": settings.solid_pod_base_url,
            "slug": settings.dataspace_slug,
            "catalog": settings.catalog_api_url,
        },
    }


app.include_router(agent_router.router)
app.include_router(catalog_router.router)
app.include_router(corpus_router.router)
app.include_router(sessions_router.router)
app.include_router(workspaces_router.router)

logger.info("All routers registered")
