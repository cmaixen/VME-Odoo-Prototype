"""Requests of owners and tenants (keys, badges, moves, ...): one intake, a fixed procedure per type.

Nothing is sent by itself: the proof request, the reminder and the order to the locksmith are
prepared as drafts on the request, and a staff member sends each one with a button.
"""
import base64
import re
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import email_normalize, format_date

from .vme_lot_contact import KEY_KINDS

REQUEST_TYPE_CODES = [
    ("key", "Extra sleutel of badge"),
    ("badge_lost", "Verlies of diefstal van een badge"),
    ("move", "Verhuis"),
    ("new_tenant", "Nieuwe huurder melden"),
    ("works_permission", "Toestemming voor werken aan een privatief"),
    ("damage", "Defect of schade"),
    ("document", "Document opvragen"),
    ("nuisance", "Klacht over overlast"),
]
REQUESTER_ROLES = [("owner", "Eigenaar van de kavel"), ("tenant", "Huurder van de kavel"), ("unknown", "Onbekend")]
STATES = [
    ("new", "Nieuw"),
    ("waiting_proof", "Wacht op bewijs"),
    ("in_progress", "In behandeling"),
    ("ordered", "Besteld"),
    ("done", "Afgehandeld"),
    ("refused", "Geweigerd"),
    ("cancelled", "Geannuleerd"),
]
CLOSED_STATES = ("done", "refused", "cancelled")

# Proofs a requester who is not the owner of the lot must deliver, per role.
PROOFS = {
    "proof_ownership": "een eigendomsbewijs (bijvoorbeeld de akte of een attest van de notaris)",
    "proof_owner_consent": "de schriftelijke toestemming van de eigenaar van de kavel",
    "proof_lease": "een kopie van het huurcontract",
}
REQUIRED_PROOFS = {
    "owner": [],
    "tenant": ["proof_owner_consent", "proof_lease"],
    "unknown": ["proof_ownership"],
}
# The proof request is followed up with a reminder after this many days.
PROOF_REMINDER_DAYS = 7
# Days after the order at which the staff member checks the delivery.
DELIVERY_FOLLOW_UP_DAYS = 14
# Payment term of the private invoice to the owner.
PRIVATE_INVOICE_DUE_DAYS = 30

# Default price per item, VAT included (most VME's cannot deduct VAT); editable on the request.
KEY_KIND_PRICES = {"entrance_key": 45.0, "garage_key": 30.0, "remote": 75.0, "badge": 25.0}
KEY_KIND_WORDS = [
    ("remote", ("afstandsbediening",)),
    ("badge", ("badge",)),
    ("garage_key", ("garagesleutel", "sleutel van de garage", "garagepoort")),
]

# Pass-through account for private costs: the owner's invoice credits it and the locksmith's
# bill debits it, so the cost never reaches the costs that are distributed over the owners.
PRIVATE_CHARGE_ACCOUNT = ("416100", "Door te rekenen privékosten")

# LEGAL-CHECK: art. 3.88 §1, 1°, b) BW - works on the common parts need a two-thirds majority of the
# assembly; some works (charging points, art. 3.82 §1 BW) follow their own procedure. To be confirmed.
WORKS_PERMISSION_MAJORITY = "two_thirds"


