"""What an owner sees in the portal, and address changes that the syndic approves.

Portal users have no access rights on the VME models at all. The portal controllers read as
sudo, but only through the helpers below, which always start from the ownerships of the
logged-in partner.
"""
from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = "res.partner"

    vme_ownership_ids = fields.One2many("vme.ownership", "partner_id", string="Eigendommen")
    vme_address_request_ids = fields.One2many("vme.address.request", "partner_id", string="Adreswijzigingen")

    def _vme_owner(self):
        """The partner that holds the ownerships: the commercial entity of the user."""
        self.ensure_one()
        return self.commercial_partner_id

    def _vme_portal_ownerships(self):
        """All ownerships, current and past, of this partner."""
        self.ensure_one()
        return self.env["vme.ownership"].sudo().search([("partner_id", "=", self._vme_owner().id)])

    def _vme_portal_associations(self):
        return self._vme_portal_ownerships().association_id

    def _vme_portal_check_association(self, association_id):
        """The VME with this id if the partner owns or owned a lot in it, else an empty recordset."""
        return self._vme_portal_associations().filtered(lambda vme: vme.id == association_id)

    def _vme_portal_provisions(self, association):
        """Posted provision call invoices of this owner in this VME. Collection costs (step 10) are internal."""
        self.ensure_one()
        if association not in self._vme_portal_associations():
            return self.env["account.move"]
        return self.env["account.move"].sudo().search([
            ("company_id", "=", association.company_id.id),
            ("partner_id", "=", self._vme_owner().id),
            ("vme_provision_call_id", "!=", False),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
        ], order="invoice_date desc, id desc")

    def _vme_portal_statement_years(self, association):
        """Years with costs or provisions for this owner, most recent first."""
        self.ensure_one()
        if association not in self._vme_portal_associations():
            return []
        owner = self._vme_owner()
        years = set(self._vme_portal_provisions(association).vme_provision_call_id.budget_id.mapped("year"))
        allocations = self.env["vme.cost.allocation"].sudo().search([
            ("association_id", "=", association.id), ("partner_id", "=", owner.id),
            ("move_id.state", "=", "posted"),
        ])
        years |= {d.year for d in allocations.mapped("invoice_date") if d}
        return sorted(years, reverse=True)

    def _vme_portal_statement(self, association, year):
        """The annual statement of this owner only, or None."""
        self.ensure_one()
        if year not in self._vme_portal_statement_years(association):
            return None
        data = association.sudo()._get_annual_statement(year, partners=self._vme_owner())
        statement = data["statements"][0] if data["statements"] else None
        if not statement:
            return None
        return {"data": data, "statement": statement, "final": date(year, 12, 31) < fields.Date.context_today(self)}

    def _vme_portal_next_assembly(self, association):
        """The next ordinary assembly of a VME, for current owners only."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        current = self._vme_portal_ownerships().filtered(
            lambda o: o.association_id == association and (not o.date_end or o.date_end >= today)
        )
        if not current:
            return self.env["vme.assembly"]
        Assembly = self.env["vme.assembly"].sudo()
        return Assembly.search([
            ("association_id", "=", association.id),
            ("state", "in", ("proposed", "confirmed")),
            ("date", ">=", today),
        ], order="date", limit=1) or Assembly.search([
            ("association_id", "=", association.id),
            ("state", "=", "draft"),
            ("period_end", ">=", today),
        ], order="period_end", limit=1)

    def _vme_is_owner(self):
        return bool(self.env["vme.ownership"].sudo().search_count([("partner_id", "=", self.commercial_partner_id.id)]))

    def _can_be_edited_by_current_customer(self, **kwargs):
        # Owners change their address through a request that the syndic approves, never directly:
        # the register of owners must stay reliable (convocations, statements, the notary).
        if not self.env.user._is_internal() and self.sudo()._vme_is_owner():
            return False
        return super()._can_be_edited_by_current_customer(**kwargs)

    def action_vme_grant_portal(self):
        """Open Odoo's own portal wizard. It sends the invitation only when the syndic clicks."""
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Portaaltoegang"),
            "res_model": "portal.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"active_model": "res.partner", "active_ids": self.ids, "active_id": self.ids[:1] and self.ids[0]},
        }


