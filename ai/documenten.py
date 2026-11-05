"""Classify incoming documents (inspection reports, policies, quotes) and put them on the right VME.

Reads every PDF in ai/documenten_inbox/, lets Claude (or the mock) decide which VME it is about
and what kind of document it is, and hands it to Odoo (vme.association.vme_receive_document).
Odoo stores it on the VME with a message in the chatter. Filing it in the right folder is
done by document management (step 15) through the extension point _vme_document_folder.

    python documenten.py --mock --dry-run   # show the classification, write nothing
    python documenten.py --mock             # put the documents on the VME's in Odoo
    python documenten.py                    # with Claude
"""
import argparse
import base64
import os
import sys
from pathlib import Path

from assistant import load_env
from classifier import RefusalError
from odoo_api import VmeDirectory
from pdf_facturen import connect
from pdf_reader import DOCUMENT_TYPES, ClaudeDocumentClassifier, MockDocumentClassifier

HERE = Path(__file__).resolve().parent


def read_documents(folder):
    return [(path, path.read_bytes()) for path in sorted(Path(folder).glob("*.pdf"))]


def run(documents, classifier, vmes, odoo=None, context=None, dry_run=False, out=print):
    """Classify and deliver every document; returns {file name: Odoo result, or None}."""
    names = {vme["id"]: vme["name"] for vme in vmes}
    results = {}
    for path, data in documents:
        try:
            result, model = classifier.classify(data, path.name)
        except RefusalError as error:
            out(f"- {path.name}: {error} Klasseer dit document manueel.")
            results[path.name] = None
            continue
        vme_name = names.get(result["association_id"])
        out(f"- {path.name}: {DOCUMENT_TYPES[result['document_type']]} / {vme_name or 'geen VME'} / "
            f"zekerheid {result['confidence']} ({model}) - {result['reason']}")
        if not vme_name:
            out("  Geen VME gevonden: niet in Odoo gezet, klasseer dit document manueel.")
            results[path.name] = None
            continue
        if dry_run:
            results[path.name] = None
            continue
        response = odoo.execute(
            "vme.association", "vme_receive_document", [result["association_id"]],
            path.name, base64.b64encode(data).decode(), result["document_type"],
            result["confidence"], result["reason"], model, context=context,
        )
        results[path.name] = response
        if response["duplicate"]:
            out("  Stond al bij deze VME, overgeslagen.")
        else:
            out(f"  Bij {vme_name} gezet; map: {response['folder'] or 'nog geen (documentbeheer volgt)'}.")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Klasseer binnenkomende documenten en zet ze bij de juiste VME.")
    parser.add_argument("--inbox", type=Path, default=HERE / "documenten_inbox", help="map met PDF-documenten")
    parser.add_argument("--mock", action="store_true", help="geen taalmodel: regels in plaats van Claude")
    parser.add_argument("--dry-run", action="store_true", help="niets in Odoo schrijven, alleen tonen")
    args = parser.parse_args(argv)
    load_env(HERE / ".env")

    documents = read_documents(args.inbox)
    if not documents:
        print(f"Geen documenten in {args.inbox}.")
        return 0
    if not args.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ontbreekt in ai/.env. Gebruik --mock om zonder taalmodel te testen.")
        return 2
    odoo = connect()
    if odoo is None:
        return 1
    directory = VmeDirectory(odoo)
    vmes = directory.load()
    classifier = MockDocumentClassifier(vmes) if args.mock else ClaudeDocumentClassifier(vmes)
    run(documents, classifier, vmes, odoo=odoo, context=directory.context, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
