"""
SPARQL Corpus Management for Adaptive Few-Shot Prompting.

Provides functions for:
- Extracting SPARQL operators from queries
- Calculating operator similarity between queries
- Managing corpus entries in the database
- Formatting examples for prompt injection
"""

import re
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timezone

from sqlmodel import Session, select

from .db import engine
from .models import SPARQLCorpusEntry

logger = logging.getLogger(__name__)


# --- Operator Extraction ---

def extract_sparql_operators(sparql_query: str) -> List[str]:
    """
    Extract SPARQL operators from a query using pattern matching.

    Returns a sorted list of unique operators found in the query.
    """
    operators = []

    # SPARQL keywords to detect
    keywords = [
        'SELECT', 'DISTINCT', 'WHERE', 'FILTER', 'OPTIONAL',
        'UNION', 'BIND', 'GROUP BY', 'ORDER BY', 'DESC', 'ASC',
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'LIMIT', 'OFFSET',
        'HAVING', 'NOT EXISTS', 'EXISTS', 'MINUS', 'VALUES',
        'SAMPLE', 'GROUP_CONCAT'
    ]

    # SPARQL functions and type conversions
    functions = [
        'CONTAINS', 'LCASE', 'UCASE', 'STRLEN', 'SUBSTR', 'STRSTARTS', 'STRENDS',
        'xsd:integer', 'xsd:string', 'xsd:decimal', 'xsd:date', 'xsd:boolean',
        'xsd:float', 'xsd:double', 'xsd:dateTime',
        'plasma:hasValue', 'REGEX', 'STR', 'LANG', 'DATATYPE',
        'IN', 'NOT IN', 'COALESCE', 'IF', 'IRI', 'URI', 'BNODE',
        'CONCAT', 'REPLACE', 'ABS', 'ROUND', 'CEIL', 'FLOOR',
        'YEAR', 'MONTH', 'DAY', 'HOURS', 'MINUTES', 'SECONDS',
        'NOW', 'UUID', 'STRUUID', 'BOUND', 'ISIRI', 'ISBLANK', 'ISLITERAL'
    ]

    query_normalized = sparql_query.upper()

    # Check for keywords (word boundary matching)
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_normalized):
            operators.append(keyword)

    # Check for functions (case-sensitive for prefixed ones)
    for func in functions:
        if func.startswith('xsd:') or func.startswith('plasma:'):
            # Case-sensitive check for prefixed functions
            if func in sparql_query:
                operators.append(func)
        else:
            pattern = r'\b' + re.escape(func) + r'\b'
            if re.search(pattern, query_normalized):
                operators.append(func)

    return sorted(list(set(operators)))


