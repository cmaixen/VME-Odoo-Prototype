import base64
from datetime import date
from email.message import EmailMessage

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

from ..models.account_move_ai import is_valid_be_vat, is_valid_iban, parse_amount, parse_date

PDF_FILE = "vme_belgie/demo_data/facturen_pdf/lift_onderhoud_residentie_linde_2026-q4.pdf"
KNOWN_IBAN = "BE75999000900251"
OTHER_IBAN = "BE64999000900352"


def _reading(**overrides):
    """What the script sends for the demo lift invoice, with some fields replaced."""
    values = {
        "supplier_name": "Liftonderhoud Test BV",
        "supplier_vat": "BE0000000493",
        "customer_name": "VME Residentie Leesproef",
        "invoice_number": "LO-2026-0412",
        "invoice_date": "2026-10-30",
        "due_date": "2026-11-29",
        "period_start": "2026-10-01",
        "period_end": "2026-12-31",
        "description": "Onderhoudscontract lift, vierde kwartaal 2026",
        "amount_untaxed": "480.00",
        "amount_tax": "100.80",
        "amount_total": "580.80",
        "currency": "EUR",
        "iban": KNOWN_IBAN,
    }
    values.update(overrides)
    return {code: {"value": value, "confidence": "high"} for code, value in values.items()}


