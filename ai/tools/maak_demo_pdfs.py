"""Make the fictitious PDF invoices, documents and mails for the demo of step 21.

    python tools/maak_demo_pdfs.py

Writes
- addons/vme_belgie/demo_data/facturen_pdf/*.pdf: three PDF invoices without UBL;
- ai/facturen_pdf_inbox/*.eml: the same invoices as mails to the bill address of each VME;
- ai/documenten_inbox/*.pdf: an inspection report, an insurance policy and a quote.

All names, numbers and IBANs are made up (VAT numbers 0000..., bank code 999). The three
invoices show the three cases of the IBAN check: a known supplier with its confirmed account,
a known supplier with a different IBAN ("new account number", a common fraud), and a new supplier.
"""
import sys
from email.message import EmailMessage
from email.utils import format_datetime
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pdf_text import write_pdf  # noqa: E402

PDF_DIR = HERE.parent / "addons" / "vme_belgie" / "demo_data" / "facturen_pdf"
MAIL_DIR = HERE / "facturen_pdf_inbox"
DOC_DIR = HERE / "documenten_inbox"

VMES = {
    "linde": ("VME Residentie Linde", "Lindedreef 12", "2000 Voorbeeldstad", "facturen-residentie-linde"),
    "beuken": ("VME Hof ter Beuken", "Beukenhof 3", "9000 Voorbeeldstad", "facturen-hof-ter-beuken"),
    "kaai": ("VME Kaaihuis", "Kaaistraat 7", "8000 Voorbeeldstad", "facturen-kaaihuis"),
}

# What the mock (and Claude) should read from each invoice; the tests compare with this.
INVOICES = [
    {
        "file": "lift_onderhoud_residentie_linde_2026-q4.pdf",
        "vme": "linde",
        "sender": "facturen@liftonderhoud.example.com",
        "supplier_name": "Liftonderhoud Voorbeeld BV",
        "supplier_address": ("Kabelweg 4", "2000 Voorbeeldstad"),
        "supplier_vat": "BE0000000493",
        "iban": "BE75999000900251",
        "invoice_number": "LO-2026-0412",
        "invoice_date": "2026-10-30",
        "due_date": "2026-11-29",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "description": "Onderhoudscontract lift blok A, vierde kwartaal 2026",
        "amount_untaxed": "480.00",
        "amount_tax": "100.80",
        "amount_total": "580.80",
        "rate": 21,
        "note": None,
    },
    {
        "file": "elektriciteit_hof_ter_beuken_2026-10.pdf",
        "vme": "beuken",
        "sender": "facturen@energieleverancier.example.com",
        "supplier_name": "Energieleverancier Voorbeeld NV",
        "supplier_address": ("Stroomlaan 1", "1000 Voorbeeldstad"),
        "supplier_vat": "BE0000000394",
        # Not the confirmed account BE86 9990 0090 0150: the AI reading must warn.
        "iban": "BE64999000900352",
        "invoice_number": "EV-2026-110412",
        "invoice_date": "2026-11-03",
        "due_date": "2026-12-03",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "description": "Elektriciteit gemene delen, oktober 2026",
        "amount_untaxed": "310.00",
        "amount_tax": "65.10",
        "amount_total": "375.10",
        "rate": 21,
        "note": "Let op: ons rekeningnummer is gewijzigd. Betaal voortaan op het nieuwe nummer hieronder.",
    },
    {
        "file": "dakgoot_kaaihuis_2026-10.pdf",
        "vme": "kaai",
        "sender": "info@dakwerken.example.com",
        "supplier_name": "Dakwerken Voorbeeld BV",
        "supplier_address": ("Pannenstraat 21", "8000 Voorbeeldstad"),
        "supplier_vat": "BE0000001186",  # not a supplier in Odoo yet
        "iban": "BE53999000900453",
        "invoice_number": "DW-26-077",
        "invoice_date": "2026-10-28",
        "due_date": "2026-11-27",
        "period_start": None,
        "period_end": None,
        "description": "Herstelling dakgoot achtergevel",
        "amount_untaxed": "850.00",
        "amount_tax": "51.00",
        "amount_total": "901.00",
        "rate": 6,
        "note": "Btw 6%: renovatie van een woning ouder dan tien jaar.",
    },
]

