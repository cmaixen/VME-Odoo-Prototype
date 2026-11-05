"""Central communication with owners and tenants: mailings, surveys, the log per person and registered mail."""
import base64

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools import format_date

from .communication_providers import get_provider

# Channels a mailing can ask for; "preference" follows the paper or e-mail choice of each person.
REQUESTED_CHANNELS = [
    ("preference", "Volgens voorkeur (e-mail of brief)"),
    ("letter", "Brief per post"),
    ("registered", "Aangetekend"),
    ("sms", "Sms"),
    ("push", "Pushbericht"),
]
# Channels a person is actually reached by.
CHANNELS = [
    ("email", "E-mail"),
    ("letter", "Brief per post"),
    ("registered", "Aangetekend"),
    ("sms", "Sms"),
    ("push", "Pushbericht"),
]
AUDIENCES = [
    ("all_owners", "Alle eigenaars"),
    ("block", "Eigenaars van een blok"),
    ("lots", "Eigenaars van gekozen kavels"),
    ("tenants", "Huurders"),
    ("partners", "Gekozen personen"),
]
ROLES = [("owner", "Eigenaar"), ("tenant", "Huurder"), ("other", "Andere")]


def render_placeholders(text, values):
    """Replace {eigenaar}, {kavels}, ... in an HTML text by escaped values."""
    if not text:
        return text
    result = str(text)
    for key, value in values.items():
        result = result.replace("{%s}" % key, str(escape(value or "")))
    return Markup(result)


class ResPartner(models.Model):
    _inherit = "res.partner"

    vme_communication_preference = fields.Selection(
        [("email", "E-mail"), ("paper", "Papier (brief per post)")],
        string="Voorkeur communicatie", default="email",
        help="Mededelingen gaan per e-mail, tenzij deze persoon papier vraagt of geen e-mailadres heeft.")
    vme_communication_log_ids = fields.One2many("vme.communication.log", "partner_id", string="Communicatielog")
    vme_communication_count = fields.Integer(string="Communicatie", compute="_compute_vme_communication_count")

    def _compute_vme_communication_count(self):
        counts = dict(self.env["vme.communication.log"]._read_group(
            [("partner_id", "in", self.ids)], ["partner_id"], ["__count"]))
        for partner in self:
            partner.vme_communication_count = counts.get(partner, 0)

    def action_open_vme_communication_log(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Communicatielog %s", self.name),
            "res_model": "vme.communication.log",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {"search_default_group_association": 1},
        }


class VmeLot(models.Model):
    _inherit = "vme.lot"

    building_block = fields.Char(string="Blok", index=True, help="Bijvoorbeeld A of B: om mededelingen per blok te versturen.")

    def _get_tenants_on(self, date):
        """Tenants of these lots on the given date.

        Hook for the tenants of steps 19 and 25 (rental management): they override this method.
        Until then nobody rents, so a mailing to the tenants has no recipients.
        """
        return self.env["res.partner"]


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    communication_count = fields.Integer(string="Verzendingen", compute="_compute_communication_count")

    def _compute_communication_count(self):
        counts = dict(self.env["vme.communication"]._read_group(
            [("association_id", "in", self.ids)], ["association_id"], ["__count"]))
        for vme in self:
            vme.communication_count = counts.get(vme, 0)

    def action_open_communications(self):
        return self._action_open_related("vme.communication", self.env._("Verzendingen"))