class VmeRequestType(models.Model):
    _name = "vme.request.type"
    _description = "Soort aanvraag"
    _order = "sequence, id"

    name = fields.Char(string="Naam", required=True, translate=True)
    code = fields.Selection(REQUEST_TYPE_CODES, string="Procedure", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    needs_verification = fields.Boolean(
        string="Bewijs nodig voor niet-eigenaars",
        help="Een gekende eigenaar van de kavel is meteen geverifieerd. Een huurder bezorgt de toestemming "
             "van de eigenaar en het huurcontract, een onbekende een eigendomsbewijs.",
    )
    checklist = fields.Text(string="Checklist", help="Eén stap per regel. Elke nieuwe aanvraag krijgt deze stappen.")
    description = fields.Text(string="Werkwijze")

    _code_unique = models.Constraint("UNIQUE (code)", "Er bestaat al een aanvraagtype met deze procedure.")


class VmeRequestCheck(models.Model):
    _name = "vme.request.check"
    _description = "Stap in de checklist van een aanvraag"
    _order = "request_id, sequence, id"

    request_id = fields.Many2one("vme.request", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Stap", required=True)
    done = fields.Boolean(string="Gedaan")
    done_date = fields.Date(string="Gedaan op", compute="_compute_done_date", store=True, readonly=False)

    @api.depends("done")
    def _compute_done_date(self):
        for check in self:
            check.done_date = check.done and (check.done_date or fields.Date.context_today(check))


class VmeRequest(models.Model):
    _name = "vme.request"
    _description = "Aanvraag van een bewoner"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    name = fields.Char(string="Nummer", readonly=True, copy=False, default="/")
    title = fields.Char(string="Onderwerp", required=True)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    lot_id = fields.Many2one(
        "vme.lot", string="Kavel", index=True, tracking=True, domain="[('association_id', '=', association_id)]")
    request_type_id = fields.Many2one("vme.request.type", string="Soort aanvraag", required=True, tracking=True)
    type_code = fields.Selection(related="request_type_id.code", store=True, string="Procedure")
    channel = fields.Selection(
        [("mail", "E-mail"), ("portal", "Portaal"), ("manual", "Manueel")],
        string="Kanaal", required=True, default="manual",
    )
    source_reference = fields.Char(string="Referentie bron", index=True, copy=False,
                                   help="Message-ID van de mail, zodat dezelfde mail maar één aanvraag wordt.")
    request_date = fields.Date(string="Ontvangen op", required=True, default=fields.Date.context_today)
    description = fields.Text(string="Vraag")
    user_id = fields.Many2one("res.users", string="Verantwoordelijke", default=lambda self: self.env.user,
                              domain="[('share', '=', False)]", tracking=True)
    state = fields.Selection(STATES, string="Status", required=True, default="new", tracking=True, copy=False)

    requester_id = fields.Many2one("res.partner", string="Aanvrager", required=True, tracking=True)
    requester_email = fields.Char(related="requester_id.email", string="E-mail aanvrager")
    requester_role = fields.Selection(
        REQUESTER_ROLES, string="Aanvrager is", compute="_compute_requester_role", store=True, readonly=False,
        tracking=True, help="Herkend aan het e-mailadres. Pas aan als de aanvrager zich anders voorstelt.",
    )
    owner_id = fields.Many2one(
        "res.partner", string="Eigenaar van de kavel", compute="_compute_owner", store=True,
        help="Eigenaar op de datum van de aanvraag. Krijgt een privé-aanrekening.",
    )
    check_ids = fields.One2many("vme.request.check", "request_id", string="Checklist", copy=True)
    checks_progress = fields.Char(string="Voortgang checklist", compute="_compute_checks_progress")

    # Verification
    needs_verification = fields.Boolean(string="Bewijs nodig", compute="_compute_needs_verification", store=True)
    proof_ownership = fields.Boolean(string="Eigendomsbewijs ontvangen en nagekeken", tracking=True)
    proof_owner_consent = fields.Boolean(string="Toestemming eigenaar ontvangen en nagekeken", tracking=True)
    proof_lease = fields.Boolean(string="Huurcontract ontvangen en nagekeken", tracking=True)
    proof_attachment_ids = fields.Many2many("ir.attachment", string="Bewijsstukken")
    missing_proofs = fields.Char(string="Ontbrekend bewijs", compute="_compute_missing_proofs")
    proof_requested_date = fields.Date(string="Bewijs gevraagd op", readonly=True, copy=False)
    proof_reminder_date = fields.Date(string="Herinnering verstuurd op", readonly=True, copy=False)
    reminder_due = fields.Boolean(string="Herinnering nodig", compute="_compute_reminder_due")
    verified_date = fields.Date(string="Geverifieerd op", readonly=True, copy=False)
    proof_mail_body = fields.Html(string="Concept bewijsvraag", copy=False)
    refuse_reason = fields.Char(string="Reden weigering", copy=False)

    # Key or badge
    key_kind = fields.Selection(KEY_KINDS, string="Soort sleutel of badge")
    quantity = fields.Integer(string="Aantal", default=1)
    unit_price = fields.Monetary(string="Prijs per stuk", compute="_compute_unit_price", store=True, readonly=False,
                                 help="Inclusief btw: voor de VME is de btw een kost.")
    amount = fields.Monetary(string="Privé aan te rekenen", compute="_compute_amount", store=True)
    locksmith_id = fields.Many2one(related="association_id.locksmith_partner_id", string="Slotenmaker")
    order_mail_subject = fields.Char(string="Onderwerp bestelling", copy=False)
    order_mail_body = fields.Html(string="Concept bestelling", copy=False)
    order_attachment_id = fields.Many2one("ir.attachment", string="Bestelbon", readonly=True, copy=False)
    order_ready = fields.Boolean(string="Bestelling klaar", compute="_compute_order_ready")
    order_sent_date = fields.Date(string="Besteld op", readonly=True, copy=False)
    key_numbers = fields.Char(string="Nummers", copy=False,
                              help="Nummers van de geleverde sleutels of badges, gescheiden door komma's.")
    delivery_date = fields.Date(string="Geleverd op", copy=False)
    key_ids = fields.One2many("vme.lot.key", "request_id", string="Geregistreerd")
    invoice_id = fields.Many2one("account.move", string="Factuur eigenaar", readonly=True, copy=False)

    # Other procedures
    blocked_key_ids = fields.Many2many(
        "vme.lot.key", "vme_request_blocked_key_rel", "request_id", "key_id", string="Te blokkeren",
        domain="[('lot_id', '=', lot_id), ('state', '=', 'active')]",
    )
    planned_date = fields.Date(string="Datum", help="Datum van de verhuis of begin van de huur.")
    tenant_partner_id = fields.Many2one("res.partner", string="Nieuwe huurder")
    decision_route = fields.Selection(
        [("council", "Advies van de raad van mede-eigendom"), ("assembly", "Punt op de volgende AV")],
        string="Beslissing via",
    )
    assembly_item_id = fields.Many2one("vme.assembly.item", string="Agendapunt", readonly=True, copy=False)

    # Computes

    @api.depends("requester_id", "lot_id", "request_date")
    def _compute_requester_role(self):
        for request in self:
            if request.requester_id and request.association_id:
                role, _lot = request._identify(request.requester_id.email, request.lot_id, request.request_date)
                request.requester_role = role
            elif not request.requester_role:
                request.requester_role = "unknown"

    @api.depends("lot_id", "request_date")
    def _compute_owner(self):
        for request in self:
            request.owner_id = request.lot_id and request.lot_id._get_owner_on(request.request_date)

    @api.depends("check_ids.done")
    def _compute_checks_progress(self):
        for request in self:
            request.checks_progress = f"{len(request.check_ids.filtered('done'))}/{len(request.check_ids)}"

    @api.depends("request_type_id.needs_verification", "requester_role")
    def _compute_needs_verification(self):
        for request in self:
            request.needs_verification = request.request_type_id.needs_verification and request.requester_role != "owner"

    @api.depends("requester_role", "proof_ownership", "proof_owner_consent", "proof_lease")
    def _compute_missing_proofs(self):
        for request in self:
            missing = request._missing_proof_fields()
            request.missing_proofs = ", ".join(PROOFS[f] for f in missing) if missing else False

    @api.depends("state", "proof_requested_date", "proof_reminder_date")
    def _compute_reminder_due(self):
        today = fields.Date.context_today(self)
        for request in self:
            request.reminder_due = bool(
                request.state == "waiting_proof" and request.proof_requested_date
                and not request.proof_reminder_date
                and request.proof_requested_date + timedelta(days=PROOF_REMINDER_DAYS) <= today
            )

    @api.depends("key_kind")
    def _compute_unit_price(self):
        for request in self:
            request.unit_price = KEY_KIND_PRICES.get(request.key_kind, 0.0)

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for request in self:
            request.amount = request.currency_id.round(request.quantity * request.unit_price) \
                if request.currency_id else request.quantity * request.unit_price

    @api.depends("state", "type_code", "order_attachment_id", "order_sent_date")
    def _compute_order_ready(self):
        for request in self:
            request.order_ready = bool(
                request.type_code == "key" and request.state == "in_progress"
                and request.order_attachment_id and not request.order_sent_date
            )

    def _missing_proof_fields(self):
        self.ensure_one()
        if not self.needs_verification:
            return []
        return [f for f in REQUIRED_PROOFS[self.requester_role or "unknown"] if not self[f]]

    # Who is asking?

    def _identify(self, email, lot=None, on_date=None):
        """Role of the person with this e-mail address for the lot: (role, lot).

        Without a lot, the lot is the one this person owns or rents in the VME.
        """
        self.ensure_one()
        return self.env["vme.request"]._identify_in(self.association_id, email, lot, on_date)

    @api.model
    def _identify_in(self, vme, email, lot=None, on_date=None):
        on_date = on_date or fields.Date.context_today(self)
        email = email_normalize(email or "")
        lots = lot or vme.sudo().lot_ids
        if not email:
            return "unknown", lot
        for candidate in lots.sorted(lambda l: (l.sequence, l.name)):
            owner = candidate.sudo()._get_owner_on(on_date)
            if owner and email_normalize(owner.email or "") == email:
                return "owner", candidate
        for candidate in lots.sorted(lambda l: (l.sequence, l.name)):
            tenants = candidate.sudo()._get_tenants_on(on_date)
            if any(email_normalize(t.email or "") == email for t in tenants):
                return "tenant", candidate
        return "unknown", lot

    # Intake: mail (ai/), portal (step 15) or manual

    @api.model
    def create_from_intake(self, association_id, request_type, email, name="", lot_id=False, subject="", body="",
                           channel="mail", reference="", summary="", proposed_reply="", attachments=None):
        """Create a request from an incoming mail or a portal form and start its procedure.

        Called over JSON-RPC by the AI assistant (ai/) and later by the owner portal. The requester
        is recognised by the e-mail address; an unknown address becomes a new contact.
        ``attachments`` is a list of {"name", "datas" (base64), "mimetype"}; ``proposed_reply`` is the
        reply the AI assistant suggests, kept as an internal note. Returns the request id;
        a second call with the same ``reference`` returns the existing request.
        """
        if reference:
            existing = self.search([("source_reference", "=", reference)], limit=1)
            if existing:
                return existing.id
        vme = self.env["vme.association"].browse(association_id).exists()
        request_type_rec = self.env["vme.request.type"].search([("code", "=", request_type)], limit=1)
        if not vme or not request_type_rec:
            raise UserError(self.env._("Onbekende VME of soort aanvraag."))
        lot = self.env["vme.lot"].browse(lot_id).exists() if lot_id else self.env["vme.lot"]
        if lot and lot.association_id != vme:
            lot = self.env["vme.lot"]
        role, lot = self._identify_in(vme, email, lot)
        partner = self._find_or_create_requester(vme, email, name, lot, role)
        text = f"{subject}\n{body}".lower()
        vals = {
            "association_id": vme.id,
            "lot_id": lot.id if lot else False,
            "request_type_id": request_type_rec.id,
            "title": subject or request_type_rec.name,
            "description": body,
            "channel": channel,
            "source_reference": reference or False,
            "requester_id": partner.id,
        }
        if request_type == "key":
            vals["key_kind"] = next(
                (kind for kind, words in KEY_KIND_WORDS if any(w in text for w in words)), "entrance_key")
        # Start the procedure after the incoming mail is in the chatter, so the history reads in order.
        request = self.with_context(vme_request_defer_start=True).create(vals).with_context(vme_request_defer_start=False)
        intro = self.env._("Ontvangen via %s.", dict(self._fields["channel"].selection)[channel])
        if summary:
            intro += " " + self.env._("Samenvatting: %s", summary)
        attachment_ids = [
            self.env["ir.attachment"].create({
                "name": att["name"], "datas": att["datas"], "mimetype": att.get("mimetype"),
                "res_model": request._name, "res_id": request.id,
            }).id
            for att in attachments or []
        ]
        request.message_post(
            body=Markup("<p>%s</p><p><b>%s</b></p><p>%s</p>") % (
                intro, subject, Markup("<br/>").join((body or "").splitlines())),
            attachment_ids=attachment_ids,
            message_type="comment", subtype_xmlid="mail.mt_note",
        )
        if proposed_reply:
            request.message_post(
                body=Markup("<p><b>%s</b></p><p>%s</p>") % (
                    self.env._("Voorgesteld antwoord van de AI-assistent (niet verstuurd):"),
                    Markup("<br/>").join(proposed_reply.splitlines())),
                message_type="comment", subtype_xmlid="mail.mt_note",
            )
        if attachment_ids:
            request.proof_attachment_ids = [Command.set(attachment_ids)]
        request._start_procedure()
        return request.id

    @api.model
    def _find_or_create_requester(self, vme, email, name, lot, role):
        Partner = self.env["res.partner"]
        if lot and role == "owner":
            return lot.current_owner_id or lot._get_owner_on(fields.Date.context_today(self))
        if lot and role == "tenant":
            normalized = email_normalize(email)
            return lot._get_tenants_on(fields.Date.context_today(self)).filtered(
                lambda p: email_normalize(p.email or "") == normalized)[:1]
        normalized = email_normalize(email or "")
        partner = normalized and Partner.search([("email_normalized", "=", normalized)], limit=1)
        return partner or Partner.create({"name": name or email or self.env._("Onbekende aanvrager"), "email": email})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("vme.request") or "/"
            if "check_ids" not in vals and vals.get("request_type_id"):
                lines = [line.strip() for line in (
                    self.env["vme.request.type"].browse(vals["request_type_id"]).checklist or "").splitlines()]
                vals["check_ids"] = [Command.create({"name": line, "sequence": i}) for i, line in enumerate(lines) if line]
        requests = super().create(vals_list)
        if not self.env.context.get("vme_request_defer_start"):
            requests._start_procedure()
        return requests

    @api.depends("name", "title")
    def _compute_display_name(self):
        for request in self:
            request.display_name = f"{request.name} {request.title or ''}".strip()

    # Procedure

    def _start_procedure(self):
        for request in self.filtered(lambda r: r.state == "new"):
            if request.needs_verification:
                request.write({"state": "waiting_proof", "proof_mail_body": request._proof_mail_body()})
                request._todo(
                    self.env._("Bewijs opvragen bij de aanvrager"),
                    note=self.env._("Kijk de bewijsvraag na in het tabblad Berichten en klik op \"Bewijs opvragen\"."),
                )
            elif request.type_code == "key":
                request._mark_verified(self.env._("De aanvrager is de eigenaar van de kavel."))
            else:
                request.state = "in_progress"
                if request.type_code == "damage":
                    request._forward_damage()

    def _todo(self, summary, deadline=None, note=""):
        self.ensure_one()
        return self.activity_schedule(
            "mail.mail_activity_data_todo", date_deadline=deadline or fields.Date.context_today(self),
            summary=summary, note=note, user_id=(self.user_id or self.env.user).id,
        )

    def _close_todos(self, feedback):
        self.activity_ids.action_feedback(feedback=feedback)

    def _item_label(self, article=True):
        self.ensure_one()
        if self.type_code == "key" and self.key_kind:
            label = dict(KEY_KINDS)[self.key_kind].lower()
            if self.quantity > 1:
                return f"{self.quantity} × {label}"
            return self.env._("een %s", label) if article else label
        return self.request_type_id.name.lower()

    def _proof_mail_body(self):
        self.ensure_one()
        role = self.requester_role or "unknown"
        proofs = [PROOFS[f] for f in REQUIRED_PROOFS[role]]
        lot = self.lot_id.name or self.env._("uw kavel")
        if role == "tenant":
            reason = self.env._("U staat bij ons gekend als huurder van kavel %s. Voor deze aanvraag hebben we nodig:", lot)
        else:
            reason = self.env._(
                "We vinden uw e-mailadres niet terug bij de eigenaars van %s. Om uw aanvraag te kunnen "
                "behandelen, hebben we nodig:", lot)
        return Markup(
            "<p>%(greeting)s</p><p>%(received)s</p><p>%(reason)s</p><ul>%(proofs)s</ul><p>%(cost)s</p>"
            "<p>%(reply)s</p><p>%(signature)s</p>"
        ) % {
            "greeting": self.env._("Beste %s,", self.requester_id.name),
            "received": self.env._("We ontvingen uw aanvraag voor %(item)s voor %(vme)s, kavel %(lot)s.",
                                   item=self._item_label(), vme=self.association_id.name, lot=lot),
            "reason": reason,
            "proofs": Markup("").join(Markup("<li>%s</li>") % p for p in proofs),
            "cost": self.env._("Alleen de syndicus kan veiligheidssleutels en badges bestellen. De kost wordt "
                               "aangerekend aan de eigenaar van de kavel."),
            "reply": self.env._("U kunt de documenten als bijlage op deze mail terugsturen. Zodra ze nagekeken "
                                "zijn, bestellen we uw %s.", self._item_label(article=False)),
            "signature": Markup("Met vriendelijke groeten,<br/>Het team van de syndicus"),
        }

    def _post_to(self, partners, subject, body, attachments=None):
        """Send one mail from the chatter of the request: only ever called from a button."""
        self.ensure_one()
        missing = partners.filtered(lambda p: not p.email)
        if missing:
            raise UserError(self.env._("%s heeft geen e-mailadres.", ", ".join(missing.mapped("name"))))
        return self.message_post(
            body=body, subject=subject, partner_ids=partners.ids,
            attachment_ids=(attachments or self.env["ir.attachment"]).ids,
            message_type="comment", subtype_xmlid="mail.mt_comment",
        )

    def action_send_proof_request(self):
        today = fields.Date.context_today(self)
        for request in self:
            if request.state != "waiting_proof":
                raise UserError(self.env._("Deze aanvraag wacht niet op bewijs."))
            request._post_to(request.requester_id,
                             self.env._("Uw aanvraag %(name)s: bewijs nodig", name=request.name),
                             request.proof_mail_body or request._proof_mail_body())
            request._close_todos(self.env._("Bewijs opgevraagd."))
            request.proof_requested_date = today
            request._todo(self.env._("Herinnering: bewijs nog niet ontvangen"),
                          deadline=today + timedelta(days=PROOF_REMINDER_DAYS),
                          note=self.env._("Nog geen bewijs? Klik op \"Herinnering versturen\"."))
        return True

    def action_send_proof_reminder(self):
        today = fields.Date.context_today(self)
        for request in self:
            if request.state != "waiting_proof" or not request.proof_requested_date:
                raise UserError(self.env._("Vraag eerst het bewijs op."))
            body = Markup("<p><b>%s</b></p>") % self.env._(
                "Herinnering: we ontvingen nog geen bewijs voor uw aanvraag van %s.",
                format_date(self.env, request.request_date),
            ) + (request.proof_mail_body or request._proof_mail_body())
            request._post_to(request.requester_id,
                             self.env._("Herinnering: uw aanvraag %(name)s", name=request.name), body)
            request._close_todos(self.env._("Herinnering verstuurd."))
            request.proof_reminder_date = today
            request._todo(self.env._("Bewijs opvolgen of aanvraag weigeren"),
                          deadline=today + timedelta(days=PROOF_REMINDER_DAYS))
        return True

    def action_verify(self):
        for request in self:
            if request.state != "waiting_proof":
                raise UserError(self.env._("Deze aanvraag wacht niet op bewijs."))
            if request._missing_proof_fields():
                raise UserError(self.env._("Nog niet ontvangen of nagekeken: %s.", request.missing_proofs))
            request._mark_verified(self.env._("Bewijs nagekeken door %s.", self.env.user.name))
        return True

    def _mark_verified(self, reason):
        self.ensure_one()
        self._close_todos(self.env._("Geverifieerd."))
        self.write({"state": "in_progress", "verified_date": fields.Date.context_today(self)})
        self.message_post(body=self.env._("Geverifieerd: %s", reason))
        if self.type_code == "key":
            self._prepare_order()
            if self.order_ready and self._auto_send_order():
                self.action_send_order()

    def _auto_send_order(self):
        """Whether the order may leave without a click after verification.

        Hook for a later per-VME setting ("bestelling automatisch versturen na verificatie");
        until that decision is taken, nothing is sent by itself (see docs/beslissingen.md).
        """
        return False

    def _prepare_order(self):
        """Order form for the locksmith as PDF plus a draft mail, ready to send with one click."""
        self.ensure_one()
        if not self.locksmith_id:
            self._todo(self.env._("Slotenmaker instellen voor %s", self.association_id.name),
                       note=self.env._("Vul de slotenmaker in op de VME en klik dan op \"Bestelling opnieuw opmaken\"."))
            return False
        content, _ext = self.env["ir.actions.report"]._render_qweb_pdf("vme_belgie.action_report_request_order", self.ids)
        if self.order_attachment_id:
            self.order_attachment_id.unlink()
        self.order_attachment_id = self.env["ir.attachment"].create({
            "name": self.env._("Bestelbon %s.pdf", self.name.replace("/", "-")),
            "datas": base64.b64encode(content), "mimetype": "application/pdf",
            "res_model": self._name, "res_id": self.id,
        })
        vme = self.association_id
        self.order_mail_subject = self.env._("Bestelling %(item)s %(vme)s, %(name)s",
                                             item=self._item_label(article=False), vme=vme.name, name=self.name)
        self.order_mail_body = Markup(
            "<p>%s</p><p>%s</p><ul><li>%s</li><li>%s</li><li>%s</li></ul><p>%s</p><p>%s</p>"
        ) % (
            self.env._("Beste %s,", self.locksmith_id.name),
            self.env._("Als syndicus van %s bestellen we:", vme.name),
            self.env._("%(item)s voor kavel %(lot)s", item=self._item_label(), lot=self.lot_id.name or "-"),
            self.env._("Sleutelcertificaat: %s", vme.key_certificate_ref or self.env._("zie bijlage")),
            self.env._("Referentie: %s", self.name),
            self.env._("De bestelbon zit in bijlage. Graag een bevestiging met de leverdatum en de nummers."),
            Markup("Met vriendelijke groeten,<br/>Het team van de syndicus"),
        )
        self._todo(self.env._("Bestelling slotenmaker nakijken en versturen"),
                   note=self.env._("De bestelling staat klaar als concept in het tabblad Berichten."))
        return True

    def action_prepare_order(self):
        for request in self:
            if request.type_code != "key" or request.state != "in_progress":
                raise UserError(self.env._("Alleen een geverifieerde aanvraag voor een sleutel of badge kan besteld worden."))
            request._prepare_order()
        return True

    def action_send_order(self):
        """Send the prepared order to the locksmith of the VME: the one click of the staff member."""
        today = fields.Date.context_today(self)
        for request in self:
            if not request.order_ready:
                raise UserError(self.env._("Er staat geen bestelling klaar voor %s.", request.name))
            attachments = request.order_attachment_id
            certificate = request.association_id.key_certificate_file and self.env["ir.attachment"].sudo().search([
                ("res_model", "=", "vme.association"), ("res_id", "=", request.association_id.id),
                ("res_field", "=", "key_certificate_file")], limit=1)
            if certificate:
                attachments |= certificate.copy({
                    "name": request.association_id.key_certificate_filename or certificate.name,
                    "res_model": request._name, "res_id": request.id, "res_field": False,
                })
            request._post_to(request.locksmith_id, request.order_mail_subject, request.order_mail_body, attachments)
            request._close_todos(self.env._("Bestelling verstuurd."))
            request.write({"state": "ordered", "order_sent_date": today})
            request._todo(self.env._("Levering opvolgen en registreren"),
                          deadline=today + timedelta(days=DELIVERY_FOLLOW_UP_DAYS))
        return True

    def _parse_key_numbers(self):
        self.ensure_one()
        return [n.strip() for n in re.split(r"[,;\n]", self.key_numbers or "") if n.strip()]

    def action_register_delivery(self):
        """Register the delivered keys in the lot's register and charge the owner privately."""
        for request in self:
            if request.type_code != "key" or request.state != "ordered":
                raise UserError(self.env._("Alleen een bestelde sleutel of badge kan geleverd worden."))
            numbers = request._parse_key_numbers()
            if len(numbers) != request.quantity:
                raise UserError(self.env._(
                    "Vul %(qty)s nummer(s) in, gescheiden door komma's (nu %(count)s).",
                    qty=request.quantity, count=len(numbers)))
            if not request.lot_id or not request.owner_id:
                raise UserError(self.env._("Kies de kavel: de eigenaar krijgt de kost aangerekend."))
            delivery = request.delivery_date or fields.Date.context_today(self)
            self.env["vme.lot.key"].create([{
                "lot_id": request.lot_id.id, "kind": request.key_kind, "number": number,
                "issue_date": delivery, "partner_id": request.requester_id.id, "request_id": request.id,
            } for number in numbers])
            invoice = request._create_private_invoice(delivery) if request.amount else self.env["account.move"]
            request._close_todos(self.env._("Geleverd."))
            request.write({"state": "done", "delivery_date": delivery, "invoice_id": invoice.id})
            request.message_post(body=self.env._(
                "Geleverd en geregistreerd: %(numbers)s.%(invoice)s", numbers=", ".join(numbers),
                invoice=invoice and self.env._(" Aangerekend aan %(owner)s met factuur %(name)s.",
                                               owner=request.owner_id.name, name=invoice.name) or ""))
        return True

    @api.model
    def _private_charge_account(self, company):
        Account = self.env["account.account"].sudo().with_company(company)
        code, name = PRIVATE_CHARGE_ACCOUNT
        account = Account.search([("company_ids", "in", company.id), ("code", "=", code)], limit=1)
        return account or Account.create({
            "code": code, "name": name, "account_type": "asset_current", "company_ids": [company.id],
        })

    def _create_private_invoice(self, invoice_date):
        """Invoice to the owner of the lot in the VME's company; it is not distributed over the owners."""
        self.ensure_one()
        company = self.company_id
        journal = self.env["account.journal"].sudo().search(
            [("company_id", "=", company.id), ("type", "=", "sale")], limit=1)
        if not journal:
            raise UserError(self.env._("Het rekeningstelsel van %s is niet volledig.", self.association_id.name))
        invoice = self.env["account.move"].sudo().with_company(company).create({
            "move_type": "out_invoice",
            "journal_id": journal.id,
            "partner_id": self.owner_id.id,
            "invoice_date": invoice_date,
            "invoice_date_due": invoice_date + timedelta(days=PRIVATE_INVOICE_DUE_DAYS),
            # Paid to the working capital account, like the other income of the VME.
            "vme_fund": "working",
            "vme_request_id": self.id,
            "ref": self.name,
            "invoice_line_ids": [Command.create({
                "name": self.env._("%(item)s kavel %(lot)s (aanvraag %(name)s), privé aangerekend",
                                   item=self._item_label(article=False).capitalize(), lot=self.lot_id.name, name=self.name),
                "quantity": self.quantity,
                "price_unit": self.unit_price,
                "account_id": self._private_charge_account(company).id,
                "tax_ids": [Command.clear()],
            })],
        })
        invoice.action_post()
        return invoice

    def action_refuse(self):
        for request in self:
            if not request.refuse_reason:
                raise UserError(self.env._("Vul de reden van de weigering in."))
            request._close_todos(self.env._("Geweigerd."))
            request.state = "refused"
            request.message_post(body=self.env._("Geweigerd: %s", request.refuse_reason))
        return True

    def action_done(self):
        for request in self:
            if request.type_code == "key":
                raise UserError(self.env._("Een sleutel of badge wordt afgesloten door de levering te registreren."))
            request._close_todos(self.env._("Afgehandeld."))
            request.state = "done"
        return True

    def action_cancel(self):
        self._close_todos(self.env._("Geannuleerd."))
        self.state = "cancelled"

    def action_reset(self):
        """Back to the start of the procedure, e.g. after correcting the role of the requester."""
        for request in self.filtered(lambda r: r.state in ("waiting_proof", "refused", "cancelled")):
            request._close_todos(self.env._("Opnieuw gestart."))
            request.write({"state": "new", "proof_requested_date": False, "proof_reminder_date": False})
            request._start_procedure()
        return True

    # Procedures of the other request types

    def action_block_keys(self):
        for request in self:
            if not request.blocked_key_ids:
                raise UserError(self.env._("Kies de badges of sleutels die geblokkeerd moeten worden."))
            request.blocked_key_ids.action_block(request=request)
            request.message_post(body=self.env._(
                "Geblokkeerd in het register: %s. Laat ze ook blokkeren in het toegangssysteem.",
                ", ".join(request.blocked_key_ids.mapped("display_name"))))
        return True

    def action_register_tenant(self):
        # LEGAL-CHECK: art. 3.93 BW - the house rules (reglement van orde) bind tenants and occupants once
        # they are made known to them; the checklist asks to send them to the new tenant. To be confirmed.
        for request in self:
            tenant = request.tenant_partner_id or (request.requester_role == "tenant" and request.requester_id)
            if not tenant or not request.lot_id:
                raise UserError(self.env._("Vul de kavel en de nieuwe huurder in."))
            self.env["vme.lot.contact"].create({
                "lot_id": request.lot_id.id, "partner_id": tenant.id, "role": "tenant",
                "date_start": request.planned_date or fields.Date.context_today(self),
            })
            request.message_post(body=self.env._(
                "%(tenant)s geregistreerd als huurder van %(lot)s. Bezorg hem of haar het reglement van orde.",
                tenant=tenant.name, lot=request.lot_id.name))
        return True

    def action_add_to_assembly(self):
        """Put the permission on the agenda of the next assembly of the VME that is not held yet."""
        for request in self:
            assembly = self.env["vme.assembly"].search([
                ("association_id", "=", request.association_id.id),
                ("state", "in", ("draft", "proposed", "confirmed")),
            ], order="year, date, id", limit=1)
            if not assembly:
                raise UserError(self.env._("Er is nog geen volgende algemene vergadering voor %s.",
                                           request.association_id.name))
            item = self.env["vme.assembly.item"].create({
                "assembly_id": assembly.id,
                "sequence": max(assembly.item_ids.mapped("sequence") or [0]) + 10,
                "name": self.env._("Toestemming werken aan privatief %(lot)s: %(title)s",
                                   lot=request.lot_id.name or "", title=request.title),
                "description": request.description,
                "majority": WORKS_PERMISSION_MAJORITY,
            })
            request.write({"assembly_item_id": item.id, "decision_route": "assembly"})
            request.message_post(body=self.env._("Geagendeerd op %s.", assembly.display_name))
        return True

    def _forward_damage(self):
        """Hand a reported defect or damage over to the damage files of step 14.

        Link point: once the model ``vme.damage.claim`` exists with a method
        ``_create_from_request(request)``, the claim is created there. Until then the staff member
        gets a to-do with the report.
        """
        for request in self:
            Claim = self.env["vme.damage.claim"] if "vme.damage.claim" in self.env else None
            if Claim is not None and hasattr(Claim, "_create_from_request"):
                claim = Claim._create_from_request(request)
                request.message_post(body=self.env._("Doorgestuurd naar schadedossier %s.", claim.display_name))
            else:
                request._todo(self.env._("Defect of schade doorsturen naar een schadedossier"),
                              note=escape(request.description or request.title))


class AccountMove(models.Model):
    _inherit = "account.move"

    vme_request_id = fields.Many2one(
        "vme.request", string="Aanvraag", index=True, copy=False,
        help="Privé-kost van een aanvraag: niet verdeeld over de eigenaars en niet in de jaarafrekening.",
    )

    def _vme_auto_distribute(self):
        # A locksmith's bill for a private request is charged to one owner, not distributed.
        return super(AccountMove, self.filtered(lambda m: not m.vme_request_id))._vme_auto_distribute()
