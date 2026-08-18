"""
Corpus Router for SPARQL Few-Shot Examples Management.

Provides API endpoints for managing the SPARQL corpus used in adaptive few-shot prompting.
These endpoints are intended for developers only.
"""

import json
import logging
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlmodel import Session, select

from ..db import engine
from ..models import (
    SPARQLCorpusEntry,
    SPARQLCorpusEntryCreate,
    SPARQLCorpusEntryRead,
    SPARQLCorpusEntryUpdate
)
from ..sparql_corpus import (
    add_corpus_entry,
    get_all_corpus_entries,
    get_corpus_entry_by_id,
    delete_corpus_entry,
    get_corpus_stats,
    extract_sparql_operators,
    categorize_complexity
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/corpus", tags=["corpus"])


# --- CRUD Endpoints ---

@router.get("", response_model=List[SPARQLCorpusEntryRead])
async def list_corpus_entries():
    """
    List all corpus entries.

    Returns all SPARQL examples in the corpus ordered by creation date (newest first).
    """
    entries = get_all_corpus_entries()
    return [SPARQLCorpusEntryRead(
        id=e.id,
        natural_language_query=e.natural_language_query,
        sparql_query=e.sparql_query,
        sparql_operators=e.sparql_operators,
        complexity=e.complexity,
        semantic_models=e.semantic_models,
        is_multi_model=e.is_multi_model,
        source=e.source,
        theme=e.theme,
        created_at=e.created_at,
        updated_at=e.updated_at,
        usage_count=e.usage_count,
        success_rate=e.success_rate
    ) for e in entries]


@router.post("", response_model=SPARQLCorpusEntryRead)
async def create_corpus_entry(entry_data: SPARQLCorpusEntryCreate):
    """
    Create a new corpus entry.

    Operators and complexity are automatically extracted from the SPARQL query.
    """
    try:
        entry = add_corpus_entry(
            natural_language_query=entry_data.natural_language_query,
            sparql_query=entry_data.sparql_query,
            semantic_models=entry_data.semantic_models,
            semantic_models_content=entry_data.semantic_models_content,
            source=entry_data.source,
            theme=entry_data.theme
        )

        return SPARQLCorpusEntryRead(
            id=entry.id,
            natural_language_query=entry.natural_language_query,
            sparql_query=entry.sparql_query,
            sparql_operators=entry.sparql_operators,
            complexity=entry.complexity,
            semantic_models=entry.semantic_models,
            is_multi_model=entry.is_multi_model,
            source=entry.source,
            theme=entry.theme,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            usage_count=entry.usage_count,
            success_rate=entry.success_rate
        )

    except Exception as e:
        logger.error(f"Error creating corpus entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{entry_id}", response_model=SPARQLCorpusEntryRead)
async def get_corpus_entry(entry_id: str):
    """Get a specific corpus entry by ID."""
    entry = get_corpus_entry_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Corpus entry {entry_id} not found")

    return SPARQLCorpusEntryRead(
        id=entry.id,
        natural_language_query=entry.natural_language_query,
        sparql_query=entry.sparql_query,
        sparql_operators=entry.sparql_operators,
        complexity=entry.complexity,
        semantic_models=entry.semantic_models,
        is_multi_model=entry.is_multi_model,
        source=entry.source,
        theme=entry.theme,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        usage_count=entry.usage_count,
        success_rate=entry.success_rate
    )


@router.patch("/{entry_id}", response_model=SPARQLCorpusEntryRead)
async def update_corpus_entry(entry_id: str, update_data: SPARQLCorpusEntryUpdate):
    """
    Update a corpus entry.

    If SPARQL query is updated, operators and complexity are re-extracted.
    """
    with Session(engine) as session:
        entry = session.get(SPARQLCorpusEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail=f"Corpus entry {entry_id} not found")

        # Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(entry, key, value)

        # Re-extract operators if SPARQL changed
        if "sparql_query" in update_dict:
            entry.sparql_operators = extract_sparql_operators(entry.sparql_query)
            entry.complexity = categorize_complexity(
                entry.sparql_operators,
                entry.sparql_query,
                entry.is_multi_model
            )

        # Update multi-model flag if semantic_models changed
        if "semantic_models" in update_dict:
            entry.is_multi_model = len(entry.semantic_models) > 1

        session.add(entry)
        session.commit()
        session.refresh(entry)

        return SPARQLCorpusEntryRead(
            id=entry.id,
            natural_language_query=entry.natural_language_query,
            sparql_query=entry.sparql_query,
            sparql_operators=entry.sparql_operators,
            complexity=entry.complexity,
            semantic_models=entry.semantic_models,
            is_multi_model=entry.is_multi_model,
            source=entry.source,
            theme=entry.theme,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
            usage_count=entry.usage_count,
            success_rate=entry.success_rate
        )


@router.delete("/{entry_id}")
async def remove_corpus_entry(entry_id: str):
    """Delete a corpus entry by ID."""
    success = delete_corpus_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Corpus entry {entry_id} not found")

    return {"message": f"Corpus entry {entry_id} deleted successfully"}


# --- Statistics ---

@router.get("/stats/summary")
async def get_corpus_statistics():
    """
    Get statistics about the corpus.

    Returns total entries, operator distribution, complexity distribution, etc.
    """
    stats = get_corpus_stats()
    return stats


# --- Migration Endpoint ---

@router.post("/migrate-from-json")
async def migrate_from_json(file: UploadFile = File(...)):
    """
    Migrate corpus entries from a JSON file.

    Expected JSON format:
    [
        {
            "id": "optional_id",
            "anfrage": "Natural language query",
            "sparql_query": "SELECT ...",
            "semantic_models": ["model1.ttl", "model2.ttl"],
            "semantic_models_content": {"model1.ttl": "RDF content..."},
            "sparql_operators": ["SELECT", "FILTER", ...] // optional, will be extracted if missing
        },
        ...
    ]
    """
    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        if not isinstance(data, list):
            raise HTTPException(
                status_code=400,
                detail="JSON file must contain a list of examples"
            )

        migrated_count = 0
        errors = []

        for i, item in enumerate(data):
            try:
                # Extract required fields
                nl_query = item.get('anfrage') or item.get('natural_language_query')
                sparql_query = item.get('sparql_query')

                if not nl_query or not sparql_query:
                    errors.append(f"Item {i}: Missing 'anfrage' or 'sparql_query'")
                    continue

                # Get semantic models
                semantic_models = item.get('semantic_models', [])

                # Get or format semantic models content
                semantic_models_content = None
                if 'semantic_models_content' in item:
                    content_dict = item['semantic_models_content']
                    if isinstance(content_dict, dict):
                        blocks = []
                        for model_name, model_content in content_dict.items():
                            blocks.append(f"Model: {model_name}\n```\n{model_content}\n```")
                        semantic_models_content = "\n\n".join(blocks)
                    elif isinstance(content_dict, str):
                        semantic_models_content = content_dict

                # Add entry
                entry = add_corpus_entry(
                    natural_language_query=nl_query,
                    sparql_query=sparql_query,
                    semantic_models=semantic_models,
                    semantic_models_content=semantic_models_content,
                    source="migrated",
                    theme=item.get('theme')
                )
                migrated_count += 1
                logger.info(f"Migrated entry: {entry.id}")

            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")
                logger.error(f"Error migrating item {i}: {e}")

        return {
            "message": f"Migration completed",
            "migrated_count": migrated_count,
            "total_items": len(data),
            "errors": errors if errors else None
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migrate-from-path")
async def migrate_from_path(json_path: str):
    """
    Migrate corpus entries from a JSON file path on the server.

    This is useful for migrating the existing natural_language_to_sparql_queries.json file.
    """
    try:
        path = Path(json_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {json_path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise HTTPException(
                status_code=400,
                detail="JSON file must contain a list of examples"
            )

        migrated_count = 0
        errors = []

        for i, item in enumerate(data):
            try:
                nl_query = item.get('anfrage') or item.get('natural_language_query')
                sparql_query = item.get('sparql_query')

                if not nl_query or not sparql_query:
                    errors.append(f"Item {i}: Missing required fields")
                    continue

                semantic_models = item.get('semantic_models', [])

                semantic_models_content = None
                if 'semantic_models_content' in item:
                    content_dict = item['semantic_models_content']
                    if isinstance(content_dict, dict):
                        blocks = []
                        for model_name, model_content in content_dict.items():
                            blocks.append(f"Model: {model_name}\n```\n{model_content}\n```")
                        semantic_models_content = "\n\n".join(blocks)

                entry = add_corpus_entry(
                    natural_language_query=nl_query,
                    sparql_query=sparql_query,
                    semantic_models=semantic_models,
                    semantic_models_content=semantic_models_content,
                    source="migrated",
                    theme=item.get('theme')
                )
                migrated_count += 1

            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")

        return {
            "message": f"Migration from {json_path} completed",
            "migrated_count": migrated_count,
            "total_items": len(data),
            "errors": errors if errors else None
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in file: {e}")
    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Search Endpoint ---

@router.post("/search")
async def search_corpus_by_operators(operators: List[str], max_results: int = 5):
    """
    Search corpus entries by SPARQL operators.

    Returns entries ranked by operator similarity score.
    """
    from ..sparql_corpus import get_corpus_entries_by_operators

    results = get_corpus_entries_by_operators(operators, max_results=max_results)

    return {
        "query_operators": operators,
        "results": results,
        "total_matches": len(results)
    }
