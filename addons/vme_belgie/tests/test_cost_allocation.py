from datetime import date

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..models.allocation_tools import largest_remainder

YEAR_START, YEAR_END = date(2026, 1, 1), date(2026, 12, 31)


@tagged("post_install", "-at_install")
class TestCostAllocation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Verdeling"})
        cls.env.cr.precommit.run()  # load the chart of accounts, as a real save would
        cls.company = cls.vme.company_id
        cls.lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": name} for name in ("A1", "A2", "A3")
        ])
        cls.key = cls.env["vme.key"].create({
            "name": "Algemeen",
            "association_id": cls.vme.id,
            "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s})
                         for lot, s in zip(cls.lots, (500, 300, 200))],
        })
        Partner = cls.env["res.partner"]
        cls.owner_1, cls.owner_2, cls.seller, cls.buyer = Partner.create([
            {"name": n} for n in ("Eigenaar T1", "Eigenaar T2", "Verkoper T3", "Koper T3")
        ])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.lots[0].id, "partner_id": cls.owner_1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[1].id, "partner_id": cls.owner_2.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.lots[2].id, "partner_id": cls.seller.id,
             "date_start": date(2015, 1, 1), "date_end": date(2026, 6, 30)},
            {"lot_id": cls.lots[2].id, "partner_id": cls.buyer.id, "date_start": date(2026, 7, 1)},
        ])
        cls.supplier = Partner.create({"name": "Energieleverancier Test", "is_company": True})

    def _bill(self, price, key=None, taxes=False, move_type="in_invoice", start=YEAR_START, end=YEAR_END):
        return self.env["account.move"].with_company(self.company).create({
            "move_type": move_type,
            "partner_id": self.supplier.id,
            "invoice_date": date(2026, 12, 31),
            "vme_period_start": start,
            "vme_period_end": end,
            "invoice_line_ids": [Command.create({
                "name": "Elektriciteit gemene delen",
                "quantity": 1,
                "price_unit": price,
                "tax_ids": [Command.set(taxes.ids)] if taxes else [Command.clear()],
                "vme_key_id": (key or self.key).id,
            })],
        })

    def _amount_by_partner(self, allocations):
        result = {}
        for allocation in allocations:
            result[allocation.partner_id] = round(result.get(allocation.partner_id, 0.0) + allocation.amount, 2)
        return result

    def test_largest_remainder(self):
        self.assertEqual(largest_remainder(100, [1, 1, 1], 2), [33.34, 33.33, 33.33])
        self.assertEqual(largest_remainder(-100, [1, 1, 1], 2), [-33.34, -33.33, -33.33])
        self.assertEqual(sum(largest_remainder(1000, [7, 11, 13])), 1000)

    def test_bill_belongs_to_vme_of_its_company(self):
        bill = self._bill(1000)
        self.assertEqual(bill.vme_association_id, self.vme)

    def test_purchase_journal_has_default_expense_account(self):
        journal = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "purchase")], limit=1
        )
        # Account codes are company-dependent in Odoo 19.
        self.assertEqual(journal.default_account_id.with_company(self.company).code, "611000")
        self.assertEqual(self._bill(10).invoice_line_ids.account_id, journal.default_account_id)

    def test_period_defaults_to_invoice_date(self):
        bill = self.env["account.move"].with_company(self.company).create({
            "move_type": "in_invoice", "partner_id": self.supplier.id, "invoice_date": date(2026, 3, 15),
        })
        self.assertEqual((bill.vme_period_start, bill.vme_period_end), (date(2026, 3, 15), date(2026, 3, 15)))

    def test_full_year_with_sale(self):
        bill = self._bill(1000)
        allocations = bill._vme_distribute()
        amounts = self._amount_by_partner(allocations)
        self.assertEqual(amounts[self.owner_1], 500.0)
        self.assertEqual(amounts[self.owner_2], 300.0)
        # Lot A3 (200) sold on 30 June: 181 days seller, 184 days buyer.
        self.assertEqual(amounts[self.seller], round(200 * 181 / 365, 2))
        self.assertEqual(round(amounts[self.seller] + amounts[self.buyer], 2), 200.0)
        seller_line = allocations.filtered(lambda a: a.partner_id == self.seller)
        self.assertEqual((seller_line.date_from, seller_line.date_to, seller_line.days),
                         (YEAR_START, date(2026, 6, 30), 181))
        self.assertEqual(round(sum(allocations.mapped("amount")), 2), 1000.0)

    def test_rounding_sums_exactly(self):
        equal_key = self.env["vme.key"].create({
            "name": "Gelijk", "association_id": self.vme.id, "total_shares": 3,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 1}) for lot in self.lots],
        })
        bill = self._bill(100, key=equal_key, start=date(2026, 1, 1), end=date(2026, 1, 31))
        allocations = bill._vme_distribute()
        self.assertEqual(sorted(allocations.mapped("amount"), reverse=True), [33.34, 33.33, 33.33])

    def test_amount_includes_vat(self):
        tax = self.company.account_purchase_tax_id
        self.assertTrue(tax, "The Belgian chart should provide a default purchase tax")
        bill = self._bill(1000, taxes=tax)
        allocations = bill._vme_distribute()
        self.assertAlmostEqual(sum(allocations.mapped("amount")), bill.amount_total, places=2)
        self.assertGreater(bill.amount_total, 1000)

    def test_credit_note_is_negative(self):
        refund = self._bill(100, move_type="in_refund", start=date(2026, 1, 1), end=date(2026, 1, 1))
        allocations = refund._vme_distribute()
        self.assertEqual(round(sum(allocations.mapped("amount")), 2), -100.0)
        self.assertTrue(all(a.amount <= 0 for a in allocations))

    def test_redistribute_replaces(self):
        bill = self._bill(1000)
        bill._vme_distribute()
        bill._vme_distribute()
        self.assertEqual(len(bill.vme_allocation_ids), 4)
        self.assertEqual(bill.vme_allocation_owner_count, 4)

    def test_line_without_key_is_refused(self):
        bill = self._bill(1000)
        bill.invoice_line_ids.vme_key_id = False
        with self.assertRaises(UserError):
            bill._vme_distribute()

    def test_lot_without_owner_in_period_is_refused(self):
        lot = self.env["vme.lot"].create({"association_id": self.vme.id, "name": "A4"})
        key = self.env["vme.key"].create({
            "name": "Met lege kavel", "association_id": self.vme.id, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": self.lots[0].id, "shares": 900}),
                         Command.create({"lot_id": lot.id, "shares": 100})],
        })
        with self.assertRaises(UserError):
            self._bill(1000, key=key)._vme_distribute()

    def test_reversed_period_is_refused(self):
        with self.assertRaises(UserError):
            self._bill(1000, start=YEAR_END, end=YEAR_START)._vme_distribute()


