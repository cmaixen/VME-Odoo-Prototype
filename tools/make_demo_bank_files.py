"""Write the fictitious bank statements of the demo (stap 12) to addons/vme_belgie/demo_data/bankafschriften/.

    python3 tools/make_demo_bank_files.py

The structured communications follow from the invoice numbers of the demo history
(F/2026/00075 -> +++120/2600/07589+++), the opening balances are the provisions received in
2026. Change this file and run it again if the demo history changes.
"""
import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
MODULE = ROOT / "addons" / "vme_belgie"
OUT = MODULE / "demo_data" / "bankafschriften"

spec = importlib.util.spec_from_file_location("bank_formats", MODULE / "models" / "bank_formats.py")
bank_formats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bank_formats)
Statement, Transaction, write_coda = bank_formats.Statement, bank_formats.Transaction, bank_formats.write_coda


def iban(number):
    """Valid Belgian IBAN on the unassigned bank code 999 (same as fake_iban in the demo data)."""
    first10 = f"999{number:07d}"
    bban = first10 + f"{int(first10) % 97 or 97:02d}"
    return f"BE{98 - int(bban + '111400') % 97:02d}{bban}"


def ref(invoice_number):
    """Structured communication of demo invoice F/2026/<invoice_number>."""
    return bank_formats.make_structured(f"12026{invoice_number:05d}")


def tx(day, amount, communication, name, account, bank_ref):
    return Transaction(date(2026, 11, day), Decimal(amount), communication, communication.startswith("+++"),
                       name, account, bank_ref)


STATEMENT_DATE = date(2026, 11, 5)
# Fictitious counterparty accounts of owners and suppliers (not in the demo data: Odoo learns them).
A3, B7, K2 = iban(1001), iban(1002), iban(1003)
FAMILY, UNKNOWN = iban(1004), iban(1005)
ELEVATOR, CLEANING, GAS = iban(2001), iban(2002), iban(2003)

# One file per VME, one statement per fund account: (account, number, opening balance, movements).
FILES = {
    "residentie_linde_2026-11-05.cod": ("VME RESIDENTIE LINDE", [
        ("BE49999000000171", "044", "23568.00", [
            tx(3, "-1815.00", "ELEVATOR-20260915", "Liftonderhoud Voorbeeld BV", ELEVATOR, "LIN-WK-0441"),
            tx(3, "-1815.00", "CLEANING-20260930", "Schoonmaak Voorbeeld BV", CLEANING, "LIN-WK-0442"),
            # Late: due 4 November.
            tx(5, "432.00", ref(75), "Eigenaar Linde A3", A3, "LIN-WK-0443"),
        ]),
        ("BE38999000000272", "044", "2356.80", [
            # No communication, paid by someone else: proposal on lot A3 in the text and the amount.
            tx(5, "43.20", "reservefonds A3 oproep 4", "Familie Voorbeeld", FAMILY, "LIN-RK-0441"),
        ]),
    ]),
    "hof_ter_beuken_2026-11-05.cod": ("VME HOF TER BEUKEN", [
        ("BE27999000000373", "044", "47160.00", [
            # Typo in the communication of call 3 (F/2026/00099, +++120/2600/09916+++).
            tx(2, "420.00", "+++120/2600/09917+++", "Eigenaar Beuken B7", B7, "BEU-WK-0441"),
            tx(3, "-14520.00", "GAS-20260930", "Gasleverancier Voorbeeld NV", GAS, "BEU-WK-0442"),
            # Too little for call 4 (420.00 due).
            tx(4, "200.00", ref(145), "Eigenaar Beuken B7", B7, "BEU-WK-0443"),
            # Reserve capital of call 3 paid on the working capital account.
            tx(4, "15.75", ref(122), "Eigenaar Beuken B7", B7, "BEU-WK-0444"),
        ]),
        ("BE16999000000474", "044", "1768.50", [
            # On time (due 4 November): matched without exception.
            tx(4, "15.75", ref(168), "Eigenaar Beuken B7", B7, "BEU-RK-0441"),
        ]),
    ]),
    "kaaihuis_2026-11-05.cod": ("VME KAAIHUIS", [
        ("BE05999000000575", "044", "9000.00", [
            tx(3, "-726.00", "CLEANING-20260930", "Schoonmaak Voorbeeld BV", CLEANING, "KAA-WK-0441"),
            # Call 4 of K2 was already paid on 25 October: double payment.
            tx(4, "423.00", ref(38), "Eigenaar Kaaihuis K2", K2, "KAA-WK-0442"),
        ]),
    ]),
}

