from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.vme_rentmeester.models import rent_rules

# Hand-checkable index series: 100 when the lease is signed, +10% in the year of the freeze, +5% after.
INDEX = {date(2021, 12, 1): 100.0, date(2023, 1, 1): 110.0, date(2024, 1, 1): 115.5}


def lookup(month):
    if month not in INDEX:
        raise rent_rules.IndexMissing(month)
    return INDEX[month]


def index_lease(region, epc, anniversary, request_date=None):
    """Lease of 1000 a month signed 10 January 2022, in force on 1 February 2022."""
    return rent_rules.compute_indexation(region, 1000.0, date(2022, 1, 10), date(2022, 2, 1), anniversary, epc,
                                         lookup, request_date=request_date)


@tagged("post_install", "-at_install")
class TestIndexationRules(TransactionCase):
    """The formula and the energy-label freeze per region, without the database."""

    def test_formula_and_index_months(self):
        values = index_lease("flanders", "C", date(2023, 2, 1))
        # Start index: month before signing; new index: month before the anniversary.
        self.assertEqual(values["start_index_month"], date(2021, 12, 1))
        self.assertEqual(values["new_index_month"], date(2023, 1, 1))
        self.assertEqual(values["new_rent"], 1100.0)
        self.assertEqual(index_lease("flanders", "C", date(2024, 2, 1))["new_rent"], 1155.0)

    def test_flanders_freeze(self):
        # D: half the indexation in the frozen year; the lost half stays out afterwards.
        self.assertEqual(index_lease("flanders", "D", date(2023, 2, 1))["new_rent"], 1047.62)  # 1100 / 1.05
        self.assertEqual(index_lease("flanders", "D", date(2024, 2, 1))["new_rent"], 1100.0)  # 1155 / 1.05
        # E: no indexation in the frozen year, correction factor 1.1 afterwards.
        frozen = index_lease("flanders", "E", date(2023, 2, 1))
        self.assertEqual((frozen["new_rent"], frozen["correction_factor"], frozen["freeze_rate"]), (1000.0, 1.1, 0.0))
        self.assertEqual(index_lease("flanders", "E", date(2024, 2, 1))["new_rent"], 1050.0)  # 1155 / 1.1
        self.assertEqual(index_lease("flanders", "none", date(2024, 2, 1))["new_rent"], 1050.0)

    def test_brussels_freeze(self):
        # Brussels lets label D index fully, E for half, F not at all.
        self.assertEqual(index_lease("brussels", "D", date(2024, 2, 1))["new_rent"], 1155.0)
        self.assertEqual(index_lease("brussels", "E", date(2023, 2, 1))["new_rent"], 1047.62)
        self.assertEqual(index_lease("brussels", "F", date(2023, 2, 1))["new_rent"], 1000.0)
        self.assertEqual(index_lease("brussels", "F", date(2024, 2, 1))["new_rent"], 1050.0)

    def test_wallonia_freeze(self):
        # Wallonia: D and E for half, F and G not at all.
        self.assertEqual(index_lease("wallonia", "D", date(2023, 2, 1))["new_rent"], 1047.62)
        self.assertEqual(index_lease("wallonia", "E", date(2024, 2, 1))["new_rent"], 1100.0)
        self.assertEqual(index_lease("wallonia", "G", date(2024, 2, 1))["new_rent"], 1050.0)
        self.assertEqual(index_lease("wallonia", "C", date(2024, 2, 1))["new_rent"], 1155.0)

    def test_freeze_window_per_region(self):
        """Anniversary 5 October: frozen in 2022 in Flanders, in 2023 in Brussels and Wallonia."""
        series = {date(2021, 8, 1): 100.0, date(2022, 9, 1): 108.0, date(2023, 9, 1): 112.0}
        expected = {"flanders": date(2022, 10, 5), "brussels": date(2023, 10, 5), "wallonia": date(2023, 10, 5)}
        for region, frozen in expected.items():
            factor, anniversary, _rate = rent_rules.freeze_correction(
                region, "F", date(2021, 10, 5), date(2021, 8, 1), series.__getitem__)
            self.assertEqual(anniversary, frozen, region)
        # Flanders lost 2022 (108 / 100), the others 2023 (112 / 108).
        self.assertAlmostEqual(rent_rules.freeze_correction(
            "flanders", "F", date(2021, 10, 5), date(2021, 8, 1), series.__getitem__)[0], 1.08)
        self.assertAlmostEqual(rent_rules.freeze_correction(
            "brussels", "F", date(2021, 10, 5), date(2021, 8, 1), series.__getitem__)[0], 112 / 108)

    def test_lease_after_freeze_has_no_correction(self):
        series = {date(2023, 11, 1): 128.0, date(2024, 12, 1): 131.2}
        values = rent_rules.compute_indexation("flanders", 800.0, date(2023, 12, 15), date(2024, 1, 1),
                                               date(2025, 1, 1), "F", series.__getitem__)
        self.assertEqual((values["correction_factor"], values["freeze_anniversary"]), (1.0, None))
        self.assertEqual(values["new_rent"], 820.0)

    def test_retroactive_limit(self):
        # Asked in time: from the anniversary. Asked late: at most three months back.
        self.assertEqual(index_lease("flanders", "C", date(2024, 2, 1), date(2024, 3, 20))["effective_date"],
                         date(2024, 2, 1))
        for region in ("flanders", "brussels", "wallonia"):
            self.assertEqual(index_lease(region, "C", date(2024, 2, 1), date(2024, 7, 15))["effective_date"],
                             date(2024, 4, 15), region)

    def test_missing_index(self):
        with self.assertRaises(rent_rules.IndexMissing):
            index_lease("flanders", "C", date(2025, 2, 1))

    def test_region_from_zip(self):
        cases = {"1050": "brussels", "1300": "wallonia", "4000": "wallonia", "7000": "wallonia",
                 "1500": "flanders", "2000": "flanders", "9000": "flanders", "": False}
        for zip_code, region in cases.items():
            self.assertEqual(rent_rules.region_from_zip(zip_code), region, zip_code)

    def test_notice(self):
        # Short lease ending 28 February 2027: notice at the latest on 30 November 2026.
        self.assertEqual(rent_rules.notice_deadline(date(2027, 2, 28), "short"), date(2026, 11, 30))
        self.assertEqual(rent_rules.notice_end_date(date(2026, 11, 30), 3), date(2027, 2, 28))
        # Nine years ending 31 August 2028: the landlord gives six months.
        self.assertEqual(rent_rules.notice_deadline(date(2028, 8, 31), "nine", "landlord"), date(2028, 2, 29))
        self.assertEqual(rent_rules.notice_deadline(date(2028, 8, 31), "nine", "tenant"), date(2028, 5, 31))
        # A notice in the middle of a month runs from the first of the next month.
        self.assertEqual(rent_rules.notice_end_date(date(2026, 11, 20), 3), date(2027, 2, 28))


