from datetime import date

from freezegun import freeze_time

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = "2026-11-05"


@tagged("post_install", "-at_install")
@freeze_time(TODAY)
class TestInstallations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Keuring"})
        Partner = cls.env["res.partner"]
        cls.edtc, cls.maintenance, cls.other = Partner.create([
            {"name": "EDTC Test", "is_company": True},
            {"name": "Liftfirma Test", "is_company": True},
            {"name": "Andere leverancier", "is_company": True},
        ])
        cls.lift = cls.env["vme.installation"].create({
            "association_id": cls.vme.id, "name": "Lift test", "installation_type": "elevator",
            "inspection_partner_id": cls.edtc.id, "maintenance_partner_id": cls.maintenance.id,
        })

    def _inspection(self, installation, when, kind="inspection", result="compliant", remarks=()):
        return self.env["vme.inspection"].create({
            "installation_id": installation.id, "date": when, "kind": kind, "result": result,
            "remark_ids": [Command.create(r) for r in remarks],
        })

    def test_default_interval_and_due_date(self):
        self.assertEqual(self.lift.inspection_interval_months, 6)
        self.assertEqual(self.lift.due_state, "unknown")
        self._inspection(self.lift, date(2026, 5, 12))
        self.assertEqual(self.lift.last_inspection_date, date(2026, 5, 12))
        self.assertEqual(self.lift.next_inspection_date, date(2026, 11, 12))
        extinguishers = self.env["vme.installation"].create({
            "association_id": self.vme.id, "name": "Blussers", "installation_type": "fire_extinguishers",
        })
        self.assertEqual(extinguishers.inspection_interval_months, 12)
        extinguishers.inspection_interval_months = 24  # adjustable per installation
        self._inspection(extinguishers, date(2026, 1, 1))
        self.assertEqual(extinguishers.next_inspection_date, date(2028, 1, 1))

    def test_due_state_boundaries(self):
        cases = {
            date(2026, 5, 4): "overdue",   # due 04-11-2026, yesterday
            date(2026, 5, 5): "due_30",    # due today
            date(2026, 6, 5): "due_30",    # due in 30 days
            date(2026, 6, 6): "due_60",    # due in 31 days
            date(2026, 8, 3): "due_90",    # due in 90 days
            date(2026, 8, 4): "ok",        # due in 91 days
        }
        for inspection_date, expected in cases.items():
            installation = self.env["vme.installation"].create({
                "association_id": self.vme.id, "name": f"Lift {inspection_date}", "installation_type": "elevator",
            })
            self._inspection(installation, inspection_date)
            self.assertEqual(installation.due_state, expected, inspection_date)

    def test_maintenance_visit_does_not_count_and_risk_analysis(self):
        self._inspection(self.lift, date(2026, 3, 1))
        self._inspection(self.lift, date(2026, 9, 1), kind="maintenance")
        self._inspection(self.lift, date(2012, 1, 15), kind="risk_analysis")
        self.assertEqual(self.lift.last_inspection_date, date(2026, 3, 1))
        self.assertEqual(self.lift.next_risk_analysis_date, date(2027, 1, 15))
        self.assertEqual(self.lift.risk_analysis_due_state, "due_90")

    def test_retest_required(self):
        self._inspection(self.lift, date(2026, 5, 12), result="non_compliant")
        self.assertTrue(self.lift.retest_required)
        self._inspection(self.lift, date(2026, 6, 20), kind="retest", result="compliant")
        self.assertFalse(self.lift.retest_required)

    def test_cron_creates_one_task_per_due_date(self):
        self._inspection(self.lift, date(2026, 5, 12))  # due 12-11-2026
        Installation = self.env["vme.installation"]
        Installation._cron_schedule_inspection_activities()
        Installation._cron_schedule_inspection_activities()
        self.assertEqual(len(self.lift.activity_ids), 1)
        self.assertEqual(self.lift.activity_ids.date_deadline, date(2026, 11, 12))
        # A new inspection moves the due date beyond 60 days: no new task.
        self._inspection(self.lift, date(2026, 11, 1))
        Installation._cron_schedule_inspection_activities()
        self.assertEqual(len(self.lift.activity_ids), 1)
        # A due date that moves back within 60 days gets exactly one more task.
        self.lift.inspection_interval_months = 1  # due 01-12-2026, within 60 days
        Installation._cron_schedule_inspection_activities()
        Installation._cron_schedule_inspection_activities()
        self.assertEqual(len(self.lift.activity_ids), 2)

    def test_remarks_follow_up(self):
        inspection = self._inspection(self.lift, date(2026, 5, 12), result="remarks", remarks=[
            {"name": "Noodverlichting kooi", "severity": "major", "deadline": date(2026, 8, 31)},
            {"name": "Smering geleiders", "severity": "minor", "deadline": date(2026, 12, 31)},
        ])
        late, later = inspection.remark_ids.sorted("deadline")
        self.assertTrue(late.is_overdue)
        self.assertFalse(later.is_overdue)
        self.assertEqual((self.lift.open_remark_count, self.lift.overdue_remark_count), (2, 1))
        Remark = self.env["vme.inspection.remark"]
        self.assertEqual(Remark.search([("installation_id", "=", self.lift.id), ("is_overdue", "=", True)]), late)
        self.assertEqual(Remark.search([("installation_id", "=", self.lift.id), ("is_overdue", "=", False)]), later)
        self.assertEqual(Remark.search([("installation_id", "=", self.lift.id), ("is_overdue", "!=", True)]), later)
        late.state = "resolved"
        self.assertEqual(late.resolved_date, date(2026, 11, 5))
        self.assertFalse(late.is_overdue)
        self.assertEqual(self.lift.open_remark_count, 1)
        self.assertFalse(Remark.search([("installation_id", "=", self.lift.id), ("is_overdue", "=", True)]))