DOCUMENTS = [
    {
        "file": "keuringsverslag_lift_residentie_linde.pdf",
        "vme": "Residentie Linde",
        "document_type": "inspection_report",
        "lines": [
            (50, 790, 16, True, "Keuringsdienst Voorbeeld vzw"),
            (50, 772, 9, False, "Controleweg 9, 1000 Voorbeeldstad - BTW BE0000000889"),
            (50, 720, 18, True, "KEURINGSVERSLAG"),
            (50, 700, 11, False, "Periodieke keuring van een personenlift (KB 9 maart 2003)"),
            (50, 660, 10, False, "Gebouw: Residentie Linde, Lindedreef 12, 2000 Voorbeeldstad"),
            (50, 645, 10, False, "Installatie: Lift blok A - Trappenhal"),
            (50, 630, 10, False, "Datum keuring: 03/11/2026"),
            (50, 600, 11, True, "Besluit: conform, met een opmerking"),
            (50, 585, 10, False, "Opmerking: noodverlichting in de liftkooi hersteld en werkend bevonden."),
            (50, 555, 10, False, "Volgende periodieke keuring: binnen zes maanden."),
        ],
    },
    {
        "file": "polis_brandverzekering_hof_ter_beuken.pdf",
        "vme": "Hof ter Beuken",
        "document_type": "insurance_policy",
        "lines": [
            (50, 790, 16, True, "Verzekeringen Voorbeeld NV"),
            (50, 772, 9, False, "BTW BE0000000691"),
            (50, 720, 18, True, "VERZEKERINGSPOLIS BRAND - GEBOUW"),
            (50, 700, 11, False, "Polisnummer: BR-2026-55120"),
            (50, 660, 10, False, "Verzekeringnemer: VME Hof ter Beuken, Beukenhof 3, 9000 Voorbeeldstad"),
            (50, 645, 10, False, "Verzekerd: het gebouw met alle gemene en privatieve delen"),
            (50, 630, 10, False, "Looptijd: 01/01/2027 tot 31/12/2027, stilzwijgend verlengd"),
            (50, 615, 10, False, "Jaarpremie: 6.240,00 EUR"),
        ],
    },
    {
        "file": "offerte_gevelrenovatie_kaaihuis.pdf",
        "vme": "Kaaihuis",
        "document_type": "quote",
        "lines": [
            (50, 790, 16, True, "Gevelwerken Voorbeeld BV"),
            (50, 772, 9, False, "BTW BE0000001285"),
            (50, 720, 18, True, "OFFERTE"),
            (50, 700, 11, False, "Gevelrenovatie voorgevel - offerte OF-2026-031, geldig tot 31/01/2027"),
            (50, 660, 10, False, "Voor: VME Kaaihuis, Kaaistraat 7, 8000 Voorbeeldstad"),
            (50, 645, 10, False, "Reinigen, voegen herstellen en hydrofuge behandeling"),
            (50, 630, 10, False, "Totaal excl. btw: 18.400,00 EUR"),
        ],
    },
]


