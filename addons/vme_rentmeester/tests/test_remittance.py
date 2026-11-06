from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..models import remittance_rules as rules


@tagged("post_install", "-at_install")
class TestRemittanceRules(TransactionCase):
    def test_percent_fee_and_vat(self):
        self.assertEqual(rules.percent_fee(1200, 7), 84.0)
        self.assertEqual(rules.fee_vat(84.0), 17.64)
        self.assertEqual(rules.percent_fee(333.33, 6.5), 21.67)  # 21.66645 rounds up

    def test_fixed_fee_months(self):
        start = date(2026, 1, 15)
        self.assertEqual(rules.months_to_charge(date(2026, 1, 1), start), 1)
        self.assertEqual(rules.months_to_charge(date(2026, 3, 1), start), 3)
        self.assertEqual(rules.months_to_charge(date(2026, 3, 1), start, last_charged=date(2026, 1, 1)), 2)
        self.assertEqual(rules.months_to_charge(date(2026, 3, 1), start, last_charged=date(2026, 3, 1)), 0)
        # After the end of the mandate nothing more is charged.
        self.assertEqual(rules.months_to_charge(date(2026, 6, 1), start, date(2026, 3, 1), date(2026, 4, 30)), 1)
        self.assertEqual(rules.fixed_fee(65, 2), 130.0)

    def test_split_partial_payment(self):
        # 450 paid on 800 rent + 100 charges: 400 rent, 50 charges.
        self.assertEqual(rules.split_received(450, 800, 100), (400.0, 50.0))
        self.assertEqual(rules.split_received(100, 0, 0), (0.0, 0.0))
        self.assertEqual(rules.balance(1350, 121, 101.64), 1127.36)