@tagged("post_install", "-at_install")
class TestIndexationContract(TransactionCase):
    """Indexation records on a contract, with the index table in the database."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Index = cls.env["vme.rent.index"]
        for month, value in INDEX.items():
            record = Index.search([("month", "=", month)])
            if record:
                record.value = value
            else:
                Index.create({"month": month, "value": value})
        cls.landlord, cls.tenant = cls.env["res.partner"].create([
            {"name": "Verhuurder Index"}, {"name": "Huurder Index"}])
        cls.contract = cls.env["vme.rent.contract"].create({
            "landlord_id": cls.landlord.id, "tenant_ids": [(6, 0, cls.tenant.ids)], "property_address": "Teststraat 1",
            "region": "flanders", "date_signed": date(2022, 1, 10), "date_start": date(2022, 2, 1),
            "duration_years": 9, "rent": 1000, "epc_label": "E",
        })
        cls.contract.action_activate()

    def test_indexations_follow_each_other(self):
        first = self.contract._create_indexation(date(2023, 2, 1), request_date=date(2023, 1, 20))
        first.action_confirm()
        second = self.contract._create_indexation(date(2024, 2, 1), request_date=date(2024, 1, 20))
        self.assertEqual((first.previous_rent, first.new_rent), (1000.0, 1000.0))
        self.assertEqual((second.previous_rent, second.new_rent, second.increase), (1000.0, 1050.0, 50.0))
        # A draft does not change the rent; a confirmed indexation does, from its effective date.
        self.assertEqual(self.contract._get_rent_on(date(2024, 3, 1)), 1000.0)
        second.action_confirm()
        self.assertEqual(self.contract._get_rent_on(date(2024, 1, 31)), 1000.0)
        self.assertEqual(self.contract._get_rent_on(date(2024, 2, 1)), 1050.0)
        # The same anniversary is never indexed twice.
        self.assertEqual(self.contract._create_indexation(date(2024, 2, 1)), second)

    def test_index_missing_in_table(self):
        with self.assertRaises(UserError):
            self.contract._create_indexation(date(2031, 2, 1))

    def test_oral_or_excluded_lease_is_not_indexed(self):
        self.contract.is_written = False
        with self.assertRaises(UserError):
            self.contract._create_indexation(date(2023, 2, 1))
        self.contract.write({"is_written": True, "indexation_excluded": True})
        with self.assertRaises(UserError):
            self.contract._create_indexation(date(2023, 2, 1))

    def test_deposit_warning_per_region(self):
        self.contract.write({"deposit_amount": 2500, "deposit_type": "blocked_account"})
        self.assertFalse(self.contract.deposit_warning)  # Flanders: three months
        self.contract.region = "brussels"
        self.assertTrue(self.contract.deposit_warning)  # Brussels: two months on a blocked account
        self.contract.deposit_type = "bank_guarantee"
        self.assertFalse(self.contract.deposit_warning)
