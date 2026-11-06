"""Requests and survey answers in the owner portal: an owner or tenant only ever files requests for
its own lots, only sees its own requests and answers only its own survey lines. Nothing is sent."""
import base64
from datetime import date, timedelta
from io import BytesIO

from werkzeug.datastructures import FileStorage

from odoo import fields, http
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import HttpCase, TransactionCase, tagged

from .test_portal import PASSWORD, PortalFixture


class PortalRequestFixture(PortalFixture):
    """The portal fixture, plus a tenant of A1 with a login and a survey to all owners."""

    @classmethod
    def _setup_request_fixture(cls):
        env = cls.env
        cls._setup_portal_fixture()
        cls.tenant = env["res.partner"].create({"name": "Huurder P", "email": "huurder.p@example.com"})
        env["vme.lot.contact"].create({
            "lot_id": cls.a1.id, "partner_id": cls.tenant.id, "role": "tenant", "date_start": date(2025, 9, 1)})
        cls.portal_users[cls.tenant] = env["res.users"].with_context(no_reset_password=True).create({
            "login": cls.tenant.email, "password": PASSWORD, "partner_id": cls.tenant.id,
            "group_ids": [Command.set(env.ref("base.group_portal").ids)],
        })
        cls.key_type = env.ref("vme_belgie.request_type_key")
        cls.survey = cls._make_survey(cls.vme)
        cls.other_survey = cls._make_survey(cls.other_vme)
        cls.owner_log = cls.survey.log_ids.filtered(lambda log: log.partner_id == cls.owner)
        cls.neighbour_log = cls.survey.log_ids.filtered(lambda log: log.partner_id == cls.neighbour)

    @classmethod
    def _make_survey(cls, vme, confirm=True, deadline=None):
        survey = cls.env["vme.communication"].create({
            "association_id": vme.id, "name": "Laadpalen in {vme}", "kind": "survey",
            "question": "Interesse in een laadpaal?", "body_html": "<p>Beste {eigenaar},</p>",
            "answer_deadline": deadline or fields.Date.today() + timedelta(days=30),
            "option_ids": [Command.create({"name": name, "sequence": i}) for i, name in enumerate(("Ja", "Nee"))],
        })
        survey.action_prepare_recipients()
        if confirm:
            survey.action_confirm()
        return survey

    @staticmethod
    def _file(name="bewijs.pdf", content=b"%PDF fictief bewijs"):
        return FileStorage(stream=BytesIO(content), filename=name, content_type="application/pdf")


