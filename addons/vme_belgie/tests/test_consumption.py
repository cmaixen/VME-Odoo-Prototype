from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

Q1_START, Q1_END = date(2026, 1, 1), date(2026, 3, 31)


@tagged("post_install", "-at_install")
class TestConsumption(TransactionCase):
    """Hand-checkable case: A1 600/1000 and A2 400/1000, heating split 30% fixed and 70% by consumption.

    Q1 2026: A1 uses 100 units (one allocator, coefficient 1), A2 uses 300 (150 read × coefficient 2).
    A bill of 1000: fixed 300 → A1 180, A2 120; variable 700 → A1 175, A2 525.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Verbruik"})
        cls.env.cr.precommit.run()  # load the chart of accounts, as a real save would
        cls.company = cls.vme.company_id
        cls.a1, cls.a2 = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.key = cls.env["vme.key"].create({
            "name": "Verwarming op verbruik", "association_id": cls.vme.id, "key_type": "consumption",
            "meter_type": "heating", "fixed_percent": 30, "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in ((cls.a1, 600), (cls.a2, 400))],
        })
        Partner = cls.env["res.partner"]
        cls.owner_1, cls.seller, cls.buyer = Partner.create([{"name": n} for n in ("Eigenaar V1", "Verkoper V2", "Koper V2")])
        cls.env["vme.ownership"].create([
            {"lot_id": cls.a1.id, "partner_id": cls.owner_1.id, "date_start": date(2015, 1, 1)},
            {"lot_id": cls.a2.id, "partner_id": cls.seller.id, "date_start": date(2015, 1, 1)},
        ])
        cls.meter_1, cls.meter_2 = cls.env["vme.meter"].create([
            {"name": "KV-A1", "lot_id": cls.a1.id, "meter_type": "heating", "factor": 1.0},
            {"name": "KV-A2", "lot_id": cls.a2.id, "meter_type": "heating", "factor": 2.0},
        ])
        cls.env["vme.meter.reading"].create([
            {"meter_id": cls.meter_1.id, "date": date(2025, 12, 31), "value": 1000},
            {"meter_id": cls.meter_1.id, "date": Q1_END, "value": 1100},
            {"meter_id": cls.meter_2.id, "date": date(2025, 12, 31), "value": 500},
            {"meter_id": cls.meter_2.id, "date": Q1_END, "value": 650},
        ])
        cls.supplier = Partner.create({"name": "Gasleverancier Test", "is_company": True})

    def _bill(self, price, move_type="in_invoice", taxes=False, start=Q1_START, end=Q1_END):
        return self.env["account.move"].with_company(self.company).create({
            "move_type": move_type,
            "partner_id": self.supplier.id,
            "invoice_date": end,
            "vme_period_start": start,
            "vme_period_end": end,
            "invoice_line_ids": [Command.create({
                "name": "Aardgas centrale verwarming", "quantity": 1, "price_unit": price,
                "tax_ids": [Command.set(taxes.ids)] if taxes else [Command.clear()],
                "vme_key_id": self.key.id,
            })],
        })

    def _sell_a2(self, deed_date):
        self.a2.ownership_ids.date_end = date.fromordinal(deed_date.toordinal() - 1)
        self.env["vme.ownership"].create({"lot_id": self.a2.id, "partner_id": self.buyer.id, "date_start": deed_date})

    def _by_partner(self, allocations, field="amount"):
        result = {}
        for allocation in allocations:
            result[allocation.partner_id] = round(result.get(allocation.partner_id, 0.0) + allocation[field], 3)
        return result

    # --- Meters and readings ---

    def test_index_interpolated_per_day(self):
        # 31/12 → 31/03 is 90 days, 100 units: 31/01 is 31 days in.
        self.assertAlmostEqual(self.meter_1._index_at(date(2026, 1, 31)), 1000 + 100 * 31 / 90)
        self.assertEqual(self.meter_1._index_at(Q1_END), 1100)
        self.assertEqual(self.meter_2._consumption(Q1_START, Q1_END), 300)  # 150 × coefficient 2

    def test_readings_only_go_up(self):
        with self.assertRaises(ValidationError):
            self.env["vme.meter.reading"].create({"meter_id": self.meter_1.id, "date": date(2026, 2, 15), "value": 1200})
        with self.assertRaises(ValidationError):
            self.env["vme.meter.reading"].create({"meter_id": self.meter_1.id, "date": date(2026, 4, 30), "value": 1050})

    def test_fixed_percent_between_0_and_100(self):
        with self.assertRaises(ValidationError):
            self.key.fixed_percent = 120

    # --- Distribution fixed / variable ---

    def test_fixed_and_variable(self):
        allocations = self._bill(1000)._vme_distribute()
        amounts = self._by_partner(allocations)
        self.assertEqual(amounts, {self.owner_1: 355.0, self.seller: 645.0})
        a1 = allocations.filtered(lambda a: a.lot_id == self.a1)
        self.assertEqual((a1.fixed_amount, a1.variable_amount, a1.consumption), (180.0, 175.0, 100.0))
        a2 = allocations.filtered(lambda a: a.lot_id == self.a2)
        self.assertEqual((a2.fixed_amount, a2.variable_amount, a2.consumption), (120.0, 525.0, 300.0))

    def test_sum_is_bill_total(self):
        taxes = self.company.account_purchase_tax_id
        bill = self._bill(1234.57, taxes=taxes)
        allocations = bill._vme_distribute()
        self.assertAlmostEqual(sum(allocations.mapped("amount")), bill.amount_total, places=2)
        for allocation in allocations:
            self.assertAlmostEqual(allocation.amount, allocation.fixed_amount + allocation.variable_amount, places=2)

    def test_all_fixed_needs_no_readings(self):
        self.key.fixed_percent = 100
        self.meter_2.reading_ids.filtered(lambda r: r.date == Q1_END).unlink()
        amounts = self._by_partner(self._bill(1000)._vme_distribute())
        self.assertEqual(amounts, {self.owner_1: 600.0, self.seller: 400.0})

    def test_all_variable(self):
        self.key.fixed_percent = 0
        amounts = self._by_partner(self._bill(1000)._vme_distribute())
        self.assertEqual(amounts, {self.owner_1: 250.0, self.seller: 750.0})

    def test_credit_note(self):
        allocations = self._bill(1000, move_type="in_refund")._vme_distribute()
        self.assertEqual(self._by_partner(allocations), {self.owner_1: -355.0, self.seller: -645.0})

    # --- Missing data ---

    def test_missing_reading_is_refused(self):
        self.meter_2.reading_ids.filtered(lambda r: r.date == Q1_END).unlink()
        with self.assertRaisesRegex(UserError, "Ontbrekende meterstand.*KV-A2"):
            self._bill(1000)._vme_distribute()

    def test_period_after_last_reading_is_refused(self):
        with self.assertRaisesRegex(UserError, "KV-A1"):
            self._bill(1000, start=date(2026, 4, 1), end=date(2026, 6, 30))._vme_distribute()

    def test_lot_without_meter_is_refused(self):
        self.meter_2.active = False
        with self.assertRaisesRegex(UserError, "Geen teller.*A2"):
            self._bill(1000)._vme_distribute()

    def test_no_consumption_is_refused(self):
        self.meter_1.reading_ids.filtered(lambda r: r.date == Q1_END).value = 1000
        self.meter_2.reading_ids.filtered(lambda r: r.date == Q1_END).value = 500
        with self.assertRaisesRegex(UserError, "geen verbruik"):
            self._bill(1000)._vme_distribute()

    def test_posting_with_missing_reading_keeps_bill_posted(self):
        self.meter_2.reading_ids.filtered(lambda r: r.date == Q1_END).unlink()
        bill = self._bill(1000)
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(bill.vme_allocation_ids)
        self.assertTrue(any("Ontbrekende meterstand" in body for body in bill.message_ids.mapped("body")))

    # --- Sale in the cost period ---

    def test_sale_without_reading_at_deed(self):
        """Deed on 16/02: the seller owned A2 for 46 of 90 days, the buyer 44; consumption pro rata per day."""
        self._sell_a2(date(2026, 2, 16))
        allocations = self._bill(1000)._vme_distribute()
        consumption = self._by_partner(allocations, "consumption")
        self.assertAlmostEqual(consumption[self.seller], 300 * 46 / 90, places=3)
        self.assertAlmostEqual(consumption[self.buyer], 300 * 44 / 90, places=3)
        self.assertEqual(self._by_partner(allocations, "variable_amount"),
                         {self.owner_1: 175.0, self.seller: 268.33, self.buyer: 256.67})
        self.assertEqual(self._by_partner(allocations, "fixed_amount"),
                         {self.owner_1: 180.0, self.seller: 61.33, self.buyer: 58.67})

    def test_sale_with_reading_at_deed(self):
        """A reading on the day before the deed gives the real consumption: 50 × 2 for the seller, 100 × 2 for the buyer."""
        self._sell_a2(date(2026, 2, 16))
        self.env["vme.meter.reading"].create({"meter_id": self.meter_2.id, "date": date(2026, 2, 15), "value": 550})
        allocations = self._bill(1000)._vme_distribute()
        self.assertEqual(self._by_partner(allocations, "consumption"),
                         {self.owner_1: 100.0, self.seller: 100.0, self.buyer: 200.0})
        self.assertEqual(self._by_partner(allocations, "variable_amount"),
                         {self.owner_1: 175.0, self.seller: 175.0, self.buyer: 350.0})
        self.assertAlmostEqual(sum(allocations.mapped("amount")), 1000, places=2)

    def test_annual_statement_shows_consumption(self):
        bill = self._bill(1000)
        bill.action_post()
        data = self.vme._get_annual_statement(2026)
        self.assertTrue(data["is_complete"])
        by_partner = {st["partner"]: st for st in data["statements"]}
        key = by_partner[self.seller]["keys"][0]
        self.assertEqual(key["amount"], 645.0)
        self.assertEqual(key["consumption"], {"used": 300.0, "unit": "eenheden", "fixed": 120.0, "variable": 525.0})


@tagged("post_install", "-at_install")
class TestMeterImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Meteropname"})
        cls.lots = cls.env["vme.lot"].create([{"association_id": cls.vme.id, "name": n} for n in ("A1", "A2")])
        cls.meter = cls.env["vme.meter"].create({"name": "W-A1", "lot_id": cls.lots[0].id, "meter_type": "water"})
        cls.env["vme.meter.reading"].create({"meter_id": cls.meter.id, "date": date(2025, 12, 31), "value": 120})
        cls.Wizard = cls.env["vme.meter.import.wizard"]

    def _csv(self, *rows):
        return ("\n".join(["kavel;teller;soort;datum;stand;coefficient"] + list(rows)) + "\n").encode()

    def test_check_writes_nothing(self):
        raw = self._csv("A1;W-A1;water;31/03/2026;130,5;", "A2;KV-A2-1;verwarming;31/03/2026;80;1,25")
        plan, messages = self.Wizard._check_file(self.vme, raw)
        self.assertFalse([m for m in messages if m[0] == "error"])
        self.assertEqual(len(plan["rows"]), 2)
        self.assertIn("KV-A2-1", plan["new_meters"])
        self.assertTrue(any("nieuw" in m[2] for m in messages if m[0] == "warning"))
        self.assertFalse(self.env["vme.meter"].search([("name", "=", "KV-A2-1")]))
        self.assertEqual(len(self.meter.reading_ids), 1)

    def test_errors(self):
        raw = self._csv(
            "A9;W-A9;water;31/03/2026;10;",         # unknown lot
            "A1;W-A1;gas;31/03/2026;130;",           # unknown type
            "A1;W-A1;water;31/13/2026;130;",         # invalid date
            "A1;W-A1;water;30/06/2026;abc;",         # invalid reading
            "A1;W-A1;water;31/03/2026;110;",         # lower than the reading of 31/12/2025
            "A2;W-A1;water;30/09/2026;150;",         # meter of another lot
        )
        plan, messages = self.Wizard._check_file(self.vme, raw)
        errors = sorted(m[1] for m in messages if m[0] == "error")
        self.assertEqual(errors, [2, 3, 4, 5, 6, 7])
        with self.assertRaises(UserError):
            self.Wizard._import_file(self.vme, raw, "fout.csv")
        self.assertEqual(len(self.meter.reading_ids), 1)

    def test_missing_column(self):
        _plan, messages = self.Wizard._check_file(self.vme, b"kavel;teller;datum;stand\nA1;W-A1;31/03/2026;130\n")
        self.assertEqual(messages[0][0], "error")
        self.assertIn("soort", messages[0][2])

    def test_import_and_import_again(self):
        raw = self._csv("A1;W-A1;water;31/03/2026;130,5;", "A2;KV-A2-1;verwarming;2026-03-31;80;1,25")
        readings = self.Wizard._import_file(self.vme, raw, "opname.csv")
        self.assertEqual(len(readings), 2)
        new_meter = self.env["vme.meter"].search([("name", "=", "KV-A2-1")])
        self.assertEqual((new_meter.lot_id, new_meter.meter_type, new_meter.factor), (self.lots[1], "heating", 1.25))
        self.assertEqual(self.meter.last_reading_value, 130.5)
        # The same file again: nothing new, no error.
        plan, messages = self.Wizard._check_file(self.vme, raw)
        self.assertFalse(plan["rows"])
        self.assertFalse([m for m in messages if m[0] == "error"])
        # Another value for a date that is already read in is an error.
        _plan, messages = self.Wizard._check_file(self.vme, self._csv("A1;W-A1;water;31/03/2026;131;"))
        self.assertEqual([m[0] for m in messages if m[1] == 2], ["error"])

    def test_wizard_dry_run_then_import(self):
        import base64
        wizard = self.Wizard.create({
            "association_id": self.vme.id, "filename": "opname.csv",
            "data_file": base64.b64encode(self._csv("A1;W-A1;water;31/03/2026;130;")),
        })
        wizard.action_check()
        self.assertEqual((wizard.state, wizard.error_count), ("checked", 0))
        self.assertIn("Geen fouten", wizard.report_html)
        action = wizard.action_import()
        self.assertEqual(len(action["domain"][0][2]), 1)
