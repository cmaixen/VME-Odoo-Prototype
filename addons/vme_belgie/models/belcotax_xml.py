"""Belcotax-on-web XML for the 281.50 forms (fees, commissions and similar payments), income years up to 2025.

Plain Python without Odoo, like sepa_xml.py, so the file can be tested on its own. Nothing is sent
anywhere: the staff member downloads the file and uploads it in Belcotax-on-web.

Written from the official XSD "Belcotax 2025" (version 2, 29.01.2026) in data/belcotax/ and the brochure
"Belcotax-on-web inkomsten 2025" (version 3, 14.01.2026) of the FOD Financiën. Every file is validated
against that XSD before it is handed to the user. From income year 2026 the new Belcotax-on-web no
longer accepts this XML: see belcotax_jsonl.py.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from lxml import etree

XSD_PATH = Path(__file__).resolve().parent.parent / "data" / "belcotax" / "Belcotax-2025.xsd"
FICHE_TYPE = "28150"
# LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, zones 2.030, 1.020 and 0.025 - 1 natural person,
# 2 legal person; language 1 Dutch; 0 original sending (1 grouped corrections).
KIND_PERSON = "1"
KIND_COMPANY = "2"
LANGUAGE_DUTCH = "1"
CATEGORIES = ("commission", "fees", "benefits", "expenses")
# Zones of the amounts per category on the 281.50, and the total 2.064.
AMOUNT_ZONES = {"commission": "f50_2060_commissies", "fees": "f50_2061_erelonenofvacatie",
                "benefits": "f50_2062_voordelenaardbedrag", "expenses": "f50_2063_kosten"}

# Country codes of the RSZ, which both Belcotax formats use (annex 1 of the brochure). Only the countries a
# VME is likely to pay; for another country the overview warns and the staff member completes the file.
# The XML writes 0 for Belgium and the five digits otherwise, the JSON of 2026 always the last three.
RSZ_COUNTRY_CODES = {
    "BE": "150", "NL": "129", "FR": "111", "DE": "103", "LU": "113", "ES": "109", "IT": "128",
    "PT": "123", "AT": "105", "CH": "127", "GB": "112",
}

# Maximum lengths of the zones in the brochure and the XSD (where they are commented out).
LENGTHS = {
    "v0014_naam": 41, "v0015_adres": 32, "v0017_gemeente": 27, "v0018_telefoonnummer": 12,
    "v0021_contactpersoon": 34, "v0023_emailadres": 44, "a1011_naamnl1": 28, "a1012_naamnl2": 31,
    "a1013_adresnl": 32, "a1015_gemeente": 27, "f2013_naam": 41, "f2015_adres": 150, "f2017_gemeente": 27,
    "f2112_buitenlandspostnummer": 12, "f2114_voornamen": 15, "f50_2107_uitgeoefendberoep": 32,
}


def digits(value):
    return re.sub(r"\D", "", value or "")


def kbo_is_valid(number):
    """Belgian company number: ten digits, the last two are 97 minus the first eight modulo 97."""
    number = digits(number)
    if len(number) == 9:
        number = "0" + number
    return len(number) == 10 and number[0] in "01" and 97 - int(number[:8]) % 97 == int(number[8:])


def kbo(number):
    """The company number as ten digits, or "" when it is not a valid Belgian one."""
    number = digits(number)
    if len(number) == 9:
        number = "0" + number
    return number if kbo_is_valid(number) else ""


def national_number_is_valid(number):
    """National register number: eleven digits, check on the first nine (born after 1999: prefixed with 2)."""
    number = digits(number)
    if len(number) != 11:
        return False
    check = int(number[9:])
    return check in (97 - int(number[:9]) % 97, 97 - int("2" + number[:9]) % 97)


def national_number(number):
    """The national number as eleven digits, or "" when the check digits are wrong."""
    return digits(number) if national_number_is_valid(number) else ""


def rsz_country(iso_code):
    """Three-digit RSZ code of a country (empty ISO code: Belgium), or "" when we do not know it."""
    return RSZ_COUNTRY_CODES.get(iso_code or "BE", "")


def cents(amount):
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class Debtor:
    """The VME that paid, or the sender of the file: name, address, company number and contact."""
    name: str
    street: str
    zip: str
    city: str
    kbo: str
    country: str = "BE"
    contact: str = ""
    email: str = ""
    phone: str = ""
    key: str = ""  # reference of the resource in the JSON of 2026


@dataclass
class Fiche:
    """One beneficiary with the amounts paid in the year, per category (in euro)."""
    sequence: int
    name: str
    street: str
    zip: str
    city: str
    is_company: bool
    national_number: str = ""
    kbo: str = ""
    vat: str = ""
    first_names: str = ""
    profession: str = ""
    country: str = "BE"  # ISO code
    amounts: dict = field(default_factory=dict)  # category -> amount
    key: str = ""  # unique key of the fiche in the JSON of 2026: a new upload with the same key replaces it
    beneficiary_key: str = ""

    def amount(self, category):
        return cents(self.amounts.get(category, 0.0))

    @property
    def total(self):
        return sum(self.amount(c) for c in CATEGORIES)

    @property
    def is_belgian(self):
        return (self.country or "BE") == "BE"


def _add(parent, tag, value, required=False):
    """Add a zone; an empty optional zone is left out. An amount of 0 stays "0" (and 0 == False in Python)."""
    if (value is None or value is False or value == "") and not required:
        return None
    element = etree.SubElement(parent, tag)
    text = "" if value is None or value is False else str(value)
    element.text = text[:LENGTHS[tag]] if tag in LENGTHS else text
    return element


def _xml_country(iso_code):
    # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, zones 1.016 and 2.018 - "nul indien België",
    # otherwise the RSZ country code of annex 1.
    code = rsz_country(iso_code)
    if code == "150":
        return "0"
    return code.zfill(5) if code else ""


def build_belcotax_xml(year, debtor, fiches, created=None, sender=None):
    """The file for one VME (the debtor) and one income year, with one Fiche28150 per beneficiary.

    The sender is who uploads the file, usually the office of the syndic; without one the VME sends itself.
    """
    # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, zone 0.024 - the company number of the sender
    # must be the one used to log in to Belcotax-on-web.
    sender = sender or debtor
    created = (created or date.today()).strftime("%d-%m-%Y")
    debtor_kbo = kbo(debtor.kbo)
    root = etree.Element("Verzendingen")
    sending = etree.SubElement(root, "Verzending")
    _add(sending, "v0002_inkomstenjaar", year, True)
    _add(sending, "v0010_bestandtype", "BELCOTAX", True)
    _add(sending, "v0011_aanmaakdatum", created, True)
    _add(sending, "v0014_naam", sender.name, True)
    _add(sending, "v0015_adres", sender.street, True)
    _add(sending, "v0016_postcode", sender.zip, True)
    _add(sending, "v0017_gemeente", sender.city, True)
    _add(sending, "v0018_telefoonnummer", sender.phone, True)
    _add(sending, "v0021_contactpersoon", sender.contact, True)
    _add(sending, "v0022_taalcode", LANGUAGE_DUTCH, True)
    _add(sending, "v0023_emailadres", sender.email, True)
    _add(sending, "v0024_nationaalnr", kbo(sender.kbo), True)
    _add(sending, "v0025_typeenvoi", "0", True)

    declarations = etree.SubElement(sending, "Aangiften")
    declaration = etree.SubElement(declarations, "Aangifte")
    _add(declaration, "a1002_inkomstenjaar", year, True)
    _add(declaration, "a1005_registratienummer", debtor_kbo, True)
    _add(declaration, "a1011_naamnl1", debtor.name[:LENGTHS["a1011_naamnl1"]], True)
    _add(declaration, "a1012_naamnl2", debtor.name[LENGTHS["a1011_naamnl1"]:])
    _add(declaration, "a1013_adresnl", debtor.street, True)
    _add(declaration, "a1014_postcodebelgisch", debtor.zip)
    _add(declaration, "a1015_gemeente", debtor.city, True)
    _add(declaration, "a1016_landwoonplaats", _xml_country(debtor.country))
    _add(declaration, "a1020_taalcode", LANGUAGE_DUTCH, True)

    statements = etree.SubElement(declaration, "Opgaven")
    statement = etree.SubElement(statements, "Opgave32550")
    control_total = 0
    for fiche in fiches:
        node = etree.SubElement(statement, "Fiche28150")
        _add(node, "f2002_inkomstenjaar", year, True)
        _add(node, "f2005_registratienummer", debtor_kbo, True)
        _add(node, "f2008_typefiche", FICHE_TYPE, True)
        _add(node, "f2009_volgnummer", fiche.sequence, True)
        # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, fiche 281.50 note (1) and (2) - a legal
        # person has its company number in 2.011 and 2.110 stays empty; a natural person has his national
        # number in 2.011 (optional) and, for a liberal profession, his company number in 2.110.
        if fiche.is_company:
            _add(node, "f2011_nationaalnr", kbo(fiche.kbo))
        else:
            _add(node, "f2011_nationaalnr", national_number(fiche.national_number))
        _add(node, "f2013_naam", fiche.name, True)
        _add(node, "f2015_adres", fiche.street, True)
        _add(node, "f2016_postcodebelgisch", fiche.zip if fiche.is_belgian else "", fiche.is_belgian)
        _add(node, "f2017_gemeente", fiche.city)
        _add(node, "f2018_landwoonplaats", _xml_country(fiche.country))
        _add(node, "f2028_typetraitement", "0", True)  # 0 = ordinary fiche
        _add(node, "f2029_enkelopgave325", "0", True)  # 0 = fiche 281
        _add(node, "f2112_buitenlandspostnummer", fiche.zip if not fiche.is_belgian else "")
        _add(node, "f2114_voornamen", fiche.first_names)
        _add(node, "f50_2030_aardpersoon", KIND_COMPANY if fiche.is_company else KIND_PERSON, True)
        # LEGAL-CHECK: brochure Belcotax-on-web inkomsten 2025, validation 281.50 - 2.031 (nihil) is 1 if and
        # only if 2.065 is 0; we only report payments, so nihil is 0 and 2.065 stays empty: 2.064 already
        # holds what was paid in the year.
        _add(node, "f50_2031_nihil", "0", True)
        amounts = {AMOUNT_ZONES[c]: fiche.amount(c) for c in CATEGORIES}
        amounts["f50_2064_totaal"] = fiche.total  # 2.060 + 2.061 + 2.062 + 2.063 = 2.064
        # Control total 2.059: the sum of the zones 2.060 up to 2.088 on the fiche, so the total counts too.
        _add(node, "f50_2059_totaalcontrole", sum(amounts.values()), True)
        for tag, amount in amounts.items():
            _add(node, tag, amount, True)
        _add(node, "f50_2107_uitgeoefendberoep", fiche.profession)
        _add(node, "f50_2110_kbonbr", kbo(fiche.kbo) if not fiche.is_company else "")
        control_total += sum(amounts.values())
    # The XSD wants the zones of a fiche in its own order, not in the order we fill them.
    for node in statement:
        _sort_zones(node)

    # Control records: counts and sums of the sequence numbers (2.009) and the control totals (2.059).
    sequences = sum(f.sequence for f in fiches)
    _add(declaration, "r8002_inkomstenjaar", year, True)
    _add(declaration, "r8005_registratienummer", debtor_kbo)
    _add(declaration, "r8010_aantalrecords", len(fiches) + 2, True)  # with the opening and closing record
    _add(declaration, "r8011_controletotaal", sequences, True)
    _add(declaration, "r8012_controletotaal", control_total, True)

    _add(sending, "r9002_inkomstenjaar", year, True)
    _add(sending, "r9010_aantallogbestanden", 3, True)  # opening record, one declaration, closing record
    _add(sending, "r9011_totaalaantalrecords", len(fiches) + 4, True)
    _add(sending, "r9012_controletotaal", sequences, True)
    _add(sending, "r9013_controletotaal", control_total, True)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _zone_number(element):
    match = re.match(r"f(?:50_)?(\d{4})_", element.tag)
    return (element.tag.startswith("f50_"), int(match.group(1)) if match else 0)


def _sort_zones(node):
    # The common zones f2xxx come first, then the f50_ zones; within each group by zone number, except
    # 2.105 and 2.112/2.114 that follow 2.029 in the XSD: their numbers are already higher, so this holds.
    node[:] = sorted(node, key=_zone_number)


_SCHEMA = []


def validate(xml):
    """Validate a file against the official XSD; return the errors (an empty list when valid)."""
    if not _SCHEMA:
        _SCHEMA.append(etree.XMLSchema(etree.parse(str(XSD_PATH))))
    schema = _SCHEMA[0]
    if schema.validate(etree.fromstring(xml)):
        return []
    return [f"regel {e.line}: {e.message}" for e in list(schema.error_log)[:5]]
