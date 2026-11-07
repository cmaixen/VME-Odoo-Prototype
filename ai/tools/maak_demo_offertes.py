"""Make the three fictitious quotes for the facade renovation of Residentie Linde (quote comparison).

    python tools/maak_demo_offertes.py

Writes addons/vme_belgie/demo_data/offertes/*.pdf. The demo data attaches them to the quotes of
the works "Gevelrenovatie voor- en achtergevel"; ai/offertes.py compares them.

All companies, numbers and amounts are made up (VAT numbers 0000...). The differences are on
purpose, so the comparison has something to show:
- Gevelwerken Fictief: complete, 6% VAT, scaffolding included;
- Renovatiebedrijf Voorbeeld: cheapest, but without scaffolding ("niet inbegrepen") and without
  a construction all risks insurance; price revision after 31/12/2026;
- Bouwonderneming Denkbeeld: charges 21% VAT instead of 6%, and does not mention the water
  repellent treatment at all.
"""
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pdf_text import write_pdf_pages  # noqa: E402

PDF_DIR = HERE.parent / "addons" / "vme_belgie" / "demo_data" / "offertes"

CUSTOMER = ("VME Residentie Linde", "Lindedreef 12", "2000 Voorbeeldstad")
SUBJECT = "Gevelrenovatie voor- en achtergevel (bouwjaar 1978)"

