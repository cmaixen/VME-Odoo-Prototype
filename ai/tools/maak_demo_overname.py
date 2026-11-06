"""Make the fictitious documents for taking over Residentie Wilg from another syndic.

    python tools/maak_demo_overname.py

Writes in addons/vme_belgie/demo_data/migratie/residentie-wilg-documenten/
- basisakte.pdf: the deed (three pages) with the splitting, the shares in the common parts and
  the special keys for the lift and for each staircase;
- basisakte-scan.pdf: the same deed as a "scan": a noisy image per page with an OCR text layer
  underneath, in which the share of A2 is unreadable and the share of B3 reads "1O5";
- notulen-av-2025.pdf and notulen-av-2026.pdf: the minutes of the last two general assemblies
  of the previous syndic, with works still to do, a deviating key, mandates and procedures;
- voorstel-mock.json: what the offline reader (--mock) reads from each of them; the tests in
  ai/tests and in the Odoo module compare with this.

The scan needs Pillow (pip install pillow); the other files need nothing extra. All names,
addresses and numbers are made up.
"""
import io
import json
import random
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from pdf_text import write_pages  # noqa: E402

OUT = HERE.parent / "addons" / "vme_belgie" / "demo_data" / "migratie" / "residentie-wilg-documenten"

# Lot, type, floor, staircase, share in the common parts (/1000), share in the lift (/1000).
LOTS = [
    ("A1", "appartement", "gelijkvloers", "trap A", 95, 60),
    ("A2", "appartement", "eerste verdieping", "trap A", 110, 125),
    ("A3", "appartement", "tweede verdieping", "trap A", 110, 145),
    ("A4", "appartement", "derde verdieping", "trap A", 135, 170),
    ("B1", "appartement", "gelijkvloers", "trap B", 90, 60),
    ("B2", "appartement", "eerste verdieping", "trap B", 105, 125),
    ("B3", "appartement", "tweede verdieping", "trap B", 105, 145),
    ("B4", "appartement", "derde verdieping", "trap B", 130, 170),
    ("G1", "garage", "kelder", "-", 25, None),
    ("G2", "garage", "kelder", "-", 25, None),
    ("G3", "garage", "kelder", "-", 25, None),
    ("G4", "garage", "kelder", "-", 25, None),
    ("K1", "berging", "kelder", "-", 10, None),
    ("K2", "berging", "kelder", "-", 10, None),
]
# What the OCR layer of the scan makes of some shares in the common parts.
SCAN_NOISE = {"A2": "1?0", "B3": "1O5"}

TOP, LEFT, LINE = 790, 50, 14


def paragraph(text, y, size=10, width=100, bold=False):
    """Wrapped lines of text from height y down; returns (items, next y)."""
    items = []
    for line in textwrap.wrap(text, width):
        items.append((LEFT, y, size, bold, line))
        y -= LINE
    return items, y - 6


def header(lines, title):
    items = [(LEFT, TOP, 9, False, line) for line in lines[:1]]
    y = TOP - 12
    for line in lines[1:]:
        items.append((LEFT, y, 9, False, line))
        y -= 12
    y -= 24
    items.append((LEFT, y, 15, True, title))
    return items, y - 30


def share_rows(rows, y, columns, noise=None):
    """Table rows as one text object each, so a reader finds the cells of a row together."""
    items = []
    titles, *body = rows
    items.append(("row", y, 9, True, list(zip(columns, titles))))
    items.append(("line", LEFT, y - 4, 545, y - 4))
    y -= 18
    for row in body:
        cells = list(row)
        if noise and cells[0] in noise:
            cells[-1] = noise[cells[0]] + "/1000"
        items.append(("row", y, 10, False, list(zip(columns, cells))))
        y -= 15
    items.append(("line", LEFT, y + 8, 545, y + 8))
    return items, y - 14


NOTARY = ["Notariskantoor Voorbeeld - Notarisplein 1, 3000 Voorbeeldstad",
          "Repertorium 2009/0412 - verleden op 14 mei 2009"]