class VmeOwnership(models.Model):
    _inherit = "vme.ownership"

    # The register of owners: current contact details of every owner.
    email = fields.Char(related="partner_id.email", string="E-mail")
    phone = fields.Char(related="partner_id.phone", string="Telefoon")
    contact_address = fields.Char(string="Adres", compute="_compute_contact_address")
    is_current = fields.Boolean(string="Huidige eigenaar", compute="_compute_is_current", search="_search_is_current")
    has_portal = fields.Boolean(string="Portaal", compute="_compute_has_portal")

    @api.depends("partner_id.street", "partner_id.zip", "partner_id.city")
    def _compute_contact_address(self):
        for ownership in self:
            partner = ownership.partner_id
            ownership.contact_address = ", ".join(filter(None, [
                partner.street, " ".join(filter(None, [partner.zip, partner.city]))]))

    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for ownership in self:
            ownership.is_current = ownership.date_start <= today and (not ownership.date_end or ownership.date_end >= today)

    def _search_is_current(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        today = fields.Date.context_today(self)
        domain = ["&", ("date_start", "<=", today), "|", ("date_end", "=", False), ("date_end", ">=", today)]
        return domain if (operator == "=") == value else ["!", *domain]

    def _compute_has_portal(self):
        for ownership in self:
            ownership.has_portal = bool(ownership.partner_id.sudo().user_ids.filtered(lambda u: u.active and u.share))

    def action_vme_grant_portal(self):
        return self.partner_id.action_vme_grant_portal()


ADDRESS_FIELDS = ["street", "street2", "zip", "city", "country_id", "phone", "email"]


class VmeAddressRequest(models.Model):
    _name = "vme.address.request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Adreswijziging van een eigenaar"
    _order = "create_date desc, id desc"

    partner_id = fields.Many2one("res.partner", string="Eigenaar", required=True, index=True, readonly=True)
    state = fields.Selection(
        [("to_approve", "Te keuren"), ("approved", "Goedgekeurd"), ("refused", "Geweigerd")],
        string="Status", default="to_approve", required=True, tracking=True, readonly=True,
    )
    street = fields.Char(string="Straat")
    street2 = fields.Char(string="Straat 2")
    zip = fields.Char(string="Postcode")
    city = fields.Char(string="Gemeente")
    country_id = fields.Many2one("res.country", string="Land")
    phone = fields.Char(string="Telefoon")
    email = fields.Char(string="E-mail")
    old_address = fields.Text(string="Huidige gegevens", readonly=True)
    refusal_reason = fields.Char(string="Reden van weigering")
    association_names = fields.Char(string="VME's", compute="_compute_association_names")

    @api.depends("partner_id")
    def _compute_association_names(self):
        for request in self:
            request.association_names = ", ".join(
                request.partner_id.sudo()._vme_portal_associations().mapped("name"))

    @api.model
    def _summary(self, partner):
        return "\n".join(filter(None, [
            partner.street, partner.street2, " ".join(filter(None, [partner.zip, partner.city])),
            partner.country_id.name, partner.phone, partner.email,
        ]))

    @api.model
    def _create_from_portal(self, partner, values):
        """Create a request for the owner and a to-do for the syndic. Nothing is sent."""
        vals = {key: values.get(key) or False for key in ADDRESS_FIELDS}
        country = str(vals["country_id"] or "")
        vals["country_id"] = int(country) if country.isdigit() and self.env["res.country"].browse(int(country)).exists() else False
        request = self.sudo().create({**vals, "partner_id": partner.id, "old_address": self._summary(partner)})
        request.activity_schedule(
            "mail.mail_activity_data_todo",
            summary=self.env._("Adreswijziging nakijken: %s", partner.name),
            user_id=self.env.ref("base.user_admin").id,
        )
        return request

    def action_approve(self):
        for request in self:
            if request.state != "to_approve":
                raise UserError(self.env._("Deze aanvraag is al behandeld."))
            request.partner_id.write({key: request[key].id if key == "country_id" else request[key]
                                      for key in ADDRESS_FIELDS if request[key]})
            request.state = "approved"
            request.activity_feedback(["mail.mail_activity_data_todo"])

    def action_refuse(self):
        for request in self:
            if request.state != "to_approve":
                raise UserError(self.env._("Deze aanvraag is al behandeld."))
            request.state = "refused"
            request.activity_feedback(["mail.mail_activity_data_todo"])

    @api.depends("partner_id")
    def _compute_display_name(self):
        for request in self:
            request.display_name = self.env._("Adreswijziging %s", request.partner_id.name or "")