def categorize_complexity(
    operators: List[str],
    sparql_query: str,
    is_multi_model: bool = False
) -> str:
    """
    Determine query complexity based on operators and structure.

    Returns: 'basic', 'intermediate', or 'advanced'
    """
    advanced_ops = {'UNION', 'GROUP BY', 'ORDER BY', 'HAVING', 'NOT EXISTS', 'MINUS', 'VALUES'}
    intermediate_ops = {'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'BIND', 'OPTIONAL', 'COALESCE', 'SAMPLE', 'GROUP_CONCAT'}

    # Check for advanced operators
    if any(op in operators for op in advanced_ops):
        return 'advanced'

    # Check for intermediate operators
    if any(op in operators for op in intermediate_ops):
        return 'intermediate'

    # Multiple FILTERs indicate intermediate complexity
    filter_count = sparql_query.upper().count('FILTER')
    if filter_count >= 2:
        return 'intermediate'

    # Multi-model queries are at least intermediate
    if is_multi_model:
        return 'intermediate'

    return 'basic'


def count_triple_patterns(sparql_query: str) -> int:
    """Count approximate number of triple patterns in a SPARQL query."""
    # Simple heuristic: count lines with triple pattern structure
    # Look for patterns like: ?subject predicate ?object or ?subject predicate "literal"
    pattern = r'\?\w+\s+[\w:]+\s+[\?\w":]+\s*[.;]'
    matches = re.findall(pattern, sparql_query)
    return len(matches)


# --- Similarity Calculation ---

def calculate_operator_similarity(
    query_operators: Set[str],
    corpus_operators: Set[str],
    intersection_weight: float = 0.4,
    coverage_weight: float = 0.6
) -> float:
    """
    Calculate similarity between two sets of operators using Jaccard + coverage.

    Formula: (jaccard_score * intersection_weight) + (coverage_score * coverage_weight)

    Args:
        query_operators: Operators from the target query
        corpus_operators: Operators from a corpus entry
        intersection_weight: Weight for Jaccard similarity (default 0.4)
        coverage_weight: Weight for coverage score (default 0.6)

    Returns:
        Combined similarity score between 0 and 1
    """
    if not query_operators and not corpus_operators:
        return 0.0

    intersection = query_operators.intersection(corpus_operators)
    union = query_operators.union(corpus_operators)

    jaccard_score = len(intersection) / len(union) if union else 0.0
    coverage_score = len(intersection) / len(query_operators) if query_operators else 0.0

    combined_score = (jaccard_score * intersection_weight) + (coverage_score * coverage_weight)

    return combined_score


# --- Database Operations ---

def get_corpus_entries_by_operators(
    target_operators: List[str],
    max_results: int = 2,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Find best matching SPARQL examples from the database based on operator matching.

    Args:
        target_operators: List of predicted operators to match
        max_results: Maximum number of results to return
        min_score: Minimum similarity score threshold

    Returns:
        List of matching corpus entries with relevance scores
    """
    if not target_operators:
        logger.warning("No target operators provided, returning empty results")
        return []

    target_set = set(op.upper() for op in target_operators)
    scored_entries = []

    with Session(engine) as session:
        # Load all corpus entries
        statement = select(SPARQLCorpusEntry)
        entries = session.exec(statement).all()

        logger.debug(f"Searching {len(entries)} corpus entries for operators: {target_operators}")

        for entry in entries:
            entry_operators = set(op.upper() for op in entry.sparql_operators)

            # Calculate similarity
            combined_score = calculate_operator_similarity(target_set, entry_operators)

            if combined_score >= min_score:
                intersection = target_set.intersection(entry_operators)

                scored_entry = {
                    "entry_id": entry.id,
                    "natural_language_query": entry.natural_language_query,
                    "user_query": entry.natural_language_query,  # Alias for compatibility
                    "sparql_query": entry.sparql_query,
                    "complete_sparql": entry.sparql_query,  # Alias for compatibility
                    "operators": entry.sparql_operators,
                    "complexity": entry.complexity,
                    "semantic_models": entry.semantic_models_content or "",
                    "model_hints": "Example from corpus.",
                    "source": entry.source,
                    "relevance_score": combined_score,
                    "matching_operators": list(intersection),
                    "exact_matches": len(intersection)
                }
                scored_entries.append(scored_entry)

    # Sort by relevance score (descending)
    scored_entries.sort(key=lambda x: x["relevance_score"], reverse=True)

    logger.info(f"Found {len(scored_entries)} matching corpus entries for operators: {target_operators}")
    for entry in scored_entries[:max_results]:
        logger.info(f"  - {entry['entry_id']}: score={entry['relevance_score']:.3f}, matches={entry['matching_operators']}")

    return scored_entries[:max_results]


def add_corpus_entry(
    natural_language_query: str,
    sparql_query: str,
    semantic_models: List[str] = None,
    semantic_models_content: str = None,
    source: str = "manual",
    theme: str = None
) -> SPARQLCorpusEntry:
    """
    Add a new corpus entry to the database with auto-extracted metadata.

    Args:
        natural_language_query: The user's natural language query
        sparql_query: The correct SPARQL query
        semantic_models: List of semantic model filenames
        semantic_models_content: Full RDF content of semantic models
        source: Origin of the entry (manual, learned, migrated)
        theme: Optional category/theme

    Returns:
        The created SPARQLCorpusEntry
    """
    # Auto-extract operators
    operators = extract_sparql_operators(sparql_query)

    # Determine if multi-model
    is_multi_model = len(semantic_models) > 1 if semantic_models else False

    # Calculate complexity
    complexity = categorize_complexity(operators, sparql_query, is_multi_model)

    with Session(engine) as session:
        entry = SPARQLCorpusEntry(
            natural_language_query=natural_language_query,
            sparql_query=sparql_query,
            sparql_operators=operators,
            complexity=complexity,
            semantic_models=semantic_models or [],
            semantic_models_content=semantic_models_content,
            is_multi_model=is_multi_model,
            source=source,
            theme=theme
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        logger.info(f"Added corpus entry {entry.id}: {len(operators)} operators, complexity={complexity}")
        return entry


def update_corpus_entry_metrics(entry_id: str, was_successful: bool) -> None:
    """
    Update usage count and success rate for a corpus entry.

    Args:
        entry_id: ID of the corpus entry
        was_successful: Whether the query generation was successful
    """
    with Session(engine) as session:
        entry = session.get(SPARQLCorpusEntry, entry_id)
        if entry:
            entry.usage_count += 1
            # Update success rate as running average
            old_rate = entry.success_rate
            old_count = entry.usage_count - 1
            if old_count > 0:
                entry.success_rate = (old_rate * old_count + (1.0 if was_successful else 0.0)) / entry.usage_count
            else:
                entry.success_rate = 1.0 if was_successful else 0.0

            entry.updated_at = datetime.now(timezone.utc)
            session.add(entry)
            session.commit()
            logger.debug(f"Updated metrics for {entry_id}: usage={entry.usage_count}, success_rate={entry.success_rate:.2f}")


def get_all_corpus_entries() -> List[SPARQLCorpusEntry]:
    """Get all corpus entries from the database."""
    with Session(engine) as session:
        statement = select(SPARQLCorpusEntry).order_by(SPARQLCorpusEntry.created_at.desc())
        return list(session.exec(statement).all())


def get_corpus_entry_by_id(entry_id: str) -> Optional[SPARQLCorpusEntry]:
    """Get a specific corpus entry by ID."""
    with Session(engine) as session:
        return session.get(SPARQLCorpusEntry, entry_id)


def delete_corpus_entry(entry_id: str) -> bool:
    """Delete a corpus entry by ID."""
    with Session(engine) as session:
        entry = session.get(SPARQLCorpusEntry, entry_id)
        if entry:
            session.delete(entry)
            session.commit()
            logger.info(f"Deleted corpus entry {entry_id}")
            return True
        return False


def get_corpus_stats() -> Dict[str, Any]:
    """Get statistics about the corpus."""
    with Session(engine) as session:
        statement = select(SPARQLCorpusEntry)
        entries = list(session.exec(statement).all())

        if not entries:
            return {
                "total_entries": 0,
                "unique_operators": 0,
                "all_operators": [],
                "complexity_distribution": {},
                "source_distribution": {}
            }

        all_operators = set()
        complexity_distribution = {}
        source_distribution = {}

        for entry in entries:
            all_operators.update(entry.sparql_operators)

            complexity = entry.complexity
            complexity_distribution[complexity] = complexity_distribution.get(complexity, 0) + 1

            source = entry.source
            source_distribution[source] = source_distribution.get(source, 0) + 1

        return {
            "total_entries": len(entries),
            "unique_operators": len(all_operators),
            "all_operators": sorted(list(all_operators)),
            "complexity_distribution": complexity_distribution,
            "source_distribution": source_distribution
        }


# --- Formatting for Prompts ---

def format_examples_for_prompt(matching_entries: List[Dict[str, Any]]) -> str:
    """
    Format found corpus entries as few-shot examples for the SPARQL generation prompt.

    Args:
        matching_entries: List of corpus entries with relevance scores

    Returns:
        Formatted string ready for prompt injection
    """
    if not matching_entries:
        return ""

    formatted_examples = ["Here are some examples of how to solve the task:"]

    for i, entry in enumerate(matching_entries, 1):
        user_query = entry.get('user_query', entry.get('natural_language_query', 'Unknown query'))
        semantic_models = entry.get('semantic_models', 'No semantic models available')
        model_hints = entry.get('model_hints', 'The model is suitable.')
        sparql_query = entry.get('complete_sparql', entry.get('sparql_query', 'No SPARQL query available'))

        example_block = f'''--- Example {i} ---
User query: "{user_query}"
Semantic models:

{semantic_models}

Hints from model check: {model_hints}
Answer:
{sparql_query}
--- End Example {i} ---

'''
        formatted_examples.append(example_block)

    return "\n".join(formatted_examples)


def get_all_operators() -> List[str]:
    """Returns a list of all unique operators in the corpus."""
    with Session(engine) as session:
        statement = select(SPARQLCorpusEntry)
        entries = list(session.exec(statement).all())

        all_operators = set()
        for entry in entries:
            all_operators.update(entry.sparql_operators)

        # Add standard operators that should always be available
        standard_operators = [
            'SELECT', 'DISTINCT', 'WHERE', 'FILTER', 'OPTIONAL',
            'UNION', 'BIND', 'GROUP BY', 'ORDER BY', 'DESC', 'ASC',
            'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'LIMIT',
            'CONTAINS', 'LCASE', 'REGEX', 'STR',
            'xsd:integer', 'xsd:string', 'xsd:decimal', 'xsd:date',
            'plasma:hasValue'
        ]
        all_operators.update(standard_operators)

        return sorted(list(all_operators))