def deed_pages(noise=None):
    page1, y = header(NOTARY, "BASISAKTE EN REGLEMENT VAN MEDE-EIGENDOM")
    parts = [
        ("Hoofdstuk I - Beschrijving van het gebouw", True),
        ("Het gebouw draagt de naam Residentie Wilg. Het is gelegen aan de Wilgenlaan 21, 3000 Voorbeeldstad, "
         "en bestaat uit twee trappenhallen (trap A en trap B) met elk vier appartementen, en een kelder met "
         "vier garages en twee bergingen. Trap A en trap B hebben samen een lift.", False),
        ("De mede-eigenaars vormen samen de Vereniging van mede-eigenaars Residentie Wilg, met zetel in het "
         "gebouw. De vereniging wordt vertegenwoordigd door de syndicus.", False),
        ("Hoofdstuk II - Splitsing", True),
        ("Het gebouw wordt gesplitst in veertien privatieve kavels, zoals beschreven in de tabel op de volgende "
         "bladzijde. Elke kavel omvat een privatief deel en een aandeel in de gemene delen, uitgedrukt in "
         "duizendsten. De aandelen zijn bepaald volgens de netto-vloeroppervlakte, de bestemming en de ligging "
         "van elke kavel, zoals toegelicht in het verslag van de landmeter-expert dat aan deze akte gehecht is.",
         False),
        ("De lasten van de gemene delen worden gedragen in verhouding tot de aandelen in de algemene delen, "
         "behoudens de bijzondere lasten van hoofdstuk III.", False),
    ]
    for text, bold in parts:
        items, y = paragraph(text, y, size=11 if bold else 10, bold=bold)
        page1 += items

    page2, y = header(NOTARY, "Hoofdstuk II - Splitsing (vervolg)")
    page2.append((LEFT, y, 11, True, "Tabel 1 - Algemene delen - totaal 1000/1000"))
    y -= 22
    rows = [("Kavel", "Type", "Verdieping", "Trap", "Aandeel")] + [
        (lot, kind, floor, stair, f"{general}/1000") for lot, kind, floor, stair, general, _lift in LOTS]
    items, y = share_rows(rows, y, [LEFT, 110, 220, 350, 450], noise)
    page2 += items
    items, y = paragraph("Totaal van de aandelen in de algemene delen: duizend duizendsten (1000/1000).", y)
    page2 += items

    page3, y = header(NOTARY, "Hoofdstuk III - Bijzondere lasten")
    items, y = paragraph(
        "Artikel 12. De kosten van onderhoud, keuring, herstelling en verbruik van de lift worden alleen gedragen "
        "door de appartementen, volgens de verdeling in tabel 2. De garages en bergingen dragen niet bij in de "
        "kosten van de lift.", y)
    page3 += items
    page3.append((LEFT, y, 11, True, "Tabel 2 - Lift - totaal 1000/1000"))
    y -= 22
    rows = [("Kavel", "Aandeel")] + [(lot, f"{lift}/1000") for lot, *_rest, lift in LOTS if lift]
    items, y = share_rows(rows, y, [LEFT, 450])
    page3 += items
    items, y = paragraph(
        "Artikel 13. De kosten eigen aan één trappenhal (schoonmaak, verlichting, schilderwerk van de trap) worden "
        "alleen gedragen door de appartementen van die trap, in verhouding tot hun aandeel in de algemene delen.", y)
    page3 += items
    for stair, letter in (("Trap A", "A"), ("Trap B", "B")):
        shares = [(lot, general) for lot, _k, _f, s, general, _l in LOTS if s == f"trap {letter}"]
        total = sum(general for _lot, general in shares)
        page3.append((LEFT, y, 11, True, f"Tabel {3 if letter == 'A' else 4} - {stair} - totaal {total}/{total}"))
        y -= 22
        items, y = share_rows([("Kavel", "Aandeel")] + [(lot, f"{general}/{total}") for lot, general in shares],
                              y, [LEFT, 450])
        page3 += items
    items, y = paragraph("Aldus verleden te Voorbeeldstad, op datum als voormeld.", y)
    page3 += items
    return [page1, page2, page3]