@tagged("post_install", "-at_install")
@freeze_time(TODAY)
class TestInspectionInvoices(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Factuurkeuring"})
        cls.env.cr.precommit.run()  # chart of accounts
        lot = cls.env["vme.lot"].create({"association_id": cls.vme.id, "name": "A1"})
        owner = cls.env["res.partner"].create({"name": "Eigenaar Keuring"})
        cls.env["vme.ownership"].create({"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)})
        cls.key = cls.env["vme.key"].create({
            "name": "Lift", "association_id": cls.vme.id, "key_type": "elevator", "total_shares": 1000,
            "line_ids": [Command.create({"lot_id": lot.id, "shares": 1000})],
        })
        cls.edtc, cls.other = cls.env["res.partner"].create([
            {"name": "EDTC Factuur", "is_company": True},
            {"name": "Andere Factuur", "is_company": True},
        ])
        cls.lift = cls.env["vme.installation"].create({
            "association_id": cls.vme.id, "name": "Lift", "installation_type": "elevator",
            "inspection_partner_id": cls.edtc.id,
        })
        cls.env["vme.inspection"].create({"installation_id": cls.lift.id, "date": date(2026, 5, 12)})
        for partner in (cls.edtc, cls.other):
            cls.env["vme.distribution.rule"].create({
                "association_id": cls.vme.id, "partner_id": partner.id, "key_id": cls.key.id,
                "installation_id": cls.lift.id,
            })

    def _post_bill(self, partner, when=date(2026, 11, 3)):
        bill = self.env["account.move"].with_company(self.vme.company_id).create({
            "move_type": "in_invoice", "partner_id": partner.id, "invoice_date": when,
            "invoice_line_ids": [Command.create({"name": "Preventieve inspectie lift", "price_unit": 180,
                                                 "tax_ids": [Command.clear()]})],
        })
        bill.action_post()
        return bill

    def test_bill_of_inspection_body_registers_inspection(self):
        bill = self._post_bill(self.edtc)
        inspection = self.lift.inspection_ids.filtered(lambda i: i.move_id == bill)
        self.assertEqual(len(inspection), 1)
        self.assertEqual(self.lift.last_inspection_date, date(2026, 11, 3))
        self.assertEqual(self.lift.next_inspection_date, date(2027, 5, 3))
        self.assertTrue(bill.vme_allocation_ids)  # still distributed as before
        # Processing the same bill again does not duplicate the inspection.
        bill._vme_register_inspections()
        self.assertEqual(len(self.lift.inspection_ids.filtered(lambda i: i.move_id == bill)), 1)

    def test_bill_of_other_supplier_does_not(self):
        self._post_bill(self.other)
        self.assertEqual(self.lift.last_inspection_date, date(2026, 5, 12))
        self.assertEqual(len(self.lift.inspection_ids), 1)
