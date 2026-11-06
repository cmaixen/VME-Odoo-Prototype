"""Digital and hybrid assembly (step 24): voting rights online, closing a vote, written votes
beforehand, extraordinary assemblies, and the audit trail of the signed minutes."""
import hashlib
from datetime import date

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

TODAY = date(2026, 11, 5)

IP_A = "192.0.2.10"  # documentation addresses (RFC 5737)
IP_B = "192.0.2.20"


class OnlineAssemblyFixture:

    @classmethod
    def _setup_online(cls):
        shares = [300, 250, 200, 150, 100]
        cls.vme = cls.env["vme.association"].create({
            "name": "AV Residentie Online", "assembly_period_month": "3", "assembly_period_day": 10})
        lots = cls.env["vme.lot"].create([
            {"association_id": cls.vme.id, "name": f"L{i}", "sequence": i} for i in range(1, len(shares) + 1)])
        cls.env["vme.key"].create({
            "name": "Algemeen", "association_id": cls.vme.id, "key_type": "general", "total_shares": sum(shares),
            "line_ids": [Command.create({"lot_id": lot.id, "shares": s}) for lot, s in zip(lots, shares)],
        })
        cls.owners = cls.env["res.partner"].create([{"name": f"Eigenaar Online {lot.name}"} for lot in lots])
        cls.env["vme.ownership"].create([
            {"lot_id": lot.id, "partner_id": owner.id, "date_start": date(2015, 1, 1)}
            for lot, owner in zip(lots, cls.owners)])
        room = cls.env["vme.assembly.room"].create({"name": "Zaal Online"})
        slot = cls.env["vme.assembly.slot"].create({
            "date": date(2027, 3, 20), "time_start": 19.0, "room_id": room.id,
            "user_id": cls.env.ref("base.user_admin").id,
        })
        cls.assembly = cls.env["vme.assembly"].with_context(vme_today=TODAY).create({
            "association_id": cls.vme.id, "year": 2027, "slot_id": slot.id, "meeting_mode": "hybrid",
            "video_url": "https://meet.example.com/av-residentie-online",
        })
        cls.assembly.action_confirm()
        cls.assembly.action_create_attendance_list()
        cls.attendee = {a.partner_id: a for a in cls.assembly.attendee_ids}
        cls.item = cls.env["vme.assembly.item"].create({
            "assembly_id": cls.assembly.id, "name": "Laadpalen in de garage", "majority": "absolute", "sequence": 50})

    def _att(self, index):
        return self.attendee[self.owners[index]]

    def _vote(self, item, partner, votes, ip=IP_A):
        """votes: {owner index: vote}"""
        return item._portal_cast_votes(partner, {self._att(i): v for i, v in votes.items()}, ip)


