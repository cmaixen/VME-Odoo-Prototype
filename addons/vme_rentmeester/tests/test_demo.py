from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRentDemo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["vme.association"].with_user(cls.env.ref("base.user_admin"))._load_demo_data()
        cls.env.cr.precommit.run()
        cls.contracts = cls.env["vme.rent.contract"].search([("tenant_ids.name", "like", "Huurder ")])

    def test_three_rented_apartments(self):
        self.assertEqual(sorted(self.contracts.association_id.mapped("name")), ["Hof ter Beuken", "Residentie Linde"])
        self.assertEqual(len(self.contracts), 3)
        self.assertTrue(all(c.state == "active" and c.company_id.is_rent_management for c in self.contracts))
        self.assertTrue(all(email.endswith("@example.com") for email in self.contracts.tenant_ids.mapped("email")))

    def test_demo_indexations_and_tasks(self):
        a2, a7, b23 = (self.contracts.filtered(lambda c, n=n: n in c.tenant_id.name) for n in ("A2", "A7", "B23"))
        draft = a2.indexation_ids.filtered(lambda i: i.state == "draft")
        self.assertEqual(draft.anniversary_date, date(2026, 11, 1))
        self.assertGreater(draft.correction_factor, 1.0)  # EPC E during the freeze
        self.assertEqual(a7.notice_deadline, date(2026, 11, 30))
        self.assertIn("Opzegtermijn verstrijkt", " ".join(a7.activity_ids.mapped("summary")))
        frozen = b23.indexation_ids.filtered(lambda i: i.anniversary_date == date(2023, 9, 1))
        self.assertEqual(frozen.freeze_rate, 0.5)  # EPC D in Flanders
