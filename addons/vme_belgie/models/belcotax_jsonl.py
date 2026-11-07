"""Belcotax-on-web JSON Lines for the 281.50 forms, income years from 2026.

From income year 2026 the new Belcotax-on-web ("BOW 2.0", in production from February 2027) accepts only
JSON Lines: the old XML structure (v, a, f and r tags) is refused. One line per object: first the
resources (the contact person, the VME as debtor, each beneficiary as person or organisation), then one
fiche per beneficiary that refers to them by key.

Written from the JSON schemas "schemas preproduction BOW" (October 2026, data/belcotax/2026/), the examples
"ExamplesBelcotax2026" and the brochure "Pre-opening Belcotax-on-web" (version 2, 03.11.2026) of the FOD
Financiën. These are pre-production documents: the final version follows at the end of 2026. Every file is
validated against the schemas before it is handed to the user. Plain Python without Odoo; nothing is sent.
"""
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .belcotax_xml import CATEGORIES, kbo, national_number, rsz_country

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "data" / "belcotax" / "2026"
FIRST_JSONL_YEAR = 2026
SCHEMA_CONTACT = "urn:r:d:c:1"
SCHEMA_ORGANISATION = "urn:r:d:o:1"
SCHEMA_PERSON = "urn:r:d:p:1"
SCHEMA_FILES = {
    SCHEMA_CONTACT: "resource_contact_nl.json",
    SCHEMA_ORGANISATION: "resource_organisation_nl.json",
    SCHEMA_PERSON: "resource_person_nl.json",
    "urn:f:d:2026:50:2": "fiche_2026_50_2_nl.json",
}
# Zones of the amounts per category on the 281.50. The total 2.064 is computed by Belcotax ("readOnly").
AMOUNT_ZONES = {"commission": "2060", "fees": "2061", "benefits": "2062", "expenses": "2063"}


def uses_jsonl(year):
    """Belcotax-on-web wants JSON Lines for this income year (and no longer the XML)."""
    # LEGAL-CHECK: brochure Pre-opening Belcotax-on-web (03.11.2026), 2.2 - for income year 2026 the old
    # structure with tags v, a, f and r is not allowed for sendings per file; only JSON Lines.
    return year >= FIRST_JSONL_YEAR


def fiche_schema(year):
    """Schema id of the 281.50 of an income year (version 2 of the schema for 2026)."""
    return f"urn:f:d:{year}:50:2"


def phone(number):
    """A phone number as +32..., the only form the schema accepts, or "" when it cannot be made so."""
    number = re.sub(r"[^\d+]", "", number or "")
    if number.startswith("00"):
        number = "+" + number[2:]
    elif number.startswith("0"):
        number = "+32" + number[1:]
    return number if re.fullmatch(r"\+[0-9]{9,15}", number) else ""


@dataclass
class Contact:
    """The staff member who prepared the file: Belcotax mails its feedback to him."""
    key: str
    name: str
    email: str
    phone: str = ""
    language: str = "nl"


def _cut(value, length):
    return (value or "").strip()[:length]


def _address(street, zip_code, city, country):
    """The address object, or None when we do not know the country code (the schema requires it)."""
    code = rsz_country(country)
    if not code:
        return None
    address = {"s": _cut(street, 100), "p": _cut(zip_code, 50), "c": _cut(city, 100), "l": code}
    return {key: value for key, value in address.items() if value}


def _organisation(key, name, company_number="", vat="", address=None):
    line = {"$s": SCHEMA_ORGANISATION, "k": key}
    identification = {}
    if kbo(company_number):
        identification["cbein"] = kbo(company_number)
    elif vat and re.fullmatch(r"[A-Z]{2}[A-Z0-9]+", vat) and not vat.startswith("BE"):
        identification["vat"] = vat[:25]  # a foreign company without Belgian company number
    if identification:
        line["i"] = identification
    line["n"] = {"nl": _cut(name, 255)}
    if address:
        line["a"] = address
    return line


def _person(fiche):
    line = {"$s": SCHEMA_PERSON, "k": fiche.beneficiary_key}
    identification = {}
    if national_number(fiche.national_number):
        identification["ssin"] = national_number(fiche.national_number)
    if kbo(fiche.kbo):
        identification["cbein"] = kbo(fiche.kbo)
    if identification:
        line["i"] = identification
    if fiche.first_names:
        line["fn"] = [_cut(fiche.first_names, 50)]
    if fiche.name:
        line["ln"] = [_cut(fiche.name, 50)]
    address = _address(fiche.street, fiche.zip, fiche.city, fiche.country)
    if address:
        line["a"] = address
    return line


def _euro(cents_amount):
    return float(Decimal(cents_amount) / 100)


