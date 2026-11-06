import base64
from datetime import date, timedelta

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestRequests(TransactionCase):
    """A1 belongs to the owner and is rented out to the tenant; A2 belongs to another owner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        admin = cls.env.ref("base.user_admin")
        cls.vme = cls.env["vme.association"].create({
            "name": "Residentie Aanvraag", "assembly_period_month": "3", "assembly_period_day": 1,
            "key_certificate_ref": "CERT-TEST-1",
        })
        cls.env.cr.precommit.run()
        banks = cls.env["res.partner.bank"].create([
            {"acc_number": "BE68 5390 0754 7034", "partner_id": cls.vme.partner_id.id},
            {"acc_number": "BE71 0961 2345 6769", "partner_id": cls.vme.partner_id.id},
        ])
        cls.vme.write({"working_capital_bank_id": banks[0].id, "reserve_capital_bank_id": banks[1].id})
        banks.with_user(admin).allow_out_payment = True
        cls.locksmith, cls.owner, cls.other, cls.tenant, cls.buyer = cls.env["res.partner"].create([
            {"name": "Slotenmaker Test", "email": "slotenmaker@example.com", "is_company": True},
            {"name": "Eigenaar A1", "email": "eigenaar.a1@example.com"},
            {"name": "Eigenaar A2", "email": "eigenaar.a2@example.com"},
            {"name": "Huurder A1", "email": "huurder.a1@example.com"},
            {"name": "Koper A1", "email": "koper.a1@example.com"},
        ])
        cls.vme.locksmith_partner_id = cls.locksmith
        cls.a1, cls.a2 = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": "A1", "sequence": 1},
            {"association_id": cls.vme.id, "name": "A2", "sequence": 2},
        ])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": cls.a1.id, "shares": 600}),
                         Command.create({"lot_id": cls.a2.id, "shares": 400})],
        })
        cls.env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.owner.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.other.id, "date_start": date(2015, 1, 1)},
        ])
        cls.env["vme.lot.contact"].create({
            "lot_id": cls.a1.id, "partner_id": cls.tenant.id, "role": "tenant", "date_start": date(2025, 9, 1),
        })
        cls.Request = cls.env["vme.request"]

    def _intake(self, email, subject="Extra badge", body="Graag een extra badge voor de inkom.", **kwargs):
        return self.Request.browse(self.Request.create_from_intake(
            self.vme.id, kwargs.pop("request_type", "key"), email, subject=subject, body=body, **kwargs))

    def _sent_messages(self, request):
        """Messages that went or go out by mail to someone (not internal notes)."""
        return request.message_ids.filtered(lambda m: m.message_type == "comment" and m.partner_ids)

    # Verification

    def test_owner_is_verified_at_once(self):
        request = self._intake("Eigenaar.A1@example.com")
        self.assertEqual(request.requester_id, self.owner)
        self.assertEqual(request.requester_role, "owner")
        self.assertEqual(request.lot_id, self.a1)
        self.assertEqual(request.key_kind, "badge")
        self.assertFalse(request.needs_verification)
        self.assertEqual(request.state, "in_progress")
        self.assertEqual(request.verified_date, TODAY)
        self.assertTrue(request.order_ready)
        self.assertTrue(request.order_attachment_id)
        self.assertIn("CERT-TEST-1", request.order_mail_body)
        # The order is a draft: nothing went out.
        self.assertFalse(self._sent_messages(request))
        self.assertIn("Bestelling slotenmaker nakijken en versturen", request.activity_ids.mapped("summary"))

    def test_owner_of_another_lot_is_not_verified(self):
        request = self._intake("eigenaar.a2@example.com", lot_id=self.a1.id)
        self.assertEqual(request.requester_role, "unknown")
        self.assertEqual(request.state, "waiting_proof")
        self.assertEqual(request.missing_proofs, "een eigendomsbewijs (bijvoorbeeld de akte of een attest van de notaris)")

    def test_tenant_without_consent_waits(self):
        request = self._intake("huurder.a1@example.com", subject="Extra sleutel",
                               body="Ik huur A1 en wil een extra sleutel van de inkom.")
        self.assertEqual(request.requester_id, self.tenant)
        self.assertEqual(request.requester_role, "tenant")
        self.assertEqual(request.lot_id, self.a1)
        self.assertEqual(request.owner_id, self.owner)
        self.assertEqual(request.key_kind, "entrance_key")
        self.assertEqual(request.state, "waiting_proof")
        self.assertIn("toestemming van de eigenaar", request.proof_mail_body)
        self.assertIn("huurcontract", request.proof_mail_body)
        self.assertFalse(request.order_attachment_id)
        self.assertFalse(self._sent_messages(request))
        with self.assertRaises(UserError):
            request.action_verify()
        request.proof_owner_consent = True
        with self.assertRaises(UserError):  # the lease is still missing
            request.action_verify()

    def test_tenant_with_consent_is_verified(self):
        consent = base64.b64encode(b"%PDF-1.4 toestemming").decode()
        request = self._intake("huurder.a1@example.com", attachments=[
            {"name": "toestemming_eigenaar.pdf", "datas": consent, "mimetype": "application/pdf"},
            {"name": "huurcontract.pdf", "datas": consent, "mimetype": "application/pdf"},
        ])
        self.assertEqual(len(request.proof_attachment_ids), 2)
        self.assertEqual(request.state, "waiting_proof")
        request.write({"proof_owner_consent": True, "proof_lease": True})
        request.action_verify()
        self.assertEqual(request.state, "in_progress")
        self.assertTrue(request.order_ready)

    def test_unknown_requester(self):
        request = self._intake("onbekend@example.com", name="Onbekende Bewoner", lot_id=self.a2.id)
        self.assertEqual(request.requester_role, "unknown")
        self.assertEqual(request.requester_id.name, "Onbekende Bewoner")
        self.assertEqual(request.requester_id.email, "onbekend@example.com")
        self.assertEqual(request.state, "waiting_proof")
        self.assertIn("eigendomsbewijs", request.proof_mail_body)
        request.proof_ownership = True
        request.action_verify()
        self.assertEqual(request.state, "in_progress")

    def test_manual_request_identifies_role(self):
        key_type = self.env.ref("vme_belgie.request_type_key")
        request = self.Request.create({
            "association_id": self.vme.id, "lot_id": self.a1.id, "request_type_id": key_type.id,
            "title": "Afstandsbediening", "requester_id": self.tenant.id, "key_kind": "remote",
        })
        self.assertEqual(request.channel, "manual")
        self.assertEqual(request.requester_role, "tenant")
        self.assertEqual(request.state, "waiting_proof")
        self.assertEqual(len(request.check_ids), 3)
        self.assertTrue(request.name.startswith("AANV/2026/"))

    def test_same_mail_makes_one_request(self):
        first = self._intake("eigenaar.a1@example.com", reference="badge-a1@example.com")
        second = self._intake("eigenaar.a1@example.com", reference="badge-a1@example.com")
        self.assertEqual(first, second)

    # Proof request and reminder

    def test_proof_request_and_reminder_after_seven_days(self):
        request = self._intake("huurder.a1@example.com")
        self.assertFalse(request.reminder_due)
        request.action_send_proof_request()
        sent = self._sent_messages(request)
        self.assertEqual(sent.partner_ids, self.tenant)
        self.assertEqual(request.proof_requested_date, TODAY)
        reminder = request.activity_ids.filtered(lambda a: a.summary == "Herinnering: bewijs nog niet ontvangen")
        self.assertEqual(reminder.date_deadline, TODAY + timedelta(days=7))
        with freeze_time(TODAY + timedelta(days=6)):
            request.invalidate_recordset(["reminder_due"])
            self.assertFalse(request.reminder_due)
        with freeze_time(TODAY + timedelta(days=7)):
            request.invalidate_recordset(["reminder_due"])
            self.assertTrue(request.reminder_due)
            request.action_send_proof_reminder()
            self.assertEqual(len(self._sent_messages(request)), 2)
            self.assertEqual(request.proof_reminder_date, TODAY + timedelta(days=7))
            request.invalidate_recordset(["reminder_due"])
            self.assertFalse(request.reminder_due)

    # Order, delivery, private charge and register

    def _ordered(self, email="eigenaar.a1@example.com"):
        request = self._intake(email)
        if request.state == "waiting_proof":
            request.write({"proof_owner_consent": True, "proof_lease": True})
            request.action_verify()
        request.action_send_order()
        return request

    def test_send_order_is_one_click(self):
        request = self._ordered()
        sent = self._sent_messages(request)
        self.assertEqual(sent.partner_ids, self.locksmith)
        self.assertIn(request.order_attachment_id, sent.attachment_ids)
        self.assertEqual(request.state, "ordered")
        self.assertEqual(request.order_sent_date, TODAY)
        with self.assertRaises(UserError):
            request.action_send_order()

    def test_order_waits_for_a_click(self):
        # After verification the order is ready, but only a staff member sends it.
        request = self._intake("eigenaar.a1@example.com")
        self.assertTrue(request.order_ready)
        self.assertEqual(request.state, "in_progress")
        self.assertFalse(self._sent_messages(request))

    def test_no_locksmith_gives_a_task(self):
        self.vme.locksmith_partner_id = False
        request = self._intake("eigenaar.a1@example.com")
        self.assertEqual(request.state, "in_progress")
        self.assertFalse(request.order_ready)
        self.assertTrue(request.activity_ids.filtered(lambda a: a.summary.startswith("Slotenmaker instellen")))

    def test_delivery_registers_and_charges_the_owner(self):
        request = self._ordered("huurder.a1@example.com")
        request.write({"quantity": 2, "unit_price": 27.5})
        request.key_numbers = "BA-001"
        with self.assertRaises(UserError):  # two badges need two numbers
            request.action_register_delivery()
        request.key_numbers = "BA-001, BA-002"
        request.action_register_delivery()
        self.assertEqual(request.state, "done")
        keys = self.a1.key_register_ids
        self.assertEqual(sorted(keys.mapped("number")), ["BA-001", "BA-002"])
        self.assertEqual(keys.partner_id, self.tenant)
        self.assertEqual(set(keys.mapped("kind")), {"badge"})
        self.assertEqual(keys.request_id, request)

        invoice = request.invoice_id
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.company_id, self.vme.company_id)
        self.assertEqual(invoice.partner_id, self.owner)  # the owner pays, not the tenant
        self.assertEqual(invoice.amount_total, 55.0)
        self.assertEqual(invoice.invoice_date_due, TODAY + timedelta(days=30))
        self.assertFalse(invoice.invoice_line_ids.tax_ids)
        # The code of an account depends on the company in Odoo 19.
        self.assertEqual(invoice.invoice_line_ids.account_id.with_company(self.vme.company_id).code, "416100")
        self.assertEqual(invoice.vme_fund, "working")
        self.assertEqual(invoice.vme_request_id, request)
        self.assertEqual(invoice.partner_bank_id, self.vme.working_capital_bank_id)

    def test_locksmith_bill_is_not_distributed(self):
        request = self._ordered()
        request.key_numbers = "BA-007"
        request.action_register_delivery()
        bill = self.env["account.move"].with_company(self.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": self.locksmith.id, "invoice_date": TODAY,
            "vme_request_id": request.id,
            "invoice_line_ids": [Command.create({
                "name": "Badge", "quantity": 1, "price_unit": 25.0, "tax_ids": [Command.clear()],
                "account_id": self.Request._private_charge_account(self.vme.company_id).id,
            })],
        })
        bill.action_post()
        self.assertFalse(bill.vme_allocation_ids)
        statement = self.vme._get_annual_statement(2026)
        self.assertNotIn(bill, statement["undistributed_bills"])
        self.assertEqual(statement["bills_total"], 0.0)
        self.assertTrue(statement["is_complete"])

    # Other procedures

    def test_badge_lost_blocks_the_badge(self):
        badge = self.env["vme.lot.key"].create({
            "lot_id": self.a1.id, "kind": "badge", "number": "BA-100", "partner_id": self.owner.id,
        })
        request = self._intake("eigenaar.a1@example.com", subject="Badge verloren", request_type="badge_lost")
        self.assertEqual(request.state, "in_progress")  # no proof needed to block
        request.blocked_key_ids = badge
        request.action_block_keys()
        self.assertEqual(badge.state, "blocked")
        self.assertEqual(badge.blocked_date, TODAY)
        request.action_done()
        self.assertEqual(request.state, "done")

    def test_new_tenant_is_registered(self):
        newcomer = self.env["res.partner"].create({"name": "Nieuwe Huurder A2", "email": "nieuw.a2@example.com"})
        request = self._intake("eigenaar.a2@example.com", subject="Nieuwe huurder", request_type="new_tenant")
        request.write({"tenant_partner_id": newcomer.id, "planned_date": date(2026, 12, 1)})
        request.action_register_tenant()
        self.assertEqual(self.a2._get_tenants_on(date(2026, 12, 1)), newcomer)
        self.assertFalse(self.a2._get_tenants_on(TODAY))
        with freeze_time(date(2026, 12, 2)):
            role, lot = self.Request._identify_in(self.vme, "nieuw.a2@example.com")
        self.assertEqual((role, lot), ("tenant", self.a2))

    def test_works_permission_on_next_assembly(self):
        request = self._intake("eigenaar.a1@example.com", subject="Airco buitenunit", request_type="works_permission")
        with self.assertRaises(UserError):  # no assembly planned yet
            request.action_add_to_assembly()
        assembly = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2027})
        request.action_add_to_assembly()
        self.assertEqual(request.assembly_item_id.assembly_id, assembly)
        self.assertEqual(request.assembly_item_id.majority, "two_thirds")
        self.assertIn("A1", request.assembly_item_id.name)

    def test_damage_gives_a_task_until_damage_files_exist(self):
        request = self._intake("eigenaar.a1@example.com", subject="Inkomdeur sluit niet", request_type="damage")
        self.assertEqual(request.state, "in_progress")
        self.assertIn("Defect of schade doorsturen naar een schadedossier", request.activity_ids.mapped("summary"))

    # Sale file

    def test_register_in_sale_file_and_deed(self):
        owner_key, tenant_badge = self.env["vme.lot.key"].create([
            {"lot_id": self.a1.id, "kind": "entrance_key", "number": "VS-1", "partner_id": self.owner.id,
             "issue_date": date(2015, 1, 1)},
            {"lot_id": self.a1.id, "kind": "badge", "number": "BA-2", "partner_id": self.tenant.id},
        ])
        blocked = self.env["vme.lot.key"].create({
            "lot_id": self.a1.id, "kind": "badge", "number": "BA-3", "partner_id": self.owner.id,
        })
        blocked.action_block()
        sale = self.env["vme.sale.file"].create({
            "association_id": self.vme.id, "lot_ids": [Command.set(self.a1.ids)], "buyer_id": self.buyer.id,
        })
        self.assertEqual(sale.key_register_ids, owner_key | tenant_badge)
        info = sale._get_notary_information()
        self.assertEqual(info["keys_issued"], owner_key | tenant_badge)
        self.assertIn("VS-1", sale.information_html)
        sale.deed_date = date(2026, 12, 15)
        sale.action_deed_done()
        self.assertEqual(owner_key.partner_id, self.buyer)
        self.assertEqual(tenant_badge.partner_id, self.tenant)  # the tenant keeps the badge
        self.assertEqual(blocked.partner_id, self.owner)
        # The deed message lists the keys; other steps may post after it (e.g. the welcome letter).
        self.assertTrue(any("VS-1" in message.body for message in sale.message_ids))
