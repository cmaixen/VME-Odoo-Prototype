from datetime import date
from email.message import EmailMessage

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open, mute_logger

UBL_FILE = "vme_belgie/demo_data/facturen/elektriciteit_residentie_linde_2026.xml"


def _mail(to, message_id, attachment=None, sender="facturen@energie-mailtest.example.com"):
    """Raw mail as a mail server would hand it to Odoo's gateway."""
    message = EmailMessage()
    message["From"] = f"Energie Mailtest <{sender}>"
    message["To"] = to
    message["Subject"] = "Factuur elektriciteit"
    message["Message-ID"] = message_id
    message.set_content("In bijlage onze factuur.")
    if attachment:
        message.add_attachment(attachment, maintype="application", subtype="xml", filename="factuur.xml")
    return message.as_string()


@tagged("post_install", "-at_install")
class TestBillMail(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Postbus"})
        cls.env.cr.precommit.run()  # load the chart of accounts, which also sets the alias
        cls.company = cls.vme.company_id
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("P1", "P2")])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in lots],
        })
        owners = cls.env["res.partner"].create([{"name": f"Eigenaar {lot.name}"} for lot in lots])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(lots, owners)
        ])
        # Same VAT number as the supplier in the UBL file, so the import finds this partner.
        cls.supplier = cls.env["res.partner"].create({
            "name": "Energie Mailtest", "is_company": True, "vat": "BE0000000394",
            "email": "facturen@energie-mailtest.example.com",
        })
        cls.account = cls.env["account.account"].with_company(cls.company).search(
            [("company_ids", "in", cls.company.id), ("code", "=", "612500")], limit=1
        )
        cls.env["vme.distribution.rule"].create({
            "association_id": cls.vme.id, "partner_id": cls.supplier.id,
            "key_id": cls.key.id, "account_id": cls.account.id,
        })
        with file_open(UBL_FILE, "rb") as f:
            cls.ubl = f.read()

    def _bills(self):
        return self.env["account.move"].search([("company_id", "=", self.company.id), ("move_type", "=", "in_invoice")])

    def test_vme_has_bill_address(self):
        self.assertEqual(self.vme.bill_alias_email, "facturen-residentie-postbus@syndicus.example.com")
        journal = self.vme._purchase_journal()
        self.assertEqual(journal.alias_id.alias_defaults and journal.alias_id.alias_model_id.model, "account.move")

    def test_mail_with_ubl_becomes_draft_bill(self):
        raw = _mail(self.vme.bill_alias_email, "<ubl-1@energie-mailtest.example.com>", self.ubl)
        bill_id = self.env["mail.thread"].message_process(False, raw)

        bill = self.env["account.move"].browse(bill_id)
        self.assertEqual(bill, self._bills())
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.state, "draft")  # never posted automatically
        self.assertEqual(bill.vme_association_id, self.vme)
        self.assertEqual(bill.partner_id, self.supplier)
        self.assertEqual(bill.ref, "EV-2026-110301")
        self.assertEqual((bill.vme_period_start, bill.vme_period_end), (date(2025, 11, 1), date(2026, 10, 31)))
        self.assertEqual(len(bill.invoice_line_ids), 2)
        self.assertEqual(bill.invoice_line_ids.vme_key_id, self.key)
        self.assertEqual(bill.invoice_line_ids.account_id, self.account)
        self.assertAlmostEqual(bill.amount_total, 5324.00, places=2)

        # Posting distributes it like an uploaded invoice.
        bill.action_post()
        self.assertAlmostEqual(sum(bill.vme_allocation_ids.mapped("amount")), 5324.00, places=2)

    def test_same_mail_twice_gives_one_bill(self):
        raw = _mail(self.vme.bill_alias_email, "<ubl-2@energie-mailtest.example.com>", self.ubl)
        self.env["mail.thread"].message_process(False, raw)
        with mute_logger("odoo.addons.mail.models.mail_thread"):
            self.assertFalse(self.env["mail.thread"].message_process(False, raw))
        self.assertEqual(len(self._bills()), 1)

    def test_mail_without_attachment_makes_no_bill(self):
        raw = _mail(self.vme.bill_alias_email, "<leeg-1@energie-mailtest.example.com>")
        with mute_logger("odoo.addons.mail.models.mail_thread"):
            self.env["mail.thread"].message_process(False, raw)
        self.assertFalse(self._bills())

    def test_unknown_address_is_refused(self):
        raw = _mail("facturen-bestaat-niet@syndicus.example.com", "<onbekend-1@energie-mailtest.example.com>", self.ubl)
        with mute_logger("odoo.addons.mail.models.mail_thread"), self.assertRaises(ValueError):
            self.env["mail.thread"].message_process(False, raw)
        self.assertFalse(self._bills())

    def test_alias_restored_on_upgrade(self):
        # VME's created before step 7b: no mail domain on the company, default journal alias.
        journal = self.vme._purchase_journal()
        journal.alias_name = "vendor-bills-oud"
        self.company.alias_domain_id = False
        self.env["vme.association"]._ensure_all_bill_aliases()
        self.assertEqual(self.company.alias_domain_id, self.env.ref("vme_belgie.mail_alias_domain_vme"))
        self.assertEqual(journal.alias_name, "facturen-residentie-postbus")
