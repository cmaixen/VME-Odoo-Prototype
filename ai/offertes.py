"""Compare the contractor quotes of works and put the comparison as a draft on the works in Odoo.

A staff member clicks "Offertes vergelijken" on works with two to four quote PDFs; Odoo then
makes a comparison "Wacht op AI". This script fetches the PDFs of every waiting comparison,
lets Claude (or the offline stand-in) read them, and hands the result to Odoo
(vme.works.comparison.vme_ai_apply_comparison). Odoo builds the table, checks the numbers and
keeps it as a draft: the syndic reviews, edits and approves it. Nothing is sent to anyone.

    python offertes.py                     # Claude, fills the waiting comparisons in Odoo
    python offertes.py --offline           # fixed rules, no API key and no network for the model
    python offertes.py --offline --dry-run # only show what was read
    python offertes.py --offline --bestand a.pdf b.pdf c.pdf   # without Odoo

Without ANTHROPIC_API_KEY in ai/.env the script runs offline by itself.
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
from offerte_reader import QUOTE_FIELDS, ClaudeQuoteComparer, OfflineQuoteComparer
from pdf_facturen import all_companies_context, connect

HERE = Path(__file__).resolve().parent
STATUS_LABELS = {"included": "inbegrepen", "excluded": "NIET inbegrepen", "absent": "niet vermeld"}


def pending_comparisons(odoo, context, ids=None):
    domain = [("state", "=", "to_read")]
    if ids:
        domain.append(("id", "in", list(ids)))
    return odoo.execute("vme.works.comparison", "search_read", domain,
                        fields=["name", "works_id", "association_id", "column_ids"], order="id", context=context)


def comparison_pdfs(odoo, comparison, context):
    """[(file name, bytes)] in column order; None when a column has no PDF."""
    columns = odoo.execute("vme.works.comparison.column", "search_read", [("id", "in", comparison["column_ids"])],
                           fields=["sequence", "attachment_id"], order="sequence, id", context=context)
    pdfs = []
    for column in columns:
        if not column["attachment_id"]:
            return None
        [attachment] = odoo.execute("ir.attachment", "read", [column["attachment_id"][0]], fields=["name", "datas"],
                                    context=context)
        pdfs.append((attachment["name"], base64.b64decode(attachment["datas"])))
    return pdfs


def format_comparison(comparison):
    lines = []
    labels = dict(QUOTE_FIELDS)
    for number, quote in enumerate(comparison["quotes"], 1):
        lines.append(f"    Offerte {number}: {quote['contractor']['value'] or '?'}")
        for code, label in labels.items():
            if code == "contractor":
                continue
            value, page = quote[code]["value"], quote[code]["page"]
            lines.append(f"      {label}: {value or '-'}" + (f" (p. {page})" if page else ""))
        for reservation in quote["reservations"]:
            lines.append(f"      Voorbehoud: {reservation['text']}" +
                         (f" (p. {reservation['page']})" if reservation["page"] else ""))
    for post in comparison["posts"]:
        cells = ", ".join(f"{item['quote']}: {STATUS_LABELS[item['status']]}"
                          + (f" {item['amount']}" if item["amount"] else "") for item in post["items"])
        lines.append(f"    Post {post['label']}: {cells}")
    lines.append(f"    Samenvatting: {comparison['summary']}")
    return "\n".join(lines)


def run(odoo, comparer, dry_run=False, ids=None, out=print):
    """Compare every waiting comparison; returns {comparison id: summary from Odoo, or None}."""
    context = all_companies_context(odoo)
    comparisons = pending_comparisons(odoo, context, ids)
    if not comparisons:
        out("Geen offertevergelijkingen die op AI wachten.")
    results = {}
    for comparison in comparisons:
        label = f"{comparison['association_id'][1]}: {comparison['works_id'][1]}"
        pdfs = comparison_pdfs(odoo, comparison, context)
        if not pdfs:
            out(f"- {label}: een offerte heeft geen PDF, overgeslagen.")
            results[comparison["id"]] = None
            continue
        try:
            result, model = comparer.compare(pdfs)
        except (RefusalError, ValueError) as error:
            out(f"- {label}: {error} Maak de vergelijking manueel.")
            results[comparison["id"]] = None
            continue
        out(f"- {label}, {len(pdfs)} offertes, gelezen door {model}:")
        if dry_run:
            out(format_comparison(result))
            results[comparison["id"]] = None
            continue
        try:
            summary = odoo.execute("vme.works.comparison", "vme_ai_apply_comparison", [comparison["id"]], result, model,
                                   context=context)
        except OdooError as error:
            out(f"  Niet ingevuld: {error}")
            results[comparison["id"]] = None
            continue
        results[comparison["id"]] = summary
        out(f"  Concept klaar op het werk: {summary['lines']} rijen, {len(summary['attention'])} aandachtspunt(en). "
            f"De syndicus kijkt het na en keurt het goed.")
        for point in summary["attention"]:
            out(f"    NAKIJKEN: {point}")
    return results


def make_comparer(offline):
    return OfflineQuoteComparer() if offline else ClaudeQuoteComparer()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Vergelijk offertes van aannemers met AI en zet een concept in Odoo.")
    parser.add_argument("--offline", "--mock", action="store_true",
                        help="geen taalmodel: vaste regels op de demo-offertes, zonder netwerk")
    parser.add_argument("--dry-run", action="store_true", help="niets in Odoo invullen, alleen tonen")
    parser.add_argument("--json", action="store_true", help="met --bestand: het resultaat als JSON")
    parser.add_argument("--bestand", type=Path, nargs="+", help="vergelijk alleen deze PDF's, zonder Odoo")
    args = parser.parse_args(argv)
    load_env(HERE / ".env")

    offline = args.offline
    if not offline and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Geen ANTHROPIC_API_KEY in ai/.env: offline vergelijking met vaste regels.")
        offline = True
    comparer = make_comparer(offline)
    if args.bestand:
        try:
            result, model = comparer.compare([(path.name, path.read_bytes()) for path in args.bestand])
        except ValueError as error:
            print(error)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False) if args.json
              else f"Gelezen door {model}:\n{format_comparison(result)}")
        return 0
    odoo = connect()
    if odoo is None:
        return 1
    run(odoo, comparer, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
