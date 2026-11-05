"""SEPA payment files: credit transfers (pain.001.001.09) and direct debits (pain.008.001.08).

Plain Python without Odoo, like bank_formats.py, so the files can be tested on their own. Odoo
Community has no SEPA export (account_sepa and account_sepa_direct_debit are Enterprise), so this is
our own code, written from the ISO 20022 message definitions and the EPC implementation guidelines.
Every file is validated against the official XSD in data/sepa/ before it is handed to the user.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from lxml import etree

XSD_DIR = Path(__file__).resolve().parent.parent / "data" / "sepa"
PAIN_001 = "pain.001.001.09"
PAIN_008 = "pain.008.001.08"
NOT_PROVIDED = "NOTPROVIDED"  # no BIC: allowed within SEPA since 2016 (IBAN only)


class SepaError(ValueError):
    """The data cannot become a valid SEPA file; the message is shown to the user."""


@dataclass
class Party:
    name: str
    iban: str
    bic: str = ""


@dataclass
class Payment:
    """One transfer (to a creditor) or one collection (from a debtor)."""
    end_to_end_id: str
    amount: Decimal
    party: Party  # creditor of a transfer, debtor of a collection
    communication: str = ""  # free text, or a Belgian structured communication (+++123/4567/89002+++)
    mandate_id: str = ""  # direct debit only
    mandate_date: date | None = None


@dataclass
class PaymentGroup:
    """One PmtInf block: one account of the VME, one date, (direct debit) one sequence type."""
    group_id: str
    account: Party  # the VME: debtor of transfers, creditor of collections
    execution_date: date
    payments: list = field(default_factory=list)
    sequence_type: str = "RCUR"  # direct debit: FRST, RCUR, OOFF or FNAL


# SEPA allows only a basic Latin character set (EPC guidelines, "SEPA character set").
_ALLOWED = re.compile(r"[^A-Za-z0-9/\-?:().,'+ ]")


def sepa_text(value, length):
    """Text limited to the SEPA character set: accents dropped, other characters replaced by a space."""
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", _ALLOWED.sub(" ", text)).strip()
    return text[:length].strip()


def sepa_id(value, length=35):
    """Identifier (MsgId, EndToEndId, mandate): no spaces, may not start or end with '/' nor contain '//'."""
    text = sepa_text(value, 200).replace(" ", "")
    text = re.sub(r"/{2,}", "/", text).strip("/")
    return text[:length].strip("/")


def iban_is_valid(iban):
    iban = re.sub(r"\s", "", iban or "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        return False
    digits = "".join(str(int(char, 36)) for char in iban[4:] + iban[:4])
    return int(digits) % 97 == 1


def creditor_identifier(country, national_id, business_code="ZZZ"):
    """SEPA creditor identifier: country, check digits, business code, national identifier.

    For a Belgian VME the national identifier is the KBO number: BE69ZZZ0123456749. The check digits
    are computed like an IBAN, on the national identifier and the country, without the business code.
    """
    national = re.sub(r"[^A-Za-z0-9]", "", national_id or "").upper()
    digits = "".join(str(int(char, 36)) for char in national + country.upper() + "00")
    return f"{country.upper()}{98 - int(digits) % 97:02d}{business_code}{national}"


def creditor_identifier_is_valid(identifier):
    identifier = re.sub(r"\s", "", identifier or "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{3}[A-Z0-9]{1,28}", identifier):
        return False
    return creditor_identifier(identifier[:2], identifier[7:], identifier[4:7]) == identifier


def _structured_digits(communication):
    digits = re.sub(r"\D", "", communication or "")
    if len(digits) == 12 and re.fullmatch(r"\s*[+*]{3}.*[+*]{3}\s*", communication or ""):
        return digits
    return None


class _Builder:
    def __init__(self, message):
        self.ns = f"urn:iso:std:iso:20022:tech:xsd:{message}"
        self.root = etree.Element(f"{{{self.ns}}}Document", nsmap={None: self.ns})

    def sub(self, parent, tag, text=None, **attrs):
        element = etree.SubElement(parent, f"{{{self.ns}}}{tag}", **attrs)
        if text is not None:
            element.text = str(text)
        return element

    def path(self, parent, tags, text=None):
        """Nested elements: path(x, "Id/IBAN", "BE..") -> <Id><IBAN>BE..</IBAN></Id>."""
        names = tags.split("/")
        for name in names[:-1]:
            parent = self.sub(parent, name)
        return self.sub(parent, names[-1], text)

    def agent(self, parent, tag, bic):
        institution = self.path(parent, f"{tag}/FinInstnId")
        if bic:
            self.sub(institution, "BICFI", bic)
        else:
            self.path(institution, "Othr/Id", NOT_PROVIDED)

    def remittance(self, parent, communication):
        digits = _structured_digits(communication)
        if not digits and not communication:
            return
        info = self.sub(parent, "RmtInf")
        if digits:
            # Belgian structured communication: SCOR with issuer BBA (Febelfin guidelines).
            ref_info = self.path(info, "Strd/CdtrRefInf")
            ref_type = self.sub(ref_info, "Tp")
            self.path(ref_type, "CdOrPrtry/Cd", "SCOR")
            self.sub(ref_type, "Issr", "BBA")
            self.sub(ref_info, "Ref", digits)
        else:
            self.sub(info, "Ustrd", sepa_text(communication, 140))

    def header(self, parent, message_id, initiator, groups, created):
        payments = [p for g in groups for p in g.payments]
        header = self.sub(parent, "GrpHdr")
        self.sub(header, "MsgId", sepa_id(message_id))
        self.sub(header, "CreDtTm", created.replace(microsecond=0).isoformat())
        self.sub(header, "NbOfTxs", len(payments))
        self.sub(header, "CtrlSum", _amount(sum(p.amount for p in payments)))
        self.path(header, "InitgPty/Nm", sepa_text(initiator, 70))

    def tostring(self):
        return etree.tostring(self.root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def _amount(value):
    return f"{Decimal(value):.2f}"


def _check(groups, kind):
    if not groups or not any(g.payments for g in groups):
        raise SepaError("Er zijn geen betalingen om in het bestand te zetten.")
    for group in groups:
        if not iban_is_valid(group.account.iban):
            raise SepaError(f"De rekening {group.account.iban} van de VME is geen geldig IBAN-nummer.")
        for payment in group.payments:
            if payment.amount <= 0:
                raise SepaError(f"{payment.party.name}: het bedrag moet groter zijn dan nul.")
            if not iban_is_valid(payment.party.iban):
                raise SepaError(f"{payment.party.name}: {payment.party.iban or 'geen rekeningnummer'} is geen geldig IBAN-nummer.")
            if kind == "debit" and not (payment.mandate_id and payment.mandate_date):
                raise SepaError(f"{payment.party.name}: geen mandaat voor de domiciliëring.")


def build_credit_transfer(message_id, initiator, groups, created=None):
    """pain.001.001.09: one PmtInf per account and execution date. Returns bytes."""
    _check(groups, "transfer")
    created = created or datetime.now()
    b = _Builder(PAIN_001)
    initiation = b.sub(b.root, "CstmrCdtTrfInitn")
    groups = [g for g in groups if g.payments]
    b.header(initiation, message_id, initiator, groups, created)
    for group in groups:
        info = b.sub(initiation, "PmtInf")
        b.sub(info, "PmtInfId", sepa_id(group.group_id))
        b.sub(info, "PmtMtd", "TRF")
        # One bank movement per payment, so the statement confirms each bill on its own.
        b.sub(info, "BtchBookg", "false")
        b.sub(info, "NbOfTxs", len(group.payments))
        b.sub(info, "CtrlSum", _amount(sum(p.amount for p in group.payments)))
        b.path(info, "PmtTpInf/SvcLvl/Cd", "SEPA")
        b.path(info, "ReqdExctnDt/Dt", group.execution_date.isoformat())
        b.path(info, "Dbtr/Nm", sepa_text(group.account.name, 70))
        b.path(info, "DbtrAcct/Id/IBAN", group.account.iban)
        b.agent(info, "DbtrAgt", group.account.bic)
        b.sub(info, "ChrgBr", "SLEV")
        for payment in group.payments:
            tx = b.sub(info, "CdtTrfTxInf")
            b.path(tx, "PmtId/EndToEndId", sepa_id(payment.end_to_end_id))
            b.sub(b.sub(tx, "Amt"), "InstdAmt", _amount(payment.amount), Ccy="EUR")
            if payment.party.bic:
                b.agent(tx, "CdtrAgt", payment.party.bic)
            b.path(tx, "Cdtr/Nm", sepa_text(payment.party.name, 70))
            b.path(tx, "CdtrAcct/Id/IBAN", payment.party.iban)
            b.remittance(tx, payment.communication)
    return b.tostring()


def build_direct_debit(message_id, initiator, creditor_id, groups, created=None):
    """pain.008.001.08 (SEPA Core): one PmtInf per account, date and sequence type. Returns bytes."""
    _check(groups, "debit")
    if not creditor_identifier_is_valid(creditor_id):
        raise SepaError(f"De schuldeiseridentificatie {creditor_id or '(leeg)'} is ongeldig.")
    created = created or datetime.now()
    b = _Builder(PAIN_008)
    initiation = b.sub(b.root, "CstmrDrctDbtInitn")
    groups = [g for g in groups if g.payments]
    b.header(initiation, message_id, initiator, groups, created)
    for group in groups:
        info = b.sub(initiation, "PmtInf")
        b.sub(info, "PmtInfId", sepa_id(group.group_id))
        b.sub(info, "PmtMtd", "DD")
        b.sub(info, "BtchBookg", "false")
        b.sub(info, "NbOfTxs", len(group.payments))
        b.sub(info, "CtrlSum", _amount(sum(p.amount for p in group.payments)))
        payment_type = b.sub(info, "PmtTpInf")
        b.path(payment_type, "SvcLvl/Cd", "SEPA")
        b.path(payment_type, "LclInstrm/Cd", "CORE")
        b.sub(payment_type, "SeqTp", group.sequence_type)
        b.sub(info, "ReqdColltnDt", group.execution_date.isoformat())
        b.path(info, "Cdtr/Nm", sepa_text(group.account.name, 70))
        b.path(info, "CdtrAcct/Id/IBAN", group.account.iban)
        b.agent(info, "CdtrAgt", group.account.bic)
        b.sub(info, "ChrgBr", "SLEV")
        scheme = b.path(info, "CdtrSchmeId/Id/PrvtId/Othr")
        b.sub(scheme, "Id", re.sub(r"\s", "", creditor_id).upper())
        b.path(scheme, "SchmeNm/Prtry", "SEPA")
        for payment in group.payments:
            tx = b.sub(info, "DrctDbtTxInf")
            b.path(tx, "PmtId/EndToEndId", sepa_id(payment.end_to_end_id))
            b.sub(tx, "InstdAmt", _amount(payment.amount), Ccy="EUR")
            mandate = b.path(tx, "DrctDbtTx/MndtRltdInf")
            b.sub(mandate, "MndtId", sepa_id(payment.mandate_id))
            b.sub(mandate, "DtOfSgntr", payment.mandate_date.isoformat())
            b.agent(tx, "DbtrAgt", payment.party.bic)
            b.path(tx, "Dbtr/Nm", sepa_text(payment.party.name, 70))
            b.path(tx, "DbtrAcct/Id/IBAN", payment.party.iban)
            b.remittance(tx, payment.communication)
    return b.tostring()


_SCHEMAS = {}


def validate(xml, message):
    """Validate a file against the official XSD of message (PAIN_001 or PAIN_008); raise SepaError."""
    if message not in _SCHEMAS:
        _SCHEMAS[message] = etree.XMLSchema(etree.parse(str(XSD_DIR / f"{message}.xsd")))
    schema = _SCHEMAS[message]
    document = etree.fromstring(xml)
    if not schema.validate(document):
        errors = "; ".join(f"regel {e.line}: {e.message}" for e in list(schema.error_log)[:5])
        raise SepaError(f"Het bestand voldoet niet aan het schema {message}: {errors}")
    return True
