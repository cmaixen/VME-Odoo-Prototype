from datetime import date
from decimal import Decimal

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

from ..models.bank_formats import (
    BankFileError, Statement, Transaction, find_structured, make_structured, parse_camt053, parse_coda,
    parse_statement_file, write_coda,
)

OWNER_IBAN = "BE40999000100963"  # fictitious, bank code 999


class TestBankFormats(TransactionCase):
    """The file formats on their own, without matching."""

    def test_structured_communication(self):
        self.assertEqual(make_structured(1202600075), "+++120/2600/07589+++")
        self.assertEqual(find_structured("Provisie +++120/2600/07589+++ dank"), ("120260007589", True))
        self.assertEqual(find_structured("***120/2600/07589***"), ("120260007589", True))
        self.assertEqual(find_structured("120260007589"), ("120260007589", True))
        self.assertEqual(find_structured("+++120/2600/07569+++"), ("120260007569", False))
        self.assertEqual(find_structured("provisie A3 oktober"), (None, False))
        # The remainder 0 is written as 97.
        self.assertEqual(make_structured(97), "+++000/0000/09797+++")

    def test_coda_round_trip(self):
        statement = Statement(
            account_number="BE68539007547034", currency="EUR", number="012", date=date(2026, 11, 5),
            balance_start=Decimal("1000.00"), balance_end=Decimal("1310.50"),
            transactions=[
                Transaction(date(2026, 11, 3), Decimal("432.00"), "+++120/2600/07589+++", True,
                            "Eigenaar Test", OWNER_IBAN, "REF1"),
                Transaction(date(2026, 11, 4), Decimal("-121.50"), "Factuur LIFT-2026-09 onderhoud", False,
                            "Liftonderhoud Voorbeeld BV", "BE29999000200852", "REF2"),
            ],
        )
        text = write_coda([statement], date(2026, 11, 5))
        self.assertTrue(all(len(line) == 128 for line in text.splitlines()))
        [parsed] = parse_coda(text.encode("latin-1"))
        self.assertEqual(parsed.account_number, "BE68539007547034")
        self.assertEqual((parsed.balance_start, parsed.balance_end), (Decimal("1000"), Decimal("1310.5")))
        self.assertEqual(parsed.date, date(2026, 11, 5))
        incoming, outgoing = parsed.transactions
        self.assertEqual((incoming.amount, incoming.communication, incoming.structured), (Decimal("432"), "+++120/2600/07589+++", True))
        self.assertEqual((incoming.counterparty_name, incoming.counterparty_account), ("Eigenaar Test", OWNER_IBAN))
        self.assertEqual((outgoing.amount, outgoing.communication), (Decimal("-121.5"), "Factuur LIFT-2026-09 onderhoud"))

    def test_coda_balance_must_add_up(self):
        statement = Statement("BE68539007547034", "EUR", "001", date(2026, 11, 5), Decimal(0), Decimal(10),
                              [Transaction(date(2026, 11, 5), Decimal(5), "x")])
        with self.assertRaises(BankFileError):
            parse_coda(write_coda([statement], date(2026, 11, 5)))

    def test_camt053(self):
        with file_open("vme_belgie/demo_data/bankafschriften/kaaihuis_reservekapitaal_2026-11-05.xml", "rb") as f:
            file_format, [statement] = parse_statement_file(f.read())
        self.assertEqual(file_format, "CAMT.053")
        self.assertEqual(statement.account_number, "BE91999000000676")
        self.assertEqual(statement.balance_end - statement.balance_start, sum(t.amount for t in statement.transactions))
        self.assertTrue(statement.transactions)

    def test_unknown_format(self):
        with self.assertRaises(BankFileError):
            parse_statement_file(b"Datum;Bedrag\n")
        with self.assertRaises(BankFileError):
            parse_camt053(b"<Document><Other/></Document>")


