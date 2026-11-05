"""Deliver vendor bill mails to Odoo, the way an incoming mail server would.

Each .eml in ai/facturen_inbox/ is handed to Odoo's mail gateway (mail.thread.message_process),
exactly like Odoo's own odoo-mailgate.py does for a mail server. Odoo routes the mail on its
To: address: facturen-<vme>@<domain> is the alias of the purchase journal of that VME, so the
mail becomes a draft vendor bill in that VME, with its UBL attachment read in.

    python facturen_mailgate.py              # deliver all mails in ai/facturen_inbox/
    python facturen_mailgate.py --dry-run    # only show where each mail would go

Odoo ignores a mail whose Message-ID it already processed, so running twice is harmless.
"""
import argparse
import email
import email.policy
import os
import sys
from pathlib import Path

from assistant import load_env
from odoo_api import OdooClient, OdooError

HERE = Path(__file__).resolve().parent


def read_mails(folder):
    """(path, raw text) of every .eml in the folder, sorted by name."""
    return [(path, path.read_text(encoding="utf-8")) for path in sorted(Path(folder).glob("*.eml"))]


def describe(raw):
    message = email.message_from_string(raw, policy=email.policy.default)
    attachments = [part.get_filename() for part in message.iter_attachments()]
    return str(message["To"]), str(message["Subject"]), attachments


def deliver(odoo, raw):
    """Hand one raw mail to Odoo's gateway; returns the id of the new record, or None."""
    return odoo.execute("mail.thread", "message_process", False, raw) or None


def bill_summary(odoo, move_id, context):
    move = odoo.execute(
        "account.move", "read", [move_id],
        fields=["company_id", "partner_id", "ref", "amount_total", "state", "vme_period_start", "vme_period_end",
                "invoice_line_ids"],
        context=context,
    )[0]
    lines = odoo.execute("account.move.line", "read", move["invoice_line_ids"], fields=["vme_key_id"], context=context)
    keys = sorted({line["vme_key_id"][1] for line in lines if line["vme_key_id"]}) or ["geen sleutel"]
    return (
        f"{move['company_id'][1]}: conceptfactuur {move['ref'] or '(zonder referentie)'} van "
        f"{move['partner_id'][1] if move['partner_id'] else 'onbekende leverancier'}, "
        f"{move['amount_total']:.2f} EUR, periode {move['vme_period_start']} - {move['vme_period_end']}, "
        f"{len(lines)} lijn(en), sleutel: {', '.join(keys)}"
    )


def run(odoo, mails, dry_run=False, out=print):
    """Deliver the mails; returns {file name: record id or None}."""
    results = {}
    context = None
    if not dry_run:
        user = odoo.execute("res.users", "read", [odoo.uid], fields=["company_ids"])[0]
        context = {"allowed_company_ids": user["company_ids"]}
    for path, raw in mails:
        to, subject, attachments = describe(raw)
        out(f"- {path.name}: aan {to}, \"{subject}\", bijlagen: {', '.join(attachments) or 'geen'}")
        if dry_run:
            continue
        try:
            record_id = deliver(odoo, raw)
        except OdooError as error:
            # E.g. no alias matches the address: a real mail server would bounce the mail.
            out(f"  Niet verwerkt: {error}")
            results[path.name] = None
            continue
        results[path.name] = record_id
        if record_id:
            out(f"  {bill_summary(odoo, record_id, context)}")
        else:
            out("  Al eerder verwerkt of geen factuur aangemaakt (zie de Odoo-log).")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Lever factuurmails aan Odoo zoals een inkomende mailserver.")
    parser.add_argument("--inbox", type=Path, default=HERE / "facturen_inbox", help="map met .eml-bestanden")
    parser.add_argument("--dry-run", action="store_true", help="niets aanleveren, alleen tonen")
    args = parser.parse_args(argv)
    load_env(HERE / ".env")

    mails = read_mails(args.inbox)
    if not mails:
        print(f"Geen mails in {args.inbox}.")
        return 0
    if args.dry_run:
        run(None, mails, dry_run=True)
        return 0

    url = os.environ.get("ODOO_URL", "http://localhost:8069")
    try:
        odoo = OdooClient(
            url,
            os.environ.get("ODOO_DB", "vme_demo"),
            os.environ.get("ODOO_USER", "admin"),
            os.environ.get("ODOO_PASSWORD", "admin"),
        )
    except (OSError, OdooError) as error:
        print(f"Kan Odoo niet bereiken op {url}: {error}")
        return 1
    run(odoo, mails)
    return 0


if __name__ == "__main__":
    sys.exit(main())
