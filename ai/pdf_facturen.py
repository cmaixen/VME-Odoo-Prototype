"""Read vendor bills that arrived as a PDF without UBL, and fill the drafts in Odoo.

Odoo marks such a draft bill "Te lezen door AI" (mail to the bill address or upload). This
script fetches each one's PDF, lets Claude (or the mock) read supplier, VAT number, invoice
number, dates, cost period, amounts and IBAN with a confidence per field, and hands that to
Odoo (account.move.vme_ai_apply_reading). Odoo checks every field and fills the draft; the
distribution rules then set key and account. Nothing is posted or paid, no supplier and no
bank account is created: a staff member reviews the draft.

    python pdf_facturen.py                   # Claude, fills the drafts in Odoo
    python pdf_facturen.py --mock            # rule-based stand-in, no API key needed
    python pdf_facturen.py --mock --dry-run  # only show what was read
    python pdf_facturen.py --mock --bestand ../addons/vme_belgie/demo_data/facturen_pdf/x.pdf
"""
import argparse
import base64
import os
import sys
from pathlib import Path

from assistant import load_env
from classifier import RefusalError
from odoo_api import OdooClient, OdooError
from pdf_reader import READING_FIELDS, ClaudeInvoiceReader, MockInvoiceReader

HERE = Path(__file__).resolve().parent
STATUS_LABELS = {"ok": "in orde", "warning": "NAKIJKEN", "danger": "GEVAAR"}


def all_companies_context(odoo):
    user = odoo.execute("res.users", "read", [odoo.uid], fields=["company_ids"])[0]
    return {"allowed_company_ids": user["company_ids"]}


def pending_bills(odoo, context, ids=None):
    """Draft bills of all VME's that wait for an AI reading."""
    domain = [("vme_ai_state", "=", "to_read"), ("state", "=", "draft")]
    if ids:
        domain.append(("id", "in", list(ids)))
    return odoo.execute(
        "account.move", "search_read", domain,
        fields=["name", "company_id", "invoice_source_email", "message_main_attachment_id"],
        order="id", context=context,
    )


def bill_pdf(odoo, bill, context):
    """(file name, bytes) of the bill's PDF, or None. Prefers the main attachment."""
    attachments = odoo.execute(
        "ir.attachment", "search_read",
        [("res_model", "=", "account.move"), ("res_id", "=", bill["id"]), ("mimetype", "=", "application/pdf")],
        fields=["name", "datas"], order="id", context=context,
    )
    main = bill.get("message_main_attachment_id") and bill["message_main_attachment_id"][0]
    attachments.sort(key=lambda a: a["id"] != main)
    if not attachments:
        return None
    return attachments[0]["name"], base64.b64decode(attachments[0]["datas"])


def format_reading(reading):
    width = max(len(label) for _code, label in READING_FIELDS)
    return "\n".join(
        f"    {label:<{width}}  {reading[code]['value'] or '-'}  ({reading[code]['confidence']})"
        for code, label in READING_FIELDS
    )


def run(odoo, reader, dry_run=False, ids=None, out=print):
    """Read every pending bill; returns {bill id: summary from Odoo, or None}."""
    context = all_companies_context(odoo)
    bills = pending_bills(odoo, context, ids)
    if not bills:
        out("Geen facturen die op een AI-lezing wachten.")
    results = {}
    for bill in bills:
        label = f"{bill['company_id'][1]}: concept {bill['id']} ({bill['invoice_source_email'] or 'upload'})"
        pdf = bill_pdf(odoo, bill, context)
        if not pdf:
            out(f"- {label}: geen PDF gevonden, overgeslagen.")
            results[bill["id"]] = None
            continue
        name, data = pdf
        try:
            reading, model = reader.read(data, name)
        except RefusalError as error:
            out(f"- {label}: {error} Vul deze factuur manueel in.")
            results[bill["id"]] = None
            continue
        out(f"- {label}, {name}, gelezen door {model}:")
        if dry_run:
            out(format_reading(reading))
            results[bill["id"]] = None
            continue
        try:
            summary = odoo.execute("account.move", "vme_ai_apply_reading", [bill["id"]], reading, model,
                                   context=context)
        except OdooError as error:
            out(f"  Niet ingevuld: {error}")
            results[bill["id"]] = None
            continue
        results[bill["id"]] = summary
        out(
            f"  Ingevuld: {summary['partner'] or 'leverancier onbekend'}, {summary['ref'] or 'zonder nummer'}, "
            f"{summary['amount_total']:.2f} EUR, sleutel: {', '.join(summary['keys']) or 'geen'}; "
            f"{summary['danger']} gevaar, {summary['warning']} om na te kijken."
        )
        for check in summary["checks"]:
            if check["status"] != "ok":
                out(f"    {STATUS_LABELS[check['status']]} {check['field']}: {check['message']}")
    return results


def connect():
    url = os.environ.get("ODOO_URL", "http://localhost:8069")
    try:
        return OdooClient(
            url,
            os.environ.get("ODOO_DB", "vme_demo"),
            os.environ.get("ODOO_USER", "admin"),
            os.environ.get("ODOO_PASSWORD", "admin"),
        )
    except (OSError, OdooError) as error:
        print(f"Kan Odoo niet bereiken op {url}: {error}")
        return None


def make_reader(mock):
    return MockInvoiceReader() if mock else ClaudeInvoiceReader()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lees PDF-facturen zonder UBL met AI en vul de concepten in Odoo in.")
    parser.add_argument("--mock", action="store_true", help="geen taalmodel: regels in plaats van Claude")
    parser.add_argument("--dry-run", action="store_true", help="niets in Odoo invullen, alleen tonen")
    parser.add_argument("--bestand", type=Path, help="lees alleen dit PDF-bestand, zonder Odoo")
    args = parser.parse_args(argv)
    load_env(HERE / ".env")

    if not args.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ontbreekt in ai/.env. Gebruik --mock om zonder taalmodel te testen.")
        return 2
    reader = make_reader(args.mock)
    if args.bestand:
        reading, model = reader.read(args.bestand.read_bytes(), args.bestand.name)
        print(f"{args.bestand.name}, gelezen door {model}:\n{format_reading(reading)}")
        return 0
    odoo = connect()
    if odoo is None:
        return 1
    run(odoo, reader, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