def build_belcotax_jsonl(year, debtor, contact, fiches):
    """The file for one VME (the debtor) and one income year: resources first, then one fiche per beneficiary."""
    lines = []
    contact_line = {"$s": SCHEMA_CONTACT, "k": contact.key, "ln": [_cut(contact.name, 50)],
                    "e": contact.email, "l": contact.language}
    if phone(contact.phone):
        contact_line["p"] = {"l": phone(contact.phone)}
    lines.append(contact_line)
    lines.append(_organisation(debtor.key, debtor.name, debtor.kbo,
                               address=_address(debtor.street, debtor.zip, debtor.city, debtor.country)))
    for fiche in fiches:
        if fiche.is_company:
            lines.append(_organisation(fiche.beneficiary_key, fiche.name, fiche.kbo, fiche.vat,
                                       _address(fiche.street, fiche.zip, fiche.city, fiche.country)))
        else:
            lines.append(_person(fiche))
    for fiche in fiches:
        line = {"$s": fiche_schema(year), "k": fiche.key, "2010": str(fiche.sequence)}
        for category in CATEGORIES:
            if fiche.amount(category):
                line[AMOUNT_ZONES[category]] = _euro(fiche.amount(category))
        if fiche.profession:
            line["2107"] = fiche.profession
        line.update({"b": fiche.beneficiary_key, "c": contact.key, "d": debtor.key})
        lines.append(line)
    return "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines).encode()


# Offline validation against the official JSON schemas. The Odoo image has no jsonschema package, so this
# checks the keywords those schemas use (draft 2020-12): type, const, enum, oneOf, properties,
# additionalProperties, required, minimum, multipleOf, pattern, min/maxLength, items, min/maxItems,
# minProperties and $ref to $defs. Unknown keywords ("title", "unit", "zoneType", ...) are annotations.

_TYPES = {"string": str, "object": dict, "array": list, "boolean": bool}
_SCHEMAS = {}


def _schema(schema_id):
    if schema_id not in _SCHEMAS:
        _SCHEMAS[schema_id] = json.loads((SCHEMA_DIR / SCHEMA_FILES[schema_id]).read_text())
    return _SCHEMAS[schema_id]


def _is_type(value, kind):
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


def _check(value, schema, root, path, errors):
    if "$ref" in schema:
        _check(value, root["$defs"][schema["$ref"].split("/")[-1]], root, path, errors)
    kinds = schema.get("type")
    if kinds and not any(_is_type(value, kind) for kind in ([kinds] if isinstance(kinds, str) else kinds)):
        errors.append(f"{path}: verwacht {kinds}")
        return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: moet {schema['const']!r} zijn")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} niet in {schema['enum']}")
    if "oneOf" in schema:
        matches = sum(1 for option in schema["oneOf"] if not _errors(value, option, root, path))
        if matches != 1:
            errors.append(f"{path}: {value!r} past niet op precies één keuze")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            errors.append(f"{path}: lengte {len(value)} buiten de grenzen")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} past niet op {schema['pattern']}")
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: kleiner dan {schema['minimum']}")
        if "multipleOf" in schema and Decimal(str(value)) % Decimal(str(schema["multipleOf"])):
            errors.append(f"{path}: geen veelvoud van {schema['multipleOf']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            errors.append(f"{path}: aantal elementen buiten de grenzen")
        for index, item in enumerate(value):
            _check(item, schema.get("items", {}), root, f"{path}[{index}]", errors)
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: {key} ontbreekt")
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: te weinig eigenschappen")
        for key, item in value.items():
            if key in properties:
                _check(item, properties[key], root, f"{path}.{key}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: onbekende eigenschap {key}")


def _errors(value, schema, root, path):
    errors = []
    _check(value, schema, root, path, errors)
    return errors


def validate(data):
    """Validate a JSON Lines file against the official schemas; return the errors (empty when valid)."""
    errors = []
    keys = set()
    for number, text in enumerate(data.decode().splitlines(), start=1):
        line = json.loads(text)
        schema_id = re.sub(r":(nl|fr|de)$", "", line.get("$s", ""))
        # Only the schema of 2026 is published: a later year is checked against its structure.
        lookup = re.sub(r"^urn:f:d:\d{4}:", "urn:f:d:2026:", schema_id)
        if lookup not in SCHEMA_FILES:
            errors.append(f"regel {number}: geen schema voor {line.get('$s')!r}")
            continue
        schema = dict(_schema(lookup))
        if lookup != schema_id:
            schema["properties"] = dict(schema["properties"], **{"$s": {"type": "string"}})
        errors += _errors(line, schema, schema, f"regel {number}")
        # LEGAL-CHECK: brochure Pre-opening Belcotax-on-web (03.11.2026), 6.1 - a key is unique per sender
        # and may appear only once in a sending; a new sending with the same key replaces the fiche.
        if (line.get("$s"), line.get("k")) in keys:
            errors.append(f"regel {number}: sleutel {line.get('k')!r} komt twee keer voor")
        keys.add((line.get("$s"), line.get("k")))
    return errors[:5]

