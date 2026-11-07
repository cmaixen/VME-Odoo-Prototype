import io
from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

TODAY = date(2026, 11, 5)


@tagged("post_install", "-at_install")
class TestAssemblyMeeting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vme, cls.owners = cls._make_vme("AV Residentie Stemming", [300, 250, 200, 150, 100])
        room = cls.env["vme.assembly.room"].create({"name": "Zaal Stemming"})
        cls.slot = cls.env["vme.assembly.slot"].create({
            "date": date(2027, 3, 20), "time_start": 19.0, "room_id": room.id,
            "user_id": cls.env.ref("base.user_admin").id,
        })
        cls.assembly = cls.env["vme.assembly"].with_context(vme_today=TODAY).create({
            "association_id": cls.vme.id, "year": 2027, "slot_id": cls.slot.id,
        })
        cls.assembly.action_confirm()
        cls.assembly.action_create_attendance_list()
        cls.attendee = {a.partner_id: a for a in cls.assembly.attendee_ids}

    @classmethod
    def _make_vme(cls, name, shares):
        vme = cls.env["vme.association"].create({"name": name, "assembly_period_month": "3", "assembly_period_day": 10})
        lots = cls.env["vme.lot"].create([
            {"association_id": vme.id, "name": f"L{i}", "sequence": i} for i in range(1, len(shares) + 1)])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": vme.id, "key_type": "general", "total_shares": sum(shares),
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, shares)],
        })
        owners = cls.env["res.partner"].create([{"name": f"{name} eigenaar {lot.name}"} for lot in lots])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(lots, owners)])
        return vme, owners

    def _attend(self, present=(), represented=None, holder=None):
        """present: owner indexes present; represented: indexes represented by holder."""
        for index, owner in enumerate(self.owners):
            vals = {"attendance": "absent", "proxy_holder_id": False}
            if index in present:
                vals["attendance"] = "present"
            elif represented and index in represented:
                vals = {"attendance": "represented", "proxy_holder_id": holder.id}
            self.attendee[owner].write(vals)

    def _vote(self, majority, votes):
        """votes: {owner index: "for"/"against"/"abstain"}; other present owners vote for."""
        item = self.env["vme.assembly.item"].create({
            "assembly_id": self.assembly.id, "name": "Testpunt", "majority": majority, "sequence": 99})
        item._prepare_votes()
        for vote in item.vote_ids:
            index = self.owners.ids.index(vote.partner_id.id)
            vote.vote = votes.get(index, "for")
        return item

    # Agenda and attendance

    def test_default_agenda(self):
        names = self.assembly.item_ids.mapped("name")
        self.assertEqual(len(names), 6)
        self.assertIn("Goedkeuring van de jaarrekening 2026", names)
        self.assertEqual(self.assembly.item_ids.filtered(lambda i: "Verslag" in i.name).majority, "none")

    def test_attendance_list_from_general_key(self):
        self.assertEqual(len(self.assembly.attendee_ids), 5)
        self.assertEqual(self.assembly.shares_total, 1000)
        self.assertEqual(self.attendee[self.owners[0]].shares, 300)
        self.assertEqual(self.attendee[self.owners[0]].lot_names, "L1")

    # Quorum

    def test_quorum_majority_of_owners_and_half_of_shares(self):
        self._attend(present=(0, 1, 2))  # 3/5 owners, 750/1000
        self.assertTrue(self.assembly.quorum_reached)
        self._attend(present=(0, 1))  # 2/5 owners, 550/1000
        self.assertFalse(self.assembly.quorum_reached)
        self._attend(present=(2, 3, 4))  # 3/5 owners but only 450/1000
        self.assertFalse(self.assembly.quorum_reached)
        self._attend(present=(1, 3), represented=(4,), holder=self.owners[1])  # 3/5 owners, exactly 500
        self.assertTrue(self.assembly.quorum_reached)

    def test_quorum_three_quarters_of_shares(self):
        self.assertTrue(self.assembly._is_quorum_reached(10, 4, 1000, 800))
        self.assertFalse(self.assembly._is_quorum_reached(10, 4, 1000, 750))

    def test_second_session_has_no_quorum_requirement(self):
        self._attend(present=(4,))
        self.assertFalse(self.assembly.quorum_reached)
        self.assembly.second_session = True
        self.assertTrue(self.assembly.quorum_reached)

    # Majorities

    def test_absolute_majority(self):
        self._attend(present=range(5))
        self.assertEqual(self._vote("absolute", {2: "against", 3: "against", 4: "against"}).outcome, "adopted")  # 550/1000
        self.assertEqual(self._vote("absolute", {0: "against", 3: "against", 4: "against"}).outcome, "rejected")  # 450/1000
        # Exactly half is not a majority.
        self.assertEqual(self._vote("absolute", {1: "against", 2: "against", 4: "against"}).outcome, "rejected")  # 450...
        tie = self._vote("absolute", {0: "against", 2: "against"})  # for 500, against 500
        self.assertEqual((tie.votes_for, tie.votes_against), (500, 500))
        self.assertEqual(tie.outcome, "rejected")

    def test_abstentions_do_not_count(self):
        self._attend(present=range(5))
        item = self._vote("absolute", {1: "against", 2: "abstain", 3: "abstain", 4: "abstain"})
        self.assertEqual((item.votes_for, item.votes_against, item.votes_abstain), (300, 250, 450))
        self.assertEqual(item.outcome, "adopted")

    def test_two_thirds_and_four_fifths(self):
        self._attend(present=range(5))
        self.assertEqual(self._vote("two_thirds", {2: "against", 4: "against"}).outcome, "adopted")  # 700/1000
        self.assertEqual(self._vote("two_thirds", {2: "against", 3: "against"}).outcome, "rejected")  # 650/1000
        self.assertEqual(self._vote("four_fifths", {2: "against"}).outcome, "adopted")  # exactly 800/1000
        self.assertEqual(self._vote("four_fifths", {1: "against"}).outcome, "rejected")  # 750/1000

    def test_unanimity_of_all_owners(self):
        self._attend(present=range(5))
        self.assertEqual(self._vote("unanimous", {}).outcome, "adopted")
        self.assertEqual(self._vote("unanimous", {4: "abstain"}).outcome, "rejected")
        # Everyone present votes for, but one owner is absent.
        self._attend(present=range(4))
        self.assertEqual(self._vote("unanimous", {}).outcome, "rejected")

    def test_unanimity_with_a_majority_owner(self):
        # The cap of art. 3.87 §6 (600 counts as 400) must not make a unanimous vote fail.
        vme, owners = self._make_vme("AV Residentie Meerderheid", [600, 400])
        slot = self.slot.copy({"date": date(2027, 3, 21)})
        assembly = self.env["vme.assembly"].with_context(vme_today=TODAY).create({
            "association_id": vme.id, "year": 2027, "slot_id": slot.id,
        })
        assembly.action_confirm()
        assembly.action_create_attendance_list()
        assembly.attendee_ids.write({"attendance": "present"})
        item = self.env["vme.assembly.item"].create({
            "assembly_id": assembly.id, "name": "Testpunt", "majority": "unanimous", "sequence": 99})
        item._prepare_votes()
        item.vote_ids.vote = "for"
        self.assertEqual(item.outcome, "adopted")
        item.vote_ids.filtered(lambda v: v.partner_id == owners[1]).vote = "against"
        self.assertEqual(item.outcome, "rejected")

    def test_no_owner_outvotes_all_others(self):
        self.assembly.second_session = True
        self._attend(present=(0, 4))  # 300 against 100
        item = self._vote("absolute", {4: "against"})
        # The largest owner is capped at the 100 votes of the others: 100 against 100.
        self.assertEqual((item.votes_for, item.votes_against), (100, 100))
        self.assertEqual(item.outcome, "rejected")

    def test_no_quorum_and_pending(self):
        self._attend(present=(4,))
        self.assertEqual(self._vote("absolute", {}).outcome, "no_quorum")
        pending = self.env["vme.assembly.item"].create({"assembly_id": self.assembly.id, "name": "Nog niet gestemd"})
        self.assertEqual(pending.outcome, "pending")

    # Proxies

    def test_proxy_needs_holder(self):
        with self.assertRaises(ValidationError):
            self.attendee[self.owners[0]].attendance = "represented"

    def test_proxy_limits(self):
        # 4 small lots of 20 and 4 large lots of 230: 1000 votes, 10% = 100.
        vme, owners = self._make_vme("AV Residentie Volmacht", [20, 20, 20, 20, 230, 230, 230, 230])
        assembly = self.env["vme.assembly"].create({"association_id": vme.id, "year": 2027})
        assembly.action_create_attendance_list()
        attendee = {a.partner_id: a for a in assembly.attendee_ids}
        holder = self.env["res.partner"].create({"name": "Volmachthouder Test"})
        # Three proxies are always allowed, whatever their weight.
        for owner in owners[4:7]:
            attendee[owner].write({"attendance": "represented", "proxy_holder_id": holder.id})
        # A fourth large proxy brings the holder to 92%: refused.
        with self.assertRaises(ValidationError):
            attendee[owners[7]].write({"attendance": "represented", "proxy_holder_id": holder.id})
        # Four small proxies (80 votes, 8%) are allowed for another holder...
        other = self.env["res.partner"].create({"name": "Tweede volmachthouder"})
        for owner in owners[:4]:
            attendee[owner].write({"attendance": "represented", "proxy_holder_id": other.id})
        # ...but not for a present owner whose own 230 votes push the total over 10%.
        attendee[owners[7]].attendance = "present"
        for owner in owners[:3]:
            attendee[owner].proxy_holder_id = owners[7]
        with self.assertRaises(ValidationError):
            attendee[owners[3]].proxy_holder_id = owners[7]

    # Convocations

    def test_convocation_pdfs_in_one_run(self):
        """All convocations and statements of an assembly come from one wkhtmltopdf run per report."""
        Report = self.env.registry["ir.actions.report"]
        runs = []

        def pre_render(report, report_ref, res_ids=None, data=None):
            runs.append((report_ref, list(res_ids)))
            return {rid: {"stream": io.BytesIO(b"%PDF-" + str(rid).encode()), "attachment": None}
                    for rid in res_ids}, "pdf"

        def one_by_one(*args, **kwargs):
            raise AssertionError("rendered one record at a time")

        with patch.object(Report, "_pre_render_qweb_pdf", pre_render), patch.object(Report, "_render_qweb_pdf", one_by_one):
            self.assembly.action_create_convocations()
        convocations = self.assembly.convocation_ids
        self.assertEqual([ref for ref, _ids in runs], [
            "vme_belgie.action_report_assembly_convocation", "vme_belgie.action_report_annual_statement"])
        self.assertEqual(runs[0][1], convocations.ids)
        for convocation in convocations:
            self.assertEqual(len(convocation.attachment_ids), 2)
            self.assertIn(b"%%PDF-%d" % convocation.id, [a.raw for a in convocation.attachment_ids])

    def test_convocations_are_drafts_with_documents(self):
        mails_before = self.env["mail.mail"].search_count([])
        action = self.assembly.action_create_convocations()
        self.assertEqual(action["params"]["type"], "success")
        convocations = self.assembly.convocation_ids
        self.assertEqual(len(convocations), 5)
        self.assertEqual(set(convocations.mapped("state")), {"draft"})
        self.assertTrue(all(c.attachment_ids for c in convocations))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
        self.assertFalse(self.assembly.convocation_sent_date)
        # Sending through the composer marks the convocation and the assembly.
        composer = convocations[0].action_open_composer()
        self.assertTrue(composer["context"]["mark_convocation_as_sent"])
        convocations[0].with_context(mark_convocation_as_sent=True).message_post(body="Oproeping")
        self.assertEqual(convocations[0].state, "sent")
        self.assertTrue(self.assembly.convocation_sent_date)
        self.assertEqual(convocations[1].state, "draft")

    def test_late_convocation_warns(self):
        action = self.assembly.with_context(vme_today=date(2027, 3, 10)).action_create_convocations()
        self.assertEqual(action["params"]["type"], "warning")

    def test_every_convocation_must_leave_on_time(self):
        """B-D2: the first convocation on time does not cover the others (deadline 5 March 2027)."""
        first, second = self.env["vme.assembly.convocation"].create([
            {"assembly_id": self.assembly.id, "partner_id": owner.id, "lot_names": "L"} for owner in self.owners[:2]])
        first.write({"state": "sent", "sent_date": date(2027, 3, 1)})
        self.assembly.convocation_sent_date = date(2027, 3, 1)
        on_time = self.assembly.with_context(vme_today=date(2027, 3, 4))
        self.assertNotEqual(on_time.warning_level, "danger")
        after = self.assembly.with_context(vme_today=date(2027, 3, 6))
        self.assertEqual(after.warning_level, "danger")
        self.assertIn("nog niet verstuurd", after.warning)
        self.assertIn(second.partner_id.name, after.warning)
        second.write({"state": "sent", "sent_date": date(2027, 3, 6)})
        after.invalidate_recordset(["warning", "warning_level"])
        self.assertEqual(after.warning_level, "danger")
        self.assertIn("vertrokken na", after.warning)
        self.assertNotIn(first.partner_id.name, after.warning)

    def test_convocation_needs_a_date(self):
        unplanned = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2028})
        with self.assertRaises(UserError):
            unplanned.action_create_convocations()

    # Closing, register and follow-up

    def test_closing_registers_decisions_and_follow_up(self):
        self._attend(present=range(5))
        with self.assertRaises(UserError):
            self.assembly.action_mark_held()
        self.assembly.action_prepare_votes()
        roof = self.env["vme.assembly.item"].create({
            "assembly_id": self.assembly.id, "sequence": 7, "name": "Dakwerken", "majority": "two_thirds",
            "follow_up_summary": "Offertes vragen voor de dakwerken", "follow_up_deadline": date(2027, 5, 1),
        })
        roof.action_all_for()
        self.assembly.action_mark_held()
        self.assertEqual(self.assembly.state, "held")
        decided = self.assembly.item_ids.filtered("decision_number")
        self.assertEqual(len(decided), 6)  # five voted standard points plus the roof
        self.assertEqual(roof.decision_number, "2027/06")
        self.assertEqual(roof.activity_ids.summary, "Offertes vragen voor de dakwerken")
        self.assertEqual(roof.activity_ids.date_deadline, date(2027, 5, 1))
        html = self.env["ir.actions.report"]._render_qweb_html(
            "vme_belgie.action_report_assembly_minutes", self.assembly.ids)[0]
        self.assertIn(b"Dakwerken", html)
        self.assertIn(b"Het quorum is bereikt", html)
