"""The JSON schemas for structured output stay within the limits of the Anthropic API.

The API refuses a schema with more than 16 union-typed parameters (type arrays or anyOf) and an
enum value that does not match the declared type. Offline tests never call the API, so these
limits are checked here.
"""
import pytest

from classifier import RESULT_SCHEMA
from offerte_reader import COMPARISON_SCHEMA
from overname_reader import TAKEOVER_SCHEMA
from pdf_reader import DOCUMENT_SCHEMA, INVOICE_SCHEMA

MAX_UNIONS = 16
SCHEMAS = {
    "classifier": RESULT_SCHEMA,
    "quotes": COMPARISON_SCHEMA,
    "takeover": TAKEOVER_SCHEMA,
    "documents": DOCUMENT_SCHEMA,
    "invoices": INVOICE_SCHEMA,
}
JSON_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}


def _walk(schema):
    yield schema
    for sub in schema.get("properties", {}).values():
        yield from _walk(sub)
    if isinstance(schema.get("items"), dict):
        yield from _walk(schema["items"])
    for sub in schema.get("anyOf", []):
        yield from _walk(sub)


@pytest.mark.parametrize("name", SCHEMAS)
def test_union_types_within_limit(name):
    unions = sum(1 for node in _walk(SCHEMAS[name]) if isinstance(node.get("type"), list) or "anyOf" in node)
    assert unions <= MAX_UNIONS


@pytest.mark.parametrize("name", SCHEMAS)
def test_enum_values_match_type(name):
    for node in _walk(SCHEMAS[name]):
        if "enum" not in node:
            continue
        types = node["type"] if isinstance(node.get("type"), list) else [node.get("type")]
        allowed = tuple(JSON_TYPES[t] for t in types)
        for value in node["enum"]:
            assert isinstance(value, allowed), (name, value, types)
