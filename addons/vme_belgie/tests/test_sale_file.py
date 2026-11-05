from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestSaleFile(TransactionCase):
    """A1 (500) and G1 (100) of the seller are sold; A2 (400) belongs to another owner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({
            "name": "Residentie Verkoop", "assembly_period_month": "3", "assembly_period_day": 1,
            "legal_proceedings": "<p>Procedure tegen aannemer Voorbeeld over de gevel.</p>",
        })
        cls.env.cr.precommit.run()
        Bank = cls.env["res.partner.bank"]
        banks = Bank.create([
            {"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id},
            {"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id},
        ])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(admin).allow_out_payment = True
        cls.a1, cls.g1, cls.a2 = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": "A1", "sequence": 1},
            {"association_id": cls.vme.id, "name": "G1", "sequence": 2, "lot_type": "garage"},
            {"association_id": cls.vme.id, "name": "A2", "sequence": 3},
        ])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s})
                         for lot, s in ((cls.a1, 500), (cls.g1, 100), (cls.a2, 400))],
        })
        cls.seller, cls.other, cls.buyer, cls.notary = cls.env["res.partner"].create([
            {"name": "Verkoper A1"}, {"name": "Eigenaar A2"}, {"name": "Koper A1"},
            {"name": "Notaris Test", "is_company": True},
        ])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.seller.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.g1.id, "partner_id": cls.seller.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.other.id, "date_start": date(2015, 1, 1)},
        ])
        for year in (2026, 2027):
            cls.env["vme.budget"].create({
                "association_id": cls.vme.id, "year": year, "calls_per_year": "2",
                "working_capital_budget": 1200, "reserve_capital_contribution": 200,
            })
        for number, call_date in ((1, date(2026, 1, 5)), (2, date(2026, 7, 5))):
            cls.env["vme.provision.call.wizard"].create({
                "association_ids": [Command.set(cls.vme.ids)], "year": 2026, "number": number,
                "invoice_date": call_date, "date_due": call_date.replace(day=28), "post_invoices": True,
            }).action_create_calls()
        cls.provisions = cls.env["account.move"].search([("vme_provision_call_id.association_id", "=", cls.vme.id)])
        # The seller leaves working capital call 2 unpaid, the other owner reserve call 2.
        unpaid = cls.provisions.filtered(lambda m: m.vme_provision_call_id.number == 2 and (
            (m.partner_id == cls.seller and m.vme_fund == "working")
            or (m.partner_id == cls.other and m.vme_fund == "reserve")))
        journals = cls.vme._ensure_fund_bank_journals()[cls.vme]
        for fund in ("working", "reserve"):
            cls.env["account.payment.register"].with_company(cls.vme.company_id).with_context(
                active_model="account.move",
                active_ids=(cls.provisions - unpaid).filtered(lambda m, f=fund: m.vme_fund == f).ids,
            ).create({"journal_id": journals[fund].id, "payment_date": date(2026, 8, 1), "group_payment": False}
                     ).action_create_payments()

        # Assembly of 2026 with roof works (not done) and a lift renovation (done).
        room = cls.env["vme.assembly.room"].create({"name": "Zaal Verkoop"})
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
             "works_amount": 5000, "works_done": True},
        ])
        cls.assembly.item_ids.filtered(lambda i: i.majority != "none").action_all_for()
        cls.assembly.action_mark_held()

        cls.sale = cls.env["vme.sale.file"].create({
            "association_id": cls.vme.id,
            "lot_ids": [Command.set((cls.a1 | cls.g1).ids)],
            "notary_id": cls.notary.id,
            "notary_reference": "NOT/123",
            "buyer_id": cls.buyer.id,
            "first_request_date": date(2026, 10, 28),
        })

    def test_seller_and_deadlines(self):
        self.assertEqual(self.sale.seller_id, self.seller)
        self.assertEqual(self.sale.first_deadline, date(2026, 11, 12))
        self.assertEqual(self.sale.answer_deadline, date(2026, 11, 12))
        self.assertEqual(self.sale.deadline_state, "warning")  # 7 days left
        self.assertEqual(self.sale.activity_ids.date_deadline, date(2026, 11, 12))

        self.sale.second_request_date = date(2026, 11, 20)
        self.assertEqual(self.sale.state, "second_received")
        self.assertEqual(self.sale.second_deadline, date(2026, 12, 20))
        self.assertEqual(sorted(self.sale.activity_ids.mapped("date_deadline")), [date(2026, 11, 12), date(2026, 12, 20)])

    def test_deadline_warning(self):
        sale = self.sale.copy({"first_request_date": date(2026, 11, 1)})
        self.assertEqual(sale.deadline_state, "ok")  # due 16 November
        sale.first_request_date = date(2026, 10, 23)
        self.assertEqual(sale.deadline_state, "warning")  # due 7 November
        self.assertIn("nog 2 dagen", sale.deadline_text)
        sale.first_request_date = date(2026, 10, 15)
        self.assertEqual(sale.deadline_state, "danger")  # due 30 October

    def test_information(self):
        info = self.sale._get_notary_information()
        self.assertEqual([(k["shares"], k["total"]) for k in info["keys"]], [(600, 1000)])
        # Reserve capital: 2 x 100 called (paid or not), the sold lots have 600/1000 of it.
        self.assertEqual(info["reserve_balance"], 200.0)
        self.assertEqual(info["reserve_share"], 120.0)
        # Only the seller's own arrears: working capital call 2 (600/1000 of 600).
        self.assertEqual([a["amount"] for a in info["arrears"]], [360.0])
        self.assertEqual(info["arrears"][0]["move"].partner_id, self.seller)
        self.assertEqual(info["arrears_total"], 360.0)
        # Works not executed, with the share of the sold lots; executed works are left out.
        self.assertEqual([(w["item"], w["share"]) for w in info["works"]], [(self.roof, 6000.0)])
        self.assertIn("aannemer Voorbeeld", info["legal_proceedings"])
        self.assertEqual(info["assemblies"], self.assembly)
        self.assertEqual(info["statement"]["working"]["paid"], 360.0)

    def test_works_with_own_key(self):
        lift_key = self.env["vme.key"].create({
            "name": "Lift", "association_id": self.vme.id, "key_type": "elevator", "total_shares": 100,
            "line_ids": [Command.create({"lot_id": self.a1.id, "shares": 40}),
                         Command.create({"lot_id": self.a2.id, "shares": 60})],
        })
        self.roof.works_key_id = lift_key
        info = self.sale._get_notary_information()
        self.assertEqual(info["works"][0]["share"], 4000.0)

    def test_answer_first(self):
        self.sale.action_answer_first()
        self.assertEqual(self.sale.state, "first_answered")
        self.assertEqual(self.sale.first_answer_date, TODAY)
        self.assertFalse(self.sale.activity_ids)
        self.assertFalse(self.sale.answer_deadline)
        self.assertTrue(self.sale.message_ids.attachment_ids.filtered(lambda a: "eerste vraag" in a.name))

    def test_report_renders(self):
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_notary_information", self.sale.ids, data={"answer": "second"})
        html = html.decode()
        self.assertIn("Inlichtingen aan de notaris", html)
        self.assertIn("Notaris Test", html)
        self.assertIn("NOT/123", html)
        self.assertIn("tweede vraag", html)
        self.assertIn("Dakwerken", html)
        self.assertIn(self.sale._get_notary_information()["arrears"][0]["move"].name, html)
        self.assertIn("Totaal achterstallen", self.sale.information_html)

    def test_deed_transfers_ownership(self):
        self.sale.deed_date = date(2026, 12, 1)
        self.sale.action_deed_done()
        self.assertEqual(self.sale.state, "done")
        for lot in self.a1 | self.g1:
            self.assertEqual(lot._get_owner_on(date(2026, 11, 30)), self.seller)
            self.assertEqual(lot._get_owner_on(date(2026, 12, 1)), self.buyer)
        self.assertEqual(self.a2._get_owner_on(date(2026, 12, 1)), self.other)
        # The next provision call goes to the buyer.
        self.env["vme.provision.call.wizard"].create({
            "association_ids": [Command.set(self.vme.ids)], "year": 2027, "number": 1,
            "invoice_date": date(2027, 1, 5), "date_due": date(2027, 1, 31), "post_invoices": True,
        }).action_create_calls()
        calls_2027 = self.env["account.move"].search([
            ("vme_provision_call_id.budget_id.year", "=", 2027), ("company_id", "=", self.vme.company_id.id)])
        self.assertEqual(calls_2027.partner_id, self.buyer | self.other)
        self.assertEqual(sum(calls_2027.filtered(lambda m: m.partner_id == self.buyer and m.vme_fund == "working")
                             .mapped("amount_total")), 360.0)

    def test_deed_needs_date_and_buyer(self):
        with self.assertRaises(UserError):
            self.sale.action_deed_done()

    def test_deed_refused_when_seller_is_not_owner(self):
        self.sale.write({"seller_id": self.other.id, "deed_date": date(2026, 12, 1)})
        with self.assertRaises(UserError):
            self.sale.action_deed_done()