# Every quote: posts as (label, amount or None for "not included"), the page on which each block
# starts, and the expected reading; the tests compare the mock and the Odoo demo with this.
QUOTES = [
    {
        "file": "offerte_gevelwerken_fictief_GF-2026-207.pdf",
        "contractor": "Gevelwerken Fictief BV",
        "address": ("Voegenstraat 5", "2000 Voorbeeldstad"),
        "vat": "BE0000001681",
        "email": "offertes@gevelwerken.example.com",
        "reference": "GF-2026-207",
        "date": "2026-09-22",
        "posts": [
            ("Werfinrichting en afsluiting", "1850.00"),
            ("Stelling voor- en achtergevel, plaatsen en afbreken", "9400.00"),
            ("Gevelreiniging met lage druk en stoom", "6300.00"),
            ("Herstel voegwerk (uitslijpen en opnieuw voegen)", "14200.00"),
            ("Betonherstel balkons en lateien", "8750.00"),
            ("Waterafstotende behandeling (hydrofuge)", "4100.00"),
            ("Afvoer afval en container", "1200.00"),
        ],
        "excluded": [],
        "posts_on_page_2": 5,
        "amount_untaxed": "45800.00",
        "vat_rate": 6,
        "amount_tax": "2748.00",
        "amount_total": "48548.00",
        "vat_note": "Btw 6%: renovatie van een woning ouder dan tien jaar.",
        "terms_page": 3,
        "execution_period": "9 werkweken, start in overleg",
        "validity": "60 dagen na de offertedatum (tot 21/11/2026)",
        "payment_terms": "30% bij bestelling, 60% volgens vorderingsstaten, 10% bij voorlopige oplevering; "
                         "betaling binnen 30 dagen",
        "warranty": "10 jaar op betonherstel, 5 jaar op de waterafstotende behandeling",
        "insurance": "Alle bouwplaatsrisico's (ABR) en BA uitbating; attest bij bestelling",
        "reservations": [
            "Verborgen betonschade die pas na het afkappen zichtbaar wordt, in regie aan 85,00 EUR per uur.",
        ],
    },
    {
        "file": "offerte_renovatiebedrijf_voorbeeld_RV-26-1189.pdf",
        "contractor": "Renovatiebedrijf Voorbeeld NV",
        "address": ("Herstellaan 18", "2000 Voorbeeldstad"),
        "vat": "BE0000001780",
        "email": "info@renovatiebedrijf.example.com",
        "reference": "RV/26/1189",
        "date": "2026-10-03",
        "posts": [
            ("Werfinrichting", "1400.00"),
            ("Reinigen van de gevels", "5900.00"),
            ("Voegwerk herstellen", "13600.00"),
            ("Betonherstel balkons", "9200.00"),
            ("Hydrofuge behandeling", "3800.00"),
            ("Afvoer puin", "950.00"),
        ],
        "excluded": ["Stelling: te plaatsen door een derde in opdracht van de VME"],
        "posts_on_page_2": 6,
        "amount_untaxed": "34850.00",
        "vat_rate": 6,
        "amount_tax": "2091.00",
        "amount_total": "36941.00",
        "vat_note": "Btw 6%: renovatie van een woning ouder dan tien jaar.",
        "terms_page": 2,
        "execution_period": "7 werkweken na het plaatsen van de stelling",
        "validity": "30 dagen",
        "payment_terms": "40% voorschot bij bestelling, saldo bij oplevering; betaling binnen 15 dagen",
        "warranty": "Wettelijke tienjarige aansprakelijkheid; 2 jaar op de hydrofuge behandeling",
        "insurance": "BA bedrijf",
        "reservations": [
            "Prijzen onder voorbehoud van herziening volgens de ABEX-index bij een start na 31/12/2026.",
            "Water en elektriciteit kosteloos ter beschikking door de opdrachtgever.",
        ],
    },
    {
        "file": "offerte_bouwonderneming_denkbeeld_BD-OF-2026-0611.pdf",
        "contractor": "Bouwonderneming Denkbeeld BV",
        "address": ("Metselaarsweg 2", "2000 Voorbeeldstad"),
        "vat": "BE0000001879",
        "email": "offerte@denkbeeld.example.com",
        "reference": "BD-OF-2026-0611",
        "date": "2026-10-10",
        "posts": [
            ("Werfinrichting, signalisatie en werfkeet", "2100.00"),
            ("Steigerwerken (huur 10 weken inbegrepen)", "10250.00"),
            ("Hogedrukreiniging gevels", "6800.00"),
            ("Voegen: uitkrabben en opnieuw voegen", "15100.00"),
            ("Herstel betonschade balkons", "8400.00"),
            ("Afvoer van afval", "1350.00"),
        ],
        "excluded": [],
        "posts_on_page_2": 4,
        "amount_untaxed": "44000.00",
        "vat_rate": 21,
        "amount_tax": "9240.00",
        "amount_total": "53240.00",
        "vat_note": None,
        "terms_page": 3,
        "execution_period": "10 werkweken",
        "validity": "90 dagen",
        "payment_terms": "Maandelijkse vorderingsstaten, betaling binnen 30 dagen",
        "warranty": "10 jaar op betonherstel en voegwerk",
        "insurance": "Alle bouwplaatsrisico's (ABR) en BA; polis op aanvraag",
        "reservations": [
            "Bij temperaturen onder 5 °C worden de voegwerken uitgesteld; de uitvoeringstermijn verlengt dan.",
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


def _letterhead(quote, page, pages):
    return [
        (50, 790, 16, True, quote["contractor"]),
        (50, 774, 9, False, f"{quote['address'][0]}, {quote['address'][1]} - {quote['email']}"),
        (50, 762, 9, False, f"BTW {quote['vat']}"),
        (470, 790, 9, False, f"Pagina {page}/{pages}"),
        ("line", 50, 752, 545, 752),
    ]


def _post_items(posts, start_number, y):
    items = [(50, y, 10, True, "Omschrijving"), (440, y, 10, True, "Bedrag excl. btw"), ("line", 50, y - 8, 545, y - 8)]
    y -= 26
    for number, (label, amount) in enumerate(posts, start_number):
        items.append((50, y, 10, False, f"{number}. {label}"))
        items.append((440, y, 10, False, f"{belgian_amount(amount)} EUR"))
        y -= 18
    return items, y


def quote_pages(quote):
    """The text of each page, as items for write_pdf_pages."""
    pages_count = quote["terms_page"]
    first, second = quote["posts"][:quote["posts_on_page_2"] - 1], quote["posts"][quote["posts_on_page_2"] - 1:]
    customer, street, city = CUSTOMER
    page1 = _letterhead(quote, 1, pages_count) + [
        (380, 720, 10, True, "Klant"),
        (380, 706, 10, False, customer),
        (380, 693, 10, False, street),
        (380, 680, 10, False, city),
        (50, 720, 20, True, "OFFERTE"),
        (50, 690, 10, False, f"Offertenummer: {quote['reference']}"),
        (50, 676, 10, False, f"Datum: {belgian_date(quote['date'])}"),
        (50, 650, 10, False, f"Betreft: {SUBJECT}"),
    ]
    items, y = _post_items(first, 1, 610)
    page1 += items
    page2 = _letterhead(quote, 2, pages_count)
    items, y = _post_items(second, len(first) + 1, 720)
    page2 += items
    y -= 10
    for text in quote["excluded"]:
        page2.append((50, y, 10, True, f"Niet inbegrepen: {text}"))
        y -= 18
    page2 += [
        ("line", 50, y, 545, y),
        (300, y - 20, 10, False, f"Totaal excl. btw: {belgian_amount(quote['amount_untaxed'])} EUR"),
        (300, y - 34, 10, False, f"Btw {quote['vat_rate']}%: {belgian_amount(quote['amount_tax'])} EUR"),
        (300, y - 52, 12, True, f"Totaal incl. btw: {belgian_amount(quote['amount_total'])} EUR"),
    ]
    y -= 80
    if quote["vat_note"]:
        page2.append((50, y, 9, False, quote["vat_note"]))
        y -= 30
    terms = [
        (50, 0, 12, True, "Voorwaarden"),
        (50, 0, 10, False, f"Uitvoeringstermijn: {quote['execution_period']}"),
        (50, 0, 10, False, f"Geldigheid: {quote['validity']}"),
        (50, 0, 10, False, f"Betalingsvoorwaarden: {quote['payment_terms']}"),
        (50, 0, 10, False, f"Waarborg: {quote['warranty']}"),
        (50, 0, 10, False, f"Verzekering: {quote['insurance']}"),
    ] + [(50, 0, 10, False, f"Voorbehoud: {text}") for text in quote["reservations"]] + [
        (50, 0, 10, False, "Voor akkoord, datum en handtekening van de opdrachtgever:"),
    ]
    if quote["terms_page"] == 2:
        target, y = page2, y
    else:
        target, y = _letterhead(quote, 3, pages_count), 720
    for x, _y, size, bold, text in terms:
        # Long conditions continue on indented lines (about 95 characters fit on a line).
        for index, part in enumerate(textwrap.wrap(text, 95)):
            target.append((x + (15 if index else 0), y, size, bold, part))
            y -= 14
        y -= 8 if bold else 4
    pages = [page1, page2]
    if quote["terms_page"] == 3:
        pages.append(target)
    return pages


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for quote in QUOTES:
        (PDF_DIR / quote["file"]).write_bytes(write_pdf_pages(quote_pages(quote)))
        print(f"{PDF_DIR / quote['file']}")


if __name__ == "__main__":
    main()