@tagged("post_install", "-at_install")
class TestBankMatching(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Bank"})
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        Bank = cls.env["res.partner.bank"]
        cls.working_bank = Bank.create({"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id})
        cls.reserve_bank = Bank.create({"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id})
        cls.vme.write({"working_capital_bank_id": cls.working_bank.id, "reserve_capital_bank_id": cls.reserve_bank.id})
        (cls.working_bank | cls.reserve_bank).with_user(cls.env.ref("base.user_admin")).allow_out_payment = True
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name, "lot_type": "apartment"} for name in ("A1", "A2")
        ])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in cls.lots],
        })
        cls.owner_a1, cls.owner_a2 = cls.env["res.partner"].create([{"name": "Eigenaar Bank A1"}, {"name": "Eigenaar Bank A2"}])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.lots[0].id, "partner_id": cls.owner_a1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.owner_a2.id, "date_start": date(2015, 1, 1)},
        ])
        cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": 2026,
            "working_capital_budget": 4000, "reserve_capital_contribution": 400, "calls_per_year": "4",
        })
        cls.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(cls.vme.ids)], "year": 2026, "number": 1,
            "invoice_date": date(2026, 1, 5), "date_due": date(2026, 2, 4), "post_invoices": True,
        }).action_create_calls()
        invoices = cls.env["account.move"].search([("vme_provision_call_id.association_id", "=", cls.vme.id)])
        cls.inv = {
            (move.partner_id, move.vme_fund): move for move in invoices
        }  # each 500 working or 50 reserve
        cls.journals = cls.vme._ensure_fund_bank_journals()[cls.vme]

        company = cls.vme.company_id
        cls.supplier = cls.env["res.partner"].create({"name": "Liftonderhoud Bank BV", "is_company": True})
        cls.bill = cls.env["account.move"].with_company(company).create({
            "move_type": "in_invoice", "partner_id": cls.supplier.id, "invoice_date": date(2026, 1, 10),
            "ref": "LIFT-2026-01",
            "invoice_line_ids": [Command.create({"name": "Onderhoud lift", "quantity": 1, "price_unit": 300, "tax_ids": [Command.clear()]})],
        })
        cls.bill.with_company(company).action_post()

    def _import(self, transactions, fund="working", number="001"):
        bank = self.working_bank if fund == "working" else self.reserve_bank
        total = sum(Decimal(str(t.amount)) for t in transactions)
        statement = Statement(bank.sanitized_acc_number, "EUR", number, max(t.date for t in transactions),
                              Decimal(0), total, transactions)
        data = write_coda([statement], statement.date).encode("latin-1")
        return self.env["vme.bank.import.wizard"]._import_file(data, "test.cod")

    def _pay(self, move, amount=None, day=date(2026, 2, 1), communication=None, name="", account="", fund=None):
        amount = move.amount_total if amount is None else amount
        communication = move.payment_reference if communication is None else communication
        return self._import([Transaction(day, Decimal(str(amount)), communication, communication.startswith("+++"),
                                         name, account)], fund=fund or move.vme_fund)

    def test_reference_from_invoice_number(self):
        move = self.inv[self.owner_a1, "working"]
        year, number = move.name.split("/")[-2:]
        self.assertEqual(move.payment_reference, make_structured(f"1{year}{int(number):05d}"))

    def test_import_routes_each_account_to_its_fund_journal(self):
        working = Transaction(date(2026, 2, 1), Decimal(500), self.inv[self.owner_a1, "working"].payment_reference, True)
        reserve = Transaction(date(2026, 2, 1), Decimal(50), self.inv[self.owner_a1, "reserve"].payment_reference, True)
        statements = [
            Statement(self.working_bank.sanitized_acc_number, "EUR", "007", date(2026, 2, 1), Decimal(0), Decimal(500), [working]),
            Statement(self.reserve_bank.sanitized_acc_number, "EUR", "007", date(2026, 2, 1), Decimal(0), Decimal(50), [reserve]),
        ]
        data = write_coda(statements, date(2026, 2, 1)).encode("latin-1")
        lines = self.env["vme.bank.import.wizard"]._import_file(data, "twee.cod")
        self.assertEqual(lines.mapped("journal_id"), self.journals["working"] | self.journals["reserve"])
        self.assertEqual(sorted(lines.mapped("vme_bank_fund")), ["reserve", "working"])
        self.assertEqual(set(lines.mapped("vme_match_state")), {"auto"})
        # The same file again creates nothing.
        self.assertFalse(self.env["vme.bank.import.wizard"]._import_file(data, "twee.cod"))
        # Also when the statement got another name, as in the language of a French-speaking colleague.
        lines.statement_id.name = "CODA 007 du 01/02/2026"
        self.assertFalse(self.env["vme.bank.import.wizard"]._import_file(data, "twee.cod"))

    def test_unknown_account_is_refused(self):
        statement = Statement("BE40999000100963", "EUR", "001", date(2026, 2, 1), Decimal(0), Decimal(1),
                              [Transaction(date(2026, 2, 1), Decimal(1), "x")])
        with self.assertRaises(UserError):
            self.env["vme.bank.import.wizard"]._import_file(write_coda([statement], date(2026, 2, 1)), "vreemd.cod")

    def test_auto_match_on_structured_communication(self):
        move = self.inv[self.owner_a1, "working"]
        line = self._pay(move)
        self.assertEqual(line.vme_match_state, "auto")
        self.assertFalse(line.vme_exception)
        self.assertFalse(line.vme_follow_up)
        self.assertTrue(line.is_reconciled)
        self.assertEqual(move.payment_state, "paid")
        self.assertEqual(line.partner_id, self.owner_a1)
        self.assertEqual(line.vme_matched_move_ids, move)

    def test_late_payment_is_matched_and_followed_up(self):
        move = self.inv[self.owner_a1, "working"]
        line = self._pay(move, day=date(2026, 2, 14))  # due 4 February
        self.assertEqual(line.vme_match_state, "auto")
        self.assertEqual(line.vme_days_late, 10)
        self.assertTrue(line.vme_follow_up)
        self.assertEqual(move.payment_state, "paid")

    def test_underpayment_is_matched_partially(self):
        move = self.inv[self.owner_a2, "working"]
        line = self._pay(move, amount=300)
        self.assertEqual((line.vme_match_state, line.vme_exception), ("auto", "underpaid"))
        self.assertEqual(move.payment_state, "partial")
        self.assertAlmostEqual(move.amount_residual, 200)
        self.assertTrue(line.vme_follow_up)

    def test_overpayment_leaves_a_credit_for_the_owner(self):
        move = self.inv[self.owner_a2, "working"]
        line = self._pay(move, amount=520)
        self.assertEqual((line.vme_match_state, line.vme_exception), ("auto", "overpaid"))
        self.assertEqual(move.payment_state, "paid")
        credit = line.move_id.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable" and not l.reconciled)
        self.assertEqual((credit.partner_id, credit.balance), (self.owner_a2, -20))

    def test_wrong_communication_gives_a_proposal_on_name_and_amount(self):
        move = self.inv[self.owner_a2, "working"]
        digits = move.payment_reference.replace("+", "").replace("/", "")
        typo = f"+++{digits[:3]}/{digits[3:7]}/{digits[7:9]}{(int(digits[9]) + 1) % 10}{digits[10:]}+++"
        line = self._pay(move, communication=typo, name="Eigenaar Bank A2", account=OWNER_IBAN)
        self.assertEqual((line.vme_match_state, line.vme_exception), ("suggested", "wrong_reference"))
        self.assertEqual(line.vme_candidate_move_ids, move)
        self.assertEqual(line.partner_id, self.owner_a2)
        self.assertFalse(line.is_reconciled)
        self.assertEqual(move.payment_state, "not_paid")

        line.action_vme_reconcile()
        self.assertEqual(line.vme_match_state, "manual")
        self.assertEqual(move.payment_state, "paid")
        # The bank account of the owner is remembered, so the next payment is recognised by it.
        self.assertIn(OWNER_IBAN, self.owner_a2.bank_ids.mapped("sanitized_acc_number"))

    def test_proposal_from_a_lot_in_the_communication(self):
        move = self.inv[self.owner_a1, "reserve"]
        line = self._pay(move, communication="reservefonds A1 eerste oproep", name="Familie Voorbeeld")
        self.assertEqual((line.vme_match_state, line.vme_exception), ("suggested", "no_reference"))
        self.assertEqual(line.vme_candidate_move_ids, move)
        self.assertIn("A1", line.vme_match_note)

    def test_proposal_on_amount_alone_needs_a_unique_amount(self):
        # Both owners owe 500 on the working capital: an unknown payer of 500 gets no proposal.
        line = self._import([Transaction(date(2026, 2, 1), Decimal(500), "provisie", False, "Onbekende Betaler")])
        self.assertEqual((line.vme_match_state, line.vme_exception), ("todo", "no_reference"))
        self.assertFalse(line.vme_candidate_move_ids)
        self.assertIn("2 openstaande provisies", line.vme_match_note)

    def test_payment_on_the_account_of_the_other_fund(self):
        move = self.inv[self.owner_a1, "reserve"]
        line = self._pay(move, fund="working")
        self.assertEqual((line.vme_match_state, line.vme_exception), ("suggested", "wrong_fund"))
        self.assertEqual(line.vme_candidate_move_ids, move)
        self.assertFalse(line.is_reconciled)
        line.action_vme_reconcile()
        self.assertEqual(move.payment_state, "paid")
        self.assertEqual(line.vme_exception, "wrong_fund")  # still to transfer to the reserve account
        self.assertTrue(line.vme_follow_up)

    def test_double_payment_and_booking_on_the_owner(self):
        move = self.inv[self.owner_a1, "working"]
        self._pay(move)
        line = self._pay(move, day=date(2026, 2, 3))
        self.assertEqual((line.vme_match_state, line.vme_exception), ("todo", "already_paid"))
        self.assertEqual(line.partner_id, self.owner_a1)
        line.action_vme_book_on_partner()
        self.assertTrue(line.is_reconciled)
        credit = line.move_id.line_ids.filtered(lambda l: l.account_id.account_type == "asset_receivable")
        self.assertEqual((credit.partner_id, credit.balance), (self.owner_a1, -500))

    def test_supplier_payment_on_bill_reference(self):
        line = self._import([Transaction(date(2026, 2, 2), Decimal(-300), "LIFT-2026-01", False, "Liftonderhoud Bank BV")])
        self.assertEqual(line.vme_match_state, "auto")
        self.assertEqual(self.bill.payment_state, "paid")
        self.assertEqual(line.partner_id, self.supplier)

    def test_supplier_payment_with_other_amount_is_only_a_proposal(self):
        line = self._import([Transaction(date(2026, 2, 2), Decimal(-250), "LIFT-2026-01", False, "Liftonderhoud Bank BV")])
        self.assertEqual(line.vme_match_state, "suggested")
        self.assertEqual(line.vme_candidate_move_ids, self.bill)
        self.assertEqual(self.bill.payment_state, "not_paid")

    def test_undo_and_rematch(self):
        move = self.inv[self.owner_a2, "reserve"]
        line = self._pay(move)
        line.action_vme_undo()
        self.assertEqual(line.vme_match_state, "auto")  # matched again on the communication
        self.assertEqual(move.payment_state, "paid")
        line.action_undo_reconciliation()
        self.assertEqual(move.payment_state, "not_paid")

    def test_invoicing_user_can_link(self):
        """Odoo Community lets only the hidden group "Basic" edit bank lines; the module opens it to Invoicing."""
        user = self.env["res.users"].create({
            "name": "Medewerker Bank", "login": "medewerker.bank",
            "group_ids": [Command.set([self.env.ref("account.group_account_invoice").id])],
            "company_ids": [Command.set(self.vme.company_id.ids)], "company_id": self.vme.company_id.id,
        })
        move = self.inv[self.owner_a2, "working"]
        line = self._pay(move, communication="provisie", name="Eigenaar Bank A2")
        self.assertEqual(line.vme_match_state, "suggested")
        line.with_user(user).action_vme_reconcile()
        self.assertEqual((line.vme_match_state, move.payment_state), ("manual", "paid"))
