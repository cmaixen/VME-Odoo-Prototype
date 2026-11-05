from datetime import date

from freezegun import freeze_time

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.vme_contract import add_months_to_period_end, notice_deadline

TODAY = "2026-11-05"


@tagged("post_install", "-at_install")
@freeze_time(TODAY)
class TestContracts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme = cls.env["vme.association"].create({"name": "Residentie Contract"})
        cls.supplier = cls.env["res.partner"].create({"name": "Schoonmaak Test", "is_company": True})
        cls.todo = cls.env.ref("mail.mail_activity_data_todo")

    def _contract(self, **vals):
        return self.env["vme.contract"].create({
            "association_id": self.vme.id, "name": "Schoonmaak", "contract_type": "cleaning",
            "partner_id": self.supplier.id, **vals,
        })

    def _tasks(self, contract):
        return contract.activity_ids.filtered(lambda a: a.activity_type_id == self.todo)

    def test_notice_deadline_counts_back_from_next_period(self):
        cases = [
            (date(2027, 3, 31), 3, date(2026, 12, 31)),
            (date(2026, 12, 31), 1, date(2026, 11, 30)),
            (date(2027, 2, 28), 3, date(2026, 11, 30)),  # not 28 November
            (date(2027, 6, 30), 6, date(2026, 12, 31)),
            (date(2027, 6, 15), 2, date(2027, 4, 15)),   # mid-month end date
            (date(2028, 2, 29), 12, date(2027, 2, 28)),  # leap day
        ]
        for period_end, months, expected in cases:
            self.assertEqual(notice_deadline(period_end, months), expected, (period_end, months))
        self.assertFalse(notice_deadline(False, 3))
        self.assertFalse(notice_deadline(date(2027, 3, 31), 0))

    def test_renewal_keeps_month_ends(self):
        self.assertEqual(add_months_to_period_end(date(2026, 12, 31), 12), date(2027, 12, 31))
        self.assertEqual(add_months_to_period_end(date(2027, 2, 28), 12), date(2028, 2, 29))
        self.assertEqual(add_months_to_period_end(date(2026, 11, 30), 3), date(2027, 2, 28))

    def test_default_notice_period_per_type(self):
        insurance = self._contract(contract_type="insurance", date_end=date(2027, 3, 31))
        energy = self._contract(contract_type="energy", date_end=date(2027, 3, 31))
        self.assertEqual(insurance.notice_period_months, 3)
        self.assertEqual(insurance.notice_deadline, date(2026, 12, 31))
        self.assertEqual(energy.notice_period_months, 1)
        self.assertEqual(energy.notice_deadline, date(2027, 2, 28))
        energy.notice_period_months = 2  # adjustable per contract
        self.assertEqual(energy.notice_deadline, date(2027, 1, 31))

    def test_notice_state_boundaries(self):
        cases = {
            date(2026, 11, 4): "passed",  # yesterday
            date(2026, 11, 5): "due_30",  # today is still in time
            date(2026, 12, 5): "due_30",
            date(2026, 12, 6): "due_60",
            date(2027, 2, 3): "due_90",
            date(2027, 2, 4): "ok",
        }
        for deadline, expected in cases.items():
            # One month notice: the period ends one month after the deadline.
            contract = self._contract(notice_period_months=1, date_end=add_months_to_period_end(deadline, 1))
            self.assertEqual(contract.notice_deadline, deadline)
            self.assertEqual(contract.notice_state, expected, deadline)
        self.assertEqual(self._contract(date_end=False).notice_state, "none")

    def test_cron_creates_one_task_per_notice_deadline(self):
        contract = self._contract(date_end=date(2026, 12, 31), notice_period_months=1)  # deadline 30-11-2026
        later = self._contract(date_end=date(2027, 6, 30), notice_period_months=3)  # deadline 31-03-2027
        Contract = self.env["vme.contract"]
        Contract._cron_schedule_contract_activities()
        Contract._cron_schedule_contract_activities()
        tasks = self._tasks(contract)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.date_deadline, date(2026, 11, 30))
        self.assertIn("Schoonmaak Test", tasks.note)
        self.assertFalse(self._tasks(later))
        # A new deadline (the period was changed) gets a new task, once.
        contract.date_end = date(2027, 1, 31)
        Contract._cron_schedule_contract_activities()
        Contract._cron_schedule_contract_activities()
        self.assertEqual(len(self._tasks(contract)), 2)

    def test_cron_skips_passed_ended_and_open_ended_contracts(self):
        passed = self._contract(date_end=date(2026, 12, 31), notice_period_months=3)  # deadline 30-09-2026
        notice_given = self._contract(date_end=date(2026, 12, 31), notice_period_months=1)
        notice_given.action_give_notice()
        staff = self._contract(contract_type="staff", date_end=False, auto_renew=False)
        self.env["vme.contract"]._cron_schedule_contract_activities()
        for contract in (passed, notice_given, staff):
            self.assertFalse(self._tasks(contract), contract.name)
        self.assertEqual(passed.notice_state, "passed")

    def test_cron_renews_or_ends_expired_contracts(self):
        renewing = self._contract(date_end=date(2026, 10, 31), notice_period_months=1)
        two_years_late = self._contract(date_end=date(2024, 12, 31), renewal_months=12)
        fixed = self._contract(date_end=date(2026, 10, 31), auto_renew=False)
        cancelled = self._contract(date_end=date(2026, 10, 31))
        cancelled.state = "notice_given"
        self.env["vme.contract"]._cron_schedule_contract_activities()
        self.assertEqual(renewing.date_end, date(2027, 10, 31))
        self.assertEqual(renewing.notice_deadline, date(2027, 9, 30))
        self.assertEqual(renewing.state, "running")
        self.assertEqual(two_years_late.date_end, date(2026, 12, 31))
        self.assertEqual(fixed.state, "ended")
        self.assertEqual(cancelled.state, "ended")

    def test_give_notice(self):
        contract = self._contract(date_end=date(2026, 12, 31), notice_period_months=1)
        self.env["vme.contract"]._cron_schedule_contract_activities()
        self.assertEqual(len(self._tasks(contract)), 1)
        contract.action_give_notice()
        self.assertFalse(self._tasks(contract))  # the notice task is marked done
        self.assertEqual(contract.state, "notice_given")
        self.assertEqual(contract.notice_given_date, date(2026, 11, 5))
        self.assertEqual(contract.notice_state, "none")
        with self.assertRaises(UserError):
            contract.action_give_notice()
        late = self._contract(date_end=date(2026, 12, 31), notice_period_months=3)
        late.action_give_notice()
        self.assertIn("na de opzegtermijn", late.message_ids[0].body)
        contract.action_reopen()
        self.assertEqual(contract.state, "running")
        self.assertFalse(contract.notice_given_date)

    def test_yearly_evaluation(self):
        contract = self._contract(date_start=date(2025, 1, 1), date_end=date(2027, 12, 31))
        self.assertEqual(contract.next_evaluation_date, date(2026, 1, 1))  # never evaluated: overdue
        self.env["vme.contract.evaluation"].create({
            "contract_id": contract.id, "date": date(2025, 11, 20), "rating": "sufficient", "outcome": "tender",
        })
        self.assertEqual(contract.last_evaluation_date, date(2025, 11, 20))
        self.assertEqual(contract.next_evaluation_date, date(2026, 11, 20))
        Contract = self.env["vme.contract"]
        Contract._cron_schedule_contract_activities()
        Contract._cron_schedule_contract_activities()
        tasks = self._tasks(contract)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks.date_deadline, date(2026, 11, 20))
        self.assertIn("evaluatie", tasks.summary.lower())

    def test_distribution_rule_and_bills(self):
        key = self.env["vme.key"].create({"name": "Algemeen", "association_id": self.vme.id, "key_type": "general"})
        contract = self._contract(date_end=date(2027, 12, 31))
        self.assertFalse(contract.distribution_rule_id)
        rule = self.env["vme.distribution.rule"].create({
            "association_id": self.vme.id, "partner_id": self.supplier.id, "key_id": key.id,
        })
        contract.invalidate_recordset(["distribution_rule_id", "distribution_key_id"])
        self.assertEqual(contract.distribution_rule_id, rule)
        self.assertEqual(contract.distribution_key_id, key)
        self.assertEqual(contract.billed_this_year, 0)
        action = contract.action_open_bills()
        self.assertIn(("company_id", "=", self.vme.company_id.id), action["domain"])

    def test_installation_maintenance_contract(self):
        lift = self.env["vme.installation"].create({
            "association_id": self.vme.id, "name": "Lift", "installation_type": "elevator",
        })
        self.assertFalse(lift.maintenance_contract_id)
        contract = self._contract(contract_type="elevator", installation_id=lift.id, date_end=date(2027, 12, 31))
        self.assertEqual(contract.notice_period_months, 6)
        self.assertEqual(lift.maintenance_contract_id, contract)
        self.assertEqual(lift.maintenance_contract_end, date(2027, 12, 31))
        contract.action_end()
        self.assertFalse(lift.maintenance_contract_id)
