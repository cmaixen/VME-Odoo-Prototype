from datetime import date

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFinancialStatements(TransactionCase):
    """Two years of a small VME: provisions, costs with and without VAT, and works paid from the reserve.

    2025: working 1000, reserve 500 called and paid; maintenance 300.
    2026: working 1200, reserve 600 called, owner B leaves his working call unpaid (480);
    energy 1000 + 21% VAT, insurance 200, roof works 2000 paid from the reserve capital.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Balans"})
        cls.env.cr.precommit.run()
        cls.company = cls.vme.company_id
        banks = cls.env["res.partner.bank"].create([
            {"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id},
            {"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id},
        ])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(admin).allow_out_payment = True
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (600, 400))],
        })
        cls.owner_a, cls.owner_b = cls.env["res.partner"].create([{"name": "Eigenaar Balans A"}, {"name": "Eigenaar Balans B"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lots[0].id, "partner_id": cls.owner_a.id, "date_start": date(2015, 1, 1)},
            {"lot_id": lots[1].id, "partner_id": cls.owner_b.id, "date_start": date(2015, 1, 1)},
        ])
        journals = cls.vme._ensure_fund_bank_journals()[cls.vme]
        for year, working, reserve in ((2025, 1000, 500), (2026, 1200, 600)):
            cls.env["vme.budget"].create({
                "association_id": cls.vme.id, "year": year, "calls_per_year": "1",
                "working_capital_budget": working, "reserve_capital_contribution": reserve,
            })
            cls.env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(cls.vme.ids)], "year": year, "number": 1,
                "invoice_date": date(year, 1, 5), "date_due": date(year, 1, 28), "post_invoices": True,
            }).action_create_calls()
            calls = cls.env["account.move"].search([
                ("vme_provision_call_id.association_id", "=", cls.vme.id), ("invoice_date", "=", date(year, 1, 5))])
            paid = calls.filtered(lambda m, y=year: not (y == 2026 and m.partner_id == cls.owner_b and m.vme_fund == "working"))
            for fund in ("working", "reserve"):
                cls.env["account.payment.register"].with_company(cls.company).with_context(
                    active_model="account.move", active_ids=paid.filtered(lambda m, f=fund: m.vme_fund == f).ids,
                ).create({"journal_id": journals[fund].id, "payment_date": date(year, 2, 1), "group_payment": False}
                         ).action_create_payments()
        cls.supplier = cls.env["res.partner"].create({"name": "Leverancier Balans", "is_company": True})
        cls.works = cls.env["vme.works"].create({"association_id": cls.vme.id, "name": "Dakwerken", "financing": "reserve"})
        cls.works.state = "awarded"
        vat = cls.company.account_purchase_tax_id
        cls.bills = {
            "maintenance": cls._bill(date(2025, 6, 1), "611000", 300),
            "energy": cls._bill(date(2026, 3, 1), "612500", 1000, taxes=vat),
            "insurance": cls._bill(date(2026, 4, 1), "614000", 200),
            "roof": cls._bill(date(2026, 9, 1), "611000", 2000, works=cls.works),
        }

    @classmethod
    def _account(cls, code):
        return cls.env["account.account"].with_company(cls.company).search(
            [("company_ids", "in", cls.company.id), ("code", "=", code)], limit=1)

    @classmethod
    def _bill(cls, invoice_date, code, amount, taxes=None, works=None):
        bill = cls.env["account.move"].with_company(cls.company).create({
            "move_type": "in_invoice", "partner_id": cls.supplier.id, "invoice_date": invoice_date,
            "vme_works_id": works.id if works else False,
            "invoice_line_ids": [Command.create({
                "name": "Kost", "price_unit": amount, "account_id": cls._account(code).id, "vme_key_id": cls.key.id,
                "tax_ids": [Command.set(taxes.ids)] if taxes else [Command.clear()],
            })],
        })
        bill.action_post()
        return bill

    def _row(self, rows, code):
        return next((row for row in rows if row["code"] == code), {"amount": 0.0, "previous": 0.0})

    def test_balance_sheet_closes(self):
        data = self.vme._get_financial_statements(2026)
        self.assertTrue(data["balance_ok"])
        self.assertTrue(data["carry_ok"])
        self.assertFalse(data["unclassified"])
        self.assertEqual(data["assets_total"]["amount"], data["liabilities_total"]["amount"])
        self.assertEqual(data["assets_total"]["previous"], data["liabilities_total"]["previous"])

    def test_balance_sheet_headings(self):
        data = self.vme._get_financial_statements(2026)
        assets, liabilities = data["assets"], data["liabilities"]
        # Owner B's working call of 2026 is open: 400/1000 of 1200.
        self.assertEqual(self._row(assets, "4101")["amount"], 480)
        self.assertEqual(self._row(assets, "4100")["amount"], 0)
        # Payments without a bank statement still count on the bank account of their fund.
        self.assertEqual(self._row(assets, "550")["amount"], 1100)
        self.assertEqual(self._row(assets, "551")["amount"], 1000 + 720)
        # All bills are unpaid: 300 + 1210 + 200 + 2000.
        self.assertEqual(self._row(liabilities, "440")["amount"], 3710)
        self.assertEqual(self._row(liabilities, "440")["previous"], 300)
        # Reserve: 500 + 600 called, 2000 used for the roof.
        self.assertEqual(self._row(liabilities, "48901")["amount"], 500 + 600 - 2000)
        self.assertEqual(self._row(liabilities, "48901")["amount"], self.vme._get_fund_balance("reserve"))
        # Working: 1000 + 1200 called, costs 300 + 1210 + 200.
        self.assertEqual(self._row(liabilities, "48902")["amount"], 2200 - 1710)
        self.assertEqual(self._row(liabilities, "48902")["previous"], 1000 - 300)

    def test_vat_is_a_cost(self):
        energy = self.bills["energy"]
        self.assertEqual(energy.amount_total, 1210)
        self.assertEqual(set(energy.line_ids.filtered(lambda l: l.display_type == "tax").account_id.mapped("code")),
                         {"612500"})
        recoverable_vat = self.env["account.account"].with_company(self.company).search(
            [("company_ids", "in", self.company.id), ("code", "=like", "411%")])
        self.assertTrue(recoverable_vat)
        self.assertFalse(self.env["account.move.line"].search([
            ("company_id", "=", self.company.id), ("account_id", "in", recoverable_vat.ids)]))

    def test_income_statement(self):
        data = self.vme._get_financial_statements(2026)
        costs = data["costs"]
        self.assertEqual(self._row(costs, "612")["amount"], 1210)
        self.assertEqual(self._row(costs, "614")["amount"], 200)
        # Works bills go to 611, gross: the reserve capital pays them, they stay a cost of the year.
        self.assertEqual(self._row(costs, "611")["amount"], 2000)
        self.assertEqual(self._row(costs, "610")["previous"], 300)
        self.assertEqual(self._row(data["income"], "700")["amount"], 600)
        self.assertEqual(self._row(data["income"], "701")["amount"], 1200)
        self.assertEqual(data["result"]["amount"], 1800 - 3410)

    def test_costs_equal_the_bills_of_the_year(self):
        data = self.vme._get_financial_statements(2026)
        bills_2026 = sum(bill.amount_total for bill in self.bills.values() if bill.invoice_date.year == 2026)
        self.assertEqual(data["costs_total"]["amount"], bills_2026)
        lines = self.env["account.move.line"].search([
            ("company_id", "=", self.company.id), ("parent_state", "=", "posted"), ("account_id.account_type", "=", "expense"),
            ("date", ">=", date(2026, 1, 1)), ("date", "<=", date(2026, 12, 31)),
            ("move_id", "not in", self.bills["roof"].vme_reserve_move_id.ids)])
        self.assertEqual(data["costs_total"]["amount"], sum(lines.mapped("balance")))

    def test_carry_forward_per_fund(self):
        carry = self.vme._get_financial_statements(2026)["carry"]
        self.assertEqual(carry["reserve"]["opening"]["amount"], 500)
        self.assertEqual(carry["reserve"]["costs"]["amount"], 2000)
        self.assertEqual(carry["reserve"]["closing"]["amount"], -900)
        self.assertEqual(carry["working"]["opening"]["amount"], 700)
        self.assertEqual(carry["working"]["costs"]["amount"], 1410)
        self.assertEqual(carry["working"]["closing"]["amount"], 490)
        self.assertEqual(carry["total"]["closing"]["amount"], 500 + 700 + 1800 - 3410)

    def test_previous_year_column(self):
        data_2026 = self.vme._get_financial_statements(2026)
        data_2025 = self.vme._get_financial_statements(2025)
        for section in ("assets", "liabilities", "costs", "income"):
            for row in data_2025[section]:
                self.assertEqual(self._row(data_2026[section], row["code"])["previous"], row["amount"], row["name"])

    def test_report_renders(self):
        wizard = self.env["vme.financial.statements.wizard"].create({"association_id": self.vme.id, "year": 2026})
        self.assertIn("Over te dragen middelen reservekapitaal", wizard.preview_html)
        self.assertIn("de balans sluit", wizard.preview_html)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_financial_statements", wizard.ids)
        html = html.decode()
        self.assertIn("Balans en resultatenrekening 2026", html)
        self.assertIn("Leveringen aan de vereniging", html)

    def test_auditor_reads_only_his_vme(self):
        auditor_partner = self.env["res.partner"].create({"name": "Commissaris Balans", "email": "commissaris.balans@example.com"})
        mandate = self.env["vme.mandate"].create({
            "association_id": self.vme.id, "role": "auditor", "partner_id": auditor_partner.id,
            "date_start": date(2026, 3, 10)})
        mandate.action_grant_access()
        auditor = mandate.user_id
        other_vme = self.env["vme.association"].create({"name": "Residentie Andere Balans"})
        wizard = self.env["vme.financial.statements.wizard"].with_user(auditor).create(
            {"association_id": self.vme.id, "year": 2026})
        self.assertIn("Totaal activa", wizard.preview_html)
        self.assertTrue(self.vme.with_user(auditor)._get_financial_statements(2026)["balance_ok"])
        with self.assertRaises(AccessError):
            other_vme.with_user(auditor)._get_financial_statements(2026)
        menu = self.env.ref("vme_belgie.menu_vme_financial_statements")
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(auditor)._visible_menu_ids())
