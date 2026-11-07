import re
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import Form, TransactionCase, tagged

from ..wizard import vme_provision_call_wizard as provision_wizard


@tagged("post_install", "-at_install")
class TestProvisionCall(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Provisie"})
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        Bank = cls.env["res.partner.bank"]
        cls.working_bank = Bank.create({"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id})
        cls.reserve_bank = Bank.create({"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id})
        cls.vme.write({"working_capital_bank_id": cls.working_bank.id, "reserve_capital_bank_id": cls.reserve_bank.id})
        # Trusting a bank account is a human action in Odoo (never the system user).
        (cls.working_bank | cls.reserve_bank).with_user(cls.env.ref("base.user_admin")).allow_out_payment = True
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": n, "lot_type": t}
            for n, t in (("A1", "apartment"), ("A2", "apartment"), ("G1", "garage"))
        ])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(cls.lots, (550, 400, 50))],
        })
        Partner = cls.env["res.partner"]
        cls.owner, cls.seller, cls.buyer = Partner.create([{"name": n} for n in ("Eigenaar P1", "Verkoper P2", "Koper P2")])
        cls.env["vme.ownership"].create([
            # Owner P1 owns apartment A1 and garage G1.
            {"lot_id": cls.lots[0].id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[2].id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.seller.id,
             "date_start": date(2015, 1, 1), "date_end": date(2026, 6, 30)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.buyer.id, "date_start": date(2026, 7, 1)},
        ])
        cls.budget = cls.env["vme.budget"].create({
            "association_id": cls.vme.id, "year": 2026,
            "working_capital_budget": 10000, "reserve_capital_contribution": 1000, "calls_per_year": "4",
        })

    def _run(self, number=1, invoice_date=date(2026, 1, 15), vmes=None, post=True):
        wizard = self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set((vmes or self.vme).ids)],
            "year": 2026, "number": number,
            "invoice_date": invoice_date, "date_due": invoice_date.replace(day=28),
            "post_invoices": post,
        })
        action = wizard.action_create_calls()
        calls = self.env["vme.provision.call"].search(action["domain"])
        return calls.invoice_ids

    def test_amounts_banks_and_accounts(self):
        invoices = self._run()
        working = invoices.filtered(lambda m: m.vme_fund == "working")
        reserve = invoices.filtered(lambda m: m.vme_fund == "reserve")
        self.assertEqual(round(sum(working.mapped("amount_total")), 2), 2500.0)
        self.assertEqual(round(sum(reserve.mapped("amount_total")), 2), 250.0)
        self.assertEqual(len(working), 2)  # two owners on 15 January
        self.assertEqual(len(reserve), 2)
        self.assertEqual(working.partner_bank_id, self.working_bank)
        self.assertEqual(reserve.partner_bank_id, self.reserve_bank)
        self.assertEqual(working.invoice_line_ids.account_id.with_company(self.vme.company_id).mapped("code"), ["100100"])
        self.assertEqual(reserve.invoice_line_ids.account_id.with_company(self.vme.company_id).mapped("code"), ["100200"])
        self.assertFalse(invoices.invoice_line_ids.tax_ids)

    def test_owner_with_two_lots_gets_one_invoice_per_fund(self):
        invoices = self._run().filtered(lambda m: m.partner_id == self.owner)
        self.assertEqual(len(invoices), 2)
        working = invoices.filtered(lambda m: m.vme_fund == "working")
        self.assertEqual(len(working.invoice_line_ids), 2)
        self.assertEqual(working.amount_total, 2500 * 0.6)  # 550 + 50 of 1000

    def test_call_goes_to_owner_on_invoice_date(self):
        before = self._run(number=1, invoice_date=date(2026, 1, 15))
        after = self._run(number=3, invoice_date=date(2026, 7, 15))
        self.assertIn(self.seller, before.partner_id)
        self.assertNotIn(self.buyer, before.partner_id)
        self.assertIn(self.buyer, after.partner_id)
        self.assertNotIn(self.seller, after.partner_id)

    def test_structured_communication(self):
        invoices = self._run()
        for invoice in invoices:
            match = re.fullmatch(r"\+\+\+(\d{3})/(\d{4})/(\d{5})\+\+\+", invoice.payment_reference or "")
            self.assertTrue(match, invoice.payment_reference)
            digits = "".join(match.groups())
            self.assertEqual(int(digits[:10]) % 97 or 97, int(digits[10:]))
        self.assertEqual(len(set(invoices.mapped("payment_reference"))), len(invoices))

    def test_draft_when_not_posting(self):
        invoices = self._run(post=False)
        self.assertEqual(set(invoices.mapped("state")), {"draft"})

    def test_same_call_twice_is_refused(self):
        self._run()
        with self.assertRaises(UserError):
            self._run()

    def test_untrusted_bank_account_is_refused(self):
        self.reserve_bank.with_user(self.env.ref("base.user_admin")).allow_out_payment = False
        self.assertTrue(self.vme.untrusted_fund_bank_ids)
        with self.assertRaises(UserError):
            self._run()

    def test_number_outside_budget_is_refused(self):
        with self.assertRaises(UserError):
            self._run(number=5)

    def test_tracking_record(self):
        self._run()
        call = self.budget.provision_call_ids
        self.assertEqual(len(call), 1)
        self.assertEqual((call.amount_working, call.amount_reserve), (2500.0, 250.0))
        self.assertEqual((call.invoice_count, call.open_count, call.paid_count), (4, 4, 0))

    def test_admin_with_other_company_selected(self):
        # In the browser the user usually has the main company selected, not the VME's.
        admin = self.env.ref("base.user_admin")
        wizard = self.env["vme.provision.call.wizard"].with_user(admin).with_context(
            allowed_company_ids=[self.env.ref("base.main_company").id]
        ).create({
            "association_ids": [Command.set(self.vme.ids)], "year": 2026, "number": 1,
            "invoice_date": date(2026, 1, 15), "date_due": date(2026, 1, 28), "post_invoices": True,
        })
        wizard.action_create_calls()
        invoices = self.budget.provision_call_ids.invoice_ids
        self.assertEqual(set(invoices.mapped("state")), {"posted"})
        self.assertEqual(invoices.filtered(lambda m: m.vme_fund == "working").partner_bank_id, self.working_bank)

    def test_preview_in_open_form(self):
        # The open form works on temporary copies of the VMEs (NewId); the budget must still be found.
        with Form(self.env["vme.provision.call.wizard"]) as wizard:
            wizard.association_ids.add(self.vme)
            wizard.year = 2026
            self.assertIn("Residentie Provisie", wizard.preview_html)
            self.assertNotIn("Geen budget", wizard.preview_html)

    def test_vme_without_budget_is_skipped(self):
        other = self.env["vme.association"].create({"name": "Residentie Zonder Budget"})
        invoices = self._run(vmes=self.vme | other)
        self.assertEqual(invoices.vme_provision_call_id.association_id, self.vme)

    def test_reserve_warning(self):
        # No posted bills in 2025: estimate on the working capital budget (5% of 10000 = 500).
        self.assertTrue(self.budget.previous_year_charges_estimated)
        self.assertEqual(self.budget.reserve_minimum, 500.0)
        self.assertFalse(self.budget.reserve_warning)
        self.budget.reserve_capital_contribution = 400
        self.assertTrue(self.budget.reserve_warning)
        self.budget.reserve_exception_by_general_assembly = True
        self.assertFalse(self.budget.reserve_warning)

    def test_reserve_minimum_uses_posted_bills_of_previous_year(self):
        supplier = self.env["res.partner"].create({"name": "Leverancier 2025", "is_company": True})
        bill = self.env["account.move"].with_company(self.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": date(2025, 6, 1),
            "invoice_line_ids": [Command.create({"name": "Onderhoud", "price_unit": 30000, "tax_ids": [Command.clear()]})],
        })
        bill.invoice_line_ids.vme_key_id = self.vme.key_ids
        bill.action_post()
        self.budget.invalidate_recordset()
        self.assertFalse(self.budget.previous_year_charges_estimated)
        self.assertEqual(self.budget.previous_year_charges, 30000.0)
        self.assertEqual(self.budget.reserve_minimum, 1500.0)
        self.assertTrue(self.budget.reserve_warning)  # 1000 < 1500

    def test_reserve_minimum_counts_only_ordinary_charges(self):
        supplier = self.env["res.partner"].create({"name": "Leverancier 2025", "is_company": True})
        request = self.env["vme.request"].create({
            "association_id": self.vme.id, "request_type_id": self.env.ref("vme_belgie.request_type_key").id,
            "title": "Sleutel voor één eigenaar", "requester_id": supplier.id,
        })
        bills = self.env["account.move"].with_company(self.vme.company_id).create([{
            "move_type": "in_invoice", "partner_id": supplier.id, "invoice_date": date(2025, 6, 1),
            "invoice_line_ids": [Command.create({"name": name, "price_unit": amount, "tax_ids": [Command.clear()]})],
        } for name, amount in (("Onderhoud", 20000), ("Dakwerken", 50000), ("Sleutel", 100))])
        bills.invoice_line_ids.vme_key_id = self.vme.key_ids
        bills[1].vme_reserve_move_id = bills[1]  # paid from the reserve capital
        bills[2].vme_request_id = request  # charged to one owner
        bills.action_post()
        self.budget.invalidate_recordset()
        # Only the maintenance is an ordinary common charge: 5% of 20000.
        self.assertEqual(self.budget.previous_year_charges, 20000.0)
        self.assertEqual(self.budget.reserve_minimum, 1000.0)
        self.assertFalse(self.budget.reserve_warning)

    def test_large_selection_runs_in_background(self):
        # More than BACKGROUND_THRESHOLD VMEs: queued, then made VME per VME by the cron (docs/dev/schaal.md).
        other = self.env["vme.association"].create({"name": "Residentie Zonder Budget"})
        wizard = self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set((self.vme | other).ids)], "year": 2026, "number": 1,
            "invoice_date": date(2026, 1, 15), "date_due": date(2026, 1, 28), "post_invoices": True,
        })
        with patch.object(provision_wizard, "BACKGROUND_THRESHOLD", 1):
            action = wizard.action_create_calls()
        run = self.env["vme.provision.call.run"].browse(action["res_id"])
        self.assertEqual(run.state, "queued")
        self.assertFalse(self.budget.provision_call_ids)
        steps = []
        run._process(lambda: steps.append(1) or 60)
        self.assertEqual((run.state, len(steps)), ("done", 2))
        self.assertEqual(run.done_association_ids, self.vme | other)
        self.assertIn("Residentie Zonder Budget: geen budget voor 2026", run.log)
        invoices = self.budget.provision_call_ids.invoice_ids
        self.assertEqual(len(invoices), 4)
        self.assertEqual(set(invoices.mapped("state")), {"posted"})
        self.assertEqual(self.env["vme.provision.call"].search(run.action_open_calls()["domain"]), self.budget.provision_call_ids)

    def test_background_run_stops_when_out_of_time_and_logs_errors(self):
        other = self.env["vme.association"].create({"name": "Residentie Zonder Sleutel"})
        self.env["vme.budget"].create({"association_id": other.id, "year": 2026, "working_capital_budget": 100,
                                       "reserve_capital_contribution": 10})
        run = self.env["vme.provision.call.run"].create({
            "year": 2026, "number": 1, "invoice_date": date(2026, 1, 15), "date_due": date(2026, 1, 28),
            "association_ids": [Command.set((other | self.vme).ids)],
        })
        run._process(lambda: 0)  # no time left after the first VME
        self.assertEqual((run.state, len(run.done_association_ids)), ("queued", 1))
        run._process()
        self.assertEqual(run.state, "done")
        self.assertIn("Residentie Zonder Sleutel:", run.log)
        self.assertTrue(self.budget.provision_call_ids)
