from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..models.vme_collection import aging_bucket, legal_max_penalty

DUE = date(2026, 2, 4)


@tagged("post_install", "-at_install")
class TestCollection(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Invordering"})
        cls.env.cr.precommit.run()  # load the chart of accounts and the fund accounts
        cls.company = cls.vme.company_id
        Bank = cls.env["res.partner.bank"]
        working = Bank.create({"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id})
        reserve = Bank.create({"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id})
        cls.vme.write({"working_capital_bank_id": working.id, "reserve_capital_bank_id": reserve.id})
        (working | reserve).with_user(cls.env.ref("base.user_admin")).allow_out_payment = True
        cls.owner, cls.payer = cls.env["res.partner"].create([
            {"name": "Eigenaar Invordering X1", "email": "eigenaar.x1@example.com"},
            {"name": "Eigenaar Invordering X2", "email": "eigenaar.x2@example.com"},
        ])
        cls.accounts = {
            code: cls.env["account.account"].with_company(cls.company).search(
                [("company_ids", "in", cls.company.id), ("code", "=", code)], limit=1)
            for code in ("100100", "100200", "751000", "743000")
        }
        cls.invoices = cls._invoice(cls.owner, 1500, "working") | cls._invoice(cls.owner, 150, "reserve")
        cls.Collection = cls.env["vme.collection"]

    @classmethod
    def _invoice(cls, partner, amount, fund, due=DUE, invoice_date=date(2026, 1, 5)):
        move = cls.env["account.move"].with_company(cls.company).create({
            "move_type": "out_invoice",
            "partner_id": partner.id,
            "invoice_date": invoice_date,
            "invoice_date_due": due,
            "vme_fund": fund,
            "invoice_line_ids": [Command.create({
                "name": f"Provisie {fund}", "quantity": 1, "price_unit": amount,
                "account_id": cls.accounts["100100" if fund == "working" else "100200"].id,
                "tax_ids": [Command.clear()],
            })],
        })
        move.action_post()
        return move

    def _pay(self, moves):
        self.env["account.payment.register"].with_company(self.company).with_context(
            active_model="account.move", active_ids=moves.ids,
        ).create({"payment_date": DUE}).action_create_payments()

    def _refresh(self, today):
        self.Collection._refresh(today)
        return self.Collection.with_context(vme_today=today).search(
            [("partner_id", "=", self.owner.id), ("association_id", "=", self.vme.id)], order="id desc", limit=1)

    def _send_draft(self, collection, today):
        draft = collection.reminder_ids.filtered(lambda r: r.state == "draft")
        self.assertEqual(len(draft), 1)
        draft.with_context(vme_today=today).action_mark_sent()
        return draft

    def _list_queries(self, collections, today):
        """Queries to show these dossiers in the list, from an empty cache."""
        self.env.invalidate_all()
        before = self.env.cr.sql_log_count
        collections.with_context(vme_today=today).read(["lot_names", "amount_due", "next_step", "interest_preview"])
        return self.env.cr.sql_log_count - before

    def test_list_does_not_query_per_dossier(self):
        owners = self.env["res.partner"].create([{"name": f"Eigenaar Lijst {i}"} for i in range(6)])
        lots = self.env["vme.lot"].create([{"association_id": self.vme.id, "name": f"L{i}"} for i in range(6)])
        self.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2020, 1, 1)} for lot, owner in zip(lots, owners)])
        for owner in owners:
            self._invoice(owner, 100, "working")
        today = DUE + timedelta(days=5)
        self.Collection._refresh(today)
        collections = self.Collection.search([("association_id", "=", self.vme.id), ("partner_id", "in", owners.ids)])
        self.assertEqual(len(collections), 6)
        self.assertEqual(collections.sorted(lambda c: c.partner_id.name).mapped("lot_names"), lots.mapped("name"))
        self.assertEqual(set(collections.with_context(vme_today=today).mapped("amount_due")), {100.0})
        self.assertEqual(self._list_queries(collections[:2], today), self._list_queries(collections, today))

    # Aging

    def test_aging_buckets(self):
        self.assertEqual([aging_bucket(d) for d in (1, 30, 31, 60, 61, 90, 91, 400)],
                         ["0_30", "0_30", "31_60", "31_60", "61_90", "61_90", "90_plus", "90_plus"])

    def test_arrears_overview(self):
        # The overview counts from the real date of today.
        today = fields.Date.today()
        partner = self.env["res.partner"].create({"name": "Eigenaar Ouderdom"})
        for days, amount in ((10, 100), (45, 200), (75, 300), (120, 400)):
            self._invoice(partner, amount, "working", due=today - timedelta(days=days),
                          invoice_date=today - timedelta(days=days + 30))
        self._invoice(partner, 999, "working", due=today + timedelta(days=5), invoice_date=today)  # not due yet
        paid = self._invoice(partner, 50, "working", due=today - timedelta(days=20), invoice_date=today - timedelta(days=40))
        self._pay(paid)
        arrears = self.env["vme.arrears"].search([("partner_id", "=", partner.id)])
        self.assertEqual({a.aging: a.amount_residual for a in arrears},
                         {"0_30": 100, "31_60": 200, "61_90": 300, "90_plus": 400})
        self.assertEqual(arrears.association_id, self.vme)
        self.assertTrue(all(a.payment_reference.startswith("+++") for a in arrears))
        self.assertEqual(max(arrears.mapped("days_overdue")), 120)

    # Levels

    def test_levels_go_up_one_by_one(self):
        collection = self._refresh(DUE)
        self.assertFalse(collection, "Not overdue on the due date itself")
        collection = self._refresh(DUE + timedelta(days=1))
        self.assertEqual(collection.state, "open")
        self.assertEqual(collection.amount_due, 1650)
        self.assertEqual(collection.reminder_ids.level, "1")
        self.assertEqual(self._refresh(DUE + timedelta(days=2)).reminder_ids.mapped("level"), ["1"], "One draft at a time")

        first = self._send_draft(collection, DUE + timedelta(days=2))
        self.assertEqual(collection.level, "1")
        self.assertFalse(self._refresh(first.sent_date + timedelta(days=13)).reminder_ids.filtered(lambda r: r.state == "draft"))
        collection = self._refresh(first.sent_date + timedelta(days=14))
        second = collection.reminder_ids.filtered(lambda r: r.state == "draft")
        self.assertEqual(second.level, "2")
        self.assertEqual(second.first_reminder_date, first.sent_date)

        self._send_draft(collection, second.date)
        collection = self._refresh(second.date + timedelta(days=14))
        third = collection.reminder_ids.filtered(lambda r: r.state == "draft")
        self.assertEqual(third.level, "3")
        self._send_draft(collection, third.date)
        later = third.date + timedelta(days=30)
        collection = self._refresh(later)
        self.assertFalse(collection.reminder_ids.filtered(lambda r: r.state == "draft"), "No level after the notice")
        self.assertEqual(collection.with_context(vme_today=later).next_step, "Doorsturen naar advocaat of deurwaarder")

    def test_first_reminder_after_configured_days(self):
        self.vme.collection_first_reminder_days = 10
        self.assertFalse(self._refresh(DUE + timedelta(days=9)).reminder_ids)
        self.assertEqual(self._refresh(DUE + timedelta(days=10)).reminder_ids.level, "1")

    def test_paid_dossier_is_closed(self):
        collection = self._refresh(DUE + timedelta(days=5))
        draft = collection.reminder_ids
        self._pay(self.invoices)
        self.Collection._refresh(DUE + timedelta(days=6))
        self.assertEqual(collection.state, "closed")
        self.assertEqual(draft.state, "cancel")
        self.assertFalse(self.env["vme.arrears"].search([("partner_id", "=", self.owner.id)]))

    def test_reminder_content_and_sending(self):
        mails_before = self.env["mail.mail"].search_count([])
        collection = self._refresh(DUE + timedelta(days=3))
        reminder = collection.reminder_ids
        self.assertEqual(reminder.amount_due, 1650)
        self.assertEqual(len(reminder.line_ids), 2)
        self.assertEqual(set(reminder.line_ids.mapped("bank_account")), {"BE68 5390 0754 7034", "BE71 0961 2345 6769"})
        for line in reminder.line_ids:
            self.assertIn(line.payment_reference, reminder.body_html)
        self.assertIn("Vriendelijke herinnering", reminder.subject)
        self.assertIn("kosteloos", reminder.body_html)
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before, "Nothing is sent by itself")

        composer = reminder.with_context(vme_today=DUE + timedelta(days=3)).action_open_composer()
        self.assertTrue(composer["context"]["mark_reminder_as_sent"])
        self.assertTrue(composer["context"]["default_attachment_ids"])
        reminder.with_context(mark_reminder_as_sent=True, vme_today=DUE + timedelta(days=4)).message_post(body="Herinnering")
        self.assertEqual(reminder.state, "sent")
        self.assertEqual(reminder.sent_date, DUE + timedelta(days=4))

    # Interest and damages

    def test_legal_penalty_scale(self):
        self.assertEqual([legal_max_penalty(b) for b in (0, 100, 150, 300, 500, 1650, 100000)],
                         [0, 20, 20, 45, 65, 122.5, 2000])

    def test_costs_need_a_free_reminder_and_a_term(self):
        collection = self._refresh(DUE + timedelta(days=1))
        with self.assertRaises(UserError):
            collection.with_context(vme_today=DUE + timedelta(days=60))._charge_costs()
        first = self._send_draft(collection, DUE + timedelta(days=1))  # sent 5 February
        with self.assertRaises(UserError):
            collection.with_context(vme_today=first.sent_date + timedelta(days=13))._charge_costs()

    def test_interest_and_damages_booked_on_owner(self):
        collection = self._refresh(DUE + timedelta(days=1))
        first = self._send_draft(collection, DUE + timedelta(days=1))
        start = first.sent_date + timedelta(days=14)
        today = start + timedelta(days=30)
        invoice = collection.with_context(vme_today=today)._charge_costs()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.partner_id, self.owner)
        self.assertEqual(invoice.company_id, self.company)
        interest = invoice.invoice_line_ids.filtered(lambda l: l.account_id == self.accounts["751000"])
        penalty = invoice.invoice_line_ids.filtered(lambda l: l.account_id == self.accounts["743000"])
        # 8% per year over 30 days on 1500 and on 150.
        self.assertEqual(sorted(interest.mapped("price_unit")), [0.99, 9.86])
        # 10% of 1650 = 165, capped by the consumer scale at 65 + 5% of 1150 = 122.50.
        self.assertEqual(penalty.price_unit, 122.5)
        self.assertEqual(collection.interest_until, today)
        self.assertEqual(collection.penalty_date, today)

        # A second charge only adds the new days of interest, on the provisions, not on the costs.
        later = today + timedelta(days=10)
        second = collection.with_context(vme_today=later)._charge_costs()
        self.assertEqual(sorted(second.invoice_line_ids.mapped("price_unit")), [0.33, 3.29])
        # The costs are now part of what the owner owes.
        self.assertAlmostEqual(collection.with_context(vme_today=later).amount_due, 1650 + invoice.amount_total + second.amount_total, places=2)

    def test_interest_from_due_date_without_consumer_rules(self):
        self.vme.write({"collection_consumer_rules": False, "collection_interest_rate": 20,
                        "collection_penalty_percent": 10, "collection_penalty_min": 50})
        collection = self._refresh(DUE + timedelta(days=1))
        costs = collection._compute_costs(DUE + timedelta(days=365))
        self.assertEqual(sorted(i["amount"] for i in costs["interest"]), [30.0, 300.0])
        self.assertEqual(costs["penalty"], 165.0)

    def test_consumer_rate_is_capped(self):
        self.env["ir.config_parameter"].sudo().set_param("vme_belgie.legal_interest_rate", "4.5")
        self.vme.collection_interest_rate = 20
        self.assertEqual(self.vme.collection_effective_rate, 12.5)
        self.vme.collection_consumer_rules = False
        self.assertEqual(self.vme.collection_effective_rate, 20)

    # Forwarding

    def test_forward_to_bailiff(self):
        collection = self._refresh(DUE + timedelta(days=1))
        bailiff = self.env["res.partner"].create({"name": "Gerechtsdeurwaarder Voorbeeld", "email": "deurwaarder@example.com"})
        collection.forward_partner_id = bailiff
        with self.assertRaises(UserError):
            collection.action_forward()  # no notice sent yet
        day = DUE + timedelta(days=1)
        for _level in range(3):
            self._send_draft(collection, day)
            day += timedelta(days=14)
            collection = self._refresh(day)
        action = collection.with_context(vme_today=day).action_forward()
        self.assertEqual(action["context"]["default_partner_ids"], bailiff.ids)
        self.assertTrue(action["context"]["default_attachment_ids"])
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_collection_overview", collection.ids)[0]
        self.assertIn(b"Ingebrekestelling", html)
        collection.with_context(mark_collection_as_forwarded=True).message_post(body="Dossier")
        self.assertEqual(collection.state, "forwarded")
        self.assertTrue(collection.forward_date)

    # Multi-company: the VME's invoices live in its own company

    def test_buttons_work_without_the_vme_company_selected(self):
        collection = self._refresh(DUE + timedelta(days=1))
        admin = self.env.ref("base.user_admin")
        main = self.env.ref("base.main_company")
        as_admin = collection.with_user(admin).with_context(allowed_company_ids=main.ids)
        today = DUE + timedelta(days=1)
        reminder = as_admin.reminder_ids.with_context(vme_today=today)
        reminder.action_open_composer()
        reminder.action_mark_sent()
        later = today + timedelta(days=40)
        as_admin.with_context(vme_today=later).action_charge_costs()
        as_admin.invalidate_recordset()
        values = as_admin.with_context(vme_today=later).read(
            ["amount_due", "next_step", "interest_preview", "penalty_preview", "cost_summary", "arrears_ids"])[0]
        self.assertIn("Factuur", values["cost_summary"])
        self.assertTrue(as_admin.penalty_date)
        self.env["vme.arrears"].with_user(admin).with_context(allowed_company_ids=main.ids).search_read(
            [("partner_id", "=", self.owner.id)], ["move_name", "collection_id", "amount_residual"])