MINUTES_HEADER = [
    "Vereniging van mede-eigenaars Residentie Wilg - Wilgenlaan 21, 3000 Voorbeeldstad - KBO 0000.001.483",
    "Syndicus: Beheerkantoor Vorige Syndicus BV, Oude Baan 8, 3000 Voorbeeldstad",
]

MINUTES = {
    "notulen-av-2025.pdf": ("NOTULEN VAN DE GEWONE ALGEMENE VERGADERING VAN 10 APRIL 2025", [
        [
            "Aanwezig of vertegenwoordigd: 11 van de 14 kavels, samen 905/1000. De vergadering kan geldig "
            "beslissen. Voorzitter van de vergadering: Eigenaar Wilg A3. Secretaris: de syndicus.",
            "Punt 1. Goedkeuring van de rekeningen 2024. De vergadering keurt de rekeningen en de balans van 2024 "
            "goed en geeft kwijting aan de syndicus en aan de raad van mede-eigendom. Aangenomen met 11 stemmen.",
            "Punt 2. Budget 2025. Het budget voor het werkkapitaal wordt vastgesteld op 18.400,00 EUR. De "
            "jaarlijkse inbreng in het reservekapitaal blijft 6.000,00 EUR. Aangenomen met 11 stemmen.",
            "Punt 3. Renovatie dak trap B. De vergadering beslist het dak van trap B te vernieuwen, omdat de "
            "dakbedekking aan het einde van haar levensduur is. De kostprijs wordt geraamd op 48.500,00 EUR "
            "excl. btw, te betalen uit het reservekapitaal en te verdelen volgens de algemene delen. De syndicus "
            "vraagt drie offertes op basis van een lastenboek van de architect. Aangenomen met 2/3 van de stemmen.",
        ],
        [
            "Punt 4. Waterinfiltratie in de kelder. De vergadering geeft de syndicus opdracht om een procedure in "
            "te leiden tegen de aannemer van de kelderwerken, omdat de herstelling van 2023 de infiltratie niet "
            "verholpen heeft. Aangenomen met 11 stemmen.",
            "Punt 5. Varia. Het fietsenrek bij de ingang wordt vervangen binnen het gewone budget.",
            "De vergadering wordt gesloten om 21.40 uur. Getekend door de voorzitter, de secretaris en de "
            "aanwezige mede-eigenaars.",
        ],
    ]),
    "notulen-av-2026.pdf": ("NOTULEN VAN DE GEWONE ALGEMENE VERGADERING VAN 16 APRIL 2026", [
        [
            "Aanwezig of vertegenwoordigd: 12 van de 14 kavels, samen 930/1000. De vergadering kan geldig "
            "beslissen. Voorzitter van de vergadering: Eigenaar Wilg A3. Secretaris: de syndicus.",
            "Punt 1. Goedkeuring van de rekeningen 2025. De vergadering keurt de rekeningen en de balans van 2025 "
            "goed en geeft kwijting aan de syndicus. Aangenomen met 12 stemmen.",
            "Punt 2. Stand van zaken dak trap B. Twee van de drie offertes zijn binnen. De werken zijn nog niet "
            "gegund; de syndicus legt de offertes voor aan de raad van mede-eigendom zodra de derde binnen is. "
            "Het budget van de vorige vergadering blijft behouden.",
            "Punt 3. Vervanging garagepoort. De vergadering beslist de garagepoort te vervangen. De kostprijs "
            "wordt geraamd op 6.200,00 EUR excl. btw, te betalen uit het werkkapitaal. In afwijking van de "
            "basisakte worden deze kosten verdeeld volgens een eigen sleutel 'Garagepoort': alleen de garages "
            "G1, G2, G3 en G4, elk voor een gelijk deel. Aangenomen met 4/5 van de stemmen.",
        ],
        [
            "Punt 4. Benoemingen. Eigenaar Wilg A3 wordt voorzitter van de raad van mede-eigendom. Eigenaar Wilg "
            "B2 wordt lid van de raad van mede-eigendom. Eigenaar Wilg B4 wordt commissaris van de rekeningen. "
            "De mandaten lopen tot de volgende gewone algemene vergadering.",
            "Punt 5. Lopende procedures. De procedure tegen Bouwbedrijf Voorbeeld NV wegens de waterinfiltratie "
            "in de kelder loopt bij de rechtbank van eerste aanleg Voorbeeldstad; de zaak is uitgesteld naar "
            "12 januari 2027. Tegen de eigenaar van kavel G3 loopt een procedure bij het vredegerecht voor "
            "achterstallige provisies van 1.240,00 EUR.",
            "Punt 6. Overdracht. De vergadering stelt vast dat de syndicus zijn mandaat neerlegt op 31 december "
            "2026 en vraagt hem het archief over te dragen aan de nieuwe syndicus.",
            "De vergadering wordt gesloten om 22.05 uur.",
        ],
    ]),
}


