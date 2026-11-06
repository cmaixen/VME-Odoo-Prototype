from datetime import date, timedelta

from odoo import fields
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAnnualStatementSmall(TransactionCase):
    """Hand-checkable case: one owner of 600/1000 and one of 400/1000."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Afrekening"})
        cls.env.cr.precommit.run()
        Bank = cls.env["res.partner.bank"]
        banks = Bank.create([
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
        cls.owner_a, cls.owner_b = cls.env["res.partner"].create([{"name": "Eigenaar Afr A"}, {"name": "Eigenaar Afr B"}])
        cls.env["vme.ownership"].create([
            {"lot_id": lots[0].id, "partner_id": cls.owner_a.id, "date_start": date(2015, 1, 1)},
            {"lot_id": lots[1].id, "partner_id": cls.owner_b.id, "date_start": date(2015, 1, 1)},
        ])
        cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": 2026, "calls_per_year": "2",
            "working_capital_budget": 1200, "reserve_capital_contribution": 200,
        })
        # Two calls of 600 working capital (A: 360, B: 240) and 100 reserve capital.
        for number, call_date in ((1, date(2026, 1, 5)), (2, date(2026, 7, 5))):
            cls.env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(cls.vme.ids)], "year": 2026, "number": number,
                "invoice_date": call_date, "date_due": call_date.replace(day=28), "post_invoices": True,
            }).action_create_calls()
        journals = cls.vme._ensure_fund_bank_journals()[cls.vme]
        provisions = cls.env["account.move"].search([("vme_provision_call_id.association_id", "=", cls.vme.id)])
        # Owner B leaves the second working capital call unpaid.
        paid = provisions.filtered(lambda m: not (m.partner_id == cls.owner_b and m.vme_fund == "working"
                                                  and m.vme_provision_call_id.number == 2))
        for fund in ("working", "reserve"):
            cls.env["account.payment.register"].with_company(cls.vme.company_id).with_context(
                active_model="account.move", active_ids=paid.filtered(lambda m, f=fund: m.vme_fund == f).ids,
            ).create({"journal_id": journals[fund].id, "payment_date": date(2026, 8, 1), "group_payment": False}
                     ).action_create_payments()
        supplier = cls.env["res.partner"].create({"name": "Leverancier Afrekening", "is_company": True})
        cls.bill = cls.env["account.move"].with_company(cls.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": date(2026, 6, 1),
            "invoice_line_ids": [Command.create({
                "name": "Onderhoud", "price_unit": 1000, "tax_ids": [Command.clear()], "vme_key_id": cls.key.id,
            })],
        })
        cls.bill.action_post()

    def _statement(self, partner):
        data = self.vme._get_annual_statement(2026)
        return data, next(st for st in data["statements"] if st["partner"] == partner)

    def test_balances(self):
        data, a = self._statement(self.owner_a)
        _data, b = self._statement(self.owner_b)
        self.assertTrue(data["is_complete"])
        self.assertEqual(data["allocated_total"], 1000.0)
        # A: costs 600, paid 2 x 360 = 720, balance -120 (refund).
        self.assertEqual((a["cost_total"], a["working"]["paid"], a["working"]["open"], a["balance"]), (600.0, 720.0, 0.0, -120.0))
        # B: costs 400, paid 240 (second call open), balance +160 to pay; 240 still open.
        self.assertEqual((b["cost_total"], b["working"]["paid"], b["working"]["open"], b["balance"]), (400.0, 240.0, 240.0, 160.0))

    def test_reserve_capital_is_not_settled(self):
        _data, a = self._statement(self.owner_a)
        self.assertEqual((a["reserve"]["invoiced"], a["reserve"]["paid"]), (120.0, 120.0))
        self.assertEqual(a["balance"], a["cost_total"] - a["working"]["paid"])

    def test_next_year_call_sent_this_year_is_not_counted(self):
        # A provision call for 2027 dated in December 2026 belongs to the 2027 statement.
        self.env["vme.budget"].create({
            "association_id": self.vme.id, "year": 2027, "calls_per_year": "2",
            "working_capital_budget": 1200, "reserve_capital_contribution": 200,
        })
        self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(self.vme.ids)], "year": 2027, "number": 1,
            "invoice_date": date(2026, 12, 15), "date_due": date(2027, 1, 15), "post_invoices": True,
        }).action_create_calls()
        _data, a = self._statement(self.owner_a)
        self.assertEqual(a["working"]["invoiced"], 720.0)  # still only the two 2026 calls
        statement_2027 = self.vme._get_annual_statement(2027)
        a_2027 = next(st for st in statement_2027["statements"] if st["partner"] == self.owner_a)
        self.assertEqual(a_2027["working"]["invoiced"], 360.0)

    def test_check_reports_undistributed_bill(self):
        supplier = self.env["res.partner"].create({"name": "Zonder sleutel", "is_company": True})
        bill = self.env["account.move"].with_company(self.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": date(2026, 9, 1),
            "invoice_line_ids": [Command.create({"name": "Herstelling", "price_unit": 50, "tax_ids": [Command.clear()]})],
        })
        bill.action_post()  # no key, so not distributed
        data = self.vme._get_annual_statement(2026)
        self.assertFalse(data["is_complete"])
        self.assertIn(bill, data["undistributed_bills"])

    def test_report_renders(self):
        wizard = self.env["vme.annual.statement.wizard"].create({"association_id": self.vme.id, "year": 2026})
        self.assertIn("Eigenaar Afr B", wizard.preview_html)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_annual_statement", wizard.ids)
        html = html.decode()
        self.assertIn("Jaarafrekening 2026", html)
        self.assertIn("Eigenaar Afr A", html)
        self.assertIn("bij te betalen", html)


# A full demo year (~300 payments in one test transaction) takes over 10 minutes in Odoo's
# test environment, so it is left out of the standard run: use --test-tags vme_slow.
@tagged("post_install", "-at_install", "-standard", "vme_slow")
class TestAnnualStatementDemo(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.env["vme.association"].with_user(admin)._load_demo_data()
        cls.env.cr.precommit.run()
        # The test database is empty outside a test, so its planner statistics say "0 rows";
        # without fresh statistics the ~300 demo payments take minutes instead of seconds.
        cls.env.flush_all()
        cls.env.cr.execute("ANALYZE account_move, account_move_line, account_partial_reconcile, res_partner")
        cls.env["vme.association"].with_user(admin)._load_demo_history()
        cls.linde = cls.env["vme.association"].search([("name", "=", "Residentie Linde")])
        cls.data = cls.linde._get_annual_statement(2026)
        cls.by_name = {st["partner"].name: st for st in cls.data["statements"]}

    def test_all_costs_distributed(self):
        bills = self.env["account.move"].search([
            ("company_id", "=", self.linde.company_id.id), ("move_type", "=", "in_invoice"), ("state", "=", "posted"),
        ])
        self.assertEqual(len(bills), 7)  # 2 lift, 3 cleaning, 1 insurance, 1 electricity (UBL)
        self.assertTrue(self.data["is_complete"])
        self.assertAlmostEqual(self.data["allocated_total"], sum(bills.mapped("amount_total")), places=2)
        self.assertAlmostEqual(sum(st["cost_total"] for st in self.data["statements"]), self.data["bills_total"], places=2)

    def test_sale_of_a5(self):
        seller = self.by_name["Eigenaar Linde A5"]
        buyer = self.by_name["Nieuwe eigenaar Linde A5"]
        # Provisions: calls 1-2 to the seller, calls 3-4 to the buyer, each 101/1000 of 6000.
        self.assertEqual(seller["working"]["invoiced"], 2 * 606.0)
        self.assertEqual(buyer["working"]["invoiced"], 2 * 606.0)
        # Year-long insurance: the seller pays 181 days, the buyer 184 days of the same share.
        insurance_seller = next(b for b in seller["bills"] if b["supplier"].startswith("Verzekeringen"))
        insurance_buyer = next(b for b in buyer["bills"] if b["supplier"].startswith("Verzekeringen"))
        self.assertEqual(insurance_seller["partial_days"], 181)
        self.assertAlmostEqual(insurance_seller["amount"] + insurance_buyer["amount"], round(4200 * 101 / 1000, 2), places=2)

    def test_unpaid_call_of_a3(self):
        a3 = self.by_name["Eigenaar Linde A3"]
        self.assertEqual(len(a3["working"]["open_invoices"]), 1)
        self.assertEqual(a3["working"]["open"], a3["working"]["invoiced"] / 4)
        self.assertEqual(a3["balance"], round(a3["cost_total"] - a3["working"]["paid"], 2))

    def test_hof_ter_beuken_settles_on_consumption(self):
        # Gas is split on consumption: large consumers pay extra, small consumers get money back.
        beuken = self.env["vme.association"].search([("name", "=", "Hof ter Beuken")])
        data = beuken._get_annual_statement(2026)
        self.assertTrue(data["is_complete"])
        paid_all = [st for st in data["statements"] if st["working"]["open"] == 0]
        self.assertTrue(any(st["balance"] > 0 for st in paid_all))
        self.assertTrue(any(st["balance"] < 0 for st in paid_all))

    def test_demo_bank_statements(self):
        """The fictitious CODA/CAMT files (stap 12) still match the invoice numbers of the demo history."""
        self.env["vme.association"].with_user(self.env.ref("base.user_admin"))._load_demo_bank_statements()
        lines = self.env["account.bank.statement.line"].search([("vme_association_id", "!=", False)])
        outcome = sorted((line.vme_association_id.name, line.vme_bank_fund, float(line.amount), line.vme_match_state,
                          line.vme_exception or "", line.vme_days_late) for line in lines)
        self.assertEqual(outcome, sorted([
            ("Residentie Linde", "working", -1815.0, "auto", "", 0),
            ("Residentie Linde", "working", -1815.0, "auto", "", 0),
            ("Residentie Linde", "working", 432.0, "auto", "", 1),
            ("Residentie Linde", "reserve", 43.2, "suggested", "no_reference", 0),
            ("Hof ter Beuken", "working", 840.0, "suggested", "wrong_reference", 0),
            ("Hof ter Beuken", "working", -14520.0, "auto", "", 0),
            ("Hof ter Beuken", "working", 200.0, "auto", "underpaid", 0),
            ("Hof ter Beuken", "working", 15.75, "suggested", "wrong_fund", 0),
            ("Hof ter Beuken", "reserve", 15.75, "auto", "", 0),
            ("Kaaihuis", "working", -726.0, "auto", "", 0),
            ("Kaaihuis", "working", 423.0, "todo", "already_paid", 0),
            ("Kaaihuis", "reserve", 250.0, "todo", "no_reference", 0),
        ]))

    def test_demo_payments(self):
        """Stap 20 on the demo: approvals, a transfer batch per VME, a direct debit and the demo statement."""
        admin = self.env.ref("base.user_admin")
        VME = self.env["vme.association"].with_user(admin)
        VME._load_demo_bank_statements()
        VME._load_demo_payments()
        bills = self.env["account.move"].search([("vme_approval_state", "=", "first_approved")])
        self.assertTrue(bills)
        bills.with_user(admin).action_vme_approve()
        Batch = self.env["vme.payment.batch"].with_user(admin)
        tomorrow = fields.Date.today() + timedelta(days=1)
        for vme in VME.search([]):
            batch = Batch.create({"association_id": vme.id, "batch_type": "transfer", "fund": "working",
                                  "due_until": date(2026, 12, 31), "execution_date": tomorrow})
            batch.action_fill_proposal()
            self.assertTrue(batch.line_ids, vme.name)
            # Only trusted supplier accounts end up in a batch (Odoo's own check, never bypassed).
            self.assertTrue(all(batch.line_ids.partner_bank_id.mapped("allow_out_payment")), vme.name)
            batch.action_generate_file()
            batch.action_mark_sent()
        call = self.env["vme.provision.call"].search([("association_id.name", "=", "Hof ter Beuken"), ("number", "=", 4)])
        debit = Batch.browse(call.with_user(admin).action_create_direct_debit_batch()["res_id"])
        self.assertEqual(debit.line_ids.partner_id.name, "Eigenaar Beuken B7")
        debit.action_generate_file()
        debit.action_mark_sent()
        VME._load_demo_payment_statement()
        batches = self.env["vme.payment.batch"].search([])
        self.assertEqual(set(batches.mapped("state")), {"done"})
        self.assertEqual(debit.rejected_count, 1)
        self.assertEqual(sum(batches.mapped("paid_count")), sum(batches.mapped("line_count")) - 1)
        self.assertTrue(self.env["vme.collection"].search([("partner_id.name", "=", "Eigenaar Beuken B7"), ("state", "=", "open")]))

    def test_demo_cycle(self):
        """The three demo VMEs each at another point of their yearly cycle on 5 November 2026."""
        today = date(2026, 11, 5)
        Vme = self.env["vme.association"].with_context(vme_today=today)
        linde, hof, kaai = (Vme.search([("name", "=", n)]) for n in ("Residentie Linde", "Hof ter Beuken", "Kaaihuis"))
        Step = self.env["vme.cycle.step"].with_context(vme_today=today)

        def steps(vme, year):
            return Step.search([("association_id", "=", vme.id), ("year", "=", year)])

        # Residentie Linde: 2026 done, the assembly of 2027 proposed and waiting for confirmation.
        self.assertEqual(set(steps(linde, 2026).mapped("state")), {"done"})
        planning = steps(linde, 2027).filtered(lambda s: s.code == "planning")
        self.assertEqual(planning.state, "ready")
        self.assertEqual(self.env["vme.assembly"].browse(planning.res_id).state, "proposed")
        self.assertEqual(linde.cycle_late_count, 0)
        self.assertIn("Klaargezet: AV 2027 plannen", linde.cycle_current_step)
        # Hof ter Beuken: the assembly of 2026 was never planned.
        late = hof.cycle_step_ids.filtered(lambda s: s._is_late(today))
        self.assertEqual(sorted(late.mapped("code")), ["agenda", "assembly", "convocation"])
        self.assertTrue(hof.signal_cycle)
        self.assertNotIn(linde, Vme.search([("signal_cycle", "=", True)]))
        # Kaaihuis: taken over in October, next step from 10 November.
        self.assertEqual(steps(kaai, 2026).mapped("code"), ["provision"])
        self.assertEqual(steps(kaai, 2026).state, "done")
        self.assertEqual(kaai.cycle_late_count, 0)
        self.assertIn("AV 2027 plannen", kaai.cycle_current_step)
        # The cycle posted nothing: no posted invoice of 2027.
        self.assertFalse(self.env["account.move"].search([("state", "=", "posted"), ("date", ">=", "2027-01-01")]))
