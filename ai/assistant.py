"""AI assistant for owner mails.

Reads the mails in ai/inbox/, links each one to a VME and lot in Odoo, picks the topic,
drafts a reply in Dutch, and puts it as a to-do activity on the VME. Nothing is ever sent:
a staff member reviews the draft and sends it from Odoo or their mail program.

    python assistant.py              # Claude via the Anthropic API, writes to Odoo
    python assistant.py --mock       # rule-based stand-in, no API key needed
    python assistant.py --dry-run    # show the result, write nothing to Odoo
"""
import argparse
import html
import os
import sys
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from classifier import TOPICS, URGENCIES, ClaudeClassifier, MockClassifier, RefusalError
from mails import read_inbox
from odoo_api import OdooClient, OdooError, VmeDirectory

HERE = Path(__file__).resolve().parent

# Days until the deadline of the activity, per urgency.
DEADLINE_DAYS = {"high": 0, "normal": 2, "low": 5}
CONFIDENCE_LABELS = {"high": "hoog", "medium": "gemiddeld", "low": "laag (nakijken!)"}
# Topics that also get a draft damage claim in Odoo (step 14).
DAMAGE_TOPICS = {"leak"}


def load_env(path):
    """Read KEY=value lines into os.environ, without overwriting what is already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def lot_label(vmes, result):
    for vme in vmes:
        for lot in vme["lots"]:
            if lot["id"] == result.lot_id:
                return lot["name"]
    return "kavel onbekend"


def activity_summary(vmes, result):
    return f"AI-voorstel: {TOPICS[result.topic]} ({lot_label(vmes, result)})"


def mail_day(mail):
    """Date of the mail, or None when the Date header cannot be read."""
    try:
        return parsedate_to_datetime(mail.date).date()
    except (TypeError, ValueError):
        return None


def activity_note(mail, result, vmes, claim_id=None):
    """HTML note with everything the staff member needs to check and send the reply."""
    e = html.escape

    def paragraphs(text):
        return "".join(f"<p>{e(block).replace(chr(10), '<br/>')}</p>" for block in text.split("\n\n"))

    return (
        "<p><b>Voorgesteld antwoord, nog niet verstuurd.</b> Kijk het na, pas aan waar nodig en "
        "verstuur het zelf. Markeer de activiteit daarna als gedaan.</p>"
        "<ul>"
        f"<li><b>Van:</b> {e(mail.sender_name)} &lt;{e(mail.sender_email)}&gt;</li>"
        f"<li><b>Kavel:</b> {e(lot_label(vmes, result))}</li>"
        f"<li><b>Onderwerp:</b> {e(TOPICS[result.topic])}</li>"
        f"<li><b>Dringendheid:</b> {e(URGENCIES[result.urgency])}</li>"
        f"<li><b>Zekerheid koppeling:</b> {e(CONFIDENCE_LABELS[result.confidence])}"
        f" &#8212; {e(result.matching_reason)}</li>"
        f"<li><b>Samenvatting:</b> {e(result.summary)}</li>"
        "</ul>"
        + (f"<p>Schadedossier {claim_id} aangemaakt als melding: kijk het na in Werken en schade.</p>" if claim_id else "")
        + f"<h4>Conceptantwoord: {e(result.reply_subject)}</h4>"
        f"<blockquote>{paragraphs(result.reply_body)}</blockquote>"
        f"<h4>Oorspronkelijke mail: {e(mail.subject)}</h4>"
        f"<p class=\"text-muted\">{e(mail.date)} &#183; {e(mail.reference)}</p>"
        f"<blockquote>{paragraphs(mail.body)}</blockquote>"
        f"<p class=\"text-muted\">Voorgesteld door {e(result.model)}.</p>"
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Koppel mails van eigenaars aan een VME en stel een antwoord voor.")
    parser.add_argument("--inbox", type=Path, default=HERE / "inbox", help="map met .eml- en .txt-mails")
    parser.add_argument("--mock", action="store_true", help="geen taalmodel: regels in plaats van Claude")
    parser.add_argument("--dry-run", action="store_true", help="niets in Odoo schrijven, alleen tonen")
    parser.add_argument("--force", action="store_true", help="ook mails die al een activiteit hebben")
    return parser


def run(mails, directory, classifier, vmes, dry_run=False, force=False, user_id=None, today=None, out=print):
    """Process all mails; returns a list of (mail, result, activity id or None)."""
    today = today or date.today()
    processed = []
    for mail in mails:
        if not force and not dry_run and directory.find_activity(mail.reference):
            out(f"- {mail.path.name}: al verwerkt, overgeslagen")
            continue
        try:
            result = classifier.classify(mail)
        except RefusalError as error:
            out(f"- {mail.path.name}: {error} Behandel deze mail manueel.")
            continue
        vme_name = next((v["name"] for v in vmes if v["id"] == result.association_id), None)
        out(
            f"- {mail.path.name}: {vme_name or 'geen VME'} / {lot_label(vmes, result)} / "
            f"{TOPICS[result.topic]} / {URGENCIES[result.urgency]} / zekerheid {result.confidence}"
        )
        activity_id = None
        if result.association_id is None:
            # An activity needs a record; without a VME a person has to look at the mail.
            out("  Geen VME gevonden: niet in Odoo gezet, behandel deze mail manueel.")
        elif dry_run:
            out("  " + result.reply_body.replace("\n", "\n  "))
        else:
            claim_id = None
            if result.topic in DAMAGE_TOPICS:
                claim_id = directory.create_damage_claim(
                    result.association_id, mail.subject, mail.body, mail.reference,
                    lot_id=result.lot_id, owner_id=result.owner_id, mail_date=mail_day(mail),
                )
                out(f"  Schadedossier {claim_id} aangemaakt (melding, nog niet aangegeven).")
            activity_id = directory.create_activity(
                result.association_id,
                activity_summary(vmes, result),
                activity_note(mail, result, vmes, claim_id),
                today + timedelta(days=DEADLINE_DAYS[result.urgency]),
                user_id=user_id,
            )
            out(f"  Activiteit {activity_id} aangemaakt op {vme_name}.")
        processed.append((mail, result, activity_id))
    return processed


def main(argv=None):
    args = build_parser().parse_args(argv)
    load_env(HERE / ".env")

    mails = read_inbox(args.inbox)
    if not mails:
        print(f"Geen mails in {args.inbox}.")
        return 0

    if not args.mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ontbreekt in ai/.env. Gebruik --mock om zonder taalmodel te testen.")
        return 2

    url = os.environ.get("ODOO_URL", "http://localhost:8069")
    try:
        odoo = OdooClient(
            url,
            os.environ.get("ODOO_DB", "vme_demo"),
            os.environ.get("ODOO_USER", "admin"),
            os.environ.get("ODOO_PASSWORD", "admin"),
        )
    except (OSError, OdooError) as error:  # URLError is an OSError
        print(f"Kan Odoo niet bereiken op {url}: {error}")
        return 1
    directory = VmeDirectory(odoo)
    vmes = directory.load()
    classifier = MockClassifier(vmes) if args.mock else ClaudeClassifier(vmes)

    print(f"{len(mails)} mail(s), {len(vmes)} VME('s) in Odoo, model: {classifier.model}")
    user_id = int(os.environ["ODOO_ACTIVITY_USER_ID"]) if os.environ.get("ODOO_ACTIVITY_USER_ID") else None
    run(mails, directory, classifier, vmes, dry_run=args.dry_run, force=args.force, user_id=user_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
