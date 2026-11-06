"""Requests (step 19) and survey answers (step 23) in the owner portal (step 15).

Same rules as models/vme_portal.py: portal users have no access rights on these models, the
controllers read as sudo, but only through the helpers below, which always start from the
logged-in partner. A request from the portal follows the procedure of a request by mail; a staff
member still decides and sends everything.
"""
import base64

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command

from .vme_request import CLOSED_STATES

# What the owner reads as status. Drafts and internal notes never reach the portal.
PORTAL_STATES = [
    ("new", "Ontvangen"),
    ("waiting_proof", "Wacht op uw bewijs"),
    ("in_progress", "In behandeling"),
    ("ordered", "Besteld"),
    ("done", "Afgehandeld"),
    ("refused", "Geweigerd"),
    ("cancelled", "Geannuleerd"),
]
# Files an owner can add to a request: size per file, number per upload.
PORTAL_MAX_FILE_SIZE = 10 * 1024 * 1024
PORTAL_MAX_FILES = 5


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _vme_portal_tenant_lots(self):
        """Lots this partner rents today. vme_rentmeester adds the lots of its leases."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        partner = self._vme_owner()
        contacts = self.env["vme.lot.contact"].sudo().search([
            ("partner_id", "=", partner.id), ("role", "=", "tenant"), ("date_start", "<=", today),
            "|", ("date_end", "=", False), ("date_end", ">=", today),
        ])
        return contacts.lot_id

    def _vme_portal_current_tenant_lots(self):
        """The tenant lots, checked against the one rule for tenants: vme.lot._get_tenants_on."""
        today = fields.Date.context_today(self)
        partner = self._vme_owner()
        return self._vme_portal_tenant_lots().filtered(lambda lot: partner in lot._get_tenants_on(today))

    def _vme_portal_request_lots(self):
        """Lots this partner may file a request for: those it owns today and those it rents."""
        self.ensure_one()
        owned = self._vme_portal_ownerships().filtered("is_current").lot_id
        lots = owned | self._vme_portal_current_tenant_lots()
        return lots.sorted(lambda lot: (lot.association_id.name, lot.sequence, lot.name))

    def _vme_portal_has_access(self):
        """Owner (now or before) or tenant: whoever gets the tile on /my."""
        return self._vme_is_owner() or bool(self._vme_portal_current_tenant_lots())

    def _vme_portal_requests(self):
        """The requests this partner filed itself, by mail or in the portal."""
        self.ensure_one()
        return self.env["vme.request"].sudo().search([("requester_id", "=", self._vme_owner().id)])

    def _vme_portal_request(self, request_id):
        return self._vme_portal_requests().filtered(lambda r: r.id == request_id)

    def _vme_portal_request_types(self):
        return self.env["vme.request.type"].sudo().search([])

    def _vme_portal_create_request(self, lot, type_code, subject, body, files=None):
        """File a request from the portal: the same intake and procedure as a request by mail."""
        self.ensure_one()
        partner = self._vme_owner()
        if lot not in self._vme_portal_request_lots():
            raise UserError(self.env._("Kies een van uw kavels."))
        if type_code not in self._vme_portal_request_types().mapped("code"):
            raise UserError(self.env._("Kies een soort aanvraag."))
        if not (subject or "").strip():
            raise UserError(self.env._("Vul het onderwerp in."))
        request_id = self.env["vme.request"].sudo().create_from_intake(
            lot.association_id.id, type_code, partner.email, name=partner.name, lot_id=lot.id,
            subject=subject.strip(), body=(body or "").strip(), channel="portal",
            attachments=_portal_attachments(self.env, files),
            requester_id=partner.id, user_id=self.env.ref("base.user_admin").id,
        )
        request = self.env["vme.request"].sudo().browse(request_id)
        if not request.activity_ids:
            # Types without a fixed first step (a certificate, a complaint) would otherwise go unnoticed.
            request._todo(self.env._("Aanvraag uit het portaal behandelen"))
        return request

    def _vme_portal_surveys(self):
        """Survey lines of this partner from mailings that were sent: open ones first."""
        self.ensure_one()
        logs = self.env["vme.communication.log"].sudo().search([
            ("partner_id", "=", self._vme_owner().id),
            ("communication_id.kind", "=", "survey"),
            ("communication_id.state", "=", "sent"),
            ("state", "=", "sent"),
        ])
        return logs.sorted(lambda log: (bool(log.answer_option_id), -log.id))

    def _vme_portal_survey(self, log_id):
        return self._vme_portal_surveys().filtered(lambda log: log.id == log_id)


def _portal_attachments(env, files):
    """Uploaded files as {"name", "datas", "mimetype"}, the format of create_from_intake."""
    files = [f for f in files or [] if f and f.filename]
    if len(files) > PORTAL_MAX_FILES:
        raise UserError(env._("Voeg maximaal %s bestanden toe.", PORTAL_MAX_FILES))
    result = []
    for upload in files:
        content = upload.read()
        if len(content) > PORTAL_MAX_FILE_SIZE:
            raise UserError(env._("%s is groter dan 10 MB.", upload.filename))
        result.append({"name": upload.filename, "datas": base64.b64encode(content), "mimetype": upload.mimetype})
    return result


class VmeRequest(models.Model):
    _inherit = "vme.request"

    portal_state = fields.Selection(PORTAL_STATES, string="Status in het portaal", compute="_compute_portal_state")

    @api.depends("state")
    def _compute_portal_state(self):
        for request in self:
            request.portal_state = request.state

    def _portal_is_open(self):
        self.ensure_one()
        return self.state not in CLOSED_STATES

    def _portal_messages(self):
        """Messages the requester may read: the mails between the requester and the syndic, never notes."""
        self.ensure_one()
        requester = self.requester_id
        comment = self.env.ref("mail.mt_comment")
        return self.sudo().message_ids.filtered(
            lambda m: m.subtype_id == comment and m.message_type in ("comment", "email")
            and (m.author_id == requester or requester in m.partner_ids)
        ).sorted("date")

    def _portal_can_add_proof(self):
        self.ensure_one()
        return self.state == "waiting_proof"

    def _portal_add_proof(self, partner, files, note=""):
        """The requester adds proof documents. A staff member checks them; nothing is approved by itself."""
        self.ensure_one()
        if self.requester_id != partner._vme_owner():
            raise UserError(self.env._("Deze aanvraag is niet van u."))
        if not self._portal_can_add_proof():
            raise UserError(self.env._("Deze aanvraag wacht niet op bewijs."))
        values = _portal_attachments(self.env, files)
        if not values:
            raise UserError(self.env._("Voeg minstens één bestand toe."))
        request = self.sudo()
        attachments = self.env["ir.attachment"].sudo().create([
            {**value, "res_model": request._name, "res_id": request.id} for value in values])
        request.proof_attachment_ids = [Command.link(a.id) for a in attachments]
        request.message_post(
            body=Markup("<p>%s</p>%s") % (
                self.env._("Bewijs opgeladen in het portaal."),
                Markup("<p>%s</p>") % note if note else Markup("")),
            attachment_ids=attachments.ids, message_type="comment", subtype_xmlid="mail.mt_note",
        )
        request._todo(self.env._("Bewijs uit het portaal nakijken"),
                      note=self.env._("Vink het nagekeken bewijs aan en klik op \"Bewijs goedkeuren\"."))
        return attachments


class VmeCommunication(models.Model):
    _inherit = "vme.communication"

    def _portal_open_for_answers(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        return self.kind == "survey" and self.state == "sent" and (
            not self.answer_deadline or self.answer_deadline >= today)

    def _render_logs(self):
        super()._render_logs()
        # A survey tells people with a portal login where they can answer.
        for communication in self.filtered(lambda c: c.kind == "survey"):
            base_url = communication.get_base_url()
            for log in communication.log_ids:
                if not log.partner_id.sudo().user_ids.filtered(lambda u: u.share and u.active):
                    continue
                url = f"{base_url}/my/vme/survey/{log.id}"
                log.body_html = (log.body_html or Markup("")) + Markup(
                    '<p>%s <a href="%s">%s</a></p>') % (
                    self.env._("U kunt ook antwoorden in het eigenaarsportaal:"), url, url)


class VmeCommunicationLog(models.Model):
    _inherit = "vme.communication.log"

    answer_channel = fields.Selection(
        [("portal", "Portaal"), ("manual", "Ingegeven door de syndicus")], string="Antwoord via", readonly=True,
        help="Portaal: de eigenaar of huurder antwoordde zelf. Anders gaf een medewerker het antwoord in.")

    def write(self, vals):
        if vals.get("answer_option_id") and "answer_channel" not in vals:
            vals["answer_channel"] = "manual"
        return super().write(vals)

    def _portal_answer(self, partner, option_id, note=""):
        """Answer of the partner itself; it can be changed until the deadline."""
        self.ensure_one()
        if self.partner_id != partner._vme_owner() or self.state != "sent":
            raise UserError(self.env._("Deze bevraging is niet voor u."))
        communication = self.communication_id
        if not communication or not communication._portal_open_for_answers():
            raise UserError(self.env._("Deze bevraging is afgesloten."))
        option = communication.option_ids.filtered(lambda o: str(o.id) == str(option_id))
        if not option:
            raise UserError(self.env._("Kies een antwoord."))
        self.sudo().write({
            "answer_option_id": option.id, "answer_note": (note or "").strip()[:500] or False,
            "answer_date": fields.Date.context_today(self), "answer_channel": "portal",
        })
        return True
