from datetime import date, timedelta

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

    def test_tenants_receive_mailings(self):
        # The tenants of a lease are tenants of the lot, so a mailing to the tenants reaches them.
        contract = self.contracts.filtered(lambda c: c.association_id.name == "Residentie Linde")[:1]
        lot = contract.lot_ids[:1]
        self.assertIn(contract.tenant_id, lot._get_tenants_on(date(2026, 11, 5)))
        self.assertNotIn(contract.tenant_id, lot._get_tenants_on(contract.date_start - timedelta(days=1)))
        mailing = self.env["vme.communication"].create({
            "name": "Waterafsluiting", "association_id": contract.association_id.id,
            "audience": "tenants", "reference_date": date(2026, 11, 5),
        })
        self.assertIn(contract.tenant_id, [partner for partner, _lots, _role in mailing._get_recipients()])

    def test_demo_mandates(self):
        mandates = self.contracts.mandate_id
        self.assertEqual(len(mandates), 3)
        self.assertEqual(sorted(mandates.mapped("fee_type")), ["fixed", "percent", "percent"])
        self.assertTrue(all(m.fee_tax_id.amount == 21.0 for m in mandates))
        office = self.contracts.company_id
        self.assertTrue(office.rent_bank_id)
        # Loaded as admin, so the accounts are trusted (Odoo's own check, never bypassed).
        self.assertTrue(all(b.allow_out_payment for b in mandates.partner_bank_id | office.rent_bank_id))
