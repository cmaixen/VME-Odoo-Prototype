"""Belcotax-on-web XML for the 281.50 forms (fees, commissions and similar payments).

Plain Python without Odoo, like sepa_xml.py, so the file can be tested on its own. Nothing is sent
anywhere: the staff member downloads the file and uploads it in Belcotax-on-web.

TO VALIDATE: the structure follows the public Belcotax-on-web XML brochure (tags Verzending > Aangifte >
Opgave32550 > Fiche28150, amounts in eurocent, dates as dd-mm-yyyy) as far as we could reconstruct it.
We have no XSD of the FOD Financiën in the repository: check the file against the brochure of the
income year, and with a test upload in Belcotax-on-web, before a VME uses it.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from lxml import etree

FICHE_TYPE = "28150"
# Codes in the brochure (to validate): 1 natural person, 2 legal person; language 1 Dutch.
KIND_PERSON = "1"
KIND_COMPANY = "2"
LANGUAGE_DUTCH = "1"
COUNTRY_BELGIUM = "00000"
CATEGORIES = ("commission", "fees", "benefits", "expenses")


def digits(value):
    return re.sub(r"\D", "", value or "")


def kbo_is_valid(number):
    """Belgian company number: ten digits, the last two are 97 minus the first eight modulo 97."""
    number = digits(number)
    if len(number) == 9:
        number = "0" + number
    return len(number) == 10 and number[0] in "01" and 97 - int(number[:8]) % 97 == int(number[8:])


def national_number_is_valid(number):
    """National register number: eleven digits, check on the first nine (born after 1999: prefixed with 2)."""
    number = digits(number)
    if len(number) != 11:
        return False
    check = int(number[9:])
    return check in (97 - int(number[:9]) % 97, 97 - int("2" + number[:9]) % 97)


def cents(amount):
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


@dataclass
class Debtor:
    """The VME that paid: name, address and company number."""
    name: str
    street: str
    zip: str
    city: str
    kbo: str
    contact: str = ""
    email: str = ""
    phone: str = ""


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
    first_names: str = ""
    profession: str = ""
    country_code: str = COUNTRY_BELGIUM
    amounts: dict = field(default_factory=dict)  # category -> amount

    def amount(self, category):
        return cents(self.amounts.get(category, 0.0))

    @property
    def total(self):
        return sum(self.amount(c) for c in CATEGORIES)


def _add(parent, tag, value):
    element = etree.SubElement(parent, tag)
    # Not "if value": an amount of 0 must stay "0" (and 0 == False in Python).
    element.text = "" if value is None or value is False else str(value)
    return element


def build_belcotax_xml(year, debtor, fiches, created=None):
    """The file for one VME and one income year, with one Fiche28150 per beneficiary."""
    created = (created or date.today()).strftime("%d-%m-%Y")
    kbo = digits(debtor.kbo)
    root = etree.Element("Verzendingen")
    sending = etree.SubElement(root, "Verzending")
    _add(sending, "v0002_inkomstenjaar", year)
    _add(sending, "v0010_bestandtype", "BELCOTAX")
    _add(sending, "v0011_aanmaakdatum", created)
    _add(sending, "v0014_naam", debtor.name)
    _add(sending, "v0015_adres", debtor.street)
    _add(sending, "v0016_postcode", debtor.zip)
    _add(sending, "v0017_gemeente", debtor.city)
    _add(sending, "v0018_telefoonnummer", debtor.phone)
    _add(sending, "v0021_contactpersoon", debtor.contact)
    _add(sending, "v0022_taalcode", LANGUAGE_DUTCH)
    _add(sending, "v0023_emailadres", debtor.email)
    _add(sending, "v0024_nationaalnr", kbo)
    _add(sending, "v0025_typeenvoi", "0")  # 0 = original sending

    declarations = etree.SubElement(sending, "Aangiften")
    declaration = etree.SubElement(declarations, "Aangifte")
    _add(declaration, "a1002_inkomstenjaar", year)
    _add(declaration, "a1005_registratienummer", kbo)
    _add(declaration, "a1011_naamnl1", debtor.name)
    _add(declaration, "a1013_adresnl", debtor.street)
    _add(declaration, "a1014_postcodebelgisch", debtor.zip)
    _add(declaration, "a1015_gemeente", debtor.city)
    _add(declaration, "a1016_landwoonplaats", COUNTRY_BELGIUM)
    _add(declaration, "a1020_taalcode", LANGUAGE_DUTCH)

    statements = etree.SubElement(declaration, "Opgaven")
    statement = etree.SubElement(statements, "Opgave32550")
    control_total = 0
    for fiche in fiches:
        node = etree.SubElement(statement, "Fiche28150")
        _add(node, "f2002_inkomstenjaar", year)
        _add(node, "f2005_registratienummer", kbo)
        _add(node, "f2008_typefiche", FICHE_TYPE)
        _add(node, "f2009_volgnummer", fiche.sequence)
        _add(node, "f2011_nationaalnr", digits(fiche.national_number) if not fiche.is_company else "")
        _add(node, "f2013_naam", fiche.name)
        _add(node, "f2015_adres", fiche.street)
        _add(node, "f2016_postcodebelgisch", fiche.zip if fiche.country_code == COUNTRY_BELGIUM else "")
        _add(node, "f2017_gemeente", fiche.city)
        _add(node, "f2018_landwoonplaats", fiche.country_code)
        _add(node, "f2028_typetraitement", "0")  # 0 = ordinary fiche
        _add(node, "f2029_enkelopgave325", "0")
        _add(node, "f2112_buitenlandspostnummer", fiche.zip if fiche.country_code != COUNTRY_BELGIUM else "")
        _add(node, "f2114_voornamen", fiche.first_names)
        _add(node, "f50_2030_aardpersoon", KIND_COMPANY if fiche.is_company else KIND_PERSON)
        _add(node, "f50_2031_nihil", "0")
        _add(node, "f50_2060_commissies", fiche.amount("commission"))
        _add(node, "f50_2061_erelonenofvacatie", fiche.amount("fees"))
        _add(node, "f50_2062_voordelenaardbedrag", fiche.amount("benefits"))
        _add(node, "f50_2063_kosten", fiche.amount("expenses"))
        _add(node, "f50_2064_totaal", fiche.total)
        _add(node, "f50_2065_werkelijkbetaaldb", fiche.total)
        _add(node, "f50_2107_uitgeoefendberoep", fiche.profession)
        _add(node, "f50_2110_kbonbr", digits(fiche.kbo) if fiche.is_company else "")
        control_total += fiche.total

    _add(declaration, "r8002_inkomstenjaar", year)
    _add(declaration, "r8005_registratienummer", kbo)
    _add(declaration, "r8010_aantalrecords", len(fiches) + 2)  # the fiches plus the opening and closing record
    _add(declaration, "r8011_controletotaal", sum(f.sequence for f in fiches))
    _add(declaration, "r8012_controletotaal", control_total)

    _add(sending, "r9002_inkomstenjaar", year)
    _add(sending, "r9010_aantallogbestanden", 3)
    _add(sending, "r9011_totaalaantalrecords", len(fiches) + 4)
    _add(sending, "r9012_controletotaal", sum(f.sequence for f in fiches))
    _add(sending, "r9013_controletotaal", control_total)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)
