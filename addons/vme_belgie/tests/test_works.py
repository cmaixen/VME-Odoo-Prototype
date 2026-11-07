from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestWorks(TransactionCase):
    """A1 (600) and A2 (400) on the general key; the reserve capital holds 5000 euro."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({
            "name": "Residentie Werken", "assembly_period_month": "3", "assembly_period_day": 1,
            "works_quote_threshold": 5000, "works_min_quotes": 3,
        })
        cls.env.cr.precommit.run()
        cls.company = cls.vme.company_id
        cls.a1, cls.a2 = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": "A1", "sequence": 1},
            {"association_id": cls.vme.id, "name": "A2", "sequence": 2},
        ])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": cls.a1.id, "shares": 600}),
                         Command.create({"lot_id": cls.a2.id, "shares": 400})],
        })
        cls.owner1, cls.owner2, cls.roofer, cls.roofer2, cls.roofer3 = cls.env["res.partner"].create([
            {"name": "Eigenaar A1"}, {"name": "Eigenaar A2"},
            {"name": "Dakwerker Een", "is_company": True}, {"name": "Dakwerker Twee", "is_company": True},
            {"name": "Dakwerker Drie", "is_company": True},
        ])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.owner1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.owner2.id, "date_start": date(2015, 1, 1)},
        ])
        cls.reserve_account = cls._account("100200")
        cls.expense_account = cls._account("611000")
        # Reserve capital built up in earlier years: 5000 euro on the reserve bank account.
        bank_journal = cls.env["account.journal"].search([("company_id", "=", cls.company.id), ("type", "=", "bank")], limit=1)
        opening = cls.env["account.move"].with_company(cls.company).create({
            "move_type": "entry", "date": date(2026, 1, 1),
            "journal_id": cls.env["account.journal"].search(
                [("company_id", "=", cls.company.id), ("type", "=", "general")], limit=1).id,
            "line_ids": [
                Command.create({"account_id": bank_journal.default_account_id.id, "debit": 5000}),
                Command.create({"account_id": cls.reserve_account.id, "credit": 5000}),
            ],
        })
        opening.action_post()

        room = cls.env["vme.assembly.room"].create({"name": "Zaal Werken"})
        slot = cls.env["vme.assembly.slot"].create({
            "date": date(2026, 3, 10), "time_start": 19.0, "room_id": room.id, "user_id": admin.id})
        cls.assembly = cls.env["vme.assembly"].create({"association_id": cls.vme.id, "year": 2026, "slot_id": slot.id})
        cls.assembly.action_confirm()
        cls.assembly.action_create_attendance_list()
        cls.assembly.attendee_ids.attendance = "present"
        cls.roof, cls.lift = cls.env["vme.assembly.item"].create([
            {"assembly_id": cls.assembly.id, "sequence": 50, "name": "Dakwerken", "majority": "two_thirds",
             "works_amount": 10000},
            {"assembly_id": cls.assembly.id, "sequence": 51, "name": "Liftrenovatie", "majority": "two_thirds",
             "works_amount": 3000},
        ])
        cls.assembly.item_ids.filtered(lambda i: i.majority != "none").action_all_for()
        cls.assembly.action_mark_held()

    @classmethod
    def _account(cls, code):
        return cls.env["account.account"].with_company(cls.company).search(
            [("company_ids", "in", cls.company.id), ("code", "=", code)], limit=1)

    def _works(self, decision=None, **vals):
        decision = decision or self.roof
        return self.env["vme.works"].create({
            "association_id": self.vme.id, "decision_id": decision.id, "name": decision.name, **vals})

    def _quote(self, works, partner, amount):
        return self.env["vme.works.quote"].create({"works_id": works.id, "partner_id": partner.id, "amount": amount})

    def _awarded(self, amount=9600, financing="reserve"):
        works = self._works(financing=financing)
        works.action_request_quotes()
        quote = self._quote(works, self.roofer, amount)
        self._quote(works, self.roofer2, amount + 800)
        self._quote(works, self.roofer3, amount + 1500)
        quote.action_award()
        return works

    def _bill(self, partner, amount, invoice_date=date(2026, 11, 20)):
        return self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice", "partner_id": partner.id, "invoice_date": invoice_date,
            "invoice_line_ids": [Command.create({
                "name": "Dakwerken", "quantity": 1, "price_unit": amount, "tax_ids": [Command.clear()]})],
        })

    def _reserve_balance(self):
        return self.vme._get_fund_balance("reserve")

    # Decision, budget and quotes

    def test_budget_and_key_come_from_the_decision(self):
        works = self._works()
        self.assertEqual(works.budget, 10000)
        self.assertEqual(works.key_id, self.key)
        self.assertEqual(works.decision_number, self.roof.decision_number)
        self.assertEqual(works.min_quotes, 3)

    def test_decision_must_be_adopted(self):
        rejected = self.env["vme.assembly.item"].create({
            "assembly_id": self.assembly.id, "sequence": 60, "name": "Zonnepanelen", "majority": "none"})
        with self.assertRaises(ValidationError):
            self._works(decision=rejected)

    def test_award_needs_the_minimum_number_of_quotes_above_the_threshold(self):
        works = self._works()
        works.action_request_quotes()
        quote = self._quote(works, self.roofer, 9600)
        self._quote(works, self.roofer2, 10400)
        self.assertEqual(works.quotes_missing, 1)
        with self.assertRaises(UserError):
            quote.action_award()
        self._quote(works, self.roofer3, 11100)
        quote.action_award()
        self.assertEqual(works.state, "awarded")
        self.assertEqual((works.contractor_id, works.contract_amount, works.award_date), (self.roofer, 9600, TODAY))
        self.assertEqual(works.quote_ids.mapped("state"), ["awarded", "rejected", "rejected"])
        self.assertTrue(quote.is_cheapest)
        self.assertEqual(quote.budget_difference, -400)
        self.assertIn("Opdrachtbevestiging opmaken voor Dakwerker Een", works.activity_ids.mapped("summary"))

    def test_one_quote_is_enough_below_the_threshold(self):
        works = self._works(decision=self.lift)
        self.assertEqual(works.min_quotes, 1)
        works.action_request_quotes()
        self._quote(works, self.roofer, 2900).action_award()
        self.assertEqual(works.state, "awarded")

    def test_quote_above_the_threshold_needs_more_quotes_even_with_a_low_budget(self):
        works = self._works(decision=self.lift)
        works.action_request_quotes()
        with self.assertRaises(UserError):
            self._quote(works, self.roofer, 6000).action_award()

    # Statuses

    def test_status_flow_and_delivery_marks_the_decision_done(self):
        works = self._awarded()
        with self.assertRaises(UserError):
            works.action_deliver()
        works.action_start()
        self.assertEqual((works.state, works.date_start), ("in_progress", TODAY))
        works.provisional_delivery_date = date(2026, 12, 18)
        works.action_deliver()
        self.assertEqual(works.state, "delivered")
        self.assertTrue(self.roof.works_done)
        self.assertEqual(works.liability_end_date, date(2036, 12, 18))
        final = works.activity_ids.filtered(lambda a: a.summary.startswith("Definitieve oplevering"))
        self.assertEqual(final.date_deadline, date(2027, 12, 18))
        works.action_close()
        self.assertEqual((works.state, works.final_delivery_date), ("closed", TODAY))
        self.assertFalse(works.activity_ids)

    def test_request_quotes_needs_a_budget_and_cancel_with_posted_bill_fails(self):
        works = self._works(decision=self.lift, budget=0)
        works.budget = 0
        with self.assertRaises(UserError):
            works.action_request_quotes()
        awarded = self._awarded()
        self._bill(self.roofer, 2000).action_post()
        with self.assertRaises(UserError):
            awarded.action_cancel()

    # Financing from the reserve capital

    def test_reserve_available_takes_other_awarded_works_into_account(self):
        other = self._works(decision=self.lift, financing="reserve")
        other.action_request_quotes()
        self._quote(other, self.roofer2, 2000).action_award()
        works = self._works(financing="reserve")
        self.assertEqual(works.reserve_balance, 5000)
        self.assertEqual(works.reserve_committed, 2000)
        self.assertEqual(works.reserve_available, 3000)
        self.assertEqual(works.reserve_shortfall, 7000)  # budget 10000
        self.assertEqual(self._works(financing="working").reserve_shortfall, 0)

    def test_reserve_in_the_list_does_not_query_per_works(self):
        works = self.env["vme.works"].concat(*(self._works(financing="reserve") for _i in range(5)))

        def queries(records):
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            records.read(["reserve_available", "reserve_shortfall"])
            return self.env.cr.sql_log_count - before

        self.assertEqual(set(works.mapped("reserve_available")), {5000})
        self.assertEqual(queries(works[:1]), queries(works))

    def test_award_warns_when_the_reserve_is_short(self):
        works = self._awarded(amount=9600)
        self.assertEqual(works.reserve_shortfall, 4600)
        self.assertTrue(any("reservekapitaal volstaat niet" in (m.body or "") for m in works.message_ids))

    def test_reserve_financed_bill_is_booked_on_the_reserve_and_kept_out_of_the_working_balance(self):
        works = self._awarded(amount=4000)
        bill = self._bill(self.roofer, 1500)
        self.assertEqual(bill.vme_works_id, works, "bill of the contractor is linked to the works")
        self.assertEqual(bill.invoice_line_ids.vme_key_id, self.key)
        bill.action_post()

        entry = bill.vme_reserve_move_id
        self.assertEqual(entry.state, "posted")
        self.assertEqual(entry.line_ids.filtered(lambda l: l.account_id == self.reserve_account).debit, 1500)
        self.assertEqual(entry.line_ids.filtered(lambda l: l.account_id == bill.invoice_line_ids.account_id).credit, 1500)
        self.assertEqual(self._reserve_balance(), 3500)
        self.assertEqual((works.invoiced_amount, works.remaining_amount), (1500, 2500))
        self.assertEqual(works.reserve_shortfall, 0)
        # The cost is still distributed per owner, to show each share in the works.
        self.assertEqual(sorted(bill.vme_allocation_ids.mapped("amount")), [600, 900])

        data = self.vme._get_annual_statement(2026)
        a1 = next(st for st in data["statements"] if st["partner"] == self.owner1)
        self.assertEqual(a1["cost_total"], 0)
        self.assertEqual(a1["reserve_works"][0]["works"], works)
        self.assertEqual((a1["reserve_works"][0]["amount"], a1["reserve_works_total"]), (900, 900))
        self.assertEqual(a1["reserve_works"][0]["total_vme"], 1500)
        self.assertTrue(data["is_complete"])

        bill.button_draft()
        self.assertFalse(bill.vme_reserve_move_id)
        self.assertEqual(self._reserve_balance(), 5000)
        bill.action_post()
        self.assertEqual(self._reserve_balance(), 3500)

    def test_reserve_entry_ignores_the_defaults_of_the_bill_form(self):
        # Posting from the bills of the works passes default_vme_works_id in the context.
        works = self._awarded(amount=4000)
        bill = self._bill(self.roofer, 1500)
        bill.with_context(default_vme_works_id=works.id, default_move_type="in_invoice").action_post()
        self.assertEqual(bill.vme_reserve_move_id.move_type, "entry")
        self.assertFalse(bill.vme_reserve_move_id.vme_works_id)
        self.assertEqual(works.bill_ids, bill)
        self.assertEqual(works.invoiced_amount, 1500)

    def test_reserve_financed_credit_note_gives_back_to_the_reserve(self):
        works = self._awarded(amount=4000)
        self._bill(self.roofer, 1500).action_post()
        refund = self.env["account.move"].with_company(self.company).create({
            "move_type": "in_refund", "partner_id": self.roofer.id, "invoice_date": date(2026, 11, 25),
            "invoice_line_ids": [Command.create({"name": "Korting", "quantity": 1, "price_unit": 300,
                                                 "tax_ids": [Command.clear()]})],
        })
        self.assertEqual(refund.vme_works_id, works)
        refund.action_post()
        self.assertEqual(self._reserve_balance(), 3800)
        self.assertEqual(works.invoiced_amount, 1200)

    def test_working_capital_works_are_settled_in_the_annual_statement(self):
        works = self._awarded(amount=4000, financing="working")
        bill = self._bill(self.roofer, 1000)
        self.assertEqual(bill.vme_works_id, works)
        bill.action_post()
        self.assertFalse(bill.vme_reserve_move_id)
        self.assertEqual(self._reserve_balance(), 5000)
        data = self.vme._get_annual_statement(2026)
        a1 = next(st for st in data["statements"] if st["partner"] == self.owner1)
        self.assertEqual((a1["cost_total"], a1["reserve_works"]), (600, []))

    def test_bill_of_another_supplier_is_not_linked(self):
        self._awarded(amount=4000)
        self.assertFalse(self._bill(self.roofer2, 500).vme_works_id)