def belgian_date(iso):
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def belgian_amount(text):
    whole, cents = text.split(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    return ".".join([whole] + groups) + "," + cents


def invoice_items(inv):
    customer, street, city, _alias = VMES[inv["vme"]]
    iban = " ".join(inv["iban"][i:i + 4] for i in range(0, len(inv["iban"]), 4))
    items = [
        (50, 790, 16, True, inv["supplier_name"]),
        (50, 774, 9, False, f"{inv['supplier_address'][0]}, {inv['supplier_address'][1]}"),
        (50, 762, 9, False, f"BTW {inv['supplier_vat']}"),
        (380, 720, 10, True, "Klant"),
        (380, 706, 10, False, customer),
        (380, 693, 10, False, street),
        (380, 680, 10, False, city),
        (50, 720, 20, True, "FACTUUR"),
        (50, 690, 10, False, f"Factuurnummer: {inv['invoice_number']}"),
        (50, 676, 10, False, f"Factuurdatum: {belgian_date(inv['invoice_date'])}"),
        (50, 662, 10, False, f"Vervaldatum: {belgian_date(inv['due_date'])}"),
    ]
    if inv["period_start"]:
        items.append((50, 648, 10, False,
                      f"Periode: {belgian_date(inv['period_start'])} - {belgian_date(inv['period_end'])}"))
    items += [
        ("line", 50, 620, 545, 620),
        (50, 606, 10, True, "Omschrijving"),
        (460, 606, 10, True, "Bedrag"),
        ("line", 50, 598, 545, 598),
        (50, 582, 10, False, inv["description"]),
        (460, 582, 10, False, f"{belgian_amount(inv['amount_untaxed'])} EUR"),
        ("line", 50, 560, 545, 560),
        (300, 540, 10, False, f"Totaal excl. btw: {belgian_amount(inv['amount_untaxed'])} EUR"),
        (300, 526, 10, False, f"Btw {inv['rate']}%: {belgian_amount(inv['amount_tax'])} EUR"),
        (300, 508, 12, True, f"Te betalen: {belgian_amount(inv['amount_total'])} EUR"),
    ]
    y = 460
    if inv["note"]:
        items.append((50, y, 10, True, inv["note"]))
        y -= 20
    items += [
        (50, y, 10, False, f"Te betalen op rekening IBAN {iban} voor {belgian_date(inv['due_date'])}"),
        (50, y - 14, 10, False, f"met vermelding van factuurnummer {inv['invoice_number']}."),
        ("line", 50, 70, 545, 70),
        (50, 56, 8, False, f"{inv['supplier_name']} - {inv['supplier_address'][0]}, {inv['supplier_address'][1]}"
                           f" - BTW {inv['supplier_vat']} - IBAN {iban}"),
        (50, 44, 8, False, "Fictieve factuur voor de demo van het VME-prototype."),
    ]
    return items


def invoice_mail(inv, pdf, index):
    customer, _street, _city, alias = VMES[inv["vme"]]
    message = EmailMessage()
    message["From"] = f"{inv['supplier_name']} <{inv['sender']}>"
    message["To"] = f"{alias}@syndicus.example.com"
    message["Subject"] = f"Factuur {inv['invoice_number']} - {customer}"
    message["Date"] = format_datetime(datetime(2026, 11, 4, 9, index, tzinfo=timezone.utc))
    message["Message-ID"] = f"<{inv['invoice_number'].lower()}@{inv['sender'].split('@')[1]}>"
    message.set_content(f"Geachte klant,\n\nIn bijlage vindt u factuur {inv['invoice_number']} als PDF.\n\n"
                        f"Met vriendelijke groeten,\n{inv['supplier_name']}\n")
    message.add_attachment(pdf, maintype="application", subtype="pdf", filename=inv["file"])
    return message.as_string()


def main():
    for folder in (PDF_DIR, MAIL_DIR, DOC_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    for index, inv in enumerate(INVOICES, 1):
        pdf = write_pdf(invoice_items(inv))
        (PDF_DIR / inv["file"]).write_bytes(pdf)
        mail_name = f"{index:02d}_{inv['file'].removesuffix('.pdf')}.eml"
        (MAIL_DIR / mail_name).write_text(invoice_mail(inv, pdf, index), encoding="utf-8")
    for doc in DOCUMENTS:
        items = doc["lines"] + [(50, 44, 8, False, "Fictief document voor de demo van het VME-prototype.")]
        (DOC_DIR / doc["file"]).write_bytes(write_pdf(items))
    print(f"{len(INVOICES)} facturen, {len(INVOICES)} mails en {len(DOCUMENTS)} documenten geschreven.")


if __name__ == "__main__":
    main()