@tagged("post_install", "-at_install")
class TestBillAiReading(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Leesproef"})
        cls.env.cr.precommit.run()  # load the chart of accounts, which also sets the bill alias
        cls.company = cls.vme.company_id
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("L1", "L2")])
        cls.key = cls.env["vme.key"].create({
            "name": "Lift", "association_id": cls.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in lots],
        })
        owners = cls.env["res.partner"].create([{"name": f"Eigenaar {lot.name}"} for lot in lots])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(lots, owners)
        ])
        cls.supplier = cls.env["res.partner"].create({
            "name": "Liftonderhoud Test BV", "is_company": True, "vat": "BE0000000493",
            "email": "facturen@liftonderhoud-test.example.com",
        })
        cls.bank = cls.env["res.partner.bank"].create({"acc_number": KNOWN_IBAN, "partner_id": cls.supplier.id})
        # Only a person may confirm a bank account, not the system user the tests run as.
        cls.bank.with_user(cls.env.ref("base.user_admin")).allow_out_payment = True
        cls.account = cls.env["account.account"].with_company(cls.company).search(
            [("company_ids", "in", cls.company.id), ("code", "=", "611000")], limit=1
        )
        cls.env["vme.distribution.rule"].create({
            "association_id": cls.vme.id, "partner_id": cls.supplier.id,
            "key_id": cls.key.id, "account_id": cls.account.id,
        })

    def _pending_bill(self):
        """Draft bill as Odoo makes it from a mail with a PDF: no lines, waiting for the AI."""
        return self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice", "company_id": self.company.id, "vme_ai_state": "to_read",
        })

    def _check(self, bill, code):
        return bill.vme_ai_check_ids.filtered(lambda c: c.field_code == code)

    # --- helpers -------------------------------------------------------

    def test_vat_and_iban_check_digits(self):
        self.assertTrue(is_valid_be_vat("BE0000000493"))
        self.assertFalse(is_valid_be_vat("BE0000000494"))
        self.assertTrue(is_valid_iban(KNOWN_IBAN))
        self.assertFalse(is_valid_iban("BE75999000900252"))
        self.assertEqual(parse_amount("1.234,56 EUR"), 1234.56)
        self.assertEqual(parse_amount("580.80"), 580.8)
        self.assertIsNone(parse_amount("n.v.t."))
        self.assertEqual(parse_date("30/10/2026"), date(2026, 10, 30))
        self.assertIsNone(parse_date("31/02/2026"))

    # --- filling the draft ----------------------------------------------

    def test_reading_fills_draft_and_rules_set_key(self):
        bill = self._pending_bill()
        summary = bill.vme_ai_apply_reading(_reading(), "mock")

        self.assertEqual(bill.vme_ai_state, "read")
        self.assertEqual(bill.state, "draft")  # never posted automatically
        self.assertEqual(bill.partner_id, self.supplier)
        self.assertEqual(bill.ref, "LO-2026-0412")
        self.assertEqual(bill.invoice_date, date(2026, 10, 30))
        self.assertEqual(bill.invoice_date_due, date(2026, 11, 29))
        self.assertEqual((bill.vme_period_start, bill.vme_period_end), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(len(bill.invoice_line_ids), 1)
        self.assertEqual(bill.invoice_line_ids.vme_key_id, self.key)
        self.assertEqual(bill.invoice_line_ids.account_id, self.account)
        self.assertAlmostEqual(bill.amount_total, 580.80)
        self.assertEqual(bill.invoice_line_ids.tax_ids.amount, 21)
        self.assertEqual(bill.partner_bank_id, self.bank)
        self.assertEqual(set(bill.vme_ai_check_ids.mapped("status")), {"ok"})
        self.assertEqual(len(bill.vme_ai_check_ids), 14)
        self.assertEqual((summary["danger"], summary["warning"]), (0, 0))

        bill.action_post()  # nothing to review: posting works and distributes
        self.assertEqual(bill.state, "posted")
        self.assertEqual(len(bill.vme_allocation_ids), 2)

    def test_reading_only_once(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(), "mock")
        with self.assertRaises(UserError):
            bill.vme_ai_apply_reading(_reading(), "mock")

    # --- field checks ---------------------------------------------------

    def test_totals_that_do_not_add_up_are_flagged(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(amount_total="590.80"), "mock")
        self.assertEqual(self._check(bill, "amount_total").status, "warning")
        self.assertIn("niet gelijk aan het totaal", self._check(bill, "amount_total").message)

    def test_wrong_vat_check_digits_are_a_danger(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(supplier_vat="BE0000000494"), "mock")
        self.assertEqual(self._check(bill, "supplier_vat").status, "danger")
        self.assertFalse(bill.partner_id)

    def test_dates_low_confidence_and_missing_fields(self):
        reading = _reading(invoice_date="2027-01-15", due_date="2026-12-01", period_start="2026-12-31",
                           period_end="2026-10-01", invoice_number=None)
        reading["description"]["confidence"] = "low"
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(reading, "mock")
        self.assertEqual(self._check(bill, "invoice_date").status, "warning")  # in the future
        self.assertEqual(self._check(bill, "due_date").status, "warning")  # before the invoice date
        self.assertEqual(self._check(bill, "period_end").status, "warning")  # end before start
        self.assertEqual(self._check(bill, "invoice_number").status, "warning")  # not read
        self.assertEqual(self._check(bill, "description").status, "warning")  # low confidence
        # The period was not taken over: the invoice date is used instead.
        self.assertEqual(bill.vme_period_start, date(2027, 1, 15))

    def test_customer_of_another_vme_and_duplicate_number(self):
        first = self._pending_bill()
        first.vme_ai_apply_reading(_reading(), "mock")
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(customer_name="VME Ander Gebouw"), "mock")
        self.assertEqual(self._check(bill, "customer_name").status, "warning")
        self.assertEqual(self._check(bill, "invoice_number").status, "warning")
        self.assertIn("dubbel", self._check(bill, "invoice_number").message)

    # --- IBAN and new supplier: never accepted automatically -------------

    def test_other_iban_than_confirmed_account_is_a_danger(self):
        banks_before = self.env["res.partner.bank"].search_count([])
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(iban=OTHER_IBAN), "mock")

        check = self._check(bill, "iban")
        self.assertEqual(check.status, "danger")
        self.assertIn("BE75 9990 0090 0251", check.message)  # the confirmed account, as Odoo shows it
        self.assertIn("fraude", check.message)
        self.assertEqual(bill.vme_ai_iban, OTHER_IBAN)
        self.assertFalse(bill.partner_bank_id)  # neither the new nor silently the old account
        self.assertEqual(self.env["res.partner.bank"].search_count([]), banks_before)  # never stored
        self.assertEqual(bill.vme_ai_danger_count, 1)

    def test_known_but_unconfirmed_iban_is_a_danger(self):
        self.env["res.partner.bank"].create({"acc_number": OTHER_IBAN, "partner_id": self.supplier.id})
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(iban=OTHER_IBAN), "mock")
        self.assertEqual(self._check(bill, "iban").status, "danger")
        self.assertIn("niet bevestigd", self._check(bill, "iban").message)
        self.assertFalse(bill.partner_bank_id)

    def test_invalid_iban_is_a_danger(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(iban="BE75999000900252"), "mock")
        self.assertEqual(self._check(bill, "iban").status, "danger")
        self.assertIn("Ongeldig IBAN", self._check(bill, "iban").message)

    def test_new_supplier_is_never_created(self):
        partners_before = self.env["res.partner"].search_count([])
        bill = self._pending_bill()
        bill.partner_id = self.supplier  # as if the sender's address matched a known supplier
        bill.vme_ai_apply_reading(
            _reading(supplier_name="Dakwerken Test BV", supplier_vat="BE0000001186", iban="BE53999000900453"), "mock"
        )
        self.assertFalse(bill.partner_id)  # the VAT number on the bill decides, not the sender
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)
        self.assertEqual(self._check(bill, "supplier_vat").status, "danger")
        self.assertIn("Nieuwe leverancier", self._check(bill, "supplier_vat").message)
        self.assertEqual(self._check(bill, "iban").status, "danger")

    def test_danger_blocks_posting_until_reviewed(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(iban=OTHER_IBAN), "mock")
        with self.assertRaises(UserError):
            bill.action_post()
        bill.action_vme_ai_mark_reviewed()
        self.assertEqual(bill.vme_ai_reviewed_by_id, self.env.user)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.partner_bank_id)  # reviewing does not accept the IBAN of the bill

    def test_recheck_after_confirming_the_account(self):
        bill = self._pending_bill()
        bill.vme_ai_apply_reading(_reading(iban=OTHER_IBAN), "mock")
        # The supplier confirmed by phone: a person adds and confirms the new account.
        bank = self.env["res.partner.bank"].create({"acc_number": OTHER_IBAN, "partner_id": self.supplier.id})
        bank.with_user(self.env.ref("base.user_admin")).allow_out_payment = True
        bill.action_vme_ai_recheck()
        self.assertEqual(self._check(bill, "iban").status, "ok")
        self.assertEqual(bill.partner_bank_id, bank)
        self.assertFalse(bill.vme_ai_danger_count)

    # --- arrival by mail ---------------------------------------------------

    def test_mail_with_pdf_waits_for_ai_reading(self):
        with file_open(PDF_FILE, "rb") as f:
            pdf = f.read()
        message = EmailMessage()
        message["From"] = "Liftonderhoud Test BV <facturen@liftonderhoud-test.example.com>"
        message["To"] = self.vme.bill_alias_email
        message["Subject"] = "Factuur LO-2026-0412"
        message["Message-ID"] = "<lo-2026-0412@liftonderhoud-test.example.com>"
        message.set_content("In bijlage onze factuur.")
        message.add_attachment(pdf, maintype="application", subtype="pdf", filename="factuur.pdf")

        bill = self.env["account.move"].browse(self.env["mail.thread"].message_process(False, message.as_string()))
        self.assertEqual(bill.vme_association_id, self.vme)
        self.assertEqual(bill.vme_ai_state, "to_read")
        self.assertFalse(bill.invoice_line_ids)
        self.assertTrue(bill.attachment_ids.filtered(lambda a: a.mimetype == "application/pdf"))

        bill.vme_ai_apply_reading(_reading(), "mock")
        self.assertEqual(bill.invoice_line_ids.vme_key_id, self.key)

    # --- documents -----------------------------------------------------------

    def test_document_is_stored_on_vme_once(self):
        data = base64.b64encode(b"%PDF-1.4 keuringsverslag").decode()
        first = self.vme.vme_receive_document("keuring.pdf", data, "inspection_report", "high", "Noemt het gebouw.", "mock")
        self.assertFalse(first["duplicate"])
        self.assertFalse(first["folder"])  # no folders before document management (step 15)
        attachment = self.env["ir.attachment"].browse(first["attachment_id"])
        self.assertEqual((attachment.res_model, attachment.res_id), ("vme.association", self.vme.id))
        self.assertIn("Keuringsverslag", attachment.description)
        self.assertIn("Keuringsverslag", self.vme.message_ids[0].body)

        again = self.vme.vme_receive_document("keuring-kopie.pdf", data, "inspection_report", "high", "", "mock")
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["attachment_id"], attachment.id)

    def test_unknown_document_type_becomes_other(self):
        data = base64.b64encode(b"%PDF-1.4 iets").decode()
        result = self.vme.vme_receive_document("x.pdf", data, "love_letter", "low", "", "mock")
        self.assertIn("Ander document", self.env["ir.attachment"].browse(result["attachment_id"]).description)
