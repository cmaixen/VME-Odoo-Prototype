from datetime import date

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..models.belcotax_xml import kbo_is_valid, national_number_is_valid
from ..models.vme_belcotax import belcotax_deadline


@tagged("post_install", "-at_install")
class TestBelcotax(TransactionCase):
    """Residentie Fiche pays a self-employed auditor, a consultancy firm, a small expert and a cleaner in 2026.

    Only the first three are 281.50-liable; the cleaner is an ordinary supplier.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Fiche"})
        cls.env.cr.precommit.run()
        cls.company = cls.vme.company_id
        cls.company.write({"street": "Fichestraat 1", "zip": "2000", "city": "Voorbeeldstad",
                           "company_registry": "0000000196"})
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 500}) for lot in lots],
        })
        owners = cls.env["res.partner"].create([{"name": "Eigenaar Fiche A1"}, {"name": "Eigenaar Fiche A2"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)} for lot, owner in zip(lots, owners)])
        be = cls.env.ref("base.be")
        Partner = cls.env["res.partner"]
        cls.auditor = Partner.create({
            "name": "Commissaris Fiche", "street": "Controlelaan 2", "zip": "2000", "city": "Voorbeeldstad",
            "country_id": be.id, "vme_belcotax_liable": True, "vme_belcotax_category": "fees",
            "vme_belcotax_profession": "Boekhouder", "vme_national_number": "00.00.00-001.96",
        })
        cls.consultant = Partner.create({
            "name": "Advies Fiche BV", "is_company": True, "vat": "BE0000000592", "street": "Raadgeverstraat 3",
            "zip": "9000", "city": "Voorbeeldgem", "country_id": be.id, "vme_belcotax_liable": True,
            "vme_belcotax_category": "commission", "vme_belcotax_profession": "Consultant",
        })
        cls.expert = Partner.create({"name": "Expert Fiche", "vme_belcotax_liable": True})
        cls.cleaner = Partner.create({"name": "Schoonmaak Fiche BV", "is_company": True})
        cls.account = cls.env["account.account"].with_company(cls.company).search(
            [("company_ids", "in", cls.company.id), ("code", "=", "611000")], limit=1)

    def _bill(self, partner, invoice_date, amount, move_type="in_invoice", post=True):
        bill = self.env["account.move"].with_company(self.company).create({
            "move_type": move_type, "partner_id": partner.id, "invoice_date": invoice_date,
            "invoice_line_ids": [Command.create({
                "name": "Prestatie", "price_unit": amount, "account_id": self.account.id, "vme_key_id": self.key.id,
                "tax_ids": [Command.clear()],
            })],
        })
        if post:
            bill.action_post()
        return bill

    def _pay(self, bill, payment_date, amount=None):
        vals = {"payment_date": payment_date}
        if amount:
            vals["amount"] = amount
        self.env["account.payment.register"].with_company(self.company).with_context(
            active_model="account.move", active_ids=bill.ids).create(vals).action_create_payments()

    def _statement(self, year=2026):
        return self.env["vme.belcotax.statement"].create({"association_id": self.vme.id, "year": year})

    def _line(self, statement, partner):
        return statement.line_ids.filtered(lambda l: l.partner_id == partner)

    # Selection

    def test_only_paid_bills_of_liable_suppliers_in_the_year(self):
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 600), date(2026, 3, 20))
        self._pay(self._bill(self.cleaner, date(2026, 3, 1), 900), date(2026, 3, 20))  # not liable
        self._bill(self.auditor, date(2026, 5, 1), 400)  # posted, never paid
        self._bill(self.auditor, date(2026, 6, 1), 700, post=False)  # draft
        self._pay(self._bill(self.auditor, date(2025, 12, 1), 300), date(2026, 1, 10))  # paid in 2026
        self._pay(self._bill(self.auditor, date(2026, 12, 1), 200), date(2027, 1, 10))  # paid in 2027
        statement = self._statement()
        self.assertEqual(statement.line_ids.partner_id, self.auditor)
        line = self._line(statement, self.auditor)
        self.assertEqual(line.amount_fees, 900.0)
        self.assertEqual(len(line.bill_ids), 2)
        self.assertEqual(self._statement(2027).line_ids.amount_total, 200.0)

    def test_other_vme_does_not_count(self):
        other = self.env["vme.association"].create({"name": "Residentie Andere Fiche"})
        self.env.cr.precommit.run()
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 600), date(2026, 3, 20))
        statement = self.env["vme.belcotax.statement"].create({"association_id": other.id, "year": 2026})
        self.assertFalse(statement.line_ids)

    # Totals

    def test_partial_payment_credit_note_and_category(self):
        bill = self._bill(self.consultant, date(2026, 2, 1), 1000)
        self._pay(bill, date(2026, 2, 15), amount=400)
        self._pay(bill, date(2026, 4, 15), amount=350)
        refund = self._bill(self.consultant, date(2026, 5, 1), 100, move_type="in_refund")
        self._pay(refund, date(2026, 5, 10))
        line = self._line(self._statement(), self.consultant)
        self.assertEqual(line.amount_commission, 650.0)
        self.assertEqual(line.amount_fees, 0.0)
        self.assertEqual(line.amount_total, 650.0)
        self.assertEqual(line.kbo, "0000000592")
        self.assertTrue(line.is_company)

    # Threshold

    def test_threshold_of_250_euro_per_beneficiary(self):
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 250), date(2026, 3, 20))
        self._pay(self._bill(self.consultant, date(2026, 3, 1), 250.01), date(2026, 3, 20))
        statement = self._statement()
        self.assertTrue(self._line(statement, self.auditor).below_threshold)
        self.assertFalse(self._line(statement, self.consultant).below_threshold)
        self.assertEqual(statement.fiche_count, 1)
        self.assertEqual(statement.total_amount, 250.01)

    def test_threshold_counts_all_bills_together(self):
        for day in (1, 2, 3):
            self._pay(self._bill(self.auditor, date(2026, 3, day), 100), date(2026, 3, 20))
        self.assertFalse(self._line(self._statement(), self.auditor).below_threshold)

    # Warnings and XML

    def test_missing_data_warns_but_does_not_block(self):
        self._pay(self._bill(self.expert, date(2026, 3, 1), 500), date(2026, 3, 20))
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 800), date(2026, 3, 20))
        statement = self._statement()
        warning = self._line(statement, self.expert).warning
        self.assertIn("Adres onvolledig", warning)
        self.assertIn("Rijksregisternummer ontbreekt", warning)
        self.assertIn("Beroep ontbreekt", warning)
        self.assertFalse(self._line(statement, self.auditor).warning)
        self.assertEqual(statement.warning_count, 1)
        statement.action_mark_checked()
        statement.action_download_xml()
        self.assertTrue(statement.xml_file)

    def test_xml_needs_a_check_and_holds_the_fiches(self):
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 1234.56), date(2026, 3, 20))
        self._pay(self._bill(self.consultant, date(2026, 3, 1), 100), date(2026, 3, 20))  # below threshold
        statement = self._statement()
        with self.assertRaises(UserError):
            statement.action_download_xml()
        with self.assertRaises(UserError):
            statement.action_mark_filed()
        statement.action_mark_checked()
        self.assertEqual(statement.checked_by_id, self.env.user)
        statement.action_download_xml()
        root = etree.fromstring(statement._belcotax_xml())
        fiches = root.findall(".//Fiche28150")
        self.assertEqual(len(fiches), 1)
        self.assertEqual(fiches[0].findtext("f2013_naam"), "Commissaris Fiche")
        self.assertEqual(fiches[0].findtext("f2011_nationaalnr"), "00000000196")
        self.assertEqual(fiches[0].findtext("f50_2061_erelonenofvacatie"), "123456")
        self.assertEqual(fiches[0].findtext("f50_2064_totaal"), "123456")
        self.assertEqual(fiches[0].findtext("f50_2060_commissies"), "0")
        self.assertEqual(root.findtext(".//a1005_registratienummer"), "0000000196")
        self.assertEqual(root.findtext(".//r8012_controletotaal"), "123456")
        statement.action_mark_filed()
        self.assertEqual(statement.state, "filed")

    def test_recompute_takes_new_payments_and_resets_the_check(self):
        statement = self._statement()
        self.assertFalse(statement.line_ids)
        statement.action_mark_checked()
        with self.assertRaises(UserError):
            statement.action_download_xml()  # no fiches at all
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 600), date(2026, 3, 20))
        statement.action_compute()
        self.assertEqual(statement.state, "draft")
        self.assertEqual(statement.total_amount, 600.0)

    def test_staff_with_another_company_switched_on(self):
        """The totals do not depend on the companies switched on, and the audit trail only changes by button."""
        main = self.env.ref("base.main_company")
        staff = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Fiche", "login": "medewerker.fiche@example.com",
            "group_ids": [Command.set([self.env.ref("account.group_account_invoice").id])],
            "company_id": main.id, "company_ids": [Command.set((main | self.company).ids)],
        })
        self._pay(self._bill(self.auditor, date(2026, 3, 1), 600), date(2026, 3, 20))
        statement = self.env["vme.belcotax.statement"].with_user(staff).with_company(main).create(
            {"association_id": self.vme.id, "year": 2026})
        self.assertEqual(statement.total_amount, 600.0)
        with self.assertRaises(AccessError):
            statement.write({"state": "filed"})
        statement.action_mark_checked()
        self.assertEqual(statement.checked_by_id, staff)
        with self.assertRaises(UserError):
            statement.line_ids.amount_fees = 1.0
        with self.assertRaises(UserError):
            statement.action_mark_checked()
        statement.action_download_xml()
        statement.action_mark_filed()
        with self.assertRaises(UserError):
            statement.action_compute()
        with self.assertRaises(UserError):
            statement.unlink()
        statement.action_back_to_draft()
        statement.line_ids.amount_fees = 650.0

    def test_number_checks_and_deadline(self):
        self.assertTrue(kbo_is_valid("BE 0000.000.592"))
        self.assertFalse(kbo_is_valid("0000000593"))
        self.assertTrue(national_number_is_valid("00.00.00-001.96"))
        self.assertFalse(national_number_is_valid("00000000195"))
        self.assertEqual(belcotax_deadline(2026), date(2027, 6, 30))
