"""
Query refinement.

A semantic model states that a property holds a string, not which strings
occur. A filter written from the question alone can therefore miss: asking in
German about "Kobalt" does not match data that spells it "Cobalt", and the user
sees an empty result for a question the data can answer.

When a query comes back empty, the agent looks at the values actually present
and tries again. Both rounds happen between the browser and the backend without
surfacing in the conversation; only the final result is reported.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# How often a question may be re-queried before the agent reports back.
MAX_QUERY_REFINEMENTS = 2

# Literals sampled per property when probing what the data contains.
VALUE_PROBE_LIMIT = 15

# Properties probed in one round. Real questions filter on far fewer, and the
# cap keeps the probe query small.
MAX_PROBED_PROPERTIES = 6


def extract_filtered_properties(sparql_query: str) -> List[str]:
    """Return the properties a query compares against a literal.

    Only these matter when a query comes back empty: a filter on a value that
    does not occur is the common cause, and the properties involved say what to
    sample from the data.
    """
    # A property bound to a variable that is later compared with a string.
    bindings = re.findall(r"(\w+:\w+)\s+\?(\w+)", sparql_query)
    compared = set(re.findall(r"\?(\w+)\s*=\s*[\"']", sparql_query))
    compared |= set(re.findall(r"\?(\w+)\s*,\s*[\"']", sparql_query))  # CONTAINS, STRSTARTS

    properties = [prop for prop, var in bindings if var in compared]

    # A literal written straight into a triple pattern counts too.
    properties += re.findall(r"(\w+:\w+)\s+[\"'][^\"']+[\"']", sparql_query)

    seen: set = set()
    unique: List[str] = []
    for prop in properties:
        if prop not in seen:
            seen.add(prop)
            unique.append(prop)
    return unique


def build_value_probe_query(properties: List[str], prefixes: str) -> Optional[str]:
    """Build a query sampling the literals present for the given properties.

    Written as a single UNION so one round trip to the browser answers for
    every property at once.
    """
    if not properties:
        return None

    probed = properties[:MAX_PROBED_PROPERTIES]
    blocks = [
        '  { ?s %s ?value . BIND("%s" AS ?property) }' % (prop, prop)
        for prop in probed
    ]
    body = "\n  UNION\n".join(blocks)

    return (
        prefixes.strip()
        + "\n\nSELECT DISTINCT ?property ?value WHERE {\n"
        + body
        + "\n  FILTER(isLiteral(?value))\n}"
        + "\nLIMIT %d" % (VALUE_PROBE_LIMIT * len(probed))
    )


def summarise_observed_values(results: List[Dict]) -> Dict[str, List[str]]:
    """Group probe results into {property: [values]}."""

    def cell(row, key):
        value = row.get(key)
        return value.get("value") if isinstance(value, dict) else value

    grouped: Dict[str, List[str]] = {}
    for row in results or []:
        prop, value = cell(row, "property"), cell(row, "value")
        if not prop or value is None:
            continue
        values = grouped.setdefault(str(prop), [])
        if str(value) not in values and len(values) < VALUE_PROBE_LIMIT:
            values.append(str(value))
    return grouped


def build_retry_instruction(observed: Dict[str, List[str]], failed_query: str) -> str:
    """Tell the model which values exist, and ask it to write the query again."""
    hint = "\n".join(
        "- %s occurs with: %s" % (prop, ", ".join(values))
        for prop, values in observed.items()
    )
    return (
        "A previous query returned nothing because it filtered on values that do "
        "not occur in this data. These are the values actually present:\n"
        + hint
        + "\n\nWrite the query again, filtering only on values from that list. "
        "Keep the intent of the question: choose the listed value that "
        "corresponds to what was asked, even where the wording or the language "
        "differs.\n\nThe query that returned nothing:\n"
        + failed_query
    )


def prefixes_of(sparql_query: str) -> str:
    """Return the PREFIX block of a query, so a probe can reuse it."""
    return "\n".join(
        line
        for line in sparql_query.splitlines()
        if line.strip().upper().startswith("PREFIX")
    )
