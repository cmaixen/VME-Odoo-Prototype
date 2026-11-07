from datetime import timedelta

from freezegun import freeze_time

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRentCronUsers(TransactionCase):
    """The daily rent cron runs as OdooBot: its tasks go to a person (B-R2)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.landlord = cls.env["res.partner"].create({"name": "Verhuurder Taak"})
        cls.tenant = cls.env["res.partner"].create({"name": "Huurder Taak"})
        cls.manager = cls.env["res.users"].create({"name": "Beheerder Taak", "login": "beheerder.taak"})

    def _lease(self, **vals):
        contract = self.env["vme.rent.contract"].create({
            "landlord_id": self.landlord.id, "tenant_ids": [(6, 0, self.tenant.ids)], "property_address": "Taakstraat 1",
            "region": "flanders", "date_signed": "2024-01-10", "date_start": "2024-02-01", "duration_years": 3,
            "rent": 900, **vals,
        })
        contract.action_activate()
        return contract

    def test_notice_task_goes_to_the_manager(self):
        self.assertEqual(self.env.user, self.env.ref("base.user_root"))
        contract = self._lease(user_id=self.manager.id)
        # Created by OdooBot: no manager by default, so the admin gets the task instead of OdooBot.
        unassigned = self._lease()
        self.assertFalse(unassigned.user_id)
        with freeze_time(contract.notice_deadline - timedelta(days=10)):
            self.env["vme.rent.contract"]._cron_rent_reminders()
        self.assertEqual(contract.activity_ids.user_id, self.manager)
        self.assertEqual(unassigned.activity_ids.user_id, self.env.ref("base.user_admin"))
