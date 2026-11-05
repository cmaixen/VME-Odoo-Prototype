from datetime import date
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.vme_belgie.models.vme_communication import VmeLot

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestCommunication(TransactionCase):
    """Block A: A1 + G1 (same owner), A2 (paper), A3 (sold on 1 December); block B: B1 (no e-mail address)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Communicatie"})
        Lot = cls.env["vme.lot"]
        cls.a1, cls.g1, cls.a2, cls.a3, cls.b1 = Lot.create([
            {"association_id": cls.vme.id, "name": "A1", "sequence": 1, "building_block": "A"},
            {"association_id": cls.vme.id, "name": "G1", "sequence": 2, "building_block": "A", "lot_type": "garage"},
            {"association_id": cls.vme.id, "name": "A2", "sequence": 3, "building_block": "A"},
            {"association_id": cls.vme.id, "name": "A3", "sequence": 4, "building_block": "A"},
            {"association_id": cls.vme.id, "name": "B1", "sequence": 5, "building_block": "B"},
        ])
        Partner = cls.env["res.partner"]
        cls.owner1, cls.owner2, cls.seller, cls.buyer, cls.owner_b = Partner.create([
            {"name": "Eigenaar Communicatie A1", "email": "a1@example.com", "phone": "+32 000 00 00 01"},
            {"name": "Eigenaar Communicatie A2", "email": "a2@example.com", "vme_communication_preference": "paper"},
            {"name": "Verkoper Communicatie A3", "email": "a3@example.com"},
            {"name": "Koper Communicatie A3", "email": "koper.a3@example.com"},
            {"name": "Eigenaar Communicatie B1"},
        ])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.owner1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.g1.id, "partner_id": cls.owner1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.owner2.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a3.id, "partner_id": cls.seller.id, "date_start": date(2015, 1, 1),
             "date_end": date(2026, 11, 30)},
            {"lot_id": cls.a3.id, "partner_id": cls.buyer.id, "date_start": date(2026, 12, 1)},
            {"lot_id": cls.b1.id, "partner_id": cls.owner_b.id, "date_start": date(2015, 1, 1)},
        ])

    def _communication(self, **values):
        return self.env["vme.communication"].create({
            "association_id": self.vme.id, "name": "Mededeling {vme}",
            "body_html": "<p>Beste {eigenaar}, dit gaat over {kavels}.</p>", **values,
        })

    def _recipients(self, communication):
        return {partner: (lots.mapped("name"), role) for partner, lots, role in communication._get_recipients()}

    # Selection of recipients

    def test_all_owners_one_entry_per_owner(self):
        recipients = self._recipients(self._communication())
        self.assertEqual(recipients[self.owner1], (["A1", "G1"], "owner"))
        self.assertEqual(set(recipients), {self.owner1, self.owner2, self.seller, self.owner_b})

    def test_owner_on_reference_date(self):
        before = self._recipients(self._communication(reference_date=date(2026, 11, 30)))
        after = self._recipients(self._communication(reference_date=date(2026, 12, 1)))
        self.assertIn(self.seller, before)
        self.assertNotIn(self.buyer, before)
        self.assertIn(self.buyer, after)
        self.assertNotIn(self.seller, after)

    def test_block_selection(self):
        recipients = self._recipients(self._communication(audience="block", building_block=" a "))
        self.assertEqual(set(recipients), {self.owner1, self.owner2, self.seller})
        recipients = self._recipients(self._communication(audience="block", building_block="B"))
        self.assertEqual(set(recipients), {self.owner_b})

    def test_block_is_required(self):
        with self.assertRaises(UserError):
            self._communication(audience="block").action_prepare_recipients()

    def test_chosen_lots(self):
        communication = self._communication(audience="lots", lot_ids=[Command.set((self.g1 | self.b1).ids)])
        recipients = self._recipients(communication)
        self.assertEqual(recipients, {self.owner1: (["G1"], "owner"), self.owner_b: (["B1"], "owner")})

    def test_tenants_come_from_the_hook(self):
        communication = self._communication(audience="tenants")
        self.assertEqual(communication._get_recipients(), [], "No tenants before steps 19 and 25.")
        tenant = self.env["res.partner"].create({"name": "Huurder Communicatie A2", "email": "huurder@example.com"})

        def tenants_on(lots, on_date):
            return tenant if self.a2 in lots and on_date == TODAY else self.env["res.partner"]

        with patch.object(VmeLot, "_get_tenants_on", tenants_on):
            self.assertEqual(self._recipients(communication), {tenant: (["A2"], "tenant")})
            communication.action_prepare_recipients()
        self.assertEqual(communication.log_ids.partner_id, tenant)
        self.assertEqual(communication.log_ids.role, "tenant")

    def test_chosen_partners_get_their_lots(self):
        outsider = self.env["res.partner"].create({"name": "Buitenstaander", "email": "x@example.com"})
        communication = self._communication(
            audience="partners", partner_ids=[Command.set((self.buyer | outsider).ids)], reference_date=date(2026, 12, 1))
        self.assertEqual(self._recipients(communication), {self.buyer: (["A3"], "owner"), outsider: ([], "other")})

    # Channel per person

    def test_preference_paper_or_email(self):
        communication = self._communication()
        communication.action_prepare_recipients()
        channel = {log.partner_id: log.channel for log in communication.log_ids}
        self.assertEqual(channel[self.owner1], "email")
        self.assertEqual(channel[self.owner2], "letter", "Paper preference")
        self.assertEqual(channel[self.owner_b], "letter", "No e-mail address")

    def test_sms_falls_back_without_phone(self):
        communication = self._communication(channel="sms")
        self.assertEqual(communication._resolve_channel(self.owner1), "sms")
        self.assertEqual(communication._resolve_channel(self.seller), "email")
        self.assertEqual(communication._resolve_channel(self.owner2), "letter")

    def test_push_only_for_people_with_an_account(self):
        communication = self._communication(channel="push")
        self.assertEqual(communication._resolve_channel(self.owner1), "email")
        self.assertEqual(communication._resolve_channel(self.env.ref("base.user_admin").partner_id), "push")

    def test_letter_and_registered_ignore_the_preference(self):
        self.assertEqual(self._communication(channel="letter")._resolve_channel(self.owner1), "letter")
        self.assertEqual(self._communication(channel="registered")._resolve_channel(self.owner1), "registered")

    # Draft, confirmation and log

    def test_draft_sends_nothing_and_renders_placeholders(self):
        mails_before = self.env["mail.mail"].search_count([])
        communication = self._communication()
        communication.action_prepare_recipients()
        self.assertEqual(communication.state, "draft")
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
        log = communication.log_ids.filtered(lambda line: line.partner_id == self.owner1)
        self.assertEqual(log.state, "draft")
        self.assertEqual(log.subject, "Mededeling Residentie Communicatie")
        self.assertIn("Beste Eigenaar Communicatie A1, dit gaat over A1, G1.", log.body_html)

    def test_confirm_sends_by_channel_and_logs_per_owner(self):
        communication = self._communication(channel="sms")
        communication.action_confirm()
        self.assertEqual(communication.state, "sent")
        logs = {log.partner_id: log for log in communication.log_ids}
        self.assertTrue(all(log.state == "sent" and log.sent_date == TODAY for log in logs.values()))
        self.assertEqual(logs[self.owner1].channel, "sms")
        self.assertTrue(logs[self.owner1].provider_reference.startswith("MOCK-SMS-"))
        self.assertEqual(logs[self.seller].mail_id.recipient_ids, self.seller)
        self.assertEqual(logs[self.owner2].channel, "letter")
        self.assertTrue(communication.letter_attachment_id)
        self.assertEqual(self.owner1.vme_communication_count, 1)
        with self.assertRaises(UserError):
            communication.action_prepare_recipients()

    def test_registered_mailing_fills_the_register(self):
        communication = self._communication(audience="lots", lot_ids=[Command.set(self.a2.ids)], channel="registered")
        communication.action_confirm()
        registered = communication.log_ids.registered_mail_id
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered.partner_id, self.owner2)
        self.assertEqual(registered.state, "prepared")
        self.assertTrue(registered.name.startswith("AT/"))
        self.assertEqual(registered.attachment_id.mimetype, "application/pdf")
        registered.action_send_electronic()
        self.assertEqual(registered.state, "deposited")
        self.assertTrue(registered.tracking_number.startswith("MOCK-ERDS-"))
        registered.action_refresh_status()
        self.assertEqual(registered.state, "delivered")

    def test_survey_answers_per_owner(self):
        template = self.env.ref("vme_belgie.communication_template_survey_charging")
        communication = self._communication()
        communication._apply_template(template)
        self.assertEqual(communication.kind, "survey")
        self.assertEqual(communication.option_ids.mapped("name"), ["Ja, binnen het jaar", "Ja, later", "Nee"])
        communication.action_confirm()
        yes, _later, no = communication.option_ids
        logs = {log.partner_id: log for log in communication.log_ids}
        self.assertIn("Ja, binnen het jaar", logs[self.owner1].body_html)
        logs[self.owner1].answer_option_id = yes
        logs[self.owner2].answer_option_id = no
        logs[self.seller].answer_option_id = yes
        self.assertEqual(logs[self.owner1].answer_date, TODAY)
        self.assertEqual((yes.answer_count, no.answer_count), (2, 1))
        self.assertEqual(communication.answer_count, 3)

    def test_survey_needs_options(self):
        communication = self._communication(kind="survey", question="Interesse?")
        with self.assertRaises(UserError):
            communication.action_confirm()

    # Links with other steps

    def test_welcome_letter_after_the_deed(self):
        sale = self.env["vme.sale.file"].create({
            "association_id": self.vme.id, "lot_ids": [Command.set(self.a1.ids)],
            "buyer_id": self.buyer.id, "deed_date": date(2026, 12, 15),
        })
        sale.seller_id = self.owner1
        sale.action_deed_done()
        letter = sale.welcome_communication_id
        self.assertEqual(letter.state, "draft", "Never sent automatically")
        self.assertEqual(letter.log_ids.partner_id, self.buyer)
        self.assertEqual(letter.log_ids.lot_names, "A1")
        self.assertIn("Welkom als nieuwe eigenaar van A1 in Residentie Communicatie", letter.log_ids.body_html)
        self.assertFalse(letter.log_ids.mail_id)

    def test_formal_notice_goes_to_the_register(self):
        collection = self.env["vme.collection"].create({"association_id": self.vme.id, "partner_id": self.owner2.id})
        reminder = self.env["vme.collection.reminder"].create({
            "collection_id": collection.id, "level": "3", "subject": "Ingebrekestelling A2",
            "body_html": "<p>Ingebrekestelling</p>",
        })
        reminder.action_send_registered()
        self.assertEqual(reminder.state, "sent")
        registered = reminder.registered_mail_id
        self.assertEqual(registered.partner_id, self.owner2)
        self.assertEqual(registered.subject, "Ingebrekestelling A2")
        self.assertTrue(registered.attachment_id)
        log = self.env["vme.communication.log"]._get_for_records(reminder)
        self.assertEqual((log.channel, log.state), ("registered", "sent"))

    def test_lower_levels_are_logged_but_not_registered(self):
        collection = self.env["vme.collection"].create({"association_id": self.vme.id, "partner_id": self.owner1.id})
        reminder = self.env["vme.collection.reminder"].create({
            "collection_id": collection.id, "level": "1", "subject": "Herinnering A1"})
        reminder.with_context(mark_reminder_as_sent=True).action_mark_sent()
        self.assertFalse(reminder.registered_mail_id)
        log = self.env["vme.communication.log"]._get_for_records(reminder)
        self.assertEqual((log.channel, log.state), ("email", "sent"))
        with self.assertRaises(UserError):
            reminder.action_send_registered()

    def test_convocations_appear_in_the_log(self):
        assembly = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2027})
        convocation = self.env["vme.assembly.convocation"].create({
            "assembly_id": assembly.id, "partner_id": self.owner2.id, "lot_names": "A2"})
        log = self.env["vme.communication.log"]._get_for_records(convocation)
        self.assertEqual((log.state, log.channel, log.lot_names), ("draft", "letter", "A2"))
        convocation.action_mark_sent()
        self.assertEqual((log.state, log.sent_date), ("sent", TODAY))
        self.assertEqual(convocation.state, "sent", "The convocation itself works as before")
