from datetime import date

from freezegun import freeze_time

from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.vme_belgie.models.vme_budget_tracking import budget_elapsed_ratio

TODAY = date(2026, 11, 5)
# 1 July 2026 is day 182 of 365.
MID_YEAR = date(2026, 7, 1)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestBuildingCard(TransactionCase):
    """Residentie Kaart: two apartments (600/400) and a lift key; Residentie Buur is another VME."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        Vme = cls.env["vme.association"]
        cls.vme = Vme.create({"name": "Residentie Kaart", "assembly_period_month": "3", "assembly_period_day": 1})
        cls.other_vme = Vme.create({"name": "Residentie Buur"})
        cls.env.cr.precommit.run()
        banks = cls.env["res.partner.bank"].create([
            {"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id},
            {"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id},
        ])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(admin).allow_out_payment = True
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.general, cls.lift = cls.env["vme.key"].create([{
            "name": name, "association_id": cls.vme.id, "key_type": key_type, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (600, 400))],
        } for name, key_type in (("Algemeen", "general"), ("Lift", "elevator"))])
        cls.owner_a, cls.owner_b = cls.env["res.partner"].create([{"name": "Eigenaar Kaart A"}, {"name": "Eigenaar Kaart B"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lots[0].id, "partner_id": cls.owner_a.id, "date_start": date(2015, 1, 1)},
            {"lot_id": lots[1].id, "partner_id": cls.owner_b.id, "date_start": date(2015, 1, 1)},
        ])
        Account = cls.env["account.account"].with_company(cls.vme.company_id)
        cls.maintenance, cls.energy = (
            Account.search([("company_ids", "in", cls.vme.company_id.id), ("code", "=", code)], limit=1)
            for code in ("611000", "612500"))
        # Working capital 3650 (10 per day), reserve 30: below 5% of the 777 charged in 2025.
        cls.budget = cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": 2026, "calls_per_year": "1",
            "working_capital_budget": 3650, "reserve_capital_contribution": 30,
            "line_ids": [
                Command.create({"account_id": cls.maintenance.id, "key_id": cls.general.id,
                                "name": "Schoonmaak", "amount": 1825}),
                Command.create({"account_id": cls.energy.id, "key_id": cls.lift.id,
                                "name": "Stroom lift", "amount": 730}),
            ],
        })
        cls.supplier = cls.env["res.partner"].create({"name": "Lift Kaart BV", "is_company": True})
        cls.contract = cls.env["vme.contract"].create({
            "association_id": cls.vme.id, "name": "Onderhoud lift Kaart", "contract_type": "elevator",
            "partner_id": cls.supplier.id, "date_start": date(2024, 1, 1), "date_end": date(2026, 12, 31),
            "annual_amount": 1200,
        })

        # One provision call of 3650 working capital and 30 reserve capital; owner B pays nothing.
        cls.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(cls.vme.ids)], "year": 2026, "number": 1,
            "invoice_date": date(2026, 1, 5), "date_due": date(2026, 1, 31), "post_invoices": True,
        }).action_create_calls()
        journals = cls.vme._ensure_fund_bank_journals()[cls.vme]
        provisions = cls.env["account.move"].search([("vme_provision_call_id.association_id", "=", cls.vme.id)])
        for fund in ("working", "reserve"):
            cls.env["account.payment.register"].with_company(cls.vme.company_id).with_context(
                active_model="account.move",
                active_ids=provisions.filtered(lambda m, f=fund: m.vme_fund == f and m.partner_id == cls.owner_a).ids,
            ).create({"journal_id": journals[fund].id, "payment_date": date(2026, 2, 1)}).action_create_payments()

        cls.bills = (
            cls._bill(date(2026, 3, 1), cls.maintenance, cls.general, 300)
            | cls._bill(date(2026, 6, 1), cls.energy, cls.lift, 500)
            | cls._bill(date(2026, 6, 15), cls.maintenance, cls.general, 100, refund=True)
            | cls._bill(date(2026, 9, 1), cls.maintenance, cls.general, 400)
        )
        cls._bill(date(2026, 8, 1), cls.maintenance, cls.general, 999, post=False)  # draft: not a cost yet
        cls._bill(date(2025, 12, 31), cls.maintenance, cls.general, 777)  # last year

    @classmethod
    def _bill(cls, invoice_date, account, key, amount, refund=False, post=True, vme=None):
        vme = vme or cls.vme
        bill = cls.env["account.move"].with_company(vme.company_id).create({
            "move_type": "in_refund" if refund else "in_invoice",
            "partner_id": cls.supplier.id,
            "invoice_date": invoice_date,
            "invoice_line_ids": [Command.create({
                "name": "Kost", "quantity": 1, "price_unit": amount, "tax_ids": [Command.clear()],
                "account_id": account.id if account else False, "vme_key_id": key.id if key else False,
            })],
        })
        if post:
            bill.action_post()
        return bill

    def _row(self, rows, field, record):
        return next(row for row in rows if row[field] == record)

    # Budget follow-up

    def test_elapsed_ratio(self):
        self.assertEqual(budget_elapsed_ratio(2026, date(2025, 12, 31)), 0.0)
        self.assertEqual(budget_elapsed_ratio(2026, date(2026, 1, 1)), 1 / 365)
        self.assertEqual(budget_elapsed_ratio(2026, MID_YEAR), 182 / 365)
        self.assertEqual(budget_elapsed_ratio(2026, date(2026, 12, 31)), 1.0)
        self.assertEqual(budget_elapsed_ratio(2026, date(2027, 2, 1)), 1.0)
        self.assertEqual(budget_elapsed_ratio(2028, date(2028, 12, 30)), 365 / 366)  # leap year

    def test_budget_lines_and_unassigned_rest(self):
        self.assertEqual(self.budget.lines_total, 2555)
        self.assertEqual(self.budget.unassigned_amount, 1095)
        with self.assertRaises(ValidationError):
            self.budget.line_ids[0].amount = -1

    def test_tracking_per_account_and_key_up_to_date(self):
        tracking = self.vme._get_budget_tracking(2026, MID_YEAR)
        self.assertEqual(tracking["ratio"], 182 / 365)
        rows = tracking["rows"]
        # Maintenance under the general key: 300 minus a credit note of 100; the bill of
        # September, the draft and last year's bill do not count.
        cleaning = next(r for r in rows if r["account"] == self.maintenance and r["key"] == self.general)
        self.assertEqual((cleaning["budget"], cleaning["budget_to_date"], cleaning["actual"]), (1825, 910, 200))
        self.assertEqual(cleaning["difference"], 710)
        self.assertEqual(cleaning["status"], "ok")
        # 500 for the lift against 730 * 182 / 365 = 364: over budget.
        lift = next(r for r in rows if r["key"] == self.lift)
        self.assertEqual((lift["budget_to_date"], lift["actual"], lift["status"]), (364, 500, "over"))
        self.assertEqual(lift["difference"], -136)
        # The unassigned rest of the working capital budget is a row without account and key.
        rest = next(r for r in rows if not r["account"])
        self.assertEqual((rest["budget"], rest["budget_to_date"], rest["actual"]), (1095, 546, 0))
        total = tracking["total"]
        self.assertEqual((total["budget"], total["budget_to_date"], total["actual"]), (3650, 1820, 700))

        by_key = tracking["by_key"]
        self.assertEqual(self._row(by_key, "key", self.general)["actual"], 200)
        self.assertEqual(self._row(by_key, "key", self.lift)["actual"], 500)
        by_account = tracking["by_account"]
        self.assertEqual(self._row(by_account, "account", self.maintenance)["budget"], 1825)
        self.assertEqual(self._row(by_account, "account", self.energy)["actual"], 500)

        full_year = self.vme._get_budget_tracking(2026, date(2026, 12, 31))
        self.assertEqual(full_year["total"]["actual"], 1100)
        self.assertEqual(full_year["total"]["budget_to_date"], 3650)

    def test_cost_without_budget_and_line_without_key(self):
        # A cost on an account without budget line is flagged; a line without key covers every key.
        other = self.env["account.account"].with_company(self.vme.company_id).search(
            [("company_ids", "in", self.vme.company_id.id), ("code", "=", "614000")], limit=1)
        self._bill(date(2026, 5, 1), other, self.general, 250)
        rows = self.vme._get_budget_tracking(2026, MID_YEAR)["rows"]
        insurance = next(r for r in rows if r["account"] == other)
        self.assertEqual((insurance["budget"], insurance["status"]), (0, "no_budget"))

        self.budget.line_ids = [Command.create({"account_id": other.id, "amount": 365})]
        rows = self.vme._get_budget_tracking(2026, MID_YEAR)["rows"]
        insurance = [r for r in rows if r["account"] == other]
        self.assertEqual(len(insurance), 1)
        self.assertFalse(insurance[0]["key"])
        self.assertEqual((insurance[0]["budget_to_date"], insurance[0]["actual"]), (182, 250))

    def test_reserve_works_bills_not_in_working_budget(self):
        bill = self._bill(date(2026, 4, 1), self.maintenance, self.general, 5000)
        bill.vme_reserve_move_id = bill  # marks the bill as paid from the reserve capital
        tracking = self.vme._get_budget_tracking(2026, MID_YEAR)
        self.assertEqual(tracking["total"]["actual"], 700)

    def test_analysis_view_matches_tracking(self):
        self.env.flush_all()
        self.env.cr.execute("SELECT CURRENT_DATE")
        db_today = self.env.cr.fetchone()[0]
        tracking = self.vme._get_budget_tracking(2026, db_today)
        rows = self.env["vme.budget.analysis"].search([("association_id", "=", self.vme.id), ("year", "=", 2026)])
        self.assertAlmostEqual(sum(rows.mapped("budget_amount")), 3650)
        self.assertAlmostEqual(sum(rows.mapped("budget_to_date")), tracking["total"]["budget_to_date"], delta=0.02)
        # The view holds every posted bill of the year; the card stops at today.
        self.assertAlmostEqual(sum(rows.mapped("actual_amount")), 1100)
        lift = rows.filtered(lambda r: r.key_id == self.lift)
        self.assertAlmostEqual(sum(lift.mapped("difference")), sum(lift.mapped("budget_to_date")) - 500)

    # Capitals

    def test_capital_history(self):
        capital = self.vme._get_capital_history(TODAY)
        years = {entry["year"]: entry for entry in capital["years"]}
        self.assertEqual(sorted(years), [2025, 2026])
        self.assertEqual(years[2025]["working"]["closing"], -777)  # a cost before any provision
        self.assertEqual(years[2026]["working"]["opening"], -777)
        self.assertEqual(years[2026]["working"]["in"], 3650)
        self.assertEqual(years[2026]["working"]["out"], 1100)
        self.assertEqual(capital["working"], 3650 - 1100 - 777)
        self.assertEqual(capital["reserve"], 30)
        # Only owner A (600/1000) paid: that is what is on the bank accounts.
        self.assertEqual(capital["bank"]["working"], 2190)
        self.assertEqual(capital["bank"]["reserve"], 18)

        movements = self.env["vme.capital.movement"].search([("association_id", "=", self.vme.id)])
        self.assertAlmostEqual(sum(movements.filtered(lambda m: m.fund == "working").mapped("amount")), capital["working"])
        self.assertAlmostEqual(sum(movements.filtered(lambda m: m.fund == "reserve").mapped("amount")), 30)

    # Signals

    def _signals(self, today=TODAY):
        return {signal["code"] for signal in self.vme._get_signals(today)}

    def test_signal_reserve_below_minimum(self):
        # Art. 3.86 §3 BW: 30 is below 5% of the 777 charged in 2025 (38.85).
        self.assertIn("reserve", self._signals())
        self.assertTrue(self.vme.signal_reserve)
        self.assertIn("Reservefonds onder 5%", self.vme.signal_summary)
        self.assertIn(self.vme, self.env["vme.association"].search([("signal_reserve", "=", True)]))
        self.budget.reserve_exception_by_general_assembly = True
        self.assertNotIn("reserve", self._signals())
        self.assertNotIn(self.vme, self.env["vme.association"].search([("signal_reserve", "=", True)]))

    def test_signal_arrears_above_threshold(self):
        # Owner B owes 1460 working and 12 reserve capital, due since 31 January.
        self.assertEqual(self.vme._get_arrears_total(), 1472)
        self.assertIn("arrears", self._signals())
        self.vme.arrears_signal_threshold = 1472
        self.assertNotIn("arrears", self._signals())
        self.assertEqual(self.vme.arrears_amount, 1472)

    def _assembly(self, day, state="confirmed"):
        user = self.env.ref("base.user_admin")
        slot = self.env["vme.assembly.slot"].create({
            "date": day, "time_start": 19.0, "location_type": "online", "user_id": user.id})
        assembly = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": day.year, "slot_id": slot.id})
        assembly.state = state
        return assembly

    def test_signal_assembly_outside_period(self):
        # Art. 3.87 §2 BW: period 1 to 15 March; on 5 November no assembly was held.
        self.assertIn("assembly", self._signals())
        held = self._assembly(date(2026, 3, 10), state="held")
        self.assertNotIn("assembly", self._signals())
        held.state = "confirmed"
        held.slot_id = self.env["vme.assembly.slot"].create({
            "date": date(2026, 4, 2), "time_start": 19.0, "location_type": "online",
            "user_id": self.env.ref("base.user_admin").id})
        held.state = "held"
        message = next(s["message"] for s in self.vme._get_signals(TODAY) if s["code"] == "assembly")
        self.assertIn("buiten de periode", message)

    def test_signal_assembly_planned_outside_period(self):
        early = date(2026, 2, 1)
        self.assertNotIn("assembly", self._signals(early))  # the period is still to come
        self._assembly(date(2026, 4, 2))
        self.assertIn("assembly", self._signals(early))

    def test_signal_overdue_inspection(self):
        self.assertNotIn("inspection", self._signals())
        extinguishers = self.env["vme.installation"].create({
            "association_id": self.vme.id, "name": "Brandblussers Kaart", "installation_type": "fire_extinguishers",
        })
        self.env["vme.inspection"].create({"installation_id": extinguishers.id, "date": date(2025, 10, 1),
                                           "kind": "inspection", "result": "compliant"})
        self.assertIn("inspection", self._signals())
        self.assertEqual(self.vme.signal_count, len(self.vme._get_signals(TODAY)))
        self.assertIn("Vervallen keuring", self.vme.signal_summary)
        self.assertIn(self.vme, self.env["vme.association"].search([("signal_count", ">", 0)]))

    def test_portfolio_matches_card_figures(self):
        # The portfolio reads all VMEs at once; its figures equal those of the building card.
        vmes = self.vme | self.other_vme
        for day in (MID_YEAR, TODAY):
            figures = vmes._get_portfolio_figures(day)
            for vme in vmes:
                capital = vme._get_capital_history(day)
                tracking = vme._get_budget_tracking(day.year, day)["total"]
                self.assertEqual(figures[vme.id]["working"], capital["working"])
                self.assertEqual(figures[vme.id]["reserve"], capital["reserve"])
                self.assertEqual(figures[vme.id]["arrears"], vme._get_arrears_total())
                self.assertEqual(figures[vme.id]["budget_to_date"], tracking["budget_to_date"])
                self.assertEqual(figures[vme.id]["actual"], tracking["actual"])
                self.assertAlmostEqual(figures[vme.id]["usage"], tracking["usage"])
        self.assertTrue(figures[self.vme.id]["working"])

    def test_portfolio_query_count_does_not_grow_per_vme(self):
        # Scale (docs/dev/schaal.md): the portfolio costs the same number of queries for 1 or 7 VMEs.
        # Companies without a chart of accounts: loading five charts would only slow the test down.
        companies = self.env["res.company"].create([{"name": f"Residentie Extra {i}"} for i in range(5)])
        extra = self.env["vme.association"].create([
            {"name": company.name, "company_id": company.id} for company in companies])

        def count(vmes):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            vmes.mapped("signal_count")
            return self.env.cr.sql_log_count - before

        one = count(self.vme)
        self.assertLessEqual(count(self.vme | self.other_vme | extra), one + 5)

    # Cards

    def test_building_card_shows_everything(self):
        html = str(self.vme.building_card_html)
        for text in ("Kerngegevens", "Werk- en reservekapitaal", "Budget tegenover werkelijk", "611000",
                     "Lift", "Achterstallen", "Eigenaar Kaart B", "Onderhoud lift Kaart",
                     "Reservefonds onder 5%", "Te betalen facturen", "Open aanvragen"):
            self.assertIn(text, html)
        data = self.vme._get_building_card_data(TODAY)
        self.assertEqual(data["contracts"], self.contract)
        self.assertEqual(data["bills_to_pay"], self.bills.filtered(lambda b: b.move_type == "in_invoice")
                         | self.env["account.move"].search([("amount_total", "=", 777), ("company_id", "=", self.vme.company_id.id)]))
        if "vme.request" not in self.env:
            self.assertIsNone(data["requests"])  # step 19 not installed: room kept free on the card

    def test_supplier_card(self):
        html = str(self.supplier.vme_supplier_card_html)
        for text in ("Onderhoud lift Kaart", "Contracten", "Lopende werken", "Facturen", "Betaaltermijn", "Residentie Kaart"):
            self.assertIn(text, html)
        self.assertEqual(self.supplier.vme_supplier_contract_count, 1)
        self.assertEqual(self.supplier.vme_supplier_open_amount, 300 + 500 - 100 + 400 + 777)

    def test_supplier_list_does_not_query_per_supplier(self):
        suppliers = self.supplier | self.env["res.partner"].create(
            [{"name": f"Leverancier Lijst {i}", "supplier_rank": 1} for i in range(4)])

        def queries(partners):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            partners.read(["vme_supplier_contract_count", "vme_supplier_open_amount", "vme_supplier_vme_names"])
            return self.env.cr.sql_log_count - before

        self.assertEqual(queries(suppliers[:2]), queries(suppliers))
        self.assertEqual(suppliers[0].vme_supplier_open_amount, 300 + 500 - 100 + 400 + 777)
        self.assertEqual(suppliers[1:].mapped("vme_supplier_contract_count"), [0] * 4)

    def test_portal_finances(self):
        finances = self.vme._get_portal_finances(MID_YEAR)
        self.assertEqual(finances["reserve"], 30)
        self.assertEqual(finances["budget"]["total"]["actual"], 700)
        self.assertEqual({row["key"] for row in finances["budget"]["by_key"]}, {self.general, self.lift, self.env["vme.key"]})

    # The auditor sees the card of his VME and nothing else

    def test_auditor_sees_only_his_building_card(self):
        auditor_partner = self.env["res.partner"].create({"name": "Commissaris Kaart", "email": "commissaris.kaart@example.com"})
        mandate = self.env["vme.mandate"].create({
            "association_id": self.vme.id, "role": "auditor", "partner_id": auditor_partner.id,
            "date_start": date(2026, 3, 10)})
        mandate.action_grant_access()
        auditor = mandate.user_id
        Vme = self.env["vme.association"].with_user(auditor)
        self.assertEqual(Vme.search([]), self.vme)
        self.assertIn("Kerngegevens", str(self.vme.with_user(auditor).building_card_html))
        with self.assertRaises(AccessError):
            self.other_vme.with_user(auditor).building_card_html
        self.assertEqual(self.env["vme.budget.analysis"].with_user(auditor).search([]).association_id, self.vme)
        # The supplier card only covers his VME, and the portfolio menu is for staff.
        other_account = self.env["account.account"].with_company(self.other_vme.company_id).search(
            [("company_ids", "in", self.other_vme.company_id.id), ("code", "=", "611000")], limit=1)
        other_bill = self._bill(date(2026, 5, 1), other_account, None, 50, vme=self.other_vme)
        self.assertNotIn(other_bill.name, str(self.supplier.with_user(auditor).vme_supplier_card_html))
        self.assertIn(other_bill.name, str(self.supplier.vme_supplier_card_html))
        portfolio_menu = self.env.ref("vme_belgie.menu_vme_portfolio")
        self.assertNotIn(portfolio_menu.id, self.env["ir.ui.menu"].with_user(auditor)._visible_menu_ids())
        with self.assertRaises(AccessError):
            self.env["vme.budget.line"].with_user(auditor).create({
                "budget_id": self.budget.id, "account_id": self.maintenance.id, "amount": 1})