class VmeCommunicationTemplate(models.Model):
    _name = "vme.communication.template"
    _description = "Sjabloon voor een verzending"
    _order = "sequence, name"

    name = fields.Char(string="Sjabloon", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection([("message", "Mededeling"), ("survey", "Bevraging")], string="Soort",
                            required=True, default="message")
    channel = fields.Selection(REQUESTED_CHANNELS, string="Kanaal", required=True, default="preference")
    subject = fields.Char(string="Onderwerp", required=True)
    body_html = fields.Html(string="Tekst", sanitize_style=True,
                            help="Plaatshouders: {eigenaar}, {kavels}, {vme}, {adres_vme}, {datum}.")
    short_text = fields.Char(string="Korte tekst (sms, push)")
    question = fields.Char(string="Vraag")
    option_names = fields.Text(string="Antwoorden", help="Eén mogelijk antwoord per regel.")


class VmeCommunication(models.Model):
    _name = "vme.communication"
    _description = "Verzending aan eigenaars of huurders"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Onderwerp", required=True)
    association_id = fields.Many2one("vme.association", string="VME", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    template_id = fields.Many2one("vme.communication.template", string="Sjabloon")
    kind = fields.Selection([("message", "Mededeling"), ("survey", "Bevraging")], string="Soort",
                            required=True, default="message")
    state = fields.Selection([("draft", "Concept"), ("sent", "Verstuurd"), ("cancel", "Geannuleerd")],
                             string="Status", default="draft", required=True, tracking=True)
    audience = fields.Selection(AUDIENCES, string="Ontvangers", required=True, default="all_owners")
    building_block = fields.Char(string="Blok")
    lot_ids = fields.Many2many("vme.lot", string="Kavels", domain="[('association_id', '=', association_id)]")
    partner_ids = fields.Many2many("res.partner", string="Personen")
    reference_date = fields.Date(string="Eigenaar op", required=True, default=fields.Date.context_today,
                                 help="De ontvangers zijn de eigenaars (of huurders) op deze datum.")
    channel = fields.Selection(REQUESTED_CHANNELS, string="Kanaal", required=True, default="preference")
    body_html = fields.Html(string="Tekst", sanitize_style=True)
    short_text = fields.Char(string="Korte tekst (sms, push)")
    question = fields.Char(string="Vraag")
    answer_deadline = fields.Date(string="Antwoorden tegen")
    option_ids = fields.One2many("vme.communication.option", "communication_id", string="Mogelijke antwoorden")
    log_ids = fields.One2many("vme.communication.log", "communication_id", string="Ontvangerslijnen")
    recipient_count = fields.Integer(string="Aantal ontvangers", compute="_compute_stats")
    answer_count = fields.Integer(string="Aantal antwoorden", compute="_compute_stats")
    channel_summary = fields.Char(string="Per kanaal", compute="_compute_stats")
    sent_date = fields.Date(string="Verstuurd op", readonly=True)
    letter_attachment_id = fields.Many2one("ir.attachment", string="Brieven voor de post", readonly=True)
    sale_file_id = fields.Many2one("vme.sale.file", string="Verkoopdossier", index=True, ondelete="set null")

    @api.depends("log_ids.channel", "log_ids.answer_option_id", "log_ids.state")
    def _compute_stats(self):
        labels = dict(CHANNELS)
        for communication in self:
            logs = communication.log_ids.filtered(lambda log: log.state != "cancel")
            communication.recipient_count = len(logs)
            communication.answer_count = len(logs.filtered("answer_option_id"))
            parts = []
            for code, label in CHANNELS:
                count = len(logs.filtered(lambda log, c=code: log.channel == c))
                if count:
                    parts.append(f"{label}: {count}")
            communication.channel_summary = ", ".join(parts) or False

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self._apply_template(self.template_id)

    def _apply_template(self, template):
        self.update(self._template_values(template))

    @api.model
    def _template_values(self, template):
        values = {
            "name": template.subject, "kind": template.kind, "channel": template.channel,
            "body_html": template.body_html, "short_text": template.short_text, "question": template.question,
        }
        options = [line.strip() for line in (template.option_names or "").splitlines() if line.strip()]
        if template.kind == "survey" and options:
            values["option_ids"] = [Command.clear()] + [
                Command.create({"name": option, "sequence": index}) for index, option in enumerate(options)]
        return values

    # ------------------------------------------------------------------
    # Recipients
    # ------------------------------------------------------------------

    def _get_target_lots(self):
        self.ensure_one()
        lots = self.association_id.lot_ids
        if self.audience == "block":
            block = (self.building_block or "").strip().lower()
            lots = lots.filtered(lambda lot: (lot.building_block or "").strip().lower() == block)
        elif self.audience == "lots":
            lots = self.lot_ids
        return lots.sorted(lambda lot: (lot.sequence, lot.name))

    def _get_recipients(self):
        """[(partner, lots, role)] in lot order, one entry per person.

        Owners are taken on the reference date, so after a sale the buyer gets the letter and the
        seller does not. An owner of several lots (apartment and garage) gets one letter.
        """
        self.ensure_one()
        date = self.reference_date or fields.Date.context_today(self)
        recipients = {}

        def add(partner, lot, role):
            if not partner:
                return
            entry = recipients.setdefault(partner, [self.env["vme.lot"], role])
            if lot:
                entry[0] |= lot

        if self.audience == "partners":
            # A welcome letter only names the lots of the sale, not other lots the buyer already owned.
            owned = self.sale_file_id.lot_ids or self.association_id.lot_ids
            for partner in self.partner_ids:
                lots = owned.filtered(lambda lot, p=partner: lot._get_owner_on(date) == p)
                add(partner, False, "owner" if lots else "other")
                recipients[partner][0] |= lots
        elif self.audience == "tenants":
            for lot in self.association_id.lot_ids.sorted(lambda lot: (lot.sequence, lot.name)):
                for tenant in lot._get_tenants_on(date):
                    add(tenant, lot, "tenant")
        else:
            for lot in self._get_target_lots():
                add(lot._get_owner_on(date), lot, "owner")
        return [(partner, lots, role) for partner, (lots, role) in recipients.items()]

    def _resolve_channel(self, partner):
        """Channel by which this person is reached: the requested one, or paper or e-mail as fallback."""
        self.ensure_one()

        def by_preference():
            if partner.vme_communication_preference != "paper" and partner.email:
                return "email"
            return "letter"

        if self.channel == "preference":
            return by_preference()
        if self.channel == "sms":
            return "sms" if partner.phone else by_preference()
        if self.channel == "push":
            return "push" if get_provider(self.env, "push").can_reach(partner) else by_preference()
        # LEGAL-CHECK: art. 3.87 §3 BW - convocations go by registered letter unless the owner agreed
        # individually and in writing to another means; registered and letter ignore the preference.
        return self.channel

    def _placeholder_values(self, partner, lots):
        vme = self.association_id
        return {
            "eigenaar": partner.name,
            "kavels": ", ".join(lots.mapped("name")),
            "vme": vme.name,
            "adres_vme": ", ".join(filter(None, [vme.street, f"{vme.zip or ''} {vme.city or ''}".strip()])),
            "datum": format_date(self.env, self.reference_date),
        }

    def _check_editable(self):
        if self.filtered(lambda c: c.state != "draft"):
            raise UserError(self.env._("Alleen een concept kan nog gewijzigd worden."))

    def action_prepare_recipients(self):
        """(Re)build the draft recipients; nothing is sent."""
        self._check_editable()
        for communication in self:
            if communication.audience == "block" and not communication.building_block:
                raise UserError(self.env._("Vul het blok in."))
            # Draft lines only exist for this mailing; the log keeps everything that was sent.
            communication.log_ids.sudo().unlink()
            communication.write({"log_ids": [Command.create({
                "association_id": communication.association_id.id,
                "partner_id": partner.id,
                "lot_names": ", ".join(lots.mapped("name")),
                "role": role,
                "channel": communication._resolve_channel(partner),
                "subject": communication.name,
            }) for partner, lots, role in communication._get_recipients()]})
            communication._render_logs()
        return True

    def _render_logs(self):
        for communication in self:
            lots_by_name = {lot.name: lot for lot in communication.association_id.lot_ids}
            for log in communication.log_ids:
                lots = self.env["vme.lot"].browse(
                    [lots_by_name[name].id for name in (log.lot_names or "").split(", ") if name in lots_by_name])
                values = communication._placeholder_values(log.partner_id, lots)
                body = render_placeholders(communication.body_html, values)
                if communication.kind == "survey":
                    body = (body or Markup("")) + communication._survey_html()
                log.write({
                    "subject": render_placeholders(communication.name, values),
                    "body_html": body,
                    "short_text": render_placeholders(communication.short_text or communication.name, values),
                })

    def _survey_html(self):
        self.ensure_one()
        options = Markup("").join(Markup("<li>%s</li>") % option.name for option in self.option_ids)
        deadline = (Markup("<p>Graag uw antwoord tegen %s.</p>") % format_date(self.env, self.answer_deadline)
                    if self.answer_deadline else Markup(""))
        return Markup("<p><strong>%s</strong></p><ul>%s</ul>%s") % (self.question or "", options, deadline)

    # ------------------------------------------------------------------
    # Confirm and send
    # ------------------------------------------------------------------

    def action_confirm(self):
        """The employee confirms the draft: only now e-mails are queued, letters printed and the register filled."""
        self._check_editable()
        for communication in self:
            if communication.kind == "survey" and not communication.option_ids:
                raise UserError(self.env._("Een bevraging heeft minstens één mogelijk antwoord nodig."))
            if not communication.log_ids:
                communication.action_prepare_recipients()
            if not communication.log_ids:
                raise UserError(self.env._("Deze verzending heeft geen ontvangers."))
            communication._render_logs()
            communication.log_ids._send()
            letters = communication.log_ids.filtered(lambda log: log.channel == "letter")
            if letters:
                subject = render_placeholders(communication.name, {"vme": communication.association_id.name})
                communication.letter_attachment_id = letters._render_pdf(
                    self.env._("Brieven voor de post - %s.pdf", subject), communication)
            communication.write({"state": "sent", "sent_date": fields.Date.context_today(self)})
            communication.message_post(body=self.env._(
                "Verstuurd aan %(count)s ontvangers (%(channels)s).",
                count=communication.recipient_count, channels=communication.channel_summary))
        return True

    def action_cancel(self):
        self._check_editable()
        self.log_ids.write({"state": "cancel"})
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        cancelled = self.filtered(lambda c: c.state == "cancel")
        cancelled.log_ids.write({"state": "draft"})
        cancelled.write({"state": "draft"})

    def action_print_letters(self):
        self.ensure_one()
        logs = self.log_ids.filtered(lambda log: log.channel in ("letter", "registered") and log.state != "cancel")
        if not logs:
            raise UserError(self.env._("Er zijn geen brieven in deze verzending."))
        return self.env.ref("vme_belgie.action_report_communication_letter").report_action(logs)

    def action_open_logs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Ontvangers"),
            "res_model": "vme.communication.log",
            "view_mode": "list,form",
            "domain": [("communication_id", "=", self.id)],
        }


class VmeCommunicationOption(models.Model):
    _name = "vme.communication.option"
    _description = "Mogelijk antwoord op een bevraging"
    _order = "sequence, id"

    communication_id = fields.Many2one("vme.communication", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Antwoord", required=True)
    answer_count = fields.Integer(string="Aantal", compute="_compute_answer_count")

    @api.depends("communication_id.log_ids.answer_option_id")
    def _compute_answer_count(self):
        for option in self:
            option.answer_count = len(option.communication_id.log_ids.filtered(lambda log, o=option: log.answer_option_id == o))


class VmeCommunicationLog(models.Model):
    _name = "vme.communication.log"
    _description = "Communicatie met een eigenaar of huurder"
    # Newest first in the log of a person; within one mailing in the order of the lots.
    _order = "date desc, id"
    _rec_name = "subject"

    communication_id = fields.Many2one("vme.communication", string="Verzending", index=True, ondelete="cascade")
    kind = fields.Selection(related="communication_id.kind")
    association_id = fields.Many2one("vme.association", string="VME", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Ontvanger", required=True, index=True, ondelete="cascade")
    email = fields.Char(related="partner_id.email")
    lot_names = fields.Char(string="Kavels")
    role = fields.Selection(ROLES, string="Als", default="owner")
    channel = fields.Selection(CHANNELS, string="Kanaal", required=True)
    subject = fields.Char(string="Onderwerp")
    body_html = fields.Html(string="Tekst", sanitize_style=True)
    short_text = fields.Char(string="Korte tekst")
    date = fields.Date(string="Datum", required=True, default=fields.Date.context_today)
    state = fields.Selection([("draft", "Concept"), ("sent", "Verstuurd"), ("cancel", "Geannuleerd")],
                             string="Status", default="draft", required=True)
    sent_date = fields.Date(string="Verstuurd op")
    source_model = fields.Char(string="Bronmodel", readonly=True)
    source_id = fields.Integer(string="Bron-id", readonly=True)
    source_name = fields.Char(string="Bron", readonly=True)
    mail_id = fields.Many2one("mail.mail", string="E-mail", readonly=True, ondelete="set null")
    provider_reference = fields.Char(string="Referentie provider", readonly=True)
    registered_mail_id = fields.Many2one("vme.registered.mail", string="Aangetekende zending", readonly=True)
    answer_option_id = fields.Many2one("vme.communication.option", string="Antwoord",
                                       domain="[('communication_id', '=', communication_id)]")
    answer_note = fields.Char(string="Opmerking bij het antwoord")
    answer_date = fields.Date(string="Antwoord op")

    @api.onchange("answer_option_id")
    def _onchange_answer_option_id(self):
        if self.answer_option_id and not self.answer_date:
            self.answer_date = fields.Date.context_today(self)

    def write(self, vals):
        if vals.get("answer_option_id") and "answer_date" not in vals:
            vals["answer_date"] = fields.Date.context_today(self)
        return super().write(vals)

    @api.model
    def _log_records(self, records, partner_field, subject, channel, state="draft", lot_names=None):
        """One log line per record of another step (convocation, reminder), linked back to that record."""
        return self.sudo().create([{
            "association_id": record.association_id.id,
            "partner_id": record[partner_field].id,
            "lot_names": lot_names(record) if lot_names else False,
            "channel": channel(record) if callable(channel) else channel,
            "subject": subject(record) if callable(subject) else subject,
            "state": state,
            "sent_date": fields.Date.context_today(self) if state == "sent" else False,
            "source_model": record._name,
            "source_id": record.id,
            "source_name": record.display_name,
        } for record in records])

    @api.model
    def _get_for_records(self, records):
        return self.sudo().search([("source_model", "=", records._name), ("source_id", "in", records.ids)])

    def _send(self):
        """Deliver each confirmed line by its channel. E-mails go to Odoo's outgoing mail queue."""
        today = fields.Date.context_today(self)
        sms = push = None
        for log in self.filtered(lambda line: line.state == "draft"):
            values = {"state": "sent", "sent_date": today}
            if log.channel == "email":
                company = log.association_id.company_id
                mail = self.env["mail.mail"].sudo().create({
                    "subject": log.subject,
                    "body_html": log.body_html,
                    "email_from": company.email_formatted or self.env.user.email_formatted,
                    "recipient_ids": [Command.link(log.partner_id.id)],
                    "model": log.communication_id._name if log.communication_id else False,
                    "res_id": log.communication_id.id if log.communication_id else False,
                    "auto_delete": False,
                })
                values["mail_id"] = mail.id
            elif log.channel == "sms":
                sms = sms or get_provider(self.env, "sms")
                values["provider_reference"] = sms.send(log.partner_id.phone, log.short_text or log.subject)
            elif log.channel == "push":
                push = push or get_provider(self.env, "push")
                values["provider_reference"] = push.send(log.partner_id, log.subject, log.short_text or log.subject)
            elif log.channel == "registered":
                attachment = log._render_pdf(f"{log.subject} - {log.partner_id.name}.pdf", log)
                values["registered_mail_id"] = self.env["vme.registered.mail"]._create_for(
                    log, attachment, log.subject).id
            log.write(values)

    def _render_pdf(self, name, attach_to):
        """Letters of these lines in one PDF, attached to the given record."""
        content, _ext = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
            "vme_belgie.action_report_communication_letter", self.ids)
        return self.env["ir.attachment"].sudo().create({
            "name": name, "datas": base64.b64encode(content), "mimetype": "application/pdf",
            "res_model": attach_to._name, "res_id": attach_to.id,
        })

    def action_open_source(self):
        self.ensure_one()
        if self.communication_id:
            model, res_id = self.communication_id._name, self.communication_id.id
        elif self.source_model and self.source_id:
            model, res_id = self.source_model, self.source_id
        else:
            return False
        return {"type": "ir.actions.act_window", "res_model": model, "res_id": res_id,
                "view_mode": "form", "views": [(False, "form")]}

    def action_print(self):
        return self.env.ref("vme_belgie.action_report_communication_letter").report_action(self)


class VmeRegisteredMail(models.Model):
    _name = "vme.registered.mail"
    _description = "Aangetekende zending"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    name = fields.Char(string="Nummer", required=True, readonly=True, copy=False, default="/")
    association_id = fields.Many2one("vme.association", string="VME", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Bestemmeling", required=True, index=True)
    address = fields.Text(string="Adres", help="Adres op het moment van de verzending.")
    subject = fields.Char(string="Onderwerp", required=True)
    source_name = fields.Char(string="Bron")
    log_id = fields.Many2one("vme.communication.log", string="Communicatielog", ondelete="set null")
    date = fields.Date(string="Opgemaakt op", required=True, default=fields.Date.context_today)
    attachment_id = fields.Many2one("ir.attachment", string="Brief (PDF)", readonly=True)
    # LEGAL-CHECK: Verordening (EU) 910/2014 (eIDAS) art. 43-44 en art. XII.25 §3 WER - an electronic
    # registered delivery by a qualified provider counts as a registered letter; whether that also holds for
    # a formal notice (ingebrekestelling, art. 5.231 BW) and for a convocation to the general assembly
    # (art. 3.87 §3 BW) still has to be confirmed by a lawyer.
    provider = fields.Selection([("post", "Papier, af te geven bij de post"), ("electronic", "Elektronisch aangetekend")],
                                string="Verzending", required=True, default="post")
    tracking_number = fields.Char(string="Zendingsnummer", tracking=True)
    state = fields.Selection([
        ("prepared", "Klaar om af te geven"),
        ("deposited", "Afgegeven"),
        ("delivered", "Ontvangen"),
        ("returned", "Niet afgehaald"),
    ], string="Status", required=True, default="prepared", tracking=True)
    deposit_date = fields.Date(string="Afgegeven op", tracking=True)
    delivery_date = fields.Date(string="Ontvangen op", tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("vme.registered.mail") or "/"
        return super().create(vals_list)

    @api.model
    def _create_for(self, log, attachment, subject):
        partner = log.partner_id
        address = "\n".join(filter(None, [
            partner.name, partner.street, partner.street2, " ".join(filter(None, [partner.zip, partner.city]))]))
        registered = self.sudo().create({
            "association_id": log.association_id.id,
            "partner_id": partner.id,
            "address": address,
            "subject": subject,
            "source_name": log.source_name or (log.communication_id.display_name if log.communication_id else False),
            "log_id": log.id,
            "attachment_id": attachment.id,
        })
        attachment.write({"res_model": registered._name, "res_id": registered.id})
        return registered

    def action_deposit(self):
        """The employee handed the letters to the post office (and noted the tracking numbers)."""
        for registered in self.filtered(lambda r: r.state == "prepared"):
            registered.write({"state": "deposited", "deposit_date": fields.Date.context_today(self)})

    def action_send_electronic(self):
        """Hand the PDF to the configured electronic registered mail provider (a mock in the prototype)."""
        provider = get_provider(self.env, "registered")
        for registered in self.filtered(lambda r: r.state == "prepared"):
            content = base64.b64decode(registered.attachment_id.datas or b"")
            reference = provider.submit(registered, content)
            registered.write({
                "provider": "electronic", "tracking_number": reference,
                "state": "deposited", "deposit_date": fields.Date.context_today(self),
            })

    def action_refresh_status(self):
        provider = get_provider(self.env, "registered")
        for registered in self.filtered(lambda r: r.provider == "electronic" and r.state == "deposited"):
            status = provider.get_status(registered.tracking_number)
            if status == "delivered":
                registered.action_delivered()
            elif status == "returned":
                registered.action_returned()

    def action_delivered(self):
        self.write({"state": "delivered", "delivery_date": fields.Date.context_today(self)})

    def action_returned(self):
        self.write({"state": "returned"})

    def action_download(self):
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(self.env._("Deze zending heeft geen PDF."))
        return {"type": "ir.actions.act_url", "url": f"/web/content/{self.attachment_id.id}?download=true",
                "target": "self"}


class VmeSaleFile(models.Model):
    _inherit = "vme.sale.file"

    welcome_communication_id = fields.Many2one("vme.communication", string="Welkomstbrief", readonly=True)

    def action_deed_done(self):
        result = super().action_deed_done()
        for sale in self:
            sale._create_welcome_letter()
        return result

    def _create_welcome_letter(self):
        """Draft welcome letter for the buyer, owner from the deed date; the employee checks and confirms it."""
        self.ensure_one()
        template = self.env.ref("vme_belgie.communication_template_welcome", raise_if_not_found=False)
        if not template or self.welcome_communication_id:
            return
        communication_model = self.env["vme.communication"]
        communication = communication_model.create({
            "association_id": self.association_id.id,
            "audience": "partners",
            "partner_ids": [Command.set(self.buyer_id.ids)],
            "reference_date": self.deed_date,
            "sale_file_id": self.id,
            "template_id": template.id,
            **communication_model._template_values(template),
        })
        communication.action_prepare_recipients()
        self.welcome_communication_id = communication
        self.message_post(body=Markup(self.env._("Concept-welkomstbrief voor %s klaargezet; nog niet verstuurd.")) % (
            communication._get_html_link(title=self.buyer_id.name)))

    def action_open_welcome_letter(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "vme.communication",
                "res_id": self.welcome_communication_id.id, "view_mode": "form", "views": [(False, "form")]}


class VmeAssemblyConvocation(models.Model):
    _inherit = "vme.assembly.convocation"

    @api.model_create_multi
    def create(self, vals_list):
        convocations = super().create(vals_list)
        self.env["vme.communication.log"]._log_records(
            convocations, "partner_id",
            subject=lambda c: self.env._("Oproeping AV %(year)s", year=c.assembly_id.year),
            channel=lambda c: "email" if c.partner_id.email and c.partner_id.vme_communication_preference != "paper" else "letter",
            lot_names=lambda c: c.lot_names,
        )
        return convocations

    def action_mark_sent(self):
        result = super().action_mark_sent()
        # Sent through the mail composer, or marked as sent by post.
        channel = "email" if self.env.context.get("mark_convocation_as_sent") else "letter"
        self.env["vme.communication.log"]._get_for_records(self).write({
            "state": "sent", "sent_date": fields.Date.context_today(self), "channel": channel})
        return result


class VmeCollectionReminder(models.Model):
    _inherit = "vme.collection.reminder"

    registered_mail_id = fields.Many2one("vme.registered.mail", string="Aangetekende zending", readonly=True)

    def action_mark_sent(self):
        result = super().action_mark_sent()
        Log = self.env["vme.communication.log"]
        via_email = self.env.context.get("mark_reminder_as_sent")
        for reminder in self:
            # LEGAL-CHECK: art. 5.231 BW - the formal notice (level 3) is sent by registered letter.
            channel = "registered" if reminder.level == "3" else ("email" if via_email else "letter")
            log = Log._log_records(reminder, "partner_id", subject=reminder.subject or reminder.display_name,
                                   channel=channel, state="sent",
                                   lot_names=lambda r: r.collection_id.lot_names)
            if reminder.level == "3":
                content, _ext = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
                    "vme_belgie.action_report_collection_reminder", reminder.ids)
                attachment = self.env["ir.attachment"].sudo().create({
                    "name": f"{reminder.subject or reminder.display_name}.pdf", "datas": base64.b64encode(content),
                    "mimetype": "application/pdf", "res_model": reminder._name, "res_id": reminder.id,
                })
                registered = self.env["vme.registered.mail"]._create_for(
                    log, attachment, reminder.subject or reminder.display_name)
                log.registered_mail_id = registered
                reminder.sudo().registered_mail_id = registered
        return result

    def action_send_registered(self):
        """Level 3: put the formal notice in the register of registered mail and mark it as sent."""
        if self.filtered(lambda r: r.level != "3"):
            raise UserError(self.env._("Alleen een ingebrekestelling gaat aangetekend."))
        self.action_mark_sent()
        if len(self) == 1:
            return {"type": "ir.actions.act_window", "res_model": "vme.registered.mail",
                    "res_id": self.registered_mail_id.id, "view_mode": "form", "views": [(False, "form")]}
        return True