@tagged("post_install", "-at_install")
class TestPortalRequests(PortalRequestFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_request_fixture()

    def test_request_lots_are_own_current_lots(self):
        self.assertEqual(self.owner._vme_portal_request_lots(), self.a1 | self.g1)
        self.assertEqual(self.tenant._vme_portal_request_lots(), self.a1)
        self.assertEqual(self.buyer._vme_portal_request_lots(), self.a2)
        self.assertFalse(self.seller._vme_portal_request_lots(), "the seller has no lot any more")
        self.assertEqual(self.other_owner._vme_portal_request_lots(), self.other_lot)

    def test_other_lots_are_refused(self):
        for lot in (self.a3, self.a2, self.other_lot):
            with self.assertRaises(UserError, msg=lot.display_name):
                self.owner._vme_portal_create_request(lot, "key", "Badge", "")
        self.assertFalse(self.env["vme.request"].search([("association_id", "in", (self.vme | self.other_vme).ids)]))

    def test_owner_request_same_procedure_nothing_sent(self):
        mails = self.env["mail.mail"].search([])
        request = self.owner._vme_portal_create_request(
            self.a1, "key", "Extra badge", "Graag een badge voor A1.", [self._file("foto.pdf")])
        self.assertEqual(request.channel, "portal")
        self.assertEqual(request.requester_id, self.owner)
        self.assertEqual(request.requester_role, "owner")
        self.assertEqual(request.key_kind, "badge")
        self.assertEqual(request.state, "in_progress")  # verified: the owner of the lot
        self.assertFalse(request.user_id.share, "the responsible is a staff member, not the owner")
        self.assertTrue(request.activity_ids)
        self.assertFalse(request.activity_ids.user_id.filtered("share"))
        self.assertEqual(len(request.proof_attachment_ids), 1)
        self.assertFalse(request.order_sent_date)
        # Only Odoo's own notification of the new task to the staff member; nothing to the owner.
        new_mails = self.env["mail.mail"].search([]) - mails
        self.assertFalse(new_mails.recipient_ids.filtered(lambda p: not p.user_ids or p.user_ids.share),
                         "nothing is sent to the owner or the locksmith by itself")

    def test_tenant_request_waits_for_proof(self):
        request = self.tenant._vme_portal_create_request(self.a1, "key", "Sleutel inkom", "")
        self.assertEqual(request.requester_id, self.tenant)
        self.assertEqual(request.requester_role, "tenant")
        self.assertEqual(request.state, "waiting_proof")
        self.assertTrue(request.activity_ids)
        self.assertEqual(request.portal_state, "waiting_proof")
        # The tenant adds the proof in the portal; a staff member still approves it.
        request._portal_add_proof(self.tenant, [self._file("toestemming.pdf"), self._file("huurcontract.pdf")])
        self.assertEqual(len(request.proof_attachment_ids), 2)
        self.assertEqual(request.state, "waiting_proof")
        self.assertIn("Bewijs uit het portaal nakijken", request.activity_ids.mapped("summary"))
        with self.assertRaises(UserError):
            request._portal_add_proof(self.owner, [self._file()])  # not the requester

    def test_own_requests_only(self):
        mine = self.owner._vme_portal_create_request(self.a1, "document", "Attest", "")
        self.assertEqual(mine.activity_ids.summary, "Aanvraag uit het portaal behandelen")
        self.assertFalse(mine.activity_ids.user_id.share)
        tenant_request = self.tenant._vme_portal_create_request(self.a1, "damage", "Lek", "")
        self.assertEqual(self.owner._vme_portal_requests(), mine)
        self.assertEqual(self.tenant._vme_portal_requests(), tenant_request)
        self.assertFalse(self.owner._vme_portal_request(tenant_request.id))
        self.assertFalse(self.other_owner._vme_portal_requests())

    def test_portal_messages_hide_notes(self):
        request = self.tenant._vme_portal_create_request(self.a1, "key", "Badge", "")
        self.assertFalse(request._portal_messages(), "the intake note is internal")
        request.action_send_proof_request()
        self.assertEqual(len(request._portal_messages()), 1)

    def test_surveys_only_own_and_sent(self):
        self.assertEqual(self.owner._vme_portal_surveys(), self.owner_log)
        self.assertFalse(self.owner._vme_portal_survey(self.neighbour_log.id))
        draft = self._make_survey(self.vme, confirm=False)
        self.assertNotIn(draft.log_ids, self.owner._vme_portal_surveys())
        self.assertIn("/my/vme/survey/%s" % self.owner_log.id, str(self.owner_log.body_html))
        self.assertNotIn("/my/vme/survey/", str(self.neighbour_log.body_html), "the neighbour has no login")

    def test_answer_in_log_and_results(self):
        yes, no = self.survey.option_ids
        self.owner_log._portal_answer(self.owner, yes.id, "Graag op G1")
        self.assertEqual(self.owner_log.answer_option_id, yes)
        self.assertEqual(self.owner_log.answer_channel, "portal")
        self.assertEqual(self.owner_log.answer_note, "Graag op G1")
        self.assertEqual((yes.answer_count, no.answer_count), (1, 0))
        self.assertEqual(self.survey.answer_count, 1)
        self.owner_log._portal_answer(self.owner, no.id)  # changed before the deadline
        self.assertEqual((yes.answer_count, no.answer_count), (0, 1))
        with self.assertRaises(UserError):
            self.neighbour_log._portal_answer(self.owner, yes.id)
        with self.assertRaises(UserError):
            self.owner_log._portal_answer(self.owner, self.other_survey.option_ids[0].id)
        # An answer entered by a staff member.
        self.neighbour_log.answer_option_id = yes
        self.assertEqual(self.neighbour_log.answer_channel, "manual")

    def test_no_answer_after_deadline(self):
        self.survey.answer_deadline = fields.Date.today() - timedelta(days=1)
        with self.assertRaises(UserError):
            self.owner_log._portal_answer(self.owner, self.survey.option_ids[0].id)

    def test_no_orm_access_for_portal_users(self):
        for partner in (self.owner, self.tenant):
            user = self.portal_users[partner]
            for model in ("vme.request", "vme.request.type", "vme.lot.contact", "vme.lot.key",
                          "vme.communication", "vme.communication.log", "vme.communication.option"):
                with self.assertRaises(AccessError, msg=model):
                    self.env[model].with_user(user).search([])


@tagged("post_install", "-at_install")
class TestPortalRequestRoutes(PortalRequestFixture, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_request_fixture()

    def _post(self, url, data, files=None):
        return self.url_open(url, data={**data, "csrf_token": http.Request.csrf_token(self)}, files=files)

    def test_owner_files_request(self):
        self.authenticate(self.owner.email, PASSWORD)
        form = self.url_open("/my/vme/requests/new")
        self.assertEqual(form.status_code, 200)
        self.assertIn("A1", form.text)
        self.assertNotIn(f'value="{self.a3.id}"', form.text)
        response = self._post("/my/vme/requests/new", {
            "lot_id": self.g1.id, "request_type": "key", "subject": "Afstandsbediening garage",
            "description": "Graag een tweede afstandsbediening.",
        }, files={"attachments": ("foto.pdf", b"%PDF fictief", "application/pdf")})
        self.assertEqual(response.status_code, 200)
        request = self.env["vme.request"].search([("requester_id", "=", self.owner.id)])
        self.assertEqual(request.lot_id, self.g1)
        self.assertEqual(request.channel, "portal")
        self.assertIn(request.name, response.text)
        self.assertEqual(self.url_open("/my/vme/requests").status_code, 200)
        # Another lot, also one of another VME: 404 and no request.
        for lot in (self.a3, self.other_lot):
            response = self._post("/my/vme/requests/new", {"lot_id": lot.id, "request_type": "key", "subject": "X"})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.env["vme.request"].search_count([("requester_id", "=", self.owner.id)]), 1)

    def test_guessed_ids_answer_404(self):
        foreign = self.other_owner._vme_portal_create_request(self.other_lot, "document", "Attest", "")
        self.authenticate(self.owner.email, PASSWORD)
        self.assertEqual(self.url_open(f"/my/vme/request/{foreign.id}").status_code, 404)
        self.assertEqual(self._post(f"/my/vme/request/{foreign.id}/proof", {},
                                    files={"attachments": ("x.pdf", b"x", "application/pdf")}).status_code, 404)
        self.assertEqual(self.url_open(f"/my/vme/survey/{self.neighbour_log.id}").status_code, 404)
        other_log = self.other_survey.log_ids[:1]
        self.assertEqual(self._post(f"/my/vme/survey/{other_log.id}",
                                    {"option_id": self.other_survey.option_ids[0].id}).status_code, 404)
        self.assertFalse(self.neighbour_log.answer_option_id)
        self.assertFalse(other_log.answer_option_id)

    def test_owner_answers_survey(self):
        self.authenticate(self.owner.email, PASSWORD)
        self.assertIn(f"/my/vme/survey/{self.owner_log.id}", self.url_open("/my/vme").text)
        page = self.url_open(f"/my/vme/survey/{self.owner_log.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Interesse in een laadpaal?", page.text)
        yes = self.survey.option_ids[0]
        response = self._post(f"/my/vme/survey/{self.owner_log.id}", {"option_id": yes.id, "note": "Op G1"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("uw antwoord is geregistreerd", response.text)
        self.assertEqual(self.owner_log.answer_option_id, yes)
        self.assertEqual(self.owner_log.answer_channel, "portal")

    def test_tenant_pages(self):
        self.authenticate(self.tenant.email, PASSWORD)
        home = self.url_open("/my/vme")
        self.assertEqual(home.status_code, 200)
        self.assertIn("Gehuurde kavels", home.text)
        # The documents and provisions of the building stay for owners.
        self.assertEqual(self.url_open(f"/my/vme/{self.vme.id}").status_code, 404)
        response = self._post("/my/vme/requests/new", {"lot_id": self.a1.id, "request_type": "key", "subject": "Badge"})
        self.assertEqual(response.status_code, 200)
        request = self.env["vme.request"].search([("requester_id", "=", self.tenant.id)])
        self.assertEqual(request.state, "waiting_proof")
        self.assertIn("Bewijs bezorgen", response.text)
        response = self._post(f"/my/vme/request/{request.id}/proof", {"note": "Toestemming en contract"},
                              files={"attachments": ("contract.pdf", b"%PDF fictief", "application/pdf")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.proof_attachment_ids), 1)
        self.assertEqual(base64.b64decode(request.proof_attachment_ids.datas), b"%PDF fictief")

    def test_seller_cannot_file_requests(self):
        self.authenticate(self.seller.email, PASSWORD)
        self.assertEqual(self.url_open("/my/vme/requests/new").status_code, 404)