@tagged("post_install", "-at_install")
class TestAssemblyOnlineVoting(OnlineAssemblyFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_online()

    def test_online_link(self):
        self.assertTrue(self.assembly.online_token)
        self.assertTrue(self.assembly.online_url.endswith(f"/av/{self.assembly.online_token}"))
        in_person = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2028})
        self.assertFalse(in_person.online_url)
        in_person.meeting_mode = "online"
        self.assertTrue(in_person.online_token)

    def test_invitation_with_online_link_is_a_draft(self):
        self.item.allow_advance_vote = True
        convocation = self.env["vme.assembly.convocation"].create({
            "assembly_id": self.assembly.id, "partner_id": self.owners[0].id, "lot_names": "L1", "shares": 300})
        action = convocation.action_open_composer()
        self.assertEqual(action["res_model"], "mail.compose.message")  # opened for the employee, not sent
        self.assertIn(self.assembly.online_url, action["context"]["default_body"])
        self.assertIn("vooraf schriftelijk", action["context"]["default_body"])
        self.assertEqual(convocation.state, "draft")

    # Online attendance

    def test_check_in_online_counts_for_quorum(self):
        with self.assertRaises(UserError):  # the reception is not open yet
            self.assembly._portal_check_in(self.owners[0], IP_A)
        self.assembly.action_open_online()
        attendee = self.assembly._portal_check_in(self.owners[0], IP_A)
        self.assertEqual((attendee.attendance, attendee.attendance_mode, attendee.check_in_ip), ("present", "online", IP_A))
        self.assertTrue(attendee.checked_in_at)
        self.assertEqual(self.assembly.online_attendee_count, 1)
        self.assembly._portal_check_in(self.owners[1], IP_B)
        self.assembly._portal_check_in(self.owners[2], IP_B)
        # Three of five owners with 750 of 1000 shares: the quorum rule of step 11 applies as is.
        self.assertTrue(self.assembly.quorum_reached)

    def test_check_in_refused_for_strangers_and_in_person_meetings(self):
        self.assembly.action_open_online()
        stranger = self.env["res.partner"].create({"name": "Geen eigenaar"})
        with self.assertRaises(UserError):
            self.assembly._portal_check_in(stranger, IP_A)
        in_person = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2028})
        with self.assertRaises(UserError):
            in_person.action_open_online()

    # Voting rights online

    def test_vote_needs_an_open_vote(self):
        self.assembly.action_open_online()
        self.assembly._portal_check_in(self.owners[0], IP_A)
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[0], {0: "for"})
        self.item.action_open_voting()
        self._vote(self.item, self.owners[0], {0: "for"})
        vote = self.item.vote_ids
        self.assertEqual((vote.source, vote.ip_address, vote.voter_partner_id), ("online", IP_A, self.owners[0]))
        self.assertTrue(vote.cast_at)

    def test_online_votes_use_the_rules_of_step_11(self):
        self.assembly.action_open_online()
        for index in (0, 1, 2):
            self.assembly._portal_check_in(self.owners[index], IP_A)
        self.item.action_open_voting()
        self._vote(self.item, self.owners[0], {0: "for"})
        self._vote(self.item, self.owners[1], {1: "against"})
        self._vote(self.item, self.owners[2], {2: "abstain"})
        self.assertEqual((self.item.votes_for, self.item.votes_against, self.item.votes_abstain), (300, 250, 200))
        self.assertEqual(self.item.outcome, "adopted")  # 300 of 550 cast; abstentions do not count

    def test_proxy_holder_votes_for_two(self):
        self._att(1).write({"attendance": "represented", "proxy_holder_id": self.owners[0].id})
        self.assembly.action_open_online()
        self.assembly._portal_check_in(self.owners[0], IP_A)
        self.assembly._portal_check_in(self.owners[2], IP_B)
        self.item.action_open_voting()
        rights, source = self.item._portal_vote_rights(self.owners[0])
        self.assertEqual(rights, self._att(0) | self._att(1))
        self.assertEqual(source, "online")
        votes = self._vote(self.item, self.owners[0], {0: "for", 1: "against"})
        self.assertEqual(len(votes), 2)
        self.assertEqual(votes.voter_partner_id, self.owners[0])
        self.assertEqual(self.item.votes_for, 300)
        self.assertEqual(self.item.votes_against, 250)

    def test_no_double_vote_with_proxy(self):
        self._att(1).write({"attendance": "represented", "proxy_holder_id": self.owners[0].id})
        self.assembly.action_open_online()
        # The owner who gave a proxy cannot sign in himself, nor vote.
        with self.assertRaises(UserError):
            self.assembly._portal_check_in(self.owners[1], IP_B)
        self.assembly._portal_check_in(self.owners[0], IP_A)
        self.item.action_open_voting()
        self.assertFalse(self.item._portal_vote_rights(self.owners[1])[0])
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[1], {1: "against"}, IP_B)
        # The proxy holder votes once for the owner, not twice.
        self._vote(self.item, self.owners[0], {1: "for"})
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[0], {1: "against"})
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[0], {0: "for", 1: "against"})
        self.assertEqual(len(self.item.vote_ids), 1)  # the refused batch left nothing behind
        # A third owner cannot vote for someone else.
        self.assembly._portal_check_in(self.owners[2], IP_B)
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[2], {0: "against"}, IP_B)

    def test_closing_the_vote(self):
        self.assembly.action_open_online()
        for index in (0, 1, 2):
            self.assembly._portal_check_in(self.owners[index], IP_A)
        self.item.action_open_voting()
        self._vote(self.item, self.owners[0], {0: "for"})
        with self.assertRaises(UserError):  # the assembly cannot close with an open vote
            self.assembly.action_mark_held()
        self.item.action_close_voting()
        self.assertEqual(self.item.voting_state, "closed")
        self.assertTrue(self.item.voting_closed_at)
        with self.assertRaises(UserError):  # too late for owner 1
            self._vote(self.item, self.owners[1], {1: "against"}, IP_B)
        with self.assertRaises(UserError):
            self.item.action_open_voting()  # no second round
        self.assertEqual(self.item.outcome, "adopted")

    def test_online_vote_is_final(self):
        self.assembly.action_open_online()
        self.assembly._portal_check_in(self.owners[0], IP_A)
        self.item.action_open_voting()
        vote = self._vote(self.item, self.owners[0], {0: "for"})
        with self.assertRaises(UserError):
            vote.vote = "against"
        with self.assertRaises(UserError):
            vote.unlink()
        self.item.action_all_for()  # touches only votes from the room
        self.assertEqual(vote.vote, "for")

    def test_room_votes_skip_owners_voting_online(self):
        """In a hybrid meeting the room list has no default vote for owners who vote in the portal."""
        self._att(4).write({"attendance": "represented", "proxy_holder_id": self.owners[0].id})
        self._att(3).attendance = "present"  # in the room
        self.assembly.action_open_online()
        self.assembly._portal_check_in(self.owners[0], IP_A)
        self.item._prepare_votes()
        self.assertEqual(self.item.vote_ids.attendee_id, self._att(3))
        self.assertEqual(self.item.vote_ids.source, "room")

    # Written votes beforehand

    def test_written_vote_beforehand(self):
        self.item.allow_advance_vote = True
        rights, source = self.item._portal_vote_rights(self.owners[2])
        self.assertEqual((rights, source), (self._att(2), "written"))
        self._vote(self.item, self.owners[2], {2: "against"}, IP_B)
        self.assertEqual((self._att(2).attendance, self._att(2).attendance_mode), ("present", "written"))
        self.assertEqual(self.item.vote_ids.source, "written")
        with self.assertRaises(UserError):
            self._vote(self.item, self.owners[2], {2: "for"}, IP_B)
        # Once the meeting has started, written votes are over.
        self.assembly.action_open_online()
        self.assertFalse(self.item._portal_vote_rights(self.owners[3])[1])
        # Without the option nobody votes beforehand.
        other = self.env["vme.assembly.item"].create({
            "assembly_id": self.assembly.id, "name": "Zonder schriftelijke stemming", "majority": "absolute"})
        self.assembly.action_close_online()
        self.assertFalse(other._portal_vote_rights(self.owners[3])[1])

    def test_written_voter_is_not_asked_to_sign(self):
        self.item.allow_advance_vote = True
        self._vote(self.item, self.owners[2], {2: "for"}, IP_B)
        self.assembly.action_open_online()
        self.assembly._portal_check_in(self.owners[0], IP_A)
        self._att(1).attendance = "present"  # in the room
        self.assembly.write({"chair_id": self.owners[0].id, "secretary_id": self.owners[1].id})
        self.assembly.item_ids.filtered(lambda i: i.majority != "none").action_all_for()
        self.assembly.action_mark_held()
        self.assembly.action_prepare_signing()
        self.assertEqual(self.assembly.signature_ids.partner_id, self.owners[0] | self.owners[1])

    # Extraordinary assemblies

    def test_extraordinary_assembly_next_to_the_ordinary_one(self):
        Assembly = self.env["vme.assembly"]
        extra = Assembly.create({"association_id": self.vme.id, "year": 2027, "assembly_type": "extraordinary",
                                 "subject": "Laadpalen"})
        self.assertEqual(extra.name, "Buitengewone AV 2027 AV Residentie Online: Laadpalen")
        self.assertFalse(extra.period_start)
        self.assertEqual(len(extra.item_ids), 1)  # only the opening
        self.assertFalse(Assembly._create_missing_assemblies(2027, self.vme))
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            Assembly.create({"association_id": self.vme.id, "year": 2027})
            self.env.flush_all()


