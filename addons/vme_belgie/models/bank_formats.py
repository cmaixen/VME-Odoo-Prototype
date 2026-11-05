"""Read Belgian CODA and ISO 20022 CAMT.053 bank statements, and Belgian structured communications.

Plain Python without Odoo, so the formats can be tested and reused on their own. Odoo Community has
no statement import (the CODA and CAMT importers are Enterprise modules), so this is our own code,
written from the public specifications: CODA 2.6 of Febelfin and camt.053.001.02 of ISO 20022.
Only what the VME prototype needs is read: account, balances, and per movement the date, amount,
communication and counterparty. CODA information records (3) and free messages (4) are skipped.
"""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

RECORD_LENGTH = 128


class BankFileError(ValueError):
    """The file is not a statement we can read; the message is shown to the user."""


@dataclass
class Transaction:
    date: date
    amount: Decimal  # positive = money in, negative = money out
    communication: str = ""
    structured: bool = False  # communication is a Belgian structured communication (12 digits)
    counterparty_name: str = ""
    counterparty_account: str = ""
    bank_reference: str = ""


@dataclass
class Statement:
    account_number: str  # IBAN without spaces
    currency: str
    number: str
    date: date
    balance_start: Decimal
    balance_end: Decimal
    transactions: list = field(default_factory=list)


# Structured communication (OGM/VCS): 10 digits followed by their remainder modulo 97 (97 for 0).
# Febelfin standard for the "gestructureerde mededeling" (not a law); banks reject invalid ones.

def structured_check(base10):
    return int(base10) % 97 or 97


def format_structured(digits):
    """'123456789002' -> '+++123/4567/89002+++'."""
    return f"+++{digits[:3]}/{digits[3:7]}/{digits[7:]}+++"


def make_structured(number):
    base = f"{int(number):010d}"
    if len(base) != 10:
        raise ValueError(number)
    return format_structured(f"{base}{structured_check(base):02d}")


def find_structured(text):
    """Return (12 digits, valid) for the first thing in text that looks like a structured communication.

    Accepts '+++123/4567/89002+++', '***...***' and twelve digits with or without separators.
    Returns (None, False) if there is none.
    """
    if not text:
        return None, False
    match = re.search(r"[+*]{3}\s*(\d{3})\s*/?\s*(\d{4})\s*/?\s*(\d{5})\s*[+*]{3}", text) \
        or re.search(r"(?<!\d)(\d{3})[/ .]?(\d{4})[/ .]?(\d{5})(?!\d)", text)
    if not match:
        return None, False
    digits = "".join(match.groups())
    return digits, structured_check(digits[:10]) == int(digits[10:])


def _amount(text):
    return Decimal(int(text)) / 1000


def _date(text):
    """CODA date DDMMYY."""
    if not text.strip("0 "):
        return None
    return date(2000 + int(text[4:6]), int(text[2:4]), int(text[0:2]))


def parse_coda(data):
    """Parse a CODA file (bytes or str) into a list of Statement objects."""
    text = data.decode("latin-1") if isinstance(data, bytes) else data
    records = [line.rstrip("\r\n") for line in text.splitlines() if line.strip()]
    if not records or not records[0].startswith("0"):
        raise BankFileError("Dit is geen CODA-bestand: de eerste regel moet een kopregel (0) zijn.")
    statements = []
    statement = None
    transaction = None
    for number, record in enumerate(records, start=1):
        record = record.ljust(RECORD_LENGTH)
        kind = record[0]
        if kind == "0":
            if record[127] != "2":
                raise BankFileError(f"Alleen CODA versie 2 wordt ondersteund (regel {number}).")
        elif kind == "1":
            structure = record[1]
            if structure in ("2", "3"):  # IBAN
                account = record[5:39].strip()
            else:
                account = record[5:17].strip()
            sign = -1 if record[42] == "1" else 1
            statement = Statement(
                account_number=account.replace(" ", ""),
                currency=record[39:42].strip() if structure in ("2", "3") else record[18:21].strip(),
                number=record[2:5],
                date=None,
                balance_start=sign * _amount(record[43:58]),
                balance_end=Decimal(0),
            )
            statements.append(statement)
        elif kind == "2":
            if statement is None:
                raise BankFileError(f"Beweging zonder rekening (regel {number}).")
            article = record[1]
            if article == "1":
                sign = -1 if record[31] == "1" else 1
                structured = record[61] == "1"
                communication = record[62:115]
                if structured:
                    # Type 101: Belgian structured communication, 12 digits.
                    communication = format_structured(record[65:77]) if record[62:65] == "101" else record[65:115]
                detail = record[6:10]
                globalisation = record[124]
                transaction = Transaction(
                    date=_date(record[115:121]) or _date(record[47:53]),
                    amount=sign * _amount(record[32:47]),
                    communication=communication.rstrip(),
                    structured=structured,
                    bank_reference=record[10:31].strip(),
                )
                # Detail lines of a globalised movement (several payments in one) repeat the
                # amount; only the movement itself becomes a statement line.
                if detail == "0000" or globalisation == "0":
                    statement.transactions.append(transaction)
            elif article == "2" and transaction:
                if not transaction.structured:
                    transaction.communication = (transaction.communication + record[10:63].rstrip()).strip()
            elif article == "3" and transaction:
                transaction.counterparty_account = record[10:44].strip().replace(" ", "")
                transaction.counterparty_name = record[47:82].strip()
                if not transaction.structured:
                    transaction.communication = (transaction.communication + record[82:125].rstrip()).strip()
        elif kind == "8":
            if statement is None:
                raise BankFileError(f"Nieuw saldo zonder rekening (regel {number}).")
            sign = -1 if record[41] == "1" else 1
            statement.balance_end = sign * _amount(record[42:57])
            statement.date = _date(record[57:63])
        elif kind in ("3", "4", "9"):
            continue
        else:
            raise BankFileError(f"Onbekend recordtype {kind!r} op regel {number}.")
    for statement in statements:
        statement.date = statement.date or max((t.date for t in statement.transactions), default=None)
        total = statement.balance_start + sum(t.amount for t in statement.transactions)
        if total != statement.balance_end:
            raise BankFileError(
                f"Rekening {statement.account_number}: beginsaldo plus bewegingen ({total}) "
                f"is niet gelijk aan het nieuwe saldo ({statement.balance_end})."
            )
    return statements