def minutes_pages(title, pages):
    result = []
    for number, paragraphs in enumerate(pages):
        items, y = header(MINUTES_HEADER, title if number == 0 else f"{title.capitalize()} (vervolg)")
        for text in paragraphs:
            lines, y = paragraph(text, y)
            items += lines
        result.append(items)
    return result


def scan_image(items, seed, blots=()):
    """A noisy grey image of a page, slightly askew, as a cheap office scanner makes it.

    blots: (x, y) in points where a smudge covers the text.
    """
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    scale = 1.6
    width, height = int(595 * scale), int(842 * scale)
    image = Image.new("L", (width, height), 236)
    draw = ImageDraw.Draw(image)
    fonts = {}

    def font(size, bold):
        if (size, bold) not in fonts:
            fonts[size, bold] = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(size * scale),
                                                   index=1 if bold else 0)
        return fonts[size, bold]

    def text(x, y, size, bold, value):
        draw.text((x * scale, (842 - y) * scale - size * scale), value, fill=40, font=font(size, bold))

    for item in items:
        if item[0] == "line":
            _kind, x1, y1, x2, y2 = item
            draw.line([(x1 * scale, (842 - y1) * scale), (x2 * scale, (842 - y2) * scale)], fill=60, width=1)
        elif item[0] == "row":
            _kind, y, size, bold, cells = item
            for x, value in cells:
                text(x, y, size, bold, value)
        else:
            text(*item)
    for x, y in blots:
        draw.ellipse([x * scale, (842 - y) * scale - 9 * scale, (x + 7) * scale, (842 - y) * scale + 2 * scale],
                     fill=120)
    rng = random.Random(seed)
    pixels = image.load()
    for _ in range(width * height // 60):
        x, y = rng.randrange(width), rng.randrange(height)
        pixels[x, y] = rng.choice((90, 140, 200))
    image = image.filter(ImageFilter.GaussianBlur(0.7)).rotate(0.5, fillcolor=236)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=45)
    return buffer.getvalue()


def write_all():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"basisakte.pdf": write_pages(deed_pages())}
    for name, (title, pages) in MINUTES.items():
        files[name] = write_pages(minutes_pages(title, pages))
    # The image shows the deed itself, with a smudge over the second digit of the share of A2;
    # the OCR layer under it has the reading errors of SCAN_NOISE.
    clean, scanned = deed_pages(), deed_pages(noise=SCAN_NOISE)
    blots = [[(455, item[1]) for item in page if item[0] == "row" and len(item[4]) == 5 and item[4][0][1] == "A2"]
             for page in clean]
    images = [scan_image(items, seed, blots[seed]) for seed, items in enumerate(clean)]
    files["basisakte-scan.pdf"] = write_pages(scanned, images=images)
    for name, data in files.items():
        (OUT / name).write_bytes(data)

    from overname_reader import MockTakeoverReader  # noqa: PLC0415

    reader = MockTakeoverReader()
    readings = {name: reader.read(data, name)[0] for name, data in sorted(files.items())}
    (OUT / "voorstel-mock.json").write_text(json.dumps(readings, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return files


if __name__ == "__main__":
    for written in write_all():
        print(OUT / written)
