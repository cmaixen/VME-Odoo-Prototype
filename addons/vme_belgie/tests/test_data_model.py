from datetime import date

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDataModel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Test"})
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name} for name in ("A1", "A2", "A3")
        ])
        cls.owner_a = cls.env["res.partner"].create({"name": "Eigenaar Test A"})
        cls.owner_b = cls.env["res.partner"].create({"name": "Eigenaar Test B"})

    def _create_key(self, shares):
        return self.env["vme.key"].create({
            "name": "Algemeen",
            "association_id": self.vme.id,
            "total_shares": 1000,
            "line_ids": [
                Command.create({"lot_id": lot.id, "shares": value})
                for lot, value in zip(self.lots, shares)
            ],
        })

    # --- VME ---

    def test_association_creates_own_company(self):
        self.assertTrue(self.vme.company_id)
        self.assertEqual(self.vme.company_id.name, "Residentie Test")
        self.assertIn(self.vme.company_id, self.env.user.company_ids)
        other = self.env["vme.association"].create({"name": "Residentie Andere"})
        self.assertNotEqual(other.company_id, self.vme.company_id)

    def test_all_internal_users_get_access(self):
        # Created by a script running as another user: admin must still reach the VME.
        vme = self.env["vme.association"].with_user(self.env.ref("base.user_root")).create(
            {"name": "Residentie Script"}
        )
        self.assertIn(vme.company_id, self.env.ref("base.user_admin").company_ids)

    def test_new_vme_gets_belgian_chart_of_accounts(self):
        vme = self.env["vme.association"].create({"name": "Residentie Rekeningen"})
        # The chart is loaded in a precommit hook; run it as a real save would.
        self.env.cr.precommit.run()
        self.assertEqual(vme.company_id.chart_template, "be_comp")
        self.assertTrue(self.env["account.account"].search_count(
            [("company_ids", "in", vme.company_id.id)]
        ))

    def test_kbo_number_validation(self):
        self.vme.kbo_number = "0123.456.749"
        with self.assertRaises(ValidationError):
            self.vme.kbo_number = "0123.456.748"
        with self.assertRaises(ValidationError):
            self.vme.kbo_number = "12345"

    def test_working_and_reserve_need_separate_accounts(self):
        Bank = self.env["res.partner.bank"]
        working = Bank.create({"acc_number": "BE68 5390 0754 7034", "partner_id": self.vme.partner_id.id})
        reserve = Bank.create({"acc_number": "BE71 0961 2345 6769", "partner_id": self.vme.partner_id.id})
        self.vme.write({"working_capital_bank_id": working.id, "reserve_capital_bank_id": reserve.id})
        with self.assertRaises(ValidationError):
            self.vme.reserve_capital_bank_id = working

    # --- Keys ---

    def test_balanced_key_is_accepted(self):
        key = self._create_key([500, 300, 200])
        self.assertTrue(key.is_balanced)
        self.assertEqual(key.shares_sum, 1000)
        self.assertAlmostEqual(key.line_ids.filtered(lambda l: l.lot_id.name == "A1").percentage, 50.0)

    def test_unbalanced_key_is_refused(self):
        with self.assertRaises(ValidationError):
            self._create_key([500, 300, 199])

    def test_changing_a_line_must_keep_key_balanced(self):
        key = self._create_key([500, 300, 200])
        with self.assertRaises(ValidationError):
            key.line_ids[0].shares = 400

    def test_rebalancing_lines_in_one_save_is_accepted(self):
        key = self._create_key([500, 300, 200])
        line_a1, line_a2 = key.line_ids[0], key.line_ids[1]
        key.write({"line_ids": [
            Command.update(line_a1.id, {"shares": 400}),
            Command.update(line_a2.id, {"shares": 400}),
        ]})
        self.assertTrue(key.is_balanced)
        with self.assertRaises(ValidationError):
            key.write({"line_ids": [Command.delete(line_a1.id)]})

    def test_lot_from_other_association_is_refused(self):
        other = self.env["vme.association"].create({"name": "Residentie Andere"})
        foreign_lot = self.env["vme.lot"].create({"association_id": other.id, "name": "B1"})
        with self.assertRaises(ValidationError):
            self.env["vme.key"].create({
                "name": "Fout",
                "association_id": self.vme.id,
                "total_shares": 1000,
                "line_ids": [Command.create({"lot_id": foreign_lot.id, "shares": 1000})],
            })

    # --- Ownership ---

    def test_sale_during_year(self):
        lot = self.lots[0]
        Ownership = self.env["vme.ownership"]
        Ownership.create({"lot_id": lot.id, "partner_id": self.owner_a.id,
                          "date_start": date(2020, 1, 1), "date_end": date(2026, 6, 30)})
        Ownership.create({"lot_id": lot.id, "partner_id": self.owner_b.id,
                          "date_start": date(2026, 7, 1)})
        self.assertEqual(lot._get_owner_on(date(2026, 6, 30)), self.owner_a)
        self.assertEqual(lot._get_owner_on(date(2026, 7, 1)), self.owner_b)
        self.assertEqual(lot.current_owner_id, self.owner_b)

    def test_overlapping_ownership_is_refused(self):
        lot = self.lots[0]
        Ownership = self.env["vme.ownership"]
        Ownership.create({"lot_id": lot.id, "partner_id": self.owner_a.id, "date_start": date(2020, 1, 1)})
        with self.assertRaises(ValidationError):
            Ownership.create({"lot_id": lot.id, "partner_id": self.owner_b.id, "date_start": date(2026, 7, 1)})

    def test_end_before_start_is_refused(self):
        with self.assertRaises(ValidationError):
            self.env["vme.ownership"].create({
                "lot_id": self.lots[1].id, "partner_id": self.owner_a.id,
                "date_start": date(2026, 7, 1), "date_end": date(2026, 6, 30),
            })