def _coda_date(value):
    return value.strftime("%d%m%y")


def _coda_amount(value):
    return f"{int(abs(Decimal(value)) * 1000):015d}"


def _fixed(record):
    if len(record) != RECORD_LENGTH:
        raise ValueError(f"CODA record of {len(record)} characters: {record!r}")
    return record


def write_coda(statements, creation_date, bank_name="BANK VOORBEELD", holder=""):
    """Write Statement objects as a CODA 2 file (str). Used for tests and the fictitious demo files."""
    lines = [_fixed(
        "0" + "0000" + _coda_date(creation_date) + "999" + "05" + " " + " " * 7 + "0".rjust(10)
        + holder[:26].ljust(26) + "BANKBEBBXXX" + "00000000000" + " " + "00000" + " " * 16 + " " * 16
        + " " * 7 + "2"
    )]
    count = 0
    debit = credit = Decimal(0)
    for statement in statements:
        account = statement.account_number.replace(" ", "")
        account_field = account.ljust(34) + statement.currency.ljust(3)
        lines.append(_fixed(
            "1" + "2" + statement.number[-3:].rjust(3, "0") + account_field
            + ("1" if statement.balance_start < 0 else "0") + _coda_amount(statement.balance_start)
            + _coda_date(statement.date) + holder[:26].ljust(26) + "Zichtrekening".ljust(35)
            + statement.number[-3:].rjust(3, "0")
        ))
        count += 1
        for sequence, transaction in enumerate(statement.transactions, start=1):
            if transaction.amount < 0:
                debit += -transaction.amount
            else:
                credit += transaction.amount
            if transaction.structured:
                digits, _valid = find_structured(transaction.communication)
                communication = ("101" + digits).ljust(53)
            else:
                communication = transaction.communication[:53].ljust(53)
            rest = "" if transaction.structured else transaction.communication[53:]
            lines.append(_fixed(
                "21" + f"{sequence:04d}" + "0000" + transaction.bank_reference[:21].ljust(21)
                + ("1" if transaction.amount < 0 else "0") + _coda_amount(transaction.amount)
                + _coda_date(transaction.date) + "00150000" + ("1" if transaction.structured else "0")
                + communication + _coda_date(transaction.date) + statement.number[-3:].rjust(3, "0")
                + "0" + "1" + " " + "0"
            ))
            lines.append(_fixed(
                "22" + f"{sequence:04d}" + "0000" + rest[:53].ljust(53) + " " * 35 + " " * 11 + "   "
                + " " + "    " + "    " + "    " + "1" + " " + "0"
            ))
            lines.append(_fixed(
                "23" + f"{sequence:04d}" + "0000" + transaction.counterparty_account[:34].ljust(34) + "EUR"
                + transaction.counterparty_name[:35].ljust(35) + rest[53:96].ljust(43) + "0" + " " + "0"
            ))
            count += 3
        lines.append(_fixed(
            "8" + statement.number[-3:].rjust(3, "0") + account_field
            + ("1" if statement.balance_end < 0 else "0") + _coda_amount(statement.balance_end)
            + _coda_date(statement.date) + " " * 64 + "0"
        ))
        count += 1
    lines.append(_fixed(
        "9" + " " * 15 + f"{count:06d}" + _coda_amount(debit) + _coda_amount(credit) + " " * 75 + "2"
    ))
    return "\n".join(lines) + "\n"


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _find(element, path):
    """Find by local names, whatever the camt namespace version."""
    current = [element]
    for name in path.split("/"):
        current = [child for node in current for child in node if _local(child.tag) == name]
        if not current:
            return None
    return current[0]


