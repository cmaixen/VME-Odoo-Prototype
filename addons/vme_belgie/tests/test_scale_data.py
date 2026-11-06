from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..demo_data.vme_scale_data import scale_building, scale_kbo


@tagged("post_install", "-at_install")
class TestScaleData(TransactionCase):
    """The generator of the scale database (docs/dev/schaal.md), on two small VMEs."""

    def test_only_in_scale_database(self):
        with self.assertRaises(UserError):
            self.env["vme.association"]._load_scale_data(1, 1)

    def test_buildings_are_fictitious_and_reproducible(self):
        self.assertEqual(scale_building(7)["lots"], scale_building(7)["lots"])
        sizes = [len(scale_building(i)["lots"]) for i in range(1, 201)]
        self.assertGreaterEqual(min(sizes), 6)
        self.assertLessEqual(max(sizes), 60)
        self.assertTrue(self.env["vme.association"]._is_valid_kbo(scale_kbo(200)))

    def test_structure(self):
        Vme = self.env["vme.association"].with_user(self.env.ref("base.user_admin")).with_context(vme_scale_allow=True)
        vme = Vme._load_scale_data(1, 1)
        self.assertEqual(vme.name, "Residentie Test 001")
        self.assertFalse(Vme._load_scale_data(1, 1), "existing VMEs are skipped")
        self.env.cr.precommit.run()

        self.assertEqual(vme.lot_count, len(scale_building(1)["lots"]))
        for key in vme.key_ids:
            self.assertEqual(key.shares_sum, 1000, key.name)
        owners = vme.lot_ids.current_owner_id
        self.assertTrue(owners and all(o.name.startswith("Eigenaar T001-") for o in owners))
        self.assertTrue(all(o.email.endswith("@example.com") for o in owners))
        self.assertFalse(vme.untrusted_fund_bank_ids)
        self.assertTrue(vme.budget_ids and vme.installation_ids)
        self.assertTrue(vme.construction_year and vme._building_policies())
        self.assertTrue(vme.document_ids.filtered(lambda d: d.certificate_type == "epc_common"))


# About a hundred payments in one test transaction: slow in Odoo's test environment, like the demo year.
@tagged("post_install", "-at_install", "-standard", "vme_slow")
class TestScaleHistory(TransactionCase):

    def test_history(self):
        Vme = self.env["vme.association"].with_user(self.env.ref("base.user_admin")).with_context(vme_scale_allow=True)
        vme = Vme._load_scale_data(1, 1)  # number 1 is a small building (14 lots)
        self.env.cr.precommit.run()
        vme._load_scale_history()
        calls = vme.budget_ids.filtered(lambda b: b.year == 2026).provision_call_ids
        self.assertEqual(sorted(calls.mapped("number")), [1, 2, 3, 4])
        bills = self.env["account.move"].search([("company_id", "=", vme.company_id.id), ("move_type", "=", "in_invoice")])
        self.assertTrue(bills and all(bill.state == "posted" and bill.vme_allocation_ids for bill in bills))
        self.assertGreater(vme.working_capital_balance, 0)
        self.assertGreater(vme.actual_to_date_amount, 0)