@tagged("post_install", "-at_install")
class TestRemittance(TransactionCase):
    """Landlord with one lease of 800 rent + 100 charges and a mandate of 7% on the rent.

    January paid in full, February 450 of 900. A plumber bill of 121 paid for the landlord in February.
    Remittance of February, checked by hand:
    received 900 + 450 = 1350 (rent 800 + 400, charges 100 + 50); fee 7% x 1200 = 84.00, VAT 17.64,
    fee 101.64; balance 1350 - 121 - 101.64 = 1127.36.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.office = cls.env["res.company"].create({
            "name": "Rentmeester Doorstorting Test", "country_id": cls.env.ref("base.be").id,
            "currency_id": cls.env.ref("base.EUR").id, "is_rent_management": True,
        })
        cls.env["account.chart.template"].try_loading("be_comp", cls.office, install_demo=False)
        cls.env.user.company_ids |= cls.office
        cls.admin.company_ids |= cls.office
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.office.id]))
        Partner, Bank = cls.env["res.partner"], cls.env["res.partner.bank"]
        cls.landlord, cls.tenant, cls.plumber = Partner.create([
            {"name": "Verhuurder Doorstorting"}, {"name": "Huurder Doorstorting"},
            {"name": "Loodgieter Doorstorting", "is_company": True}])
        cls.office.rent_bank_id = Bank.create({"acc_number": "BE71096123456769", "partner_id": cls.office.partner_id.id})
        cls.landlord_bank = Bank.create({"acc_number": "BE68539007547034", "partner_id": cls.landlord.id})
        cls.mandate = cls.env["vme.rent.mandate"].create({
            "landlord_id": cls.landlord.id, "company_id": cls.office.id, "date_start": date(2026, 1, 1),
            "fee_type": "percent", "fee_percent": 7.0, "partner_bank_id": cls.landlord_bank.id,
            "fee_tax_id": cls.office._rent_fee_tax().id,
        })
        cls.contract = cls.env["vme.rent.contract"].create({
            "company_id": cls.office.id, "landlord_id": cls.landlord.id,
            "tenant_ids": [Command.set(cls.tenant.ids)], "property_address": "Teststraat 1, 2000 Antwerpen",
            "date_signed": date(2025, 12, 1), "date_start": date(2026, 1, 1), "duration_years": 9,
            "rent": 800, "charges_amount": 100,
        })
        cls.contract.action_activate()
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.office.id), ("type", "=", "bank")], limit=1)
        cls.jan = cls.contract._create_rent_invoices(date(2026, 1, 1), post=True)
        cls.feb = cls.contract._create_rent_invoices(date(2026, 2, 1), post=True)
        cls._pay(cls.jan, 900, date(2026, 1, 3))
        cls._pay(cls.feb, 450, date(2026, 2, 3))
        cls.cost = cls._cost(121, date(2026, 2, 10))

    @classmethod
    def _pay(cls, invoice, amount, day):
        cls.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({"journal_id": cls.journal.id, "payment_date": day, "amount": amount}).action_create_payments()

    @classmethod
    def _cost(cls, amount, day, contract=None):
        contract = contract or cls.contract
        bill = cls.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": cls.plumber.id, "invoice_date": day,
            "rent_contract_id": contract.id, "ref": "Herstelling boiler",
            "invoice_line_ids": [Command.create({
                "name": "Herstelling boiler", "price_unit": amount, "tax_ids": [Command.clear()],
                "account_id": cls.office._rent_account().id,
                "analytic_distribution": {str(contract.analytic_account_id.id): 100},
            })],
        })
        bill.action_post()
        return bill

    def _remit(self, month, landlord=None):
        return self.env["vme.rent.remittance"].create({
            "landlord_id": (landlord or self.landlord).id, "company_id": self.office.id, "month": month})

    def _rent_account_balance(self, contract=None):
        contract = contract or self.contract
        lines = self.env["account.move.line"].search([
            ("company_id", "=", self.office.id), ("account_id", "=", self.office._rent_account().id),
            ("parent_state", "=", "posted"), ("analytic_distribution", "in", [contract.analytic_account_id.id]),
        ])
        return round(sum(lines.mapped("balance")), 2)

    def test_february_by_hand(self):
        remittance = self._remit(date(2026, 2, 1))
        by_type = {}
        for line in remittance.line_ids:
            by_type[line.line_type] = by_type.get(line.line_type, 0.0) + line.amount
        self.assertEqual(by_type, {"rent": 1200.0, "charges": 150.0, "cost": 121.0, "fee": 84.0})
        self.assertEqual(remittance.received, 1350.0)
        self.assertEqual(remittance.fee_tax, 17.64)
        self.assertEqual(remittance.fee_total, 101.64)
        self.assertEqual(remittance.balance, 1127.36)
        self.assertEqual(remittance.partner_bank_id, self.landlord_bank)

    def test_only_received_up_to_month(self):
        # In January only January's 900 is received; the plumber bill is from February.
        remittance = self._remit(date(2026, 1, 1))
        self.assertEqual(remittance.received, 900.0)
        self.assertEqual(remittance.costs, 0.0)
        self.assertEqual(remittance.fee_untaxed, 56.0)  # 7% x 800

    def test_confirm_books_fee_payout_and_offset(self):
        remittance = self._remit(date(2026, 2, 1))
        remittance.action_confirm()
        fee, payout = remittance.fee_invoice_id, remittance.payout_move_id
        self.assertEqual(fee.amount_untaxed, 84.0)
        self.assertEqual(fee.amount_tax, 17.64)
        self.assertEqual(fee.payment_state, "paid")  # offset against the payout
        self.assertEqual(payout.amount_total, 1229.0)  # 1350 - 121
        self.assertEqual(payout.amount_residual, 1127.36)
        self.assertEqual(payout.partner_bank_id, self.landlord_bank)
        self.assertEqual(remittance.payment_status, "to_approve")
        # What is left on 489100 for the landlord: the unpaid half of February.
        self.assertEqual(self._rent_account_balance(), -450.0)

        # A second remittance never takes the same amounts again, only the rest of February once paid.
        self._pay(self.feb, 450, date(2026, 3, 2))
        march = self._remit(date(2026, 3, 1))
        self.assertEqual([(l.line_type, l.amount) for l in march.line_ids],
                         [("rent", 400.0), ("charges", 50.0), ("fee", 28.0)])
        self.assertEqual(march.balance, 416.12)  # 450 - 28 - 5.88
        march.action_confirm()
        self.assertEqual(self._rent_account_balance(), 0.0)
        with self.assertRaises(UserError):
            march.unlink()

    def test_negative_balance_is_carried_over(self):
        landlord = self.env["res.partner"].create({"name": "Verhuurder Vast Ereloon"})
        tenant = self.env["res.partner"].create({"name": "Huurder Vast Ereloon"})
        self.env["vme.rent.mandate"].create({
            "landlord_id": landlord.id, "company_id": self.office.id, "date_start": date(2026, 1, 1),
            "fee_type": "fixed", "fee_amount": 50.0, "fee_tax_id": self.office._rent_fee_tax().id,
        })
        contract = self.env["vme.rent.contract"].create({
            "company_id": self.office.id, "landlord_id": landlord.id, "tenant_ids": [Command.set(tenant.ids)],
            "property_address": "Vaststraat 2, 2000 Antwerpen", "date_signed": date(2025, 12, 1),
            "date_start": date(2026, 1, 1), "duration_years": 9, "rent": 500,
        })
        contract.action_activate()
        january_invoice = contract._create_rent_invoices(date(2026, 1, 1), post=True)
        self._cost(200, date(2026, 1, 20), contract)
        # January: nothing received, 200 costs, 50 + 10.50 fee -> -260.50.
        january = self._remit(date(2026, 1, 1), landlord)
        self.assertEqual(january.balance, -260.5)
        with self.assertRaises(UserError):
            january.action_confirm()
        january.action_carry_over()
        # February: January's rent paid; the cost and two months of fixed fee: 500 - 200 - 121 = 179.
        self._pay(january_invoice, 500, date(2026, 2, 4))
        february = self._remit(date(2026, 2, 1), landlord)
        fee = february.line_ids.filtered(lambda l: l.line_type == "fee")
        self.assertEqual((fee.fee_months, fee.amount, fee.tax_amount), (2, 100.0, 21.0))
        self.assertEqual(february.balance, 179.0)
        february.action_confirm()
        self.assertEqual(february.payout_move_id.amount_residual, 179.0)
        self.assertEqual(self._rent_account_balance(contract), 0.0)

    def test_confirm_with_other_company_selected(self):
        # An employee working in another company still confirms the office's remittances.
        main = self.env.ref("base.main_company")
        # Odoo only posts an invoice of a person (not the superuser) with a trusted company account.
        (self.landlord_bank | self.office.rent_bank_id).with_user(self.admin).write({"allow_out_payment": True})
        remittance = self._remit(date(2026, 2, 1)).with_user(self.admin).with_context(allowed_company_ids=main.ids)
        remittance.action_confirm()
        remittance.action_approve_payout()
        self.assertEqual(remittance.fee_invoice_id.sudo().amount_tax, 17.64)
        self.assertEqual(remittance.payment_status, "to_pay")
        action = remittance.action_create_payment_batch()
        batch = self.env["vme.payment.batch"].browse(action["res_id"]).with_user(self.admin).with_context(
            allowed_company_ids=main.ids)
        batch.action_generate_file()
        self.assertEqual(batch.state, "generated")

    def test_payment_batch_respects_trusted_accounts(self):
        remittance = self._remit(date(2026, 2, 1))
        remittance.action_confirm()
        remittance.action_approve_payout()
        self.assertEqual(remittance.payment_status, "to_pay")
        # Odoo's own check: an untrusted account of the landlord stays out of the batch.
        action = remittance.action_create_payment_batch()
        batch = self.env["vme.payment.batch"].browse(action["res_id"])
        self.assertEqual(batch.company_id, self.office)
        self.assertFalse(batch.line_ids)
        self.assertIn("niet bevestigd", batch.proposal_note)
        batch.action_cancel()

        # A person with the right permissions trusts both accounts; the system user may not.
        (self.landlord_bank | self.office.rent_bank_id).with_user(self.admin).write({"allow_out_payment": True})
        action = remittance.action_create_payment_batch()
        batch = self.env["vme.payment.batch"].browse(action["res_id"])
        self.assertEqual(batch.line_ids.amount, 1127.36)
        self.assertEqual(batch.line_ids.partner_bank_id, self.landlord_bank)
        self.assertEqual(batch.state, "draft")
        self.assertEqual(remittance.payment_status, "in_batch")
        batch.action_generate_file()  # validated against the pain.001 schema of step 20
        self.assertEqual(batch.state, "generated")  # a person uploads it in the bank; nothing is sent
        self.assertIn(b"Rentmeester Doorstorting Test", __import__("base64").b64decode(batch.file_data))

    def test_batch_belongs_to_vme_or_office(self):
        with self.assertRaises(ValidationError):
            self.env["vme.payment.batch"].create({"batch_type": "transfer"})
        with self.assertRaises(ValidationError):
            self.env["vme.payment.batch"].create({"batch_type": "direct_debit", "rent_company_id": self.office.id})
        vme = self.env["vme.association"].create({"name": "Residentie Batchtest", "zip": "2000"})
        batch = self.env["vme.payment.batch"].create({"association_id": vme.id, "batch_type": "transfer"})
        self.assertEqual(batch.company_id, vme.company_id)

    def test_report_renders(self):
        remittance = self._remit(date(2026, 2, 1))
        remittance.action_confirm()
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_rentmeester.action_report_rent_remittance", remittance.ids)[0].decode()
        self.assertIn("Door te storten", html)
        self.assertIn("Herstelling boiler", html)

    def test_statement_and_invoices_in_the_landlords_language(self):
        """A French-speaking landlord gets the statement, its lines and the fee invoice in French."""
        self.env["res.lang"]._activate_lang("fr_BE")
        self.env["ir.module.module"].search([("name", "in", ["base", "account", "vme_rentmeester"])]) \
            ._update_translations(["fr_BE"])
        self.landlord.lang = "fr_BE"
        remittance = self._remit(date(2026, 2, 1))
        rent = remittance.line_ids.filtered(lambda l: l.line_type == "rent")[:1]
        fee = remittance.line_ids.filtered(lambda l: l.line_type == "fee")
        self.assertTrue(rent.description.startswith("Loyer "), rent.description)
        self.assertIn(" sur ", fee.description)
        remittance.action_confirm()
        self.assertNotIn("Ereloon", remittance.fee_invoice_id.invoice_line_ids.name)
        self.assertIn("février 2026", remittance.fee_invoice_id.ref)
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_rentmeester.action_report_rent_remittance", remittance.ids)[0].decode()
        for dutch in ("Door te storten", "Ontvangen van de huurders", "Afrekening huur", "februari"):
            self.assertNotIn(dutch, html)
        self.assertIn("À reverser", html)
        self.assertIn("février 2026", html)
