from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@freeze_time(TODAY)
@tagged("post_install", "-at_install")
class TestDamageClaim(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme, cls.other_vme = cls.env["vme.association"].create([
            {"name": "Residentie Schade", "assembly_period_month": "3", "assembly_period_day": 1},
            {"name": "Residentie Elders", "assembly_period_month": "3", "assembly_period_day": 1},
        ])
        cls.env.cr.precommit.run()
        cls.a4, cls.a7 = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": "A4"}, {"association_id": cls.vme.id, "name": "A7"}])
        cls.foreign_lot = cls.env["vme.lot"].create({"association_id": cls.other_vme.id, "name": "B1"})
        cls.owner, cls.insurer, cls.expert, cls.plumber = cls.env["res.partner"].create([
            {"name": "Eigenaar A4"}, {"name": "Verzekeraar Test", "is_company": True},
            {"name": "Expert Test", "is_company": True}, {"name": "Loodgieter Test", "is_company": True},
        ])
        cls.policy = cls.env["vme.insurance.policy"].create({
            "association_id": cls.vme.id, "name": "Brandverzekering gebouw", "insurer_id": cls.insurer.id,
            "policy_number": "POL-1", "deductible": 300, "declaration_days": 8,
        })

    def _claim(self, **vals):
        return self.env["vme.damage.claim"].create({
            "association_id": self.vme.id, "name": "Waterschade A4", "event_date": date(2026, 11, 1),
            "report_date": date(2026, 11, 2), "lot_ids": [Command.set((self.a4 | self.a7).ids)], **vals})

    def test_policy_deadlines_and_first_task(self):
        claim = self._claim()
        self.assertEqual(claim.policy_id, self.policy)
        self.assertEqual(claim.declaration_deadline, date(2026, 11, 9))
        self.assertEqual(claim.prescription_date, date(2029, 11, 1))
        self.assertEqual(claim.activity_ids.summary, "Schade aangeven bij Verzekeraar Test")
        self.assertEqual(claim.activity_ids.date_deadline, date(2026, 11, 9))
        self.assertEqual(claim.deadline_state, "ok")
        with freeze_time(date(2026, 11, 7)):
            claim.invalidate_recordset(["deadline_state"])
            self.assertEqual(claim.deadline_state, "warning")
        with freeze_time(date(2026, 11, 10)):
            claim.invalidate_recordset(["deadline_state"])
            self.assertEqual(claim.deadline_state, "danger")

    def test_status_flow_with_tasks(self):
        claim = self._claim(repair_partner_id=self.plumber.id)
        claim.declaration_date = date(2026, 11, 3)
        claim.action_declare()
        self.assertEqual(claim.state, "declared")
        self.assertEqual(claim.deadline_state, "none")
        self.assertEqual(claim.activity_ids.summary, "Aanstelling expert opvolgen")
        self.assertEqual(claim.activity_ids.date_deadline, date(2026, 11, 17))
        with self.assertRaises(UserError):
            claim.action_expertise()  # no expert yet
        claim.write({"expert_id": self.expert.id, "expertise_date": date(2026, 11, 12)})
        claim.action_expertise()
        self.assertEqual((claim.state, claim.activity_ids.date_deadline), ("expertise", date(2026, 11, 12)))
        claim.action_repair()
        self.assertEqual(claim.state, "repair")
        bill = self.env["account.move"].with_company(self.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": self.plumber.id, "invoice_date": date(2026, 11, 20),
            "vme_damage_claim_id": claim.id,
            "invoice_line_ids": [Command.create({"name": "Herstelling afvoer", "quantity": 1, "price_unit": 1800,
                                                 "tax_ids": [Command.clear()]})],
        })
        bill.action_post()  # no key: posted without distribution
        self.assertEqual(claim.repair_cost, 1800)
        with self.assertRaises(UserError):
            claim.action_paid()  # no compensation yet
        claim.write({"compensation_amount": 1500, "payment_date": date(2026, 12, 10)})
        claim.action_paid()
        self.assertEqual(claim.state, "paid")
        self.assertEqual(claim.net_cost, 300)
        self.assertFalse(claim.activity_ids)
        with self.assertRaises(UserError):
            claim.action_cancel()

    def test_declare_needs_a_policy_and_late_declaration_is_flagged(self):
        claim = self._claim()
        claim.policy_id = False
        with self.assertRaises(UserError):
            claim.action_declare()
        claim.policy_id = self.policy
        claim.declaration_date = date(2026, 11, 12)
        claim.action_declare()
        self.assertTrue(any("na de termijn" in (m.body or "") for m in claim.message_ids))

    def test_refusal_needs_a_reason(self):
        claim = self._claim()
        claim.action_declare()
        with self.assertRaises(UserError):
            claim.action_refuse()
        claim.refusal_reason = "Slijtage, niet gedekt."
        claim.action_refuse()
        self.assertEqual(claim.state, "refused")

    def test_lots_and_policy_of_the_same_vme(self):
        with self.assertRaises(ValidationError):
            self._claim(lot_ids=[Command.set(self.foreign_lot.ids)])
        other_policy = self.env["vme.insurance.policy"].create({
            "association_id": self.other_vme.id, "name": "Polis elders", "insurer_id": self.insurer.id,
            "policy_number": "POL-2"})
        with self.assertRaises(ValidationError):
            self._claim(policy_id=other_policy.id)

    def test_create_from_mail_is_a_draft_and_runs_once_per_mail(self):
        Claim = self.env["vme.damage.claim"]
        claim_id = Claim.create_from_mail(
            self.vme.id, "Dringend: waterlek in het plafond", "Er loopt water langs het plafond.",
            reference="<lek@example.com>", lot_id=self.a4.id, owner_id=self.owner.id, mail_date="2026-11-02")
        claim = Claim.browse(claim_id)
        self.assertEqual((claim.state, claim.source, claim.reporter_id), ("reported", "mail", self.owner))
        self.assertEqual((claim.lot_ids, claim.report_date), (self.a4, date(2026, 11, 2)))
        self.assertEqual(claim.policy_id, self.policy)
        self.assertEqual(len(claim.activity_ids), 1)
        again = Claim.create_from_mail(self.vme.id, "Herhaling", "Nog steeds water.", reference="<lek@example.com>")
        self.assertEqual(again, claim_id)
        # A lot of another VME is never linked.
        foreign = Claim.browse(Claim.create_from_mail(self.vme.id, "Lek", "Water.", lot_id=self.foreign_lot.id))
        self.assertFalse(foreign.lot_ids)