def _findall(element, name):
    return [child for child in element if _local(child.tag) == name]


def _text(element, path, default=""):
    found = _find(element, path)
    return (found.text or "").strip() if found is not None and found.text else default


def parse_camt053(data):
    """Parse an ISO 20022 camt.053 file (bytes or str) into a list of Statement objects."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise BankFileError(f"Dit is geen geldig XML-bestand: {error}") from error
    report = _find(root, "BkToCstmrStmt")
    if report is None:
        raise BankFileError("Dit XML-bestand is geen CAMT.053-rekeninguittreksel.")
    statements = []
    for stmt in _findall(report, "Stmt"):
        balances = {}
        for balance in _findall(stmt, "Bal"):
            code = _text(balance, "Tp/CdOrPrtry/Cd")
            amount = Decimal(_text(balance, "Amt", "0"))
            if _text(balance, "CdtDbtInd") == "DBIT":
                amount = -amount
            balances[code] = (amount, _text(balance, "Dt/Dt"))
        if "OPBD" not in balances or "CLBD" not in balances:
            raise BankFileError("Het rekeninguittreksel heeft geen begin- of eindsaldo (OPBD/CLBD).")
        statement = Statement(
            account_number=_text(stmt, "Acct/Id/IBAN").replace(" ", ""),
            currency=_find(stmt, "Bal/Amt").get("Ccy", "EUR"),
            number=_text(stmt, "ElctrncSeqNb") or _text(stmt, "Id"),
            date=date.fromisoformat(balances["CLBD"][1][:10]),
            balance_start=balances["OPBD"][0],
            balance_end=balances["CLBD"][0],
        )
        for entry in _findall(stmt, "Ntry"):
            amount = Decimal(_text(entry, "Amt", "0"))
            outgoing = _text(entry, "CdtDbtInd") == "DBIT"
            if outgoing:
                amount = -amount
            booking = _text(entry, "BookgDt/Dt") or _text(entry, "ValDt/Dt")
            details = _find(entry, "NtryDtls/TxDtls")
            communication, structured, name, account = "", False, "", ""
            if details is not None:
                structured_ref = _text(details, "RmtInf/Strd/CdtrRefInf/Ref")
                if structured_ref:
                    digits, _valid = find_structured(structured_ref)
                    communication = format_structured(digits) if digits else structured_ref
                    structured = bool(digits)
                else:
                    remittance = _find(details, "RmtInf")
                    communication = " ".join(
                        (node.text or "").strip() for node in _findall(remittance, "Ustrd")
                    ) if remittance is not None else ""
                party = "Dbtr" if not outgoing else "Cdtr"
                name = _text(details, f"RltdPties/{party}/Nm")
                account = _text(details, f"RltdPties/{party}Acct/Id/IBAN").replace(" ", "")
            statement.transactions.append(Transaction(
                date=date.fromisoformat(booking[:10]),
                amount=amount,
                communication=communication or _text(entry, "AddtlNtryInf"),
                structured=structured,
                counterparty_name=name,
                counterparty_account=account,
                bank_reference=_text(entry, "AcctSvcrRef"),
            ))
        total = statement.balance_start + sum(t.amount for t in statement.transactions)
        if total != statement.balance_end:
            raise BankFileError(
                f"Rekening {statement.account_number}: beginsaldo plus bewegingen ({total}) "
                f"is niet gelijk aan het eindsaldo ({statement.balance_end})."
            )
        statements.append(statement)
    return statements


def parse_statement_file(data):
    """Detect CODA or CAMT.053 and parse it. Returns (format name, statements)."""
    head = data.lstrip()[:5] if isinstance(data, bytes) else data.lstrip()[:5].encode()
    if head.startswith(b"<"):
        return "CAMT.053", parse_camt053(data)
    if head.startswith(b"0"):
        return "CODA", parse_coda(data)
    raise BankFileError("Onbekend bestandsformaat: gebruik een CODA-bestand of een CAMT.053-bestand (XML).")