# The reserve account of Kaaihuis as CAMT.053, the XML alternative to CODA.
CAMT_FILE = "kaaihuis_reservekapitaal_2026-11-05.xml"
CAMT = ("BE91999000000676", "044", "900.00", [
    tx(5, "250.00", "voorschot", "J. Voorbeeld", UNKNOWN, "KAA-RK-0441"),
])


def statement(account, number, opening, movements):
    start = Decimal(opening)
    return Statement(account, "EUR", number, STATEMENT_DATE, start, start + sum(t.amount for t in movements), movements)


def camt053(st):
    def amount(value):
        return f'<Amt Ccy="EUR">{abs(value):.2f}</Amt><CdtDbtInd>{"DBIT" if value < 0 else "CRDT"}</CdtDbtInd>'

    def balance(code, value):
        return (f"<Bal><Tp><CdOrPrtry><Cd>{code}</Cd></CdOrPrtry></Tp>{amount(value)}"
                f"<Dt><Dt>{st.date.isoformat()}</Dt></Dt></Bal>")

    entries = []
    for t in st.transactions:
        party, role = ("Cdtr", "Cdtr") if t.amount < 0 else ("Dbtr", "Dbtr")
        if t.structured:
            remittance = (f"<Strd><CdtrRefInf><Tp><CdOrPrtry><Cd>SCOR</Cd></CdOrPrtry><Issr>BBA</Issr></Tp>"
                          f"<Ref>{t.communication.strip('+').replace('/', '')}</Ref></CdtrRefInf></Strd>")
        else:
            remittance = f"<Ustrd>{escape(t.communication)}</Ustrd>"
        entries.append(
            f"<Ntry>{amount(t.amount)}<Sts>BOOK</Sts><BookgDt><Dt>{t.date.isoformat()}</Dt></BookgDt>"
            f"<ValDt><Dt>{t.date.isoformat()}</Dt></ValDt><AcctSvcrRef>{t.bank_reference}</AcctSvcrRef>"
            f"<NtryDtls><TxDtls><RltdPties><{party}><Nm>{escape(t.counterparty_name)}</Nm></{party}>"
            f"<{role}Acct><Id><IBAN>{t.counterparty_account}</IBAN></Id></{role}Acct></RltdPties>"
            f"<RmtInf>{remittance}</RmtInf></TxDtls></NtryDtls></Ntry>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">\n<BkToCstmrStmt>\n'
        f"<GrpHdr><MsgId>KAA-RK-{st.date:%Y%m%d}</MsgId><CreDtTm>{st.date.isoformat()}T18:00:00</CreDtTm></GrpHdr>\n"
        f"<Stmt><Id>KAA-RK-{st.number}</Id><ElctrncSeqNb>{st.number}</ElctrncSeqNb>"
        f"<CreDtTm>{st.date.isoformat()}T18:00:00</CreDtTm>"
        f"<Acct><Id><IBAN>{st.account_number}</IBAN></Id><Ccy>EUR</Ccy><Ownr><Nm>VME KAAIHUIS</Nm></Ownr></Acct>\n"
        f"{balance('OPBD', st.balance_start)}\n{balance('CLBD', st.balance_end)}\n"
        + "\n".join(entries) + "\n</Stmt>\n</BkToCstmrStmt>\n</Document>\n"
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, (holder, statements) in FILES.items():
        content = write_coda([statement(*s) for s in statements], STATEMENT_DATE, holder=holder)
        (OUT / filename).write_text(content, encoding="latin-1")
    (OUT / CAMT_FILE).write_text(camt053(statement(*CAMT)), encoding="utf-8")
    for path in sorted(OUT.iterdir()):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
