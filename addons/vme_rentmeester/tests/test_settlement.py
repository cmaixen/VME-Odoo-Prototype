from datetime import date

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRentSettlement(TransactionCase):
    """Tenant of lot A1 (600/1000 general, 700/1000 lift) from 1 April 2026.

    Hand-checked: cleaning 1000 for the year -> A1 600 -> 275 of 365 days = 452.05 (100%);
    lift 500 for January-June -> A1 350 -> 91 of 181 days = 175.97 (100%);
    insurance 1000 -> A1 600 -> 452.05 at 0%. Tenant 628.02, provisions 9 x 50 = 450, balance 178.02.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.office = cls.env["res.company"].create({
            "name": "Rentmeesterkantoor Test", "country_id": cls.env.ref("base.be").id,
            "currency_id": cls.env.ref("base.EUR").id, "is_rent_management": True,
        })
        cls.env["account.chart.template"].try_loading("be_comp", cls.office, install_demo=False)
        cls.env.user.company_ids |= cls.office

        cls.vme = cls.env["vme.association"].create({"name": "Residentie Huur", "zip": "2000"})
        cls.env.cr.precommit.run()
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.a1 = lots[0]
        Key = cls.env["vme.key"]
        cls.general = Key.create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (600, 400))],
        })
        cls.lift = Key.create({
            "name": "Lift", "association_id": cls.vme.id, "key_type": "elevator", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (700, 300))],
        })
        cls.landlord, other, cls.tenant = cls.env["res.partner"].create([
            {"name": "Verhuurder Huur A1"}, {"name": "Eigenaar Huur A2"}, {"name": "Huurder Huur A1"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lots[0].id, "partner_id": cls.landlord.id, "date_start": date(2015, 1, 1)},
            {"lot_id": lots[1].id, "partner_id": other.id, "date_start": date(2015, 1, 1)},
        ])
        cleaner, lift_company, insurer = cls.env["res.partner"].create([
            {"name": "Schoonmaak Huurtest", "is_company": True},
            {"name": "Lift Huurtest", "is_company": True},
            {"name": "Verzekering Huurtest", "is_company": True},
        ])
        cls.env.ref("vme_rentmeester.charge_category_cleaning").partner_ids = [Command.link(cleaner.id)]
        company = cls.vme.company_id
        insurance_account = cls.env["account.account"].with_company(company).search(
            [("company_ids", "in", company.id), ("code", "=", "614000")], limit=1)
        bills = cls.env["account.move"]
        for partner, amount, key, start, end, account in (
            (cleaner, 1000, cls.general, date(2026, 1, 1), date(2026, 12, 31), False),
            (lift_company, 500, cls.lift, date(2026, 1, 1), date(2026, 6, 30), False),
            (insurer, 1000, cls.general, date(2026, 1, 1), date(2026, 12, 31), insurance_account),
        ):
            line = {"name": partner.name, "price_unit": amount, "tax_ids": [Command.clear()], "vme_key_id": key.id}
            if account:
                line["account_id"] = account.id
            bills |= cls.env["account.move"].with_company(company).create({
                "move_type": "in_invoice", "partner_id": partner.id, "invoice_date": date(2026, 6, 30),
                "vme_period_start": start, "vme_period_end": end,
                "invoice_line_ids": [Command.create(line)],
            })
        bills.with_company(company).action_post()

        cls.contract = cls.env["vme.rent.contract"].create({
            "company_id": cls.office.id, "lot_ids": [Command.set(cls.a1.ids)], "landlord_id": cls.landlord.id,
            "tenant_ids": [Command.set(cls.tenant.ids)], "date_signed": date(2026, 3, 15),
            "date_start": date(2026, 4, 1), "duration_years": 9, "rent": 700, "charges_amount": 50,
        })
        cls.contract.action_activate()
        for month in range(4, 13):
            cls.contract._create_rent_invoices(date(2026, month, 1), post=True)

    def _settle(self, year=2026):
        return self.env["vme.rent.settlement"].create({"contract_id": self.contract.id, "year": year})

    def test_contract_defaults(self):
        self.assertEqual(self.contract.region, "flanders")
        self.assertEqual(self.contract.association_id, self.vme)
        self.assertEqual(self.contract.date_end, date(2035, 3, 31))
        self.assertEqual(self.a1.current_tenant_ids, self.tenant)
        self.assertEqual(len(self.contract.charge_line_ids), self.env["vme.rent.charge.category"].search_count([]))
        self.assertEqual(self.contract.analytic_account_id.partner_id, self.landlord)

    def test_settlement_per_bill_and_rubric(self):
        settlement = self._settle()
        by_category = {line.category_id.name: line for line in settlement.line_ids}
        cleaning = by_category["Schoonmaak gemene delen"]
        lift = by_category["Lift: onderhoud en keuring"]
        insurance = by_category["Verzekering van het gebouw"]
        self.assertEqual((cleaning.owner_amount, cleaning.lease_days, cleaning.lease_amount, cleaning.tenant_amount),
                         (600.0, 275, 452.05, 452.05))
        self.assertEqual((lift.owner_amount, lift.lease_days, lift.lease_amount, lift.tenant_amount),
                         (350.0, 91, 175.97, 175.97))
        self.assertEqual((insurance.lease_amount, insurance.tenant_percent, insurance.tenant_amount), (452.05, 0.0, 0.0))
        self.assertEqual((settlement.tenant_total, settlement.provisions, settlement.balance), (628.02, 450.0, 178.02))
        self.assertEqual((settlement.date_from, settlement.date_to), (date(2026, 4, 1), date(2026, 12, 31)))

    def test_settlement_starts_from_annual_statement(self):
        """The landlord's costs in the settlement equal the landlord's costs in the annual statement."""
        statement = self.vme._get_annual_statement(2026, partners=self.landlord)["statements"][0]
        self.assertEqual(self._settle().owner_total, statement["cost_total"])
        self.assertEqual(statement["cost_total"], 1550.0)

    def test_rubric_percentage_per_contract(self):
        cleaning = self.contract.charge_line_ids.filtered(
            lambda l: l.category_id == self.env.ref("vme_rentmeester.charge_category_cleaning"))
        cleaning.tenant_percent = 40
        settlement = self._settle()
        self.assertEqual(settlement.tenant_total, 356.79)  # 180.82 + 175.97

    def test_settlement_invoice_is_a_draft(self):
        settlement = self._settle()
        settlement.action_create_invoice()
        invoice = settlement.invoice_id
        self.assertEqual((invoice.state, invoice.move_type, invoice.partner_id), ("draft", "out_invoice", self.tenant))
        self.assertEqual(invoice.amount_total, 178.02)
        self.assertEqual(invoice.company_id, self.office)

    def test_refund_when_provisions_exceed_costs(self):
        self.contract.charge_line_ids.tenant_percent = 0
        settlement = self._settle()
        self.assertEqual(settlement.balance, -450.0)
        settlement.action_create_invoice()
        self.assertEqual((settlement.invoice_id.move_type, settlement.invoice_id.amount_total), ("out_refund", 450.0))

    def test_forfait_is_not_settled(self):
        self.contract.charges_type = "forfait"
        with self.assertRaises(UserError):
            self._settle()

    def test_lease_ended_mid_year(self):
        self.contract.write({"date_moved_out": date(2026, 6, 30)})
        settlement = self._settle()
        cleaning = settlement.line_ids.filtered(lambda l: l.category_id.name == "Schoonmaak gemene delen")
        # 1 April - 30 June: 91 of 365 days of 600.
        self.assertEqual((cleaning.lease_days, cleaning.lease_amount), (91, 149.59))

    def test_rent_invoices(self):
        invoices = self.contract.invoice_ids
        self.assertEqual(len(invoices), 9)
        april = invoices.filtered(lambda m: m.rent_period == date(2026, 4, 1))
        self.assertEqual((april.amount_total, april.partner_id, april.company_id), (750.0, self.tenant, self.office))
        self.assertEqual(april.invoice_line_ids.account_id.with_company(self.office).code, "489100")
        self.assertEqual(april.invoice_line_ids[0].analytic_distribution,
                         {str(self.contract.analytic_account_id.id): 100})
        # Never twice for the same month, also for a user who has not selected the office's company.
        self.assertFalse(self.contract._create_rent_invoices(date(2026, 4, 1)))
        main = self.env.ref("base.main_company")
        other_company_user = self.contract.with_user(self.env.ref("base.user_admin")).with_company(main).with_context(
            allowed_company_ids=main.ids)
        self.assertFalse(other_company_user._create_rent_invoices(date(2026, 4, 1)))
        self.assertEqual(other_company_user.invoice_count, 9)

    def test_rent_invoice_pro_rata(self):
        contract = self.contract.copy({"date_start": date(2027, 1, 16), "date_signed": date(2027, 1, 2)})
        contract.action_activate()
        january = contract._create_rent_invoices(date(2027, 1, 1))
        # 16 of 31 days: 700 x 16/31 = 361.29 and 50 x 16/31 = 25.81.
        self.assertEqual(january.invoice_line_ids.mapped("price_unit"), [361.29, 25.81])
        self.assertEqual(january.state, "draft")

    def test_rent_invoice_after_indexation(self):
        index = self.env["vme.rent.index"]
        for month, value in ((date(2026, 2, 1), 100.0), (date(2027, 3, 1), 102.0)):
            record = index.search([("month", "=", month)]) or index.create({"month": month, "value": value})
            record.value = value
        draft = self.contract._create_rent_invoices(date(2027, 4, 1))
        self.assertEqual(draft.invoice_line_ids.filtered(lambda l: l.rent_line_type == "rent").price_unit, 700.0)
        # Confirming the indexation makes the draft invoices from the new rent on again.
        self.contract._create_indexation(date(2027, 4, 1), request_date=date(2027, 3, 10)).action_confirm()
        self.assertFalse(draft.exists())
        april = self.contract.invoice_ids.filtered(lambda m: m.rent_period == date(2027, 4, 1))
        self.assertEqual(april.invoice_line_ids.filtered(lambda l: l.rent_line_type == "rent").price_unit, 714.0)

    def test_notice_and_end(self):
        self.contract.write({"notice_date": date(2026, 11, 20), "notice_party": "tenant", "notice_months": 3})
        self.contract.action_register_notice()
        self.assertEqual((self.contract.state, self.contract.notice_end_date), ("notice", date(2027, 2, 28)))
        self.assertIn("Einde huur", self.contract.activity_ids.summary)
        # No invoice after the notice ends.
        self.assertFalse(self.contract._create_rent_invoices(date(2027, 3, 1)))
        self.contract.action_end()
        self.assertEqual((self.contract.state, self.contract.date_moved_out), ("ended", date(2027, 2, 28)))

    def test_reports_render(self):
        settlement = self._settle()
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_rentmeester.report_rent_settlement", settlement.ids)[0].decode()
        self.assertIn("Afrekening van de lasten 2026", html)
        self.assertIn("Schoonmaak gemene delen", html)
        index = self.env["vme.rent.index"]
        for month, value in ((date(2026, 2, 1), 100.0), (date(2027, 3, 1), 102.0)):
            record = index.search([("month", "=", month)]) or index.create({"month": month, "value": value})
            record.value = value
        indexation = self.contract._create_indexation(date(2027, 4, 1), request_date=date(2027, 3, 10))
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_rentmeester.report_indexation_letter", indexation.ids)[0].decode()
        self.assertIn("CONCEPT", html)
        self.assertIn("Indexering van de huurprijs", html)
