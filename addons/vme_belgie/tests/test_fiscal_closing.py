from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

YEAR = 2025


@tagged("post_install", "-at_install")
class TestFiscalClosing(TransactionCase):
    """Closing of 2025 for a small VME, checkable by hand.

    Lots A1 500, A2 300, A3 200 (general key) and a lift key on A1 only. A2 is sold on 1/7/2025
    from owner B to owner D. Two calls of 1.000 working and 200 reserve capital; owner C leaves the
    second working capital call unpaid. Costs: 1.600 general over the whole year and 600 lift.
    Settlement (costs - working provisions invoiced):
      A: 800 + 600 - 1.000 = +400   C: 320 - 400 = -80   B + D: 480 - 600 = -120   total +200
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Afsluiting"})
        cls.env.cr.precommit.run()
        cls.company = cls.vme.company_id
        banks = cls.env["res.partner.bank"].create([
            {"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id},
            {"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id},
        ])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(admin).allow_out_payment = True
        lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2", "A3")])
        cls.general = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (500, 300, 200))],
        })
        cls.lift = cls.env["vme.key"].create({
            "name": "Lift", "association_id": cls.vme.id, "key_type": "elevator", "total_shares": 1,
            "line_ids": [Command.create({"lot_id": lots[0].id, "shares": 1})],
        })
        Partner = cls.env["res.partner"]
        cls.owner_a, cls.owner_b, cls.owner_c, cls.owner_d = Partner.create([
            {"name": f"Eigenaar Afsluiting {x}"} for x in "ABCD"])
        cls.env["vme.ownership"].create([
            {"lot_id": lots[0].id, "partner_id": cls.owner_a.id, "date_start": date(2015, 1, 1)},
            {"lot_id": lots[1].id, "partner_id": cls.owner_b.id, "date_start": date(2015, 1, 1), "date_end": date(YEAR, 6, 30)},
            {"lot_id": lots[1].id, "partner_id": cls.owner_d.id, "date_start": date(YEAR, 7, 1)},
            {"lot_id": lots[2].id, "partner_id": cls.owner_c.id, "date_start": date(2015, 1, 1)},
        ])
        cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": YEAR, "calls_per_year": "2",
            "working_capital_budget": 2000, "reserve_capital_contribution": 400,
        })
        for number, call_date in ((1, date(YEAR, 1, 5)), (2, date(YEAR, 7, 5))):
            cls.env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(cls.vme.ids)], "year": YEAR, "number": number,
                "invoice_date": call_date, "date_due": call_date.replace(day=28), "post_invoices": True,
            }).action_create_calls()
        cls.journals = cls.vme._ensure_fund_bank_journals()[cls.vme]
        provisions = cls.env["account.move"].search([("vme_provision_call_id.association_id", "=", cls.vme.id)])
        paid = provisions.filtered(lambda m: not (m.partner_id == cls.owner_c and m.vme_fund == "working"
                                                  and m.vme_provision_call_id.number == 2))
        for fund in ("working", "reserve"):
            cls.env["account.payment.register"].with_company(cls.company).with_context(
                active_model="account.move", active_ids=paid.filtered(lambda m, f=fund: m.vme_fund == f).ids,
            ).create({"journal_id": cls.journals[fund].id, "payment_date": date(YEAR, 8, 1), "group_payment": False}
                     ).action_create_payments()
        cls.supplier = Partner.create({"name": "Leverancier Afsluiting", "is_company": True})
        cls._bill(1600, cls.general, date(YEAR, 1, 1), date(YEAR, 12, 31))
        cls._bill(600, cls.lift, date(YEAR, 3, 1), date(YEAR, 3, 1))
        cls.closing = cls.vme._get_fiscal_closing(YEAR)

    @classmethod
    def _bill(cls, price, key, period_start, period_end, post=True):
        bill = cls.env["account.move"].with_company(cls.company).create({
            "move_type": "in_invoice", "partner_id": cls.supplier.id, "invoice_date": period_end,
            "vme_period_start": period_start, "vme_period_end": period_end,
            "invoice_line_ids": [Command.create({
                "name": "Onderhoud", "price_unit": price, "tax_ids": [Command.clear()],
                "vme_key_id": key.id if key else False,
            })],
        })
        if post:
            bill.action_post()
        return bill

    def _by_partner(self):
        moves = self.closing.settlement_move_ids
        return {partner: sum(m.amount_total if m.move_type == "out_invoice" else -m.amount_total
                             for m in moves.filtered(lambda m, p=partner: m.partner_id == p))
                for partner in moves.partner_id}

    def _reserve_balance(self):
        return self.vme._get_fund_balance("reserve")

    def test_settlement_per_owner(self):
        self.assertTrue(self.closing.can_prepare)
        self.closing.action_prepare()
        self.assertEqual(self.closing.state, "prepared")
        moves = self.closing.settlement_move_ids
        self.assertTrue(all(m.state == "draft" for m in moves))
        amounts = self._by_partner()
        self.assertEqual(amounts[self.owner_a], 400.0)
        self.assertEqual(amounts[self.owner_c], -80.0)
        move_a = moves.filtered(lambda m: m.partner_id == self.owner_a)
        move_c = moves.filtered(lambda m: m.partner_id == self.owner_c)
        self.assertEqual((move_a.move_type, move_c.move_type), ("out_invoice", "out_refund"))
        for move in moves:
            self.assertEqual(move.vme_fund, "working")
            self.assertEqual(move.invoice_date, date(YEAR, 12, 31))
            self.assertEqual(move.invoice_line_ids.account_id.with_company(self.company).code, "100100")
            self.assertFalse(move.invoice_line_ids.tax_ids)
        # The extra payment goes to the working capital account; a refund to the owner's own account.
        self.assertEqual(move_a.partner_bank_id, self.vme.working_capital_bank_id)
        self.assertNotEqual(move_c.partner_bank_id, self.vme.working_capital_bank_id)
        self.assertIn("A1", move_a.invoice_line_ids.name)

    def test_total_is_costs_minus_provisions(self):
        self.closing.action_prepare()
        statement = self.vme._get_annual_statement(YEAR)
        costs = sum(st["cost_total"] for st in statement["statements"])
        invoiced = sum(st["working"]["invoiced"] for st in statement["statements"])
        self.assertEqual((costs, invoiced), (2200.0, 2000.0))
        self.assertEqual(self.closing.settlement_total, 200.0)
        # The unpaid provision of C stays open: open provision + settlement = balance of the statement.
        c = next(st for st in statement["statements"] if st["partner"] == self.owner_c)
        self.assertEqual(c["working"]["open"] + self._by_partner()[self.owner_c], c["balance"])
        self.assertEqual(c["balance"], 120.0)

    def test_reserve_capital_is_not_settled(self):
        before = self._reserve_balance()
        self.assertEqual(before, 400.0)
        self.closing.action_prepare()
        self.closing.action_post_settlements()
        self.assertEqual(self._reserve_balance(), before)
        lines = self.closing.settlement_move_ids.line_ids
        self.assertFalse(lines.filtered(lambda l: l.account_id.with_company(self.company).code == "100200"))
        # The seller B gets back working capital only, never his share in the reserve.
        self.assertEqual(self.closing.settlement_move_ids.filtered(
            lambda m: m.partner_id == self.owner_b).invoice_line_ids.account_id.with_company(self.company).code, "100100")

    def test_sale_during_the_year(self):
        self.closing.action_prepare()
        amounts = self._by_partner()
        statement = {st["partner"]: st for st in self.vme._get_annual_statement(YEAR)["statements"]}
        # Seller and buyer each get a document for their own period; both paid one call of 300.
        for owner in (self.owner_b, self.owner_d):
            self.assertIn(owner, amounts)
            self.assertEqual(statement[owner]["working"]["invoiced"], 300.0)
            self.assertAlmostEqual(amounts[owner], statement[owner]["cost_total"] - 300.0, places=2)
        self.assertAlmostEqual(amounts[self.owner_b] + amounts[self.owner_d], -120.0, places=2)
        # The buyer owned A2 for more days (184 of 365) and so bears more of the costs.
        self.assertGreater(statement[self.owner_d]["cost_total"], statement[self.owner_b]["cost_total"])

    def test_undistributed_bill_blocks_preparing(self):
        self._bill(50, False, date(YEAR, 9, 1), date(YEAR, 9, 1))
        self.assertFalse(self.closing.can_prepare)
        with self.assertRaises(UserError):
            self.closing.action_prepare()

    def test_draft_bill_blocks_preparing(self):
        self._bill(50, self.general, date(YEAR, 9, 1), date(YEAR, 9, 1), post=False)
        checks = {c["code"]: c for c in self.closing._get_checks()}
        self.assertFalse(checks["draft_bills"]["ok"])
        with self.assertRaises(UserError):
            self.closing.action_prepare()

    def test_drafts_block_closing(self):
        self.closing.action_prepare()
        self.assertFalse(self.closing.can_close)
        with self.assertRaises(UserError):
            self.closing.action_close()

    def test_unreconciled_bank_line_blocks_closing(self):
        self.closing.action_prepare()
        self.closing.action_post_settlements()
        self.assertTrue(self.closing.can_close)
        self.env["account.bank.statement.line"].with_company(self.company).create({
            "journal_id": self.journals["working"].id, "date": date(YEAR, 12, 20),
            "payment_ref": "Onbekende storting", "amount": 25.0,
        })
        self.closing.invalidate_recordset(["can_close", "check_html"])
        self.assertFalse(self.closing.can_close)
        with self.assertRaises(UserError):
            self.closing.action_close()

    def test_lock_and_reopen(self):
        self.closing.action_prepare()
        self.closing.action_post_settlements()
        self.closing.action_close()
        self.assertEqual(self.closing.state, "closed")
        self.assertEqual(self.company.fiscalyear_lock_date, date(YEAR, 12, 31))
        self.assertEqual(self.closing.closed_by_id, self.env.user)
        # The snapshot of the carry-forward: after the settlement the working capital result is 0.
        self.assertEqual(self.closing.working_result, 0.0)
        self.assertEqual(self.closing.reserve_result, 400.0)
        self.assertEqual(self.closing.reserve_capital, 400.0)
        # Nothing in the closed year can change: a posted document cannot go back to draft, and a
        # new entry dated in the closed year is moved into the first open period (Odoo 19 soft lock).
        with self.assertRaises(UserError):
            self.closing.settlement_move_ids[0].button_draft()
        entry = self.env["account.move"].with_company(self.company).create({
            "move_type": "entry", "date": date(YEAR, 11, 1), "line_ids": [
                Command.create({"account_id": self.closing.settlement_move_ids[0].invoice_line_ids.account_id.id,
                                "debit": 10.0}),
                Command.create({"account_id": self.journals["working"].default_account_id.id, "credit": 10.0}),
            ]})
        entry.action_post()
        self.assertGreater(entry.date, date(YEAR, 12, 31))
        # A late bill of the closed year gets its accounting date in the next year (Odoo's lock date),
        # and so counts in the statement of that year: the closed year does not change.
        total_before = self.vme._get_annual_statement(YEAR)["bills_total"]
        late = self._bill(10, self.general, date(YEAR, 11, 1), date(YEAR, 11, 1))
        self.assertGreater(late.date, date(YEAR, 12, 31))
        self.assertEqual(self.vme._get_annual_statement(YEAR)["bills_total"], total_before)
        self.assertEqual(self.vme._get_annual_statement(YEAR + 1)["bills_total"], 10.0)
        self.closing.action_reopen()
        self.assertEqual(self.closing.state, "prepared")
        self.assertFalse(self.company.fiscalyear_lock_date)
        self.closing.settlement_move_ids[0].button_draft()

    def test_prepare_again_replaces_only_drafts(self):
        self.closing.action_prepare()
        posted = self.closing.settlement_move_ids.filtered(lambda m: m.partner_id == self.owner_a)
        posted.action_post()
        self._bill(100, self.general, date(YEAR, 10, 1), date(YEAR, 10, 1))
        self.closing.action_prepare()
        self.assertEqual(posted.state, "posted")
        self.assertIn(posted, self.closing.settlement_move_ids)
        extra = self.closing.settlement_move_ids.filtered(lambda m: m.partner_id == self.owner_a) - posted
        # A's share in the new bill (500/1000 of 100) comes as an extra document.
        self.assertEqual((extra.move_type, extra.amount_total, extra.state), ("out_invoice", 50.0, "draft"))
        self.assertEqual(self._by_partner()[self.owner_a], 450.0)
        self.assertEqual(self.closing.settlement_total, 300.0)

    def test_only_a_manager_closes(self):
        main = self.env.ref("base.main_company")
        staff = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Medewerker Afsluiting", "login": "medewerker.afsluiting@example.com",
            "group_ids": [Command.set([self.env.ref("account.group_account_invoice").id])],
            "company_id": main.id, "company_ids": [Command.set((main | self.company).ids)],
        })
        # An employee prepares and posts, also with another company selected in the switcher.
        closing = self.env["vme.fiscal.closing"].with_user(staff).with_company(main).create(
            {"association_id": self.vme.id, "year": YEAR - 1})
        self.assertEqual(closing.company_id, self.company)
        self.closing.with_user(staff).with_company(main).action_prepare()
        self.closing.with_user(staff).with_company(main).action_post_settlements()
        with self.assertRaises(AccessError):
            self.closing.with_user(staff).action_close()
        self.assertFalse(self.company.fiscalyear_lock_date)

    def test_open_from_vme(self):
        action = self.vme.action_open_fiscal_closing(YEAR)
        self.assertEqual(action["res_id"], self.closing.id)
        # Without a year: the closing in progress.
        self.assertEqual(self.vme.action_open_fiscal_closing()["res_id"], self.closing.id)
        self.assertIn("Resultaat van 2025", self.closing.summary_html)
        self.assertIn("Over te dragen naar 1/1/2026", self.closing.summary_html)


# The full demo year takes minutes: only with --test-tags vme_slow.
@tagged("post_install", "-at_install", "-standard", "vme_slow")
class TestFiscalClosingDemo(TransactionCase):
    """Settle the demo year 2026 of the three demo VMEs and close Residentie Linde."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.env["vme.association"].with_user(admin)._load_demo_data()
        cls.env.cr.precommit.run()
        cls.env.flush_all()
        cls.env.cr.execute("ANALYZE account_move, account_move_line, account_partial_reconcile, res_partner")
        cls.env["vme.association"].with_user(admin)._load_demo_history()
        # Again after the history: with the statistics of the demo data alone, Odoo's query for the
        # reconciled payments of the posted settlement (_compute_reconciled_payment_ids) ran for hours.
        cls.env.flush_all()
        cls.env.cr.execute("ANALYZE account_move, account_move_line, account_partial_reconcile, account_payment, "
                           "account_account, res_partner")
        cls.vmes = cls.env["vme.association"].search([("name", "in", ("Residentie Linde", "Hof ter Beuken", "Kaaihuis"))])

    def test_settle_demo_year(self):
        self.assertEqual(len(self.vmes), 3)
        for vme in self.vmes:
            closing = vme._get_fiscal_closing(2026)
            failed = [c["message"] for c in closing._get_checks() if not c["ok"] and c["blocking"] == "prepare"]
            self.assertFalse(failed, vme.name)
            closing.action_prepare()
            statement = vme._get_annual_statement(2026)
            currency = statement["currency"]
            costs = sum(st["cost_total"] for st in statement["statements"])
            invoiced = sum(st["working"]["invoiced"] for st in statement["statements"])
            self.assertAlmostEqual(closing.settlement_total, currency.round(costs - invoiced), places=2, msg=vme.name)
            closing.action_post_settlements()
            # Per owner: the settlement plus the provisions still open is the balance of the statement.
            settled = {}
            for move in closing.settlement_move_ids:
                sign = 1 if move.move_type == "out_invoice" else -1
                settled[move.partner_id] = settled.get(move.partner_id, 0.0) + sign * move.amount_total
            for st in statement["statements"]:
                self.assertAlmostEqual(settled.get(st["partner"], 0.0) + st["working"]["open"], st["balance"],
                                       places=2, msg=f"{vme.name} {st['partner'].name}")
            # The statement itself does not change by the settlement.
            self.assertAlmostEqual(vme._get_annual_statement(2026)["bills_total"], statement["bills_total"], places=2)

    def test_close_linde(self):
        linde = self.vmes.filtered(lambda v: v.name == "Residentie Linde")
        closing = linde._get_fiscal_closing(2026)
        closing.action_prepare()
        closing.action_post_settlements()
        blocking = [c for c in closing._get_checks() if not c["ok"] and c["blocking"]]
        if blocking:
            # Only the demo bank statement lines that the demo leaves to match by hand may block.
            self.assertEqual({c["code"] for c in blocking}, {"bank"})
            self.env["account.bank.statement.line"].search(
                [("company_id", "=", linde.company_id.id), ("is_reconciled", "=", False)]).unlink()
            closing.invalidate_recordset(["can_close"])
        closing.action_close()
        self.assertEqual(linde.company_id.fiscalyear_lock_date, date(2026, 12, 31))
        self.assertTrue(linde.company_id.currency_id.is_zero(closing.working_result), closing.working_result)