@tagged("post_install", "-at_install")
class TestAssemblyMinutesSignature(OnlineAssemblyFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_online()
        cls.assembly.action_open_online()
        cls.assembly._portal_check_in(cls.owners[0], IP_A)
        cls.assembly._portal_check_in(cls.owners[1], IP_B)
        cls.attendee[cls.owners[2]].attendance = "present"  # in the room
        cls.assembly.write({"chair_id": cls.owners[2].id, "secretary_id": cls.owners[1].id})
        cls.item.action_open_voting()
        cls.item._portal_cast_votes(cls.owners[0], {cls.attendee[cls.owners[0]]: "for"}, IP_A)
        cls.item.action_close_voting()
        cls.assembly.item_ids.filtered(lambda i: i.majority != "none" and i != cls.item).action_all_for()
        cls.assembly.action_mark_held()
        cls.assembly.action_prepare_signing()

    def _signature(self, index):
        return self.assembly.signature_ids.filtered(lambda s: s.partner_id == self.owners[index])

    def test_signers_and_hash(self):
        signatures = self.assembly.signature_ids
        self.assertEqual(signatures.partner_id, self.owners[0] | self.owners[1] | self.owners[2])
        self.assertEqual(self._signature(2).role, "chair")
        self.assertEqual(self._signature(1).role, "secretary")
        self.assertEqual(self._signature(0).role, "owner")
        digest = hashlib.sha256(self.assembly.minutes_attachment_id.raw).hexdigest()
        self.assertEqual(self.assembly.minutes_sha256, digest)
        self.assertEqual(set(signatures.mapped("document_sha256")), {digest})
        self.assertEqual(self.assembly.signature_state, "pending")

    def test_sign_keeps_who_when_ip_and_hash(self):
        signature = self._signature(0)
        signature._portal_sign(self.owners[0], "  Eigenaar L1  ", IP_A, "Mozilla/5.0 (test)")
        self.assertEqual(signature.state, "signed")
        self.assertEqual(signature.signed_name, "Eigenaar L1")
        self.assertEqual(signature.ip_address, IP_A)
        self.assertEqual(signature.user_agent, "Mozilla/5.0 (test)")
        self.assertTrue(signature.signed_at)
        self.assertEqual(signature.document_sha256, self.assembly.minutes_sha256)
        self.assertTrue(signature.is_valid)
        self._signature(1)._portal_sign(self.owners[1], "Secretaris", IP_B, "")
        self._signature(2)._portal_sign(self.owners[2], "Voorzitter", IP_B, "")
        self.assertEqual(self.assembly.signature_state, "signed")

    def test_sign_only_once_and_only_for_yourself(self):
        signature = self._signature(0)
        with self.assertRaises(UserError):
            signature._portal_sign(self.owners[1], "Iemand anders", IP_B, "")
        with self.assertRaises(UserError):
            signature._portal_sign(self.owners[0], "   ", IP_A, "")
        signature._portal_sign(self.owners[0], "Eigenaar L1", IP_A, "")
        with self.assertRaises(UserError):
            signature._portal_sign(self.owners[0], "Eigenaar L1", IP_A, "")

    def test_signed_audit_trail_cannot_be_changed(self):
        signature = self._signature(0)
        signature._portal_sign(self.owners[0], "Eigenaar L1", IP_A, "")
        with self.assertRaises(UserError):
            signature.ip_address = IP_B
        with self.assertRaises(UserError):
            signature.document_sha256 = "0" * 64
        with self.assertRaises(UserError):
            signature.unlink()

    def test_changed_pdf_invalidates_signatures(self):
        self._signature(0)._portal_sign(self.owners[0], "Eigenaar L1", IP_A, "")
        self.assembly.minutes_attachment_id.raw = self.assembly.minutes_attachment_id.raw + b" "
        self.assertFalse(self._signature(0).is_valid)
        self.assertEqual(self.assembly.signature_state, "invalid")
        # Nobody can still sign the changed PDF with the old request.
        with self.assertRaises(UserError):
            self._signature(1)._portal_sign(self.owners[1], "Secretaris", IP_B, "")
        # Preparing again: a new PDF and new requests; the old signature stays as evidence, invalid.
        self.item.decision = "Verbeterde tekst van de beslissing."
        self.assembly.action_prepare_signing()
        old = self.assembly.signature_ids.filtered(lambda s: s.state == "signed")
        self.assertEqual(len(old), 1)
        self.assertFalse(old.is_valid)
        current = self.assembly.signature_ids.filtered(lambda s: s.document_sha256 == self.assembly.minutes_sha256)
        self.assertEqual(current.partner_id, self.owners[0] | self.owners[1] | self.owners[2])
        self.assertEqual(set(current.mapped("state")), {"pending"})
        self.assertEqual(self.assembly._portal_signature(self.owners[0]), current.filtered(
            lambda s: s.partner_id == self.owners[0]))

    def test_hash_ignores_bin_size(self):
        """The web client reads with bin_size; the hash must still be that of the file itself."""
        digest = hashlib.sha256(self.assembly.minutes_attachment_id.raw).hexdigest()
        self.assembly.invalidate_recordset(["minutes_sha256"])
        self.assertEqual(self.assembly.with_context(bin_size=True).minutes_sha256, digest)
        self.assertTrue(self._signature(0).with_context(bin_size=True).document_sha256 == digest)

    def test_prepare_again_without_change(self):
        """The same PDF again: existing signatures stay valid and nobody is asked twice."""
        self._signature(0)._portal_sign(self.owners[0], "Eigenaar L1", IP_A, "")
        digest = self.assembly.minutes_sha256
        self.assembly.action_prepare_signing()
        self.assertEqual(self.assembly.minutes_sha256, digest)  # tests render HTML, which does not change
        self.assertEqual(len(self.assembly.signature_ids), 3)
        self.assertTrue(self._signature(0).is_valid)

    def test_signing_only_after_the_meeting(self):
        other = self.env["vme.assembly"].create({"association_id": self.vme.id, "year": 2028})
        with self.assertRaises(UserError):
            other.action_prepare_signing()


@tagged("post_install", "-at_install")
class TestAssemblyOnlinePortal(OnlineAssemblyFixture, HttpCase):
    """The portal pages answer only for owners of the VME, and the link per assembly leads to login."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_online()
        portal = cls.env.ref("base.group_portal")
        cls.owners[0].email = "eigenaar.online.1@example.com"
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "login": "eigenaar.online.1@example.com", "password": "online-test-1234",
            "partner_id": cls.owners[0].id, "group_ids": [(6, 0, portal.ids)]})
        stranger = cls.env["res.partner"].create({"name": "Vreemde", "email": "vreemde.online@example.com"})
        cls.env["res.users"].with_context(no_reset_password=True).create({
            "login": "vreemde.online@example.com", "password": "online-test-1234",
            "partner_id": stranger.id, "group_ids": [(6, 0, portal.ids)]})

    def test_assembly_page(self):
        url = f"/my/vme/assembly/{self.assembly.id}"
        self.authenticate("eigenaar.online.1@example.com", "online-test-1234")
        self.assembly.action_open_online()
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Ik ben aanwezig (online)", response.text)
        self.assertIn("Laadpalen in de garage", response.text)
        self.authenticate("vreemde.online@example.com", "online-test-1234")
        self.assertEqual(self.url_open(url).status_code, 404)

    def test_link_per_assembly(self):
        response = self.url_open(f"/av/{self.assembly.online_token}", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/web/login", response.headers["Location"])
        self.assertEqual(self.url_open("/av/geen-geldige-code", allow_redirects=False).status_code, 404)