@tagged("post_install", "-at_install")
class TestCostAllocationOnDemoData(TransactionCase):

    def test_lift_bill_residentie_linde(self):
        self.env["vme.association"]._load_demo_data()
        self.env.cr.precommit.run()
        linde = self.env["vme.association"].search([("name", "=", "Residentie Linde")])
        lift_key = linde.key_ids.filtered(lambda k: k.key_type == "elevator")
        supplier = self.env["res.partner"].create({"name": "Liftonderhoud Test", "is_company": True})
        bill = self.env["account.move"].with_company(linde.company_id).create({
            "move_type": "in_invoice",
            "partner_id": supplier.id,
            "invoice_date": date(2026, 12, 31),
            "vme_period_start": YEAR_START,
            "vme_period_end": YEAR_END,
            "invoice_line_ids": [Command.create({
                "name": "Onderhoudscontract lift 2026", "price_unit": 777.77,
                "tax_ids": [Command.clear()], "vme_key_id": lift_key.id,
            })],
        })
        allocations = bill._vme_distribute()
        self.assertEqual(round(sum(allocations.mapped("amount")), 2), 777.77)
        self.assertNotIn("garage", allocations.lot_id.mapped("lot_type"))
        a5 = allocations.filtered(lambda a: a.lot_id.name == "A5")
        self.assertEqual(len(a5), 2)
        self.assertEqual(a5.mapped("days"), [181, 184])
