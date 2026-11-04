from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..demo_data.vme_demo_data import distribute_shares, fake_iban


@tagged("post_install", "-at_install")
class TestDemoData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["vme.association"]._load_demo_data()
        cls.vmes = cls.env["vme.association"].search([])
        cls.linde = cls.vmes.filtered(lambda v: v.name == "Residentie Linde")

    def test_helpers(self):
        self.assertEqual(sum(distribute_shares([1, 1, 1])), 1000)
        self.assertEqual(distribute_shares([1, 1, 1]), [334, 333, 333])
        iban = fake_iban(1)
        self.assertTrue(iban.startswith("BE") and iban[4:7] == "999")
        # ISO 13616 check: rearranged IBAN modulo 97 equals 1.
        rearranged = iban[4:] + "1114" + iban[2:4]
        self.assertEqual(int(rearranged) % 97, 1)

    def test_buildings_and_lots(self):
        lots_per_vme = {vme.name: vme.lot_count for vme in self.vmes}
        self.assertEqual(lots_per_vme, {"Residentie Linde": 20, "Hof ter Beuken": 24, "Kaaihuis": 6})
        for vme in self.vmes:
            self.assertTrue(vme.company_id)
            self.assertTrue(vme._is_valid_kbo(vme.kbo_number))

    def test_keys_are_balanced(self):
        keys = self.env["vme.key"].search([("association_id", "in", self.vmes.ids)])
        self.assertEqual(len(keys), 5)
        for key in keys:
            self.assertTrue(key.is_balanced, key.display_name)
            self.assertEqual(key.shares_sum, 1000)
        lift = keys.filtered(lambda k: k.key_type == "elevator")
        self.assertEqual(lift.association_id, self.linde)
        self.assertEqual(set(lift.line_ids.lot_id.mapped("lot_type")), {"apartment"})
        self.assertFalse(self.vmes.filtered(lambda v: v.name == "Kaaihuis").key_ids.filtered(
            lambda k: k.key_type == "elevator"))
        # The heating key must really differ from the general key.
        beuken_keys = keys.filtered(lambda k: k.association_id.name == "Hof ter Beuken")
        shares = {k.key_type: k.line_ids.sorted("lot_id").mapped("shares") for k in beuken_keys}
        self.assertNotEqual(shares["general"], shares["heating"])

    def test_sale_mid_year(self):
        lot_a5 = self.linde.lot_ids.filtered(lambda l: l.name == "A5")
        seller = lot_a5._get_owner_on(date(2026, 6, 30))
        buyer = lot_a5._get_owner_on(date(2026, 7, 1))
        self.assertTrue(seller and buyer)
        self.assertNotEqual(seller, buyer)
        lot_g5 = self.linde.lot_ids.filtered(lambda l: l.name == "G5")
        self.assertEqual(lot_g5._get_owner_on(date(2026, 7, 1)), buyer)

    def test_owner_with_multiple_lots(self):
        beuken = self.vmes.filtered(lambda v: v.name == "Hof ter Beuken")
        b23, b24 = (beuken.lot_ids.filtered(lambda l, n=n: l.name == n) for n in ("B23", "B24"))
        self.assertEqual(b23.current_owner_id, b24.current_owner_id)
        self.assertEqual(beuken.owner_count, 23)

    def test_separate_bank_accounts(self):
        for vme in self.vmes:
            self.assertTrue(vme.working_capital_bank_id and vme.reserve_capital_bank_id)
            self.assertNotEqual(vme.working_capital_bank_id, vme.reserve_capital_bank_id)

    def test_fictitious_contact_data(self):
        owners = self.env["vme.ownership"].search([("association_id", "in", self.vmes.ids)]).partner_id
        self.assertTrue(all(email.endswith("@example.com") for email in owners.mapped("email")))

    def test_loading_twice_is_refused(self):
        with self.assertRaises(UserError):
            self.env["vme.association"]._load_demo_data()
