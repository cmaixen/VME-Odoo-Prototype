"""People living in a lot who are not its owner, and the register of keys and badges per lot."""
from odoo import api, fields, models
from odoo.exceptions import ValidationError

KEY_KINDS = [
    ("entrance_key", "Veiligheidssleutel inkom"),
    ("garage_key", "Sleutel garagepoort"),
    ("remote", "Afstandsbediening garagepoort"),
    ("badge", "Badge"),
]


class VmeLotContact(models.Model):
    _name = "vme.lot.contact"
    _description = "Contact van een kavel"
    _order = "lot_id, date_start desc"

    lot_id = fields.Many2one("vme.lot", string="Kavel", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="lot_id.association_id", store=True)
    company_id = fields.Many2one(related="lot_id.company_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Contact", required=True, index=True)
    email = fields.Char(related="partner_id.email")
    phone = fields.Char(related="partner_id.phone")
    # Lease contracts (step 25) link to a contact with the role tenant.
    role = fields.Selection(
        [("tenant", "Huurder"), ("occupant", "Bewoner"), ("contact", "Contactpersoon")],
        string="Rol", required=True, default="tenant",
    )
    date_start = fields.Date(string="Van", required=True, default=fields.Date.context_today)
    date_end = fields.Date(string="Tot", help="Leeg laten zolang deze persoon er woont.")
    active_today = fields.Boolean(string="Nu actief", compute="_compute_active_today")

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for contact in self:
            if contact.date_end and contact.date_end < contact.date_start:
                raise ValidationError(self.env._("De einddatum moet na de begindatum liggen."))

    def _compute_active_today(self):
        today = fields.Date.context_today(self)
        for contact in self:
            contact.active_today = contact._is_active_on(today)

    def _is_active_on(self, date):
        self.ensure_one()
        return self.date_start <= date and (not self.date_end or self.date_end >= date)


class VmeLotKey(models.Model):
    _name = "vme.lot.key"
    _description = "Uitgereikte sleutel of badge"
    _inherit = ["mail.thread"]
    _order = "lot_id, issue_date desc, id desc"

    lot_id = fields.Many2one("vme.lot", string="Kavel", required=True, ondelete="cascade", index=True)
    association_id = fields.Many2one(related="lot_id.association_id", store=True)
    company_id = fields.Many2one(related="lot_id.company_id", store=True)
    kind = fields.Selection(KEY_KINDS, string="Soort", required=True)
    number = fields.Char(string="Nummer", required=True, tracking=True)
    issue_date = fields.Date(string="Uitgereikt op", required=True, default=fields.Date.context_today)
    partner_id = fields.Many2one(
        "res.partner", string="In handen van", required=True, tracking=True,
        help="De persoon die de sleutel of badge nu heeft. Bij de akte gaat dit naar de koper.",
    )
    state = fields.Selection(
        [("active", "In gebruik"), ("blocked", "Geblokkeerd"), ("returned", "Ingeleverd")],
        string="Status", required=True, default="active", tracking=True,
    )
    blocked_date = fields.Date(string="Geblokkeerd op", readonly=True)
    request_id = fields.Many2one("vme.request", string="Aanvraag", readonly=True, index=True)
    note = fields.Char(string="Opmerking")

    @api.depends("kind", "number", "lot_id.name")
    def _compute_display_name(self):
        kinds = dict(KEY_KINDS)
        for key in self:
            key.display_name = f"{kinds.get(key.kind, '')} {key.number or ''} ({key.lot_id.name or ''})".strip()

    def action_block(self, request=None):
        today = fields.Date.context_today(self)
        for key in self.filtered(lambda k: k.state == "active"):
            key.write({"state": "blocked", "blocked_date": today})
            key.message_post(body=self.env._("Geblokkeerd%s.", request and self.env._(" na aanvraag %s", request.name) or ""))
        return True

    def action_return(self):
        self.filtered(lambda k: k.state == "active").state = "returned"
        return True

    def _transfer_to(self, partner, note):
        """Hand the active keys over to another person, e.g. the buyer at the deed."""
        for key in self.filtered(lambda k: k.state == "active"):
            key.partner_id = partner
            key.message_post(body=note)


class VmeLot(models.Model):
    _inherit = "vme.lot"

    contact_ids = fields.One2many("vme.lot.contact", "lot_id", string="Huurders en bewoners")
    key_register_ids = fields.One2many("vme.lot.key", "lot_id", string="Sleutels en badges")
    request_ids = fields.One2many("vme.request", "lot_id", string="Aanvragen")

    def _get_tenants_on(self, date):
        self.ensure_one()
        return self.contact_ids.filtered(lambda c: c.role == "tenant" and c._is_active_on(date)).partner_id


class VmeAssociation(models.Model):
    _inherit = "vme.association"

    # Supplier role per VME, like the maintenance company of an installation.
    locksmith_partner_id = fields.Many2one(
        "res.partner", string="Slotenmaker",
        help="Krijgt de bestellingen van sleutels, afstandsbedieningen en badges van deze VME.",
    )
    key_certificate_ref = fields.Char(
        string="Nummer sleutelcertificaat",
        help="Het certificaat van het sluitsysteem. Alleen de syndicus kan er veiligheidssleutels mee bestellen.",
    )
    key_certificate_file = fields.Binary(string="Kopie sleutelcertificaat", attachment=True)
    key_certificate_filename = fields.Char(string="Bestandsnaam sleutelcertificaat")
    request_ids = fields.One2many("vme.request", "association_id", string="Aanvragen")
    open_request_count = fields.Integer(string="Open aanvragen", compute="_compute_open_request_count")

    def _compute_open_request_count(self):
        counts = dict(self.env["vme.request"]._read_group(
            [("association_id", "in", self.ids), ("state", "not in", ("done", "refused", "cancelled"))],
            ["association_id"], ["__count"],
        ))
        for vme in self:
            vme.open_request_count = counts.get(vme, 0)

    def action_open_requests(self):
        action = self._action_open_related("vme.request", self.env._("Aanvragen"))
        action["context"] = {**action["context"], "search_default_open": 1}
        return action
