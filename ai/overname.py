"""Read the deed and the minutes of a building taken over from another syndic, as a proposal in Odoo.

A staff member adds the deed (text PDF or scan) and the minutes of the last general assemblies
to a takeover in Odoo (VME > Configuratie > Overstap uit ander pakket). Odoo marks it "te lezen".
This script fetches those PDFs, lets Claude (or the mock) read lots, shares, keys, the data of the
VME, open decisions, procedures and mandates, with the page and fragment of each value, and hands
the readings to Odoo (vme.migration.vme_ai_apply_takeover). Odoo turns them into proposal lines;
a staff member accepts or rejects each line next to its fragment. Nothing is created before the
import, which runs the usual checks (the shares of a key must add up, and so on).

    python overname.py                        # Claude, puts the proposals in Odoo
    python overname.py --mock                 # rule-based stand-in, offline and always the same
    python overname.py --mock --dry-run       # only show what was read
    python overname.py --mock --bestand ../addons/vme_belgie/demo_data/migratie/residentie-wilg-documenten/basisakte.pdf
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

from assistant import load_env
from classifier import RefusalError
from odoo_api import OdooError
from overname_reader import ClaudeTakeoverReader, MockTakeoverReader
from pdf_facturen import all_companies_context, connect

HERE = Path(__file__).resolve().parent
KINDS = {"deed": "basisakte", "minutes": "notulen", "other": "ander document"}


def pending_migrations(odoo, context, ids=None):
    """Takeovers whose documents wait for a reading."""
    domain = [("ai_state", "=", "to_read")]
    if ids:
        domain.append(("id", "in", list(ids)))
    return odoo.execute("vme.migration", "search_read", domain, fields=["name", "document_ids"], order="id",
                        context=context)


def migration_documents(odoo, migration, context):
    """[(attachment id, file name, bytes)] of the PDFs to read, in the order they were added."""
    attachments = odoo.execute("ir.attachment", "read", migration["document_ids"], fields=["name", "datas", "mimetype"],
                               context=context)
    return [(a["id"], a["name"], base64.b64decode(a["datas"] or b"")) for a in sorted(attachments, key=lambda a: a["id"])]


SECTIONS = {"vme": "gegevens van de VME", "lots": "kavels", "keys": "sleutels", "works": "werken",
            "procedures": "procedures", "mandates": "mandaten"}


def describe(reading):
    """A few lines on what was read, for the terminal."""
    shares = [share for key in reading["keys"] for share in key["shares"]]
    counts = [f"{len(reading[name])} {label}" for name, label in SECTIONS.items() if reading[name]]
    lines = [f"    {KINDS[reading['document_kind']]}: {reading['summary']}",
             "    " + ", ".join(counts + ([f"{len(shares)} aandelen"] if shares else []))]
    for share in shares:
        if share["confidence"] == "low":
            lines.append(f"    ONZEKER aandeel {share['lot']} (blz. {share['page']}): {share['value'] or '-'} - {share['note']}")
    return "\n".join(lines)


def read_documents(documents, reader, out=print):
    """Read each (attachment id, name, bytes); returns the readings, or None if one could not be read."""
    readings, model = [], getattr(reader, "model", None)
    for attachment_id, name, data in documents:
        if not data.startswith(b"%PDF"):
            out(f"  {name}: geen PDF, overgeslagen.")
            continue
        try:
            reading, model = reader.read(data, name)
        except RefusalError as error:
            out(f"  {name}: {error} Lees dit document manueel.")
            return None, model
        out(f"  {name}, gelezen door {model}:\n{describe(reading)}")
        readings.append({"attachment_id": attachment_id, "file": name, **reading})
    return readings, model


def run(odoo, reader, dry_run=False, ids=None, out=print):
    """Read every pending takeover; returns {migration id: summary from Odoo, or None}."""
    context = all_companies_context(odoo)
    migrations = pending_migrations(odoo, context, ids)
    if not migrations:
        out("Geen overstap met documenten die op een AI-lezing wachten.")
    results = {}
    for migration in migrations:
        out(f"- {migration['name']} ({len(migration['document_ids'])} documenten)")
        readings, model = read_documents(migration_documents(odoo, migration, context), reader, out)
        if dry_run or not readings:
            results[migration["id"]] = None
            continue
        try:
            summary = odoo.execute("vme.migration", "vme_ai_apply_takeover", [migration["id"]], readings, model,
                                   context=context)
        except OdooError as error:
            out(f"  Niet in Odoo gezet: {error}")
            results[migration["id"]] = None
            continue
        results[migration["id"]] = summary
        out(f"  Voorstel in Odoo: {summary['lines']} regels, waarvan {summary['uncertain']} onzeker. "
            "Een medewerker kijkt elke regel na naast het fragment.")
    return results


def make_reader(mock):
    return MockTakeoverReader() if mock else ClaudeTakeoverReader()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lees de basisakte en de notulen van een overgenomen gebouw met AI.")
    parser.add_argument("--mock", action="store_true", help="geen taalmodel: vaste regels, offline")
    parser.add_argument("--dry-run", action="store_true", help="niets in Odoo zetten, alleen tonen")
    parser.add_argument("--bestand", type=Path, action="append", help="lees alleen dit PDF-bestand, zonder Odoo")
    parser.add_argument("--json", action="store_true", help="met --bestand: toon de volledige lezing als JSON")
    args = parser.parse_args(argv)
    load_env(HERE / ".env")

    if not args.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ontbreekt in ai/.env. Gebruik --mock om zonder taalmodel te testen.")
        return 2
    reader = make_reader(args.mock)
    if args.bestand:
        documents = [(None, path.name, path.read_bytes()) for path in args.bestand]
        readings, _model = read_documents(documents, reader, out=(lambda _text: None) if args.json else print)
        if args.json and readings:
            print(json.dumps(readings, indent=1, ensure_ascii=False))
        return 0 if readings is not None else 1
    odoo = connect()
    if odoo is None:
        return 1
    run(odoo, reader, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
