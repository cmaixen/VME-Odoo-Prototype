from datetime import date
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import format_date, mute_logger

# Assembly period 4-18 March 2027, convocation term 15 days: the last day on which the
# convocation can leave for a meeting inside the period is 3 March 2027.
LAST_CONVOCATION = date(2027, 3, 3)


@tagged("post_install", "-at_install")
class TestCycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.vme = cls._create_vme("Residentie Cyclus", budget=True)
        cls.room = cls.env["vme.assembly.room"].create({"name": "Zaal Cyclus"})
        cls.slot = cls.env["vme.assembly.slot"].create({
            "date": date(2027, 3, 17), "time_start": 19.0, "max_assemblies": 1,
            "location_type": "room", "room_id": cls.room.id, "user_id": cls.admin.id,
        })
        cls.Step = cls.env["vme.cycle.step"]

    @classmethod
    def _create_vme(cls, name, budget=True, period=True):
        values = {"name": name, "cycle_start_date": date(2026, 11, 1)}
        if period:
            values.update(assembly_period_month="3", assembly_period_day=4)
        vme = cls.env["vme.association"].create(values)
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        Bank = cls.env["res.partner.bank"]
        banks = Bank.create([{"acc_number": number, "partner_id": vme.partner_id.id}
                             for number in (f"BE00 {name[:4]} 0001", f"BE00 {name[:4]} 0002")])
        vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(cls.admin).allow_out_payment = True  # trusting an account is a human action
        lots = cls.env["vme.lot"].create([
            {"association_id": vme.id, "name": n, "lot_type": "apartment"} for n in ("C1", "C2")])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, (600, 400))],
        })
        owners = cls.env["res.partner"].create([{"name": f"Eigenaar {name} {n}"} for n in (1, 2)])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(lots, owners)])
        if budget:
            cls.env["vme.budget"].create({
                "association_id": vme.id, "year": 2027,
                "working_capital_budget": 8000, "reserve_capital_contribution": 800, "calls_per_year": "4",
            })
        return vme

    def _sync(self, today, vmes=None):
        (vmes or self.vme)._cycle_sync(today)

    def _steps(self, vme=None, year=2027):
        return self.Step.search([("association_id", "=", (vme or self.vme).id), ("year", "=", year)])

    def _step(self, code, sequence=0, vme=None, year=2027):
        return self._steps(vme, year).filtered(lambda s: s.code == code and s.sequence == sequence)

    def _company_moves(self, vme=None):
        return self.env["account.move"].search([("company_id", "=", (vme or self.vme).company_id.id)])

    # Calendar

    def test_deadlines_per_step(self):
        plan = {(v["code"], v["sequence"]): (v["date_ready"], v["date_deadline"]) for v in self.vme._cycle_plan(2027)}
        self.assertEqual(plan[("closing", 0)], (date(2027, 1, 1), date(2027, 2, 10)))
        self.assertEqual(plan[("statement", 0)], (date(2027, 1, 1), date(2027, 2, 24)))
        self.assertEqual(plan[("budget", 0)], (date(2027, 1, 2), date(2027, 2, 24)))
        self.assertEqual(plan[("planning", 0)], (date(2026, 11, 4), date(2027, 2, 1)))
        self.assertEqual(plan[("agenda", 0)], (date(2027, 2, 1), LAST_CONVOCATION))
        self.assertEqual(plan[("convocation", 0)], (date(2027, 2, 17), LAST_CONVOCATION))
        self.assertEqual(plan[("assembly", 0)], (date(2027, 3, 4), date(2027, 3, 18)))
        self.assertEqual(plan[("minutes", 0)], (date(2027, 3, 18), date(2027, 4, 17)))
        self.assertEqual(plan[("approved_budget", 0)], (date(2027, 3, 18), date(2027, 4, 17)))
        self.assertEqual(plan[("provision", 1)], (date(2026, 12, 18), date(2027, 1, 1)))
        self.assertEqual(plan[("provision", 4)], (date(2027, 9, 17), date(2027, 10, 1)))
        self.assertNotIn(("provision", 5), plan)

    def test_dated_assembly_moves_open_deadlines(self):
        self._sync(date(2026, 11, 5))  # proposes the meeting of 17 March
        assembly = self.env["vme.assembly"].search([("association_id", "=", self.vme.id), ("year", "=", 2027)])
        self.assertEqual(assembly.date, date(2027, 3, 17))
        self._sync(date(2026, 11, 6))
        self.assertEqual(self._step("convocation").date_deadline, date(2027, 3, 2))  # 17 March minus 15 days
        self.assertEqual(self._step("assembly").date_deadline, date(2027, 3, 17))
        self.assertEqual(self._step("minutes").date_deadline, date(2027, 4, 16))

    def test_monthly_calls(self):
        self.vme.budget_ids.calls_per_year = "12"
        self._sync(date(2026, 11, 5))
        provisions = self._steps().filtered(lambda s: s.code == "provision")
        self.assertEqual(len(provisions), 12)
        self.assertEqual(self._step("provision", 5).date_deadline, date(2027, 5, 1))
        self.assertEqual(self._step("provision", 5).name, "Provisieoproep 5/12 2027")
        # Back to quarterly calls: the monthly calls that no longer exist disappear.
        self.vme.budget_ids.calls_per_year = "4"
        self._sync(date(2026, 11, 6))
        self.assertEqual(len(self._steps().filtered(lambda s: s.code == "provision")), 4)

    def test_start_date_leaves_out_earlier_steps(self):
        self.vme.cycle_start_date = date(2027, 2, 15)
        self._sync(date(2026, 11, 5))
        codes = set(self._steps().mapped("code"))
        self.assertNotIn("closing", codes)  # deadline 10 February
        self.assertNotIn("planning", codes)  # deadline 1 February
        self.assertIn("convocation", codes)
        self.assertEqual(self._steps().filtered(lambda s: s.code == "provision").mapped("sequence"), [2, 3, 4])
        self.assertFalse(self._steps(year=2026))

    def test_without_assembly_period_only_closing_statement_and_calls(self):
        vme = self._create_vme("Residentie Zonder Periode", period=False)
        self._sync(date(2026, 11, 5), vme)
        self.assertEqual(set(self._steps(vme).mapped("code")), {"closing", "statement", "provision"})
        self.assertEqual(self._step("closing", vme=vme).date_deadline, date(2027, 3, 31))

    def test_cycle_off_without_start_date(self):
        self.vme.cycle_start_date = False
        self.Step._cron_run_cycle()
        self.assertFalse(self.Step.search([("association_id", "=", self.vme.id)]))

    # Preparing: drafts and tasks, never posted or sent

    def test_cron_prepares_draft_invoices_only(self):
        self._sync(date(2026, 12, 20))  # call 1 of 2027 is ready from 18 December
        step = self._step("provision", 1)
        self.assertEqual(step.state, "ready")
        invoices = self._company_moves().filtered(lambda m: m.move_type == "out_invoice")
        self.assertEqual(len(invoices), 4)  # two owners, two funds
        self.assertEqual(set(invoices.mapped("state")), {"draft"})
        self.assertEqual(invoices.mapped("invoice_date"), [date(2027, 1, 1)] * 4)
        self.assertEqual(round(sum(invoices.mapped("amount_total")), 2), 2200.0)  # (8000 + 800) / 4
        self.assertEqual((step.res_model, step.res_id), ("vme.provision.call", invoices.vme_provision_call_id.id))
        self.assertEqual(len(step.activity_ids), 1)
        self.assertIn("nakijken en boeken", step.activity_ids.summary)
        self.assertEqual(self._step("provision", 2).state, "pending")

    def test_same_step_not_prepared_twice(self):
        self._sync(date(2026, 12, 20))
        self._sync(date(2026, 12, 21))
        self.Step._cron_run_cycle()
        step = self._step("provision", 1)
        self.assertEqual(len(self.env["vme.provision.call"].search([("association_id", "=", self.vme.id)])), 1)
        self.assertEqual(len(self._company_moves()), 4)
        self.assertEqual(len(step.activity_ids), 1)
        self.assertEqual(len(self._steps()), len(self.vme._cycle_plan(2027)))
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Step.create({"association_id": self.vme.id, "year": 2027, "code": "provision", "sequence": 1,
                              "date_ready": date(2026, 12, 18), "date_deadline": date(2027, 1, 1)})

    def test_call_made_by_hand_is_reused(self):
        wizard = self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(self.vme.ids)], "year": 2027, "number": 1,
            "invoice_date": date(2026, 12, 15), "date_due": date(2027, 1, 15), "post_invoices": False,
        })
        wizard.action_create_calls()
        self._sync(date(2026, 12, 20))
        self.assertEqual(len(self._company_moves()), 4)
        self.assertEqual(self._step("provision", 1).state, "ready")

    def test_posting_the_invoices_closes_the_step(self):
        self._sync(date(2026, 12, 20))
        step = self._step("provision", 1)
        self._company_moves().with_company(self.vme.company_id).action_post()  # a human posts them
        self._sync(date(2026, 12, 22))
        self.assertEqual(step.state, "done")
        self.assertFalse(step.activity_ids)

    def test_planning_proposes_and_does_not_confirm(self):
        self._sync(date(2026, 11, 5))
        step = self._step("planning")
        assembly = self.env["vme.assembly"].browse(step.res_id)
        self.assertEqual(step.state, "ready")
        self.assertEqual(assembly.state, "proposed")
        self.assertEqual(assembly.slot_id, self.slot)
        self.assertIn("bevestigen", step.activity_ids.summary)
        self.assertEqual(self._step("convocation").state, "pending")
        assembly.action_confirm()  # the syndic confirms
        self._sync(date(2026, 11, 6))
        self.assertEqual(step.state, "done")

    def test_convocations_are_drafts(self):
        self._sync(date(2026, 11, 5))
        assembly = self.env["vme.assembly"].browse(self._step("planning").res_id)
        assembly.action_confirm()
        self._sync(date(2027, 2, 20))  # convocation ready from 15 February (2 March minus 14 days)
        step = self._step("convocation")
        self.assertEqual(step.state, "ready")
        self.assertEqual(len(assembly.convocation_ids), 2)
        self.assertEqual(set(assembly.convocation_ids.mapped("state")), {"draft"})
        self.assertFalse(assembly.convocation_sent_date)
        self.assertEqual(self._step("agenda").state, "done")  # the convocations carry the agenda
        assembly.convocation_ids.action_mark_sent()
        self._sync(date(2027, 2, 21))
        self.assertEqual(step.state, "done")

    def test_convocation_waits_for_a_confirmed_assembly(self):
        self._sync(date(2027, 2, 20))
        step = self._step("convocation")
        self.assertEqual(step.state, "ready")
        self.assertIn("Bevestig eerst", step.note)
        self.assertIn("Los eerst op", step.activity_ids.summary)
        self.assertFalse(self.env["vme.assembly.convocation"].search([("association_id", "=", self.vme.id)]))

    def test_missing_budget_gives_a_task_and_other_vmes_continue(self):
        other = self._create_vme("Residentie Zonder Budget", budget=False)
        self._sync(date(2026, 12, 20), other | self.vme)
        step = self._step("provision", 1, vme=other)
        self.assertEqual(step.state, "ready")
        self.assertIn("geen budget 2027", step.note)
        self.assertIn("Los eerst op", step.activity_ids.summary)
        self.assertFalse(self._company_moves(other))
        self.assertEqual(len(self._company_moves()), 4)

    def test_agenda_gets_renewal_of_syndic_when_due(self):
        self._sync(date(2026, 11, 5))
        assembly = self.env["vme.assembly"].browse(self._step("planning").res_id)
        Vme = type(self.env["vme.association"])
        with patch.object(Vme, "_cycle_syndic_renewal_due", return_value=True):
            self._sync(date(2027, 2, 2))
        self.assertIn("Herbenoeming van de syndicus", assembly.item_ids.mapped("name"))
        self.assertEqual(len(assembly.item_ids.filtered(lambda i: "commissaris" in i.name and "Benoeming" in i.name)), 1)
        self.assertIn("Herbenoeming van de syndicus", self._step("agenda").note)

    def test_budget_step_shows_reserve_minimum(self):
        self.vme.budget_ids.reserve_capital_contribution = 100  # under 5% of the (estimated) charges
        self._sync(date(2027, 1, 5))
        step = self._step("budget")
        self.assertEqual(step.state, "ready")
        self.assertIn("lager dan 5%", step.note)
        self.vme.budget_ids.reserve_capital_contribution = 800
        self._sync(date(2027, 1, 6))
        self.assertEqual(step.state, "done")

    # Done by hand or by the closing of the year

    def test_ticking_off_the_task_closes_a_manual_step(self):
        self._sync(date(2027, 1, 5))
        step = self._step("statement")
        self.assertEqual(step.state, "ready")
        step.activity_ids.action_feedback(feedback="Nagekeken")
        self.assertEqual(step.state, "done")
        # A step closed by a fact stays open when its task is ticked off.
        provision = self._step("provision", 1)
        provision.activity_ids.action_feedback(feedback="Gezien")
        self.assertEqual(provision.state, "ready")

    def test_lock_date_closes_the_fiscal_year(self):
        self._sync(date(2027, 1, 5))
        step = self._step("closing")
        self.assertEqual(step.state, "ready")
        self.vme.company_id.sudo().fiscalyear_lock_date = date(2026, 12, 31)
        self._sync(date(2027, 1, 6))
        self.assertEqual(step.state, "done")

    # Overview

    def test_late_step_signal_in_portfolio(self):
        today = date(2027, 2, 5)
        self._sync(today)  # the meeting is proposed but not confirmed by 1 February
        vme = self.vme.with_context(vme_today=today)
        self.assertTrue(self._step("planning").with_context(vme_today=today).is_late)
        self.assertEqual(vme.cycle_late_count, 2)  # planning (1 February) and call 1 (1 January)
        self.assertIn("Te laat: Provisieoproep 1/4 2027", vme.cycle_current_step)
        signal = next(s for s in vme._get_signals(today) if s["code"] == "cycle")
        self.assertIn("AV 2027 plannen", signal["message"])
        self.assertTrue(vme.signal_cycle)
        self.assertIn(self.vme, self.env["vme.association"].with_context(vme_today=today).search(
            [("signal_cycle", "=", True)]))
        late = self.Step.with_context(vme_today=today).search([("is_late", "=", True)])
        self.assertEqual(late.mapped("code"), ["provision", "planning"])
        self.assertNotIn(self._step("minutes"), late)

    def test_minutes_are_not_late_before_the_assembly(self):
        today = date(2027, 5, 1)
        self._sync(today)
        minutes = self._step("minutes").with_context(vme_today=today)
        self.assertEqual(minutes.date_deadline, date(2027, 4, 17))
        self.assertFalse(minutes.is_late)
        self.assertTrue(self._step("assembly").with_context(vme_today=today).is_late)

    def test_building_card_shows_the_cycle(self):
        self._sync(date(2026, 11, 5))
        data = self.vme._get_building_card_data(date(2026, 11, 5))
        self.assertIn(self._step("planning"), data["cycle_steps"])
        self.assertIn("Jaarcyclus", self.vme.with_context(vme_today=date(2026, 11, 5)).building_card_html)
        self.assertEqual(self.vme.with_context(vme_today=date(2026, 11, 5)).cycle_current_step,
                         f"Klaargezet: AV 2027 plannen (uiterlijk {format_date(self.env, date(2027, 2, 1))})")
