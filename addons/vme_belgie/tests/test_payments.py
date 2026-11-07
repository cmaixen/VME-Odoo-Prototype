import base64
from datetime import date, datetime, timedelta
from decimal import Decimal

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..demo_data.vme_demo_data import fake_iban
from ..models.bank_formats import Statement, Transaction, parse_camt053, write_camt053, write_coda
from ..models.sepa_xml import (
    PAIN_001, PAIN_008, Party, Payment, PaymentGroup, SepaError, build_credit_transfer, build_direct_debit,
    creditor_identifier, creditor_identifier_is_valid, iban_is_valid, sepa_text, validate,
)

NS1 = {"p": "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"}
NS8 = {"p": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.08"}
VME_IBAN, SUPPLIER_IBAN, OWNER_IBAN = fake_iban(9001), fake_iban(9002), fake_iban(9003)


class TestSepaXml(TransactionCase):
    """The SEPA files on their own, validated against the official ISO 20022 schemas."""

    def _transfer(self, **kwargs):
        payments = [
            Payment("BET-1-1", Decimal("1815.00"), Party("Liftonderhoud Voorbeeld BV", SUPPLIER_IBAN), "+++120/2600/07589+++"),
            Payment("BET-1-2", Decimal("12.5"), Party("Schoonmaak & Zonen", SUPPLIER_IBAN), "CLEANING-20260930"),
        ]
        group = PaymentGroup("BET-1", Party("VME Résidence Linde", VME_IBAN), date(2026, 11, 10), payments)
        return build_credit_transfer("BET/2026/0001", "VME Linde", [group], created=datetime(2026, 11, 5, 10, 0), **kwargs)

    def test_credit_transfer_is_valid_pain_001_001_09(self):
        xml = self._transfer()
        self.assertTrue(validate(xml, PAIN_001))
        root = etree.fromstring(xml)
        self.assertEqual(root.findtext("p:CstmrCdtTrfInitn/p:GrpHdr/p:NbOfTxs", namespaces=NS1), "2")
        self.assertEqual(root.findtext("p:CstmrCdtTrfInitn/p:GrpHdr/p:CtrlSum", namespaces=NS1), "1827.50")
        info = root.find("p:CstmrCdtTrfInitn/p:PmtInf", namespaces=NS1)
        self.assertEqual(info.findtext("p:BtchBookg", namespaces=NS1), "false")
        self.assertEqual(info.findtext("p:DbtrAcct/p:Id/p:IBAN", namespaces=NS1), VME_IBAN)
        self.assertEqual(info.findtext("p:Dbtr/p:Nm", namespaces=NS1), "VME Residence Linde")  # accent dropped
        first, second = info.findall("p:CdtTrfTxInf", namespaces=NS1)
        self.assertEqual(first.findtext("p:PmtId/p:EndToEndId", namespaces=NS1), "BET-1-1")
        # Belgian structured communication: SCOR, issuer BBA, 12 digits.
        self.assertEqual(first.findtext("p:RmtInf/p:Strd/p:CdtrRefInf/p:Ref", namespaces=NS1), "120260007589")
        self.assertEqual(first.findtext("p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:Issr", namespaces=NS1), "BBA")
        self.assertEqual(second.findtext("p:RmtInf/p:Ustrd", namespaces=NS1), "CLEANING-20260930")
        self.assertEqual(second.findtext("p:Cdtr/p:Nm", namespaces=NS1), "Schoonmaak Zonen")  # & not in the SEPA set

    def test_direct_debit_is_valid_pain_008_001_08(self):
        identifier = creditor_identifier("BE", "0000000097")
        first = PaymentGroup("DOM-1-W-FRST", Party("VME Linde", VME_IBAN), date(2026, 11, 20), [
            Payment("DOM-1-1", Decimal("432"), Party("Eigenaar A1", OWNER_IBAN), "+++120/2600/07589+++", "LINDE-1", date(2026, 1, 1)),
        ], "FRST")
        recurring = PaymentGroup("DOM-1-W-RCUR", Party("VME Linde", VME_IBAN), date(2026, 11, 20), [
            Payment("DOM-1-2", Decimal("43.20"), Party("Eigenaar A2", OWNER_IBAN), "provisie A2", "LINDE-2", date(2025, 6, 1)),
        ], "RCUR")
        xml = build_direct_debit("DOM/2026/0001", "VME Linde", identifier, [first, recurring])
        self.assertTrue(validate(xml, PAIN_008))
        root = etree.fromstring(xml)
        infos = root.findall("p:CstmrDrctDbtInitn/p:PmtInf", namespaces=NS8)
        self.assertEqual([i.findtext("p:PmtTpInf/p:SeqTp", namespaces=NS8) for i in infos], ["FRST", "RCUR"])
        self.assertEqual(infos[0].findtext("p:PmtTpInf/p:LclInstrm/p:Cd", namespaces=NS8), "CORE")
        self.assertEqual(infos[0].findtext("p:CdtrSchmeId/p:Id/p:PrvtId/p:Othr/p:Id", namespaces=NS8), identifier)
        tx = infos[0].find("p:DrctDbtTxInf", namespaces=NS8)
        self.assertEqual(tx.findtext("p:DrctDbtTx/p:MndtRltdInf/p:MndtId", namespaces=NS8), "LINDE-1")
        self.assertEqual(tx.findtext("p:DrctDbtTx/p:MndtRltdInf/p:DtOfSgntr", namespaces=NS8), "2026-01-01")
        self.assertEqual(root.findtext("p:CstmrDrctDbtInitn/p:GrpHdr/p:CtrlSum", namespaces=NS8), "475.20")

    def test_schema_rejects_a_broken_file(self):
        root = etree.fromstring(self._transfer())
        header = root.find("p:CstmrCdtTrfInitn/p:GrpHdr", namespaces=NS1)
        header.remove(header.find("p:MsgId", namespaces=NS1))
        with self.assertRaises(SepaError):
            validate(etree.tostring(root), PAIN_001)

    def test_checks_before_writing(self):
        self.assertTrue(iban_is_valid(VME_IBAN))
        self.assertFalse(iban_is_valid("BE00999000900100"))
        bad = PaymentGroup("X", Party("VME", VME_IBAN), date(2026, 11, 10),
                           [Payment("X-1", Decimal(10), Party("Leverancier", "BE00999000900100"))])
        with self.assertRaises(SepaError):
            build_credit_transfer("X", "VME", [bad])
        with self.assertRaises(SepaError):
            build_credit_transfer("X", "VME", [PaymentGroup("X", Party("VME", VME_IBAN), date(2026, 11, 10), [])])
        no_mandate = PaymentGroup("X", Party("VME", VME_IBAN), date(2026, 11, 10),
                                  [Payment("X-1", Decimal(10), Party("Eigenaar", OWNER_IBAN))])
        with self.assertRaises(SepaError):
            build_direct_debit("X", "VME", creditor_identifier("BE", "0000000097"), [no_mandate])

    def test_creditor_identifier(self):
        # Example of the EPC (German test identifier) and a Belgian VME with its KBO number.
        self.assertTrue(creditor_identifier_is_valid("DE98ZZZ09999999999"))
        self.assertEqual(creditor_identifier("DE", "09999999999"), "DE98ZZZ09999999999")
        self.assertTrue(creditor_identifier_is_valid(creditor_identifier("BE", "0123456749")))
        self.assertFalse(creditor_identifier_is_valid("BE00ZZZ0123456749"))

    def test_sepa_text(self):
        self.assertEqual(sepa_text("Café ‘De Linde’ & Co", 70), "Cafe De Linde Co")
        self.assertEqual(len(sepa_text("x" * 200, 140)), 140)

    def test_camt_round_trip_with_reference_and_return(self):
        transactions = [
            Transaction(date(2026, 11, 6), Decimal("-1815.00"), "LIFT-2026-09", False, "Lift BV", SUPPLIER_IBAN, "R1", "BET-1-1"),
            Transaction(date(2026, 11, 8), Decimal("-432.00"), "+++120/2600/07589+++", True, "Eigenaar A1", OWNER_IBAN,
                        "R2", "DOM-1-1", "AM04"),
        ]
        statement = Statement(VME_IBAN, "EUR", "050", date(2026, 11, 8), Decimal(5000), Decimal("2753.00"), transactions)
        [parsed] = parse_camt053(write_camt053(statement, holder="VME Linde").encode())
        transfer, returned = parsed.transactions
        self.assertEqual((transfer.end_to_end_id, transfer.return_reason, transfer.amount), ("BET-1-1", "", Decimal("-1815")))
        self.assertEqual((returned.end_to_end_id, returned.return_reason), ("DOM-1-1", "AM04"))
        self.assertEqual(returned.communication, "+++120/2600/07589+++")


@tagged("post_install", "-at_install")
class TestPayments(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Betaling", "kbo_number": "0000.000.097"})
        cls.env.cr.precommit.run()  # load the chart of accounts
        Bank = cls.env["res.partner.bank"]
        admin = cls.env.ref("base.user_admin")
        cls.working_bank = Bank.create({"acc_number": fake_iban(9101), "partner_id": cls.vme.partner_id.id})
        cls.reserve_bank = Bank.create({"acc_number": fake_iban(9102), "partner_id": cls.vme.partner_id.id})
        cls.vme.write({"working_capital_bank_id": cls.working_bank.id, "reserve_capital_bank_id": cls.reserve_bank.id})
        (cls.working_bank | cls.reserve_bank).with_user(admin).allow_out_payment = True

        Users = cls.env["res.users"].with_context(no_reset_password=True)
        invoice_group = cls.env.ref("account.group_account_invoice")
        cls.employee, cls.colleague, cls.council = Users.create([{
            "name": name, "login": login, "company_id": cls.vme.company_id.id,
            "company_ids": [Command.set(cls.vme.company_id.ids)], "group_ids": [Command.set(invoice_group.ids)],
        } for name, login in (("Medewerker Test", "medewerker.test"), ("Collega Test", "collega.test"),
                              ("Raadslid Test", "raadslid.test"))])
        cls.vme.write({"payment_approval_threshold": 1000, "payment_second_approver_id": cls.council.id})

        company = cls.vme.company_id
        cls.supplier = cls.env["res.partner"].create({"name": "Liftonderhoud Betaling BV", "is_company": True})
        cls.supplier_bank = Bank.create({"acc_number": fake_iban(9201), "partner_id": cls.supplier.id})
        cls.supplier_bank.with_user(admin).allow_out_payment = True

        def bill(amount, ref, due):
            move = cls.env["account.move"].with_company(company).create({
                "move_type": "in_invoice", "partner_id": cls.supplier.id, "invoice_date": date(2026, 10, 1),
                "invoice_date_due": due, "ref": ref, "partner_bank_id": cls.supplier_bank.id,
                "invoice_line_ids": [Command.create({"name": ref, "quantity": 1, "price_unit": amount, "tax_ids": [Command.clear()]})],
            })
            move.with_company(company).action_post()
            return move
        cls.small = bill(300, "LIFT-2026-10", date(2026, 10, 31))
        cls.large = bill(2500, "LIFT-2026-REP", date(2026, 10, 31))
        cls.later = bill(200, "LIFT-2027-01", date(2027, 1, 31))

        # Owners and one provision call, for the direct debits.
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name, "lot_type": "apartment"} for name in ("A1", "A2")])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in cls.lots],
        })
        cls.owner_a1, cls.owner_a2 = cls.env["res.partner"].create([{"name": "Eigenaar Betaling A1"}, {"name": "Eigenaar Betaling A2"}])
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
        cls.call = cls.env["vme.provision.call"].search([("association_id", "=", cls.vme.id)])
        cls.inv = {(m.partner_id, m.vme_fund): m for m in cls.call.invoice_ids}  # 500 working, 50 reserve each
        cls.owner_bank = Bank.create({"acc_number": OWNER_IBAN, "partner_id": cls.owner_a1.id})
        cls.mandate = cls.env["vme.sepa.mandate"].create({
            "association_id": cls.vme.id, "partner_id": cls.owner_a1.id, "partner_bank_id": cls.owner_bank.id,
            "signature_date": date(2026, 1, 1),
        })
        cls.tomorrow = fields.Date.today() + timedelta(days=1)

    # Helpers

    def _approve(self, *moves, user=None):
        for move in moves:
            move.with_user(user or self.employee).action_vme_approve()

    def _transfer_batch(self, **vals):
        batch = self.env["vme.payment.batch"].create({
            "association_id": self.vme.id, "batch_type": "transfer", "fund": "working",
            "due_until": date(2026, 12, 31), "execution_date": self.tomorrow, **vals,
        })
        batch.action_fill_proposal()
        return batch

    def _statement(self, transactions, fund="working", number="101"):
        bank = self.working_bank if fund == "working" else self.reserve_bank
        statement = Statement(bank.sanitized_acc_number, "EUR", number, max(t.date for t in transactions), Decimal(0),
                              sum(t.amount for t in transactions), transactions)
        return self.env["vme.bank.import.wizard"]._import_file(write_camt053(statement).encode(), "test.xml")

    # Approval rule

    def test_creditor_identifier_from_kbo(self):
        self.assertEqual(self.vme.sepa_creditor_identifier, creditor_identifier("BE", "0000000097"))

    def test_small_bill_needs_one_approval(self):
        self.assertEqual(self.small.vme_approval_state, "to_approve")
        self.assertFalse(self.small.vme_needs_second_approval)
        self._approve(self.small)
        self.assertEqual(self.small.vme_approval_state, "approved")
        self.assertEqual(self.small.vme_approved_by_id, self.employee)
        with self.assertRaises(UserError):
            self._approve(self.small, user=self.colleague)  # already approved

    def test_large_bill_needs_the_second_approver(self):
        self.assertTrue(self.large.vme_needs_second_approval)  # 2500 >= 1000
        self._approve(self.large)
        self.assertEqual(self.large.vme_approval_state, "first_approved")
        self.assertTrue(self.large.activity_ids.filtered(lambda a: a.user_id == self.council))
        # Another employee is not the second approver.
        with self.assertRaises(UserError):
            self._approve(self.large, user=self.colleague)
        self._approve(self.large, user=self.council)
        self.assertEqual(self.large.vme_approval_state, "approved")
        self.assertEqual(self.large.vme_second_approved_by_id, self.council)

    def test_second_approval_by_another_person(self):
        # The council member approves first: the second approval cannot come from the same person.
        self._approve(self.large, user=self.council)
        with self.assertRaises(UserError):
            self._approve(self.large, user=self.council)

    def test_threshold_zero_and_missing_approver(self):
        self.vme.payment_approval_threshold = 0
        self.assertFalse(self.large.vme_needs_second_approval)
        self._approve(self.large)
        self.assertEqual(self.large.vme_approval_state, "approved")
        self.vme.write({"payment_approval_threshold": 100, "payment_second_approver_id": False})
        with self.assertRaises(UserError):
            self._approve(self.small)

    def test_reset_to_draft_clears_approval(self):
        self._approve(self.small)
        self.small.button_draft()
        self.assertEqual(self.small.vme_approval_state, "to_approve")
        self.assertFalse(self.small.vme_approved_by_id)

    def test_proposal_takes_only_approved_bills_due(self):
        self._approve(self.small, self.large, self.later)
        batch = self._transfer_batch(due_until=date(2026, 11, 30))
        self.assertEqual(batch.line_ids.move_id, self.small)  # large waits, later is not due yet
        self.assertIn("wacht op de tweede goedkeuring", batch.proposal_note)
        self._approve(self.large, user=self.council)
        batch.action_fill_proposal()
        self.assertEqual(batch.line_ids.move_id, self.small | self.large)
        self.assertEqual(batch.amount_total, 2800)
        # A bill in an active batch is not proposed again.
        self.assertFalse(self._transfer_batch(due_until=date(2026, 11, 30)).line_ids)

    def test_untrusted_supplier_account_is_never_paid(self):
        self._approve(self.small)
        self.supplier_bank.with_user(self.env.ref("base.user_admin")).allow_out_payment = False
        batch = self._transfer_batch()
        self.assertFalse(batch.line_ids)
        self.assertIn("niet bevestigd", batch.proposal_note)
        # Trusted at proposal time, untrusted before the file: refused.
        self.supplier_bank.with_user(self.env.ref("base.user_admin")).allow_out_payment = True
        batch.action_fill_proposal()
        self.supplier_bank.with_user(self.env.ref("base.user_admin")).allow_out_payment = False
        with self.assertRaises(UserError):
            batch.action_generate_file()

    # SEPA file and feedback through the bank statement

    def test_transfer_batch_file_and_confirmation(self):
        self._approve(self.small)
        batch = self._transfer_batch()
        batch.action_generate_file()
        self.assertEqual(batch.state, "generated")
        xml = base64.b64decode(batch.file_data)
        self.assertTrue(validate(xml, PAIN_001))
        self.assertIn(self.supplier_bank.sanitized_acc_number.encode(), xml)
        batch.action_mark_sent()
        line = batch.line_ids
        self.assertEqual((batch.state, line.state, self.small.vme_payment_status), ("sent", "sent", "sent"))
        self.assertEqual(self.small.payment_state, "not_paid")  # sent, not yet confirmed by the bank

        [statement_line] = self._statement([Transaction(
            self.tomorrow, Decimal("-300"), "LIFT-2026-10", False, self.supplier.name,
            self.supplier_bank.sanitized_acc_number, "B1", line.end_to_end_id)])
        self.assertEqual(statement_line.vme_end_to_end_id, line.end_to_end_id)
        self.assertEqual(statement_line.vme_match_state, "auto")
        self.assertEqual(self.small.payment_state, "paid")
        self.assertEqual((line.state, line.statement_line_id), ("paid", statement_line))
        self.assertEqual(batch.state, "done")

    def test_transfer_confirmed_by_coda_without_reference(self):
        """CODA has no SEPA reference: the amount and the communication of the payment find it."""
        self._approve(self.small)
        batch = self._transfer_batch()
        batch.action_generate_file()
        batch.action_mark_sent()
        statement = Statement(self.working_bank.sanitized_acc_number, "EUR", "102", self.tomorrow, Decimal(0), Decimal(-300),
                              [Transaction(self.tomorrow, Decimal(-300), "LIFT-2026-10", False, self.supplier.name, "")])
        [statement_line] = self.env["vme.bank.import.wizard"]._import_file(
            write_coda([statement], self.tomorrow).encode("latin-1"), "test.cod")
        self.assertTrue(statement_line.is_reconciled)
        self.assertEqual(batch.line_ids.state, "paid")
        self.assertEqual(batch.state, "done")

    def test_file_only_from_a_draft_and_never_twice(self):
        self._approve(self.small)
        batch = self._transfer_batch()
        batch.action_generate_file()
        with self.assertRaises(UserError):
            batch.action_generate_file()
        with self.assertRaises(UserError):
            batch.unlink()
        batch.action_back_to_draft()
        self.assertFalse(batch.file_data)
        batch.action_cancel()
        self.assertFalse(self.small.vme_payment_status)

    def test_direct_debit_file(self):
        batch = self.env["vme.payment.batch"].browse(self.call.action_create_direct_debit_batch()["res_id"])
        # Only A1 signed a mandate: two provisions (working and reserve) of 500 and 50.
        self.assertEqual(batch.line_ids.move_id, self.inv[self.owner_a1, "working"] | self.inv[self.owner_a1, "reserve"])
        self.assertIn("Eigenaar Betaling A2", batch.proposal_note)
        self.assertGreaterEqual(batch.execution_date, self.call.date + timedelta(days=14))
        batch.action_generate_file()
        xml = base64.b64decode(batch.file_data)
        self.assertTrue(validate(xml, PAIN_008))
        root = etree.fromstring(xml)
        infos = root.findall("p:CstmrDrctDbtInitn/p:PmtInf", namespaces=NS8)
        # One block per fund account, both FRST (first collection on this mandate).
        self.assertEqual(sorted(i.findtext("p:CdtrAcct/p:Id/p:IBAN", namespaces=NS8) for i in infos),
                         sorted([self.working_bank.sanitized_acc_number, self.reserve_bank.sanitized_acc_number]))
        self.assertEqual({i.findtext("p:PmtTpInf/p:SeqTp", namespaces=NS8) for i in infos}, {"FRST"})
        batch.action_mark_sent()
        self.assertTrue(self.mandate.first_collection_done)

    def _pay(self, move, amount):
        self.env["account.payment.register"].with_company(self.vme.company_id).with_context(
            active_model="account.move", active_ids=move.ids,
        ).create({"journal_id": self.vme._ensure_fund_bank_journals()[self.vme]["working"].id, "amount": amount}
                 ).action_create_payments()

    def test_file_refused_when_paid_since_the_proposal(self):
        # The owner pays 200 by transfer between the proposal and the file: no collection of 500.
        batch = self.env["vme.payment.batch"].browse(self.call.action_create_direct_debit_batch()["res_id"])
        working = self.inv[self.owner_a1, "working"]
        self._pay(working, 200)
        with self.assertRaisesRegex(UserError, "open"):
            batch.action_generate_file()
        batch.line_ids.filtered(lambda l: l.move_id == working).amount = 300
        batch.action_generate_file()
        self.assertEqual(batch.state, "generated")

    def test_transfer_refused_when_paid_since_the_proposal(self):
        self._approve(self.small)
        batch = self._transfer_batch()
        self._pay(self.small, 100)
        with self.assertRaisesRegex(UserError, "open|betaald"):
            batch.action_generate_file()

    def test_pre_notification_term(self):
        batch = self.env["vme.payment.batch"].create({
            "association_id": self.vme.id, "batch_type": "direct_debit", "provision_call_id": self.call.id,
            "execution_date": self.call.date + timedelta(days=5),
        })
        batch.action_fill_proposal()
        with self.assertRaises(UserError):
            batch._build_direct_debit_file("TEST")

    def test_failed_direct_debit_goes_to_collection(self):
        batch = self.env["vme.payment.batch"].browse(self.call.action_create_direct_debit_batch()["res_id"])
        batch.action_generate_file()
        batch.action_mark_sent()
        working = batch.line_ids.filtered(lambda l: l.move_id.vme_fund == "working")
        reserve = batch.line_ids - working
        invoice = working.move_id

        def collected(line, amount, day, reason=""):
            return Transaction(day, Decimal(amount), line.communication, True, self.owner_a1.name, OWNER_IBAN,
                               f"B-{line.id}-{reason}", line.end_to_end_id, reason)
        day = self.tomorrow
        statement_lines = self._statement([
            collected(working, "500", day), collected(working, "-500", day + timedelta(days=2), "AM04")])
        self._statement([collected(reserve, "50", day)], fund="reserve")
        credit, returned = statement_lines.sorted("amount", reverse=True)
        self.assertEqual(credit.vme_match_state, "auto")
        self.assertEqual(credit.vme_days_late, 0)  # collected after the due date, but not the owner's fault
        self.assertEqual(reserve.state, "paid")
        # The return reopens the provision and settles both bank movements with each other.
        self.assertEqual(returned.vme_exception, "dd_returned")
        self.assertTrue(credit.is_reconciled and returned.is_reconciled)
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertEqual(invoice.amount_residual, 500)
        self.assertEqual(working.state, "rejected")
        self.assertIn("AM04", working.return_reason)
        self.assertEqual(batch.state, "done")
        collection = self.env["vme.collection"].search([("association_id", "=", self.vme.id), ("partner_id", "=", self.owner_a1.id)])
        self.assertTrue(collection)
        self.assertIn("teruggekomen", collection.message_ids[0].body)
        # The provision is overdue (due 4 February 2026): it is in the arrears of the collection.
        self.assertIn(invoice.name, collection.arrears_ids.mapped("move_name"))

    def test_mandate_rules(self):
        with self.assertRaises(Exception):
            self.env["vme.sepa.mandate"].create({
                "association_id": self.vme.id, "partner_id": self.owner_a1.id, "partner_bank_id": self.owner_bank.id,
            })
        self.assertTrue(self.mandate.reference.startswith("RESIDENTIE-"))
        self.mandate.action_revoke()
        batch = self.env["vme.payment.batch"].browse(self.call.action_create_direct_debit_batch()["res_id"])
        self.assertFalse(batch.line_ids)
