from datetime import date, datetime

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged

TODAY = date(2026, 11, 5)


@tagged("post_install", "-at_install")
class TestAssemblyPlanner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Vme = cls.env["vme.association"]
        # Created first and alphabetically first, so a naive planner would serve it first.
        cls.vme_late = Vme.create({"name": "AV Residentie Laat", "assembly_period_month": "3", "assembly_period_day": 16})
        cls.vme_early = Vme.create({"name": "AV Residentie Vroeg", "assembly_period_month": "3", "assembly_period_day": 4})
        cls.room = cls.env["vme.assembly.room"].create({"name": "Zaal Test", "address": "Teststraat 1, Voorbeeldstad"})
        cls.room2 = cls.env["vme.assembly.room"].create({"name": "Zaal Twee"})
        cls.user = new_test_user(cls.env, login="av_medewerker", name="Medewerker Test")
        cls.user.vme_max_assemblies_per_evening = 2
        cls.Slot = cls.env["vme.assembly.slot"]
        cls.Assembly = cls.env["vme.assembly"].with_context(vme_today=TODAY)

    def _slot(self, day, hour=19.0, room=None, online=False, capacity=1, user=None):
        return self.Slot.create({
            "date": day, "time_start": hour, "max_assemblies": capacity,
            "location_type": "online" if online else "room",
            "room_id": False if online else (room or self.room).id,
            "user_id": (user or self.user).id,
        })

    def _assemblies(self, year=2027):
        return self.Assembly._create_missing_assemblies(year, self.vme_late | self.vme_early)

    def _of(self, assemblies, vme):
        return assemblies.filtered(lambda a: a.association_id == vme)

    # Period and model

    def test_period_of_fifteen_days(self):
        start, end = self.vme_late._get_assembly_period(2027)
        self.assertEqual((start, end), (date(2027, 3, 16), date(2027, 3, 30)))
        assembly = self._of(self._assemblies(), self.vme_late)
        self.assertEqual((assembly.period_start, assembly.period_end), (start, end))
        self.assertEqual(assembly.state, "draft")
        self.assertIn("2027", assembly.name)

    def test_invalid_period_is_refused(self):
        with self.assertRaises(ValidationError):
            self.vme_late.write({"assembly_period_month": "2", "assembly_period_day": 29})

    def test_missing_assemblies_created_once(self):
        first = self._assemblies()
        self.assertEqual(len(first), 2)
        self.assertFalse(self._assemblies())
        no_period = self.env["vme.association"].create({"name": "AV Zonder Periode"})
        self.assertFalse(self.Assembly._create_missing_assemblies(2027, no_period))

    # Proposal

    def test_conflict_solved_by_earliest_deadline(self):
        """Both VMEs fit on 17 March; the one whose period ends first gets it."""
        shared = self._slot(date(2027, 3, 17))
        later = self._slot(date(2027, 3, 25))
        assemblies = self._assemblies()
        unplanned = assemblies._propose_schedule(today=TODAY)
        self.assertFalse(unplanned)
        self.assertEqual(self._of(assemblies, self.vme_early).slot_id, shared)
        self.assertEqual(self._of(assemblies, self.vme_late).slot_id, later)
        self.assertEqual(set(assemblies.mapped("state")), {"proposed"})

    def test_no_free_slot_in_period(self):
        self._slot(date(2027, 3, 17))
        assemblies = self._assemblies()
        unplanned = assemblies._propose_schedule(today=TODAY)
        self.assertEqual(unplanned, self._of(assemblies, self.vme_late))
        self.assertEqual(unplanned.state, "draft")
        self.assertIn("Geen vrij blok", unplanned.message_ids[0].body)

    def test_block_with_two_meetings_runs_sequentially(self):
        slot = self._slot(date(2027, 3, 17), hour=18.5, capacity=2)
        assemblies = self._assemblies()
        assemblies._propose_schedule(today=TODAY)
        self.assertEqual(assemblies.slot_id, slot)
        # 18:30 and 20:30 Brussels time (UTC+1 in March).
        starts = sorted(assemblies.mapped("datetime_start"))
        self.assertEqual(starts, [datetime(2027, 3, 17, 17, 30), datetime(2027, 3, 17, 19, 30)])

    def test_employee_limit_per_evening(self):
        self.user.vme_max_assemblies_per_evening = 1
        self._slot(date(2027, 3, 17), hour=18.0)
        second = self._slot(date(2027, 3, 17), hour=20.5, online=True)
        assemblies = self._assemblies()
        unplanned = assemblies._propose_schedule(today=TODAY)
        self.assertEqual(unplanned, self._of(assemblies, self.vme_late))
        with self.assertRaises(ValidationError):
            unplanned.slot_id = second

    def test_full_block_is_refused(self):
        slot = self._slot(date(2027, 3, 17))
        assemblies = self._assemblies()
        assemblies[0].slot_id = slot
        self.assertEqual(assemblies[0].state, "proposed")
        with self.assertRaises(ValidationError):
            assemblies[1].slot_id = slot

    def test_convocation_too_late_skips_block(self):
        """Seven days before the meeting a 15-day convocation can no longer leave in time."""
        self._slot(date(2027, 3, 17))
        assembly = self._of(self._assemblies(), self.vme_early)
        unplanned = assembly._propose_schedule(today=date(2027, 3, 10))
        self.assertEqual(unplanned, assembly)

    def test_confirmed_meetings_are_kept_on_replan(self):
        slot = self._slot(date(2027, 3, 17))
        self._slot(date(2027, 3, 25))
        assemblies = self._assemblies()
        late = self._of(assemblies, self.vme_late)
        late.slot_id = slot
        late.action_confirm()
        wizard = self.env["vme.assembly.planner.wizard"].with_context(vme_today=TODAY).create({
            "year": 2027, "association_ids": [(6, 0, (self.vme_late | self.vme_early).ids)],
        })
        wizard.action_propose()
        self.assertEqual(late.slot_id, slot)
        self.assertEqual(late.state, "confirmed")
        # The early VME lost the shared evening and has no other block within its period.
        self.assertEqual(self._of(assemblies, self.vme_early).state, "draft")

    # Double bookings of blocks

    def test_room_double_booking_is_refused(self):
        self._slot(date(2027, 3, 17), hour=19.0, capacity=2)
        with self.assertRaises(ValidationError):
            self._slot(date(2027, 3, 17), hour=21.0, user=self.env.ref("base.user_admin"))
        # Another room at the same time is fine for another employee.
        self._slot(date(2027, 3, 17), hour=19.0, room=self.room2, user=self.env.ref("base.user_admin"))

    def test_employee_double_booking_is_refused(self):
        self._slot(date(2027, 3, 17), hour=19.0)
        with self.assertRaises(ValidationError):
            self._slot(date(2027, 3, 17), hour=20.0, online=True)

    # Warnings

    def test_warnings_for_unplanned_assembly(self):
        assembly = self._of(self._assemblies(), self.vme_late)
        self.assertEqual(assembly.warning_level, "ok")
        # Last convocation for a meeting on 30 March: 15 March.
        self.assertEqual(assembly.with_context(vme_today=date(2027, 2, 20)).warning_level, "warning")
        late = assembly.with_context(vme_today=date(2027, 3, 16))
        self.assertEqual(late.warning_level, "danger")
        self.assertIn("Niet meer haalbaar", late.warning)
        at_risk = self.Assembly.with_context(vme_today=date(2027, 3, 16)).search([("warning_level", "in", ["danger"])])
        self.assertIn(assembly, at_risk)

    def test_warnings_for_planned_assembly(self):
        assembly = self._of(self._assemblies(), self.vme_late)
        assembly.slot_id = self._slot(date(2027, 3, 25))
        self.assertEqual(assembly.convocation_deadline, date(2027, 3, 10))
        self.assertEqual(assembly.warning_level, "ok")
        late = assembly.with_context(vme_today=date(2027, 3, 11))
        self.assertEqual(late.warning_level, "danger")
        self.assertIn("te laat", late.warning)
        assembly.convocation_sent_date = date(2027, 3, 12)
        self.assertEqual(assembly.warning_level, "danger")
        assembly.convocation_sent_date = date(2027, 3, 1)
        self.assertEqual(late.warning_level, "ok")

    def test_meeting_outside_period_warns(self):
        assembly = self._of(self._assemblies(), self.vme_late)
        assembly.slot_id = self._slot(date(2027, 4, 15))
        self.assertEqual(assembly.warning_level, "warning")
        self.assertIn("buiten de periode", assembly.warning)

    def test_longer_convocation_term(self):
        self.vme_late.convocation_days = 30
        assembly = self._of(self._assemblies(), self.vme_late)
        assembly.slot_id = self._slot(date(2027, 3, 25))
        self.assertEqual(assembly.convocation_deadline, date(2027, 2, 23))

    # Calendar

    def test_calendar_event_follows_the_assembly(self):
        assembly = self._of(self._assemblies(), self.vme_late)
        assembly.slot_id = self._slot(date(2027, 3, 25))
        assembly.action_confirm()
        event = assembly.calendar_event_id
        self.assertTrue(event)
        self.assertEqual(event.start, datetime(2027, 3, 25, 18, 0))
        self.assertEqual(event.user_id, self.user)
        self.assertIn(self.user.partner_id, event.partner_ids)
        self.assertIn("Zaal Test", event.location)
        # Moving a confirmed meeting moves its appointment (summer time from 28 March: UTC+2).
        assembly.slot_id = self._slot(date(2027, 3, 29), hour=20.0, online=True)
        self.assertEqual(assembly.state, "confirmed")
        self.assertEqual(event.start, datetime(2027, 3, 29, 18, 0))
        # Moving the block itself also moves the appointment.
        assembly.slot_id.date = date(2027, 3, 26)
        self.assertEqual(event.start, datetime(2027, 3, 26, 19, 0))
        assembly.action_reset()
        self.assertFalse(event.exists())
        self.assertEqual(assembly.state, "draft")
