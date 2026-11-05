from odoo import api, fields, models


class VmeLot(models.Model):
    _inherit = "vme.lot"

    rent_contract_ids = fields.Many2many("vme.rent.contract", string="Huurcontracten",
                                         compute="_compute_rent_contracts")
    current_tenant_ids = fields.Many2many("res.partner", string="Huidige huurders", compute="_compute_rent_contracts")

    @api.depends_context("uid")
    def _compute_rent_contracts(self):
        contracts = self.env["vme.rent.contract"].search([("lot_ids", "in", self.ids)])
        for lot in self:
            own = contracts.filtered(lambda c: lot in c.lot_ids)
            lot.rent_contract_ids = own
            lot.current_tenant_ids = own.filtered(lambda c: c.state in ("active", "notice")).tenant_ids
