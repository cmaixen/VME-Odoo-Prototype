from odoo import api, fields, models


class VmeLot(models.Model):
    _name = "vme.lot"
    _description = "Kavel"
    _order = "association_id, sequence, name"

    name = fields.Char(string="Kavel", required=True)
    sequence = fields.Integer(default=10)
    association_id = fields.Many2one(
        "vme.association", string="VME", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="association_id.company_id", store=True)
    lot_type = fields.Selection(
        [
            ("apartment", "Appartement"),
            ("garage", "Garage"),
            ("storage", "Berging"),
            ("commercial", "Handelsruimte"),
            ("other", "Andere"),
        ],
        string="Type",
        required=True,
        default="apartment",
    )
    floor = fields.Char(string="Verdieping")
    ownership_ids = fields.One2many("vme.ownership", "lot_id", string="Eigendommen")
    current_owner_id = fields.Many2one(
        "res.partner", string="Huidige eigenaar", compute="_compute_current_owner"
    )

    _unique_name_per_association = models.Constraint(
        "UNIQUE (association_id, name)",
        "Elke kavel moet een unieke naam hebben binnen de VME.",
    )

    @api.depends("ownership_ids.partner_id", "ownership_ids.date_start", "ownership_ids.date_end")
    def _compute_current_owner(self):
        today = fields.Date.context_today(self)
        for lot in self:
            lot.current_owner_id = lot._get_owner_on(today)

    def _get_owner_on(self, date):
        """Return the owner of this lot on the given date (empty if none)."""
        self.ensure_one()
        ownership = self.ownership_ids.filtered(
            lambda o: o.date_start <= date and (not o.date_end or o.date_end >= date)
        )
        return ownership[:1].partner_id

    @api.depends("name", "association_id.name")
    def _compute_display_name(self):
        for lot in self:
            lot.display_name = (
                f"{lot.association_id.name} - {lot.name}" if lot.association_id else lot.name
            )
